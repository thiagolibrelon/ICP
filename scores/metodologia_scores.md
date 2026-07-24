# Metodologia de Scores — Fase 3

**Responsável:** André Kimura (Cientista de Dados) — aprovação de pesos por Ricardo Bittencourt
**Data:** 2026-07-24
**Entrada:** `processado/base_mestre_corrigida.csv` + 6 arquivos `processado/agg_*.csv`
**Saída:** `scores/master_scored.csv`
**Data de referência (recência):** 2026-07-22 (data máxima encontrada na própria base, conforme regra do `PROMPT.DOCX`)

---

## 1. Universo de scoring

85.941 clientes recebem *algum* score, mas com confiança diferente:

- **Elegível transacional** (58.554 clientes, 68,1%): tem pelo menos 1 sinal de reserva, contrato ou volume, ou data de último contrato preenchida — os componentes de recência/frequência/valor são calculados por percentil dentro desse grupo.
- **Só cadastral** (27.387 clientes, todos `NUNCA LOCOU` sem nenhum sinal em nenhuma fonte) — não recebem Score_ICP baseado em comportamento algum: caem direto em **Tier "Revisão"**, mesmo que o cálculo bruto do Score_ICP exista (baseado só em `LIMITE_CREDITO` e setor/CNAE) — não é atribuição arbitrária de potencial, é proxy explicitamente sinalizado como baixa confiança.

**Confiança** por cliente = quantas das 4 fontes (`reservas`, `contratos`, `volume`, `NPS`) têm sinal:
| Confiança | Nº de fontes com sinal | Clientes | % |
|---|---|---|---|
| Alta | ≥ 3 | 8.078 | 9,4% |
| Média | 1–2 | 33.481 | 39,0% |
| Baixa | 0 | 44.382 | 51,6% |

## 2. Métricas base

| Métrica | Fórmula | Fonte |
|---|---|---|
| **Recência (dias)** | data de referência − última atividade (máx. entre data de último contrato, última reserva, abertura de contrato, visita, pesquisa NPS) | todas |
| **Frequência anual** | `RESERVA_TOTAL / meses_cobertos * 12` | `RESERVA - COTAÇÃO - CONVERSAO.csv` (fonte primária — ver decisão da auditoria de não usar o `HISTORICO DE RESERVA.csv` truncado como frequência principal) |
| **Valor (volume)** | Volume últimos 24 meses (ago/24–jul/26), somado de `VOLUME.csv` | decisão já documentada no projeto: Volume como proxy de valor, na ausência de receita/margem confiável |
| **Ticket proxy** | Volume 24M / Frequência anual (diárias por reserva) | proxy fraco — não existe tarifa/receita na base, sinalizado como tal |
| **Potencial econômico** | `LIMITE_CREDITO` (81,2% de cobertura), com fallback em `FATURAMENTO_MENSAL` (28,6% de cobertura) quando ausente | **Ajuste de peso registrado**: o `PROMPT.DOCX` sugere faturamento como sinal principal; a auditoria mostrou que `LIMITE_CREDITO` é quase 3x mais completo — usado como sinal primário |
| **Amplitude** | soma de 3 flags: tem grupo econômico + usa mais de 1 agência + usa AD e AM juntos | `NOME_GRUPO`, `agg_volume.AGENCIAS_DISTINTAS`, `agg_contratos` |
| **Crescimento** | variação % entre volume 2025 e volume 2026 anualizado (jan–jul projetado ×12/7) | `VOLUME.csv` |
| **Qualidade cadastral** | % de campos-chave preenchidos (grupo, CNAE, estado, CNPJ, limite de crédito) | `base_mestre_corrigida.csv` |
| **Aderência de segmento** | percentil da frequência mediana do setor (`SECAO_CNAE`) do cliente, entre clientes com frequência > 0 — clientes de setores historicamente mais ativos herdam nota mais alta | proxy agregado por setor, não individual |

## 3. Normalização

Todos os componentes usados nos scores são normalizados por **percentil (rank 0–100)** dentro do grupo elegível — não por min-max, pra não deixar um outlier extremo distorcer toda a escala (ex.: um cliente com volume 100x maior que o segundo colocado). Componentes "quanto menor melhor" (recência em dias, % de comprometimento de crédito) são invertidos (`100 − percentil`).

