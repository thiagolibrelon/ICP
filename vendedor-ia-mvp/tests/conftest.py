import json
import os
import sys
from pathlib import Path

os.environ["LLM_MODE"] = "mock"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from database import db, seed  # noqa: E402
from services import agent, conversations, llm_client  # noqa: E402


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    for var in ("API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_AUTH_HEADER", "LLM_TOOLS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(conversations, "LOG_FILE", tmp_path / "conversations.jsonl")
    monkeypatch.setenv("MVP_ROADMAP_PROGRESS", str(tmp_path / "roadmap_progresso.json"))  # nunca toca o progresso real
    monkeypatch.setitem(agent._modo_ferramentas, "atual", "auto")
    path = tmp_path / "test.db"
    db.set_db_path(path)
    seed.load(path)
    yield


def tool_call(nome, args, i=0):
    return {"id": f"call_{nome}_{i}", "type": "function", "function": {"name": nome, "arguments": json.dumps(args)}}


class GPTRoteirizado:
    """Substitui llm_client.completar: devolve as mensagens na ordem e guarda o que recebeu."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.recebidos = []

    def __call__(self, messages, max_tokens=1500, retries=2, json_mode=False, tools=None):
        self.recebidos.append({"messages": messages, "json_mode": json_mode, "tools": tools})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        msg = {"role": "assistant", "content": r} if isinstance(r, str) else r
        return {"message": msg, "finish_reason": "stop", "tokens_entrada": 100, "tokens_saida": 20, "tokens_cache": 0, "custo_gate": 0.0001}


@pytest.fixture
def gpt(monkeypatch):
    def instalar(*respostas):
        g = GPTRoteirizado(*respostas)
        monkeypatch.setattr(llm_client, "completar", g)
        return g
    return instalar
