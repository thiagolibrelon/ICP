# Vendedor IA — MVP simulado (v2: venda interna receptiva)

Simulador de atendimento da **venda interna**: só clientes cadastrados, contato **receptivo** (quem começa é o cliente).
O vendedor é o GPT; preço, margem, aprovação e estoque vêm de um banco próprio **fictício** (4 modelos, 3 cidades, 12 clientes).

## Executar (Windows, rede Localiza)

```bash
cd vendedor-ia-mvp
pip install -r requirements.txt
python iniciar.py                # pede a chave numa janela (ou usa API_KEY), testa o llm-gate e abre o navegador
python -m services.llm_client    # só o diagnóstico: URL, cabeçalho, chave presente?, proxy, DNS e 1 chamada mínima
python -m pytest
```

Use sempre `python -m ...` (sem admin, a pasta de scripts do pip não está no PATH). O banco é recriado sozinho quando o
mundo simulado muda de versão.

## Os dois modos (experimento A × B)

| | Modo B — oficial | Modo A — controle ("LLM pura") |
|---|---|---|
| Quem conduz | GPT, do início ao fim, sem roteiro | GPT, do início ao fim |
| Números | só via ferramentas (`avaliar_proposta`, `consultar_catalogo`...) | tabela inteira no prompt, **inclusive margens** |
| Margem | o GPT **nunca vê**; a ferramenta decide (IA → gerente simulado → negado) | o GPT vê e decide sozinho |
| Erro detectado | 1 reescrita automática; persistindo, mensagem segura | **só marcado**, nunca corrigido |

Mesmos clientes e roteiros nos dois modos; o botão **Comparativo A × B** mostra o resultado (conversas livres ficam fora).

## Mundo simulado (tudo fictício — `database/seed.py`, espelhado em `data/`)

- **Catálogo:** Onix, Polo, Creta, Dolphin (elétrico); diária e mensal 12/24/36 meses (prazo maior = mais barato).
  Volume automático: 5–9 veículos −2%, 10+ −4%.
- **Margem em 2 níveis:** a IA aprova até a margem dela; até a margem do gerente, o **gerente simulado aprova só com
  contrapartida** (24+ meses ou 5+ veículos); acima, negado com contraproposta.
- **Estoque compartilhado** por cidade (SP, Curitiba, BH): proposta registrada reserva unidades; a próxima conversa já vê
  menos. Faltando, há prazo de entrega. Botão **Reiniciar estoque**; reiniciar uma conversa devolve o que ela reservou.
- **Challenger com dado:** `comparar_diaria_mensal` (equilíbrio em 17 dias/mês) e `comparar_eletrico` (Dolphin compensa
  a partir de ~930 km/mês contra Creta e ~3.721 km/mês contra Onix). As ferramentas dizem quando **não** compensa.
- **12 clientes** com perfis dos ICPs (`../icp_segmentacao/icps_definidos.md`): 5 do ICP1, 4 do ICP2, 2 do ICP3, 1 do ICP5
  (grupo com 2 CNPJs). Cada um tem um roteiro; há 5 roteiros genéricos (suporte, multa, reclamação, humano, arrancar margem)
  e a opção **Conversa livre** (sem roteiro, para quem quiser "brincar").

## Pacote gerente/diretor

Adicionais no mensal (proteção, telemetria, km extra), roteamento por tier (Tier A → executivo dedicado; a IA não cota),
qualificação do decisor, handoff com briefing montado pelo sistema, **Painel do gerente** (concessões e fila de handoffs)
e **áudio** (🎤 → transcrição pelo llm-gate em `/audio/transcriptions`; `LLM_STT_MODEL`, `LLM_STT_URL`).

## Modo treino (vendedor humano) — http://127.0.0.1:8000/treino

O GPT interpreta o cliente (persona com segredos, objeções e condição de aceite; 3 dificuldades) e o vendedor humano vende,
usando a calculadora da alçada. **Modo treino** (coach com dicas) ou **modo prova** (sem dicas). Ao encerrar: nota 0–10
por dimensão da régua C12, com justificativa, trecho da própria fala, como melhorar e exemplo. Disciplina de margem e
informações descobertas são calculadas pelo sistema. Evolução por vendedor em ordem alfabética (sem ranking).

## Laboratório (IA-cliente × Fernanda, em lote) — http://127.0.0.1:8000/laboratorio

A IA-cliente (as mesmas personas do Treino, com um **comportamento** por teste) conversa sozinha com a Fernanda nos modos
A e B. Cada conversa termina quando o cliente decide, quando a Fernanda registra proposta ou transfere, quando entra em
loop ou no limite de turnos (12; **24 nas conversas longas**). Ao final, o sistema confere regras, cenário e
comportamento (✅/❌) e o avaliador do Treino dá a nota C12 (opcional). Cada conversa devolve o estoque que reservou.

- **Tipos prontos:** rodada completa (12 clientes × 8 comportamentos × A e B = 192), críticos 5× (30), conversas longas
  de 24 turnos (12), red team (20), negociação de desconto (36) e teste de abertura (120). Ou personalizada.
