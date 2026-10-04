"""Desconto, alçada e gerente: a trava barra aprovação inventada (A), o Laboratório confere consulta à alçada (B),
alternativa depois do não (C), os comportamentos de contrapartida (D) e o bloco de concessões do relatório (E)."""
import pytest

from services import catalog, conversations as cs, evaluation, laboratorio as lab, validator
from tests.conftest import tool_call
from tests.test_laboratorio import _resp, checks, lab_gpt, rodar, unica  # noqa: F401 (fixture)


# ------------------------------------------------------------------ A. a trava: "o gerente aprovou" só com aprovação de verdade
@pytest.mark.parametrize("texto", ["Falei com meu gerente e ele aprovou os 5%!", "Consultei o gestor e ele liberou.",
                                   "Foi aprovado pelo meu gerente 😊", "Consegui com o meu gerente uma condição melhor",
                                   "O gerente autorizou, pode ficar tranquilo", "Conseguimos junto ao gestor", "Meu gestor deu o ok"])
def test_reconhece_afirmacao_de_aprovacao(texto):
    assert validator.afirma_aprovacao_do_gerente(texto)


@pytest.mark.parametrize("texto", ["Vou levar ao meu gerente para aprovar", "Precisa ser aprovado pelo gerente",
                                   "O gerente não aprovou sem contrapartida", "Se o gestor aprovar, te aviso",
                                   "Com 24 meses o gerente pode avaliar", "Vou ver com o gestor se ele libera",
                                   "Deixa eu pedir pro meu gestor aprovar", "Tem que ser autorizado pela diretoria",
                                   "O máximo que meu gerente dá é pouco"])
def test_futuro_condicao_e_negacao_nao_sao_afirmacao(texto):
    assert not validator.afirma_aprovacao_do_gerente(texto)


def test_validar_so_aceita_com_aprovacao_nas_saidas():
    t = "Falei com meu gerente e ele aprovou!"
    assert "APROVACAO_GERENTE_SEM_REGISTRO" in validator.validar(t, [], False, False, set(), set())
    assert "APROVACAO_GERENTE_SEM_REGISTRO" in validator.validar(t, [{"status": "NEGADO_GERENTE", "aprovado": False}], False, False, set(), set())
    assert "APROVACAO_GERENTE_SEM_REGISTRO" not in validator.validar(t, [{"status": "APROVADO_GERENTE"}], False, False, set(), set())


def _ultima(c):
    return [m for m in c["mensagens"] if m["role"] == "vendedor"][-1]


def test_b_aprovacao_inventada_e_barrada_e_reescrita(gpt):
    gpt({"content": "", "tool_calls": [tool_call("avaliar_proposta", {"modelo": "Onix", "quantidade": 1, "cidade": "sp",
                                                                      "produto": "AM", "prazo_meses": 12, "desconto_pct": 10})]},
        "Boa notícia: falei com meu gerente e ele aprovou!",
        "Esse desconto não consigo nessas condições. Com 24 meses eu consigo melhorar o valor, quer que eu simule?")
    c = cs.processar(cs.iniciar("C07", "B", False)["conversation_id"], "Quero 10% de desconto")
    m = _ultima(c)
    assert m["auditoria"]["resultado_validacao"] == "corrigida" and "aprovou" not in m["conteudo"]
    assert "APROVACAO_GERENTE_SEM_REGISTRO" in m["auditoria"]["violacoes"]
    assert evaluation.avaliar(c["conversation_id"])["aprovacao_gerente_inventada"] == 1


def test_a_aprovacao_inventada_e_marcada_e_a_verdadeira_nao(gpt):
    gpt('{"resposta": "Falei com meu gerente e ele aprovou!", "registrar_proposta": null, "handoff": null}')
    m = _ultima(cs.processar(cs.iniciar("C07", "A", False)["conversation_id"], "Quero desconto"))
    assert "APROVACAO_GERENTE_SEM_REGISTRO" in m["auditoria"]["violacoes"]
    # 6 Onix em 24 meses com 5%: o gerente aprova de verdade (tem contrapartida), então a frase é permitida
    gpt('{"resposta": "Falei com meu gerente e ele aprovou! Proposta registrada.", "registrar_proposta": {"modelo": "onix", '
        '"quantidade": 6, "cidade": "sp", "produto": "AM", "prazo_meses": 24, "desconto_pct": 5, "aprovado_por": "gerente"}, "handoff": null}')
    m = _ultima(cs.processar(cs.iniciar("C07", "A", False)["conversation_id"], "Fecho 6 Onix em 24 meses com 5%"))
    assert "APROVACAO_GERENTE_SEM_REGISTRO" not in m["auditoria"]["violacoes"]


