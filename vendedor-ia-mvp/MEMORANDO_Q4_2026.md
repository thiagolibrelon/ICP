# MEMORANDO

| | |
|---|---|
| **Para** | [Nome do gestor] — [Cargo] |
| **De** | [Seu nome] — [Área] |
| **Data** | 01/10/2026 · atualizado em 05/10/2026 |
| **Assunto** | Vendedor IA e Treino de Vendas com IA — status do MVP, definição de sucesso e roadmap do 4º trimestre de 2026 |
| **Classificação** | Interno. O MVP usa apenas dados fictícios |

> **Atualização de 06/10/2026:** o Treino de vendas virou **frente própria** (app `treino-vendedor`, com banco, roadmap e roteiro próprios). Este documento continua cobrindo as duas frentes no Q4; as metas e o cronograma do Treino passam a ser acompanhados em `../treino-vendedor/ROADMAP_TREINO.md`.

---

## 1. Resumo executivo

Construímos e validamos tecnicamente, na rede da empresa e com o GPT 5.4 mini via llm-gate, um MVP com **duas frentes**:

1. **Vendedor IA ("Fernanda")**: atende clientes cadastrados pelo WhatsApp (simulado), diagnostica a necessidade, ensina
   com números (comportamento Challenger), negocia dentro da alçada e registra proposta ou transfere para um humano com um
   resumo completo. **Preço, desconto, estoque e aprovação são sempre decididos por código, nunca pelo GPT.**
2. **Treino de vendas**: o GPT faz o papel do cliente e o vendedor humano vende. No fim, o vendedor recebe uma **nota pela
   régua C12** (a mesma do classificador de ligações), com justificativa, o trecho da própria fala e onde melhorar.

Para testar em escala, construímos um **Laboratório**: uma IA faz o papel do cliente e conversa sozinha com a Fernanda,
em lote, e o sistema confere cada conversa. Isso torna viáveis as ~190 conversas por rodada, o red team e a comparação
de versões (aberturas, modelos) dentro do trimestre.

Também desenhamos a **frente ativa**: a Fernanda chamando clientes da carteira, com um motivo verdadeiro do cadastro
(contrato vencendo, diária alta, frota própria). Ela já roda no simulador, no Laboratório e no Treino, com as regras de
contato no sistema (cliente estratégico nunca, quem pediu para parar nunca mais, frequência limitada). No Q4 ela é
testada; o uso real fica para 2027.

E já temos a **referência do time em setembro** (C12 das ligações receptivas de venda): fechou na ligação 12,7%,
tentativa comercial 41%, Challenger com dado 22,9%.

**Objetivo do Q4:** chegar a 19/12/2026 com **evidência suficiente para decidir** se a Fernanda segue para um piloto real
no Teams no 1º trimestre de 2027 e com o **Treino calibrado e em uso** por um grupo piloto.

**O que peço nesta etapa:** **US$ 200 de uso do llm-gate no trimestre** (detalhe em `docs/PEDIDO_ORCAMENTO_Q4.md`), validação das metas (seção 5), acesso a dados de referência (C12 e CRM), início do processo
de LGPD e cerca de 4 horas de 2 a 3 gestores em novembro para calibrar a nota do Treino (seção 8).

---

## 2. Contexto

- O plano original previa um MVP 100% sintético (HTML + Python + SQLite + GPT) para validar a hipótese comercial antes de
  qualquer integração real (Teams, WhatsApp, Salesforce, preços reais).
- O mercado resolve "vendedor com IA" com **agentes com ferramentas**: n8n e Copilot Studio são exemplos. O nosso segue o
  mesmo padrão, com uma diferença deliberada: **a margem fica no código, não no prompt**.
- A empresa já tem um ativo raro: transcrições reais classificadas pelo **C12** (venda, Challenger com dado concreto,
  problemas). O projeto usa essa régua para medir a IA e os vendedores na mesma escala.

---

## 3. O que já está construído (MVP v3, em funcionamento)

### 3.1 Vendedor IA — Fernanda

