"""Modo treino: o GPT faz o cliente e o coach; o avaliador aplica a régua C12; partes da nota vêm do sistema."""
import json

import pytest
from fastapi.testclient import TestClient

import app as A
from database.personas import PERSONAS
from services import training as tr


def cliente(msg, estado="NEGOCIANDO", revelou=(), objecao=None):
    return json.dumps({"mensagem": msg, "estado": estado, "revelou": list(revelou), "objecao": objecao})


AVALIACAO = {
    "dimensoes": {
        "diagnostico": {"nota": 8, "justificativa": "Perguntou a frequência.", "ancora": "quantos dias por mês vocês usam os carros",
                        "como_melhorar": "Pergunte quem decide.", "exemplo": "E quem aprova do lado de vocês?"},
        "challenger": {"nota": 9, "justificativa": "Mostrou a conta.", "ancora": "22 dias de diária saem mais caro que o mensal",
                       "como_melhorar": "", "exemplo": "", "trouxe_dado_concreto": "NAO", "conectou_a_situacao_do_cliente": "SIM",
                       "cliente_reagiu": "SIM", "codigos": ["CH2"]},
        "objecoes": {"nota": 6, "justificativa": "Respondeu o prazo.", "ancora": "", "como_melhorar": "Explore o medo.", "exemplo": "",
                     "respostas": [{"objecao": "OB2", "resposta": "R1", "eficacia": "media"}]},
        "qualificacao": {"nota": 2, "justificativa": "Não perguntou quem decide.", "ancora": "", "como_melhorar": "Pergunte.", "exemplo": ""},
        "adicionais": {"nota": 0, "justificativa": "Não ofereceu proteção.", "ancora": "", "como_melhorar": "", "exemplo": ""},
        "fechamento": {"nota": 7, "justificativa": "Definiu retorno.", "ancora": "frase que o vendedor nunca disse de verdade aqui",
                       "como_melhorar": "", "exemplo": "", "tipo": "FC2", "proximo_passo_claro": "SIM", "prazo_definido": "NAO"},
        "tom": {"nota": 9, "justificativa": "Cordial.", "ancora": "", "como_melhorar": "", "exemplo": ""}},
    "pontos_fortes": ["Diagnóstico"], "pontos_a_melhorar": ["Qualificação"], "resumo": "Bom começo."}


def test_iniciar_cliente_abre_a_conversa():
    t = tr.iniciar("Ana", "C01", "TREINO", "medio")
    assert t["mensagens"][0]["role"] == "cliente" and t["mensagens"][0]["conteudo"] == PERSONAS["C01"]["abertura"]
    assert t["progresso"] == {"segredos_descobertos": 0, "segredos_total": 3, "estado_cliente": "NEGOCIANDO"}


@pytest.mark.parametrize("args", [("", "C01", "TREINO", "medio"), ("Ana", "C01", "X", "medio"), ("Ana", "C01", "PROVA", "impossivel")])
def test_parametros_invalidos(args):
    with pytest.raises(ValueError):
        tr.iniciar(*args)


def test_cliente_revela_segredo_e_coach_so_no_modo_treino(gpt):
    g = gpt(cliente("Uns 22 dias por mês, direto.", revelou=["uso", "inventado"]),
            json.dumps({"dica": "Agora pergunte quem decide.", "foco": "qualificacao"}))
    t = tr.mensagem(tr.iniciar("Ana", "C01", "TREINO")["treino_id"], "Quantos dias por mês vocês usam os carros?")
    assert t["progresso"]["segredos_descobertos"] == 1                       # id inventado pelo modelo é ignorado
    assert [m["role"] for m in t["mensagens"]] == ["cliente", "vendedor", "cliente", "coach"]
    persona = g.recebidos[0]["messages"][0]["content"]
    assert "Rogério" in persona and "revela_se" in persona and g.recebidos[0]["json_mode"]
    assert g.recebidos[0]["messages"][-1] == {"role": "user", "content": "Quantos dias por mês vocês usam os carros?"}


def test_modo_prova_nao_tem_coach(gpt):
    gpt(cliente("Uns 22 dias."))
    t = tr.mensagem(tr.iniciar("Ana", "C01", "PROVA")["treino_id"], "Quantos dias?")
    assert "coach" not in [m["role"] for m in t["mensagens"]]


def test_calculadora_e_proposta_nao_mexem_no_estoque_real():
    from services import catalog
    antes = catalog.avaliar_proposta("onix", 1, "cwb", "AM", 12)["estoque_disponivel"]
    tid = tr.iniciar("Ana", "C01")["treino_id"]
    assert tr.avaliar_condicao(tid, {"modelo": "onix", "quantidade": 3, "cidade": "cwb", "produto": "AM", "prazo_meses": 12,
                                     "desconto_pct": 5})["status"] == "NEGADO_GERENTE"
    assert "erro" in tr.registrar(tid, {"modelo": "onix", "quantidade": 3, "cidade": "cwb", "produto": "AM", "prazo_meses": 12,
                                        "desconto_pct": 5})
    p = tr.registrar(tid, {"modelo": "onix", "quantidade": 3, "cidade": "cwb", "produto": "AM", "prazo_meses": 12, "desconto_pct": 2})
    assert p["proposta_id"].startswith("TP-") and p["tem_contrapartida"] is False
    assert catalog.avaliar_proposta("onix", 1, "cwb", "AM", 12)["estoque_disponivel"] == antes


