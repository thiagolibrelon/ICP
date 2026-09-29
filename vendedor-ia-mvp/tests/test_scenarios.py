import pytest

from services import conversation_service as cs
from services import evaluation_service, validator

ROTEIROS = {
    "C001_EXPANSAO": (["Preciso de mais dois carros por 6 meses em Curitiba", "Achei o preço alto, quero 5% de desconto",
                       "Fechado, pode enviar a proposta"], "PROPOSTA_SIMULADA"),
    "C002_MIGRACAO": (["Quero migrar de diárias para mensal, 2 carros por 12 meses em São Paulo", "Não quero me comprometer com prazo longo",
                       "Quero 3% de desconto", "fechado, pode enviar a proposta"], "PROPOSTA_SIMULADA"),
    "C003_RETENCAO": (["Preciso de 4 carros por 12 meses em Campinas", "O concorrente está mais barato, quero 5% de desconto",
                       "Quero 5% mesmo"], "HANDOFF"),
    "C004_RENOVACAO": (["Quero renovar 6 carros por 12 meses em Belo Horizonte", "E se eu quiser cancelar antes, tem multa?",
                        "Quero 5% de desconto", "fechado, pode registrar"], "PROPOSTA_SIMULADA"),
    "C005_PILOTO": (["Quero testar 1 carro por 3 meses", "Não sei se vou ter demanda suficiente", "fechado, pode enviar a proposta"],
                    "PROPOSTA_SIMULADA"),
    "C006_CROSSSELL": (["Preciso de 2 utilitários por 6 meses em Curitiba", "Vocês garantem que tem utilitário disponível?",
                        "fechado, pode enviar a proposta"], "PROPOSTA_SIMULADA"),
    "C007_REATIVACAO": (["Tive uma experiência péssima da última vez e ninguém resolveu"], "HANDOFF"),
    "C008_SAZONAL": (["Preciso de 3 carros por 5 dias em São Paulo, é urgente", "Dá para fechar com crédito aprovado?",
                      "fechado, pode enviar a proposta"], "PROPOSTA_SIMULADA"),
    "C009_REGIONAL": (["Preciso de 4 carros por 12 meses em Curitiba", "Quero também o preço em São Paulo", "E em Belo Horizonte?",
                       "fechado, pode enviar a proposta"], "PROPOSTA_SIMULADA"),
    "C010_CHURN": (["Preciso renovar 3 carros por 12 meses em Porto Alegre", "Recebi uma proposta melhor de outra locadora, quero 3% de desconto",
                    "Quero 3% mesmo"], "HANDOFF"),
    "S011_SUPORTE": (["Não consigo acessar o portal, esqueci minha senha"], "ENCAMINHADO_SUPORTE"),
}


def rodar(cenario, falas):
    c = cs.iniciar_conversa(cenario_id=cenario)
    for f in falas:
        c = cs.processar_mensagem(c["conversation_id"], f)
    return c


def test_cenarios_cobrem_10_mais_suporte():
    assert len(cs.listar_cenarios()) == 11


@pytest.mark.parametrize("cenario", ROTEIROS)
def test_roteiro_do_cenario(cenario):
    falas, esperado = ROTEIROS[cenario]
    c = rodar(cenario, falas)
    assert c["desfecho"] == esperado
    for m in c["mensagens"]:
        if m["role"] == "vendedor":
            assert m["validacao"] == "OK"
            assert validator.validar(m["conteudo"], m["auditoria"]["fatos"]) == []
    av = evaluation_service.avaliar(c["conversation_id"])
    assert av["informacao_inventada"] is False and av["desconto_fora_alcada"] is False
    assert av["handoff_correto"] is True and av["desfecho_ok"] is True


def test_c001_desconto_limitado_a_alcada():
    c = rodar("C001_EXPANSAO", ROTEIROS["C001_EXPANSAO"][0])
    assert c["desconto_final"] == 0.03 and c["fora_da_alcada"] == 0
    prop = c["estado"]["proposta"]
    assert prop["preco_unitario"] == 2764.50


def test_c002_e_c004_sem_desconto():
    for cen in ("C002_MIGRACAO", "C004_RENOVACAO"):
        c = rodar(cen, ROTEIROS[cen][0])
        assert c["desconto_final"] == 0.0
        assert c["estado"]["proposta"]["preco_unitario"] == c["estado"]["cotacao"]["preco_unitario"]


