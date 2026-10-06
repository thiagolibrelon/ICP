"""Ciclo de vida das conversas (receptivas: quem abre é o cliente) e persistência/auditoria."""
import json
import uuid
from datetime import datetime, timezone

from database import db
from database.db import BASE_DIR
from services import agent, ativa, catalog, llm_client

LOG_FILE = BASE_DIR / "logs" / "conversations.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")  # ms: mede o tempo de resposta da Fernanda


def listar_clientes() -> list[dict]:
    rows = db.fetch_all("SELECT c.*, r.roteiro_id, r.texto AS roteiro_texto FROM clientes c LEFT JOIN roteiros r "
                        "ON r.cliente_id = c.cliente_id ORDER BY c.cliente_id")
    return [r for r in rows if r["roteiro_id"]]  # os 30 atendíveis (a filial C12B entra só como outro CNPJ do grupo)


def fila_handoffs() -> list[dict]:
    rows = db.fetch_all("SELECT h.*, c.razao_social, c.tier FROM handoffs h JOIN clientes c USING (cliente_id) ORDER BY h.criado_em DESC")
    for r in rows:
        r["briefing"] = json.loads(r.pop("briefing_json") or "{}")
    return rows


def listar_roteiros() -> list[dict]:
    return db.fetch_all("SELECT * FROM roteiros ORDER BY generico, roteiro_id")


def iniciar(cliente_id: str, modo: str = "B", livre: bool = False, roteiro_id: str | None = None,
            abertura: str | None = None, origem: str = "receptiva", motivo: str | None = None, fonte: str = "simulador") -> dict:
    """origem 'receptiva': o cliente procura a Fernanda. origem 'ativa': a Fernanda procura o cliente (chame abrir_contato)."""
    if origem not in ("receptiva", "ativa"):
        raise ValueError("origem deve ser receptiva ou ativa")
    if modo not in ("A", "B"):
        raise ValueError("modo deve ser A ou B")
    abertura = str(abertura or agent.abertura_padrao())
    if abertura not in agent.ABERTURAS:
        raise ValueError("abertura deve ser 1 ou 2")
    if not db.fetch_one("SELECT 1 FROM clientes WHERE cliente_id=?", (cliente_id,)):
        raise LookupError("Cliente inexistente")
    motivo_escolhido = None
    if origem == "ativa":
        ok, porque = ativa.pode_contatar(cliente_id, fonte)
        if not ok:
            raise ValueError(porque)
        ms = ativa.motivos(cliente_id)
        motivo_escolhido = next((m for m in ms if m["motivo"] == motivo), None) if motivo else ms[0]
        if not motivo_escolhido:
            raise ValueError("Motivo não se aplica a este cliente")
        livre, roteiro_id = False, None
    elif livre:
        roteiro_id = None
    elif not roteiro_id:
        roteiro_id = f"R_{cliente_id}"
    cid = "CV-" + uuid.uuid4().hex[:10].upper()
    estado = {"memoria": [], "abertura": abertura, "origem": origem, "motivo": motivo_escolhido}
    db.execute("INSERT INTO conversas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (cid, cliente_id, modo, int(livre), roteiro_id, _now(), None, "ATIVA", "EM_ANDAMENTO",
                json.dumps(catalog.estoque_atual()), json.dumps(estado)))
    if origem == "ativa":
        ativa.registrar_contato(cid, cliente_id, motivo_escolhido, fonte)
    return obter(cid)


def obter(conv_id: str) -> dict:
    c = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not c:
        raise LookupError("Conversa inexistente")
    est = json.loads(c.pop("estado_json") or "{}")
    c["abertura"] = est.get("abertura", "1")
    c["origem"] = est.get("origem", "receptiva")
    c["ativo"] = ativa.contato_da_conversa(conv_id) if c["origem"] == "ativa" else None
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


def _carregar(conv_id: str) -> tuple[dict, dict]:
    row = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    if row["status"] != "ATIVA":
        raise ValueError("Conversa encerrada; reinicie para continuar")
    return row, json.loads(row["estado_json"])


def _responder(conv_id: str, row: dict, estado: dict, historico: list[dict], entrada: str, extra: dict | None = None,
               simular_falha: bool = False, marca: dict | None = None) -> dict:
    """Um turno da Fernanda (modo A ou B) + auditoria + desfecho. 'entrada' é a fala do cliente ou uma instrução do sistema."""
    ctx = {"conversation_id": conv_id, "cliente_id": row["cliente_id"], "modo": row["modo"], "memoria": estado["memoria"],
           "abertura": estado.get("abertura", "1"), "origem": estado.get("origem", "receptiva"), "motivo": estado.get("motivo"),
           "historico": historico, **(extra or {})}
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
    auditoria.update(marca or {})
    _log(conv_id, "vendedor", r["texto"], auditoria, r)
    estado["memoria"] = ctx["memoria"]
    props = db.fetch_one("SELECT COUNT(*) n FROM propostas WHERE conversation_id=?", (conv_id,))["n"]
    hos = db.fetch_one("SELECT COUNT(*) n FROM handoffs WHERE conversation_id=?", (conv_id,))["n"]
    desfecho = "PROPOSTA" if props else "HANDOFF" if hos else "EM_ANDAMENTO"
    db.execute("UPDATE conversas SET estado_json=?, desfecho=? WHERE conversation_id=?", (json.dumps(estado, default=str), desfecho, conv_id))
    return obter(conv_id)


