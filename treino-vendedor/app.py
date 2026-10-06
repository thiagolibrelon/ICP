"""API do Treino de vendas — frente própria, separada da Fernanda e do Laboratório. Executar: python iniciar.py"""
import base64
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from database import db, seed
from services import llm_client, training, trilha

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def _lifespan(_app):
    seed.ensure()
    yield


app = FastAPI(title="Treino de vendas", version="1.0.0", lifespan=_lifespan)


class NovoTreino(BaseModel):
    vendedor: str = Field(min_length=1, max_length=80)
    cliente_id: str
    modo: str = Field("TREINO", pattern="^(PROVA|TREINO)$")
    dificuldade: str = Field("medio", pattern="^(facil|medio|dificil)$")
    frente: str = Field("receptiva", pattern="^(receptiva|ativa)$", description="ativa = o vendedor inicia o contato")
    coach: bool | None = Field(None, description="Coach IA ligado? Padrão: ligado no TREINO, sempre desligado na PROVA")


class Coach(BaseModel):
    ligado: bool


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


class Audio(BaseModel):
    audio_base64: str = Field(min_length=10, max_length=15_000_000)
    mime: str = "audio/webm"
    duracao_s: float | None = None


def _tratar(fn, *a):
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/health")
def health():
    return {"ok": True, "llm_mode": llm_client.mode(), "llm_configurado": llm_client.configured(),
            "modelos": llm_client.modelos_atuais()}


@app.get("/api/treino/personas")
def treino_personas():
    return training.personas()


@app.post("/api/treino", status_code=201)
def treino_novo(body: NovoTreino):
    return _tratar(training.iniciar, body.vendedor, body.cliente_id, body.modo, body.dificuldade, body.frente, body.coach)


@app.get("/api/treino/historico")
def treino_historico(vendedor: str | None = None):
    return training.historico(vendedor)


@app.get("/api/treino/trilha")
def treino_trilha(vendedor: str | None = None):
    """A trilha (competências × 15 prompts × cenários) e, se vier o vendedor, o nível dele em cada competência."""
    out = trilha.mapa()
    if vendedor:
        out["progresso"] = _tratar(trilha.progresso, vendedor)
    return out


@app.get("/api/treino/{tid}")
def treino_obter(tid: str):
    return _tratar(training.obter, tid)


@app.post("/api/treino/{tid}/mensagem")
def treino_mensagem(tid: str, body: Mensagem):
    return _tratar(training.mensagem, tid, body.conteudo)


@app.post("/api/treino/{tid}/audio")
def treino_audio(tid: str, body: Audio):
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


@app.post("/api/treino/{tid}/coach")
def treino_coach(tid: str, body: Coach):
    return _tratar(training.definir_coach, tid, body.ligado)


@app.post("/api/treino/{tid}/encerrar")
def treino_encerrar(tid: str):
    return _tratar(training.encerrar, tid)


# ------------------------------------------------------------------ backup do banco do Treino (treinos e notas)
@app.get("/api/backup/banco")
def backup_banco():
    pasta = Path(tempfile.mkdtemp(prefix="treino_backup_"))
    arq = db.copiar(pasta / "treino.db")
    return FileResponse(arq, media_type="application/octet-stream", filename=f"treino_{datetime.now():%Y-%m-%d_%H%M}.db",
                        background=BackgroundTask(lambda: shutil.rmtree(pasta, ignore_errors=True)))


@app.get("/")
def pagina_treino():
    return FileResponse(BASE / "frontend" / "treino.html")


app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")
