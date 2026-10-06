"""Trilha de treinamento: competências (dos 15 prompts de análise), 30 clientes e nível por competência."""
import json

from fastapi.testclient import TestClient

import app as A
from database import seed
from database.personas import PERSONAS
from services import carteira, catalog, training as tr, trilha


def test_30_clientes_no_cadastro_e_no_treino():
    assert len(PERSONAS) == 30 and set(PERSONAS) == {r[0] for r in seed.CLIENTES} == {f"C{i:02d}" for i in range(1, 31)}
    assert set(seed.TIERS) >= set(PERSONAS)
    assert [c for c in PERSONAS if seed.TIERS[c] == "A"] == ["C10", "C12"]   # os novos são da carteira da venda interna
    assert catalog.consultar_cliente("C30")["razao_social"] == "Cassini Educação"
    assert catalog.consultar_cliente("C12B")["razao_social"] == "Mu Holding Filial BH"


def test_toda_persona_tem_competencia_valida_e_objecoes_do_classificador():
    for cid, p in PERSONAS.items():
        assert p["competencias"] and set(p["competencias"]) <= set(trilha.POR_ID), cid
        assert all(o["codigo"] in {f"OB{i}" for i in range(1, 8)} for o in p["objecoes"]), cid
        assert p["segredos"] and len({s["id"] for s in p["segredos"]}) == len(p["segredos"]), cid
        if p["janela_adicional"]:
            assert p["janela_adicional"]["codigo"] in {"PROTECAO_TOTAL", "TELEMETRIA", "KM_EXTRA_1000"}, cid


def test_toda_competencia_tem_cenario_e_os_15_prompts_estao_mapeados():
    m = trilha.mapa()
    assert all(c["cenarios"] for c in m["competencias"])
    assert [x["prompt"] for x in m["prompts"]] == [f"P{i}" for i in range(1, 16)]
    assert {x["prompt"] for x in m["prompts"] if x["competencia"] is None} == {"P13", "P14"}   # exploratórios: gestor


def test_novos_clientes_tem_motivo_de_contato_ativo_do_cadastro():
    assert carteira.motivos("C20")[0]["motivo"] == "RENOVACAO"            # vence em 10 dias
    assert carteira.motivos("C29")[0]["motivo"] == "DIARIA_ALTA"          # 25 dias de diária
    assert carteira.motivos("C16")[0]["motivo"] in ("FROTA_PROPRIA", "KM_ACIMA_FRANQUIA")
    assert carteira.motivos("C24")[0]["motivo"] == "RELACIONAMENTO"       # prospect sem locação


def _prova(gpt, nome, cid, dificuldade, nota, frente="receptiva"):
    av = {"dimensoes": {k: {"nota": nota, "justificativa": "x"} for k in
                        ("diagnostico", "challenger", "objecoes", "qualificacao", "fechamento", "tom", "adicionais")}}
    av["dimensoes"]["challenger"].update(trouxe_dado_concreto="SIM", conectou_a_situacao_do_cliente="SIM", cliente_reagiu="SIM")
    gpt(json.dumps({"mensagem": "ok", "estado": "NEGOCIANDO", "revelou": [s["id"] for s in PERSONAS[cid]["segredos"]]}), json.dumps(av))
    tid = tr.iniciar(nome, cid, "PROVA", dificuldade, frente)["treino_id"]
    tr.mensagem(tid, "Quantos dias por mês vocês usam e quem decide?")
    return tr.encerrar(tid)


def test_nivel_por_competencia_so_conta_prova(gpt):
    _prova(gpt, "Ana", "C17", "medio", 8)                              # C17: diagnóstico, challenger, objeções
    p = {c["id"]: c for c in trilha.progresso("Ana")["competencias"]}
    assert p["challenger"]["nivel"] == "prata" and p["challenger"]["proximo"]["nivel"] == "ouro"
    assert p["margem"]["nivel"] is None and p["margem"]["provas"] == 0
    # treino com coach não conta para nível
    gpt(json.dumps({"mensagem": "ok"}), json.dumps({"dica": "x"}), json.dumps({"dimensoes": {}}))
    tid = tr.iniciar("Ana", "C02", "TREINO", "dificil")["treino_id"]
    tr.mensagem(tid, "oi")
    tr.encerrar(tid)
    assert {c["id"]: c for c in trilha.progresso("Ana")["competencias"]}["margem"]["provas"] == 0


def test_ouro_exige_duas_provas_dificeis_e_uma_na_ativa(gpt):
    _prova(gpt, "Bia", "C27", "dificil", 9)
    _prova(gpt, "Bia", "C29", "dificil", 9)
    assert {c["id"]: c for c in trilha.progresso("Bia")["competencias"]}["challenger"]["nivel"] == "prata"
    _prova(gpt, "Bia", "C27", "dificil", 9, frente="ativa")
    p = trilha.progresso("Bia")
    assert {c["id"]: c for c in p["competencias"]}["challenger"]["nivel"] == "ouro"
    assert {c["id"]: c for c in p["competencias"]}["abertura"]["provas"] == 1   # a prova ativa conta para abertura
    assert p["por_nivel"]["ouro"] >= 1 and p["total"] == len(trilha.COMPETENCIAS)


def test_nota_baixa_nao_sobe_de_nivel(gpt):
    _prova(gpt, "Caio", "C21", "dificil", 5)
    assert {c["id"]: c for c in trilha.progresso("Caio")["competencias"]}["fechamento"]["nivel"] is None


def test_challenger_sem_dado_nao_conta_para_o_nivel(gpt):
    av = {"dimensoes": {k: {"nota": 9, "justificativa": "x"} for k in ("diagnostico", "challenger", "objecoes", "fechamento", "tom")}}
    gpt(json.dumps({"mensagem": "ok", "revelou": ["uso", "projeto"]}), json.dumps(av))     # sem trouxe_dado_concreto
    tid = tr.iniciar("Duda", "C17", "PROVA", "medio")["treino_id"]
    tr.mensagem(tid, "Quantos dias por mês vocês usam?")
    tr.encerrar(tid)
    p = {c["id"]: c for c in trilha.progresso("Duda")["competencias"]}
    assert p["challenger"]["nivel"] is None and p["diagnostico"]["nivel"] == "prata"   # regra do C12: limitado a 4


def test_api_trilha():
    with TestClient(A.app) as c:
        t = c.get("/api/treino/trilha").json()
        assert len(t["competencias"]) == 9 and "progresso" not in t
        assert c.get("/api/treino/trilha", params={"vendedor": "Ana"}).json()["progresso"]["provas"] == 0
        assert c.get("/api/treino/T-NAO-EXISTE").status_code == 404                  # rota da trilha não engole /{tid}
