# ICPs Prioritários — Fase 4

**Responsável:** Patrícia Nogueira (ICP & Segmentação) — evidência validada por André Kimura
**Entrada:** `processado/df_scored_full.pkl` (85.941 clientes com scores)
**Método:** cada ICP-hipótese do `PROMPT.DOCX` foi testado contra padrão real de setor (`SECAO_CNAE`), uso de produto (AD/AM), duração de contrato e estrutura de grupo econômico — nenhum ICP foi aceito sem evidência quantitativa.

---

## ICP 1 — Operação móvel recorrente ✅ VALIDADO (confiança Alta)

**Descrição:** empresas com equipes de campo, manutenção, engenharia, facilities, telecom ou energia, com necessidade frequente de mobilidade.

**Setores que sustentam a hipótese** (score de ICP médio consistentemente acima da média geral de 52,5): Construção, Água/Esgoto/Gestão de Resíduos, Eletricidade e Gás, Informação e Comunicação, Atividades Administrativas e Serviços Complementares (onde estão classificados facilities/segurança no CNAE brasileiro).

| Métrica | Valor |
|---|---|
| Tamanho do grupo | 18.051 clientes (21,0% da base) |
| Score ICP médio | 55,99 (vs. 52,53 geral) |
| Frequência anual (mediana) | 2,0 reservas/ano |
| Volume médio 24M | 3,82 |
| % em Tier A | 2,56% (vs. 1,98% geral) |
| Participação no volume total | 26,75% |
| Região predominante | São Paulo (19,9% do grupo) |

**Produto com maior aderência:** AD (aluguel diário) — uso de AM+AD simultâneo é raro em todos os setores (<1,6%).
**Principal oportunidade:** volume alto mas Tier A ainda pequeno (2,56%) — espaço de expansão dentro do próprio grupo.
**Principal risco:** frequência mediana baixa (2/ano) mesmo sendo o maior grupo — indica muitos clientes esporádicos dentro do ICP, não uniformemente recorrentes.
**Proposta de valor:** disponibilidade rápida de veículo para deslocamento de equipe técnica/operacional, sem necessidade de frota própria parada em manutenção.
**Canal sugerido:** Inside Sales / Executivo (depende do Tier individual).

## ICP 2 — Mobilidade comercial e executiva ✅ VALIDADO (confiança Alta)

**Descrição:** representantes comerciais, consultorias, equipes executivas com deslocamento recorrente.

**Setores:** Atividades Profissionais Científicas e Técnicas (consultorias), Atividades Financeiras de Seguros e Serviços Relacionados.

| Métrica | Valor |
|---|---|
| Tamanho do grupo | 11.325 clientes (13,18% da base) |
| Score ICP médio | **61,13** (o mais alto entre os 2 ICPs validados, vs. 52,53 geral) |
| Frequência anual (mediana) | 2,0 reservas/ano |
| Volume médio 24M | 3,37 |
| % em Tier A | 4,57% (mais que o dobro da média geral) |
| Participação no volume total | 14,81% |

**Produto com maior aderência:** AD.
**Principal oportunidade:** maior concentração de Tier A da base — priorizar retenção e cross-sell aqui primeiro.
**Principal risco:** grupo menor que o ICP1, oportunidade de aquisição mais restrita numericamente.
**Proposta de valor:** flexibilidade para reuniões/visitas sem custo fixo de frota própria.
**Canal sugerido:** Executivo dedicado (Tier A/B).

## ICP 3 — Frota própria potencialmente substituível ⚠️ HIPÓTESE (nicho real, confiança Média)

**Descrição:** clientes com contratos de longa duração (uso contínuo), sinal de possível substituição de frota própria.

**Evidência:** só **1.037 clientes (1,2% da base, 10,9% de quem tem contrato aberto)** têm duração média de contrato acima de 365 dias — mas esse nicho pequeno tem características muito distintas: **volume médio de 33,76** (quase 9x a média do ICP1) e **score ICP médio de 66,38**, o mais alto entre todos os grupos analisados.

