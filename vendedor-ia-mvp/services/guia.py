"""Guia dentro da ferramenta: glossário, roadmap (com progresso editável) e "Como utilizar" (o Roteiro de Testes).

O conteúdo vem de arquivos legíveis, editáveis à mão:
  guia/glossario.json          termos por categoria
  guia/roadmap.json            fases e itens (a definição, versionada no Git)
  guia/roadmap_progresso.json  status, notas e itens próprios (o avanço de quem usa; fica fora do Git)
  ROTEIRO_DE_TESTES.md         vira a aba "Como utilizar", sem cópia
  LABORATORIO.md               vira a aba "Laboratório" (como usar e o que fazer quando der errado)
O progresso é separado da definição de propósito: atualizar o roadmap no Git não apaga o avanço já registrado.
"""
import json
import os
import re
import threading
import unicodedata
import uuid
from datetime import datetime
from html import escape
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
GUIA_DIR = BASE / "guia"
ROTEIRO = BASE / "ROTEIRO_DE_TESTES.md"
LABORATORIO = BASE / "LABORATORIO.md"

STATUS = {"nao_iniciado": "Não iniciado", "em_andamento": "Em andamento", "concluido": "Concluído", "bloqueado": "Bloqueado"}
_lock = threading.Lock()


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _progresso_path() -> Path:
    return Path(os.getenv("MVP_ROADMAP_PROGRESS", GUIA_DIR / "roadmap_progresso.json"))


def _ler_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ glossário
def glossario() -> dict:
    g = _ler_json(GUIA_DIR / "glossario.json")
    g["total_termos"] = sum(len(c["termos"]) for c in g["categorias"])
    return g


# ------------------------------------------------------------------ roadmap
def _progresso() -> dict:
    path = _progresso_path()
    vazio = {"itens": {}, "custom": []}
    if not path.exists():
        return vazio
    try:
        dados = _ler_json(path)
    except (OSError, ValueError):
        # nunca sobrescrever um arquivo ilegível: guarda uma cópia e começa de novo
        path.replace(path.with_name(f"{path.stem}.corrompido-{datetime.now():%Y%m%d%H%M%S}{path.suffix}"))
        return vazio
    dados.setdefault("itens", {})
    dados.setdefault("custom", [])
    return dados


def _salvar(dados: dict) -> None:
    path = _progresso_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # gravação atômica: queda no meio não deixa o arquivo pela metade


def _definicao() -> dict:
    return _ler_json(GUIA_DIR / "roadmap.json")


def _item(base: dict, prog: dict, custom: bool) -> dict:
    p = prog["itens"].get(base["id"], {})
    status = p.get("status") or base.get("status_inicial") or "nao_iniciado"
    return {"id": base["id"], "titulo": base["titulo"], "trilha": base.get("trilha", ""), "prazo": base.get("prazo", ""),
            "descricao": base.get("descricao", ""), "fonte": base.get("fonte", ""), "marco": bool(base.get("marco")),
            "custom": custom, "status": status, "atualizado_em": p.get("atualizado_em"), "concluido_em": p.get("concluido_em"),
            "notas": p.get("notas", [])}


def _resumo(itens: list[dict]) -> dict:
    r = {k: sum(1 for i in itens if i["status"] == k) for k in STATUS}
    r["total"] = len(itens)
    r["falta"] = r["total"] - r["concluido"]
    r["pct"] = round(100 * r["concluido"] / r["total"]) if r["total"] else 0
    return r


def roadmap() -> dict:
    with _lock:
        d, prog = _definicao(), _progresso()
    fases, todos = [], []
    for f in d["fases"]:
        itens = [_item(i, prog, False) for i in f["itens"]]
        itens += [_item(c, prog, True) for c in prog["custom"] if c["fase_id"] == f["id"]]
        todos += itens
        fases.append({"id": f["id"], "titulo": f["titulo"], "periodo": f.get("periodo", ""), "descricao": f.get("descricao", ""),
                      "itens": itens, "resumo": _resumo(itens)})
    return {"versao": d.get("versao"), "origem": d.get("origem", ""), "status": STATUS, "fases": fases, "resumo": _resumo(todos)}


