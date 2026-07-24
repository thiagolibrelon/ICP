# Plano de Ação Comercial (Fase 7)

**Responsáveis:** Juliana Marques (comercial/trade) + Ricardo Bittencourt (arbitragem e análise executiva final)
**Base:** `master_classificada/MASTER_CLASSIFICADA.csv` (85.941 clientes), `icp_segmentacao/*`, `saidas/tabela3_acoes_por_segmento.csv`
**Data:** 2026-07-24

---

## 1. Recomendações práticas (Etapa 8 do `PROMPT.DOCX`)

### 1. Aquisição de empresas semelhantes aos melhores ICPs
- **Público:** empresas com perfil firmográfico igual ao ICP1 (Construção, Água/Esgoto, Eletricidade/Gás, Informação/Comunicação, Administrativas) e ICP2 (Consultorias, Financeiras), fora da base atual.
- **Justificativa:** ICP1+ICP2 juntos são 32,2% da base mas respondem por 41,6% do volume, com score ICP médio bem acima da média geral (55,99 e 61,13 vs. 52,53).
- **Impacto:** Alto | **Esforço:** Alto | **Prazo:** Médio prazo | **KPI:** nº de novos CNPJs ativados nesses setores | **Critério de sucesso:** taxa de conversão de lead→contrato igual ou acima da média histórica desses setores | **Teste:** piloto por setor antes de escalar | **Grupo de controle:** sim, comparar setor-alvo vs. aquisição genérica.

### 2. Personalização das campanhas por ICP
- **Público:** todos os 22.343 clientes já atribuídos a ICP1/ICP2/ICP3/ICP5.
- **Justificativa:** cada ICP tem proposta de valor e canal diferentes já documentados em `icps_definidos.md`.
- **Impacto:** Médio | **Esforço:** Médio | **Prazo:** Curto prazo | **KPI:** taxa de resposta por campanha segmentada vs. campanha genérica.

### 3. Aumento da conversão dos leads
- **Público:** clientes com cotação registrada mas sem reserva (`COTACAO_GERAL_TOTAL > 0` e `RESERVA_TOTAL = 0`).
- **Justificativa:** cobertura de conversão (`RESERVA - COTAÇÃO - CONVERSAO.csv`) já mostra taxa de conversão calculável por cliente — dá pra isolar quem cotou e não fechou.
- **Impacto:** Alto | **Esforço:** Médio | **Prazo:** Curto prazo | **KPI:** `% Conversão` médio do grupo-alvo.

### 4. Aumento da segunda compra
- **Público:** cluster **Novos com potencial** (340 clientes, recência média de só 10 dias, score de potencial médio mais alto entre clusters ativos — 63,0).
- **Justificativa:** menor recência de todos os clusters — janela de onboarding ainda aberta.
- **Impacto:** Médio | **Esforço:** Médio | **Prazo:** Curto prazo | **KPI:** taxa de segunda reserva em até 90 dias | **Grupo de controle:** sim.

### 5. Aumento da frequência
- **Público:** cluster **Alto potencial subpenetrado** (2.191 clientes, score de potencial no quartil superior mas valor capturado abaixo da mediana).
- **Justificativa:** é o cluster com maior gap entre potencial e valor atual — oportunidade de crescimento em quem já é cliente, não aquisição nova.
- **Impacto:** Alto | **Esforço:** Médio | **Prazo:** Médio prazo | **KPI:** variação de `FREQUENCIA_ANUAL` pré/pós ação.

### 6. Migração de aluguel diário para mensal
- **Público:** cluster **Potencial de aluguel mensal** (34 clientes — usam só AD, nunca AM, com volume de AD no quartil superior).
- **Justificativa:** sinal direto e objetivo (uso intenso de AD sem nenhum AM) — grupo pequeno mas com critério de entrada muito preciso.
- **Impacto:** Médio | **Esforço:** Baixo | **Prazo:** Curto prazo | **KPI:** taxa de migração AD→AM no grupo-alvo.

### 7. Retenção dos clientes em risco
- **Público:** cluster **Em risco** (997 clientes, ainda `ATIVO`, Score de Risco no quartil superior).
- **Justificativa:** ainda ativos — janela de intervenção antes de virarem inativos; representam 1,44% do volume total, perda evitável com ação rápida.
- **Impacto:** Médio-Alto | **Esforço:** Médio | **Prazo:** Curto prazo (ação imediata) | **KPI:** taxa de recuperação (volta a reservar em 90 dias) | **Grupo de controle:** sim, essencial pra medir se a ação realmente evitou perda.

### 8. Reativação dos inativos
- **Público:** 28.635 clientes `INATIVO`, segmentados em recentes (532), intermediários (7.856) e antigos (20.247).
- **Justificativa:** juntos são 33,3% da base — mas o ticket médio cai muito com o tempo de inatividade (recentes 1,96 → intermediários 2,07 → antigos 0,52), então a intensidade de investimento deve cair na mesma proporção.
- **Impacto:** Médio (alto em volume de clientes, baixo por cliente) | **Esforço:** Baixo (automação) | **Prazo:** Curto prazo pra recentes, contínuo pra antigos | **KPI:** taxa de reativação por faixa.

