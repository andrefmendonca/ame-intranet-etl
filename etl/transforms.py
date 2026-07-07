"""Transformações das fontes ANS para as tabelas canônicas da intranet.

Regras validadas empiricamente na sessão de fundação (07/07/2026):
  • ans_ntrp_faixas — deduplicação por (id_plano, dt_ntrp): 99,70% das notas da
    mesma data compartilham o mesmo vetor de percentuais entre faixas (variantes
    regionais mudam o nível de preço, não a estrutura). Guarda-se uma nota de
    referência com os VCMs brutos, o vetor derivado v1..v9 e os testes do
    art. 3º, I e II, da RN nº 63/2003 pré-computados.
  • ans_rpc_agregado — exclui avisos "em negociação" (LG_NEGOCIACAO=1, conforme
    dicionário oficial do PDA-043); agrega por plano × UF × ano × agrupamento.
  • ans_rpc_contratos_ba — linhas brutas apenas da UF configurada (espelho RPC:
    localizar o contrato do cliente e o seu mês de aniversário).
"""
from __future__ import annotations
import csv, re
from collections import defaultdict
from pathlib import Path
from .config import TOP_OPERADORAS, UF_BRUTO, LOTE_ARQUIVOS_RPC

_FAIXAS = ["00 a 18", "19 a 23", "24 a 28", "29 a 33", "34 a 38",
           "39 a 43", "44 a 48", "49 a 53", "54 a 58", "59 anos"]
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")


def _txt(v: str | None) -> str | None:
    v = (v or "").strip().strip('"').strip()
    return v or None


def _num(v: str | None) -> float | None:
    v = _txt(v)
    if not v:
        return None
    try:
        return float(v.replace(".", "").replace(",", ".")) if ("," in v) else float(v)
    except ValueError:
        return None


def _inteiro(v: str | None) -> int | None:
    v = _txt(v)
    try:
        return int(float(v)) if v else None
    except ValueError:
        return None


def _data_iso(v: str | None) -> str | None:
    v = _txt(v)
    if not v:
        return None
    if _ISO.match(v):
        return v[:10]
    m = _BR.match(v)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


# ----------------------------------------------------------------------------- produtos
def t_produtos(path: Path) -> list[dict]:
    saida, vistos = [], set()
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        cab = [c.strip().lower() for c in next(r)]
        idx = {c: i for i, c in enumerate(cab)}
        datas = {"dt_situacao", "dt_registro_plano", "dt_atualizacao"}
        for row in r:
            if len(row) < len(cab):
                continue
            pid = _inteiro(row[idx["id_plano"]])
            if pid is None or pid in vistos:
                continue
            vistos.add(pid)
            reg = {"id_plano": pid}
            for c in cab[1:]:
                v = row[idx[c]]
                reg[c] = _data_iso(v) if c in datas else _txt(v)
            saida.append(reg)
    return saida


# --------------------------------------------------------------------------------- pool
def t_pool(path: Path) -> list[dict]:
    saida, vistos = [], set()
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        next(r)
        for row in r:
            if len(row) < 10:
                continue
            chave = (_txt(row[0]), _inteiro(row[1]), _txt(row[2]) or "Único")
            if None in chave[:2] or chave in vistos:
                continue
            vistos.add(chave)
            saida.append({
                "registro_operadora": chave[0], "ciclo": chave[1],
                "tp_agrupamento": chave[2],
                "pct_unico": _num(row[3]), "pct_ambulatorial": _num(row[4]),
                "pct_int_sem_obstet": _num(row[5]), "pct_int_com_obstet": _num(row[6]),
                "qt_contratos": _inteiro(row[7]), "qt_benef": _inteiro(row[8]),
                "razao_social": _txt(row[9]),
            })
    return saida


