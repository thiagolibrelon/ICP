"""Modo treino: o GPT faz o cliente e o coach; o avaliador aplica a régua C12; partes da nota vêm do sistema."""
import json

import pytest
from fastapi.testclient import TestClient

import app as A
from database.personas import PERSONAS
from services import llm_client, training as tr


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
        assert len(c.get("/api/treino/personas").json()) == 30
        t = c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C04", "modo": "PROVA", "dificuldade": "dificil"}).json()
        r = c.post(f"/api/treino/{t['treino_id']}/avaliar-condicao", json={"modelo": "dolphin", "quantidade": 2, "cidade": "curitiba",
                                                                           "produto": "AM", "prazo_meses": 24, "pacotes_km_extra": 3})
        assert r.json()["adicionais_total_mensal"] == 3 * 180 * 2
        assert c.post(f"/api/treino/{t['treino_id']}/encerrar").json()["status"] == "AVALIADO"
        assert c.get("/").status_code == 200
        assert c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C01", "modo": "X"}).status_code == 422


# ------------------------------------------------------------------ coach ligado/desligado (frente de líder coach)
def test_coach_desligado_no_inicio_nao_da_dica(gpt):
    gpt(cliente("Uns 22 dias."))
    t = tr.iniciar("Ana", "C01", "TREINO", coach=False)
    assert t["coach"] is False and t["modo"] == "TREINO"
    t = tr.mensagem(t["treino_id"], "Quantos dias?")
    assert "coach" not in [m["role"] for m in t["mensagens"]]


def test_coach_padrao_ligado_no_treino_e_desligado_na_prova():
    assert tr.iniciar("Ana", "C01", "TREINO")["coach"] is True
    assert tr.iniciar("Ana", "C01", "PROVA")["coach"] is False
    with pytest.raises(ValueError):
        tr.iniciar("Ana", "C01", "PROVA", coach=True)


def test_coach_trocado_no_meio_fica_registrado(gpt):
    gpt(cliente("Uns 22 dias.", revelou=["uso"]), json.dumps({"dica": "Pergunte quem decide."}),
        cliente("O Marcos."), json.dumps(AVALIACAO))
    tid = tr.iniciar("Ana", "C01", "TREINO")["treino_id"]
    tr.mensagem(tid, "Quantos dias por mês vocês usam os carros?")             # coach ligado: 1 dica
    assert tr.definir_coach(tid, False)["coach"] is False
    tr.definir_coach(tid, False)                                                # repetir não cria outra troca
    t = tr.mensagem(tid, "E quem decide aí?")                                   # coach desligado: sem dica
    assert [m["role"] for m in t["mensagens"]].count("coach") == 1
    r = tr.encerrar(tid)["resultado"]["coach"]
    assert r["situacao"] == "misto" and r["dicas"] == 1
    assert [(x["ligado"], x["depois_da_resposta"]) for x in r["trocas"]] == [(False, 1)]
    with pytest.raises(ValueError):
        tr.definir_coach(tid, True)                                             # encerrado


def test_prova_nao_liga_coach():
    tid = tr.iniciar("Ana", "C01", "PROVA")["treino_id"]
    with pytest.raises(ValueError):
        tr.definir_coach(tid, True)


def test_historico_separa_com_e_sem_coach(gpt):
    for coach in (True, False, False):
        gpt(cliente("Uns 22 dias."), *( [json.dumps({"dica": "ok"})] if coach else []), json.dumps(AVALIACAO))
        tid = tr.iniciar("Ana", "C01", "TREINO", coach=coach)["treino_id"]
        tr.mensagem(tid, "Quantos dias por mês vocês usam os carros?")
        tr.encerrar(tid)
    h = tr.historico()
    assert h["por_coach"]["ligado"]["treinos"] == 1 and h["por_coach"]["desligado"]["treinos"] == 2
    assert {t["coach"] for t in h["treinos"]} == {"ligado", "desligado"}
    assert set(h["vendedores"][0]["por_coach"]) == {"ligado", "desligado"}


