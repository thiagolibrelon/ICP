import re

from database import db


def identificar_cliente(identificador: str) -> dict | None:
    """Aceita cliente_id (C001), código (CLI-1001) ou CNPJ fictício."""
    ident = (identificador or "").strip()
    digits = re.sub(r"\D", "", ident)
    row = db.fetch_one(
        "SELECT * FROM clientes WHERE upper(cliente_id)=upper(?) OR upper(codigo_cliente)=upper(?) OR cnpj_ficticio=?",
        (ident, ident, ident))
    if row is None and digits:
        for c in db.fetch_all("SELECT * FROM clientes"):
            if re.sub(r"\D", "", c["cnpj_ficticio"]) == digits:
                return c
    return row


def consultar_perfil(cliente_id: str) -> dict | None:
    return db.fetch_one("SELECT * FROM clientes WHERE cliente_id=?", (cliente_id,))


def consultar_historico(cliente_id: str) -> list[dict]:
    return db.fetch_all("SELECT * FROM historico_mensal WHERE cliente_id=? ORDER BY mes_referencia", (cliente_id,))


def resumo_historico(cliente_id: str) -> dict:
    h = consultar_historico(cliente_id)
    if not h:
        return {"meses": 0}
    ultimos = h[-3:]
    primeiros = h[:3]
    media = lambda rows: sum(r["volume_medio_ad"] + r["volume_medio_am"] for r in rows) / len(rows)  # noqa: E731
    ini, fim = media(primeiros), media(ultimos)
    tendencia = "ESTAVEL"
    if fim > ini * 1.1:
        tendencia = "CRESCENTE"
    elif fim < ini * 0.9:
        tendencia = "EM_QUEDA"
    return {
        "meses": len(h),
        "tendencia": tendencia,
        "reclamacoes_12m": sum(r["reclamacoes"] for r in h),
        "cancelamentos_12m": sum(r["cancelamentos"] for r in h),
        "receita_12m": round(sum(r["receita_ad"] + r["receita_am"] for r in h), 2),
    }


def consultar_oportunidades(cliente_id: str) -> list[dict]:
    return db.fetch_all("SELECT * FROM oportunidades WHERE cliente_id=?", (cliente_id,))


def consultar_ofertas(cliente_id: str) -> list[dict]:
    return db.fetch_all("SELECT * FROM ofertas WHERE cliente_id=? AND status='ATIVA'", (cliente_id,))