- **Aberturas:** a Fernanda tem duas formas de começar a conversa (1 = atual; 2 = SPIN com o cadastro como hipótese).
  Seletor no Simulador, opção na rodada personalizada e bloco Abertura 1 × 2 no relatório; padrão em `FERNANDA_ABERTURA`.
- **Red team ampliado (prompt injection):** 9 ataques (36 conversas), auditor de segurança para o que regra fixa não pega
  e trava para "sou humana".
- **Modelo por papel:** Fernanda, IA-cliente e avaliador podem usar modelos diferentes (`LLM_MODEL_VENDEDORA`,
  `LLM_MODEL_CLIENTE`, `LLM_MODEL_AVALIADOR`); cada rodada guarda os modelos usados; botão **Comparar** põe rodadas lado a lado.
- **Backup:** antes de recriar o banco, cópia automática em `database/backups/`; no Guia, **Baixar banco (backup)**.
- **Frente ativa:** a Fernanda inicia o contato com a carteira, com motivo verdadeiro do cadastro. Regras no sistema
  (Tier A bloqueado, descadastro, 1 contato a cada 7 dias, 1 follow-up sem resposta, identificação como assistente
  virtual). No Simulador (seletor de frente e Painel do gerente › Carteira), no Laboratório (tipo Frente ativa, 84
  conversas) e no Treino (o vendedor chama o cliente). Detalhes em `LABORATORIO.md` §3.2.
- **Desconto e gerente:** checagens de consulta à alçada, alternativa depois do "não", aprovação do gerente inventada
  (também barrada pela trava) e preço segurado sem contrapartida; bloco **Concessões e alçada** no relatório.
- **2 conversas em paralelo** por padrão (dá para usar 1). Rodadas podem ser canceladas e retomadas; se o servidor cair,
  a rodada fica "Interrompida" e é retomada do ponto em que parou.
- Antes de iniciar, a tela mostra custo e tempo estimados. Relatório: A × B, por comportamento, conversas longas,
  checagens reprovadas, tokens e custo; exportação CSV.

## Guia da ferramenta — http://127.0.0.1:8000/guia

Tela ligada pelas abas do topo. Três abas:

- **Roadmap** — o plano completo (o que já foi construído, os 6 sprints do Q4, pedidos, gates e
  evoluções). Cada item tem status (não iniciado, em andamento, concluído, bloqueado), notas com data e, se quiser, itens
  próprios. O topo mostra o percentual, "onde estou agora" e o que ainda falta; há filtro "só o que falta".
- **Como funciona** — 4 imagens da arquitetura da Fernanda (chat × agente, uma mensagem por dentro, ferramentas e
  bases, proteção contra ataques), servidas de `docs/como_funciona/` (editável em `arquitetura.html`).
- **Glossário** — todos os termos do projeto (negócio, simulador, treino, medição, governança e ICP), com busca.
- **Como utilizar** — o `ROTEIRO_DE_TESTES.md`, lido do arquivo (sem cópia: editou o arquivo, a aba muda).
- **Laboratório** — o `LABORATORIO.md`: como usar a aba Laboratório, como ler o relatório e o que fazer quando der errado
  (em qual camada está o problema: prompt, ferramenta, validador, dados, memória ou modelo).

Onde ficam os dados: `guia/roadmap.json` (itens e fases, versionados no Git; edite para mudar o plano), `guia/glossario.json`
(termos) e `guia/roadmap_progresso.json` (**o seu avanço**: status, notas e itens próprios; criado sozinho, fica fora do Git).
Atualizar o `roadmap.json` nunca apaga o progresso já marcado. O caminho do progresso pode ser trocado com
`MVP_ROADMAP_PROGRESS`. Para guardar uma cópia, basta copiar esse arquivo.

## Chave do llm-gate

Mesmo padrão do `classificar_ligacoes_diario.py`: variável `API_KEY` ou janela; a chave fica só na memória do processo.
Chamada via `requests` (usa o proxy do Windows), cabeçalhos `api_key` e `X-Correlation-ID`, `reasoning_effort=minimal`
(cai para `low`/sem se recusado). O agente usa *tool calling* nativo; se o gate recusar `tools`, passa sozinho para um
protocolo JSON equivalente (`LLM_TOOLS`). Custo real lido de `cost.token.total`.

## Medir com a régua das ligações reais

**Exportar p/ classificador** gera `cd_segmento;transcricao_limpa` (falas `AGENTE:`/`CLIENTE:`) para o
`classificar_ligacoes_diario.py --entrada <csv> --saida <pasta>`. Conversas com menos de 600 caracteres compactados viram
`sem_conteudo` (`TAMANHO_MINIMO`) — para esta rodada, diminua para ~200.

## Estrutura

`app.py` (API) · `iniciar.py` · `frontend/` · `services/` (`catalog` = ferramentas determinísticas, `agent` = modos A/B,
`validator`, `conversations`, `evaluation`, `training`, `laboratorio`, `ativa`, `guia`, `llm_client`) · `prompts/` (base, regras B, regras A) · `guia/` (glossário e roadmap) · `database/` · `tests/`.