def test_c004_nao_cita_valor_de_multa():
    c = rodar("C004_RENOVACAO", ROTEIROS["C004_RENOVACAO"][0][:2])
    resp = c["mensagens"][-1]["conteudo"]
    assert "R$" not in resp and "%" not in resp


def test_c006_nunca_promete_disponibilidade():
    c = rodar("C006_CROSSSELL", ROTEIROS["C006_CROSSSELL"][0])
    resp = [m for m in c["mensagens"] if m["acao_sugerida"] == "INFORMAR_DISPONIBILIDADE"][0]["conteudo"]
    assert "Não consigo confirmar disponibilidade" in resp


def test_c008_nao_simula_credito():
    c = rodar("C008_SAZONAL", ROTEIROS["C008_SAZONAL"][0][:2])
    assert c["mensagens"][-1]["acao_sugerida"] == "INFORMAR_SEM_CREDITO"


def test_c009_permite_duas_cotacoes_e_bloqueia_a_terceira():
    c = rodar("C009_REGIONAL", ROTEIROS["C009_REGIONAL"][0][:3])
    acoes = [m["acao_sugerida"] for m in c["mensagens"] if m["role"] == "vendedor"]
    assert acoes[1:] == ["APRESENTAR_COTACAO", "APRESENTAR_COTACAO", "LIMITE_COTACOES"]
    assert len(c["estado"]["pracas_cotadas"]) == 2


def test_c010_primeiro_contrapropoe_depois_humano():
    c = rodar("C010_CHURN", ROTEIROS["C010_CHURN"][0][:2])
    assert c["mensagens"][-1]["acao_sugerida"] == "CONTRAPROPOR_DESCONTO" and not c["handoff"]


def test_suporte_nao_forca_venda():
    c = rodar("S011_SUPORTE", ROTEIROS["S011_SUPORTE"][0])
    assert c["estado"]["cotacao"] is None and c["proposta_gerada"] == 0
    assert "R$" not in c["mensagens"][-1]["conteudo"]


def test_diagnostico_antes_do_preco():
    c = cs.iniciar_conversa(cenario_id="C001_EXPANSAO")
    c = cs.processar_mensagem(c["conversation_id"], "Qual o preço?")
    assert c["mensagens"][-1]["acao_sugerida"] == "DIAGNOSTICAR" and "R$" not in c["mensagens"][-1]["conteudo"]


def test_pedido_de_humano_faz_handoff():
    c = cs.iniciar_conversa(cenario_id="C002_MIGRACAO")
    c = cs.processar_mensagem(c["conversation_id"], "Quero falar com um atendente humano")
    assert c["handoff"] == 1 and c["desfecho"] == "HANDOFF"


def test_quantidade_fora_da_regra_nao_inventa_preco():
    c = cs.iniciar_conversa(cenario_id="C001_EXPANSAO")
    c = cs.processar_mensagem(c["conversation_id"], "Preciso de 30 carros por 6 meses")
    assert c["mensagens"][-1]["acao_sugerida"] == "FORA_DA_REGRA" and "R$" not in c["mensagens"][-1]["conteudo"]


def test_reiniciar_e_exportar_e_metricas():
    c = rodar("C001_EXPANSAO", ROTEIROS["C001_EXPANSAO"][0])
    evaluation_service.avaliar(c["conversation_id"])
    assert evaluation_service.metricas()["conversas_avaliadas"] == 1
    r = cs.reiniciar(c["conversation_id"])
    assert len(r["mensagens"]) == 1 and r["desfecho"] == "EM_ANDAMENTO" and r["proposta_gerada"] == 0


def test_conversa_encerrada_nao_aceita_mensagem():
    c = cs.iniciar_conversa(cenario_id="C001_EXPANSAO")
    c = cs.processar_mensagem(c["conversation_id"], "obrigado, tchau")
    assert c["status"] == "ENCERRADA"
    with pytest.raises(ValueError):
        cs.processar_mensagem(c["conversation_id"], "oi")


def test_inicio_por_cnpj_ficticio():
    c = cs.iniciar_conversa(identificador="00.000.003/0001-13")
    assert c["cliente_id"] == "C003"
