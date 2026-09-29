from database import db

EPS = 1e-9


def get_rule(cliente_id: str, produto: str | None = None) -> dict | None:
    """Regra vigente do segmento do cliente (e produto, se informado)."""
    sql = ("SELECT r.* FROM regras_negociacao r JOIN clientes c ON c.segmento = r.segmento "
           "WHERE c.cliente_id = ?")
    params: list = [cliente_id]
    if produto:
        sql += " AND r.produto = ?"
        params.append(produto)
    return db.fetch_one(sql, tuple(params))


def produtos_permitidos(cliente_id: str) -> list[str]:
    rows = db.fetch_all(
        "SELECT r.produto FROM regras_negociacao r JOIN clientes c ON c.segmento = r.segmento WHERE c.cliente_id = ?",
        (cliente_id,))
    return [r["produto"] for r in rows]


def avaliar_desconto(cliente_id: str, oferta_id: str, desconto_solicitado: float) -> dict:
    oferta = db.fetch_one("SELECT * FROM ofertas WHERE oferta_id=? AND cliente_id=?", (oferta_id, cliente_id))
    if oferta is None:
        return {"aprovado": False, "desconto_maximo": 0.0, "desconto_concedido": 0.0, "exige_handoff": False,
                "motivo": "OFERTA_INEXISTENTE", "regra_id": None}
    regra = get_rule(cliente_id, oferta["produto"])
    maximo = regra["desconto_maximo"] if regra else 0.0
    if desconto_solicitado <= maximo + EPS:
        return {"aprovado": True, "desconto_maximo": maximo, "desconto_concedido": desconto_solicitado,
                "exige_handoff": False, "motivo": "DENTRO_DA_ALCADA", "regra_id": regra["regra_id"] if regra else None}
    return {"aprovado": False, "desconto_maximo": maximo, "desconto_concedido": maximo,
            "exige_handoff": bool(regra and regra["exige_handoff"]),
            "motivo": "SOLICITACAO_ACIMA_DA_ALCADA", "regra_id": regra["regra_id"] if regra else None}
