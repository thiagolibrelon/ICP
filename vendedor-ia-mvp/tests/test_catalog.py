import pytest

from services import catalog as c
from services.catalog import ErroFerramenta


def test_preco_volume_e_prazo():
    r = c.calcular("onix", 1, "sp", "AM", 12)
    assert r["preco_unitario_final"] == 2690.0 and r["total_mensal"] == 2690.0
    assert c.calcular("onix", 1, "sp", "AM", 36)["preco_unitario_final"] == 2420.0          # prazo maior = mais barato
    assert c.calcular("onix", 5, "sp", "AM", 12)["desconto_volume_pct"] == 2.0              # volume automático
    assert c.calcular("onix", 10, "sp", "AM", 12)["preco_unitario_final"] == round(2690 * 0.96, 2)
    assert c.calcular("creta", 3, "bh", "AD", dias=5)["total"] == round(239 * 3 * 5, 2)


@pytest.mark.parametrize("args,erro", [
    (("onix", 1, "sp", "AM", 3), "12, 24 ou 36"),
    (("onix", 1, "joinville", "AM", 12), "Cidade sem atendimento"),
    (("fusca", 1, "sp", "AM", 12), "não está no catálogo"),
    (("onix", 1, "sp", "AD"), "informe 'dias'"),
])
def test_entradas_invalidas_viram_erro_explicativo(args, erro):
    with pytest.raises(ErroFerramenta, match=erro):
        c.calcular(*args)


def test_alcada_em_dois_niveis_e_gerente_exige_contrapartida():
    assert c.avaliar_proposta("onix", 1, "sp", "AM", 12, None, 3)["status"] == "APROVADO"             # IA sozinha
    neg = c.avaliar_proposta("onix", 1, "sp", "AM", 12, None, 5)
    assert neg["status"] == "NEGADO_GERENTE" and neg["contraproposta_desconto_pct"] == 3.0            # sem contrapartida
    assert c.avaliar_proposta("onix", 1, "sp", "AM", 24, None, 5)["status"] == "APROVADO_GERENTE"     # prazo 24m
    assert c.avaliar_proposta("onix", 5, "sp", "AM", 12, None, 5)["aprovado_por"] == "gerente_simulado"  # volume
    acima = c.avaliar_proposta("onix", 5, "sp", "AM", 24, None, 15)
    assert acima["status"] == "ACIMA_DO_LIMITE" and acima["contraproposta_desconto_pct"] == 6.0


def test_margem_nunca_sai_das_ferramentas():
    saidas = [c.consultar_catalogo("sp"), c.consultar_cliente("C07"), c.avaliar_proposta("creta", 1, "sp", "AM", 12, None, 1),
              c.comparar_diaria_mensal("onix", 10), c.comparar_eletrico(2000, "creta")]
    texto = str(saidas).lower()
    assert "margem" not in texto and "margem_ia" not in texto and "margem_gerente" not in texto


def test_challenger_honesto_diaria_x_mensal():
    alpha = c.comparar_diaria_mensal("onix", 22, 3)       # Alpha Obras: 22 dias -> mensal
    epsilon = c.comparar_diaria_mensal("onix", 6, 2)      # Épsilon: 6 dias -> diária
    assert alpha["mais_barato"] == "MENSAL" and alpha["diferenca_por_mes"] == round(159 * 22 * 3 - 2690 * 3, 2)
    assert epsilon["mais_barato"] == "DIARIA" and "não recomende o mensal" in epsilon["leitura"]


def test_challenger_honesto_eletrico():
    teta = c.comparar_eletrico(3000, "onix")      # 3.000 km: não compensa
    delta = c.comparar_eletrico(4500, "onix")     # 4.500 km: compensa
    assert teta["compensa"] is False and teta["km_de_equilibrio"] == 3721
    assert delta["compensa"] is True and delta["economia_mensal_por_veiculo_com_dolphin"] > 0
    assert c.comparar_eletrico(1000, "creta")["compensa"] is True


def test_estoque_compartilhado_reserva_e_reinicia():
    assert c.avaliar_proposta("creta", 4, "bh", "AM", 12)["estoque_suficiente"] is False
    with pytest.raises(ErroFerramenta, match="aceita_prazo_entrega"):
        c.registrar_proposta("CV1", "C03", "B", "creta", 4, "bh", "AM", 12)
    p = c.registrar_proposta("CV1", "C03", "B", "creta", 4, "bh", "AM", 12, aceita_prazo_entrega=True)
    assert p["unidades_reservadas"] == 1 and p["entrega_futura_unidades"] == 3
    assert c.avaliar_proposta("creta", 1, "bh", "AM", 12)["estoque_disponivel"] == 0   # a próxima conversa já vê
    c.reiniciar_estoque()
    assert c.avaliar_proposta("creta", 1, "bh", "AM", 12)["estoque_disponivel"] == 1


def test_registrar_so_o_que_foi_aprovado():
    with pytest.raises(ErroFerramenta, match="não aprovada"):
        c.registrar_proposta("CV1", "C07", "B", "onix", 6, "sp", "AM", 12, desconto_pct=9)


def test_cliente_cadastrado_e_grupo():
    assert c.identificar_cliente("11.111.001/0001-51")["razao_social"] == "Alpha Obras"
    with pytest.raises(ErroFerramenta, match="só atende clientes cadastrados"):
        c.identificar_cliente("99.999.999/0001-99")
    mu = c.consultar_cliente("C12")
    assert mu["outros_cnpjs_do_grupo"][0]["cliente_id"] == "C12B"
