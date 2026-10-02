import json
import re

import pytest
from fastapi.testclient import TestClient

import app as A
from services import guia


# ------------------------------------------------------------------ conteúdo (arquivos editáveis à mão)
def test_glossario_sem_termos_repetidos_nem_vazios():
    g = guia.glossario()
    termos = [t for c in g["categorias"] for t in c["termos"]]
    assert g["total_termos"] == len(termos) >= 80
    assert all(t["termo"].strip() and len(t["definicao"]) > 20 for t in termos)
    nomes = [t["termo"].lower() for t in termos]
    assert len(nomes) == len(set(nomes))
    assert len({c["id"] for c in g["categorias"]}) == len(g["categorias"])


def test_glossario_cobre_os_termos_que_o_responsavel_mais_pergunta():
    texto = json.dumps(guia.glossario(), ensure_ascii=False)
    for termo in ("ICP", "Alçada", "Contrapartida", "Handoff", "Tier A", "Modo A", "Modo B", "Régua C12",
                  "Gate 1", "Challenger", "Red team", "Playbook", "Executor em lote"):
        assert termo in texto, termo


def test_roadmap_definicao_integra():
    d = json.loads((guia.GUIA_DIR / "roadmap.json").read_text(encoding="utf-8"))
    ids = [i["id"] for f in d["fases"] for i in f["itens"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 55
    assert len({f["id"] for f in d["fases"]}) == len(d["fases"])
    for f in d["fases"]:
        assert f["itens"], f["id"]
        for i in f["itens"]:
            assert i["id"].startswith(f["id"] + "-") and i["titulo"].strip() and i.get("fonte")
            assert i.get("status_inicial", "nao_iniciado") in guia.STATUS
    # os seis sprints do Q4 e a decisão de 19/12 estão lá
    assert {"S1", "S2", "S3", "S4", "S5", "S6"} <= {f["id"] for f in d["fases"]}
    assert any(i["id"] == "S6-03" and i["marco"] for f in d["fases"] for i in f["itens"])


def test_roadmap_inicial():
    r = guia.roadmap()
    assert r["resumo"]["total"] == sum(len(f["itens"]) for f in r["fases"])
    con = next(f for f in r["fases"] if f["id"] == "CON")
    assert con["resumo"]["pct"] == 100          # o que já foi construído nasce concluído
    s1 = next(f for f in r["fases"] if f["id"] == "S1")
    # S1-01 (executor em lote = Laboratório) já foi entregue; o restante do sprint nasce não iniciado
    assert s1["resumo"]["concluido"] == 1 and _item(r, "S1-01")["status"] == "concluido"
    assert all(i["status"] == "nao_iniciado" for i in s1["itens"] if i["id"] != "S1-01")
    assert r["resumo"]["falta"] == r["resumo"]["total"] - r["resumo"]["concluido"]


# ------------------------------------------------------------------ progresso
def _item(r, item_id):
    return next(i for f in r["fases"] for i in f["itens"] if i["id"] == item_id)


def test_status_persiste_e_calcula_resumo(tmp_path):
    r = guia.definir_status("S1-01", "em_andamento")
    assert _item(r, "S1-01")["status"] == "em_andamento" and r["resumo"]["em_andamento"] == 1
    r = guia.definir_status("S1-01", "concluido")
    i = _item(r, "S1-01")
    assert i["status"] == "concluido" and i["concluido_em"] and r["fases"][1]["resumo"]["concluido"] == 1
    # persistiu em disco, lido de novo sem estado em memória
    assert json.loads((tmp_path / "roadmap_progresso.json").read_text(encoding="utf-8"))["itens"]["S1-01"]["status"] == "concluido"
    assert _item(guia.roadmap(), "S1-01")["status"] == "concluido"
    # reabrir limpa a data de conclusão
    assert _item(guia.definir_status("S1-01", "bloqueado"), "S1-01")["concluido_em"] is None


def test_status_invalido_e_item_inexistente():
    with pytest.raises(ValueError):
        guia.definir_status("S1-01", "feito")
    with pytest.raises(LookupError):
        guia.definir_status("XX-99", "concluido")
    with pytest.raises(LookupError):
        guia.anotar("XX-99", "oi")


def test_notas_com_data_e_remocao():
    r = guia.anotar("PED-04", "  Abri o chamado na Privacidade  ")
    n = _item(r, "PED-04")["notas"]
    assert len(n) == 1 and n[0]["texto"] == "Abri o chamado na Privacidade" and n[0]["em"]
    with pytest.raises(ValueError):
        guia.anotar("PED-04", "   ")
    r = guia.remover_nota("PED-04", n[0]["id"])
    assert _item(r, "PED-04")["notas"] == []
    with pytest.raises(LookupError):
        guia.remover_nota("PED-04", "naoexiste")


def test_itens_proprios_so_os_proprios_podem_ser_removidos():
    r = guia.adicionar_item("EVO", " Conversar com o time do llm-gate ", "marcar reunião")
    novo = next(i for i in next(f for f in r["fases"] if f["id"] == "EVO")["itens"] if i["custom"])
    assert novo["id"] == "EVO-U1" and novo["titulo"] == "Conversar com o time do llm-gate" and novo["status"] == "nao_iniciado"
    assert guia.adicionar_item("EVO", "Outro")["resumo"]["total"] == r["resumo"]["total"] + 1
    guia.definir_status("EVO-U1", "em_andamento")
    guia.anotar("EVO-U1", "ligar amanhã")
    r = guia.remover_item("EVO-U1")
    assert not any(i["id"] == "EVO-U1" for f in r["fases"] for i in f["itens"])
    with pytest.raises(ValueError):                       # item da definição não se remove
        guia.remover_item("S1-01")
    with pytest.raises(LookupError):
        guia.adicionar_item("ZZ", "x")
    with pytest.raises(ValueError):
        guia.adicionar_item("EVO", "  ")
    assert guia.adicionar_item("EVO", "De novo")["fases"]  # id liberado é reaproveitado sem colidir
    ids = [i["id"] for f in guia.roadmap()["fases"] for i in f["itens"]]
    assert len(ids) == len(set(ids))


def test_progresso_corrompido_e_preservado_e_nao_derruba(tmp_path):
    arq = tmp_path / "roadmap_progresso.json"
    arq.write_text("{isso nao e json", encoding="utf-8")
    r = guia.definir_status("S1-01", "em_andamento")
    assert _item(r, "S1-01")["status"] == "em_andamento"
    copias = list(tmp_path.glob("roadmap_progresso.corrompido-*.json"))
    assert len(copias) == 1 and copias[0].read_text(encoding="utf-8") == "{isso nao e json"


def test_atualizar_a_definicao_nao_apaga_o_avanco(tmp_path, monkeypatch):
    guia.definir_status("S2-01", "em_andamento")
    guia.anotar("S2-01", "primeira conversa rodada")
    original = (guia.GUIA_DIR / "roadmap.json").read_text(encoding="utf-8")
    d = json.loads(original)
    d["fases"][2]["itens"][0]["titulo"] = "Rodada 1 (renomeada no Git)"
    novo = tmp_path / "guia"
    novo.mkdir()
    (novo / "roadmap.json").write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(guia, "GUIA_DIR", novo)
    i = _item(guia.roadmap(), "S2-01")
    assert i["titulo"] == "Rodada 1 (renomeada no Git)" and i["status"] == "em_andamento" and len(i["notas"]) == 1


# ------------------------------------------------------------------ Markdown -> HTML (aba "Como utilizar")
def test_md_escapa_html_e_formata():
    h = guia.md_para_html("# Título <b>\n\nTexto **forte** com `a<b|c` e <script>alert(1)</script>.")["html"]
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "<strong>forte</strong>" in h and "<code>a&lt;b|c</code>" in h and "&lt;b&gt;" in h


def test_md_negrito_pode_envolver_codigo():
    h = guia.md_para_html("**Arquivo `.txt`** exportado, e `**nao**` fica literal")["html"]
    assert "<strong>Arquivo <code>.txt</code></strong> exportado" in h and "<code>**nao**</code>" in h


def test_md_tabela_lista_e_aninhamento():
    md = "| A | B |\n|---|---|\n| 1 | `x` |\n\n1. um\n2. dois\n  continua\n\n- pai\n  - filho **n**\n- irmão\n\n> cita\n> duas linhas\n\n---\n"
    h = guia.md_para_html(md)["html"]
    assert "<th>A</th>" in h and "<td><code>x</code></td>" in h
    assert "<ol><li>um</li><li>dois continua</li></ol>" in h
    assert "<ul><li>pai<ul><li>filho <strong>n</strong></li></ul></li><li>irmão</li></ul>" in h
    assert "<blockquote>cita<br>duas linhas</blockquote>" in h and "<hr>" in h


def test_md_linha_estranha_nao_trava():
    h = guia.md_para_html("| solta sem tabela\n\ntexto")["html"]
    assert "solta sem tabela" in h and "<p>texto</p>" in h


def test_como_utilizar_e_o_roteiro_de_testes():
    r = guia.como_utilizar()
    assert "Roteiro de Testes" in r["html"] and "B05 · Épsilon" in r["html"]
    md = guia.ROTEIRO.read_text(encoding="utf-8").splitlines()
    assert r["html"].count("<table>") == sum(1 for ln in md if re.fullmatch(r"\|[-| :]+\|", ln))   # nenhuma tabela se perdeu
    assert r["html"].count("<tr>") == sum(1 for ln in md if ln.startswith("|") and not re.fullmatch(r"\|[-| :]+\|", ln))
    assert len(r["toc"]) >= 10 and all(re.fullmatch(r"[a-z0-9-]+", t["id"]) for t in r["toc"])
    assert any("Bloco G" in t["titulo"] for t in r["toc"])
    ids = re.findall(r'id="([^"]+)"', r["html"])
    assert len(ids) == len(set(ids))
    assert "|---" not in r["html"] and "**" not in r["html"]  # nada de Markdown cru sobrando


def test_aba_laboratorio_do_guia():
    r = guia.laboratorio()
    assert r["arquivo"] == "LABORATORIO.md" and "é ajuste de prompt" in r["html"]
    md = guia.LABORATORIO.read_text(encoding="utf-8").splitlines()
    assert r["html"].count("<tr>") == sum(1 for ln in md if ln.startswith("|") and not re.fullmatch(r"\|[-| :]+\|", ln))
    assert any("Quando der errado" in t["titulo"] for t in r["toc"])
    assert "|---" not in r["html"] and "**" not in r["html"]
    with TestClient(A.app) as c:
        assert c.get("/api/guia/laboratorio").json()["toc"]
        assert 'id="tab-laboratorio"' in c.get("/guia").text


def test_aba_como_funciona_serve_as_imagens():
    with TestClient(A.app) as c:
        assert 'id="tab-como-funciona"' in c.get("/guia").text
        for arq in ("1_chat_x_fernanda.png", "2_uma_mensagem_por_dentro.png", "3_ferramentas_e_bases.png"):
            r = c.get(f"/como-funciona/{arq}")
            assert r.status_code == 200 and r.headers["content-type"] == "image/png"
            assert arq in c.get("/static/guia.js").text


# ------------------------------------------------------------------ HTTP
def test_api_guia_e_roadmap():
    with TestClient(A.app) as c:
        assert c.get("/guia").status_code == 200 and "Guia da ferramenta" in c.get("/guia").text
        assert c.get("/api/guia/glossario").json()["total_termos"] >= 80
        assert "toc" in c.get("/api/guia/como-utilizar").json()
        assert c.get("/api/roadmap").json()["resumo"]["total"] >= 55
        r = c.post("/api/roadmap/S1-01/status", json={"status": "em_andamento"}).json()
        assert r["resumo"]["em_andamento"] == 1
        assert c.post("/api/roadmap/S1-01/status", json={"status": "xx"}).status_code == 400
        assert c.post("/api/roadmap/NAO-01/status", json={"status": "concluido"}).status_code == 404
        n = c.post("/api/roadmap/S1-01/notas", json={"texto": "reunião marcada"})
        assert n.status_code == 201
        nota = next(i for f in n.json()["fases"] for i in f["itens"] if i["id"] == "S1-01")["notas"][0]
        assert c.delete(f"/api/roadmap/S1-01/notas/{nota['id']}").status_code == 200
        assert c.post("/api/roadmap/S1-01/notas", json={"texto": "   "}).status_code == 400
        assert c.post("/api/roadmap/itens", json={"fase_id": "EVO", "titulo": "Minha ideia"}).status_code == 201
        assert c.delete("/api/roadmap/itens/EVO-U1").status_code == 200
        assert c.delete("/api/roadmap/itens/S1-01").status_code == 400
        assert c.delete("/api/roadmap/itens/EVO-U9").status_code == 404
        assert c.post("/api/roadmap/itens", json={"fase_id": "NAO", "titulo": "x"}).status_code == 404


def test_telas_existentes_linkam_para_o_guia():
    with TestClient(A.app) as c:
        assert 'href="/guia"' in c.get("/").text and 'href="/guia"' in c.get("/treino").text
