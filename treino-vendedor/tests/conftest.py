import json
import os
import sys
from pathlib import Path

os.environ["LLM_MODE"] = "mock"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from database import db, seed  # noqa: E402
from services import llm_client  # noqa: E402


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    for var in ("API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_AUTH_HEADER"):
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "treino.db"
    db.set_db_path(path)
    seed.load(path)
    yield


class GPTRoteirizado:
    """Substitui llm_client.completar: devolve as mensagens na ordem e guarda o que recebeu."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.recebidos = []

    def __call__(self, messages, max_tokens=1500, retries=2, json_mode=False, tools=None):
        self.recebidos.append({"messages": messages, "json_mode": json_mode, "papel": llm_client.papel_atual()})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return {"message": {"role": "assistant", "content": r}, "finish_reason": "stop", "tokens_entrada": 100, "tokens_saida": 20,
                "tokens_cache": 0, "custo_gate": 0.0001}


@pytest.fixture
def gpt(monkeypatch):
    def instalar(*respostas):
        g = GPTRoteirizado(*respostas)
        monkeypatch.setattr(llm_client, "completar", g)
        return g
    return instalar
