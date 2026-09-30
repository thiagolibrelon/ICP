"""Ciclo de vida das conversas (receptivas: quem abre é o cliente) e persistência/auditoria."""
import json
import uuid
from datetime import datetime, timezone

from database import db
from database.db import BASE_DIR
from services import agent, catalog, llm_client

LOG_FILE = BASE_DIR / "logs" / "conversations.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def listar_clientes() -> list[dict]:
    rows = db.fetch_all("SELECT c.*, r.roteiro_id, r.texto AS roteiro_texto FROM clientes c LEFT JOIN roteiros r "
                        "ON r.cliente_id = c.cliente_id ORDER BY c.cliente_id")
    return [r for r in rows if r["roteiro_id"]]  # os 12 atendíveis (a filial C12B entra só como outro CNPJ do grupo)


def listar_roteiros() -> list[dict]:
    return db.fetch_all("SELECT * FROM roteiros ORDER BY generico, roteiro_id")


def iniciar(cliente_id: str, modo: str = "B", livre: bool = False, roteiro_id: str | None = None) -> dict:
    if modo not in ("A", "B"):
        raise ValueError("modo deve ser A ou B")
    if not db.fetch_one("SELECT 1 FROM clientes WHERE cliente_id=?", (cliente_id,)):
        raise LookupError("Cliente inexistente")
    if livre:
        roteiro_id = None
    elif not roteiro_id:
        roteiro_id = f"R_{cliente_id}"
    cid = "CV-" + uuid.uuid4().hex[:10].upper()
    estado = {"memoria": []}
    db.execute("INSERT INTO conversas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (cid, cliente_id, modo, int(livre), roteiro_id, _now(), None, "ATIVA", "EM_ANDAMENTO",
                json.dumps(catalog.estoque_atual()), json.dumps(estado)))
    return obter(cid)


def obter(conv_id: str) -> dict:
    c = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not c:
        raise LookupError("Conversa inexistente")
    c.pop("estado_json")
    c["estoque_inicio"] = json.loads(c.pop("estoque_inicio_json") or "[]")
    msgs = db.fetch_all("SELECT * FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    for m in msgs:
        m["auditoria"] = json.loads(m.pop("auditoria_json")) if m.get("auditoria_json") else None
    c["mensagens"] = msgs
    c["cliente"] = catalog.consultar_cliente(c["cliente_id"])
    c["roteiro"] = db.fetch_one("SELECT * FROM roteiros WHERE roteiro_id=?", (c["roteiro_id"],)) if c["roteiro_id"] else None
    c["propostas"] = db.fetch_all("SELECT * FROM propostas WHERE conversation_id=?", (conv_id,))
    c["handoffs"] = db.fetch_all("SELECT * FROM handoffs WHERE conversation_id=?", (conv_id,))
    return c


def _log(conv_id: str, role: str, conteudo: str, auditoria: dict | None = None, uso: dict | None = None) -> None:
    u = uso or {}
    db.execute("INSERT INTO mensagens (conversation_id,timestamp,role,conteudo,tokens_entrada,tokens_saida,custo_gate,auditoria_json) "
               "VALUES (?,?,?,?,?,?,?,?)", (conv_id, _now(), role, conteudo, u.get("tokens_entrada", 0), u.get("tokens_saida", 0),
                                          u.get("custo_gate") or 0, json.dumps(auditoria, ensure_ascii=False, default=str) if auditoria else None))
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"conversation_id": conv_id, "role": role, "conteudo": conteudo, "auditoria": auditoria},
                               ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def processar(conv_id: str, texto: str) -> dict:
    row = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    if row["status"] != "ATIVA":
        raise ValueError("Conversa encerrada; reinicie para continuar")
    estado = json.loads(row["estado_json"])
    historico = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    _log(conv_id, "cliente", texto)
    ctx = {"conversation_id": conv_id, "cliente_id": row["cliente_id"], "modo": row["modo"], "memoria": estado["memoria"]}
    try:
        r = (agent.turno_a if row["modo"] == "A" else agent.turno_b)(ctx, historico, texto)
    except llm_client.LLMUnavailable as e:
        r = {"texto": agent.CONTINGENCIA, "chamadas": [], "violacoes": [], "resultado_validacao": "contingencia",
             "erro_llm": str(e), "modo_ferramentas": None, "tokens_entrada": 0, "tokens_saida": 0, "custo_gate": 0}
    auditoria = {k: r.get(k) for k in ("chamadas", "violacoes", "resultado_validacao", "modo_ferramentas", "erro_llm")}
    auditoria["modo"] = row["modo"]
    _log(conv_id, "vendedor", r["texto"], auditoria, r)
    estado["memoria"] = ctx["memoria"]
    props = db.fetch_one("SELECT COUNT(*) n FROM propostas WHERE conversation_id=?", (conv_id,))["n"]
    hos = db.fetch_one("SELECT COUNT(*) n FROM handoffs WHERE conversation_id=?", (conv_id,))["n"]
    desfecho = "PROPOSTA" if props else "HANDOFF" if hos else "EM_ANDAMENTO"
    db.execute("UPDATE conversas SET estado_json=?, desfecho=? WHERE conversation_id=?", (json.dumps(estado, default=str), desfecho, conv_id))
    return obter(conv_id)


def encerrar(conv_id: str) -> dict:
    row = db.fetch_one("SELECT desfecho FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    desfecho = row["desfecho"] if row["desfecho"] != "EM_ANDAMENTO" else "SEM_ACORDO"
    db.execute("UPDATE conversas SET status='ENCERRADA', fim=?, desfecho=? WHERE conversation_id=?", (_now(), desfecho, conv_id))
    return obter(conv_id)


def reiniciar(conv_id: str) -> dict:
    """Apaga mensagens/propostas/handoffs desta conversa e DEVOLVE ao estoque o que ela tinha reservado."""
    if not db.fetch_one("SELECT 1 FROM conversas WHERE conversation_id=?", (conv_id,)):
        raise LookupError("Conversa inexistente")
    for p in db.fetch_all("SELECT modelo, cidade, unidades_reservadas FROM propostas WHERE conversation_id=?", (conv_id,)):
        db.execute("UPDATE estoque SET unidades = unidades + ? WHERE modelo=? AND cidade=?", (p["unidades_reservadas"], p["modelo"], p["cidade"]))
    for t in ("mensagens", "propostas", "handoffs"):
        db.execute(f"DELETE FROM {t} WHERE conversation_id=?", (conv_id,))
    db.execute("UPDATE conversas SET status='ATIVA', fim=NULL, desfecho='EM_ANDAMENTO', estado_json=?, estoque_inicio_json=? "
               "WHERE conversation_id=?", (json.dumps({"memoria": []}), json.dumps(catalog.estoque_atual()), conv_id))
    return obter(conv_id)
