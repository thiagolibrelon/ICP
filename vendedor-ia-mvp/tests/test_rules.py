import pytest

from services import rules_service as r

ALCADAS = {"C001": 0.03, "C002": 0.0, "C003": 0.02, "C004": 0.0, "C005": 0.0, "C006": 0.0, "C007": 0.02, "C008": 0.0,
           "C009": 0.01, "C010": 0.01}


def test_exemplo_do_plano():
    assert r.avaliar_desconto("C001", "OF001", 0.05) == {
        "aprovado": False, "desconto_maximo": 0.03, "desconto_concedido": 0.03, "exige_handoff": True,
        "motivo": "SOLICITACAO_ACIMA_DA_ALCADA", "regra_id": "REG_CON_001"}


@pytest.mark.parametrize("cid,maximo", ALCADAS.items())
def test_alcada_por_cliente(cid, maximo):
    of = f"OF{int(cid[1:]):03d}"
    assert r.avaliar_desconto(cid, of, maximo)["aprovado"] is True
    assert r.avaliar_desconto(cid, of, maximo + 0.005)["aprovado"] is False


def test_oferta_inexistente():
    assert r.avaliar_desconto("C001", "OF999", 0.01)["motivo"] == "OFERTA_INEXISTENTE"