def test_api_coach():
    with TestClient(A.app) as c:
        t = c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C01", "coach": False}).json()
        assert t["coach"] is False
        assert c.post(f"/api/treino/{t['treino_id']}/coach", json={"ligado": True}).json()["coach"] is True
        p = c.post("/api/treino", json={"vendedor": "Ana", "cliente_id": "C01", "modo": "PROVA"}).json()
        assert c.post(f"/api/treino/{p['treino_id']}/coach", json={"ligado": True}).status_code == 400


# ------------------------------------------------------------------ frente ativa e papel de cada chamada
def test_treino_ativo_vendedor_comeca_com_motivo(monkeypatch):
    vistos = []

    def fake(messages, **kw):
        vistos.append(" ".join(str(m.get("content")) for m in messages))
        if messages[0]["content"].startswith("Você vai INTERPRETAR"):
            return {"message": {"content": json.dumps({"mensagem": "Oi, quem fala?", "estado": "NEGOCIANDO", "revelou": [], "objecao": None})},
                    "tokens_entrada": 1, "tokens_saida": 1, "custo_gate": 0}
        return {"message": {"content": json.dumps({"dica": "Diga quem é e o motivo."})}, "tokens_entrada": 1, "tokens_saida": 1, "custo_gate": 0}
    monkeypatch.setattr(llm_client, "completar", fake)
    t = tr.iniciar("Ana", "C02", "TREINO", "medio", "ativa")
    assert t["mensagens"] == [] and t["frente"] == "ativa" and t["motivo"]["motivo"] == "RENOVACAO"
    t = tr.mensagem(t["treino_id"], "Oi, Sandra! Aqui é a Ana, da locadora. O contrato dos 5 Polo vence em 20 dias. Posso te ajudar na renovação?")
    assert [m["role"] for m in t["mensagens"]] == ["vendedor", "cliente", "coach"]
    assert "contato ativo" in vistos[0] and '"frente": "ativa"' in vistos[1] and "O vendedor iniciou o contato" in vistos[1]
    with pytest.raises(ValueError):
        tr.iniciar("Ana", "C02", "TREINO", "medio", "outra")


def test_treino_marca_o_papel_de_cada_chamada(monkeypatch):
    vistos = []

    def fake(messages, **kw):
        vistos.append(llm_client.papel_atual())
        if messages[0]["content"].startswith("Você vai INTERPRETAR"):
            return {"message": {"content": cliente("Uns 22 dias.")}, "tokens_entrada": 1, "tokens_saida": 1, "custo_gate": 0}
        return {"message": {"content": json.dumps({"dica": "ok"})}, "tokens_entrada": 1, "tokens_saida": 1, "custo_gate": 0}
    monkeypatch.setattr(llm_client, "completar", fake)
    tr.mensagem(tr.iniciar("Ana", "C01", "TREINO")["treino_id"], "Quantos dias?")
    assert vistos == ["cliente", "coach"]


# ------------------------------------------------------------------ nota completa: abertura, promessas, oportunidades, conta
COMPLETA = json.loads(json.dumps(AVALIACAO))
COMPLETA["dimensoes"].update({
    "abertura": {"nota": 8, "justificativa": "Contextualizou.", "ancora": "", "tipo": "AB1", "usou_nome": "SIM",
                 "sinalizou_conta": "NAO", "primeira_pergunta": "diagnostico"},
    "promessas": {"nota": 5, "justificativa": "Uma sem prazo.", "ancora": "",
                  "lista": [{"tipo": "PM2", "frase": "mandar a proposta", "prazo": "hoje", "risco": "medio"},
                            {"tipo": "PM5", "frase": "ver com o gerente", "prazo": "sem prazo", "risco": "alto"},
                            {"tipo": "PM9", "frase": "código inventado", "prazo": "", "risco": "alto"}]},
    "oportunidades": {"nota": 4, "justificativa": "Não ofereceu proteção.", "ancora": "",
                      "perdidas": [{"codigo": "OP6", "o_que_faltou": "proteção", "deveria_ter_dito": "x", "impacto": "alto"}, "lixo"]},
    "conta": {"nota": None, "justificativa": "Sem sinais.", "ancora": "", "sinais": []}})
COMPLETA["dimensoes"]["diagnostico"]["comportamentos"] = ["B1", "B3", "B99"]


