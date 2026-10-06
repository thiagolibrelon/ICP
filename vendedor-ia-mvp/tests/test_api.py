import csv
import io

from fastapi.testclient import TestClient

import app as A


def test_fluxo_http_offline():
    with TestClient(A.app) as c:
        assert len(c.get("/api/clientes").json()) == 30
        assert len(c.get("/api/roteiros").json()) == 35  # 30 clientes + 5 genéricos
        conv = c.post("/api/conversations", json={"cliente_id": "C01", "modo": "B"}).json()
        assert conv["mensagens"] == [] and conv["roteiro"]["roteiro_id"] == "R_C01"      # receptivo: começa vazio
        r = c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"conteudo": "Oi"}).json()
        assert r["mensagens"][-1]["auditoria"]["resultado_validacao"] == "contingencia"  # sem GPT (mock)
        assert c.post(f"/api/conversations/{conv['conversation_id']}/close").json()["status"] == "ENCERRADA"
        assert c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"conteudo": "Oi"}).status_code == 400
        assert c.post("/api/conversations", json={"cliente_id": "C99"}).status_code == 404
        assert c.post("/api/estoque/reiniciar").status_code == 200
        assert "A_llm_pura" in c.get("/api/comparativo").json()


def test_export_no_formato_do_classificador():
    with TestClient(A.app) as c:
        conv = c.post("/api/conversations", json={"cliente_id": "C01", "modo": "A"}).json()
        c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"conteudo": "Quero 3 Onix"})
        linhas = list(csv.DictReader(io.StringIO(c.get("/api/export/classificador.csv").content.decode("utf-8-sig")), delimiter=";"))
    assert {"cd_segmento", "transcricao_limpa", "status_transcricao", "modo"} <= set(linhas[0])
    assert linhas[0]["transcricao_limpa"].startswith("CLIENTE: Quero 3 Onix | AGENTE: ")
