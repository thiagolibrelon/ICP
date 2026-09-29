"""Ferramentas com efeito: proposta e handoff SIMULADOS (nada sai do sistema)."""
import uuid
from datetime import datetime, timezone

from database import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registrar_proposta(conversation_id: str, cliente_id: str, cotacao: dict, desconto: float, observacao: str = "") -> dict:
    fator = 1 - desconto
    pid = "PROP-" + uuid.uuid4().hex[:8].upper()
    preco_unit = round(cotacao["preco_unitario"] * fator, 2)
    db.execute("INSERT INTO propostas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (pid, conversation_id, cliente_id, cotacao["produto"], cotacao["quantidade"], cotacao["prazo"],
                preco_unit, desconto, cotacao["validade_dias"], observacao, _now()))
    return {"proposta_id": pid, "preco_unitario": preco_unit, "desconto": desconto, "validade_dias": cotacao["validade_dias"],
            "simulada": True}


def criar_handoff(conversation_id: str, cliente_id: str, motivo: str, resumo: str) -> dict:
    hid = "HO-" + uuid.uuid4().hex[:8].upper()
    db.execute("INSERT INTO handoffs VALUES (?,?,?,?,?,?)", (hid, conversation_id, cliente_id, motivo, resumo, _now()))
    return {"handoff_id": hid, "motivo": motivo, "simulado": True}


def encerrar_conversa(conversation_id: str, status: str = "ENCERRADA") -> None:
    db.execute("UPDATE conversas SET status=?, fim=? WHERE conversation_id=?", (status, _now(), conversation_id))
