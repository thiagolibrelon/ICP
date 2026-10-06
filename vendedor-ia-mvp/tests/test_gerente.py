"""Pacote do gerente/diretor: handoff com briefing, concessões, roteamento por tier, qualificação, adicionais e áudio."""
import base64

import pytest
from fastapi.testclient import TestClient

import app as A
from services import agent, catalog, conversations as cs, evaluation, llm_client
from services.catalog import ErroFerramenta
from tests.conftest import tool_call


def ctx_de(cliente="C04"):
    c = cs.iniciar(cliente, "B")
    return {"conversation_id": c["conversation_id"], "cliente_id": cliente, "memoria": [], "historico": []}


# ------------------------------------------------------------------ adicionais
def test_adicionais_somam_no_mensal_sem_desconto():
    r = catalog.avaliar_proposta("onix", 4, "cwb", "AM", 12, None, 3, ["TELEMETRIA"], 3)
    assert r["adicionais_mensal_por_veiculo"] == 59 + 3 * 180                      # telemetria + 3 pacotes de km
    assert r["total_mensal"] == round(r["total_mensal_veiculos"] + r["adicionais_total_mensal"], 2)
    assert r["total_mensal_veiculos"] == round(2690 * 0.97 * 4, 2)               # desconto só no carro


def test_adicional_invalido_ou_na_diaria():
    with pytest.raises(ErroFerramenta, match="não existe"):
        catalog.calcular("onix", 1, "sp", "AM", 12, adicionais=["SEGURO_VIDA"])
    with pytest.raises(ErroFerramenta, match="só existem no mensal"):
        catalog.calcular("onix", 1, "sp", "AD", dias=3, adicionais=["TELEMETRIA"])


def test_cadastro_indica_km_acima_da_franquia():
    assert catalog.consultar_cliente("C04")["km_acima_da_franquia_por_veiculo"] == 2500
    assert catalog.pacotes_km_necessarios(4500) == 3 and catalog.pacotes_km_necessarios(1800) == 0
    assert "adicionais_mensal" in catalog.consultar_catalogo("sp")


# ------------------------------------------------------------------ roteamento por tier
def test_tier_a_nao_negocia_com_a_ia():
    ctx = ctx_de("C10")
    assert "erro" in agent.executar("avaliar_proposta", {"modelo": "onix", "quantidade": 15, "cidade": "sp", "produto": "AM",
                                                         "prazo_meses": 36}, ctx)
    with pytest.raises(ErroFerramenta, match="Tier A"):
        catalog.registrar_proposta(ctx["conversation_id"], "C10", "B", "onix", 15, "sp", "AM", 36)
    assert catalog.consultar_cliente("C10")["atendimento"] == "EXECUTIVO_DEDICADO"


def test_tier_a_no_contexto_do_gpt(gpt):
    g = gpt("Oi! Vou te passar agora pro seu executivo dedicado.")
    cs.processar(cs.iniciar("C12", "B")["conversation_id"], "Oi, quero cotar 3 carros pra filial de BH")
    assert "CLIENTE TIER A" in g.recebidos[0]["messages"][0]["content"]


def test_modo_a_marca_tier_a_negociado(gpt):
    gpt('{"resposta": "Fechado!", "registrar_proposta": {"modelo": "onix", "quantidade": 15, "cidade": "sp", "produto": "AM", '
        '"prazo_meses": 36, "desconto_pct": 0}, "handoff": null}')
    c = cs.processar(cs.iniciar("C10", "A")["conversation_id"], "15 Onix por 36 meses")
    assert "TIER_A_NEGOCIADO_PELA_IA" in c["mensagens"][-1]["auditoria"]["violacoes"]
    assert evaluation.avaliar(c["conversation_id"])["tier_a_respeitado"] is False


