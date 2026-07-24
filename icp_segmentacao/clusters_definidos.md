# Segmentação Comercial — 14 Clusters (Fase 4)

**Responsável:** Patrícia Nogueira — critérios de corte validados por André Kimura (todos os percentis calculados sobre o grupo elegível transacional, 58.531 clientes)
**Entrada:** `processado/df_scored_full.pkl` + `processado/cv_sazonalidade.csv`
**Saída:** `processado/df_clustered_full.pkl` (usado na Fase 5)
**Regra:** clusters mutuamente exclusivos (1 `CLUSTER_PRINCIPAL` por cliente, ordem de prioridade fixa abaixo); oportunidades adicionais viram `TAGS_SECUNDARIAS` (`grupo_economico`, `potencial_am`).

---

## Ordem de decisão (top-down, primeira regra que casar vence)

1. **Dados insuficientes** — `TIER == "Revisão"`
2. **Inativos antigos** — `CLIENTE_ATIVO == "INATIVO"` e recência > 365 dias (ou sem data de atividade)
3. **Inativos intermediários** — `INATIVO` e 180 < recência ≤ 365 dias
4. **Inativos recentes** — `INATIVO` e recência ≤ 180 dias
5. **Em risco** — `Score_Risco` no quartil superior (≥ 53,6) entre clientes ainda `ATIVO`
6. **Campeões** — `Tier A` e `Score_Recompra` no quartil superior (≥ 69,0)
7. **Alto potencial subpenetrado** — `Score_Potencial` no quartil superior (≥ 45,4) **e** `Score_Valor` abaixo da mediana (< 42,3)
8. **Recorrentes** — `Frequência anual` no quartil superior (≥ 6 reservas/ano)
9. **Novos com potencial** — tempo de relacionamento ≤ 180 dias (primeira abertura de contrato) e `Score_Potencial` ≥ 50
10. **Sazonais** — coeficiente de variação do volume mensal > 1,0 (ver `auditoria`/Fase 4 ICP4 — critério raramente atingido nesta base)
11. **Potencial de aluguel mensal** — usa só AD, nunca AM, e volume de AD no quartil superior (≥ 3)
12. **Potencial de cross-sell** — pertence a grupo econômico real (>1 `CODIGO_CLIENTE` no mesmo `NOME_GRUPO`) e ainda usa só 1 agência
13. **Baixo potencial atual** — `Tier C` que não caiu em nenhuma regra anterior
14. **Fallback → Recorrentes** — qualquer `Tier A/B` restante sem padrão distintivo

## Resultado real (85.941 clientes)

| Cluster | N | % da base | % do volume | Ticket médio (proxy) | Freq. média | Recência média (dias) | Score Potencial médio |
|---|---|---|---|---|---|---|---|
| Dados insuficientes | 27.387 | 31,87% | 0,00% | 0,00 | 0,00 | — | 27,59 |
| Inativos antigos | 20.247 | 23,56% | 4,10% | 0,52 | 0,85 | 1.209 | 31,66 |
| **Recorrentes** | 18.689 | 21,75% | **55,83%** | 7,70 | 8,13 | 53 | 38,67 |
| Inativos intermediários | 7.856 | 9,14% | 6,31% | 2,07 | 2,41 | 279 | 35,50 |
| Baixo potencial atual | 5.542 | 6,45% | 3,29% | 1,53 | 2,02 | 85 | 24,65 |
| Alto potencial subpenetrado | 2.191 | 2,55% | 1,10% | 1,30 | 5,10 | 61 | 52,55 |
| **Campeões** | 1.642 | 1,91% | **23,59%** | 37,04 | 26,31 | 21 | 54,25 |
| Em risco | 997 | 1,16% | 1,44% | 3,73 | 6,51 | 124 | 40,52 |
| Inativos recentes | 532 | 0,62% | 0,40% | 1,96 | 2,62 | 55 | 37,68 |
| Potencial de cross-sell | 478 | 0,56% | 1,41% | 7,60 | 2,73 | 65 | 37,97 |
| Novos com potencial | 340 | 0,40% | 2,32% | 17,56 | 2,56 | 10 | 63,02 |
| Potencial de aluguel mensal | 34 | 0,04% | 0,10% | 7,29 | 3,23 | 4 | 41,65 |
| Sazonais | 6 | 0,01% | 0,12% | 50,50 | 1,40 | 47 | 51,18 |
| **Sensíveis a preço** | **0** | **0%** | — | — | — | — | — |

**Concentração:** só 2 clusters — **Campeões (1,91% dos clientes) e Recorrentes (21,75%)** — respondem por **79,4% de todo o volume** da base. Isso confirma o padrão clássico de concentração de valor em poucos clientes (Pareto), mesmo sem dado de receita real.

## Nota por cluster

- **Campeões**: ticket médio 37,0 (10x a média geral) e recência de só 21 dias — grupo pequeno mas crítico, prioridade máxima de retenção.
- **Alto potencial subpenetrado**: 2.191 clientes com potencial acima da média mas valor capturado abaixo da mediana — maior oportunidade de expansão pura (não é aquisição, é crescer quem já é cliente).
- **Inativos antigos** é o 2º maior cluster (23,6% da base) — volume de reativação relevante, mas cada cliente individualmente vale pouco (ticket 0,52) — cadência automatizada, não humana.
- **Sensíveis a preço** ficou com **0 clientes**, não por bug: a auditoria já havia identificado que a base **não tem nenhum campo de desconto/tarifa aplicada** — não existe dado pra calcular esse cluster com critério objetivo. Registrado como gap de dado, não populado arbitrariamente (regra do `PROMPT.DOCX`: não atribuir sem evidência).
- **Sazonais**: só 6 clientes — consistente com o ICP4 já rejeitado na Fase 4 (documento `icps_definidos.md`) por falta de padrão sazonal na base.
- **Novos com potencial**: menor recência média de todos os clusters (10 dias) e 2º maior score de potencial médio (63,0) — bom sinal de entrada, vale acompanhar se convertem em Recorrentes ou Campeões nos próximos meses.
