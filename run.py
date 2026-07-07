#!/usr/bin/env python3
"""Orquestrador do ETL ANS — Intranet AME.

Uso:
  python run.py                       # run mensal (janela móvel do RPC)
  python run.py --backfill            # recarga histórica completa (primeiro run)
  python run.py --dry --local /tmp    # desenvolvimento: sem rede/escrita, CSVs em out/
  python run.py --fase ntrp           # executa uma única fase

Fases: produtos, operadoras, indice_individual, pool, ntrp, rpc (ordem padrão).
Saída ≠ 0 quando qualquer fase falha (o Actions fica vermelho); as fases
independentes prosseguem e cada uma registra proveniência em ans_cargas.
"""
from __future__ import annotations
import argparse, hashlib, sys, traceback
from datetime import datetime, timezone
from pathlib import Path

from etl.config import FONTES
from etl import fontes, transforms
from etl.carga import upsert, prune, registrar_carga

SEED_DIR = Path(transforms.__file__).parent / "seeds"

FASES = ["produtos", "operadoras", "indice_individual", "pool", "ntrp", "rpc"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--local", type=Path, default=None)
    ap.add_argument("--fase", choices=FASES + ["all"], default="all")
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc).isoformat()
    work = Path("work"); work.mkdir(exist_ok=True)
    fases = FASES if args.fase == "all" else [args.fase]
    resumo, falhas = [], []

    for fase in fases:
        try:
            if fase == "produtos":
                prov = fontes.baixar(FONTES["produtos"], work / FONTES["produtos"].rsplit("/", 1)[-1], args.local)
                linhas = transforms.t_produtos(prov["path"])
                n = upsert("ans_produtos", linhas, "id_plano", run_ts, args.dry)
                prune("ans_produtos", run_ts, dry=args.dry)
                registrar_carga("PDA-008 produtos", prov["url"], prov["sha256"],
                                n, "ok", dry=args.dry)
                resumo.append((fase, n))

            elif fase == "operadoras":
                pa = fontes.baixar(FONTES["operadoras_ativas"],
                                   work / "Relatorio_cadop.csv", args.local)
                pc = fontes.baixar(FONTES["operadoras_canceladas"],
                                   work / "Relatorio_cadop_canceladas.csv", args.local)
                linhas = transforms.t_operadoras(pa["path"], pc["path"])
                n = upsert("ans_operadoras", linhas, "registro_operadora", run_ts, args.dry)
                prune("ans_operadoras", run_ts, dry=args.dry)
                registrar_carga("CADOP operadoras", pa["url"], pa["sha256"],
                                n, "ok", detalhe=f"ativas+canceladas; sha canceladas {pc['sha256'][:12]}",
                                dry=args.dry)
                resumo.append((fase, n))

            elif fase == "indice_individual":
                seed = SEED_DIR / "indice_individual.csv"
                linhas = transforms.t_indice_individual(seed)
                sha = hashlib.sha256(seed.read_bytes()).hexdigest()
                n = upsert("ans_indice_individual", linhas, "ciclo", run_ts, args.dry)
                prune("ans_indice_individual", run_ts, dry=args.dry)
                registrar_carga("SEED indice individual (ANS)",
                                "repo:etl/seeds/indice_individual.csv", sha,
                                n, "ok", dry=args.dry)
                resumo.append((fase, n))

            elif fase == "pool":
                prov = fontes.baixar(FONTES["pool"], work / FONTES["pool"].rsplit("/", 1)[-1], args.local)
                linhas = transforms.t_pool(prov["path"])
                n = upsert("ans_pool", linhas,
                           "registro_operadora,ciclo,tp_agrupamento", run_ts, args.dry)
                prune("ans_pool", run_ts, dry=args.dry)
                registrar_carga("PDA-055 pool", prov["url"], prov["sha256"],
                                n, "ok", dry=args.dry)
                resumo.append((fase, n))

            elif fase == "ntrp":
                paths, prov = fontes.obter_ntrp(work, args.local)
                linhas = transforms.t_ntrp(paths)
                n = upsert("ans_ntrp_faixas", linhas, "id_plano,dt_ntrp", run_ts, args.dry)
                prune("ans_ntrp_faixas", run_ts, dry=args.dry)
                registrar_carga("NTRP/VCM faixa etária", prov["url"], prov["sha256"],
                                n, "ok", detalhe=f"{len(paths)} arquivos anuais",
                                dry=args.dry)
                resumo.append((fase, n))

            elif fase == "rpc":
                provs, comps = fontes.obter_rpc(work, args.backfill, args.local)
                if not provs:
                    raise RuntimeError("nenhum arquivo RPC obtido")
                agregado, brutos, anos = transforms.t_rpc([p["path"] for p in provs], work)
                n1 = upsert("ans_rpc_agregado", agregado,
                            "id_plano,sg_uf,ano,cd_agrupamento", run_ts, args.dry)
                n2 = upsert("ans_rpc_contratos_ba", brutos,
                            "id_contrato,dt_inicio", run_ts, args.dry)
                extra = "" if args.backfill else f"ano=gte.{min(anos)}"
                prune("ans_rpc_agregado", run_ts, extra, dry=args.dry)
                prune("ans_rpc_contratos_ba", run_ts, extra, dry=args.dry)
                registrar_carga(
                    "PDA-043 RPC", FONTES["rpc_dir"], "-", n1 + n2, "ok",
                    detalhe=f"{len(provs)} arquivos; competências {comps[:1]}…{comps[-1:]}; "
                            f"anos {anos[0]}–{anos[-1]}; agregado={n1}; brutos_ba={n2}",
                    dry=args.dry)
                resumo.append((fase, n1 + n2))

        except Exception as e:  # noqa: BLE001 — fase falha isolada, run prossegue
            traceback.print_exc()
            falhas.append(fase)
            try:
                registrar_carga(fase, "-", "-", 0, "falha", detalhe=str(e), dry=args.dry)
            except Exception:
                print(f"  !! impossível registrar falha de {fase} em ans_cargas")

    print("\n== RESUMO DO RUN ==")
    for fase, n in resumo:
        print(f"  {fase:10s} {n:>10,} linhas")
    if falhas:
        print(f"  FALHAS: {', '.join(falhas)}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
