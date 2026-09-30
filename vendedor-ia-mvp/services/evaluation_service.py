"""Avaliação da conversa: regras determinísticas + comentário opcional do LLM avaliador."""
import json
import os
from pathlib import Path

from database import db
from services import conversation_service, llm_client

EPS = 1e-9
PROMPT_AVALIADOR = (Path(__file__).resolve().parent.parent / "prompts" / "avaliador.md").read_text(encoding="utf-8")
HANDOFF_OBRIGATORIO = {"HUMANO", "RECLAMACAO", "SUPORTE"}


def avaliar(conv_id: str) -> dict:
    conv = conversation_service.obter_conversa(conv_id)
    state = conv["estado"]
    vend = [m for m in conv["mensagens"] if m["role"] == "vendedor"]
    audits = [m["auditoria"] or {} for m in vend]
    intents = {a.get("intencao") for a in audits}
    cen = db.fetch_one("SELECT * FROM cenarios WHERE cenario_id=?", (conv["cenario_id"],))
    esperados = json.loads(cen["desfechos_esperados"]) if cen else []
    comercial = bool(cen["abertura_comercial"]) if cen else True
    obs: list[str] = []

    ofertou = any((a.get("fatos") or {}).get("cotacao") for a in audits)
    # diagnóstico
    if not comercial:
        diagnostico = 5 if not ofertou and "REGISTRAR_PROPOSTA" not in {a.get("acao") for a in audits} else 1
        if diagnostico == 1:
            obs.append("Forçou oferta em conversa de suporte.")
    else:
        perguntas = 0
        for m, a in zip(vend, audits):
            if (a.get("fatos") or {}).get("cotacao"):
                break
            perguntas += "?" in m["conteudo"]
        diagnostico = min(5, 2 + perguntas) if ofertou else 3
        if perguntas < 2 and ofertou:
            obs.append("Poderia aprofundar o diagnóstico antes de apresentar preço.")

    violacoes = [v for a in audits for v in a.get("violacoes_brutas") or []]
    inventada = bool(violacoes)
    fora_alcada = False
    for a in audits:
        d = (a.get("fatos") or {}).get("desconto")
        if d and d["desconto_concedido"] > (d["desconto_maximo"] or 0) + EPS:
            fora_alcada = True
    fora_alcada = fora_alcada or bool(state.get("fora_da_alcada"))
    aderencia = max(1, 5 - 2 * len({tuple(v) for v in violacoes}) - (3 if fora_alcada else 0))
    if inventada:
        obs.append(f"O LLM produziu conteúdo não autorizado ({len(violacoes)}) e a resposta foi reescrita: {', '.join(violacoes[:3])}.")

    # handoff
    motivos_legitimos = {"DESCONTO_ACIMA_DA_ALCADA", "ANALISE_CREDITO"}
    exigido = bool(intents & HANDOFF_OBRIGATORIO)
    criado = bool(state.get("handoff"))
    handoff_correto = criado if exigido else (not criado or state["handoff"]["motivo"] in motivos_legitimos | {"SOLICITACAO_CLIENTE"})
    if not handoff_correto:
        obs.append("Handoff exigido não foi criado." if not criado else "Handoff criado sem motivo previsto.")

    # Challenger com dado concreto (mesma régua do classificador C12) e janela comercial em suporte (OP1)
    meta = json.loads(cen["meta_json"] or "{}") if cen else {}
    challenger = state.get("challenger_usado")
    if meta.get("dado_concreto") and not challenger:
        obs.append(f"Não usou o dado concreto disponível ({meta['dado_concreto']}).")
    janela_ok = None
    if meta.get("problema"):
        janela_prevista = meta.get("produto")
        janela_ok = bool(state.get("janela")) == bool(janela_prevista)
        if janela_prevista and not state.get("janela"):
            obs.append("OP1: suporte sem pergunta comercial, embora o problema se conectasse a um produto.")
        if not janela_prevista and (state.get("janela") or ofertou):
            obs.append("Ofereceu algo comercial em suporte puro.")

    # próximo passo
    ultimo = vend[-1] if vend else None
    ultima_acao = (audits[-1].get("acao") if audits else None)
    if ultimo and ultima_acao in ("REGISTRAR_PROPOSTA", "HANDOFF_CRIADO", "ENCAMINHAR_SUPORTE", "ENCERRAR",
                                                   "REGISTRAR_INTERESSE", "RESPEITAR_RECUSA", "INFORMAR_SEM_CREDITO") and "em até" in ultimo["conteudo"]:
        proximo = 5
    elif ultimo and "?" in ultimo["conteudo"]:
        proximo = 3
    else:
        proximo = 2
    if proximo < 5:
        obs.append("A conversa ainda não terminou com próximo passo e prazo definidos.")

    # objeção
    trataram = [a for a in audits if a.get("intencao") in ("OBJECAO", "DESCONTO")]
    if trataram:
        objecao = 5 if all(a.get("acao") in ("TRATAR_OBJECAO", "APLICAR_DESCONTO", "CONTRAPROPOR_DESCONTO", "NEGAR_DESCONTO", "HANDOFF_CRIADO")
                           for a in trataram) and not violacoes else 3
    else:
        objecao = None

    observado = state["desfecho"]
    ok = observado in esperados
    if not ok:
        obs.append(f"Desfecho observado ({observado}) diferente dos esperados ({', '.join(esperados)}).")
    if not obs:
        obs.append("Conversa aderente às regras e ao roteiro esperado.")

    if llm_client.mode() != "mock" and llm_client.configured():
        try:
            transcr = "\n".join(f"{m['role']}: {m['conteudo']}" for m in conv["mensagens"])
            r = llm_client.chat([{"role": "system", "content": PROMPT_AVALIADOR},
                                 {"role": "user", "content": transcr}], max_tokens=400, retries=1)
            extra = json.loads(r["texto"]).get("observacoes", [])
            obs.extend(str(x) for x in extra[:4])
        except Exception:  # noqa: BLE001 - avaliador LLM é opcional
            obs.append("Avaliador LLM indisponível; apenas avaliação determinística.")

    res = {"conversation_id": conv_id, "cenario_id": conv["cenario_id"], "diagnostico": diagnostico, "aderencia_regras": aderencia,
           "tratamento_objecao": objecao, "proximo_passo": proximo, "informacao_inventada": inventada,
           "desconto_fora_alcada": fora_alcada, "handoff_correto": handoff_correto,
           "desfecho_esperado": "|".join(esperados), "desfecho_observado": observado, "desfecho_ok": ok,
           "dado_concreto_usado": challenger, "dado_concreto_esperado": meta.get("dado_concreto") or None,
           "janela_comercial_ok": janela_ok, "interesse_registrado": (state.get("interesse") or {}).get("produto"),
           "custo_gate": round(sum(a.get("custo_gate") or 0 for a in audits), 6), "observacoes": obs}
    notas = [n for n in (diagnostico, aderencia, objecao, proximo) if n is not None]
    res["nota_comercial"] = round(sum(notas) / len(notas), 2)
    db.execute("DELETE FROM avaliacoes WHERE conversation_id=?", (conv_id,))
    db.execute("INSERT INTO avaliacoes (conversation_id,cenario_id,diagnostico,aderencia_regras,tratamento_objecao,proximo_passo,"
               "informacao_inventada,desconto_fora_alcada,handoff_correto,desfecho_esperado,desfecho_observado,observacoes) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (conv_id, conv["cenario_id"], diagnostico, aderencia, objecao, proximo, int(inventada), int(fora_alcada),
                int(handoff_correto), res["desfecho_esperado"], observado, json.dumps(obs, ensure_ascii=False)))
    return res