# --------------------------------------------------------------------------------- ntrp
def t_ntrp(paths: list[Path]) -> list[dict]:
    """Deduplica as notas em vintages (id_plano, dt_ntrp) para TODAS as operadoras."""
    def faixa_idx(rotulo: str) -> int | None:
        for i, p in enumerate(_FAIXAS):
            if rotulo.startswith(p):
                return i
        return None

    vcm: dict[str, list] = {}
    meta: dict[str, tuple] = {}
    for fp in paths:
        with open(fp, encoding="utf-8", newline="") as f:
            next(f)
            for linha in f:
                p = linha.rstrip("\n").split(";")
                if len(p) < 7:
                    continue
                i = faixa_idx(p[5].strip('"'))
                if i is None:
                    continue
                try:
                    v = float(p[6])
                except ValueError:
                    continue
                nota = p[2].strip()
                vcm.setdefault(nota, [None] * 10)[i] = v
                if nota not in meta:
                    meta[nota] = (p[1].strip(), _data_iso(p[3]), _txt(p[4]))

    grupos: dict[tuple, list[str]] = defaultdict(list)
    for nota, valores in vcm.items():
        if all(x is not None and x > 0 for x in valores):
            pid, dt, _ = meta[nota]
            if pid and dt:
                grupos[(pid, dt)].append(nota)

    saida = []
    for (pid, dt), notas in grupos.items():
        ref = min(notas, key=lambda n: int(n) if n.isdigit() else 0)
        vs = vcm[ref]
        vetor = [round(100 * (vs[i + 1] / vs[i] - 1), 3) for i in range(9)]
        razao = round(vs[9] / vs[0], 3)
        a17 = round(100 * (vs[6] / vs[0] - 1), 3)
        a710 = round(100 * (vs[9] / vs[6] - 1), 3)
        reg = {"id_plano": int(pid), "dt_ntrp": dt, "n_notas": len(notas),
               "cd_nota_ref": int(ref), "abrangencia": meta[ref][2]}
        reg |= {f"vcm_f{i+1}": round(vs[i], 2) for i in range(10)}
        reg |= {f"v{i+1}": vetor[i] for i in range(9)}
        reg |= {"razao_ultima_primeira": razao, "var_acum_1a7": a17,
                "var_acum_7a10": a710,
                "rn63_art3_i": razao <= 6.0 + 1e-9,
                "rn63_art3_ii": a710 <= a17 + 1e-6}
        saida.append(reg)
    return saida


