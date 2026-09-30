"""Validações determinísticas da resposta do vendedor contra os fatos autorizados."""
import re

from services.textutil import parse_brl

MONEY_KEYS = {"preco_unitario", "preco_total", "preco_total_mensal", "preco_minimo_unitario", "custo_diarias_mes",
              "custo_mensal_equivalente"}
PCT_KEYS = {"desconto", "desconto_concedido", "desconto_maximo", "desconto_solicitado"}


def _collect(obj, keys: set[str], out: list[float]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
            else:
                _collect(v, keys, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, keys, out)


def valores_autorizados(fatos: dict) -> tuple[set[float], set[float]]:
    money, pcts = [], []
    _collect(fatos, MONEY_KEYS, money)
    _collect(fatos, PCT_KEYS, pcts)
    return {round(m, 2) for m in money}, {round(p * 100, 2) for p in pcts}


BANNED = [
    (r"\b(system prompt|prompt|instru[cç][oõ]es internas|meu prompt)\b", "MENCIONA_INSTRUCOES_INTERNAS"),
    (r"(?:temos|tem|h[aá]|garant\w+|confirmo)\b[^.]{0,40}\bdispon[ií]vel|disponibilidade\s+(?:est[aá]\s+)?(?:garantida|confirmada)|reservei", "PROMETE_DISPONIBILIDADE"),
]
PROPOSTA_ENVIADA = r"proposta\s+(?:j[aá]\s+)?(?:foi\s+|est[aá]\s+)?(?:enviada|emitida|registrada)|enviei\s+(?:a|sua)\s+proposta|registrei\s+(?:a|sua)\s+proposta"
HANDOFF_FEITO = r"\b(?:transferi|encaminhei|abri\s+(?:um\s+)?(?:chamado|handoff)|j[aá]\s+encaminhamos|foi\s+encaminad)"


def validar(resposta: str, fatos: dict) -> list[str]:
    violacoes: list[str] = []
    money_ok, pct_ok = valores_autorizados(fatos)
    for m in re.findall(r"R\$\s*([\d\.]+(?:,\d{1,2})?)", resposta):
        if round(parse_brl(m), 2) not in money_ok:
            violacoes.append(f"PRECO_NAO_AUTORIZADO:{m}")
    for p in re.findall(r"(\d+(?:,\d+)?)\s*%", resposta):
        if round(float(p.replace(",", ".")), 2) not in pct_ok:
            violacoes.append(f"DESCONTO_NAO_AUTORIZADO:{p}%")
    low = resposta.lower()
    for pattern, code in BANNED:
        if re.search(pattern, low):
            violacoes.append(code)
    if re.search(PROPOSTA_ENVIADA, low) and not fatos.get("proposta"):
        violacoes.append("PROPOSTA_AFIRMADA_SEM_REGISTRO")
    if re.search(HANDOFF_FEITO, low) and not fatos.get("handoff"):
        violacoes.append("HANDOFF_AFIRMADO_SEM_REGISTRO")
    if not resposta.strip():
        violacoes.append("RESPOSTA_VAZIA")
    return violacoes
