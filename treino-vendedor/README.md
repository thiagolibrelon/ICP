# Treino de vendas

O vendedor humano atende um cliente simulado pelo GPT e, no fim, recebe uma nota pela régua do time (C12), com
justificativa, trecho da própria fala, como melhorar e exemplo. Tudo é **fictício**: clientes, CNPJs, preços e estoque.
As notas são para o desenvolvimento do vendedor, não para ranking nem cobrança.

Frente própria desde 06/10/2026. Nasceu dentro do `vendedor-ia-mvp` (Fernanda e Laboratório) e foi separada: tem
app, banco, mundo simulado e testes próprios, e não importa nada do outro projeto.

## Executar (Windows, rede da empresa)

```
pip install -r requirements.txt
python iniciar.py            # abre em http://127.0.0.1:8001
python iniciar.py --offline  # sem GPT: só para ver as telas
```

A chave do llm-gate vem de `API_KEY` (ou `LLM_API_KEY` / `.env`); se não existir, `iniciar.py` pede numa janela e não
salva em lugar nenhum. A porta é 8001 para rodar junto com a Fernanda (8000). Modelo por papel: `LLM_MODEL_CLIENTE`,
`LLM_MODEL_COACH`, `LLM_MODEL_AVALIADOR` (senão `LLM_MODEL`, padrão gpt-5.4-mini).

## O que tem

- **30 cenários** (clientes C01–C30) com segredos, objeções (OB1–OB7), condição de aceite, desafio e as competências
  que treinam. 3 dificuldades; frente **receptiva** (o cliente chama) ou **ativa** (você chama, com o motivo do cadastro).
- **Modo treino** (com coach) ou **modo prova** (sem coach; é o que conta para o nível).
- **Coach IA: ligado/desligado.** No modo treino, antes de iniciar ou no meio. A troca fica registrada e a evolução mostra
  a média com coach ligado, desligado, trocado no meio e em prova (frente de líder coach).
- **Nota completa (12 dimensões)** com os códigos dos 15 prompts de análise de ligações: abertura (AB), diagnóstico
  (B1–B10 + segredos descobertos), qualificação, Challenger (CH, sem dado = no máximo 4), objeções (OB × R), adicionais,
  oportunidades perdidas (OP), disciplina de margem (calculada pelo sistema), promessas (PM), fechamento (FC), sinais da
  conta (IC e eventos raros) e tom. A **escuta** (P12) é calculada pelo sistema e aparece no resultado.
- **Trilha:** 9 competências, cenários por competência e nível Bronze/Prata/Ouro (só provas contam). Botão "Trilha".
- **Calculadora da alçada:** as regras do mundo simulado (preço, volume, gerente, estoque), sem mexer no estoque.
- **Evolução por vendedor** em ordem alfabética, sem ranking. **Backup do banco** na aba "Baixar banco".

## Documentos

| Arquivo | Conteúdo |
|---|---|
| `TRILHA_TREINAMENTO.md` | Desenho da trilha, para validar com o gestor e o líder coach |
| `ROADMAP_TREINO.md` | O que foi feito e o que falta no Q4 e em 2027 |
| `ROTEIRO_DE_TESTES_TREINO.md` | Roteiro para testar sem conhecer o sistema |
| `GLOSSARIO.md` | Termos e códigos |

## Estrutura

```
app.py                 API (FastAPI) e a página do Treino
iniciar.py             sobe o servidor na porta 8001
services/training.py   ciclo do treino, coach, nota e evolução
services/trilha.py     competências, níveis e progresso
services/catalog.py    calculadora da alçada (motor de preço)
services/carteira.py   motivo do contato na frente ativa
services/validator.py  checagens da disciplina de margem
services/llm_client.py chamada ao llm-gate (cliente, coach, avaliador)
database/              mundo simulado (seed.py, personas.py) e banco treino.db
prompts/               cliente simulado, coach e avaliador
frontend/              tela do Treino
tests/                 testes automáticos (python -m pytest)
```