# ---------------------------------------------------------------------------------- rpc
def t_rpc(paths: list[Path], workdir: Path) -> tuple[list[dict], list[dict], list[int]]:
    """Agrega o RPC (DuckDB, com spill em disco) e extrai as linhas brutas da UF alvo.
    Devolve (agregado, brutos_uf, anos_processados)."""
    import duckdb
    con = duckdb.connect(str(workdir / "rpc.duckdb"))
    con.execute("DROP TABLE IF EXISTS r")
    top = sorted(TOP_OPERADORAS)
    base_sel = """
        SELECT try_cast(ID_PLANO AS BIGINT)                        AS id_plano,
               trim(ID_CONTRATO)                                   AS id_contrato,
               lpad(trim(CD_OPERADORA), 6, '0')                    AS cd_op,
               try_cast(DT_INIC_APLICACAO AS DATE)                 AS dt_inicio,
               try_cast(replace(PC_PERCENTUAL, ',', '.') AS DOUBLE) AS pct,
               try_cast(QT_BENEF_COMUNICADO AS INTEGER)            AS qt,
               coalesce(nullif(trim(SG_UF_CONTRATO_REAJ), ''), 'ND') AS uf,
               coalesce(try_cast(CD_AGRUPAMENTO AS SMALLINT), 0)   AS agrup,
               (trim(LG_PARCELADO) = '1')                          AS parcelado,
               (trim(LG_NEGOCIACAO) = '1')                         AS negociacao
        FROM read_csv({fontes}, delim=';', header=true, all_varchar=true,
                      union_by_name=true, ignore_errors=true)
    """
    criado = False
    for i in range(0, len(paths), LOTE_ARQUIVOS_RPC):
        lote = [str(p) for p in paths[i:i + LOTE_ARQUIVOS_RPC]]
        sel = base_sel.format(fontes=lote)
        con.execute(("CREATE TABLE r AS " if not criado else "INSERT INTO r ") + sel)
        criado = True

    def _dicts(res) -> list[dict]:
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, t)) for t in res.fetchall()]

    filtro_top = "cd_op IN (" + ",".join(f"'{c}'" for c in top) + ")"
    agregado = _dicts(con.execute(f"""
        SELECT id_plano, uf AS sg_uf, year(dt_inicio) AS ano, agrup AS cd_agrupamento,
               count(*)::INT AS n_comunicados, sum(qt)::BIGINT AS n_benef,
               round(median(pct), 2) AS pct_mediana,
               round(quantile_cont(pct, 0.25), 2) AS pct_p25,
               round(quantile_cont(pct, 0.75), 2) AS pct_p75
        FROM r
        WHERE NOT negociacao AND pct IS NOT NULL AND dt_inicio IS NOT NULL
              AND id_plano IS NOT NULL AND {filtro_top}
        GROUP BY 1, 2, 3, 4
    """))

    brutos = _dicts(con.execute(f"""
        SELECT id_contrato, id_plano, dt_inicio, year(dt_inicio) AS ano,
               month(dt_inicio) AS mes_inicio, qt AS qt_benef, round(pct, 2) AS pct,
               agrup AS cd_agrupamento, parcelado AS lg_parcelado,
               negociacao AS lg_negociacao
        FROM r
        WHERE uf = '{UF_BRUTO}' AND dt_inicio IS NOT NULL AND id_contrato IS NOT NULL
              AND {filtro_top}
        QUALIFY row_number() OVER (PARTITION BY id_contrato, dt_inicio
                                   ORDER BY pct DESC NULLS LAST) = 1
    """))

    anos = [x[0] for x in con.execute(
        "SELECT DISTINCT year(dt_inicio) FROM r WHERE dt_inicio IS NOT NULL ORDER BY 1"
    ).fetchall()]
    con.close()
    for reg in agregado + brutos:
        for k, v in list(reg.items()):
            if hasattr(v, "isoformat"):
                reg[k] = v.isoformat()
    return agregado, brutos, anos


