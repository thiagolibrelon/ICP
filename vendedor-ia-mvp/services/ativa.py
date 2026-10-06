"""Frente ATIVA: a Fernanda inicia o contato com clientes da carteira, sempre com um motivo verdadeiro do sistema.

Regras (decididas em Python, não pelo GPT):
- só clientes da carteira da venda interna: Tier A (estratégico) é do executivo e nunca recebe contato ativo da IA;
- quem pediu para parar (descadastro) nunca mais recebe contato ativo;
- frequência: no máximo 1 contato ativo por cliente a cada DIAS_ENTRE_CONTATOS dias, e no máximo 1 follow-up sem resposta;
- o motivo vem do cadastro (contrato vencendo, diária alta, frota própria, km acima da franquia); a IA não inventa motivo.
Contatos do Laboratório (origem 'laboratorio') não contam para frequência e não deixam descadastro para trás.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from database import db
from database.personas import PERSONAS
from services import catalog

DIAS_ENTRE_CONTATOS = 7
MAX_FOLLOW_UPS = 1
FRANQUIA_KM = 2000
RESULTADOS = ("INTERESSADO", "RETORNAR_DEPOIS", "SEM_INTERESSE", "PERDIDO_CONCORRENTE", "PESSOA_ERRADA", "DESCADASTRO")
FINAIS = {"RETORNAR_DEPOIS", "SEM_INTERESSE", "PERDIDO_CONCORRENTE", "PESSOA_ERRADA", "DESCADASTRO"}
NOMES_MOTIVO = {"RENOVACAO": "Contrato vencendo", "DIARIA_ALTA": "Diária com uso alto", "FROTA_PROPRIA": "Frota própria",
                "KM_ACIMA_FRANQUIA": "Km acima da franquia", "RELACIONAMENTO": "Relacionamento"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def garantir_tabelas() -> None:
    sql = (Path(__file__).resolve().parent.parent / "database" / "schema.sql").read_text(encoding="utf-8")
    conn = db.connect()
    try:
        conn.executescript(sql[sql.index("-- ATIVA"):])
        conn.commit()
    finally:
        conn.close()


def contato_de(cliente_id: str) -> dict:
    p = PERSONAS.get(cliente_id) or {}
    return {"nome": p.get("contato") or "responsável", "cargo": p.get("cargo") or ""}


def motivos(cliente_id: str) -> list[dict]:
    """Motivos de contato tirados do cadastro, do mais forte para o mais fraco. Todo número aqui é real (do sistema)."""
    c = catalog.consultar_cliente(cliente_id)
    modelo = (c.get("modelo_atual") or "").title()
    qtd, out = c.get("qtd_atual") or 0, []
    vence = c.get("contrato_vence_dias")
    if c.get("produto_atual") == "AM" and vence is not None and vence <= 90:
        data = (datetime.now() + timedelta(days=vence)).strftime("%d/%m/%Y")
        out.append({"motivo": "RENOVACAO", "prioridade": 100 if vence <= 30 else 70,
                    "resumo": f"contrato de {qtd} {modelo} no mensal vence em {vence} dias ({data})",
                    "dados": {"qtd": qtd, "modelo": modelo, "vence_em_dias": vence, "data_vencimento": data}})
    if c.get("produto_atual") == "AD" and (c.get("dias_diaria_mes") or 0) >= 15:
        out.append({"motivo": "DIARIA_ALTA", "prioridade": 80,
                    "resumo": f"usa {qtd} {modelo} na diária cerca de {c['dias_diaria_mes']} dias por mês",
                    "dados": {"qtd": qtd, "modelo": modelo, "dias_por_mes": c["dias_diaria_mes"]}})
    if (c.get("frota_propria") or 0) > 0:
        out.append({"motivo": "FROTA_PROPRIA", "prioridade": 60,
                    "resumo": f"tem frota própria de {c['frota_propria']} carros",
                    "dados": {"frota_propria": c["frota_propria"]}})
    if c.get("produto_atual") == "AM" and (c.get("km_mes") or 0) > FRANQUIA_KM:
        out.append({"motivo": "KM_ACIMA_FRANQUIA", "prioridade": 50,
                    "resumo": f"roda cerca de {c['km_mes']} km/mês por carro, acima da franquia de {FRANQUIA_KM} km",
                    "dados": {"km_mes": c["km_mes"], "franquia_km": FRANQUIA_KM, "qtd": qtd, "modelo": modelo}})
    if not out:
        out.append({"motivo": "RELACIONAMENTO", "prioridade": 20, "resumo": f"cliente com {qtd} {modelo} ({c.get('produto_atual')})".strip(),
                    "dados": {"qtd": qtd, "modelo": modelo}})
    for m in out:
        m["titulo"] = NOMES_MOTIVO[m["motivo"]]
    return sorted(out, key=lambda m: -m["prioridade"])


def descadastrado(cliente_id: str) -> bool:
    garantir_tabelas()
    return bool(db.fetch_one("SELECT 1 FROM ativo_descadastros WHERE cliente_id=?", (cliente_id,)))


def _ultimo_contato(cliente_id: str) -> dict | None:
    return db.fetch_one("SELECT * FROM ativo_contatos WHERE cliente_id=? AND origem != 'laboratorio' ORDER BY criado_em DESC LIMIT 1",
                        (cliente_id,))


def pode_contatar(cliente_id: str, origem: str = "simulador") -> tuple[bool, str]:
    garantir_tabelas()
    c = db.fetch_one("SELECT tier FROM clientes WHERE cliente_id=?", (cliente_id,))
    if not c:
        return False, "Cliente inexistente"
    if c["tier"] == "A":
        return False, "Cliente estratégico (Tier A): o contato ativo é do executivo dedicado, não da IA"
    if descadastrado(cliente_id):
        return False, "Cliente pediu para não receber contato ativo (descadastro)"
    if origem != "laboratorio":
        u = _ultimo_contato(cliente_id)
        if u and datetime.fromisoformat(u["criado_em"]) > datetime.now(timezone.utc) - timedelta(days=DIAS_ENTRE_CONTATOS):
            return False, f"Limite de frequência: já houve contato ativo com este cliente nos últimos {DIAS_ENTRE_CONTATOS} dias"
    return True, ""


def registrar_contato(conversation_id: str, cliente_id: str, motivo: dict, origem: str) -> str:
    cid = "AT-" + uuid.uuid4().hex[:8].upper()
    db.execute("INSERT INTO ativo_contatos (contato_id, conversation_id, cliente_id, motivo, motivo_json, origem, criado_em, atualizado_em) "
               "VALUES (?,?,?,?,?,?,?,?)", (cid, conversation_id, cliente_id, motivo["motivo"], json.dumps(motivo, ensure_ascii=False),
                                             origem, _now(), _now()))
    return cid


def contato_da_conversa(conversation_id: str) -> dict | None:
    garantir_tabelas()
    r = db.fetch_one("SELECT * FROM ativo_contatos WHERE conversation_id=?", (conversation_id,))
    if r:
        r["motivo_dados"] = json.loads(r.pop("motivo_json") or "{}")
    return r


def marcar_resposta(conversation_id: str) -> None:
    db.execute("UPDATE ativo_contatos SET respondeu=1, atualizado_em=? WHERE conversation_id=?", (_now(), conversation_id))


def contar_follow_up(conversation_id: str) -> None:
    c = contato_da_conversa(conversation_id)
    if not c:
        raise ValueError("Esta conversa não é um contato ativo")
    if c["respondeu"]:
        raise ValueError("O cliente já respondeu: siga a conversa, não é caso de follow-up")
    if c["follow_ups"] >= MAX_FOLLOW_UPS:
        raise ValueError(f"Limite de frequência: no máximo {MAX_FOLLOW_UPS} follow-up sem resposta")
    db.execute("UPDATE ativo_contatos SET follow_ups=follow_ups+1, atualizado_em=? WHERE conversation_id=?", (_now(), conversation_id))


def registrar_resultado(conversation_id: str, resultado: str, detalhe: str = "", retorno_em: str | None = None) -> dict:
    """Ferramenta da Fernanda (registrar_resultado_contato). Descadastro vale para todos os contatos futuros."""
    resultado = str(resultado or "").upper().strip()
    if resultado not in RESULTADOS:
        raise ValueError(f"Resultado inválido. Use um destes: {', '.join(RESULTADOS)}")
    c = contato_da_conversa(conversation_id)
    if not c:
        raise ValueError("Esta conversa não é um contato ativo")
    db.execute("UPDATE ativo_contatos SET resultado=?, detalhe=?, retorno_em=?, atualizado_em=? WHERE conversation_id=?",
               (resultado, (detalhe or "")[:500], retorno_em, _now(), conversation_id))
    if resultado == "DESCADASTRO":
        db.execute("INSERT OR REPLACE INTO ativo_descadastros VALUES (?,?,?,?)", (c["cliente_id"], _now(), c["origem"], conversation_id))
    return {"registrado": True, "resultado": resultado,
            "orientacao": {"DESCADASTRO": "Confirme em uma frase curta que ele não receberá mais contatos ativos e encerre.",
                           "PESSOA_ERRADA": "Não fale do contrato com esta pessoa. Agradeça e, se ela quiser, peça o contato do responsável.",
                           "RETORNAR_DEPOIS": "Confirme o dia combinado e encerre com cordialidade.",
                           "PERDIDO_CONCORRENTE": "Agradeça, deixe a porta aberta e encerre sem insistir.",
                           "SEM_INTERESSE": "Agradeça e encerre sem insistir.",
                           "INTERESSADO": "Siga a conversa normalmente."}[resultado]}


def limpar_laboratorio(conversation_id: str) -> None:
    """Uma execução do Laboratório não pode deixar descadastro para as próximas."""
    db.execute("DELETE FROM ativo_descadastros WHERE conversation_id=? AND origem='laboratorio'", (conversation_id,))


def carteira() -> list[dict]:
    """Lista priorizada para o time (e para a Fernanda): quem chamar, por quê e se pode chamar agora."""
    garantir_tabelas()
    out = []
    for c in db.fetch_all("SELECT cliente_id, razao_social, tier, cidade FROM clientes ORDER BY cliente_id"):
        ok, porque = pode_contatar(c["cliente_id"])
        ms = motivos(c["cliente_id"])
        u = _ultimo_contato(c["cliente_id"])
        out.append({"cliente_id": c["cliente_id"], "razao_social": c["razao_social"], "tier": c["tier"], "contato": contato_de(c["cliente_id"]),
                    "motivo": ms[0], "outros_motivos": ms[1:], "prioridade": ms[0]["prioridade"] if c["tier"] != "A" else 0,
                    "pode_contatar": ok, "bloqueio": porque, "descadastrado": descadastrado(c["cliente_id"]),
                    "ultimo_contato": {k: u[k] for k in ("criado_em", "resultado", "respondeu", "follow_ups", "conversation_id")} if u else None})
    return sorted(out, key=lambda x: (not x["pode_contatar"], -x["prioridade"], x["cliente_id"]))


def reiniciar_carteira() -> None:
    """Simulador: apaga o histórico de contatos e os descadastros (dados fictícios)."""
    garantir_tabelas()
    db.execute("DELETE FROM ativo_contatos WHERE origem != 'laboratorio'")
    db.execute("DELETE FROM ativo_descadastros")