**Tratamento de ausentes:** cada score é uma média ponderada dos componentes disponíveis, com os pesos **renormalizados entre os componentes presentes** — um cliente sem NPS não é penalizado com nota zero em NPS, o peso dele é redistribuído entre os componentes que existem para aquele cliente. Isso evita a distorção de tratar "sem dado" como "nota mínima".

**Tratamento de outliers:** implícito no uso de percentil — o valor absoluto do outlier não importa, só a posição relativa.

**Tratamento de clientes novos:** frequência e recência usam a janela de meses realmente coberta pela base (`meses_cobertos`), não um denominador fixo de 12 meses — evita penalizar quem só aparece no período de 2026 (7 meses) tratando-o como se tivesse ficado 12 meses inativo.

## 4. Fórmulas dos 5 scores

**Score de Valor** — `60% Volume + 25% Frequência + 15% Ticket` (conforme `readme.md` do projeto)

**Score de Potencial** — `40% Potencial Econômico (LIMITE_CREDITO) + 25% Potencial AD→AM + 20% Amplitude/Expansão + 15% Financeiro (baixo comprometimento de crédito)`
- Potencial AD→AM = percentil de volume AD, multiplicado por 1,0 se o cliente usa só AD (sem nenhum contrato AM aberto) ou por 0,3 se já usa AM (menor oportunidade de migração)

**Score de Recompra** — `50% Recência + 50% Frequência`

**Score de Risco** — `35% Recência (dias, direto) + 25% Queda de Volume (2025→2026 anualizado) + 20% NPS (Detrator=100, Neutro=50, Promotor=0) + 20% Cancelamento/No-show`
- O componente de cancelamento/no-show vem de `HISTORICO DE RESERVA.csv`, a fonte truncada (jan–jun/2025) — usado como sinal, não como verdade completa; clientes sem essa fonte simplesmente não têm esse componente (peso redistribuído).

**Score de ICP** — pesos do `PROMPT.DOCX`, com `LIMITE_CREDITO` no lugar de faturamento:
```
25% Potencial Econômico (LIMITE_CREDITO)
20% Aderência ao Segmento (frequência mediana do setor)
15% Frequência
15% Valor (Volume)
10% Recência
5%  Amplitude
5%  Crescimento
5%  Qualidade Cadastral
```

## 5. Risco de dupla contagem

`Frequência` entra tanto no Score de Valor (25%) quanto no Score de Recompra (50%) e no Score de ICP (15%) — é intencional (frequência é sinal legítimo em cada uma dessas dimensões, que respondem perguntas diferentes: "vale hoje", "volta a comprar", "é o perfil certo"), mas significa que **os 5 scores não são independentes entre si** — um cliente com frequência muito alta tende a subir em vários scores ao mesmo tempo. Isso é esperado e documentado, não um bug.

## 6. Distribuição de Tier resultante

| Tier | Critério | Clientes | % |
|---|---|---|---|
| A | Score_ICP ≥ 80 | 1.699 | 2,0% |
| B | 50 ≤ Score_ICP < 80 | 31.691 | 36,9% |
| C | Score_ICP < 50 | 25.164 | 29,3% |
| Revisão | Sem nenhum sinal transacional (todos `NUNCA LOCOU`) | 27.387 | 31,9% |
| Supressão | Duplicidade ou inconsistência cadastral objetiva | **0** | 0% — auditoria não encontrou `CODIGO_CLIENTE` duplicado nem linha malformada após correção; nenhum critério objetivo de supressão foi acionado |

**Nota:** Score_ICP médio de 52,5 (mediana 51,5) numa escala 0–100 é esperado, dado que a maior parte dos componentes é ela mesma um percentil — a distribuição tende ao centro por construção. O que diferencia os clientes é a posição relativa, não o valor absoluto.

## 7. Limitações explícitas

- Nenhum score usa `CNPJ`, `margem`, `desconto` ou `receita real` — dados inexistentes na base (confirmado na auditoria).
- `Score de Risco` usa cancelamento/no-show de uma fonte truncada (5 meses de 2025) — tratar como sinal parcial, nunca como taxa real anualizada.
- Aderência de segmento é uma média de setor herdada pelo cliente, não uma medida individual — dois clientes do mesmo `SECAO_CNAE` recebem o mesmo componente, mesmo que o comportamento individual varie.
- Correlação ≠ causalidade: um setor com frequência mediana alta não significa que "ser desse setor causa" mais compra — só que historicamente compra mais; é usado como proxy de aderência, não como explicação causal.
