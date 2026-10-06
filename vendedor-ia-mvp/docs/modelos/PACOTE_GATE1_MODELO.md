# Pacote de decisão — Gate 1: piloto interno da Fernanda no Teams

> **MODELO.** Documento para a decisão go/no-go de **19/12/2026** (marco S6-03). Preencha os campos `[ ]`.
> Critério de qualidade: quem decide entende o que está sendo pedido e por quê, sem precisar de explicação extra.

| | |
|---|---|
| Para | [gestor / diretoria] |
| De | [responsável] |
| Data | [dd/12/2026] |
| Decisão pedida | Aprovar o piloto **interno** da Fernanda no Teams no 1º trimestre de 2027 |

---

## 1. O que estamos pedindo

[Uma frase. Ex.: "Aprovar um piloto de 3 meses em que vendedores e gestores do time usam a Fernanda dentro do Teams,
ainda com dados fictícios, para validar uso real antes de qualquer contato com cliente."]

**O que o piloto NÃO é:** não fala com cliente, não usa dados reais de cliente, não dá preço oficial e não fecha
negócio. Isso só vem nos próximos portões, cada um com aprovação própria.

---

## 2. Por que agora: o que os testes provaram

| Pergunta | Resposta dos testes | Evidência |
|---|---|---|
| Ela erra preço, desconto ou estoque com o cliente? | [ex.: "Não. Zero em N conversas."] | Relatório final §3 |
| A trava do sistema é necessária? | [ex.: "Sim. Sem ela, X% das conversas tiveram erro."] | Comparação A × B |
| Ela vende bem? | [ex.: "Nota C12 X, contra Y do time."] | Relatório final §4 |
| Ela é honesta quando o cliente não deve comprar? | [ex.: "Sim, em 100% das repetições."] | Críticos 5× |
| Ela respeita alçada e gerente? | [ex.: "Sim: nenhuma concessão sem contrapartida."] | Concessões e alçada |
| Quanto custa? | [ex.: "US$ X por conversa."] | Relatório final §5 |
| O Treino ajuda os vendedores? | [ex.: "+X pontos de evolução; satisfação Y/10."] | Relatório da frente do Treino |

---

## 3. Caso de negócio

| Ganho esperado | Como medir no piloto | Estimativa |
|---|---|---|
| Atendimento fora do horário e em picos | Conversas atendidas fora do horário comercial | [ ] |
| Resposta mais rápida ao cliente | Tempo até a primeira resposta | [ ] s × hoje [ ] min |
| Desconto mais disciplinado | Desconto médio e concessões sem contrapartida | [ ]% × time [ ]% |
| Time focado em clientes estratégicos e casos complexos | Horas do time liberadas por semana | [ ] h |
| Vendedores mais preparados (Treino) | Evolução da nota C12 | [ ] pontos |

**Custo do piloto:** uso do llm-gate ~US$ [ ]/mês (base: US$ [ ] por conversa × [ ] conversas) + [horas do time].

---

## 4. Como o piloto funciona

- **Quem usa:** [N] vendedores e [N] gestor(es) do time de venda interna.
- **Onde:** agente privado no Teams (Copilot Studio), chamando a **mesma** API do MVP. O cérebro não muda; muda a porta
  de entrada.
- **Dados:** continuam fictícios. Nenhum dado real de cliente.
- **Duração:** [ ] semanas, de [ ] a [ ].
- **Arquitetura:** [anexar a imagem "Como funciona" 2 e o desenho Teams → API → bases].
- **Onde o backend roda:** [decisão do pedido PED-07].

---

## 5. Riscos e como estão controlados

| Risco | Controle | Situação |
|---|---|---|
| IA inventar preço ou condição | Preço, desconto e estoque vêm do sistema; trava confere antes de enviar | Testado: [ ] |
| Vazamento de margem ou regras internas | IA não vê margens; trava barra menções | Testado: [ ] |
| Uso de dados pessoais | Dados fictícios no piloto; LGPD em andamento para fases seguintes | [status do processo de LGPD] |
| Custo fora de controle | Teto por conversa e acompanhamento semanal | Teto: US$ [ ] |
| Indisponibilidade do llm-gate | Mensagem de contingência e transferência para o time | Testado: [ ] |
| A IA se passar por humano | Ela sempre se apresenta como assistente virtual | Testado: [ ] |

---

## 6. Critérios de sucesso do piloto (para decidir o Gate 2)

| Critério | Meta |
|---|---|
| Segurança | Zero erro de preço, desconto ou estoque, também no Teams |
| Adoção | [ ]% dos participantes usando toda semana |
| Satisfação dos vendedores e gestores | ≥ [ ]/10 |
| Qualidade (nota C12) | Mantida em relação aos testes do Q4 |
| Custo | Dentro do teto |

---

## 7. Próximos portões (visão 2027)

| Portão | O que muda | Condição |
|---|---|---|
| Gate 1 (este pedido) | HTML → agente interno no Teams | Testes do Q4 aprovados |
| Gate 2 | Dados fictícios → dados reais controlados | Arquitetura, Segurança e LGPD |
| Gate 3 | Consulta → cotação oficial | API oficial de preço e estoque |
| Gate 4 | Cotação → negociação | Alçadas aprovadas, gerente real com fila de aprovação, auditoria |
| Gate 5 | Teams → WhatsApp com o cliente | Canal aprovado, templates e proteção de dados |

---

## 8. Decisão

| Opção | O que acontece |
|---|---|
| **Aprovar** | Piloto começa em [data]; primeiro balanço em [data] |
| **Aprovar com condições** | [quais condições] |
| **Não aprovar agora** | Ajustes a fazer: [lista]; nova avaliação em [data] |

Decisão: ______________________ · Responsável: ______________________ · Data: ___/___/______

---

**Anexos:** Relatório final de testes · Memorando Q4/2026 · Imagens "Como funciona" · CSVs das rodadas
