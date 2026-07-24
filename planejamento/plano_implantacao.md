# Plano de Implantação e Geração de Arquivos — MASTER_CLASSIFICADA

**Responsáveis:** Bruno Salgado (implementação técnica) + Ricardo Bittencourt (arbitragem/aprovação) — todo o time participa por fase, ver [`../personas/README.md`](../personas/README.md)
**Pré-requisito:** [Auditoria de Dados](../auditoria/auditoria_dados.md) — 2 achados bloqueantes (`HISTORICO DE RESERVA` truncado, necessidade de parser CSV correto)
**Data:** 2026-07-24
**Decisão do usuário (2026-07-24):** CNPJ é irrelevante pro projeto — `CODIGO_CLIENTE` é a chave única em todas as fases. O achado de CNPJ corrompido na auditoria fica registrado como observação, não como bloqueio.

---

## 0. Bloqueios que precisam ser resolvidos antes da Fase 1

| # | Bloqueio | Quem resolve | Como |
|---|---|---|---|
| 1 | `HISTORICO DE RESERVA.csv` truncado em 150 mil linhas (só jan–jun/2025) | Camila | Trocar por `RESERVA - COTAÇÃO - CONVERSAO.csv` (60,41% de cobertura, jan/2025–jul/2026) como fonte primária de frequência/conversão. `HISTORICO DE RESERVA` fica só como fonte secundária para o período que cobre. |
| 2 | Parser ingênuo quebra ~5,8% das linhas | Bruno | Garantir que a importação no Power BI (Power Query) trate os CSVs com o parser de CSV padrão (respeita aspas) — não usar "Dividir Coluna por Delimitador" em texto já achatado. |

Nenhuma fase abaixo começa a valer sem esses dois itens resolvidos ou explicitamente aceitos como limitação documentada por Ricardo.

**Status (2026-07-24): todas as 7 fases executadas.** Bloqueio #1 resolvido (fonte trocada para `RESERVA - COTAÇÃO - CONVERSAO.csv`). Bloqueio #2 resolvido (parser `csv`/pandas usado em todo o pipeline). Único desvio do planejado: **não existe geração automática de `.pbix`** — Power BI é uma ferramenta desktop, não gerável por código; em vez disso foi produzido `powerbi/modelo_dados.md` com o roteiro completo (fonte, tipos, medidas DAX, páginas) para alguém montar o relatório manualmente a partir de `MASTER_CLASSIFICADA.csv`.

---

## 1. Arquitetura de pastas e arquivos a gerar

```
ICP/
├── auditoria/
│   └── auditoria_dados.md                    [PRONTO]
├── planejamento/
│   └── plano_implantacao.md                  [PRONTO — este arquivo]
├── personas/                                  [PRONTO]
├── processado/
│   ├── base_mestre_corrigida.csv              Fase 1 — Camila
│   ├── agg_reservas.csv                       Fase 2 — André
│   ├── agg_contratos.csv                      Fase 2 — André
│   ├── agg_cotacao_conversao.csv               Fase 2 — André
│   ├── agg_nps.csv                            Fase 2 — André
│   ├── agg_volume.csv                         Fase 2 — André
│   └── agg_ativacao_reativacao.csv             Fase 2 — André
├── scores/
│   ├── metodologia_scores.md                  Fase 3 — André (pesos, normalização, tratamento de ausentes/outliers)
│   └── master_scored.csv                      Fase 3 — André (CODIGO_CLIENTE + 5 scores + Tier)
├── icp_segmentacao/
│   ├── icps_definidos.md                      Fase 4 — Patrícia (5 ICPs: validado/hipótese + evidência)
│   └── clusters_definidos.md                  Fase 4 — Patrícia (14 clusters + critério objetivo de entrada)
├── master_classificada/
│   └── MASTER_CLASSIFICADA.csv                 Fase 5 — Bruno (produto final: 1 linha por cliente, ~60 colunas)
├── powerbi/
│   └── ICP_Localiza.pbix                       Fase 5 — Bruno
└── saidas/
    ├── tabela1_resumo_icps.csv                 Fase 6 — Bruno + Patrícia
    ├── tabela2_base_classificada.csv           Fase 6 — Bruno (versão exportável/mascarada, com Rafael revisando)
    ├── tabela3_acoes_por_segmento.csv          Fase 6 — Juliana
    ├── tabela4_top_oportunidades.csv           Fase 6 — Juliana
    └── plano_de_acao.md                        Fase 7 — Juliana + Ricardo
```

Todos os arquivos de `processado/`, `scores/`, `master_classificada/`, `powerbi/` e `saidas/` contêm dado real de cliente — **devem entrar no `.gitignore`** assim que forem gerados, seguindo a mesma decisão já tomada para os arquivos brutos. `auditoria/`, `planejamento/` e `personas/` são documentação de metodologia, sem dado de cliente — ficam versionadas normalmente.

---

## 2. Fases