def processar(conv_id: str, texto: str, meta_cliente: dict | None = None, simular_falha: bool = False) -> dict:
    row, estado = _carregar(conv_id)
    historico = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    _log(conv_id, "cliente", texto, meta_cliente)
    if estado.get("origem") == "ativa":
        ativa.marcar_resposta(conv_id)
    entrada = f"[ÁUDIO TRANSCRITO] {texto}" if meta_cliente and meta_cliente.get("audio") else texto
    # o briefing de handoff usa as últimas mensagens, incluindo esta do cliente
    return _responder(conv_id, row, estado, historico, entrada, {"historico": historico + [{"role": "cliente", "conteudo": texto}]},
                      simular_falha=simular_falha)


INSTRUCAO_ABERTURA_ATIVA = ("[INÍCIO DO CONTATO ATIVO — instrução do sistema, não é mensagem do cliente] Escreva agora a sua primeira "
                            "mensagem para {nome}, seguindo as regras de CONTATO ATIVO: diga que é assistente virtual, traga o motivo "
                            "com os dados do sistema, faça UMA pergunta e ofereça falar com alguém do time.")
INSTRUCAO_FOLLOW_UP = ("[FOLLOW-UP — instrução do sistema, não é mensagem do cliente] O cliente não respondeu à sua mensagem há 2 dias. "
                       "Escreva UM follow-up curto e gentil, lembrando o motivo em uma frase e oferecendo parar os contatos se ele "
                       "preferir. Não repita a mensagem anterior.")


def abrir_contato(conv_id: str) -> dict:
    """Frente ativa: a Fernanda escreve a primeira mensagem."""
    row, estado = _carregar(conv_id)
    if estado.get("origem") != "ativa":
        raise ValueError("Esta conversa não é um contato ativo")
    if db.fetch_one("SELECT 1 FROM mensagens WHERE conversation_id=?", (conv_id,)):
        raise ValueError("O contato já foi aberto")
    nome = ativa.contato_de(row["cliente_id"])["nome"]
    return _responder(conv_id, row, estado, [], INSTRUCAO_ABERTURA_ATIVA.format(nome=nome), {"primeira_ativa": True},
                      marca={"etapa_ativa": "abertura"})


def follow_up(conv_id: str) -> dict:
    """Frente ativa: o cliente não respondeu. O sistema permite no máximo 1 follow-up (a regra é do Python, não do GPT)."""
    row, estado = _carregar(conv_id)
    if estado.get("origem") != "ativa":
        raise ValueError("Esta conversa não é um contato ativo")
    ativa.contar_follow_up(conv_id)
    historico = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    return _responder(conv_id, row, estado, historico, INSTRUCAO_FOLLOW_UP, marca={"etapa_ativa": "follow_up"})


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
    est_ant = json.loads(row["estado_json"] or "{}")
    abertura = est_ant.get("abertura", "1")
    for p in db.fetch_all("SELECT modelo, cidade, unidades_reservadas FROM propostas WHERE conversation_id=?", (conv_id,)):
        db.execute("UPDATE estoque SET unidades = unidades + ? WHERE modelo=? AND cidade=?", (p["unidades_reservadas"], p["modelo"], p["cidade"]))
    for t in ("mensagens", "propostas", "handoffs"):
        db.execute(f"DELETE FROM {t} WHERE conversation_id=?", (conv_id,))
    db.execute("UPDATE conversas SET status='ATIVA', fim=NULL, desfecho='EM_ANDAMENTO', estado_json=?, estoque_inicio_json=? "
               "WHERE conversation_id=?", (json.dumps({"memoria": [], "abertura": abertura, "origem": est_ant.get("origem", "receptiva"),
                                          "motivo": est_ant.get("motivo")}), json.dumps(catalog.estoque_atual()), conv_id))
    if est_ant.get("origem") == "ativa":
        db.execute("UPDATE ativo_contatos SET follow_ups=0, respondeu=0, resultado=NULL, detalhe=NULL, retorno_em=NULL WHERE conversation_id=?",
                   (conv_id,))
        db.execute("DELETE FROM ativo_descadastros WHERE conversation_id=?", (conv_id,))
    return obter(conv_id)