# ------------------------------------------------------------------ qualificação e handoff com briefing
def test_handoff_leva_briefing_montado_pelo_sistema():
    ctx = ctx_de("C04")
    ctx["historico"] = [{"role": "cliente", "conteudo": "Quero 4 Dolphin"}]
    for nome, args in [("registrar_qualificacao", {"eh_decisor": False, "decisor": "Diretor financeiro", "prazo_decisao": "sexta"}),
                       ("avaliar_proposta", {"modelo": "dolphin", "quantidade": 4, "cidade": "cwb", "produto": "AM", "prazo_meses": 24,
                                             "desconto_pct": 9})]:
        ctx["memoria"].append({"ferramenta": nome, "entrada": args, "saida": agent.executar(nome, args, ctx)})
    out = agent.executar("criar_handoff", {"motivo": "SOLICITACAO_CLIENTE", "resumo": "Quer 4 Dolphin com 9%", "necessidade": "4 Dolphin",
                                           "objecao": "preço", "proximo_passo_sugerido": "ligar para o diretor financeiro"}, ctx)
    h = cs.fila_handoffs()[0]
    b = h["briefing"]
    assert out["briefing_enviado_ao_time"] and h["handoff_id"] == out["protocolo"]
    assert b["qualificacao"]["decisor"] == "Diretor financeiro" and b["ultima_condicao_avaliada"]["status"] == "ACIMA_DO_LIMITE"
    assert b["cliente"]["km_mes"] == 4500 and b["ultimas_mensagens"] == ["cliente: Quero 4 Dolphin"]


def test_qualificacao_aponta_o_que_falta():
    r = catalog.registrar_qualificacao(eh_decisor=True)
    assert r["faltando"] == ["decisor", "outros_envolvidos", "prazo_decisao"]


# ------------------------------------------------------------------ painel de concessões
def test_painel_de_concessoes():
    catalog.registrar_proposta("CVX", "C02", "B", "polo", 5, "sp", "AM", 12, desconto_pct=5, adicionais=["PROTECAO_TOTAL"])
    catalog.registrar_proposta("CVY", "C06", "B", "creta", 2, "sp", "AM", 12, desconto_pct=2)
    r = evaluation.painel_concessoes()
    t = r["totais"]
    assert t["propostas"] == 2 and t["com_desconto"] == 2 and t["aprovadas_gerente"] == 1
    assert t["sem_contrapartida"] == 1                                           # Creta 2 carros 12m com desconto
    polo = next(p for p in r["propostas"] if p["modelo"] == "Polo")
    cheio = round(2890 * 0.98, 2)
    assert polo["margem_cedida"] == round((cheio - round(cheio * 0.95, 2)) * 5, 2) and polo["receita_adicionais_mensal"] == 189 * 5


# ------------------------------------------------------------------ áudio
def test_audio_transcrito_segue_o_mesmo_fluxo(gpt, monkeypatch):
    monkeypatch.setattr(llm_client, "transcrever", lambda audio, nome, mime: {"texto": "quero três Onix em Curitiba",
                                                                              "modelo": "gpt-4o-mini-transcribe", "custo_gate": 0.0003})
    g = gpt("Show! Só pra confirmar: são 3 Onix em Curitiba, certo?")
    c = cs.processar_audio(cs.iniciar("C01", "B")["conversation_id"], b"fake", "audio/webm;codecs=opus", 4.2)
    cli = [m for m in c["mensagens"] if m["role"] == "cliente"][0]
    assert cli["conteudo"] == "quero três Onix em Curitiba" and cli["auditoria"]["audio"]["duracao_s"] == 4.2
    assert "[ÁUDIO TRANSCRITO] quero três Onix em Curitiba" in str(g.recebidos[0]["messages"])


def test_audio_sem_transcricao_disponivel_da_503():
    with TestClient(A.app) as c:
        conv = c.post("/api/conversations", json={"cliente_id": "C01"}).json()
        r = c.post(f"/api/conversations/{conv['conversation_id']}/audio",
                   json={"audio_base64": base64.b64encode(b"x" * 20).decode(), "mime": "audio/webm"})
    assert r.status_code == 503 and "Transcrição indisponível" in r.json()["detail"]


def test_endpoint_de_transcricao_e_404_do_gate(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "llm")
    monkeypatch.setenv("API_KEY", "k")
    assert llm_client.endpoint_transcricao().endswith("/llm-gate/v2/audio/transcriptions")

    class R:
        status_code, text = 404, "not found"
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: R())
    with pytest.raises(llm_client.TranscricaoIndisponivel, match="não tem transcrição"):
        llm_client.transcrever(llm_client._wav_silencio(0.1))


def test_api_do_gerente():
    with TestClient(A.app) as c:
        assert "totais" in c.get("/api/gerente/concessoes").json()
        assert c.get("/api/gerente/handoffs").json() == []


def test_prompt_tem_as_novas_regras():
    for trecho in ("QUALIFIQUE", "ADICIONAIS", "tier A", "ÁUDIO TRANSCRITO"):
        assert trecho in agent.BASE