| Capacidade | Como funciona |
|---|---|
| Atendimento receptivo | Somente clientes cadastrados; o cliente inicia; texto ou **áudio** (transcrito pelo llm-gate) |
| Mundo simulado | 4 modelos (Onix, Polo, Creta, Dolphin elétrico), 3 cidades, diária e mensal 12/24/36, **estoque compartilhado** |
| Negociação governada | Alçada em 2 níveis: a IA aprova até a margem dela; o **gerente simulado aprova só com contrapartida** (24+ meses ou 5+ carros); acima disso, negado com contraproposta |
| Challenger honesto | Comparações calculadas: diária × mensal e elétrico × combustão. **Diz quando não compensa** |
| Adicionais | Proteção total, telemetria e km extra, oferecidos quando se conectam à situação do cliente |
| Roteamento | Clientes **Tier A** vão para o executivo dedicado; a IA acolhe e transfere |
| Qualificação | Registra quem decide, quem participa e quando a decisão sai |
| Handoff | O humano recebe **briefing completo**: necessidade, objeção, próximo passo, decisor, condições e últimas mensagens |
| Naturalidade | Persona "Fernanda", estilo WhatsApp, balões curtos, sem fórmulas de robô; **nunca se passa por humana** |
| Segurança | Validador confere todo R$ e % contra o sistema; 1 reescrita automática; persistindo, uma mensagem segura. Também barra "o gerente aprovou" sem aprovação e "sou humana" |
| Proteção contra ataques | Prompt injection em 4 camadas: instruções, arquitetura (a IA não vê as margens), ferramentas que recusam e trava antes de enviar |
| Duas aberturas | Abertura 1 (atual) × abertura 2 (SPIN, cadastro como hipótese a confirmar), comparadas no Laboratório antes da linha de base |
| Gestão | **Painel do gerente**: concessões (desconto, quem aprovou, contrapartida, margem cedida/mês, adicionais) e fila de handoffs |
| Experimento A × B | Modo B (oficial, com ferramentas) × modo A (GPT "puro", com as margens no prompt). Mede se a trava faz diferença |

### 3.2 Treino de vendas

| Capacidade | Como funciona |
|---|---|
| 12 personas | Cada cliente tem informações escondidas (25 no total), objeções, condição de aceite e desafio do cenário |
| 3 dificuldades × 2 modos | Fácil / médio / difícil; **modo treino** (coach dá dicas ao vivo) e **modo prova** (sem dicas) |
| Ferramentas reais | O vendedor usa a calculadora da alçada; registrar proposta no treino não mexe no estoque |
| Nota pela régua C12 | 8 dimensões, cada uma com justificativa, **trecho da fala** (conferido pelo sistema), "como melhorar" e "você poderia ter dito" |
| Partes objetivas | Disciplina de margem e informações descobertas são **calculadas pelo sistema**; Challenger sem dado concreto vale no máximo 4 (regra de 24/09/2026) |
| Quem vê | O próprio vendedor e o gestor; **ordem alfabética, sem ranking** (ferramenta de desenvolvimento) |

### 3.3 Laboratório (testes em lote)

| Capacidade | Como funciona |
|---|---|
| IA-cliente × Fernanda | As 12 personas do Treino, cada uma com um comportamento (colaborativo, resistente, pede desconto, pede humano, suporte, GPT fora do ar…), conversam sozinhas com a Fernanda nos modos A e B |
| Tipos de rodada | Completa (192), críticos 5× (30), conversas longas de 24 turnos (12), red team (36), negociação de desconto (36), teste de abertura (120) ou personalizada |
| Checagens automáticas | Regras (preço, alçada, margem, Tier A, briefing), cenário (honestidade), comportamento, negociação (consultou a alçada, ofereceu alternativa, não inventou aprovação) e segurança (auditor de segurança para o que regra fixa não pega) |
| Relatório | A × B, por comportamento, abertura 1 × 2, concessões e alçada, nota C12, custo por conversa e segundos por turno; CSV |
| Comparação de modelos | Modelo por papel (Fernanda, IA-cliente, avaliador); cada rodada guarda os modelos; rodadas lado a lado |
| Operação | 2 conversas em paralelo; cancelar e retomar; estimativa de custo e tempo antes de iniciar; backup automático do banco |

### 3.4 Frente ativa (a Fernanda chama o cliente)

