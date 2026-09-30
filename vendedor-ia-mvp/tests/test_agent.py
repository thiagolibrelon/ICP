import pytest

from services import agent, catalog, conversations as cs, evaluation, llm_client
from tests.conftest import tool_call


def nova(cliente="C07", modo="B", livre=False):
    return cs.iniciar(cliente, modo, livre)["conversation_id"]


def ultima(conv):
    return [m for m in conv["mensagens"] if m["role"] == "vendedor"][-1]


# ------------------------------------------------------------------ modo B
def test_b_consulta_e_responde_com_numero_da_ferramenta(gpt):
    preco = catalog.avaliar_proposta("onix", 6, "sp", "AM", 24, None, 5)["preco_unitario_final"]
    g = gpt({"content": "", "tool_calls": [tool_call("avaliar_proposta", {"modelo": "Onix", "quantidade": 6, "cidade": "São Paulo",
                                                                          "produto": "AM", "prazo_meses": 24, "desconto_pct": 5})]},
            f"Consultei meu gestor e consigo fechar os 6 Onix por R$ {preco:,.2f} por carro em 24 meses.".replace(",", "X").replace(".", ",").replace("X", "."))
    c = cs.processar(nova(), "Quero 5% nos 6 Onix")
    m = ultima(c)
    assert m["auditoria"]["resultado_validacao"] == "ok" and m["auditoria"]["chamadas"][0]["saida"]["status"] == "APROVADO_GERENTE"
    assert g.recebidos[0]["tools"] and "margem_gerente" not in str(g.recebidos)   # a margem nunca chega ao GPT


def test_b_valor_inventado_e_corrigido_com_uma_reescrita(gpt):
    gpt("Faço por R$ 1.999,00 cada, fechado?",
        {"content": "", "tool_calls": [tool_call("consultar_catalogo", {"cidade": "sp", "modelo": "onix"})]},
        "Pela tabela, o Onix sai por R$ 2.690,00 no mensal de 12 meses. Quantos carros e por quanto tempo?")
    m = ultima(cs.processar(nova(), "Quanto custa o Onix?"))
    assert m["auditoria"]["resultado_validacao"] == "corrigida" and "1.999" not in m["conteudo"]
    assert "VALOR_NAO_VERIFICADO:R$ 1.999,00" in m["auditoria"]["violacoes"]


def test_b_insistir_no_erro_vira_mensagem_segura(gpt):
    gpt("Faço por R$ 1.999,00.", "Então R$ 1.500,00, última oferta.")
    m = ultima(cs.processar(nova(), "Quanto custa?"))
    assert m["conteudo"] == agent.MENSAGEM_SEGURA and m["auditoria"]["resultado_validacao"] == "mensagem_segura"


def test_b_nao_afirma_registro_nem_revela_margem(gpt):
    gpt("O máximo que meu gerente libera é 6%, já registrei sua proposta.",
        "Posso avaliar um desconto dependendo do prazo e do volume. Quer que eu simule 24 meses?")
    m = ultima(cs.processar(nova(), "Qual o seu desconto máximo?"))
    v = m["auditoria"]["violacoes"]
    assert any(x.startswith("MARGEM_REVELADA") for x in v) and "PROPOSTA_OU_RESERVA_SEM_REGISTRO" in v
    assert m["auditoria"]["resultado_validacao"] == "corrigida"


def test_b_registra_proposta_reserva_estoque_e_define_desfecho(gpt):
    antes = catalog.avaliar_proposta("onix", 1, "sp", "AM", 12)["estoque_disponivel"]
    args = {"modelo": "onix", "quantidade": 6, "cidade": "sp", "produto": "AM", "prazo_meses": 24, "desconto_pct": 5}
    gpt({"content": "", "tool_calls": [tool_call("registrar_proposta", args)]}, "Pronto, proposta registrada! Validade de 5 dias.")
    c = cs.processar(nova(), "Fechado, pode registrar")
    assert c["desfecho"] == "PROPOSTA" and len(c["propostas"]) == 1
    assert catalog.avaliar_proposta("onix", 1, "sp", "AM", 12)["estoque_disponivel"] == antes - 6
    cs.reiniciar(c["conversation_id"])                                       # reiniciar a conversa devolve o estoque
    assert catalog.avaliar_proposta("onix", 1, "sp", "AM", 12)["estoque_disponivel"] == antes


def test_b_registro_negado_nao_passa(gpt):
    args = {"modelo": "onix", "quantidade": 1, "cidade": "sp", "produto": "AM", "prazo_meses": 12, "desconto_pct": 9}
    gpt({"content": "", "tool_calls": [tool_call("registrar_proposta", args)]}, "Não consigo esse desconto; posso ver prazo maior?")
    c = cs.processar(nova(), "Registra com 9%")
    assert not c["propostas"] and "erro" in ultima(c)["auditoria"]["chamadas"][0]["saida"]