def test_nota_completa_traz_os_codigos_dos_prompts(gpt):
    gpt(cliente("Uns 22 dias por mês.", revelou=["uso"]), json.dumps(COMPLETA))
    tid = tr.iniciar("Ana", "C01", "PROVA")["treino_id"]
    tr.mensagem(tid, "Oi Rogério! Quantos dias por mês vocês usam os carros? Pergunto pra ver o melhor plano.")
    r = tr.encerrar(tid)["resultado"]
    d = r["dimensoes"]
    assert d["abertura"]["tipo"] == "AB1" and d["abertura"]["primeira_pergunta"] == "diagnostico"
    assert d["diagnostico"]["comportamentos"] == ["B1", "B3"]                    # código inventado é descartado
    assert [x["tipo"] for x in d["promessas"]["lista"]] == ["PM2", "PM5"] and d["promessas"]["sem_prazo"] == 1
    assert [x["codigo"] for x in d["oportunidades"]["perdidas"]] == ["OP6"]
    assert "conta" not in d                                                      # sem sinal da conta: não entra na média
    assert r["pesos"]["oportunidades"] == 1.5 and "conta" not in r["pesos"]
    assert r["escuta"]["perguntas_do_vendedor"] == 1 and r["escuta"]["padrao"] in ("TL1", "TL2", "TL3")


def test_escuta_calculada_pelo_sistema():
    hist = [{"role": "cliente", "conteudo": "um dois três quatro cinco seis sete oito nove dez"},
            {"role": "vendedor", "conteudo": "um dois? três?"}]
    e = tr.escuta(hist)
    assert e == {"palavras_vendedor_pct": 23, "padrao": "TL3", "perguntas_do_vendedor": 2, "mensagens_do_vendedor": 1,
                 "palavras_por_mensagem": 3.0}
    assert tr.escuta([{"role": "cliente", "conteudo": "oi"}]) == {}


def test_contato_ativo_sem_pergunta_limita_a_abertura(gpt):
    gpt(cliente("Quem fala?"), json.dumps(COMPLETA))
    tid = tr.iniciar("Ana", "C02", "PROVA", frente="ativa")["treino_id"]
    tr.mensagem(tid, "Bom dia, temos condições especiais para você.")
    d = tr.encerrar(tid)["resultado"]["dimensoes"]
    assert d["abertura"]["nota"] == 4.0 and "Limitado a 4" in d["abertura"]["justificativa"]


def test_avaliador_pede_as_dimensoes_novas():
    for k in ("abertura", "promessas", "oportunidades", "conta", "AB1", "PM6", "OP8", "IC7", "EV_R5", "B10"):
        assert k in tr.P_AVALIADOR, k


# ------------------------------------------------------------------ separação e migração
def test_nao_importa_nada_do_projeto_da_fernanda():
    import re
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    for f in [*raiz.glob("*.py"), *raiz.glob("services/*.py"), *raiz.glob("database/*.py")]:
        texto = f.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import) services\.?\s*(import\s+)?.*\b(agent|ativa|laboratorio|conversations|evaluation)\b",
                             texto, re.M), f
        assert "sys.path" not in texto, f


def test_importa_treinos_do_banco_antigo(tmp_path, gpt):
    import sqlite3
    from scripts import importar_treinos_do_mvp as imp
    antigo = tmp_path / "mvp.db"
    conn = sqlite3.connect(antigo)
    conn.executescript((A.BASE / "database" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO treinos VALUES ('TR-VELHO', 'Ana', 'C01', 'PROVA', 'medio', '2026-10-01', NULL, 'AVALIADO', '{}', '{}', 7.5)")
    conn.execute("INSERT INTO treino_mensagens (treino_id, timestamp, role, conteudo, meta_json) VALUES ('TR-VELHO', 't', 'vendedor', 'oi', '{}')")
    conn.commit(); conn.close()
    assert imp.importar(antigo) == {"treinos": 1, "mensagens": 1, "pulados": 0}
    assert imp.importar(antigo) == {"treinos": 0, "mensagens": 0, "pulados": 1}          # rodar de novo não duplica
    assert [t["treino_id"] for t in tr.historico("Ana")["treinos"]] == ["TR-VELHO"]
