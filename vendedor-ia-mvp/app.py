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
from services import catalog, conversations as conv, evaluation, guia, laboratorio, llm_client, training

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def _lifespan(_app):
    seed.ensure()
    laboratorio.recuperar_interrompidas()
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


class StatusItem(BaseModel):
    status: str


class NotaItem(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)


class NovaRodada(BaseModel):
    preset: str | None = None
    personas: list[str] = []
    comportamentos: list[str] = []
    modos: list[str] = []
    repeticoes: int = Field(1, ge=1, le=10)
    max_turnos: int = Field(12, ge=2, le=40)
    dificuldade: str = Field("medio", pattern="^(facil|medio|dificil)$")
    avaliar_ia: bool = True
    nome: str | None = Field(None, max_length=120)
    workers: int = Field(2, ge=1, le=4)


class NovoItem(BaseModel):
    fase_id: str
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str = Field("", max_length=1000)


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


# ------------------------------------------------------------------ LABORATÓRIO (IA-cliente x Fernanda, testes em lote)
@app.get("/api/lab/catalogo")
def lab_catalogo():
    return laboratorio.catalogo()


@app.post("/api/lab/estimar")
def lab_estimar(body: NovaRodada):
    def calc():
        if body.preset:
            if body.preset not in laboratorio.PRESETS:
                raise ValueError("Preset inexistente")
            itens = laboratorio.PRESETS[body.preset][1]()
        else:
            itens = laboratorio._itens([p for p in body.personas if p in laboratorio.PERSONAS],
                                       [c for c in body.comportamentos if c in laboratorio.COMPORTAMENTOS],
                                       [m for m in body.modos if m in ("A", "B")], body.repeticoes, body.max_turnos)
        return laboratorio.estimar(itens, body.workers, body.avaliar_ia)
    return _tratar(calc)


@app.post("/api/lab/rodadas", status_code=201)
def lab_criar(body: NovaRodada):
    return _tratar(lambda: laboratorio.criar_rodada(**body.model_dump()))


@app.get("/api/lab/rodadas")
def lab_listar():
    return laboratorio.listar_rodadas()


@app.get("/api/lab/rodadas/{rid}")
def lab_obter(rid: str):
    return _tratar(laboratorio.obter_rodada, rid)


@app.post("/api/lab/rodadas/{rid}/cancelar")
def lab_cancelar(rid: str):
    return _tratar(laboratorio.cancelar, rid)


@app.post("/api/lab/rodadas/{rid}/retomar")
def lab_retomar(rid: str):
    def ret():
        laboratorio.obter_rodada(rid)
        laboratorio.executar_rodada(rid)
        return laboratorio.obter_rodada(rid)
    return _tratar(ret)


@app.get("/api/lab/rodadas/{rid}/export.csv")
def lab_csv(rid: str):
    dados = _tratar(laboratorio.exportar_csv, rid)
    return Response(dados, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="laboratorio_{rid}.csv"'})


@app.get("/api/lab/execucoes/{exec_id}")
def lab_execucao(exec_id: str):
    return _tratar(laboratorio.obter_execucao, exec_id)


# ------------------------------------------------------------------ GUIA (glossário, roadmap com progresso, como utilizar)
@app.get("/api/guia/glossario")
def guia_glossario():
    return guia.glossario()


@app.get("/api/guia/como-utilizar")
def guia_como_utilizar():
    return _tratar(guia.como_utilizar)


@app.get("/api/guia/laboratorio")
def guia_laboratorio():
    return _tratar(guia.laboratorio)


@app.get("/api/roadmap")
def roadmap():
    return guia.roadmap()


@app.post("/api/roadmap/itens", status_code=201)
def roadmap_novo_item(body: NovoItem):
    return _tratar(guia.adicionar_item, body.fase_id, body.titulo, body.descricao)


@app.delete("/api/roadmap/itens/{item_id}")
def roadmap_remover_item(item_id: str):
    return _tratar(guia.remover_item, item_id)


@app.post("/api/roadmap/{item_id}/status")
def roadmap_status(item_id: str, body: StatusItem):
    return _tratar(guia.definir_status, item_id, body.status)


@app.post("/api/roadmap/{item_id}/notas", status_code=201)
def roadmap_nota(item_id: str, body: NotaItem):
    return _tratar(guia.anotar, item_id, body.texto)


@app.delete("/api/roadmap/{item_id}/notas/{nota_id}")
def roadmap_remover_nota(item_id: str, nota_id: str):
    return _tratar(guia.remover_nota, item_id, nota_id)


app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")


@app.get("/")
def index():
    return FileResponse(BASE / "frontend" / "index.html")


@app.get("/treino")
def pagina_treino():
    return FileResponse(BASE / "frontend" / "treino.html")


@app.get("/guia")
def pagina_guia():
    return FileResponse(BASE / "frontend" / "guia.html")


@app.get("/laboratorio")
def pagina_laboratorio():
    return FileResponse(BASE / "frontend" / "laboratorio.html")
