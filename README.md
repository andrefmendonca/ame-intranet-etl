# ame-intranet-etl

ETL mensal dos Dados Abertos da ANS para a fundação de dados da Intranet AME
(Supabase). Fontes públicas — Lei nº 12.527/2011 e Decreto nº 8.777/2016.

| Tabela | Fonte | Escopo | Cadência |
|---|---|---|---|
| `ans_produtos` | PDA-008 | Todas as operadoras (~165 mil planos) | Recarga integral mensal |
| `ans_pool` | PDA-055 | Todas as operadoras, ciclos 2013→ | Recarga integral mensal |
| `ans_ntrp_faixas` | NTRP/VCM por faixa etária | Todas as operadoras, vintages 2004→ (deduplicado por plano × data) | Recarga integral mensal |
| `ans_rpc_agregado` | PDA-043 (RPC) | Operadoras TOP (23 registros, famílias completas), 2005→ | Janela móvel de 15 meses (backfill no 1º run) |
| `ans_rpc_contratos_ba` | PDA-043 (RPC) | TOP × UF BA, linhas brutas (espelho de contrato) | Idem |
| `ans_cargas` | — | Proveniência: URL, SHA-256, linhas, status de cada carga | Cada run |

## Ativação em três passos

1. **Repositório**: crie o repositório privado `ame-intranet-etl` e envie estes
   arquivos (upload pela interface web do GitHub resolve).
2. **Secrets** (Settings → Secrets and variables → Actions):
   - `SUPABASE_URL` — ex.: `https://xxxx.supabase.co` (Project Settings → API);
   - `SUPABASE_SERVICE_KEY` — a chave `service_role` (mesma página). Ela nunca
     aparece em código; vive apenas como Secret.
3. **Primeiro run**: Actions → *ETL ANS* → *Run workflow* → marque
   **backfill = true**. Duração estimada: 40–70 min (o RPC histórico soma ~6 GB
   de download). Os runs mensais subsequentes (cron do dia 5) levam ~10–15 min.

## Aceite do backfill (Gate A)

Em `ans_cargas`, as quatro fontes com `status = ok`. Contagens de referência
(sessão de fundação, 07/07/2026):

- `ans_produtos` ≈ **165.146** linhas;
- `ans_pool` ≈ **6.058** linhas (ciclos 2013–2025);
- `ans_ntrp_faixas` ≈ **231.693** vintages (todas as operadoras);
- `ans_rpc_agregado` / `ans_rpc_contratos_ba`: volumes registrados no `detalhe`
  da carga (competências e anos processados).

Conferentes qualitativos (validados empiricamente na fundação):

1. Plano **18491260** (Amil S380 QP Nac R Copart PJ NT): todos os vintages com
   vetor `17 / 22 / 20 / 5 / 10 / 25 / 10 / 25 / 75` e razão 10ª/1ª = 5,95;
2. Plano **1480575** (UNIPLAN Múltiplo Adesão – Enfermaria, CNU): **cinco**
   vintages distintos, com mudanças protocoladas em 2007, 2013, 2015 e 2019;
3. `ans_pool` ciclo 2025, `pct_unico`: Bradesco (005711) 15,11 · SulAmérica
   (006246) 15,23 · Amil (326305) 15,98 · CNU (339679) 19,50.

## Notas de operação

- **Last-good**: padrão *upsert-then-prune* — o snapshot anterior só é removido
  após upsert completo; falha parcial preserva o último estado bom e marca
  `falha` em `ans_cargas` (o run sai com código ≠ 0 e o Actions fica vermelho).
- **Janela móvel do RPC**: a ANS recarrega comunicados retroativamente
  (comprovado: aplicação 01/2026 protocolada em 03/2026 com carga em 07/2026);
  por isso o run mensal reprocessa os últimos 15 meses e poda somente os anos
  da janela.
- **Encoding misto**: PDA-008 e PDA-055 chegam em UTF-8; RPC e NTRP, em
  Latin-1. O módulo de fontes detecta e normaliza tudo para UTF-8 no disco.
- **Registros de operadora**: o conjunto TOP foi derivado do próprio PDA-008
  (nunca de memória — a Postal Saúde é `419133`; a CNU consta como
  "UNIMED NACIONAL - COOPERATIVA CENTRAL").
- **Avisos em negociação** (`LG_NEGOCIACAO = 1`) entram nas linhas brutas da BA
  com o flag, mas ficam fora do agregado, conforme o dicionário oficial.
- **Desenvolvimento local**: `python run.py --dry --local <dir>` roda as
  transformações sem rede nem escrita remota e materializa CSVs em `out/`.

## Segurança

Dados 100% públicos; leitura via RLS (`SELECT` para `anon`/`authenticated`);
escrita exclusivamente pela `service_role` guardada como Secret do GitHub.
Endurecimento previsto (backlog): role Postgres dedicado ao ETL com grants
restritos às seis tabelas.