| Capacidade | Como funciona |
|---|---|
| Carteira priorizada | Quem chamar, por quê e se pode chamar agora; o motivo vem do cadastro (contrato vencendo, diária alta, frota própria, km acima da franquia) |
| Regras de contato no sistema | Tier A nunca recebe contato ativo da IA; descadastro vale para sempre; 1 contato a cada 7 dias; 1 follow-up sem resposta |
| Transparência | A primeira mensagem tem que dizer que ela é assistente virtual (a trava barra se não disser) |
| Reações testadas | Interessado, ocupado, irritado, pede para parar, pessoa errada, já fechou com concorrente, não responde |
| Treino ativo | O vendedor humano chama o cliente com o motivo da carteira; a nota avalia a abertura e o respeito ao tempo do cliente |

### 3.5 Base técnica

- Roda no notebook corporativo (Python + SQLite + navegador) e chama o GPT pelo llm-gate, com a mesma chave e o mesmo padrão
  do `classificar_ligacoes_diario.py`. A chave nunca fica em disco, no navegador ou em log.
- 211 testes automáticos; exportação das conversas no formato do classificador C12; auditoria de cada decisão na tela.
- Guia dentro da ferramenta: roadmap com progresso, glossário, roteiro de testes, guia do Laboratório e 4 imagens de
  "como funciona" prontas para apresentação.

---

## 4. Aprendizados até aqui

1. **O ambiente corporativo comporta o projeto**: o gate, a rede e o notebook funcionam, com os ajustes de proxy e de cabeçalho já feitos.
2. **Palavras-chave não sustentam conversa real.** O GPT precisa interpretar, e as ferramentas precisam decidir.
3. **Challenger exige dado concreto**, por isso as comparações são calculadas pelo sistema.
4. **Ensinar não é empurrar**: a IA recomenda diária quando é mais barata para o cliente.
5. **Testes do simulador medem; não treinam.** A IA melhora com regras, exemplos dos melhores vendedores e a mesma régua
   aplicada em ciclos (rodar → medir → ajustar → rodar de novo).

---

## 5. Definição de sucesso do Q4/2026

> **Sucesso = em 19/12, ter evidência para uma decisão go/no-go do piloto no Teams (Q1/2027) e o Treino calibrado
> e adotado pelo grupo piloto.** O Q4 não entrega produção; entrega prova.

### A. Segurança — modo B (tolerância zero: qualquer falha bloqueia o Gate 1)

| Critério | Meta |
|---|---|
| Preço, desconto ou estoque inventado **entregue ao cliente** | 0 |
| Desconto fora da alçada ou sem regra | 0 |
| Margem ou limite de desconto revelado | 0 |
| Cliente Tier A negociado pela IA | 0 |
| Handoff sem briefing | 0 |
| Cenários de honestidade (diária é melhor; elétrico não compensa) | 100% corretos |
| A × B | Modo B com 0 violações; modo A com violações mensuráveis (prova de que a trava é necessária) |

### B. Qualidade comercial — modo B (metas propostas, a confirmar)

| Critério | Meta |
|---|---|
| Diagnóstico antes do preço | ≥ 90% das conversas |
| Qualificou o decisor | ≥ 80% |
| Próximo passo e prazo definidos | ≥ 85% |
| Challenger com dado quando o cenário pede | ≥ 70% |
| Adicional oferecido quando há janela | ≥ 50% |
| Indicadores C12 da Fernanda (mesmo classificador, 5.4 mini) | **≥ time humano**. Referência de set/2026 nas receptivas de venda: Challenger com dado 22,9% (meta da Fernanda: 50%), tentativa comercial 41%, conectou à situação 26% |
| Teste cego "humano ou IA?" | Avaliadores acertam ≤ 60% (perto do acaso) |

### C. Robustez e operação

| Critério | Meta |
|---|---|
| Consistência (mesma conversa repetida 5×) | Critérios de segurança em 100% das repetições |
| Mensagem segura ou contingência | ≤ 3% das respostas |
| Tempo de resposta | p90 ≤ 8 s (a confirmar após a 1ª rodada) |
| Custo por conversa | Medido (custo real do gate) e com teto definido |

### D. Treino de vendas

| Critério | Meta |
|---|---|
| Adoção | 3 a 5 vendedores e 1 gestor; ≥ 4 treinos por vendedor |
| Calibração da nota | IA a até ±1,5 ponto da média dos gestores em ≥ 80% das dimensões (~20 conversas) |
| Evolução | +1 ponto médio entre o 1º e o último treino |
| Satisfação | ≥ 8/10 entre os vendedores do piloto |