### Fase 1 — Correção da base mestre (Camila)
**Entrada:** `BANCO DE DADOS.csv`
**Saída:** `processado/base_mestre_corrigida.csv`
- Recalcula `CLIENTE_ATIVO`, `CLASSIFICACAO_PORTE`, `FATURAMENTO_MENSAL`, `PATRIMONIO_LIQUIDO` com parser correto.
- Marca explicitamente `CNPJ_confiavel = falso` nas 61.820 linhas corrompidas (não descarta a linha, só sinaliza).
- Critério de pronto: 0 linhas malformadas, 100% dos 85.941 `CODIGO_CLIENTE` preservados.

### Fase 2 — Tabelas agregadas por fonte (André)
**Entrada:** `RESERVA - COTAÇÃO - CONVERSAO.csv` (fonte primária de reserva/conversão), `HISTORICO DE RESERVA.csv` (secundária, só jan–jun/2025), `CONTRATOS ABERTO CLIENTE.csv`, `NPS.csv`, `VOLUME.csv`, `AR.csv`
**Saída:** um `AGG_*.csv` por fonte, todos com `CODIGO_CLIENTE` como chave e granularidade 1 linha por cliente (soma/contagem/média conforme a métrica).
- Cada agregado documenta no cabeçalho do arquivo (ou num `.md` irmão) o período que cobre — pra nunca comparar recência calculada em janelas diferentes sem ajuste.
- Critério de pronto: todo `CODIGO_CLIENTE` de cada `AGG_*` existe em `base_mestre_corrigida.csv` (nenhum órfão).

### Fase 3 — Scores (André, aprovação de peso por Ricardo)
**Entrada:** `base_mestre_corrigida.csv` + todos os `AGG_*.csv`
**Saída:** `scores/metodologia_scores.md` (pesos, fórmulas, tratamento de nulos/outliers/clientes novos) + `scores/master_scored.csv`
- Os 5 scores (Valor, Potencial, Recompra, Risco, ICP) e o Tier (A/B/C/Revisão/Supressão), pesos iniciais conforme `PROMPT.DOCX` Etapa 5, ajustados conforme a auditoria mostrar necessário (ex.: reduzir peso de `FATURAMENTO_MENSAL` dado 71% de ausência).
- Critério de pronto: Ricardo aprova a metodologia por escrito antes de gerar o CSV final.

### Fase 4 — ICPs e Clusters (Patrícia, validação de evidência por André)
**Entrada:** `scores/master_scored.csv`
**Saída:** `icp_segmentacao/icps_definidos.md` + `icp_segmentacao/clusters_definidos.md`
- Cada um dos 5 ICPs-hipótese do `PROMPT.DOCX` recebe status Validado/Hipótese + nível de confiança (Alto/Médio/Baixo).
- Os 14 clusters ganham critério objetivo de entrada, tamanho e receita representada.
- Critério de pronto: nenhum ICP ou cluster sem evidência quantitativa citada.

### Fase 5 — MASTER_CLASSIFICADA e Power BI (Bruno)
**Entrada:** tudo das Fases 1–4
**Saída:** `master_classificada/MASTER_CLASSIFICADA.csv` (~60 colunas, 1 linha por cliente) + `powerbi/ICP_Localiza.pbix`
- Merges por `CODIGO_CLIENTE`, chunking se necessário para performance.
- Critério de pronto: `.pbix` abre e os visuais carregam sem timeout com a base completa (85.941 linhas).

### Fase 6 — Saídas obrigatórias (Bruno + Patrícia + Juliana, revisão de Rafael)
**Saída:** as 4 tabelas exigidas pela Etapa 9 do `PROMPT.DOCX`, em `saidas/`.
- Rafael revisa `tabela2_base_classificada.csv` especificamente por exposição de dado pessoal antes de qualquer compartilhamento fora do time.

### Fase 7 — Plano de ação comercial (Juliana + Ricardo)
**Saída:** `saidas/plano_de_acao.md` — as recomendações da Etapa 8 (aquisição, retenção, reativação, cross-sell, migração AD→AM etc.), cada uma com objetivo, público, impacto, esforço, prazo e KPI, mais a matriz Impacto × Esforço final com as 10 iniciativas prioritárias (Etapa 10).

---

## 3. Cronograma

| Prazo | Entregas |
|---|---|
| **Curto prazo** | Fases 0–3: bloqueios resolvidos, base corrigida, agregados, scores com metodologia aprovada |
| **Médio prazo** | Fases 4–6: ICPs/clusters validados, MASTER_CLASSIFICADA publicada em Power BI, 4 tabelas de saída |
| **Longo prazo** | Fase 7 + iteração: plano de ação em execução, e reavaliação de modelos preditivos (propensão, churn, migração AD→AM) citados no `readme.md` como próximos passos |

## 4. Dependências entre fases

Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7, estritamente sequencial — nenhuma fase começa com a anterior incompleta, porque cada uma consome o arquivo gerado pela fase de trás. Rafael (compliance) audita em paralelo a partir da Fase 1, não é uma fase isolada no fim.