### 9. Cross-sell
- **Público:** cluster **Potencial de cross-sell** (478 clientes em grupo econômico real que ainda usam só 1 agência).
- **Justificativa:** distinto de "tem campo Grupo preenchido" (98% da base) — são os 5,44% com grupo econômico real (>1 CNPJ), o sinal genuíno de oportunidade.
- **Impacto:** Médio | **Esforço:** Médio | **Prazo:** Médio prazo | **KPI:** nº de CNPJs adicionais ativados dentro do mesmo grupo.

### 10. Exploração de grupos econômicos
- Mesmo público do item 9 — ação combinada, não duplicar esforço. Ver correção de metodologia registrada em `icps_definidos.md` (ICP5): usar contagem real de CNPJs por grupo, não só o campo preenchido.

### 11. Redução da dependência de desconto
- **Não implementável com os dados atuais.** A auditoria confirmou ausência total de campo de desconto/tarifa aplicada na base — o cluster "Sensíveis a Preço" ficou com 0 clientes por falta de critério objetivo. **Recomendação:** solicitar à fonte de dados a inclusão de tarifa aplicada vs. tarifa tabela antes de qualquer iniciativa aqui.

### 12. Otimização da distribuição das carteiras comerciais
- **Público:** todos os Tiers.
- **Justificativa:** hoje 1.699 clientes em Tier A (2,0% da base) concentram atendimento consultivo — dentro da faixa de 80-150 clientes/executivo sugerida no `readme.md`, dá pra calcular o nº de executivos necessários: 1.699 ÷ 115 (médio da faixa) ≈ **15 executivos dedicados**. Tier B (31.691 clientes) ÷ 450 (médio de 300-600) ≈ **70 posições de Inside Sales**.
- **Impacto:** Alto (estrutural) | **Esforço:** Alto | **Prazo:** Médio prazo | **KPI:** carteira por executivo dentro da faixa recomendada.

---

## 2. Matriz Impacto × Esforço — 10 iniciativas prioritárias

| # | Iniciativa | Impacto | Esforço | Quadrante |
|---|---|---|---|---|
| 1 | Retenção de clientes em risco (item 7) | Alto | Médio | **Fazer primeiro** |
| 2 | Aumento de frequência — Alto potencial subpenetrado (item 5) | Alto | Médio | **Fazer primeiro** |
| 3 | Migração AD→AM (item 6) | Médio | Baixo | **Ganho rápido** |
| 4 | Reativação de inativos recentes (item 8, subgrupo recentes) | Médio | Baixo | **Ganho rápido** |
| 5 | Aumento de conversão de leads cotados (item 3) | Alto | Médio | **Fazer primeiro** |
| 6 | Otimização de distribuição de carteiras (item 12) | Alto | Alto | **Projeto estrutural** |
| 7 | Aquisição em ICP1/ICP2 (item 1) | Alto | Alto | **Projeto estrutural** |
| 8 | Aumento de segunda compra — Novos com potencial (item 4) | Médio | Médio | **Planejar** |
| 9 | Cross-sell em grupos econômicos reais (itens 9-10) | Médio | Médio | **Planejar** |
| 10 | Personalização de campanhas por ICP (item 2) | Médio | Médio | **Planejar** |

**Fora da priorização atual:** redução de dependência de desconto (item 11) — bloqueada por ausência de dado, não por falta de impacto potencial.

---

## 3. Análise Executiva Final (Etapa 10 — Ricardo)

1. **Perfil que mais gera valor hoje:** cluster **Campeões** (1,91% dos clientes, 23,59% do volume) — setores predominantes de ICP1/ICP2.
2. **Perfil com maior potencial não capturado:** cluster **Alto potencial subpenetrado** (2.191 clientes, score de potencial no quartil superior, valor abaixo da mediana).
3. **Variáveis que melhor diferenciam clientes de alto valor:** frequência anual e recência (ambas entram em 3 dos 5 scores) — não faturamento nem porte, que têm baixíssima cobertura.
4. **Segmentos a priorizar para aquisição:** ICP1 (Operação móvel recorrente) e ICP2 (Mobilidade comercial e executiva) — evidência mais forte e maior participação de volume.
5. **Clientes para atendimento humano:** Tier A (1.699) e o nicho ICP3 (1.037, volume médio 9x acima da média).
6. **Clientes que podem ficar em jornada automatizada:** Tier C (25.164) e Inativos antigos (20.247).
7. **Maior oportunidade de aumento de frequência:** cluster Alto potencial subpenetrado.
8. **Inativos com maior probabilidade de retorno:** Inativos recentes (532, recência média de 55 dias, ainda dentro do ciclo esperado).
9. **Clientes com potencial de aluguel mensal:** cluster dedicado, 34 clientes, critério objetivo (só AD, volume alto).
10. **5 ações comerciais mais importantes:** retenção de risco, expansão do subpenetrado, conversão de cotação→reserva, migração AD→AM, reativação de inativos recentes (itens 1-5 da matriz).
11. **Dados adicionais que aumentariam a precisão:** tarifa/desconto aplicado (bloqueia item 11 inteiro), faturamento com cobertura melhor que 28,6%, porte com cobertura melhor que 6,95%, `HISTORICO DE RESERVA.csv` sem truncamento.
12. **Evolução do modelo após os primeiros testes:** repetir o cálculo de Score/Tier trimestralmente, validar se os grupos de controle dos itens 4 e 7 confirmam causalidade (não só correlação) antes de escalar orçamento.
