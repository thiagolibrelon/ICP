# Vendedor IA — onde estamos e onde queremos chegar

> Consolidação das decisões e entregas até 30/09/2026. Tudo no simulador é **fictício**.
> Código: pasta `vendedor-ia-mvp/`, branch `claude/new-session-rkmsb8`.

---

## 1. O objetivo

Validar, num ambiente 100% simulado, se um **vendedor autônomo com IA** (GPT 5.4 mini via llm-gate) consegue atender a
**venda interna** com qualidade comercial e **sem sair das regras**, antes de qualquer integração real (Teams, WhatsApp,
Salesforce, preços reais).

Princípio central, mantido desde o plano original: **o Python calcula e decide; o GPT conversa.**

---

## 2. Como chegamos até aqui

| Etapa | O que aconteceu | Decisão |
|---|---|---|
| Plano oficial (Parte II) | 10 cenários + 1 de suporte, HTML + Python + SQLite + GPT | Ponto de partida |
| **v1** | Construída conforme o plano. Rodou na máquina da Localiza (`python -m uvicorn`) | Funcionou, mas... |
| Conexão com o gate | Erros: `.env` com aspas, URL duplicada, cabeçalho `api_key`, erro 11001 (httpx ignorava o proxy do Windows) | Cliente do LLM alinhado ao `classificar_ligacoes_diario.py`: `requests`, `api_key`, `X-Correlation-ID`, `reasoning_effort=minimal` |
| **Auditoria da v1** | Maior falha: quem "entendia" o cliente era uma regra de palavras-chave; o GPT só reescrevia. O MVP não testava a IA de verdade | Refazer o "cérebro" |
| Debate de desenho | Venda interna só atende cadastrado e é **receptiva**; banco próprio com 4 modelos; comparação com o que o mercado faz (n8n / agentes com ferramentas) | **v2** |
| **v2** | GPT conduz a conversa inteira consultando ferramentas; experimento A × B; conversa livre | Rodou na Localiza, inclusive um teste 100% livre ✅ |

---

## 3. O que existe hoje (v2)

### 3.1 Mundo simulado (banco próprio, fictício)

**Catálogo** (preço por veículo):

| Modelo | Diária | Mensal 12m | 24m | 36m | Margem IA | Margem gerente |
|---|---|---|---|---|---|---|
| Onix | R$ 159 | R$ 2.690 | R$ 2.540 | R$ 2.420 | 3% | 6% |
| Polo | R$ 169 | R$ 2.890 | R$ 2.730 | R$ 2.600 | 3% | 6% |
| Creta | R$ 239 | R$ 3.890 | R$ 3.670 | R$ 3.490 | 2% | 5% |
| Dolphin (elétrico) | R$ 259 | R$ 4.290 | R$ 4.050 | R$ 3.850 | 4% | 8% |

- **Volume automático:** 5 a 9 veículos −2%; 10 ou mais −4% (não gasta margem).
- **Margem em 2 níveis:** até a margem da IA, ela aprova; até a do gerente, o **gerente simulado aprova só com
  contrapartida** (24+ meses ou 5+ veículos); acima, negado com contraproposta.
- **Estoque compartilhado** (SP / Curitiba / BH) com prazo de entrega quando falta. Proposta registrada reserva unidades;
  a conversa seguinte já vê menos. Botão *Reiniciar estoque*.
- **12 clientes cadastrados**, com perfis dos ICPs do repositório (5 ICP1, 4 ICP2, 2 ICP3, 1 ICP5 com 2 CNPJs), cada um
  com uma situação e um roteiro. Mais 5 roteiros genéricos (suporte, multa, reclamação, pedir humano, arrancar margem) e
  a **conversa livre**.

### 3.2 O experimento A × B

| | **Modo B — oficial** | **Modo A — controle ("GPT puro")** |
|---|---|---|
| Quem conduz | GPT, do início ao fim, sem roteiro | GPT, do início ao fim |
| De onde vêm os números | Ferramentas (`avaliar_proposta`, `consultar_catalogo`, comparações...) | Tabela inteira no prompt, **com margens** |
| Margem | O GPT **nunca vê**; a ferramenta decide | O GPT vê e decide sozinho |
| Quando erra | 1 reescrita automática; persistindo, mensagem segura | **Só marca**, nunca corrige |