def _ids_validos(d: dict, prog: dict) -> dict[str, bool]:
    """id -> é um item próprio (custom)?"""
    ids = {i["id"]: False for f in d["fases"] for i in f["itens"]}
    ids.update({c["id"]: True for c in prog["custom"]})
    return ids


def _achar(item_id: str, d: dict, prog: dict) -> bool:
    ids = _ids_validos(d, prog)
    if item_id not in ids:
        raise LookupError("Item do roadmap inexistente")
    return ids[item_id]


def definir_status(item_id: str, status: str) -> dict:
    if status not in STATUS:
        raise ValueError(f"Status inválido. Use um de: {', '.join(STATUS)}")
    with _lock:
        d, prog = _definicao(), _progresso()
        _achar(item_id, d, prog)
        p = prog["itens"].setdefault(item_id, {})
        agora = _agora()
        if p.get("status", None) != status:
            p["atualizado_em"] = agora
        p["status"] = status
        p["concluido_em"] = (p.get("concluido_em") or agora) if status == "concluido" else None
        _salvar(prog)
    return roadmap()


def anotar(item_id: str, texto: str) -> dict:
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("A nota está vazia")
    with _lock:
        d, prog = _definicao(), _progresso()
        _achar(item_id, d, prog)
        p = prog["itens"].setdefault(item_id, {})
        p.setdefault("notas", []).append({"id": uuid.uuid4().hex[:8], "em": _agora(), "texto": texto})
        p["atualizado_em"] = _agora()
        _salvar(prog)
    return roadmap()


def remover_nota(item_id: str, nota_id: str) -> dict:
    with _lock:
        d, prog = _definicao(), _progresso()
        _achar(item_id, d, prog)
        notas = prog["itens"].get(item_id, {}).get("notas", [])
        if not any(n["id"] == nota_id for n in notas):
            raise LookupError("Nota inexistente")
        prog["itens"][item_id]["notas"] = [n for n in notas if n["id"] != nota_id]
        _salvar(prog)
    return roadmap()


def adicionar_item(fase_id: str, titulo: str, descricao: str = "") -> dict:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("O título está vazio")
    with _lock:
        d, prog = _definicao(), _progresso()
        if fase_id not in {f["id"] for f in d["fases"]}:
            raise LookupError("Fase do roadmap inexistente")
        usados = {c["id"] for c in prog["custom"]}
        n = 1
        while f"{fase_id}-U{n}" in usados:
            n += 1
        prog["custom"].append({"id": f"{fase_id}-U{n}", "fase_id": fase_id, "titulo": titulo, "descricao": (descricao or "").strip(),
                               "trilha": "Meu item", "fonte": "Adicionado na ferramenta", "criado_em": _agora()})
        _salvar(prog)
    return roadmap()


def remover_item(item_id: str) -> dict:
    with _lock:
        d, prog = _definicao(), _progresso()
        if not _achar(item_id, d, prog):
            raise ValueError("Só itens adicionados por você podem ser removidos; para os demais, use o status")
        prog["custom"] = [c for c in prog["custom"] if c["id"] != item_id]
        prog["itens"].pop(item_id, None)
        _salvar(prog)
    return roadmap()


# ------------------------------------------------------------------ "Como utilizar": Markdown -> HTML
_BLOCO_LISTA = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
_SEPARADOR_TABELA = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _inline(texto: str) -> str:
    """Escapa o HTML e aplica **negrito** e `código`. O código sai do texto antes (vira marcador) para não receber
    negrito por dentro, mas o negrito pode envolver um trecho de código: **arquivo `.txt`**."""
    codigos: list[str] = []

    def guardar(m):
        codigos.append(f"<code>{escape(m.group(1))}</code>")
        return f"\x00{len(codigos) - 1}\x00"

    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(re.sub(r"`([^`]+)`", guardar, texto.replace("\x00", ""))))
    return re.sub(r"\x00(\d+)\x00", lambda m: codigos[int(m.group(1))], html)


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _lista(itens: list[tuple[int, str, str]]) -> str:
    out, pilha = [], []  # pilha de (indentação, tag)
    for indent, tag, texto in itens:
        while pilha and indent < pilha[-1][0]:
            out.append(f"</li></{pilha.pop()[1]}>")
        if pilha and indent == pilha[-1][0]:
            if pilha[-1][1] == tag:
                out.append("</li>")
            else:
                out.append(f"</li></{pilha.pop()[1]}>")
                pilha.append((indent, tag))
                out.append(f"<{tag}>")
        else:
            pilha.append((indent, tag))
            out.append(f"<{tag}>")
        out.append(f"<li>{_inline(texto)}")
    while pilha:
        out.append(f"</li></{pilha.pop()[1]}>")
    return "".join(out)


