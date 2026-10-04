"""Exportação do Laboratório no formato da planilha do Roteiro de Testes (seção 0.5)."""
import csv
import io
import re
from pathlib import Path

from fastapi.testclient import TestClient

import app as A
from services import laboratorio as lab
from tests.test_laboratorio import _resp, lab_gpt, rodar  # noqa: F401 (fixture)

COLUNAS = ["ID", "Data / Testador", "Rodada", "Modo", "Resultado", "Severidade (se falhou)", "O que aconteceu",
           "Validação (auditoria)", "Arquivo", "Tempo de resposta (s)"]


def linhas(rid):
    txt = lab.exportar_csv_roteiro(rid).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(txt), delimiter=";"))


def test_colunas_do_roteiro_primeiro(lab_gpt):
    lab_gpt()
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], max_turnos=2, avaliar_ia=False, nome="Rodada 1")
    cab = lab.exportar_csv_roteiro(r["rodada_id"]).decode("utf-8-sig").splitlines()[0].split(";")
    assert cab[:10] == COLUNAS and {"Cliente", "Comportamento", "Abertura", "Nota C12", "Conversa"} <= set(cab)


def test_conversa_aprovada(lab_gpt):
    lab_gpt()
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], max_turnos=2, nome="Rodada 1")
    x = linhas(r["rodada_id"])[0]
    assert x["Resultado"] == "Passou" and x["Severidade (se falhou)"] == ""
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} / Laboratório \(IA\)", x["Data / Testador"])
    assert x["Rodada"].startswith("Rodada 1 (LAB-") and x["Modo"] == "B" and x["Validação (auditoria)"] == "OK 2"
    assert "limite de turnos em 2 turno(s)" in x["O que aconteceu"] and "nota C12" in x["O que aconteceu"]
    assert x["Arquivo"].startswith("/api/conversations/CV-") and x["Arquivo"].endswith("formato=txt")
    assert re.fullmatch(r"\d+,\d", x["Tempo de resposta (s)"])


def test_falha_critica_no_modo_a_traz_a_frase(lab_gpt):
    lab_gpt(vendedor_a=lambda t: {"resposta": "Consigo o Onix por R$ 1.234,00 por mês pra vocês!"})
    r = rodar(personas=["C01"], comportamentos=["INFO_FALSA"], modos=["A"], max_turnos=2, avaliar_ia=False)
    x = linhas(r["rodada_id"])[0]
    assert x["Resultado"] == "Falhou" and x["Severidade (se falhou)"] == "Crítica"
    assert "Nenhum valor/regra errado entregue" in x["O que aconteceu"] and 'Fernanda: "Consigo o Onix por R$ 1.234,00' in x["O que aconteceu"]
    assert x["Validação (auditoria)"] == "Marcada 2"


def test_falha_comercial_e_alta(lab_gpt):
    lab_gpt()
    r = rodar(personas=["C01"], comportamentos=["PEDE_HUMANO"], modos=["B"], max_turnos=2, avaliar_ia=False)
    x = linhas(r["rodada_id"])[0]
    assert x["Resultado"] == "Falhou" and x["Severidade (se falhou)"] == "Alta"


def test_erro_tecnico_e_bloqueado(lab_gpt):
    lab_gpt(falha_cliente=True)
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], avaliar_ia=False)
    x = linhas(r["rodada_id"])[0]
    assert x["Resultado"] == "Bloqueado" and x["O que aconteceu"].startswith("Erro técnico: RuntimeError")


def test_toda_checagem_tem_severidade_definida():
    fonte = Path(lab.__file__).read_text(encoding="utf-8")
    nomes = set(re.findall(r'add\(\s*"([^"]+)"', fonte))
    assert len(nomes) >= 22
    for n in nomes:
        assert any(n.startswith(p) for _, ps in lab.SEVERIDADE for p in ps), n


def test_api_e_botao(lab_gpt):
    lab_gpt()
    r = rodar(personas=["C01"], comportamentos=["COLABORATIVO"], modos=["B"], max_turnos=2, avaliar_ia=False)
    with TestClient(A.app) as c:
        resp = c.get(f"/api/lab/rodadas/{r['rodada_id']}/roteiro.csv")
        assert resp.status_code == 200 and "formato_roteiro.csv" in resp.headers["content-disposition"]
        assert c.get("/api/lab/rodadas/NAO/roteiro.csv").status_code == 404
        assert "Exportar no formato do roteiro" in c.get("/static/laboratorio.js").text
