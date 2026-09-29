import os
import sys
from pathlib import Path

os.environ["LLM_MODE"] = "mock"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from database import db, seed  # noqa: E402
from services import conversation_service  # noqa: E402


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setattr(conversation_service, "LOG_FILE", tmp_path / "conversations.jsonl")
    path = tmp_path / "test.db"
    db.set_db_path(path)
    seed.load(path)
    yield
