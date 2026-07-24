# Time do Projeto ICP — Localiza (Locação de Veículos B2B)

Time responsável por transformar as bases brutas (`AR.csv`, `BANCO DE DADOS.csv`, `HISTORICO DE RESERVA.csv`, etc.) na `MASTER_CLASSIFICADA` com ICPs, scores, tiers, clusters e plano de ação comercial, conforme definido em `../readme.md` e `../PROMPT.DOCX`.

## Papéis

| # | Persona | Papel | Dono de |
|---|---------|-------|---------|
| 1 | [Ricardo Bittencourt](01-ricardo-lead-growth-crm.md) | Consultor Sênior Growth/CRM/Analytics/Vendas B2B — Lead | Visão executiva, decisão final, Etapa 10 |
| 2 | [Camila Duarte](02-camila-engenharia-dados.md) | Engenharia de Dados | Etapa 1 (diagnóstico), Etapa 9 (Power BI: ingestão) |
| 3 | [André Kimura](03-andre-cientista-dados-scoring.md) | Cientista de Dados / Scoring | Etapa 2 (métricas), Etapa 3 (exploratória), Etapa 5 (scores) |
| 4 | [Patrícia Nogueira](04-patricia-segmentacao-icp.md) | Estrategista de ICP & Segmentação | Etapa 4 (ICPs), Etapa 6 (clusters) |
| 5 | [Bruno Salgado](05-bruno-powerbi.md) | Desenvolvedor Power BI / BI Analyst | Etapa 9 (MASTER_CLASSIFICADA técnica, merges, DAX) |
| 6 | [Juliana Marques](06-juliana-comercial-trade.md) | Gerente Comercial / Trade | Etapa 7 (priorização), Etapa 8 (plano de ação) |
| 7 | [Rafael Toledo](07-rafael-lgpd-compliance.md) | Compliance & LGPD | Transversal — auditoria de todas as etapas |
| 8 | [Marina Lopes](08-marina-crm-automacao.md) | CRM & Automação | Tier B/C, Revisão, nutrição e reativação |

## Como o time trabalha

- **Regra do projeto** (definida no `PROMPT.DOCX`): nenhuma persona pode inventar dado, atribuir potencial sem evidência, ou confundir correlação com causalidade. Quem levanta essa bandeira é o André, mas qualquer um pode travar uma entrega por isso.
- **Ordem natural de handoff**: Camila (qualidade da base) → André (métricas e scores) → Patrícia (ICPs e clusters) → Bruno (implementação técnica) → Juliana (ação comercial) → Marina (automação Tier C). Rafael audita em paralelo, em qualquer etapa.
- **Decisão final** de trade-off (ex.: "esse peso de score está certo?", "esse ICP tem evidência suficiente ou é só hipótese?") é do Ricardo — ele é quem responde a Etapa 10 do prompt (análise executiva final).
- **Tensão estrutural conhecida**: Patrícia (quer nomear ICPs com convicção, linguagem de venda) vs. André (só confirma um ICP com evidência quantitativa, "hipótese" até provar o contrário) vs. Rafael (barra qualquer atributo sensível mesmo que melhore o score). Ricardo arbitra.
