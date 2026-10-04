"""Ciclo de vida das conversas (receptivas: quem abre é o cliente) e persistência/auditoria."""
import json
import uuid
from datetime import datetime, timezone

from database import db
from database.db import BASE_DIR
from services import agent, catalog, llm_client

LOG_FILE = BASE_DIR / "logs" / "conversations.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")  # ms: mede o tempo de resposta da Fernanda


def listar_clientes() -> list[dict]:
    rows = db.fetch_all("SELECT c.*, r.roteiro_id, r.texto AS roteiro_texto FROM clientes c LEFT JOIN roteiros r "
                        "ON r.cliente_id = c.cliente_id ORDER BY c.cliente_id")
    return [r for r in rows if r["roteiro_id"]]  # os 12 atendíveis (a filial C12B entra só como outro CNPJ do grupo)


def fila_handoffs() -> list[dict]:
    rows = db.fetch_all("SELECT h.*, c.razao_social, c.tier FROM handoffs h JOIN clientes c USING (cliente_id) ORDER BY h.criado_em DESC")
    for r in rows:
        r["briefing"] = json.loads(r.pop("briefing_json") or "{}")
    return rows


def listar_roteiros() -> list[dict]:
    return db.fetch_all("SELECT * FROM roteiros ORDER BY generico, roteiro_id")


def iniciar(cliente_id: str, modo: str = "B", livre: bool = False, roteiro_id: str | None = None,
            abertura: str | None = None) -> dict:
    if modo not in ("A", "B"):
        raise ValueError("modo deve ser A ou B")
    abertura = str(abertura or agent.abertura_padrao())
    if abertura not in agent.ABERTURAS:
        raise ValueError("abertura deve ser 1 ou 2")
    if not db.fetch_one("SELECT 1 FROM clientes WHERE cliente_id=?", (cliente_id,)):
        raise LookupError("Cliente inexistente")
    if livre:
        roteiro_id = None
    elif not roteiro_id:
        roteiro_id = f"R_{cliente_id}"
    cid = "CV-" + uuid.uuid4().hex[:10].upper()
    estado = {"memoria": [], "abertura": abertura}
    db.execute("INSERT INTO conversas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (cid, cliente_id, modo, int(livre), roteiro_id, _now(), None, "ATIVA", "EM_ANDAMENTO",
                json.dumps(catalog.estoque_atual()), json.dumps(estado)))
    return obter(cid)


def obter(conv_id: str) -> dict:
    c = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not c:
        raise LookupError("Conversa inexistente")
    c["abertura"] = json.loads(c.pop("estado_json") or "{}").get("abertura", "1")
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


def processar_audio(conv_id: str, audio: bytes, mime: str, duracao_s: float | None) -> dict:
    """Áudio do cliente -> transcrição -> mesmo fluxo de texto. A transcrição fica visível e auditada."""
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/mp4": "m4a", "audio/mpeg": "mp3"}.get(mime.split(";")[0], "webm")
    t = llm_client.transcrever(audio, f"audio.{ext}", mime.split(";")[0])
    if not t["texto"]:
        raise ValueError("Não deu para entender o áudio (transcrição vazia). Tente de novo.")
    return processar(conv_id, t["texto"], {"audio": {"duracao_s": duracao_s, "modelo": t["modelo"], "custo_gate": t["custo_gate"]}})


def processar(conv_id: str, texto: str, meta_cliente: dict | None = None, simular_falha: bool = False) -> dict:
    row = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    if row["status"] != "ATIVA":
        raise ValueError("Conversa encerrada; reinicie para continuar")
    estado = json.loads(row["estado_json"])
    historico = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    _log(conv_id, "cliente", texto, meta_cliente)
    ctx = {"conversation_id": conv_id, "cliente_id": row["cliente_id"], "modo": row["modo"], "memoria": estado["memoria"],
           "abertura": estado.get("abertura", "1"),
           "historico": historico + [{"role": "cliente", "conteudo": texto}]}
    entrada = f"[ÁUDIO TRANSCRITO] {texto}" if meta_cliente and meta_cliente.get("audio") else texto
    try:
        if simular_falha:  # usado pelo Laboratório para testar a contingência ("GPT fora do ar")
            raise llm_client.LLMUnavailable("Falha simulada pelo Laboratório")
        r = (agent.turno_a if row["modo"] == "A" else agent.turno_b)(ctx, historico, entrada)
    except llm_client.LLMUnavailable as e:
        r = {"texto": agent.CONTINGENCIA, "chamadas": [], "violacoes": [], "resultado_validacao": "contingencia",
             "erro_llm": str(e), "modo_ferramentas": None, "tokens_entrada": 0, "tokens_saida": 0, "custo_gate": 0}
    auditoria = {k: r.get(k) for k in ("chamadas", "violacoes", "resultado_validacao", "modo_ferramentas", "erro_llm", "tiques")}
    auditoria["modo"] = row["modo"]
    auditoria["modelo_llm"] = llm_client.modelo("vendedora")
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
    row = db.fetch_one("SELECT estado_json FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    abertura = json.loads(row["estado_json"] or "{}").get("abertura", "1")
    for p in db.fetch_all("SELECT modelo, cidade, unidades_reservadas FROM propostas WHERE conversation_id=?", (conv_id,)):
        db.execute("UPDATE estoque SET unidades = unidades + ? WHERE modelo=? AND cidade=?", (p["unidades_reservadas"], p["modelo"], p["cidade"]))
    for t in ("mensagens", "propostas", "handoffs"):
        db.execute(f"DELETE FROM {t} WHERE conversation_id=?", (conv_id,))
    db.execute("UPDATE conversas SET status='ATIVA', fim=NULL, desfecho='EM_ANDAMENTO', estado_json=?, estoque_inicio_json=? "
               "WHERE conversation_id=?", (json.dumps({"memoria": [], "abertura": abertura}), json.dumps(catalog.estoque_atual()), conv_id))
    return obter(conv_id)
