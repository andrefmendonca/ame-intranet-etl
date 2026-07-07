"""Carga v2 — escrita via funções RPC autenticadas por token do ETL.

A service_role foi aposentada deste repositório: as escritas passam pelas
funções public.etl_gravar / etl_podar / etl_registrar (SECURITY DEFINER),
que validam um token privado e só alcançam as seis tabelas da fundação —
menor privilégio que a chave-mestra, mesmo padrão last-good de antes.

O secret SUPABASE_SERVICE_KEY do GitHub passa a guardar o TOKEN do ETL
(o mesmo valor inserido em private.etl_token via Lovable). A chave pública
de leitura (publishable) é embutida abaixo — pública por construção.
"""
from __future__ import annotations
import csv, json, os, time
from pathlib import Path
import requests

OUT = Path("out")
ANON = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRoa2N2andnZWtuZXZleGx0d2RnIiwi"
        "cm9sZSI6ImFub24iLCJpYXQiOjE3ODMzOTEzMTAsImV4cCI6MjA5ODk2NzMxMH0."
        "ZU67b2O7-StvJR-ATrLY57qZki6ns8_5mlKLG_I-2rk")


def _rpc(funcao: str, corpo: dict) -> requests.Response:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    token = os.environ["SUPABASE_SERVICE_KEY"]  # token do ETL (não é mais a service_role)
    h = {"apikey": ANON, "Authorization": f"Bearer {ANON}",
         "Content-Type": "application/json"}
    dados = json.dumps({"p_token": token, **corpo}, default=str)
    for tentativa in range(5):
        r = requests.post(f"{url}/rest/v1/rpc/{funcao}", headers=h,
                          data=dados, timeout=180)
        if r.status_code in (200, 201, 204):
            return r
        time.sleep(min(2 ** tentativa, 30))
    raise RuntimeError(f"rpc {funcao}: HTTP {r.status_code} — {r.text[:300]}")


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
