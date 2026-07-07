# Blueprint v2 — Registro consolidado da arquitetura

**Projeto:** Intranet AME · fundação de dados ANS · esteira de skills de revisão de reajuste
**Consolidado em:** 07/07/2026 (sessão noturna), por arqueologia das conversas-fonte
**Natureza:** registro de deliberações. Este documento carrega decisões, especificações e a evolução do raciocínio — não repete os relatórios integrais das sessões.

---

## 0. Cadeia de conversas-fonte

| Data | Conversa | Contribuição |
|---|---|---|
| 04/07 | [Arquitetura de intranet para escritório com Fable](https://claude.ai/chat/51d71e2c-5118-467c-9628-bf94a770b8ab) | Gênese: arquitetura de segunda linha, inventário de jobs por ROI, princípio "a IA propõe, a pessoa aprova", auditoria de skills como um dos três movimentos prioritários |
| 06/07 | [Arquitetura de intranet customizada baseada em ADVBOX](https://claude.ai/chat/70bb3ca9-6e41-49e8-b13a-42c6b5cc7004) | Dossiê consolidado: intranet por setores (não espelho da ADVBOX), decisões D1–D6, especificação dos jobs J1–J6, testes T0–T3, T0 = rotação do token ADVBOX como bloqueante |
| 07/07 (tarde) | [Análise de skills e arquitetura de sistema para intranet](https://claude.ai/chat/28458abc-f7fd-4a19-84f6-bc15da961f5a) | **A conversa-mãe**: diagnóstico da esteira, Blueprint v2 (fusões), camada de serviços, fases F0–F4, construção da `qualificacao-caso` v2, Fase A entregue, Fase B iniciada |
| 07/07 (noite, 2 sessões) | Fase B — Termos de Compromisso + diligência 2021+ | Seed `ans_reajuste_planos_antigos` 2005–2026 (98 linhas), página individual-antigo ligada, diligência TC resolvida |

---

## 1. Diagnóstico da esteira (conversa-mãe, seção 1)

As skills não são peças soltas: já formam, implicitamente, uma **esteira de produção de caso revisional** — com o Dr. André como barramento de integração entre as etapas.

| Etapa | Skill | Maturidade | Fragilidade central |
|---|---|---|---|
| Qualificação PJ | `consulta-cnpj` (v5) | Alta | Defasagem de 1–4 semanas da Minha Receita; sem SLA |
| Qualificação operadora | `consulta-operadora` (v1) | Alta | Nenhuma relevante |
| Qualificação produto | `consulta-plano` (v4) | Alta | Códigos pré-Lei 9.656/98 sem cobertura; municípios "(em breve)" |
| Normalização de insumos | `organizacao-faturas-cobranca` | Alta | Cascata de extração por operadora exige manutenção quando layout muda |
| Cálculo | `popular-planilha-revisao` | Média-alta | **Maior risco silencioso** — ver abaixo |
| Peça comercial | `analise-viabilidade-reajuste` | Alta | Compara apenas com o índice ANS individual — subutiliza o dado disponível |
| Jusante | `procuracao-saude`, `contrato-honorarios`, `peticao-revisao` | Alta | Reconsomem manualmente a mesma qualificação |

**Três observações registradas:**

1. **A duplicação tripla do pipeline de PDF é o principal débito técnico.** As três skills de consulta carregam cópias quase idênticas de `title_pt()`, expansão de abreviações, CSS, pipeline `markdown → HTML → wkhtmltopdf` e lógica de desambiguação. Qualquer ajuste de formatação é feito três vezes.
2. **A `popular-planilha-revisao` é a etapa de maior risco silencioso.** Extrai rubricas por regex e **não valida o fechamento** (não confere se a soma das rubricas bate com o total da fatura). Um layout novo pode perder uma rubrica sem aviso. Régua termina em 12/2026; limite de 10 beneficiários; DOB depende de `.md` externos.
3. **As decisões de design deliberadas estão corretas e devem ser preservadas:** separação entre "skill que formata dado oficial sem opinar" (consultas) e "skill que analisa"; a "regra de ouro" da viabilidade (nunca inferir dado faltante); o checkpoint humano entre planilha e peça; e a `consulta-plano` v2 já capturava o `id` interno como chave de join com PDA-054/055 — a arquitetura de dados já estava em embrião no próprio changelog.

---

## 2. Blueprint v2 — Fusões (deliberação final do conselho)

| # | Decisão | Status |
|---|---|---|
| 1 | `consulta-cnpj` + `consulta-operadora` + `consulta-plano` → **`qualificacao-caso`** (4 modos, um único pipeline de PDF, Ficha de Qualificação unificada) | Aprovada por unanimidade |
| 2 | `organizacao-faturas` + `popular-planilha` + `analise-viabilidade` → **encadear, não fundir**, via orquestradora `esteira-reajuste` com checkpoint humano | Mantida |
| 3 | `procuracao-saude` + `contrato-honorarios` → **`documentos-contratacao`** — assets literalmente os mesmos arquivos (`timbrado.docx` e `dados_ame.json` idênticos byte a byte), qualificação de entrada idêntica, sequência natural: um input, dois outputs | Aprovada |
| 4 | Ex-"benchmark" → **`triagem-reajuste`**: triagem interna com espelho RPC; saída externa condicionada à regra de favorabilidade | Reclassificada |
| 5 | `peticao-revisao` isolada (juízo intensivo); `calculo-nota-corretagem` fora do escopo (pessoal) | Mantidas |

---

## 3. Ferramentas da intranet (mapa final × fases)

| Ferramenta | Setor | Fonte | Fase |
|---|---|---|---|
| Painel de Ciclos (aposenta o Notion Reajustes) | Diretoria | PDA-055 + índice ANS curado | **F1** |
| Radar de Ciclo (aniversários por operadora/BA) | Comercial/Diretoria | RPC 12 meses | **F1** |
| Fila de exceções + monitor de ETL | Controladoria | logs | **F1** |
| Espelho RPC (declarado × cobrado) | Jurídico | `ans_rpc` recorte BA | **F1.5** — não depende da extração de faturas |
| Ficha de Qualificação | Comercial | REST ANS + Minha Receita + tabelas locais | F2 |
| Pré-Viabilidade com triagem embutida | Comercial | 1 fatura + agregados RPC/pool | F2 |
| Termômetro NIP + TAM Salvador | Comercial | pda-013 + PDA-024 | F2 (opcional) |
| Esteira do Caso (extração híbrida + motor + planilha) | Produção | storage + serviços | **F3 — condicionada ao volume** |
| Gerador de peças + anexo metodológico probatório | Produção | templates docx/pdf | F4 |

**Fases (cada uma com valor autônomo):** **F0** — fusões e upgrades de skill, sem tocar na intranet; **F1** — tabelas `ans_*` + ETL + painel de ciclos; **F2** — qualificação e pré-viabilidade no módulo Comercial; **F3** — esteira de produção (upload, extração híbrida, motor, planilha + viabilidade); **F4** — peças, ADVBOX e telemetria.

**Antídoto contra dispersão** (observação do conselho): este módulo disputa atenção com o AME Financeiro e com a própria intranet; a Fase 0 deve entregar valor sem tocar em infraestrutura e a Fase 1 deve nascer *dentro* da intranet planejada, **jamais como terceiro sistema**.

**Nota regulatória do conselho:** os três valores distintos observados no pool da Amil sugerem sub-agrupamento (art. 39 da RN nº 565/2022) — mais uma razão para a ETL rotular pelos códigos oficiais antes de qualquer número ir a uma peça.

---

## 4. Camada de serviços — quatro decisões estruturantes

1. **Qualificação:** consultas respondidas primeiro pelas **tabelas locais** (latência zero, sem dependência do gateway ANS-GTW.PR no caminho crítico), com fallback live para a REST. A Ficha de Qualificação vira uma **tela**, não um acionamento de skill.
2. **Extração de faturas** — o único problema genuinamente difícil do sistema. Desenho **híbrido**: parsers determinísticos portados para as três operadoras de maior volume + fallback por visão (Claude API) para o resto, **ambos submetidos ao mesmo validador de fechamento**. Divergência não trava: cai em fila de revisão. A promessa correta não é "100% de automação"; é **"100% de verificação"**.
3. **Motor de cálculo:** portar as fórmulas da planilha para **TypeScript com testes de paridade contra planilhas de casos reais já validados (golden files)**. A XLSX continua sendo gerada — como artefato auditável e entregável — mas deixa de ser o motor. Abandona-se o Excel como calculadora, não como formato.
4. **Documentos:** viabilidade em HTML→PDF (Browser Rendering do Cloudflare, mesmo layout do timbrado); procuração e contrato via templating sobre os `.docx` que as skills já usam. Nada de redesenhar peça que funciona.

**Fluxo comercial de referência:** a Sabrina cola um CNPJ e anexa uma fatura; o sistema qualifica, extrai, consulta o benchmark e devolve em minutos uma **pré-viabilidade indicativa** (ordem de grandeza, sem compromisso numérico) — munição para a reunião diagnóstica, que é o primeiro gatilho variável da remuneração dela (Marco 1).

**Posição registrada sem rodeios (fim do parecer):** o maior ganho disponível não exige uma linha da intranet — é colocar o **benchmark RPC + pool nas peças ainda esta semana**, via skill; dado que a própria ré declarou ao regulador, com chave de join já capturada, que ninguém no mercado usa. O segundo ganho é **parar de ser o barramento humano da esteira**: a fusão da qualificação custa pouco e corta dois terços dos acionamentos de abertura.

---

## 5. Quatro decisões reservadas ao Dr. André

1. O **volume mensal real de análises** — abre ou fecha a Fase 3.
2. A posição institucional sobre a comunicação da **janela de repetição** ao cliente (trienal estrita ou trienal com tese subsidiária, à luz do distinguishing citado).
3. O **limiar de amostra** para externalizar benchmark em peça.
4. A **confirmação de que a Fase 0 começa já** — os números de janeiro/2026 extraídos na revisão já eram utilizáveis em triagem e reunião comercial antes de qualquer linha de código.

---

## 6. `qualificacao-caso` v2 — anatomia (como construída em 07/07 tarde)

Skill fundida (Blueprint fusão #1), construída, executada ao vivo e entregue como `qualificacao-caso.zip` na conversa-mãe. Instalação = upload manual pela interface de Skills (ação do titular da conta).

### 6.1 Ramificação por tipo de contratação (`contratacao`)

- **Individual ou familiar** → reajuste anual pelo índice único da ANS. *(No momento da construção, a base local ainda não tinha essa série: a skill sinalizava "referência de reajuste anual não disponível nesta base". Esse trecho está **desatualizado** — ver §8.)* A qualificação recaía sobre a estrutura de faixas (RN 63).
- **Coletivo por adesão / Coletivo empresarial** → reajuste por sinistralidade/pool:
  - **Referência primária:** `ans_pool` (percentual único do agrupamento da operadora, 2013+), para contrato agrupado (< 30 vidas);
  - **Empírico:** histórico consolidado do RPC do próprio plano;
  - Se houver **reajuste cobrado** (da fatura): confrontar cobrado × referência; diferença relevante ⇒ indício de revisão.

### 6.2 Faixa etária (`ans_ntrp_faixas`) — sempre avaliada, individual e coletivo

- **Vintage aplicável:** com data de contratação, a estrutura válida é a da **última `dt_ntrp` ≤ data de contratação** (a chave estrutural é a data da NTRP, não o ano-calendário). Sem a data: avaliar **todas** as estruturas e sinalizar se **alguma** viola a RN 63.
- **RN nº 63/2003, art. 3º:** inciso I (`rn63_art3_i`: última faixa ≤ 6× a primeira; `false` ⇒ excede o teto legal); inciso II (`rn63_art3_ii`: variação acumulada 7ª→10ª ≤ variação acumulada 1ª→7ª; `false` ⇒ concentração indevida no idoso).
- Beneficiário **idoso (60+):** sinalizar o arcabouço de vedação ao reajuste por faixa após os 60 (Estatuto da Pessoa Idosa + Tema 952/STJ) — **sem redigir citação**; isso é confirmado na petição.

### 6.3 Triagem processual mínima

Sinalizar, não decidir: plano **Inativo** (`situacao_plano` = "Cancelado") não impede revisão de contratos vigentes, mas muda a narrativa; abrangência e segmentação entram na qualificação da praça e do juízo.

### 6.4 Taxonomia do veredito

| Veredito | Critério |
|---|---|
| **Viável** | Coletivo com reajustes acima da referência de pool/ANS de forma consistente, **ou** estrutura de faixa que viola a RN 63 art. 3º (I ou II). |
| **Limítrofe** | Diferença pequena/inconsistente; faixa conforme mas com concentração alta; requer a fatura e a data de contratação para fechar. |
| **Requer análise** | Dados insuficientes na base (sem RPC/pool e sem faixa clara); encaminhar à análise manual. |
| **Fora de escopo** | Plano individual sem indício de abuso de faixa (reajuste segue índice ANS regular), ou ausência de vínculo com reajuste. |

O veredito é **preliminar** e explicitamente rotulado como tal. A peça definitiva é a `analise-viabilidade-reajuste`. Base legal citada no rodapé: RN 63/2003 art. 3º I e II; Lei 10.741/2003 art. 15 §3º; STJ Temas 952, 610, 1.198.

### 6.5 Output

Relatório `.md` + `.pdf` (wkhtmltopdf, padrão acromático), nome `{cd_plano} - {Operadora} - Qualificação de Caso`:
1. **Cabeçalho:** nome do plano, operadora, registro ANS (`cd_plano`), id interno, data da consulta, "Fonte: base ANS da intranet AME (Dados Abertos da ANS)";
2. **Identificação** (contratação, segmentação, abrangência, acomodação, financiamento, situação, registro, atualização — com `title_pt()` e o mapa de situação da `consulta-plano`);
3. **Natureza do reajuste** (individual × coletivo);
4. Pool/RPC; faixas; **veredito com fundamentação**.

### 6.6 Validação ao vivo (cobaia)

Registro **492212223** (Amil S380 QP Nac R Copart PJ NT) → veredito **Limítrofe**: pool agressivo nos ciclos recentes (23,40% / 21,98% / 15,98%), faixa **conforme** à RN 63 (razão 5,95), faltando os dois insumos sob controle do cliente — a **fatura** (reajuste efetivamente cobrado) e a **data de contratação** (aniversário + vintage de faixa).

---

## 7. Fundação de dados assentada (Fases A e B + diligência)

- **Fase A** (conversa-mãe; commits `7d06e b2`/`eaf42f0`): 4ª coluna "Índice ANS ind./fam." **adjacente** ao percentual do pool no coletivo (Amil 2023: 23,40% × 9,63%; 2024: 21,98% × 6,91% — o abismo à vista em três cliques); série completa do índice individual 2000–2026 (27 ciclos, incluindo o negativo de −8,19%); ramo individual antigo com a ressalva dos Termos de Compromisso. Gate forense estabelecido: validação por amostragem do Dr. André antes de qualquer seed entrar na base.
- **Fase B + diligência 2021+** (sessões noturnas; commits `f2488d6`, `1ae3ddd` no ETL; `3efc18f`, `0c61659` no `ans-data-heart`): seed `ans_reajuste_planos_antigos` com **98 linhas, 2005–2026**. Achado central da diligência: o regime de TC **não encerrou** — a página "histórico" estava congelada em 2020; a página-mãe (atualizada 08/08/2025) traz 2021–2025 e a 639ª RDC traz 2026. Signatárias vigentes: **apenas Bradesco (005711), Sul América (006246), Itaúseg (000884) e Amil (326305)**; Golden Cross saiu em 2014; Porto Seguro só 2006.
- **Três achados forenses da diligência:** (1) **2021 foi negativo** (−7,24% seguradoras / −7,83% Amil) — qualquer positivo nesse ciclo é descumprimento direto, ganho por aritmética; (2) **seguradoras divergem** — 2024: Bradesco/Itaúseg 8,02% × Sul América 6,91% — conferir sempre o ofício da operadora específica; (3) desde 2013 o teto é a **VCMH Teto** por tipo, regida pela RN 565/2022 desde 01/02/2023. E o já sabido da Fase B: **TC ≠ índice individual** — em vários ciclos o TC foi **maior** (2017: 14,73% × 13,55%); usar o índice individual para signatária **subestima o teto**.
- **Modelo consolidado da página `dossie-plano`** (quatro regimes): individual+antigo+signatária → teto TC primário; individual+antigo não-signatária → índice individual como teto de cláusula omissa; individual novo → série do índice ANS; coletivo → pool (≤29 vidas) com índice ANS adjacente; 30+ → livre negociação (RPC referencial). NTRP transversal.

---

## 8. Delta do realinhamento da `qualificacao-caso` v2 (pendência aberta)

Anotado na própria Fase A: *"o realinhamento da `qualificacao-caso` v2 fica para depois de as colunas assentarem, para não retrabalhar a skill duas vezes."* As colunas assentaram. O delta:

1. **Individual (novo):** substituir "referência de reajuste anual não disponível nesta base" pela consulta a `ans_indice_individual` (série 2000–2026 na base). Com fatura, confrontar cobrado × índice do ciclo.
2. **NOVO ramo — individual + antigo** (`vigencia_plano = "A"`), sub-bifurcado por signatária vigente via `ans_reajuste_planos_antigos`:
   - **Signatária** (Bradesco/Sul América/Itaúseg/Amil): teto = **TC/VCMH Teto da operadora × ciclo**, não índice genérico. Alertas obrigatórios: 2021 negativo; divergência entre seguradoras (conferir o ofício da operadora específica); TC pode ser **maior** que o índice geral — usar o índice individual subestima o teto e pode marcar como abusivo reajuste que estava dentro do TC.
   - **Não-signatária:** índice ANS individual como teto de cláusula omissa.
3. **Taxonomia do veredito — revisão conceitual:** o individual deixa de ser quase-automático "Fora de escopo". Com as novas tabelas, o individual **ganha eixo de revisão de índice**: antigo de signatária com aplicação acima do teto TC do ciclo (em especial o 2021 negativo) é **Viável por aritmética**; individual com fatura mostrando aplicação acima do índice ANS idem. "Fora de escopo" fica reservado ao individual **sem fatura** e sem indício de abuso de faixa.
4. **Preservar intactos:** ramos coletivo (pool primário + RPC empírico + cobrado×referência), faixa etária/vintage/RN 63, triagem processual mínima, taxonomia rotulada como preliminar, contrato de saída para a esteira (`analise-viabilidade-reajuste` é a peça definitiva), e o pipeline `.md`+`.pdf`.
5. **Contrato de dados** (nomes idênticos à página): tabelas `ans_indice_individual`, `ans_pool`, `ans_reajuste_planos_antigos`, `ans_ntrp_faixas`; campos `contratacao`, `vigencia_plano` ("A" = antigo), `registro_operadora`, `id_plano`.

**Planos-teste** (signatárias, individuais antigos, confirmados na base): Bradesco `8700410041`; Sul América *IND Global Trad* (`10207`); Amil `S1` / `3`. Cobaia coletiva de regressão: `492212223`.

---

*Fim do registro. Alterações futuras a este blueprint devem ser feitas por commit neste arquivo, preservando o histórico.*