---

## 6. Plano de testes (resumo)

Detalhado no **Roteiro de Testes** (arquivo `ROTEIRO_DE_TESTES.md`), escrito para que uma pessoa que não conhece o
sistema consiga executá-lo.

| Camada | O que é | Volume no Q4 |
|---|---|---|
| Testes automáticos | Regressão do código a cada mudança | Contínuo (211 hoje) |
| Matriz de cenários | 12 clientes × 8 comportamentos × modos A e B | ~190 conversas por rodada; 3 rodadas |
| Repetição | Mesma conversa 5× para medir variação do GPT | Cenários críticos |
| Red team | 9 ataques: margem, injeção de instruções, preço falso, "amigo do diretor", dado pessoal, tirar do papel, vazar as regras, mensagem falsa de sistema, "diz que é humana" | 36 conversas por rodada |
| Teste de abertura | Abertura atual × SPIN com o cadastro como hipótese, modo B, 3 repetições | 120 conversas, antes da Rodada 1 |
| Comparação de modelos | O mesmo teste com outro modelo da Fernanda (cliente e avaliador fixos) | Críticos, negociação e conversas longas |
| Frente ativa | A Fernanda abre a conversa; 7 reações do cliente; identificação, motivo verdadeiro, descadastro, pessoa errada, follow-up | 84 conversas por rodada |
| Humanos reais | Vendedores como clientes; teste cego | ~50 conversas |
| Não funcional | Gate fora do ar, lentidão, concorrência, estoque disputado, custo | 1 bateria por rodada |
| Calibração | Gestores × IA nas mesmas conversas de treino | ~20 conversas |

**Regra de ouro:** nenhuma mudança de prompt ou regra entra sem rodar a suíte inteira de novo. Prompt é tratado como código:
versionado e com teste de regressão.

**Construído no início de outubro:** o **Laboratório** (executor em lote), que coloca o "GPT-cliente" do Treino para
conversar com a Fernanda automaticamente e confere cada conversa. Era o que faltava para as ~190 conversas por rodada
caberem no trimestre.

---

## 7. Roadmap do 4º trimestre (sprints de 2 semanas)

| Período | Vendedor IA | Treino | Marco |
|---|---|---|---|
| **S1** · 01–17/out | ~~Executor em lote~~ (pronto: Laboratório); teste de abertura; suíte v1 congelada; referência humana (C12 + CRM) | Seleção do piloto e dos gestores; treinamento de uso | **Metas assinadas** |
| **S2** · 20–31/out | **Rodada 1** (matriz A × B); análise e ajuste de prompts | Início do piloto (≥ 2 treinos/vendedor) | Relatório da rodada 1 |
| **S3** · 03–14/nov | Playbook com trechos dos melhores vendedores (anonimizados); validação do áudio | Coleta de ~20 conversas para calibração | Playbook v1 |
| **S4** · 17–28/nov | **Rodada 2**; red team; teste cego | **Calibração** gestores × IA; ajuste da rubrica | Relatórios da rodada 2 e da calibração |
| **S5** · 01–12/dez | **Rodada 3** (regressão final); custo e latência consolidados | Fechamento do piloto (≥ 4 treinos/vendedor); pesquisa de satisfação | Relatório final de testes |
| **S6** · 15–19/dez | **Pacote do Gate 1**: resultados, caso de negócio, arquitetura Teams, plano de LGPD | Proposta de expansão do Treino em 2027 | **Decisão go/no-go** |

Considera ~11 semanas úteis, com congelamento após 19/12.

---

## 8. Dependências e pedidos

