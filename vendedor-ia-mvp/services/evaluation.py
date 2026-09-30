"""Métricas determinísticas por conversa e o comparativo A (LLM pura) x B (LLM + ferramentas).

Conversas livres ficam fora do comparativo (não contaminam o A/B), mas continuam auditadas e exportáveis para o C12.
"""
import json
import re

from database import db
from services import catalog
from services.util import norm


def avaliar(conv_id: str) -> dict:
    c = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not c:
        raise LookupError("Conversa inexistente")
    msgs = db.fetch_all("SELECT * FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    vend = [m for m in msgs if m["role"] == "vendedor"]
    auds = [json.loads(m["auditoria_json"]) if m["auditoria_json"] else {} for m in vend]
    props = db.fetch_all("SELECT * FROM propostas WHERE conversation_id=?", (conv_id,))
    hos = db.fetch_all("SELECT * FROM handoffs WHERE conversation_id=?", (conv_id,))
    viol = [v for a in auds for v in (a.get("violacoes") or [])]
    entregues_com_problema = sum(1 for a in auds if (c["modo"] == "A" and a.get("violacoes"))
                                 or a.get("resultado_validacao") in ("mensagem_segura", "limite_de_passos"))

    def conta(prefixo):
        return sum(1 for v in viol if v.startswith(prefixo))

    sem_contrapartida = [p["proposta_id"] for p in props if (p["desconto_pct"] or 0) > 0
                         and not catalog.tem_contrapartida(p["produto"], p["quantidade"], p["prazo_meses"])]
    fora_regra = [p["proposta_id"] for p in props if not json.loads(p["checagem_json"] or "{}").get("valida", True)]
    # diagnóstico: fez pergunta antes da primeira mensagem com preço?
    idx_preco = next((i for i, m in enumerate(vend) if "R$" in m["conteudo"]), None)
    perguntou_antes = any("?" in m["conteudo"] for m in vend[: idx_preco if idx_preco is not None else len(vend)])
    ultimo = norm(vend[-1]["conteudo"]) if vend else ""
    proximo_passo = bool(props or hos) or bool(re.search(r"\b(ate|amanha|hoje|em \d+ dias?|retorno|proximo passo|protocolo)\b", ultimo))
    ferramentas = [ch["nome"] for a in auds for ch in (a.get("chamadas") or [])]
    return {
        "conversation_id": conv_id, "modo": c["modo"], "livre": bool(c["livre"]), "cliente_id": c["cliente_id"],
        "roteiro_id": c["roteiro_id"], "desfecho": c["desfecho"], "turnos_cliente": sum(1 for m in msgs if m["role"] == "cliente"),
        "propostas": len(props), "handoffs": len(hos),
        "mensagens_com_problema_entregues": entregues_com_problema,
        "correcoes_automaticas_b": sum(1 for a in auds if a.get("resultado_validacao") == "corrigida"),
        "valores_nao_verificados": conta("VALOR_NAO_VERIFICADO"), "margem_revelada": conta("MARGEM_REVELADA") + conta("MENCIONA_MARGEM"),
        "afirmou_sem_registro": conta("PROPOSTA_OU_RESERVA_SEM_REGISTRO") + conta("HANDOFF_SEM_REGISTRO"),
        "vazou_instrucoes": conta("VAZOU_INSTRUCOES"),
        "desconto_fora_da_regra": conta("DESCONTO_FORA_DA_REGRA"), "preco_divergente": conta("PRECO_DIVERGENTE"),
        "alem_do_estoque": conta("ALEM_DO_ESTOQUE"),
        "propostas_fora_da_regra": fora_regra, "concessao_sem_contrapartida": sem_contrapartida,
        "diagnostico_antes_do_preco": perguntou_antes if idx_preco is not None else None,
        "proximo_passo_definido": proximo_passo, "ferramentas_chamadas": len(ferramentas),
        "usou_comparacao": any(f.startswith("comparar_") for f in ferramentas),
        "tokens": sum((m["tokens_entrada"] or 0) + (m["tokens_saida"] or 0) for m in msgs),
        "custo_gate": round(sum(m["custo_gate"] or 0 for m in msgs), 6),
        "tiques_de_robo": sum(len(a.get("tiques") or []) for a in auds),
        "baloes_por_resposta": round(sum(m["conteudo"].count("\n\n") + 1 for m in vend) / len(vend), 1) if vend else None,
        "violacoes": viol,
    }


def comparativo() -> dict:
    """A x B só com conversas de roteiro (não livres) que tiveram pelo menos 1 turno do cliente."""
    convs = db.fetch_all("SELECT conversation_id, modo, livre FROM conversas")
    res = {"A": [], "B": []}
    livres = 0
    for c in convs:
        if c["livre"]:
            livres += 1
            continue
        a = avaliar(c["conversation_id"])
        if a["turnos_cliente"]:
            res[c["modo"]].append(a)

    def resumo(lst):
        n = len(lst)
        if not n:
            return {"conversas": 0}
        pct = lambda f: round(100 * sum(1 for a in lst if f(a)) / n, 1)  # noqa: E731
        return {"conversas": n,
                "com_proposta_pct": pct(lambda a: a["propostas"]),
                "com_problema_entregue_ao_cliente_pct": pct(lambda a: a["mensagens_com_problema_entregues"]),
                "valor_nao_verificado_pct": pct(lambda a: a["valores_nao_verificados"]),
                "margem_revelada_pct": pct(lambda a: a["margem_revelada"]),
                "proposta_fora_da_regra_pct": pct(lambda a: a["propostas_fora_da_regra"]),
                "concessao_sem_contrapartida_pct": pct(lambda a: a["concessao_sem_contrapartida"]),
                "alem_do_estoque_pct": pct(lambda a: a["alem_do_estoque"]),
                "diagnostico_antes_do_preco_pct": pct(lambda a: a["diagnostico_antes_do_preco"]),
                "proximo_passo_definido_pct": pct(lambda a: a["proximo_passo_definido"]),
                "com_tique_de_robo_pct": pct(lambda a: a["tiques_de_robo"]),
                "media_turnos": round(sum(a["turnos_cliente"] for a in lst) / n, 1),
                "tokens_por_conversa": round(sum(a["tokens"] for a in lst) / n),
                "custo_gate_por_conversa": round(sum(a["custo_gate"] for a in lst) / n, 6)}

    return {"A_llm_pura": resumo(res["A"]), "B_llm_com_ferramentas": resumo(res["B"]), "conversas_livres_fora_do_comparativo": livres}