def metricas() -> dict:
    avs = db.fetch_all("SELECT a.*, c.proposta_gerada FROM avaliacoes a JOIN conversas c USING (conversation_id)")
    convs = db.fetch_all("SELECT conversation_id, desfecho FROM conversas")
    n = len(avs)
    if not n:
        return {"conversas_avaliadas": 0, "conversas_totais": len(convs)}
    avg = lambda k: round(sum(a[k] for a in avs if a[k] is not None) / max(1, sum(1 for a in avs if a[k] is not None)), 2)  # noqa: E731
    msgs = db.fetch_all("SELECT conversation_id, role, tokens_entrada, tokens_saida FROM mensagens")
    tok_in = sum(m["tokens_entrada"] or 0 for m in msgs)
    tok_out = sum(m["tokens_saida"] or 0 for m in msgs)
    custo = tok_in / 1000 * float(os.getenv("LLM_COST_PER_1K_IN", "0.00075")) + tok_out / 1000 * float(os.getenv("LLM_COST_PER_1K_OUT", "0.0045"))
    custo_gate = sum((json.loads(m["auditoria_json"]).get("custo_gate") or 0)
                     for m in db.fetch_all("SELECT auditoria_json FROM mensagens WHERE auditoria_json IS NOT NULL"))
    com_prop = [a["conversation_id"] for a in avs if a["proposta_gerada"]]
    n_msgs_prop = [sum(1 for m in msgs if m["conversation_id"] == cid and m["role"] == "cliente") for cid in com_prop]
    pct = lambda cond: round(100 * sum(1 for a in avs if cond(a)) / n, 1)  # noqa: E731
    return {
        "conversas_avaliadas": n, "conversas_totais": len(convs),
        "taxa_conclusao_pct": pct(lambda a: a["desfecho_observado"] != "EM_ANDAMENTO"),
        "taxa_desfecho_esperado_pct": pct(lambda a: a["desfecho_observado"] in a["desfecho_esperado"].split("|")),
        "taxa_preco_correto_pct": pct(lambda a: not a["informacao_inventada"]),
        "taxa_desconto_dentro_alcada_pct": pct(lambda a: not a["desconto_fora_alcada"]),
        "taxa_handoff_correto_pct": pct(lambda a: a["handoff_correto"]),
        "taxa_proximo_passo_definido_pct": pct(lambda a: a["proximo_passo"] >= 5),
        "taxa_respostas_inventadas_pct": pct(lambda a: a["informacao_inventada"]),
        "media_mensagens_ate_proposta": round(sum(n_msgs_prop) / len(n_msgs_prop), 1) if n_msgs_prop else None,
        "tokens_por_conversa": round((tok_in + tok_out) / max(1, len(convs)), 1),
        "custo_por_conversa_estimado_usd": round(custo / max(1, len(convs)), 4),
        "custo_por_conversa_llm_gate": round(custo_gate / max(1, len(convs)), 6) if custo_gate else None,
        "nota_comercial_media": round((avg("diagnostico") + avg("proximo_passo")) / 2, 2),
        "nota_aderencia_regras_media": avg("aderencia_regras"),
    }
