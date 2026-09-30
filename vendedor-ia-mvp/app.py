"""API FastAPI do Vendedor IA (MVP simulado). Executar: python iniciar.py  (ou python -m uvicorn app:app --reload)"""
import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import db, seed
from services import (conversation_service as conv, customer_service, evaluation_service, llm_client, pricing_service,
                      rules_service, tools)

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def _lifespan(_app):
    seed.ensure()
    yield


app = FastAPI(title="Vendedor IA — MVP simulado", version="0.2.0", lifespan=_lifespan)


class NovaConversa(BaseModel):
    cenario_id: str | None = None
    identificador: str | None = Field(None, description="Código, CNPJ fictício ou cliente_id")


class Mensagem(BaseModel):
    conteudo: str = Field(min_length=1, max_length=2000)


class SimulaPreco(BaseModel):
    cliente_id: str
    produto: str
    quantidade: int = Field(gt=0)
    prazo: int = Field(gt=0, description="meses (mensais) ou dias (DIARIA)")
    praca: str | None = None


class AvaliaDesconto(BaseModel):
    cliente_id: str
    oferta_id: str
    desconto_solicitado: float = Field(ge=0, le=1)


class NovaProposta(BaseModel):
    conversation_id: str
    produto: str
    quantidade: int = Field(gt=0)
    prazo: int = Field(gt=0)
    praca: str | None = None
    desconto: float = Field(0.0, ge=0, le=1)


class NovoHandoff(BaseModel):
    conversation_id: str
    motivo: str
    resumo: str = ""


def _or_404(fn, *a):
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/health")
def health():
    return {"ok": True, "llm_mode": llm_client.mode(), "llm_configurado": llm_client.configured()}


@app.get("/api/scenarios")
def scenarios():
    return conv.listar_cenarios()


@app.post("/api/conversations", status_code=201)
def nova_conversa(body: NovaConversa):
    return _or_404(conv.iniciar_conversa, body.cenario_id, body.identificador)


@app.post("/api/conversations/{cid}/messages")
def mensagem(cid: str, body: Mensagem):
    return _or_404(conv.processar_mensagem, cid, body.conteudo)


@app.get("/api/conversations/{cid}")
def obter(cid: str):
    return _or_404(conv.obter_conversa, cid)


@app.post("/api/conversations/{cid}/evaluate")
def avaliar(cid: str):
    _or_404(conv.obter_conversa, cid)
    return evaluation_service.avaliar(cid)


@app.post("/api/conversations/{cid}/reset")
def reset(cid: str):
    return _or_404(conv.reiniciar, cid)


@app.get("/api/conversations/{cid}/export")
def exportar(cid: str, formato: str = "json"):
    c = _or_404(conv.obter_conversa, cid)
    if formato == "txt":
        linhas = [f"# Transcrição {cid} — {c['cliente']['razao_social']} ({c['cenario_id']})", ""]
        for m in c["mensagens"]:
            linhas.append(f"[{m['timestamp']}] {'Vendedor IA' if m['role'] == 'vendedor' else 'Cliente'}: {m['conteudo']}")
        return PlainTextResponse("\n".join(linhas), headers={"Content-Disposition": f'attachment; filename="{cid}.txt"'})
    return c


@app.get("/api/export/classificador.csv")
def exportar_classificador(ids: str | None = None):
    """Conversas no formato de ENTRADA do classificar_ligacoes_diario.py (';', colunas cd_segmento e transcricao_limpa).
    Assim o vendedor IA é medido com a mesma régua (C12) das ligações reais."""
    convs = db.fetch_all("SELECT conversation_id, cenario_id, inicio FROM conversas ORDER BY inicio")
    if ids:
        alvo = set(ids.split(","))
        convs = [c for c in convs if c["conversation_id"] in alvo]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["cd_segmento", "data_hora_inicio", "direcao", "nome_agente_1", "status_transcricao", "cenario_id", "transcricao_limpa"])
    for c in convs:
        msgs = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (c["conversation_id"],))
        if not any(m["role"] == "cliente" for m in msgs):
            continue
        texto = " | ".join(f"{'AGENTE' if m['role'] == 'vendedor' else 'CLIENTE'}: {' '.join(m['conteudo'].split())}" for m in msgs)
        suporte = c["cenario_id"].startswith("S")
        w.writerow([c["conversation_id"], c["inicio"].replace("T", " ").split("+")[0], "Inbound" if suporte else "Outbound",
                    "Vendedor IA", "success", c["cenario_id"], texto])
    return Response(("\ufeff" + buf.getvalue()).encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="vendedor_ia_para_classificador.csv"'})


@app.get("/api/customers/{cid}")
def cliente(cid: str):
    c = customer_service.consultar_perfil(cid)
    if not c:
        raise HTTPException(404, "Cliente inexistente")
    return c


@app.get("/api/customers/{cid}/history")
def historico(cid: str):
    return customer_service.consultar_historico(cid)


@app.get("/api/customers/{cid}/opportunities")
def oportunidades(cid: str):
    return customer_service.consultar_oportunidades(cid)


@app.post("/api/pricing/simulate")
def simular(body: SimulaPreco):
    return pricing_service.simular_preco(**body.model_dump())


@app.post("/api/rules/evaluate-discount")
def avaliar_desc(body: AvaliaDesconto):
    return rules_service.avaliar_desconto(**body.model_dump())


@app.post("/api/proposals", status_code=201)
def proposta(body: NovaProposta):
    c = _or_404(conv.obter_conversa, body.conversation_id)
    cot = pricing_service.simular_preco(c["cliente_id"], body.produto, body.quantidade, body.prazo, body.praca)
    if "erro" in cot:
        raise HTTPException(422, cot)
    av = rules_service.avaliar_desconto(c["cliente_id"], cot["oferta_id"], body.desconto)
    if not av["aprovado"]:
        raise HTTPException(422, {"erro": "DESCONTO_ACIMA_DA_ALCADA", **av})
    return tools.registrar_proposta(body.conversation_id, c["cliente_id"], cot, body.desconto, "Criada via API")


@app.post("/api/handoffs", status_code=201)
def handoff(body: NovoHandoff):
    c = _or_404(conv.obter_conversa, body.conversation_id)
    return tools.criar_handoff(body.conversation_id, c["cliente_id"], body.motivo, body.resumo)


@app.get("/api/metrics")
def metricas():
    return evaluation_service.metricas()


app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE / "frontend" / "index.html")
