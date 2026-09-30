"""API do Vendedor IA — MVP simulado v2 (venda interna receptiva). Executar: python iniciar.py"""
import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import db, seed
from services import catalog, conversations as conv, evaluation, llm_client, training

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def _lifespan(_app):
    seed.ensure()
    yield


app = FastAPI(title="Vendedor IA — MVP simulado", version="2.0.0", lifespan=_lifespan)


class NovaConversa(BaseModel):
    cliente_id: str
    modo: str = Field("B", pattern="^[AB]$", description="A = LLM pura (controle) | B = LLM + ferramentas")
    livre: bool = False
    roteiro_id: str | None = None


class Audio(BaseModel):
    audio_base64: str = Field(min_length=10, max_length=15_000_000)
    mime: str = "audio/webm"
    duracao_s: float | None = None


class NovoTreino(BaseModel):
    vendedor: str = Field(min_length=1, max_length=80)
    cliente_id: str
    modo: str = Field("TREINO", pattern="^(PROVA|TREINO)$")
    dificuldade: str = Field("medio", pattern="^(facil|medio|dificil)$")


class Condicao(BaseModel):
    modelo: str
    quantidade: int = Field(gt=0)
    cidade: str
    produto: str = "AM"
    prazo_meses: int | None = None
    dias: int | None = None
    desconto_pct: float = 0.0
    adicionais: list[str] = []
    pacotes_km_extra: int | None = None


class Mensagem(BaseModel):
    conteudo: str = Field(min_length=1, max_length=2000)


def _tratar(fn, *a):
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/health")
def health():
    return {"ok": True, "llm_mode": llm_client.mode(), "llm_configurado": llm_client.configured()}


@app.get("/api/clientes")
def clientes():
    return conv.listar_clientes()


@app.get("/api/roteiros")
def roteiros():
    return conv.listar_roteiros()


@app.get("/api/estoque")
def estoque():
    return catalog.estoque_atual()


@app.post("/api/estoque/reiniciar")
def reiniciar_estoque():
    catalog.reiniciar_estoque()
    return catalog.estoque_atual()


@app.get("/api/catalogo")
def catalogo(cidade: str | None = None):
    return _tratar(catalog.consultar_catalogo, cidade)


@app.post("/api/conversations", status_code=201)
def nova(body: NovaConversa):
    return _tratar(conv.iniciar, body.cliente_id, body.modo, body.livre, body.roteiro_id)


@app.get("/api/conversations/{cid}")
def obter(cid: str):
    return _tratar(conv.obter, cid)


@app.post("/api/conversations/{cid}/messages")
def mensagem(cid: str, body: Mensagem):
    return _tratar(conv.processar, cid, body.conteudo)


@app.post("/api/conversations/{cid}/audio")
def audio(cid: str, body: Audio):
    import base64
    try:
        dados = base64.b64decode(body.audio_base64.split(",")[-1])
    except ValueError:
        raise HTTPException(400, "Áudio inválido")
    try:
        return _tratar(conv.processar_audio, cid, dados, body.mime, body.duracao_s)
    except llm_client.TranscricaoIndisponivel as e:
        raise HTTPException(503, f"Transcrição indisponível: {e}")


@app.get("/api/gerente/concessoes")
def concessoes():
    return evaluation.painel_concessoes()


@app.get("/api/gerente/handoffs")
def handoffs():
    return conv.fila_handoffs()


@app.post("/api/conversations/{cid}/reset")
def reset(cid: str):
    return _tratar(conv.reiniciar, cid)


@app.post("/api/conversations/{cid}/close")
def fechar(cid: str):
    return _tratar(conv.encerrar, cid)


@app.post("/api/conversations/{cid}/evaluate")
def avaliar(cid: str):
    return _tratar(evaluation.avaliar, cid)


@app.get("/api/comparativo")
def comparativo():
    return evaluation.comparativo()


@app.get("/api/conversations/{cid}/export")
def exportar(cid: str, formato: str = "json"):
    c = _tratar(conv.obter, cid)
    if formato == "txt":
        linhas = [f"# {cid} — {c['cliente']['razao_social']} — modo {c['modo']}{' (livre)' if c['livre'] else ''}", ""]
        linhas += [f"[{m['timestamp']}] {'Vendedor IA' if m['role'] == 'vendedor' else 'Cliente'}: {m['conteudo']}" for m in c["mensagens"]]
        return PlainTextResponse("\n".join(linhas), headers={"Content-Disposition": f'attachment; filename="{cid}.txt"'})
    return c


@app.get("/api/export/classificador.csv")
def exportar_classificador(ids: str | None = None):
    """Conversas no formato de ENTRADA do classificar_ligacoes_diario.py (';', cd_segmento, transcricao_limpa)."""
    convs = db.fetch_all("SELECT conversation_id, modo, livre, inicio FROM conversas ORDER BY inicio")
    if ids:
        alvo = set(ids.split(","))
        convs = [c for c in convs if c["conversation_id"] in alvo]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["cd_segmento", "data_hora_inicio", "direcao", "nome_agente_1", "status_transcricao", "modo", "livre", "transcricao_limpa"])
    for c in convs:
        msgs = db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (c["conversation_id"],))
        if not msgs:
            continue
        texto = " | ".join(f"{'AGENTE' if m['role'] == 'vendedor' else 'CLIENTE'}: {' '.join(m['conteudo'].split())}" for m in msgs)
        w.writerow([c["conversation_id"], c["inicio"].replace("T", " ").split("+")[0], "Inbound", f"Vendedor IA ({c['modo']})",
                    "success", c["modo"], c["livre"], texto])
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="vendedor_ia_para_classificador.csv"'})


# ------------------------------------------------------------------ MODO TREINO (vendedor humano x cliente simulado)
@app.get("/api/treino/personas")
def treino_personas():
    return training.personas()


@app.post("/api/treino", status_code=201)
def treino_novo(body: NovoTreino):
    return _tratar(training.iniciar, body.vendedor, body.cliente_id, body.modo, body.dificuldade)


@app.get("/api/treino/historico")
def treino_historico(vendedor: str | None = None):
    return training.historico(vendedor)


@app.get("/api/treino/{tid}")
def treino_obter(tid: str):
    return _tratar(training.obter, tid)


@app.post("/api/treino/{tid}/mensagem")
def treino_mensagem(tid: str, body: Mensagem):
    return _tratar(training.mensagem, tid, body.conteudo)


@app.post("/api/treino/{tid}/audio")
def treino_audio(tid: str, body: Audio):
    import base64
    try:
        return _tratar(training.audio, tid, base64.b64decode(body.audio_base64.split(",")[-1]), body.mime, body.duracao_s)
    except llm_client.TranscricaoIndisponivel as e:
        raise HTTPException(503, f"Transcrição indisponível: {e}")


@app.post("/api/treino/{tid}/avaliar-condicao")
def treino_avaliar(tid: str, body: Condicao):
    return _tratar(training.avaliar_condicao, tid, body.model_dump())


@app.post("/api/treino/{tid}/registrar-proposta")
def treino_registrar(tid: str, body: Condicao):
    return _tratar(training.registrar, tid, body.model_dump())


@app.post("/api/treino/{tid}/encerrar")
def treino_encerrar(tid: str):
    return _tratar(training.encerrar, tid)


app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE / "frontend" / "index.html")


@app.get("/treino")
def pagina_treino():
    return FileResponse(BASE / "frontend" / "treino.html")
