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
`validator`, `conversations`, `evaluation`, `llm_client`) · `prompts/` (base, regras B, regras A) · `database/` · `tests/`.