def t_operadoras(path_ativas: Path, path_canceladas: Path) -> list[dict]:
    """Cadastro de operadoras (CADOP ativas + canceladas).

    Canceladas entram primeiro; ativas sobrescrevem por registro (se uma
    operadora constar em ambos os arquivos, prevalece o cadastro ativo).
    Registro vem zero-padded na fonte (ex.: "005711") — preservado como texto.
    """
    def _ler(path: Path, situacao: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                reg = _txt(r.get("REGISTRO_OPERADORA"))
                if not reg:
                    continue
                out[reg] = {
                    "registro_operadora": reg.zfill(6),
                    "cnpj": _txt(r.get("CNPJ")),
                    "razao_social": _txt(r.get("Razao_Social")),
                    "nome_fantasia": _txt(r.get("Nome_Fantasia")),
                    "modalidade": _txt(r.get("Modalidade")),
                    "logradouro": _txt(r.get("Logradouro")),
                    "numero": _txt(r.get("Numero")),
                    "complemento": _txt(r.get("Complemento")),
                    "bairro": _txt(r.get("Bairro")),
                    "cidade": _txt(r.get("Cidade")),
                    "uf": _txt(r.get("UF")),
                    "cep": _txt(r.get("CEP")),
                    "ddd": _txt(r.get("DDD")),
                    "telefone": _txt(r.get("Telefone")),
                    "fax": _txt(r.get("Fax")),
                    "endereco_eletronico": _txt(r.get("Endereco_eletronico")),
                    "representante": _txt(r.get("Representante")),
                    "cargo_representante": _txt(r.get("Cargo_Representante")),
                    "regiao_comercializacao": _inteiro(r.get("Regiao_de_Comercializacao")),
                    "dt_registro_ans": _data_iso(r.get("Data_Registro_ANS")),
                    "dt_descredenciamento": _data_iso(r.get("Data_Descredenciamento")),
                    "motivo_descredenciamento": _txt(r.get("Motivo_do_Descredenciamento")),
                    "situacao": situacao,
                }
        return out

    consolidado = _ler(path_canceladas, "Cancelada")
    consolidado.update(_ler(path_ativas, "Ativa"))
    return list(consolidado.values())


def t_indice_individual(path: Path) -> list[dict]:
    """Índice de reajuste anual dos planos individuais/familiares novos (ANS).

    Teto máximo autorizado pela ANS para contratos individuais/familiares
    firmados a partir de 01/01/1999 ou adaptados à Lei nº 9.656/98. Série
    curta e de atualização anual — mantida como seed versionado no repositório
    (não há PDA estruturado para este índice na base de Dados Abertos da ANS).
    O percentual pode ser negativo (ciclo 2021, reajuste negativo pós-Covid).
    A vigência (maio do ciclo a abril do ano seguinte) é determinística e
    derivada na apresentação a partir do ciclo.
    """
    out: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ciclo = _inteiro(r.get("ciclo"))
            if ciclo is None:
                continue
            out.append({
                "ciclo": ciclo,
                "percentual": _num(r.get("percentual")),
                "observacao": _txt(r.get("observacao")),
                "fonte": _txt(r.get("fonte")),
            })
    return out


def t_reajuste_planos_antigos(path: Path) -> list[dict]:
    """Reajustes autorizados por Termo de Compromisso (TC) — planos ANTIGOS.

    Aplica-se somente a contratos individuais/familiares firmados até 31/12/1998,
    NÃO adaptados à Lei 9.656/98, cuja cláusula de reajuste seja omissa ou não
    traga índice claro e explícito — e apenas às operadoras SIGNATÁRIAS de TC com
    a ANS. O percentual é o TETO autorizado do ciclo; aplicá-lo acima caracteriza
    descumprimento do TC (fundamento da revisão). Seguradoras (Bradesco, Sul
    América, Itaúseg) partilham o mesmo teto (VCMH Teto); a Amil (Medicina de
    Grupo) tem percentual próprio, em regra inferior. Golden Cross consta até o
    ciclo 2013 (alienou a carteira em 2014); Porto Seguro apenas em 2006 (resíduo).
    Nos ciclos 2005 e 2006 o valor é o "percentual final", que embute resíduo de
    anos anteriores — a composição fica em `observacao`, para não ser mal aplicado.
    Série ANS: ciclos 2005–2026, grão operadora × ciclo. Fonte de 2005–2020 no
    "Histórico … por Termo de Compromisso" (página congelada em maio/2021); 2021–2025
    na página mantida "Reajustes de preços de planos de saúde antigos" (metodologia
    VCMH Teto por tipo de operadora desde 2013); 2026 na 639ª Reunião da Diretoria
    Colegiada. Pós-2020 restam quatro signatárias (Bradesco, Sul América, Itaúseg,
    Amil); Golden Cross saiu em 2014 e Porto Seguro só teve resíduo em 2006. Em 2021
    o teto foi negativo (ciclo COVID-19). O ciclo é ancorado em julho (junho, para a
    Amil); `periodo_aplicacao` traz a vigência exata, determinante para casar com o
    mês de aniversário do contrato. Seed versionado — não há PDA estruturado para
    este dado na base de Dados Abertos.
    """
    out: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ciclo = _inteiro(r.get("ciclo"))
            reg = _txt(r.get("registro_operadora"))
            if ciclo is None or not reg:
                continue
            out.append({
                "registro_operadora": reg,
                "operadora": _txt(r.get("operadora")),
                "ciclo": ciclo,
                "percentual": _num(r.get("percentual")),
                "periodo_aplicacao": _txt(r.get("periodo_aplicacao")),
                "oficio": _txt(r.get("oficio")),
                "observacao": _txt(r.get("observacao")),
                "fonte": _txt(r.get("fonte")),
            })
    return out
