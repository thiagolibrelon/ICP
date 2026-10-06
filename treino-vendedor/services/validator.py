"""Checagens determinísticas das falas do vendedor no Treino: valor que não bate com a tabela e limite de desconto revelado.
Entram na dimensão "Disciplina de margem" da nota (parte calculada pelo sistema, sem GPT)."""
import re

from services.util import norm, parse_brl

TOLERANCIA = 0.011


def _numeros(obj, out_money: set, out_pct: set, chave: str = "") -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        (out_pct if chave.endswith("_pct") else out_money).add(round(float(obj), 2))
    elif isinstance(obj, str):
        for p in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", obj):
            out_pct.add(round(float(p.replace(",", ".")), 2))
        for m in re.findall(r"R\$\s*([\d.]+(?:,\d{1,2})?)", obj):
            out_money.add(round(parse_brl(m), 2))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _numeros(v, out_money, out_pct, str(k))
    elif isinstance(obj, list):
        for v in obj:
            _numeros(v, out_money, out_pct, chave)


def permitidos(saidas: list) -> tuple[set, set]:
    money, pct = set(), set()
    for s in saidas:
        _numeros(s, money, pct)
    return money, pct


def _contem(valor: float, conjunto: set) -> bool:
    return any(abs(valor - x) <= TOLERANCIA for x in conjunto)


def margens_reveladas(texto: str, margens: set, liberados: set) -> list[str]:
    """% perto de 'máximo/limite/teto/margem' igual a uma margem interna e que o sistema não liberou como contraproposta."""
    achados = []
    t = norm(texto)
    for trecho in re.findall(r"(?:maximo|limite|teto|margem|no maximo|chegar a)[^.?!]{0,50}?\d+(?:[.,]\d+)?\s*%|\d+(?:[.,]\d+)?\s*%[^.?!]{0,30}?(?:no maximo|de limite|e o maximo|e o teto)", t):
        for p in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", trecho):
            v = round(float(p.replace(",", ".")), 2)
            if _contem(v, margens) and not _contem(v, liberados):
                achados.append(f"MARGEM_REVELADA:{p}%")
    return achados


def valores_nao_verificados(texto: str, saidas: list) -> list[str]:
    """Valores em R$ citados pelo vendedor que não saem da tabela nem dos cálculos que ele fez."""
    money, _ = permitidos(saidas)
    return [f"R$ {m}" for m in re.findall(r"R\$\s*([\d.]+(?:,\d{1,2})?)", texto) if not _contem(round(parse_brl(m), 2), money)]
