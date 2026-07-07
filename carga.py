"""Carga no Supabase via PostgREST (service role) com semântica last-good.

Padrão upsert-then-prune: todas as linhas do run recebem o mesmo dt_carga;
o upsert por chave primária torna a operação idempotente e segura contra
duplicatas; a poda (delete de dt_carga anterior) só ocorre após o upsert
completo bem-sucedido — em falha parcial, o snapshot anterior permanece
íntegro e a fonte é marcada como 'falha' em ans_cargas.

Modo --dry: nenhuma escrita remota; as linhas viram CSVs em out/ para
inspeção e validação local.
"""
from __future__ import annotations
import csv, json, os, time
from pathlib import Path
import requests

OUT = Path("out")


def _cfg() -> tuple[str, dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}",
         "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates,return=minimal"}
    return url, h


def upsert(tabela: str, linhas: list[dict], pk: str, dt_carga: str,
           dry: bool = False, lote: int = 800) -> int:
    for r in linhas:
        r["dt_carga"] = dt_carga
    if dry:
        OUT.mkdir(exist_ok=True)
        if linhas:
            with open(OUT / f"{tabela}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
                w.writeheader(); w.writerows(linhas)
        return len(linhas)
    url, h = _cfg()
    alvo = f"{url}/rest/v1/{tabela}?on_conflict={pk}"
    for i in range(0, len(linhas), lote):
        bloco = json.dumps(linhas[i:i + lote], default=str)
        for tentativa in range(5):
            r = requests.post(alvo, headers=h, data=bloco, timeout=180)
            if r.status_code in (200, 201, 204):
                break
            time.sleep(min(2 ** tentativa, 30))
        else:
            raise RuntimeError(f"{tabela}: HTTP {r.status_code} — {r.text[:300]}")
    return len(linhas)


def prune(tabela: str, dt_carga: str, extra: str = "", dry: bool = False) -> None:
    """Remove o snapshot anterior (dt_carga < run atual), opcionalmente restrito
    por filtro extra PostgREST (ex.: 'ano=gte.2025' na janela móvel do RPC)."""
    if dry:
        return
    url, h = _cfg()
    alvo = f"{url}/rest/v1/{tabela}?dt_carga=lt.{dt_carga}" + (f"&{extra}" if extra else "")
    r = requests.delete(alvo, headers=h, timeout=600)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"prune {tabela}: HTTP {r.status_code} — {r.text[:300]}")


def registrar_carga(fonte: str, url_fonte: str, sha256: str, linhas: int,
                    status: str, detalhe: str = "", dry: bool = False) -> None:
    registro = {"fonte": fonte, "url": url_fonte, "sha256": sha256,
                "linhas": linhas, "status": status, "detalhe": detalhe[:900]}
    if dry:
        print(f"  [dry] ans_cargas ← {registro}")
        return
    url, h = _cfg()
    r = requests.post(f"{url}/rest/v1/ans_cargas", headers=h,
                      data=json.dumps(registro), timeout=60)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"ans_cargas: HTTP {r.status_code} — {r.text[:300]}")
