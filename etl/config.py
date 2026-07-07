"""Configuração do ETL ANS — Intranet AME.

Fontes: Plano de Dados Abertos da ANS (Lei nº 12.527/2011; Decreto nº 8.777/2016).
Conjunto TOP de operadoras DERIVADO EMPIRICAMENTE do PDA-008 em 07/07/2026 —
nunca codificar registro de operadora de memória (a Postal Saúde, por exemplo,
é 419133; a CNU consta como "UNIMED NACIONAL - COOPERATIVA CENTRAL").
"""

BASE = "https://dadosabertos.ans.gov.br/FTP/PDA"
UA = {"User-Agent": "Mozilla/5.0 (AME-ETL/1.0; +https://ame.adv.br)"}

FONTES = {
    "operadoras_ativas": "https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv",
    "operadoras_canceladas": "https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_canceladas/Relatorio_cadop_canceladas.csv",
    "produtos": f"{BASE}/caracteristicas_produtos_saude_suplementar-008/"
                f"pda-008-caracteristicas_produtos_saude_suplementar.csv",
    "pool":     f"{BASE}/percentuais_de_reajuste_de_agrupamento-055/"
                f"pda-055-Percentuais_de_Reajuste_de_Agrupamento.csv",
    "ntrp_zip": f"{BASE}/nota_tecnica_ntrp_vcm_faixa_etaria/"
                f"nota_tecnica_vcm_faixa_etaria.zip",
    "rpc_dir":  f"{BASE}/RPC",
}

# RPC: dois consolidados históricos + mensais pda-043-rpc-AAAAMM.csv desde 2015-01.
RPC_CONSOLIDADOS = ["pda-043-rpc-2005_2009.csv", "pda-043-rpc-2010_2014.csv"]
RPC_MENSAL_INICIO = 201501
# Recarga retroativa comprovada empiricamente (aplicação jan/2026 protocolada em
# mar/2026 com carga em jul/2026) → janela móvel de reprocessamento no run mensal.
JANELA_MESES = 15
# Tolerância: os N meses mais recentes podem ainda não estar publicados (404 aceito).
MESES_TOLERADOS_404 = 2

# Escopos:
#   ans_produtos e ans_pool e ans_ntrp_faixas → TODAS as operadoras.
#   ans_rpc_agregado e ans_rpc_contratos_ba  → conjunto TOP abaixo (famílias completas).
TOP_OPERADORAS = {
    "005711": "Bradesco Saúde",
    "005444": "Bradesco Seguros",
    "421715": "Bradesco Saúde Operadora de Planos",
    "363022": "Bradesco Saúde e Assistência",
    "006246": "SulAmérica Seguro Saúde",
    "326305": "Amil Assistência Médica",
    "302872": "Amil Saúde",
    "412384": "Amil Planos por Administração",
    "368253": "Hapvida",
    "359017": "NotreDame Intermédica",
    "348520": "NotreDame Intermédica MG",
    "006980": "NotreDame Seguradora",
    "339679": "Central Nacional Unimed (Unimed Nacional)",
    "000701": "Unimed Seguros Saúde",
    "417491": "PortoMed",
    "000582": "Porto Seguro Saúde",
    "005886": "Porto Seguro Cia de Seguros Gerais",
    "000515": "Allianz Saúde",
    "379956": "Care Plus",
    "359661": "Omint",
    "346659": "Cassi",
    "323080": "GEAP Autogestão",
    "419133": "Postal Saúde",
}

UF_BRUTO = "BA"          # linhas brutas do RPC gravadas apenas para esta UF
LOTE_UPSERT = 800        # linhas por requisição PostgREST
LOTE_ARQUIVOS_RPC = 10   # arquivos RPC ingeridos por vez no DuckDB (controle de disco)
