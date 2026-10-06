"""Copia os treinos feitos quando o Treino ainda morava no vendedor-ia-mvp (tabelas treinos e treino_mensagens do
mvp.db) para o banco do Treino. Não apaga nada do mvp.db. Treinos que já existem no destino são pulados.

Uso (a partir de treino-vendedor/):  python -m scripts.importar_treinos_do_mvp [caminho do mvp.db]
Padrão: ../vendedor-ia-mvp/database/mvp.db
"""
import sqlite3
import sys
from pathlib import Path

from database import db, seed

BASE = Path(__file__).resolve().parent.parent


def importar(origem: Path) -> dict:
    seed.ensure()
    src = sqlite3.connect(f"file:{origem}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        tem = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "treinos" not in tem:
            return {"treinos": 0, "mensagens": 0, "pulados": 0}
        treinos = [dict(r) for r in src.execute("SELECT * FROM treinos")]
        msgs = [dict(r) for r in src.execute("SELECT * FROM treino_mensagens ORDER BY id")]
    finally:
        src.close()
    existentes = {r["treino_id"] for r in db.fetch_all("SELECT treino_id FROM treinos")}
    novos = [t for t in treinos if t["treino_id"] not in existentes]
    ids = {t["treino_id"] for t in novos}
    conn = db.connect()
    try:
        with conn:
            for t in novos:
                cols = ", ".join(t)
                conn.execute(f"INSERT INTO treinos ({cols}) VALUES ({', '.join('?' * len(t))})", tuple(t.values()))
            for m in msgs:
                if m["treino_id"] in ids:
                    conn.execute("INSERT INTO treino_mensagens (treino_id, timestamp, role, conteudo, meta_json) VALUES (?,?,?,?,?)",
                                 (m["treino_id"], m["timestamp"], m["role"], m["conteudo"], m["meta_json"]))
    finally:
        conn.close()
    return {"treinos": len(novos), "mensagens": sum(1 for m in msgs if m["treino_id"] in ids), "pulados": len(treinos) - len(novos)}


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE.parent / "vendedor-ia-mvp" / "database" / "mvp.db"
    if not origem.exists():
        sys.exit(f"Não achei {origem}")
    print(importar(origem))
