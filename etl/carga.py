"""Carga v3 — escrita via funções RPC autenticadas por token do ETL.

Reescrita limpa (sem edições sobrepostas). As escritas passam pelas funções
public.etl_gravar / etl_podar / etl_registrar (SECURITY DEFINER), que validam
um token privado e só alcançam as seis tabelas da fundação.

Credenciais, todas via ambiente (secrets do GitHub Actions):
  • SUPABASE_URL          — Project URL do Supabase;
  • SUPABASE_ANON_KEY     — chave pública de leitura (header apikey/Authorization);
  • SUPABASE_SERVICE_KEY  — TOKEN do ETL (corpo p_token; não é a service_role).

O modo --dry não escreve nada remoto: materializa CSVs em out/ para inspeção.
"""
from __future__ import annotations
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

OUT = Path("out")


def _amb(nome: str) -> str:
    v = os.environ.get(nome, "")
    return v.strip()


def _rpc(funcao: str, corpo: dict) -> requests.Response:
    url = _amb("SUPABASE_URL").rstrip("/")
    anon = _amb("SUPABASE_ANON_KEY")
    token = _amb("SUPABASE_SERVICE_KEY")
    headers = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
        "Content-Type": "application/json",
    }
    dados = json.dumps({"p_token": token, **corpo}, default=str)
    resposta = None
    for tentativa in range(5):
        resposta = requests.post(f"{url}/rest/v1/rpc/{funcao}",
                                 headers=headers, data=dados, timeout=180)
        if resposta.status_code in (200, 201, 204):
            return resposta
        if resposta.status_code == 401 and tentativa == 0:
            # Diagnóstico não-vazante: comprova o que o runner recebeu, sem expor segredo.
            print(f"[DIAG] 401 em {funcao}", file=sys.stderr)
            print(f"[DIAG] ANON len={len(anon)} head={anon[:12]!r} tail={anon[-6:]!r}",
                  file=sys.stderr)
            print(f"[DIAG] TOKEN len={len(token)} head={token[:6]!r} tail={token[-4:]!r}",
                  file=sys.stderr)
            print(f"[DIAG] URL={url!r}", file=sys.stderr)
        time.sleep(min(2 ** tentativa, 30))
    corpo_erro = resposta.text[:300] if resposta is not None else "sem resposta"
    codigo = resposta.status_code if resposta is not None else "?"
    raise RuntimeError(f"rpc {funcao}: HTTP {codigo} — {corpo_erro}")


def upsert(tabela: str, linhas: list[dict], pk: str, dt_carga: str,
           dry: bool = False, lote: int = 800) -> int:
    for r in linhas:
        r["dt_carga"] = dt_carga
    if dry:
        OUT.mkdir(exist_ok=True)
        if linhas:
            with open(OUT / f"{tabela}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
                w.writeheader()
                w.writerows(linhas)
        return len(linhas)
    for i in range(0, len(linhas), lote):
        _rpc("etl_gravar", {"p_tabela": tabela, "p_conflito": pk,
                            "p_linhas": linhas[i:i + lote]})
    return len(linhas)


def prune(tabela: str, dt_carga: str, extra: str = "", dry: bool = False) -> None:
    if dry:
        return
    ano_min = int(extra.split("gte.")[1]) if "gte." in extra else None
    _rpc("etl_podar", {"p_tabela": tabela, "p_dt": dt_carga, "p_ano_min": ano_min})


def registrar_carga(fonte: str, url_fonte: str, sha256: str, linhas: int,
                    status: str, detalhe: str = "", dry: bool = False) -> None:
    if dry:
        print(f"  [dry] ans_cargas ← {fonte}: {status} ({linhas} linhas)")
        return
    _rpc("etl_registrar", {"p_fonte": fonte, "p_url": url_fonte,
                           "p_sha256": sha256, "p_linhas": linhas,
                           "p_status": status, "p_detalhe": detalhe[:900]})
