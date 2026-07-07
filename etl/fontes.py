"""Aquisição das fontes ANS com proveniência e normalização de encoding.

Todos os arquivos são persistidos em UTF-8 (os datasets do PDA são de encoding
misto: PDA-008 e PDA-055 chegam em UTF-8; RPC e NTRP/VCM, em Latin-1). A detecção
é automática por tentativa de decodificação, e a conversão ocorre no disco, uma
única vez, imediatamente após o download.
"""
from __future__ import annotations
import hashlib, os, shutil, zipfile
from datetime import date
from pathlib import Path
import requests
from .config import (FONTES, UA, RPC_CONSOLIDADOS, RPC_MENSAL_INICIO,
                     JANELA_MESES, MESES_TOLERADOS_404)

# Modo local (--local DIR): mapeia fontes para arquivos já baixados em sessões
# de desenvolvimento, dispensando rede. Nomes reais têm precedência sobre aliases.
ALIASES_LOCAIS = {
    "pda-008-caracteristicas_produtos_saude_suplementar.csv": ["prod008.bin"],
    "pda-055-Percentuais_de_Reajuste_de_Agrupamento.csv": ["pool055.csv"],
    "pda-043-rpc-202601.csv": ["rpc01.csv"],
}


def _garantir_utf8(path: Path) -> None:
    """Converte o arquivo para UTF-8 in place quando ele não decodifica como UTF-8."""
    with open(path, "rb") as f:
        amostra = f.read(1 << 20)
    try:
        amostra[: max(0, len(amostra) - 4)].decode("utf-8")
        return
    except UnicodeDecodeError:
        pass
    tmp = path.with_suffix(path.suffix + ".utf8")
    with open(path, "r", encoding="latin-1", newline="") as f, \
         open(tmp, "w", encoding="utf-8", newline="") as g:
        shutil.copyfileobj(f, g, length=1 << 20)
    os.replace(tmp, path)


def _sha256_e_linhas(path: Path) -> tuple[str, int]:
    h = hashlib.sha256(); linhas = 0
    with open(path, "rb") as f:
        while bloco := f.read(1 << 20):
            h.update(bloco); linhas += bloco.count(b"\n")
    return h.hexdigest(), linhas


def baixar(url: str, destino: Path, local_dir: Path | None = None,
           tolerar_404: bool = False) -> dict | None:
    """Baixa (ou copia do modo local) um arquivo, normaliza para UTF-8 e devolve
    proveniência {path, sha256, linhas, url}. Devolve None em 404 tolerado."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    nome = destino.name
    if local_dir:
        candidatos = [local_dir / nome] + [local_dir / a for a in ALIASES_LOCAIS.get(nome, [])]
        for c in candidatos:
            if c.exists():
                shutil.copyfile(c, destino)
                _garantir_utf8(destino)
                sha, linhas = _sha256_e_linhas(destino)
                return {"path": destino, "sha256": sha, "linhas": linhas, "url": f"local:{c}"}
        return None if tolerar_404 else (_ for _ in ()).throw(
            FileNotFoundError(f"modo local sem {nome}"))
    with requests.get(url, headers=UA, stream=True, timeout=600) as r:
        if r.status_code == 404 and tolerar_404:
            return None
        r.raise_for_status()
        with open(destino, "wb") as f:
            for bloco in r.iter_content(1 << 20):
                f.write(bloco)
    _garantir_utf8(destino)
    sha, linhas = _sha256_e_linhas(destino)
    return {"path": destino, "sha256": sha, "linhas": linhas, "url": url}



def _baixar_zip_integro(url: str, destino: Path, tentativas: int = 4) -> dict:
    """Baixa um ZIP validando a integridade (testzip); refaz em truncamento de rede."""
    import time as _t
    ultimo = None
    for k in range(tentativas):
        try:
            with requests.get(url, headers=UA, stream=True, timeout=900) as r:
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for bloco in r.iter_content(1 << 20):
                        f.write(bloco)
            with zipfile.ZipFile(destino) as z:
                if z.testzip() is not None:
                    raise zipfile.BadZipFile("CRC inválido em membro do zip")
            sha = hashlib.sha256(destino.read_bytes()).hexdigest()
            return {"sha256": sha, "bytes": destino.stat().st_size}
        except (zipfile.BadZipFile, requests.RequestException, OSError) as e:
            ultimo = e
            _t.sleep(min(2 ** k, 20))
    raise RuntimeError(f"zip corrompido após {tentativas} tentativas: {ultimo}")


def obter_ntrp(workdir: Path, local_dir: Path | None = None) -> tuple[list[Path], dict]:
    """Obtém os CSVs anuais da NTRP/VCM. No modo local aceita a pasta vcm/ já extraída."""
    if local_dir and (local_dir / "vcm").is_dir():
        arquivos = sorted((local_dir / "vcm").glob("*.csv"))
        alvo = workdir / "ntrp"; alvo.mkdir(parents=True, exist_ok=True)
        paths = []
        for a in arquivos:
            d = alvo / a.name
            shutil.copyfile(a, d); _garantir_utf8(d); paths.append(d)
        return paths, {"url": f"local:{local_dir/'vcm'}", "sha256": "-", "linhas": sum(1 for _ in paths)}
    zpath = workdir / "nota_tecnica_vcm_faixa_etaria.zip"
    meta = _baixar_zip_integro(FONTES["ntrp_zip"], zpath)
    prov = {"url": FONTES["ntrp_zip"], "sha256": meta["sha256"], "linhas": 0}
    alvo = workdir / "ntrp"; alvo.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(alvo)
    paths = sorted(alvo.glob("*.csv"))
    for p in paths:
        _garantir_utf8(p)
    prov["path"] = alvo
    return paths, prov


def mensais_alvo(backfill: bool, hoje: date | None = None) -> list[int]:
    """Lista de competências AAAAMM do RPC a processar."""
    hoje = hoje or date.today()
    fim = hoje.year * 100 + hoje.month
    todos = []
    a, m = divmod(RPC_MENSAL_INICIO, 100)
    while a * 100 + m <= fim:
        todos.append(a * 100 + m)
        m += 1
        if m == 13:
            a, m = a + 1, 1
    if backfill:
        return todos
    return todos[-JANELA_MESES:]


def obter_rpc(workdir: Path, backfill: bool, local_dir: Path | None = None) -> tuple[list[dict], list[int]]:
    """Baixa os arquivos RPC do escopo (consolidados no backfill + mensais da janela).
    Devolve (lista de proveniências com paths, competências efetivamente obtidas)."""
    alvo = workdir / "rpc"; alvo.mkdir(parents=True, exist_ok=True)
    provs, comps = [], []
    if backfill:
        for nome in RPC_CONSOLIDADOS:
            p = baixar(f"{FONTES['rpc_dir']}/{nome}", alvo / nome, local_dir,
                       tolerar_404=bool(local_dir))
            if p:
                provs.append(p)
    alvos = mensais_alvo(backfill)
    for i, comp in enumerate(alvos):
        nome = f"pda-043-rpc-{comp}.csv"
        recente = i >= len(alvos) - MESES_TOLERADOS_404
        p = baixar(f"{FONTES['rpc_dir']}/{nome}", alvo / nome, local_dir,
                   tolerar_404=recente or bool(local_dir))
        if p:
            provs.append(p); comps.append(comp)
    return provs, comps