**Veredito:** não é um segmento de massa — é um nicho pequeno mas de altíssimo valor por cliente. Fica classificado como hipótese confirmada em qualidade, não em escala: vale um tratamento comercial dedicado, não uma campanha ampla.
**Nível de confiança:** Médio (N pequeno, mas o padrão é forte e consistente dentro do próprio grupo).

## ICP 4 — Demanda sazonal ou por projeto ❌ NÃO CONFIRMADO como padrão relevante

**Descrição-hipótese:** compras concentradas em períodos, projetos, obras, eventos.

**Evidência:** calculada a variabilidade (coeficiente de variação) do volume mensal por cliente entre os 16.576 clientes com histórico mensal suficiente (`VOLUME.csv`) — **a mediana de CV foi 0,185** (uso bem constante ao longo dos meses) e **apenas 0,15% da base (≈25 clientes)** teve CV acima de 1,0 (alta variabilidade, sinal de sazonalidade forte). 41,4% dos clientes têm uso praticamente constante (CV ≤ 0,3).

**Veredito:** os dados **não sustentam** este ICP como um segmento relevante em escala — a demanda da base é majoritariamente estável mês a mês, não sazonal. Fica arquivado como hipótese rejeitada, não como perfil comercial ativo. Se a Juliana (comercial) tiver evidência qualitativa de campo contrária a isso, vale revisar com uma amostra dirigida.

## ICP 5 — Cliente multiproduto ou grupo econômico ⚠️ HIPÓTESE PARCIALMENTE VALIDADA (nicho pequeno, confiança Média)

**Descrição-hipótese:** clientes com múltiplos CNPJs relacionados ou uso de mais de um produto/região.

**Evidência importante:** o campo `NOME_GRUPO` está preenchido em 98,1% da base — mas isso é enganoso, porque na maioria dos casos o "grupo" é só o nome da própria empresa isolada. Ao filtrar só grupos que de fato têm **mais de um `CODIGO_CLIENTE` associado**, o número cai para **4.672 clientes (5,44% da base)**, distribuídos em 1.756 grupos econômicos reais.

| Métrica (grupo real, N>1) | Valor |
|---|---|
| Tamanho do grupo | 4.672 clientes (5,44% da base) |
| Score ICP médio | 55,94 |
| Volume médio 24M | 3,48 |
| Participação no volume total | 6,31% |

**Correção de metodologia registrada:** não usar `NOME_GRUPO IS NOT NULL` como critério de grupo econômico daqui pra frente — usar `COUNT(CODIGO_CLIENTE) POR NOME_GRUPO > 1`.
**Principal oportunidade:** cross-sell entre CNPJs do mesmo grupo — 1.756 grupos ainda não necessariamente comprando em todos os CNPJs.

---

## Resumo

| ICP | Status | Confiança | Tamanho | % da base | % do volume |
|---|---|---|---|---|---|
| 1. Operação móvel recorrente | Validado | Alta | 18.051 | 21,00% | 26,75% |
| 2. Mobilidade comercial e executiva | Validado | Alta | 11.325 | 13,18% | 14,81% |
| 3. Frota própria substituível | Hipótese (nicho de alto valor) | Média | 1.037 | 1,21% | — |
| 4. Demanda sazonal/projeto | Rejeitado | — | ~25 | 0,15% | — |
| 5. Multiproduto/grupo econômico | Hipótese parcial (nicho) | Média | 4.672 | 5,44% | 6,31% |

**Nota de sobreposição:** ICP1, ICP2, ICP3 e ICP5 não são mutuamente exclusivos — um cliente de Construção (ICP1) também pode pertencer a um grupo econômico real (ICP5). Por isso, na `MASTER_CLASSIFICADA`, cada cliente recebe um **ICP principal** (o de maior aderência) e os demais como **tags secundárias** — mesma lógica já prevista para os clusters no `PROMPT.DOCX`.
