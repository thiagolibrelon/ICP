"""Fatos Challenger com DADO CONCRETO, calculados em Python (o LLM só os comunica).

Mesma régua do classificador de ligações (decisão de 24/09/2026): Challenger só conta com dado concreto —
número, valor, prazo ou regra. Aqui o dado vem do histórico sintético, da tabela de preço ou de uma regra sintética.
"""
import json

from database.db import BASE_DIR
from services import customer_service, pricing_service
from services.textutil import brl, norm

_FATOS = BASE_DIR / "data" / "fatos_challenger.json"


def _estaticos() -> dict:
    return json.loads(_FATOS.read_text(encoding="utf-8")) if _FATOS.exists() else {}


# Em que momento cada tipo de fato faz sentido (CH1 responde a dúvida de regra/cancelamento; CH2 acompanha o preço...)
MOMENTOS = {
    "CH1": {"EXPLICAR_REGRAS", "TRATAR_OBJECAO"},
    "CH2": {"APRESENTAR_COTACAO", "TRATAR_OBJECAO"},
    "B3": {"TRATAR_OBJECAO", "CONTRAPROPOR_DESCONTO", "NEGAR_DESCONTO"},
}
MOMENTO_PADRAO = {"APRESENTAR_COTACAO", "TRATAR_OBJECAO", "EXPLICAR_REGRAS", "CONTRAPROPOR_DESCONTO", "NEGAR_DESCONTO"}


def para_acao(cliente_id: str, acao: str) -> dict | None:
    fato = challenger(cliente_id)
    return fato if fato and acao in MOMENTOS.get(fato["codigo"], MOMENTO_PADRAO) else None


def challenger(cliente_id: str) -> dict | None:
    """{"codigo", "texto", ...valores} ou None se não houver dado concreto para este cliente."""
    hist = customer_service.consultar_historico(cliente_id)
    if cliente_id == "C002" and hist:
        # CH2 (ROI): custo médio das diárias nos últimos 3 meses x mesma frota no mensal (tabela)
        ult = hist[-3:]
        custo = round(sum(h["receita_ad"] for h in ult) / len(ult), 2)
        veiculos = max(1, round(sum(h["volume_medio_ad"] for h in ult) / len(ult)))
        cidade = customer_service.consultar_perfil(cliente_id)["cidade"]
        cot = pricing_service.simular_preco(cliente_id, "MENSAL", veiculos, 12, norm(cidade).upper())
        if "erro" not in cot and custo > cot["preco_total"]:
            return {"codigo": "CH2", "custo_diarias_mes": custo, "custo_mensal_equivalente": cot["preco_total"], "veiculos": veiculos,
                    "texto": (f"Nos últimos 3 meses vocês gastaram em média {brl(custo)} por mês em diárias, com cerca de {veiculos} veículos; "
                              f"no mensal, {veiculos} veículos ficam em {brl(cot['preco_total'])} por mês pela tabela.")}
    if cliente_id == "C003" and len(hist) >= 6:
        # B3 (usou histórico) com número: queda de volume
        vol = lambda rows: sum(r["volume_medio_ad"] + r["volume_medio_am"] for r in rows) / len(rows)  # noqa: E731
        ini, fim = round(vol(hist[:3])), round(vol(hist[-3:]))
        if fim < ini:
            return {"codigo": "B3", "veiculos_inicio": ini, "veiculos_atual": fim,
                    "texto": f"Pelo histórico, vocês saíram de cerca de {ini} para {fim} veículos ao longo dos últimos 12 meses — quero entender o que mudou."}
    return _estaticos().get(cliente_id)
