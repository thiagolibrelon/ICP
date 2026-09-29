# Vendedor IA — MVP simulado

Chat comercial totalmente sintético: o usuário assume um de 10 clientes fictícios (+1 cenário de suporte) e conversa com um
vendedor virtual. **Python calcula e valida; o LLM explica e conduz.** Nenhum dado, preço ou contrato é real.

## Executar

```bash
cd vendedor-ia-mvp
pip install -r requirements.txt
python -m database.seed          # gera data/*.csv e database/mvp.db (opcional: o app cria no 1º start)
python -m uvicorn app:app --reload   # abre http://localhost:8000 (use python -m no Windows sem admin)
python -m pytest
```

### LLM (opcional)

Sem chave, o sistema roda 100% offline com o vendedor determinístico (templates). Para usar o GPT via endpoint autorizado:
`cp .env.example .env` e preencha `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. A chave fica **só no backend** (nunca no HTML/JS).
`LLM_MODE`: `auto` (LLM se houver chave), `mock` (nunca chama), `llm` (falha do LLM → mensagem de contingência).
Formato esperado do endpoint: `POST {LLM_BASE_URL}/chat/completions` (compatível com OpenAI).

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

## Decisões / limites do MVP

- Alçadas por cliente em `data/regras_negociacao.csv` (C001 3%, C003 2%, C007 2%, C009 1%, C010 1%, demais 0%). Acima da alçada: 1º pedido
  → contraproposta no teto + oferta de handoff; 2º pedido (ou pedido de humano/reclamação/suporte) → handoff criado.
- `max_cotacoes` limita cotações por **praça** distinta (C009 = 2). Vigência das regras é informativa (não bloqueia).
- Não há simulação de crédito nem confirmação de disponibilidade; o vendedor diz isso e não promete.
- Avaliador: notas determinísticas (diagnóstico, aderência, objeção, próximo passo, handoff, desfecho) + comentários do LLM se configurado.
- Botão “Assumir cliente” do plano não foi implementado: o usuário já é sempre o cliente.
- Classificação de intenção é por palavras-chave (suficiente para os roteiros do MVP); trocar por classificador LLM/estruturado é a evolução natural.