def _slug(texto: str, usados: set) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-") or "secao"
    slug, n = base, 2
    while slug in usados:
        slug, n = f"{base}-{n}", n + 1
    usados.add(slug)
    return slug


def md_para_html(md: str) -> dict:
    """Conversor mínimo (títulos, tabelas, listas com aninhamento, citações, código, negrito) sem dependências.
    Todo texto é escapado. Devolve {'html', 'toc'} com os títulos de nível 2 para o índice lateral."""
    linhas, out, toc, slugs = md.replace("\r\n", "\n").split("\n"), [], [], set()
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("```"):
            i += 1
            bloco = []
            while i < len(linhas) and not linhas[i].startswith("```"):
                bloco.append(linhas[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{escape(chr(10).join(bloco))}</code></pre>")
        elif m := re.match(r"^(#{1,4})\s+(.*)$", ln):
            nivel, texto = len(m.group(1)), m.group(2).strip()
            sid = _slug(texto, slugs)
            if nivel == 2:
                toc.append({"id": sid, "titulo": re.sub(r"[`*]", "", texto)})
            out.append(f'<h{nivel} id="{sid}">{_inline(texto)}</h{nivel}>')
            i += 1
        elif re.match(r"^\s*-{3,}\s*$", ln):
            out.append("<hr>")
            i += 1
        elif ln.startswith(">"):
            citacao = []
            while i < len(linhas) and linhas[i].startswith(">"):
                citacao.append(_inline(linhas[i][1:].strip()))
                i += 1
            out.append("<blockquote>" + "<br>".join(citacao) + "</blockquote>")
        elif ln.lstrip().startswith("|") and i + 1 < len(linhas) and _SEPARADOR_TABELA.match(linhas[i + 1]):
            cab = _celulas(ln)
            i += 2
            corpo = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                corpo.append(_celulas(linhas[i]))
                i += 1
            out.append('<div class="tabela"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in cab) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in corpo) + "</tbody></table></div>")
        elif _BLOCO_LISTA.match(ln):
            itens = []
            while i < len(linhas):
                m = _BLOCO_LISTA.match(linhas[i])
                if m:
                    itens.append((len(m.group(1).expandtabs(4)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)))
                    i += 1
                elif itens and linhas[i].strip() and linhas[i].startswith(" "):  # continuação do item anterior
                    indent, tag, texto = itens[-1]
                    itens[-1] = (indent, tag, f"{texto} {linhas[i].strip()}")
                    i += 1
                else:
                    break
            out.append(_lista(itens))
        else:
            par = []
            while i < len(linhas) and linhas[i].strip() and not re.match(r"^(#{1,4}\s|>|```|\s*-{3,}\s*$)", linhas[i]) \
                    and not _BLOCO_LISTA.match(linhas[i]) and not linhas[i].lstrip().startswith("|"):
                par.append(linhas[i].strip())
                i += 1
            if not par:  # linha que nenhuma regra reconheceu: não pode travar o laço
                par, i = [linhas[i].strip()], i + 1
            out.append(f"<p>{_inline(' '.join(par))}</p>")
    return {"html": "\n".join(out), "toc": toc}


def _documento(arquivo: Path) -> dict:
    """Lido do arquivo a cada pedido, sem duplicar o texto: editou o .md, a aba muda."""
    if not arquivo.exists():
        raise LookupError(f"{arquivo.name} não encontrado")
    r = md_para_html(arquivo.read_text(encoding="utf-8"))
    r["atualizado_em"] = datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    r["arquivo"] = arquivo.name
    return r


def como_utilizar() -> dict:
    """A aba 'Como utilizar' é o próprio Roteiro de Testes."""
    return _documento(ROTEIRO)


def laboratorio() -> dict:
    """A aba 'Laboratório' do Guia: o LABORATORIO.md."""
    return _documento(LABORATORIO)