def test_nota_final_com_regras_do_sistema(gpt):
    gpt(cliente("Uns 22 dias por mês.", revelou=["uso"]), json.dumps({"dica": "ok"}),
        cliente("Hum, e o preço?"), json.dumps({"dica": "ok"}),
        json.dumps(AVALIACAO))
    tid = tr.iniciar("Ana", "C01", "TREINO")["treino_id"]
    tr.mensagem(tid, "Quantos dias por mês vocês usam os carros? Pergunto pra ver o melhor plano.")
    tr.registrar(tid, {"modelo": "onix", "quantidade": 3, "cidade": "cwb", "produto": "AM", "prazo_meses": 12, "desconto_pct": 2})
    tr.mensagem(tid, "Olha, 22 dias de diária saem mais caro que o mensal. O máximo que consigo é 6% de desconto, fica R$ 1.234,00.")
    r = tr.encerrar(tid)["resultado"]
    d = r["dimensoes"]
    # diagnóstico: metade avaliador (8), metade sistema (1 de 3 segredos = 3,3)
    assert d["diagnostico"]["nota"] == round((8 + 3.3) / 2, 1) and d["diagnostico"]["ancora_verificada"] is True
    # challenger sem dado concreto: limitado a 4 (regra do time)
    assert d["challenger"]["nota"] == 4.0 and d["challenger"]["qualidade_c12"] == "nenhum"
    # disciplina de margem: desconto sem contrapartida (-4), limite revelado (-3), valor inventado (-1,5)
    assert d["disciplina_margem"]["nota"] == 1.5 and len(d["disciplina_margem"]["achados"]) == 3
    assert d["fechamento"]["ancora_verificada"] is False                      # âncora que o vendedor não disse
    assert "adicionais" in d                                                   # Alpha tem janela de proteção
    assert r["descobertas"]["o_que_faltou_descobrir"] and 0 < r["nota_geral"] < 10
    assert r["pontos_a_melhorar"] == ["Qualificação"]
    with pytest.raises(ValueError):
        tr.mensagem(tid, "mais uma")                                          # encerrado não aceita mensagem


def test_persona_sem_janela_nao_avalia_adicionais(gpt):
    gpt(cliente("6 dias."), json.dumps(AVALIACAO))
    tid = tr.iniciar("Ana", "C05", "PROVA")["treino_id"]
    tr.mensagem(tid, "Quantos dias por mês vocês usam?")
    assert "adicionais" not in tr.encerrar(tid)["resultado"]["dimensoes"]


def test_sem_gpt_mostra_so_a_parte_do_sistema():
    tid = tr.iniciar("Ana", "C01")["treino_id"]
    tr.mensagem(tid, "Oi Rogério, quantos dias vocês usam?")                  # mock: cliente não responde
    r = tr.encerrar(tid)["resultado"]
    assert r["aviso"] and set(r["dimensoes"]) == {"diagnostico", "disciplina_margem"}


def test_historico_em_ordem_alfabetica_sem_ranking(gpt):
    for nome in ("Zeca", "Ana"):
        gpt(cliente("Uns 22 dias.", revelou=["uso"]), json.dumps(AVALIACAO))
        tid = tr.iniciar(nome, "C01", "PROVA")["treino_id"]
        tr.mensagem(tid, "Quantos dias por mês vocês usam os carros?")
        tr.encerrar(tid)
    h = tr.historico()
    assert [v["vendedor"] for v in h["vendedores"]] == ["Ana", "Zeca"] and h["vendedores"][0]["ponto_mais_fraco"]
    assert len(tr.historico("Ana")["treinos"]) == 1


def test_api_treino():
    with TestClient(A.app) as c:
        assert len(c.get("/api/treino/personas").json()) == 12
        t = c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C04", "modo": "PROVA", "dificuldade": "dificil"}).json()
        r = c.post(f"/api/treino/{t['treino_id']}/avaliar-condicao", json={"modelo": "dolphin", "quantidade": 2, "cidade": "curitiba",
                                                                           "produto": "AM", "prazo_meses": 24, "pacotes_km_extra": 3})
        assert r.json()["adicionais_total_mensal"] == 3 * 180 * 2
        assert c.post(f"/api/treino/{t['treino_id']}/encerrar").json()["status"] == "AVALIADO"
        assert c.get("/treino").status_code == 200
        assert c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C01", "modo": "X"}).status_code == 422
