from services import pricing_service as p


def test_exemplo_do_plano_c001():
    r = p.simular_preco("C001", "MENSAL", 5, 6)
    assert r["preco_unitario"] == 2850.00
    assert r["preco_total_mensal"] == 14250.00
    assert r["desconto_maximo"] == 0.03
    assert r["preco_minimo_unitario"] == 2764.50
    assert r["validade_dias"] == 5


def test_quantidade_e_prazo_fora_da_regra():
    assert p.simular_preco("C001", "MENSAL", 50, 6)["erro"] == "QUANTIDADE_FORA_DA_REGRA"
    assert p.simular_preco("C001", "MENSAL", 5, 1)["erro"] == "PRAZO_FORA_DA_REGRA"


def test_produto_nao_permitido():
    assert p.simular_preco("C001", "UTILITARIO_MENSAL", 1, 6)["erro"] == "PRODUTO_NAO_PERMITIDO"


def test_praca_altera_preco():
    base = p.simular_preco("C009", "MENSAL", 4, 12, "CURITIBA")["preco_unitario"]
    sp = p.simular_preco("C009", "MENSAL", 4, 12, "SAO PAULO")["preco_unitario"]
    assert sp > base


def test_diaria_total_usa_dias():
    r = p.simular_preco("C008", "DIARIA", 3, 5)
    assert r["preco_total"] == round(189.0 * 3 * 5, 2) and r["preco_total_mensal"] is None


def test_aplicar_desconto():
    c = p.simular_preco("C001", "MENSAL", 5, 6)
    assert p.aplicar_desconto(c, 0.03) == {"desconto": 0.03, "preco_unitario": 2764.50, "preco_total": 13822.50}