| # | Pedido | Com quem | Até |
|---|---|---|---|
| 0 | **Orçamento de US$ 200 de uso do llm-gate no Q4** (`docs/PEDIDO_ORCAMENTO_Q4.md`) | Gestor | 07/out |
| 1 | Validar as metas da seção 5 | Gestor | 10/out |
| 2 | Amostra de ligações classificadas pelo C12 e indicadores do CRM (conversão, ticket, desconto médio, tempo de resposta) | Dados / Comercial | 17/out |
| 3 | Confirmar no llm-gate: suporte a `tools`, transcrição de áudio, cota para as rodadas e **quais modelos estão disponíveis** além do 5.4 mini (para comparação) | Time do llm-gate | 17/out |
| 4 | Abrir o processo de LGPD: uso de transcrições anonimizadas e das notas de treino (dado de funcionário, com RH) | Privacidade / RH | Abrir até 10/out |
| 5 | 3 a 5 vendedores e 1 gestor para o piloto do Treino (≈ 30 min/semana) | Gestão comercial | 17/out |
| 6 | 2 a 3 gestores para a calibração (≈ 4 h cada) | Gestão comercial | Novembro |
| 7 | Onde o backend vai rodar no piloto do Teams (preparação para 2027) | TI / Arquitetura | Dezembro |
| 8 | Confirmar que a cláusula de contato do contrato cobre WhatsApp e atendimento automatizado/IA (frente ativa) | Jurídico | 31/out |

---

## 9. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| O gate não aceitar chamada de ferramentas nativa | Médio | Retorno automático para o protocolo JSON (já implementado) |
| A aprovação de LGPD atrasar | Alto | Abrir o processo já; o playbook pode começar com trechos escritos pelos gestores |
| Variação natural do GPT esconder falhas | Alto | Repetição 5× e tolerância zero medida em 100% das repetições |
| Falta de tempo dos vendedores no piloto | Médio | Treinos curtos (10 min), agenda fixa semanal |
| A nota do Treino não ter credibilidade | Alto | Calibração com gestores antes de "valer"; uso para desenvolvimento, não para cobrança |
| Expectativa de produção no Q4 | Médio | Alinhar que o Q4 entrega prova e decisão; produção é 2027 |
| Contato ativo percebido como spam | Alto (quando for real) | Motivo verdadeiro e útil, identificação como assistente virtual, descadastro imediato, 1 contato a cada 7 dias; começar como copiloto (o vendedor envia) |
| Prompt injection (alguém tentar mudar as regras da IA) | Alto | Defesa em 4 camadas; a IA não vê margens e não decide preço; red team com 9 ataques a cada rodada |
| Injeção indireta quando entrar o CRM real (texto de sistemas com "instruções") | Alto (a partir do Gate 2) | Tratar texto vindo de sistemas como dado, não ordem; teste específico no Laboratório antes de ligar o CRM |
| Perder rodadas e treinos numa atualização | Médio | Backup automático do banco antes de recriar e download no Guia |
| O modelo atual (5.4 mini) ser fraco para a conversa | Médio | Comparação de modelos no Laboratório, com cliente e avaliador fixos e custo por conversa |

---

## 10. Próximos passos (próximos 10 dias)

1. Reunião de 30 min para **aprovar o orçamento de US$ 200**, **validar as metas** e os pedidos da seção 8.
2. Pedido formal da amostra do C12 e do CRM e abertura do processo de LGPD.
3. **Teste de abertura** no Laboratório (120 conversas) e escolha da abertura padrão; em seguida, **Rodada 1** (linha de base).
4. Se o llm-gate oferecer outro modelo, **comparação de modelos** da Fernanda no Laboratório.
5. Convite ao grupo piloto do Treino.
6. Reclassificar 12 meses de ligações receptivas com o 5.4 mini (referência do time) e pergunta ao jurídico sobre a frente ativa.

**Rito de acompanhamento:** status quinzenal de 30 minutos (números da rodada, decisões pendentes e riscos) e um registro
de decisões compartilhado.

---

## Anexos

- `ONDE_ESTAMOS.md` — histórico completo das decisões e do que foi construído.
- `ROTEIRO_DE_TESTES.md` — roteiro passo a passo dos testes.
- `LABORATORIO.md` — como usar o Laboratório e o que fazer quando der errado (em qual camada está o problema).
- `docs/como_funciona/` — 4 imagens: chat × agente, uma mensagem por dentro, ferramentas e bases, proteção contra ataques.
- `docs/modelos/` — modelos do relatório final de testes e do pacote de decisão do Gate 1.
- `docs/PEDIDO_ORCAMENTO_Q4.md` — pedido de US$ 200 com destino de cada dólar e controles.
- `dados_referencia/REFERENCIA_TIME_SETEMBRO_2026.md` — referência do time (C12, setembro/2026).
- `README.md` — como instalar e executar.
