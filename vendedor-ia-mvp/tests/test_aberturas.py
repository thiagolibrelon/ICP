"""Aberturas da Fernanda: 1 (atual) × 2 (SPIN, cadastro como hipótese). Só a regra 1 das instruções muda."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import app as A
from database import db
from services import agent, conversations as cs, laboratorio as lab
from tests.test_laboratorio import _resp, lab_gpt, rodar  # noqa: F401 (fixture)


# ------------------------------------------------------------------ instruções
def test_abertura_1_e_a_atual_e_a_2_so_troca_a_regra_1():
    a1, a2 = agent.instrucoes_base("1"), agent.instrucoes_base("2")
    assert a1 == agent.BASE and "vi aqui que vocês rodam com 3 Onix" in a1
    assert "HIPÓTESE" in a2 and "vi aqui que vocês rodam com 3 Onix" not in a2 and "PROBLEMA" in a2 and "IMPLICAÇÃO" in a2
    # tudo a partir da regra 2 é idêntico: a comparação mede só a abertura
    assert a1[a1.index("\n2. "):] == a2[a2.index("\n2. "):]
    assert a1[:a1.index("1. Diagnostique")] == a2[:a2.index("1. Diagnostique")]


def test_abertura_padrao_vem_do_ambiente(monkeypatch):
    assert agent.abertura_padrao() == "1"
    monkeypatch.setenv("FERNANDA_ABERTURA", "2")
    assert agent.abertura_padrao() == "2" and "HIPÓTESE" in agent.instrucoes_base(None)
    monkeypatch.setenv("FERNANDA_ABERTURA", "9")
    assert agent.abertura_padrao() == "1"


# ------------------------------------------------------------------ conversa
@pytest.mark.parametrize("modo", ["A", "B"])
def test_conversa_guarda_a_abertura_e_manda_as_instrucoes_certas(gpt, modo):
    g = gpt('{"resposta": "Oi, Rogério! Aqui é a Fernanda 🙂", "registrar_proposta": null, "handoff": null}' if modo == "A"
            else "Oi, Rogério! Aqui é a Fernanda 🙂 Hoje vocês seguem com os 3 Onix na diária, né?")
    cid = cs.iniciar("C01", modo, False, None, "2")["conversation_id"]
    c = cs.processar(cid, "Oi, tô gastando muito com os carros")
    assert c["abertura"] == "2" and "HIPÓTESE" in g.recebidos[0]["messages"][0]["content"]
    assert cs.reiniciar(cid)["abertura"] == "2"                                   # reiniciar não perde a abertura


def test_sem_abertura_usa_a_padrao_e_invalida_e_recusada():
    assert cs.iniciar("C01", "B")["abertura"] == "1"
    with pytest.raises(ValueError):
        cs.iniciar("C01", "B", False, None, "3")


def test_api_aceita_abertura():
    with TestClient(A.app) as c:
        assert c.post("/api/conversations", json={"cliente_id": "C01", "abertura": "2"}).json()["abertura"] == "2"
        assert c.post("/api/conversations", json={"cliente_id": "C01", "abertura": "3"}).status_code == 422
        assert 'id="abertura"' in c.get("/").text


# ------------------------------------------------------------------ Laboratório
def test_tipo_de_rodada_teste_de_abertura():
    itens = lab.PRESETS["teste_abertura"][1]()
    assert len(itens) == 120 and {i["modo"] for i in itens} == {"B"}
    assert sum(i["abertura"] == "1" for i in itens) == sum(i["abertura"] == "2" for i in itens) == 60
    assert not {"C10", "C12"} & {i["cliente_id"] for i in itens}
    assert {i["comportamento"] for i in itens} == {"COLABORATIVO", "RESISTENTE"}
    assert lab.catalogo()["abertura_padrao"] == "1" and len(lab.catalogo()["aberturas"]) == 2


def test_rodada_personalizada_com_duas_aberturas_e_comparativo(lab_gpt):
    g = lab_gpt(cliente=lambda t: (f"Mensagem {t}: usamos uns 22 dias por mês", "NEGOCIANDO"))
    vistos = []
    real = g.__call__

    def espiao(messages, **kw):
        if not messages[0]["content"].startswith(("Você vai INTERPRETAR", "Você é o AVALIADOR")):
            vistos.append("HIPÓTESE" in messages[0]["content"])
        return real(messages, **kw)
    import services.llm_client as llm
    llm.completar = espiao
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], aberturas=["1", "2"], max_turnos=2)
    assert [x["abertura"] for x in r["execucoes"]] == ["1", "2"]
    assert vistos.count(True) == vistos.count(False) == 2                          # cada conversa com as suas instruções
    for x in r["execucoes"]:
        assert cs.obter(x["conversation_id"])["abertura"] == x["abertura"]
    ab = r["resumo"]["aberturas"]
    assert set(ab) == {"1", "2"} and ab["1"]["n"] == ab["2"]["n"] == 1
    assert ab["1"]["nota_media"] is not None and ab["1"]["dimensoes"]["diagnostico"] is not None
    assert "abertura" in lab.exportar_csv(r["rodada_id"]).decode("utf-8-sig").splitlines()[0]


def test_rodada_com_uma_abertura_nao_tem_comparativo(lab_gpt):
    lab_gpt()
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], max_turnos=2, avaliar_ia=False)
    assert r["resumo"]["aberturas"] is None and r["execucoes"][0]["abertura"] == "1"


def test_informacoes_descobertas_sao_registradas(lab_gpt):
    def cli(t):
        return (f"Usamos uns 22 dias por mês ({t})", "NEGOCIANDO")
    g = lab_gpt(cliente=cli)
    orig = g.__call__

    def com_segredo(messages, **kw):
        out = orig(messages, **kw)
        if messages[0]["content"].startswith("Você vai INTERPRETAR"):
            j = json.loads(out["message"]["content"])
            j["revelou"] = ["uso", "inventado"]
            out["message"]["content"] = json.dumps(j)
        return out
    import services.llm_client as llm
    llm.completar = com_segredo
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], aberturas=["1", "2"], max_turnos=2, avaliar_ia=False)
    assert all(x["revelados"] == 1 for x in r["execucoes"])                       # id inventado não conta
    assert r["resumo"]["aberturas"]["1"]["descobertas_pct"] == round(100 / 3, 1)


def test_banco_antigo_ganha_as_colunas_novas(tmp_path):
    p = tmp_path / "antigo.db"
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE lab_execucoes (exec_id TEXT PRIMARY KEY, rodada_id TEXT, ordem INTEGER, cliente_id TEXT, "
                 "comportamento TEXT, modo TEXT, repeticao INTEGER, max_turnos INTEGER, status TEXT)")
    conn.execute("INSERT INTO lab_execucoes VALUES ('X-001','X',1,'C01','COLABORATIVO','B',1,12,'CONCLUIDA')")
    conn.commit()
    conn.close()
    atual = db.get_db_path()
    db.set_db_path(p)
    try:
        lab.garantir_tabelas()
        row = db.fetch_one("SELECT abertura, revelados FROM lab_execucoes WHERE exec_id='X-001'")
        assert row == {"abertura": "1", "revelados": None}                         # nada foi apagado
    finally:
        db.set_db_path(atual)