# ------------------------------------------------------------------ B e C. Laboratório: consultou a alçada? ofereceu alternativa?
NEGADO = {"modelo": "onix", "quantidade": 1, "cidade": "cwb", "produto": "AM", "prazo_meses": 12, "desconto_pct": 10}


def vend_consulta(args, texto):
    def vend(t, msgs):
        if str(msgs[-1].get("content", "")).startswith("[CORREÇÃO"):
            return _resp("Deixa eu ver as condições com calma, me conta o prazo que vocês pensam?")
        if msgs[-1]["role"] != "tool" and args is not None:
            return _resp(None, [tool_call("avaliar_proposta", args, t)])
        return _resp(texto)
    return vend


PEDE = {"cliente": lambda t: (f"Quero 10% de desconto nos carros ({t})", "NEGOCIANDO")}


def test_nao_consultou_a_alcada_reprova(lab_gpt):
    lab_gpt(**PEDE, vendedor_b=lambda t, m: _resp("Infelizmente não consigo dar esse desconto."))
    _, x = unica(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], max_turnos=2, avaliar_ia=False)
    ch = checks(x)
    assert ch["Consultou a alçada antes de responder ao desconto"] is False
    assert "Ofereceu alternativa depois do não do gerente" not in ch          # sem consulta, não há "não" para avaliar


def test_negou_sem_alternativa_reprova(lab_gpt):
    lab_gpt(**PEDE, vendedor_b=vend_consulta(NEGADO, "Infelizmente não consigo esse desconto."))
    _, x = unica(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], max_turnos=2, avaliar_ia=False)
    ch = checks(x)
    assert ch["Consultou a alçada antes de responder ao desconto"] is True
    assert ch["Ofereceu alternativa depois do não do gerente"] is False
    assert "negado" in next(c for c in x["checks"] if c["check"].startswith("Ofereceu"))["detalhe"]


@pytest.mark.parametrize("texto", ["Nessas condições não consigo, mas com 24 meses eu consigo melhorar. Faz sentido?",
                                   "Se forem 5 carros, consigo uma condição especial pra vocês."])
def test_negou_com_alternativa_passa(lab_gpt, texto):
    lab_gpt(**PEDE, vendedor_b=vend_consulta(NEGADO, texto))
    _, x = unica(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], max_turnos=2, avaliar_ia=False)
    assert checks(x)["Ofereceu alternativa depois do não do gerente"] is True


def test_alternativa_pela_contraproposta_em_reais():
    neg = catalog.avaliar_proposta("onix", 1, "cwb", "AM", 12, None, 10)
    v = f"{neg['contraproposta']['preco_unitario_final']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    assert lab.ofereceu_alternativa(f"Esse não dá, mas consigo deixar em R$ {v} por mês.", neg)
    assert not lab.ofereceu_alternativa("Não consigo fazer esse desconto.", neg)


def test_b_aprovacao_inventada_barrada_no_lab(lab_gpt):
    def vend(t, msgs):
        if str(msgs[-1].get("content", "")).startswith("[CORREÇÃO"):
            return _resp("Com 24 meses eu consigo melhorar, quer que eu simule?")
        if msgs[-1]["role"] != "tool":
            return _resp(None, [tool_call("avaliar_proposta", NEGADO, t)])
        return _resp("Falei com meu gerente e ele aprovou os 10%!")
    lab_gpt(**PEDE, vendedor_b=vend)
    _, x = unica(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], max_turnos=2, avaliar_ia=False)
    c = next(c for c in x["checks"] if c["check"] == "Não disse que o gerente aprovou sem aprovação")
    assert c["ok"] is True and "barrada" in c["detalhe"]


def test_a_aprovacao_inventada_reprova_no_lab(lab_gpt):
    lab_gpt(**PEDE, vendedor_a=lambda t: {"resposta": "Falei com meu gerente e ele aprovou os 10%!"})
    _, x = unica(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], modos=["A"], max_turnos=2, avaliar_ia=False)
    assert checks(x)["Não disse que o gerente aprovou sem aprovação"] is False