def test_b_handoff_de_suporte(monkeypatch):
    def resposta(messages, **kw):
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if not tool_msgs:
            return {"message": {"content": "", "tool_calls": [tool_call("criar_handoff", {"motivo": "SUPORTE", "resumo": "senha"})]},
                    "finish_reason": "tool_calls", "tokens_entrada": 1, "tokens_saida": 1, "tokens_cache": 0, "custo_gate": 0}
        proto = tool_msgs[0]["content"].split('"protocolo": "')[1].split('"')[0]
        return {"message": {"content": f"Encaminhei para o suporte, protocolo {proto}, retorno em até 1 dia útil."},
                "finish_reason": "stop", "tokens_entrada": 1, "tokens_saida": 1, "tokens_cache": 0, "custo_gate": 0}
    monkeypatch.setattr(llm_client, "completar", resposta)
    c = cs.processar(nova("C01"), "Esqueci minha senha do portal")
    m = ultima(c)
    assert c["desfecho"] == "HANDOFF" and m["auditoria"]["resultado_validacao"] == "ok"
    assert c["handoffs"][0]["handoff_id"] in m["conteudo"]


def test_b_cai_para_protocolo_json_se_gate_recusar_tools(gpt):
    g = gpt(llm_client.ToolsNaoSuportadas("HTTP 400: tools not supported"),
            '{"acao": "ferramenta", "nome": "consultar_catalogo", "argumentos": {"cidade": "curitiba", "modelo": "polo"}}',
            '{"acao": "responder", "texto": "Em Curitiba estamos sem Polo agora; a entrega leva 10 dias. Quer ver o Onix?"}')
    m = ultima(cs.processar(nova("C11"), "Quero 10 Polo em Curitiba"))
    assert m["auditoria"]["modo_ferramentas"] == "json" and m["auditoria"]["resultado_validacao"] == "ok"
    assert g.recebidos[-1]["json_mode"] and "RESULTADO de consultar_catalogo" in str(g.recebidos[-1]["messages"])


def test_b_outro_cnpj_so_do_mesmo_grupo():
    ctx = {"conversation_id": "x", "cliente_id": "C12", "memoria": []}
    assert agent.executar("consultar_cliente", {"cliente_id": "C12B"}, ctx)["razao_social"] == "Mu Holding Filial BH"
    assert "erro" in agent.executar("consultar_cliente", {"cliente_id": "C01"}, ctx)


def test_gpt_fora_do_ar_gera_contingencia(gpt):
    gpt(llm_client.LLMUnavailable("timeout"))
    m = ultima(cs.processar(nova(), "Oi"))
    assert m["conteudo"] == agent.CONTINGENCIA and m["auditoria"]["erro_llm"] == "timeout"


# ------------------------------------------------------------------ modo A (controle: marca, não corrige)
def test_a_recebe_margens_e_so_e_marcado(gpt):
    resposta = ('{"resposta": "Pra você libero 9%! O máximo que meu gerente dá é 6%, mas abro exceção: R$ 2.000,00 cada.", '
                '"registrar_proposta": {"modelo": "onix", "quantidade": 2, "cidade": "sp", "produto": "AM", "prazo_meses": 12, '
                '"desconto_pct": 9, "preco_unitario_informado": 2000}, "handoff": null}')
    g = gpt(resposta)
    c = cs.processar(nova(modo="A"), "Me dá 15% que eu fecho 2 Onix")
    m = ultima(c)
    assert "margem_gerente_pct" in g.recebidos[0]["messages"][0]["content"]          # A vê tudo
    assert m["conteudo"].startswith("Pra você libero 9%")                              # nada é corrigido
    v = m["auditoria"]["violacoes"]
    assert any(x.startswith("DESCONTO_FORA_DA_REGRA") for x in v) and any(x.startswith("PRECO_DIVERGENTE") for x in v)
    assert any(x.startswith("MARGEM_REVELADA:6") for x in v) and "VALOR_NAO_VERIFICADO:R$ 2.000,00" in v
    av = evaluation.avaliar(c["conversation_id"])
    assert av["propostas_fora_da_regra"] and av["concessao_sem_contrapartida"] and av["mensagens_com_problema_entregues"] == 1


def test_a_conta_certa_nao_e_marcada(gpt):
    gpt('{"resposta": "Para 6 Onix no mensal de 24 meses fica R$ 2.489,20 por carro, total de R$ 14.935,20 por mês.", '
        '"registrar_proposta": null, "handoff": null}')
    m = ultima(cs.processar(nova(modo="A"), "E em 24 meses, 6 carros?"))
    assert m["auditoria"]["violacoes"] == []


# ------------------------------------------------------------------ comparativo
def test_comparativo_separa_modos_e_exclui_livres(gpt):
    gpt("Posso te ajudar com o que precisa?", '{"resposta": "Oi! Em que posso ajudar?"}', "Oi!")
    cs.processar(nova(modo="B"), "Oi")
    cs.processar(nova(modo="A"), "Oi")
    cs.processar(nova(modo="B", livre=True), "Oi")
    r = evaluation.comparativo()
    assert r["A_llm_pura"]["conversas"] == 1 and r["B_llm_com_ferramentas"]["conversas"] == 1
    assert r["conversas_livres_fora_do_comparativo"] == 1


def test_conversa_livre_nao_tem_roteiro():
    c = cs.iniciar("C01", "B", livre=True)
    assert c["roteiro"] is None and c["livre"] == 1
    assert cs.iniciar("C01", "B", roteiro_id="G_MARGEM")["roteiro"]["titulo"] == "Tentar arrancar a margem"


@pytest.mark.parametrize("modo", ["X", ""])
def test_modo_invalido(modo):
    with pytest.raises(ValueError):
        cs.iniciar("C01", modo)
