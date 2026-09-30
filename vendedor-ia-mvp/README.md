# Vendedor IA — MVP simulado

Chat comercial totalmente sintético: o usuário assume um de 10 clientes fictícios (+1 cenário de suporte) e conversa com um
vendedor virtual. **Python calcula e valida; o LLM explica e conduz.** Nenhum dado, preço ou contrato é real.

## Executar (Windows, rede Localiza)

```bash
cd vendedor-ia-mvp
pip install -r requirements.txt
python iniciar.py                # pede a chave numa janela (ou usa API_KEY), testa o llm-gate e abre o navegador
python iniciar.py --offline      # sem GPT (vendedor em template)
python -m services.llm_client    # só o diagnóstico: URL, cabeçalho, chave presente?, proxy, DNS e 1 chamada mínima
python -m pytest
```

Use sempre `python -m ...` (sem admin, a pasta de scripts do pip não está no PATH).

### Chave do llm-gate

Mesmo padrão do `classificar_ligacoes_diario.py`: variável `API_KEY` ou janela; a chave fica **só na memória** do processo,
nunca no HTML/JS, em log ou em arquivo. `.env` é opcional (ver `.env.example`). Chamada: `POST` na URL do gate com cabeçalhos
`api_key` e `X-Correlation-ID`, `reasoning_effort=minimal` (cai para `low`/sem parâmetro se o modelo recusar), via `requests`
(usa o proxy do Windows). O custo real vem de `cost.token.total` da resposta do gate.

### Medir com a mesma régua das ligações reais

Botão **Exportar p/ classificador** (ou `GET /api/export/classificador.csv`) gera as conversas no formato de entrada do
`classificar_ligacoes_diario.py` (`cd_segmento;transcricao_limpa`, falas `AGENTE:`/`CLIENTE:`). Rode:

```bash
python classificar_ligacoes_diario.py --entrada vendedor_ia_para_classificador.csv --saida <pasta>
```

Atenção: conversas com menos de 600 caracteres compactados viram `sem_conteudo` (constante `TAMANHO_MINIMO`) — para esta
rodada, diminua para ~200 ou faça conversas com mais de 2 trocas.

## Como funciona (por mensagem)

1. `classificar` → intenção (desconto, preço, suporte, reclamação, humano, injeção…) e extração de quantidade/prazo/praça/%.
2. Orquestrador escolhe as ferramentas: `simular_preco`, `avaliar_desconto`, `registrar_proposta`, `criar_handoff`…
3. `seller.responder` pede ao LLM (ou usa o template) uma resposta **apenas com os FATOS_AUTORIZADOS**.
4. `validator` confere: valores R$ e % existem nas ferramentas, sem promessa de disponibilidade, sem “proposta enviada” sem registro,
   sem vazar instruções. Reprovou → resposta reescrita pelo template e marcada `REESCRITO_TEMPLATE`.
5. Tudo vai para SQLite (`mensagens.auditoria_json`) e `logs/conversations.jsonl`; a UI mostra intenção, ferramenta, regra, alçada, preço.

## Estrutura

`app.py` (API) · `frontend/` (HTML/CSS/JS) · `services/` (customer, pricing, rules, tools, conversation, seller, validator, llm_client,
evaluation) · `database/` (schema, seed, db) · `data/` (CSVs sintéticos, cenários, praças) · `prompts/` · `tests/`.

Endpoints: `/api/scenarios`, `/api/conversations[/{id}/messages|evaluate|reset|export]`, `/api/customers/{id}[/history|/opportunities]`,
`/api/pricing/simulate`, `/api/rules/evaluate-discount`, `/api/proposals`, `/api/handoffs`, `/api/metrics`. Docs em `/docs` (OpenAPI, base para o agente do Teams).

## Cenários (régua C12/C7 do classificador)

Cada cenário traz, no painel da esquerda, o **roteiro de quem faz o papel do cliente** e os códigos esperados: objeção (OB),
produto (PR), dado concreto (CH/B3) e problema (P). Dados concretos calculados em Python: C002 CH2 (diárias × mensal),
C003 B3 (queda de volume); regras sintéticas: C004 CH1, C006 CH4, C010 CH6. Crédito/cadastro PJ (P13) gera encaminhamento
e deixa a proposta condicionada. "Multa de trânsito" (P3) é suporte; "multa contratual" é regra. **S012_MISTO**: suporte (P3)
encaminhado primeiro, depois uma pergunta leve de telemetria (PR3) — evita o OP1 sem forçar venda; S011 (senha) não oferece nada.

## Decisões / limites do MVP

- Alçadas por cliente em `data/regras_negociacao.csv` (C001 3%, C003 2%, C007 2%, C009 1%, C010 1%, demais 0%). Acima da alçada: 1º pedido
  → contraproposta no teto + oferta de handoff; 2º pedido (ou pedido de humano/reclamação/suporte) → handoff criado.
- `max_cotacoes` limita cotações por **praça** distinta (C009 = 2). Vigência das regras é informativa (não bloqueia).
- Não há simulação de crédito nem confirmação de disponibilidade; o vendedor diz isso e não promete.
- Avaliador: notas determinísticas (diagnóstico, aderência, objeção, próximo passo, handoff, desfecho) + comentários do LLM se configurado.
- Botão “Assumir cliente” do plano não foi implementado: o usuário já é sempre o cliente.
- Classificação de intenção é por palavras-chave (suficiente para os roteiros do MVP); trocar por classificador LLM/estruturado é a evolução natural.