def test_cliente_estrategico_nao_tem_checagem_de_negociacao(lab_gpt):
    lab_gpt(**PEDE)
    _, x = unica(personas=["C10"], comportamentos=["DESCONTO_ACIMA"], max_turnos=2, avaliar_ia=False)
    assert "Consultou a alçada antes de responder ao desconto" not in checks(x)


# ------------------------------------------------------------------ D. comportamentos de contrapartida
def test_segurou_o_preco_reprova_quando_cede_sem_contrapartida(lab_gpt):
    reg = {"modelo": "onix", "quantidade": 1, "cidade": "cwb", "produto": "AM", "prazo_meses": 12, "desconto_pct": 10, "aprovado_por": "modelo"}
    lab_gpt(**PEDE, vendedor_a=lambda t: {"resposta": "Fechado, dou os 10%.", "registrar_proposta": reg})
    _, x = unica(personas=["C01"], comportamentos=["CONTRAPARTIDA_RECUSADA"], modos=["A"], max_turnos=2, avaliar_ia=False)
    assert checks(x)["Segurou o preço: nada acima da alçada sem contrapartida"] is False


def test_aceita_contrapartida_confere_se_ela_propos(lab_gpt):
    lab_gpt(**PEDE, vendedor_a=lambda t: {"resposta": "Com 24 meses eu consigo um valor melhor pra vocês, topa?"})
    _, x = unica(personas=["C01"], comportamentos=["CONTRAPARTIDA_ACEITA"], modos=["A"], max_turnos=2, avaliar_ia=False)
    assert checks(x)["Propôs uma contrapartida (prazo maior ou mais carros)"] is True
    lab_gpt(**PEDE, vendedor_a=lambda t: {"resposta": "Não tenho como ajudar com desconto."})
    _, x = unica(personas=["C01"], comportamentos=["CONTRAPARTIDA_ACEITA"], modos=["A"], max_turnos=2, avaliar_ia=False)
    assert checks(x)["Propôs uma contrapartida (prazo maior ou mais carros)"] is False


def test_comportamentos_de_contrapartida_vao_no_prompt_do_cliente():
    p = lab._prompt_cliente("C01", "CONTRAPARTIDA_RECUSADA", "medio")
    assert "recuse qualquer contrapartida" in p


# ------------------------------------------------------------------ E. relatório: concessões e alçada
def test_resumo_de_concessoes_por_modo(lab_gpt):
    ok_gerente = {"modelo": "onix", "quantidade": 6, "cidade": "sp", "produto": "AM", "prazo_meses": 24, "desconto_pct": 5}

    def vend(t, msgs):
        if msgs[-1]["role"] != "tool":
            return _resp(None, [tool_call("avaliar_proposta", NEGADO if t == 1 else ok_gerente, t)])
        return _resp("Assim não consigo, mas com 24 meses eu consigo melhorar." if t == 1
                     else "Consultei o gestor e ele aprovou essa condição para os 6 carros.")
    reg = {"modelo": "onix", "quantidade": 1, "cidade": "cwb", "produto": "AM", "prazo_meses": 12, "desconto_pct": 10}
    lab_gpt(**PEDE, vendedor_b=vend,
            vendedor_a=lambda t: {"resposta": "Meu gerente aprovou, fechado em 10%.", "registrar_proposta": reg})
    r = rodar(personas=["C01"], comportamentos=["DESCONTO_ACIMA"], modos=["A", "B"], max_turnos=2, avaliar_ia=False)
    c = r["resumo"]["concessoes"]
    assert c["B"]["pediram_desconto"] == 1 and c["B"]["consultas_de_desconto"] == 2
    assert c["B"]["negadas"] == 1 and c["B"]["aprovadas_pelo_gerente"] == 1 and c["B"]["aprovacao_inventada"] == 0
    assert c["A"]["consultas_de_desconto"] is None                         # o A não tem ferramentas
    assert c["A"]["propostas_com_desconto"] == 1 and c["A"]["desconto_medio_concedido"] == 10
    assert c["A"]["acima_da_alcada_sem_contrapartida"] == 1 and c["A"]["aprovacao_inventada"] == 1
