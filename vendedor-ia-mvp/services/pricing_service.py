import json

from database import db
from database.db import BASE_DIR
from services import rules_service

_PRACAS_FILE = BASE_DIR / "data" / "pracas.json"


def _fator_praca(praca: str | None) -> tuple[float, str | None]:
    if not praca:
        return 1.0, None
    pracas = json.loads(_PRACAS_FILE.read_text(encoding="utf-8"))
    chave = praca.upper()
    if chave not in pracas:
        return 1.0, None
    return pracas[chave], chave


def simular_preco(cliente_id: str, produto: str, quantidade: int, prazo: int, praca: str | None = None) -> dict:
    """Preço calculado por código. `prazo` = meses (produtos mensais) ou dias (DIARIA)."""
    regra = rules_service.get_rule(cliente_id, produto)
    oferta = db.fetch_one("SELECT * FROM ofertas WHERE cliente_id=? AND produto=? AND status='ATIVA'", (cliente_id, produto))
    if regra is None or oferta is None:
        return {"erro": "PRODUTO_NAO_PERMITIDO", "produto": produto}
    if not (regra["quantidade_minima"] <= quantidade <= regra["quantidade_maxima"]):
        return {"erro": "QUANTIDADE_FORA_DA_REGRA", "minimo": regra["quantidade_minima"],
                "maximo": regra["quantidade_maxima"], "regra_id": regra["regra_id"]}
    if not (regra["prazo_minimo"] <= prazo <= regra["prazo_maximo"]):
        return {"erro": "PRAZO_FORA_DA_REGRA", "minimo": regra["prazo_minimo"],
                "maximo": regra["prazo_maximo"], "regra_id": regra["regra_id"]}
    fator, praca_ok = _fator_praca(praca)
    unitario = round(oferta["preco_tabela"] * fator, 2)
    total = round(unitario * quantidade * (prazo if produto == "DIARIA" else 1), 2)
    return {
        "oferta_id": oferta["oferta_id"], "cliente_id": cliente_id, "produto": produto, "quantidade": quantidade,
        "prazo": prazo, "unidade_prazo": "dias" if produto == "DIARIA" else "meses", "praca": praca_ok,
        "preco_unitario": unitario, "preco_total": total,
        "preco_total_mensal": None if produto == "DIARIA" else total,
        "desconto_maximo": regra["desconto_maximo"],
        "preco_minimo_unitario": round(unitario * (1 - regra["desconto_maximo"]), 2),
        "validade_dias": oferta["validade_dias"], "beneficio_adicional": oferta["beneficio_adicional"] or None,
        "regra_id": regra["regra_id"],
    }


def aplicar_desconto(cotacao: dict, desconto: float) -> dict:
    """Preço final para um desconto JÁ validado por rules_service.avaliar_desconto."""
    unit = round(cotacao["preco_unitario"] * (1 - desconto), 2)
    total = round(unit * cotacao["quantidade"] * (cotacao["prazo"] if cotacao["produto"] == "DIARIA" else 1), 2)
    return {"desconto": desconto, "preco_unitario": unit, "preco_total": total}