É o mesmo padrão de "agente com ferramentas" usado no mercado (n8n, Copilot Studio), com uma diferença deliberada:
**a regra da margem vive no código, não no prompt.** O comparativo A × B mede, com dado, se isso importa.

### 3.3 Ferramentas do vendedor (modo B)

`consultar_cliente` · `identificar_cliente` · `consultar_catalogo` · `comparar_diaria_mensal` (Challenger: equilíbrio
em 17 dias/mês) · `comparar_eletrico` (Dolphin compensa a partir de ~930 km/mês contra Creta e ~3.721 contra Onix) ·
`avaliar_proposta` · `registrar_proposta` · `criar_handoff`.

As comparações dizem a verdade quando **não** compensa (ex.: diária é melhor para quem usa 6 dias/mês).

### 3.4 Naturalidade: a vendedora "Fernanda"

- Persona **Fernanda**, da venda interna; **nunca diz que é humana** (se perguntarem, é a assistente virtual do time).
- Guia de estilo WhatsApp no prompt: mensagens curtas, 1 a 3 balões, uma pergunta por vez, acompanha o tom do cliente,
  usa o cadastro com naturalidade, sem listas/markdown e sem fórmulas de robô ("Entendo sua preocupação", "Fico à
  disposição"...).
- Na tela, cada balão aparece em sequência com "Fernanda está digitando…" e pausa proporcional ao tamanho.
- Mensagem segura e de contingência reescritas com tom humano.
- **Tiques de robô** são medidos (não bloqueiam): entram na avaliação e no comparativo A × B.
- Próximo nível de naturalidade: exemplos reais anonimizados dos melhores vendedores (camada 2 da seção 5).

### 3.5 Pacote gerente/diretor (visão de operação)

- **Adicionais no mensal** (preço fixo, sem desconto): Proteção total (R$ 189), Telemetria (R$ 59) e pacote de +1.000 km
  (R$ 180) — franquia de 2.000 km/mês por veículo. A Fernanda oferece quando conecta com a dor (km acima da franquia,
  multa no condutor errado, obra/campo).
- **Roteamento por tier**: Tier A (Kappa Logística e Grupo Mu) é do executivo dedicado — a IA acolhe e transfere; as
  ferramentas bloqueiam cotação e proposta para Tier A.
- **Qualificação**: a Fernanda registra quem decide, quem mais participa e quando a decisão sai (medido: qualificou
  antes da proposta?).
- **Handoff com briefing**: o humano recebe resumo, necessidade, objeção, próximo passo sugerido, qualificação, última
  condição avaliada, propostas e últimas mensagens — montado pelo sistema, não pela memória do GPT.
- **Painel do gerente**: concessões (desconto, quem aprovou, contrapartida, margem cedida/mês, receita e adicionais)
  e fila de handoffs com o briefing.
- **Áudio**: botão 🎤 grava como cliente de WhatsApp; o áudio é transcrito pelo llm-gate (`/audio/transcriptions`) e
  segue o mesmo fluxo, marcado como [ÁUDIO TRANSCRITO] (a Fernanda confirma números/cidade se algo parecer estranho).
  O diagnóstico (`python -m services.llm_client`) informa se o gate tem transcrição; se não tiver, o botão desativa.

### 3.6 Modo treino (vendedor humano) — `/treino`

Os papéis se invertem: **o GPT faz o cliente e o vendedor humano vende**. No fim, uma nota pela **régua C12**.

- **12 personas** (uma por cliente) com contato, abertura (receptivo), **segredos** que só aparecem com boas perguntas
  (25 no total), **objeções** com códigos OB, condição de aceite, desafio Challenger e janela de adicional.
- **3 dificuldades** (fácil, médio, difícil) e **2 modos**: *treino* (coach dá uma dica a cada troca) e *prova* (sem dicas).
- O vendedor usa a **calculadora da alçada** (mesmas regras de preço, volume, gerente e estoque) e pode registrar
  proposta — sem mexer no estoque do simulador. Pode responder por áudio 🎤.
- **Nota final (0–10) por dimensão**, com justificativa, trecho literal da fala do vendedor (conferido pelo sistema),
  "como melhorar" e "você poderia ter dito": diagnóstico, Challenger com dado (régua C12; sem dado concreto, máximo 4),
  objeções (R1–R6), qualificação, adicionais, fechamento (FC1–FC5, próximo passo, prazo), tom e **disciplina de margem**
  (100% calculada pelo sistema: desconto sem contrapartida, limite revelado, preço que não bate com a tabela).
  O diagnóstico mistura a avaliação com o que o sistema sabe que foi descoberto (x de y informações-chave).
- **Quem vê:** o próprio vendedor (nota e justificativa ao encerrar) e o gestor em "Minha evolução / gestor" —
  **em ordem alfabética, sem ranking** (ferramenta de desenvolvimento). Mostra evolução e ponto a desenvolver.
- **Piloto sugerido:** 3 a 5 vendedores e 1 gestor. Antes de a nota "valer", 2–3 gestores avaliam as mesmas ~20
  conversas para calibrar o avaliador.

### 3.7 Identidade visual

As telas usam a mesma linguagem do **Simulador Estratégico de Frota (V3)** (`thiagolibrelon/Simulador_Final`):
topbar verde com a marca, abas, tokens de cor dos temas claro/escuro (com a chave na topbar), Inter + Playfair Display,
ícones SVG e o "hero" de resultado (nota do treino). Arquivos: `frontend/marca.css`, `frontend/marca.js` e
`frontend/assets/localiza-logo.png`.

### 3.8 Governança e medição

- **Validador**: todo R$ e % dito ao cliente precisa ter vindo de uma ferramenta; detecta margem revelada, proposta/
  protocolo afirmados sem registro e vazamento de instruções.
- **Auditoria na tela**: cada resposta mostra as ferramentas chamadas, entradas, saídas, tokens e custo real do gate.
- **Avaliação por conversa** e **Comparativo A × B** (conversas livres ficam fora).
- **Exportar p/ classificador**: gera o CSV no formato de entrada do `classificar_ligacoes_diario.py` → o vendedor IA é
  medido com a **mesma régua C12** das ligações reais.
- **Chave**: variável `API_KEY` ou janela; fica só na memória (nunca em HTML, log ou arquivo versionado).
- **Testes automáticos**: 66 (preço, alçada, gerente, estoque, comparações, agente A/B, validador, API, cliente do LLM).

### 3.9 Guia dentro da ferramenta — `/guia`

Terceira tela, com **Roadmap** (plano completo com status, notas e itens próprios, para acompanhar onde estamos e o que
falta), **Glossário** (110 termos, com busca) e **Como utilizar** (o `ROTEIRO_DE_TESTES.md`). O avanço fica em
`guia/roadmap_progresso.json`, fora do Git; o plano em `guia/roadmap.json`. Se mudar o roadmap do memorando, espelhe em
`guia/roadmap.json`.

### 3.10 Como rodar

```bash
cd vendedor-ia-mvp
pip install -r requirements.txt
python iniciar.py                # pede a chave, testa o gate, abre o navegador
python -m services.llm_client    # diagnóstico de conexão
python -m pytest                 # testes
```

---

## 4. O que já aprendemos

1. **O ambiente corporativo funciona**: Python, SQLite, servidor local e o llm-gate rodam na máquina da Localiza
   (usar sempre `python -m ...`; sem admin, os scripts do pip não estão no PATH).
2. **Palavras-chave não sustentam conversa real**; o GPT precisa interpretar e as ferramentas precisam decidir.
3. **Challenger exige dado concreto** (regra do time de 24/09/2026) — por isso as comparações são calculadas em Python.
4. **Challenger é ensinar, não empurrar**: a IA deve recomendar diária quando for mais barata para o cliente.
5. **Testes do simulador medem; não treinam.** Treinar a IA com as próprias conversas reforça os vícios dela.

---

## 5. Onde queremos chegar

### Próximos passos imediatos

| # | Passo | Para quê |
|---|---|---|
| 1 | **Rodada oficial A × B**: os 12 roteiros + 5 genéricos nos dois modos, reiniciando o estoque a cada par | Provar (ou não) que a trava determinística é necessária |
| 2 | **Congelar a régua**: salvar o comparativo e a nota C12 dessa rodada como linha de base | Toda mudança futura é comparada com ela |
| 3 | **Calibrar os prompts** com o que a rodada mostrar (tom, diagnóstico, fechamento) | Ajuste fino só é possível vendo o GPT real |
| 4 | **Rodar o classificador C12** nas conversas exportadas (baixar `TAMANHO_MINIMO` para ~200) | Comparar o vendedor IA com os vendedores humanos na mesma régua |

### Melhorar a IA com as transcrições reais (em camadas)

| Camada | Técnica | Status |
|---|---|---|
| 1 | Instruções no prompt | ✅ em uso |
| 2 | **Playbook**: cruzar as classificações C12 com o desfecho real e transformar o que funciona em regras e exemplos | ⏭️ próximo (enviar amostra do CSV C12, só colunas) |
| 3 | Exemplos reais (few-shot) e depois **RAG** com trechos anonimizados dos melhores vendedores | Depois do playbook |
| 4 | **Fine-tuning** | Só se 1–3 pararem de melhorar e o gate permitir |

Ciclo de melhoria: **rodar os roteiros → medir → mudar uma coisa → rodar os mesmos roteiros → manter se melhorou.**

### Entregável futuro: integração com o Aletheia

O Aletheia (análise de ligações reais em 15 prompts, 6.623 ligações consolidadas) é a fonte da régua C12 e o melhor
candidato a alimentar as camadas 2 e 3 acima. Fica no roadmap como entregável de médio prazo, **sem data**, a priorizar
depois do go/no-go de 19/12. Detalhe na seção 7.1 do `MEMORANDO_Q4_2026.md`. Resumo:

1. Medir a Fernanda e o Treino com os mesmos prompts (P1, P5, P8, P9, P10) e comparar com o time humano.
2. Realimentar personas, objeções e adicionais com a frequência real das ligações.
3. Usar as promessas (P10) no follow-up de propostas.
4. Devolver ao projeto de ICP o desfecho das ligações, para validar a segmentação.

Cuidados: só derivados anonimizados (LGPD), um conjunto de ligações reservado só para medir e conferir a cobertura de
cada prompt antes de usá-lo.

### Evoluções do simulador (a decidir)

- **Modo copiloto** (sugestão do diretor): a Fernanda escreve, o vendedor humano revisa/edita e envia — risco baixo,
  valor imediato e cada edição vira dado de treino ("sugestão da IA × o que o bom vendedor mandou").
- **Follow-up de propostas** (D+1, D+3, "vence amanhã"), **assumir conversa** e **revisão amostral** semanal.
- **Linha de base humana e metas comerciais** (conversão, ticket, desconto médio, tempo de resposta) — pré-requisito
  do Gate 1.

- **Cliente simulado pelo GPT**, seguindo os roteiros, para rodar dezenas de conversas em lote (hoje é manual).
- **Linha de base humana**: metas do vendedor IA definidas a partir dos números C12 das ligações reais
  (Challenger com dado, próximo passo, desfecho).

### Caminho até produção (gates do plano oficial)

| Gate | De → Para | Condições principais |
|---|---|---|
| 1 | HTML → **agente privado no Teams** (Copilot Studio usando a mesma API) | Rodada A × B concluída, sem preço inventado, API documentada (`/docs`) |
| 2 | Dados sintéticos → dados controlados | Aprovação de Arquitetura, Segurança e **Privacidade (LGPD: anonimizar transcrições)** |
| 3 | Consulta → cotação oficial | API oficial de preço e disponibilidade |
| 4 | Cotação → negociação | Alçadas aprovadas, handoff operacional, auditoria de concessões |
| 5 | Teams → WhatsApp | Canal aprovado, templates, proteção de dados |

---

## 6. Cuidados que não mudam

- Nenhum dado real de cliente no simulador; transcrições reais só **anonimizadas** e com aprovação.
- A chave do llm-gate nunca vai para HTML, log, print ou Git.
- Preço, margem, estoque e aprovação sempre decididos por código, nunca pelo prompt.
- Nada gerado aqui é proposta juridicamente válida.
