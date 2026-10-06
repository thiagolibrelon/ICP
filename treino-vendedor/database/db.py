import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_db_path = Path(os.getenv("TREINO_DB_PATH", BASE_DIR / "database" / "treino.db"))


def set_db_path(path) -> None:
    global _db_path
    _db_path = Path(path)


def get_db_path() -> Path:
    return _db_path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all(sql: str, params=()) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fetch_one(sql: str, params=()) -> dict | None:
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params=()) -> None:
    conn = connect()
    try:
        with conn:
            conn.execute(sql, params)
    finally:
        conn.close()


def copiar(destino) -> Path:
    """Cópia consistente do banco (API de backup do SQLite: funciona com o servidor rodando)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(_db_path, timeout=30), sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return destino

