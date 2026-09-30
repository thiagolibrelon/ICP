"""MODO TREINO: o vendedor humano vende, o GPT interpreta o cliente (persona com segredos e objeções) e, no fim,
um avaliador aplica a régua C12 e devolve nota + justificativa + onde melhorar.

- Modo PROVA: sem dicas; nota no fim.  Modo TREINO: dica do coach a cada troca; nota no fim.
- Partes determinísticas da nota: segredos descobertos (diagnóstico) e disciplina de margem (ferramentas).
- Âncoras do avaliador são conferidas contra as falas do vendedor (mesma técnica do classificador de ligações).
"""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from database import db
from database.personas import DIFICULDADES, PERSONAS
from services import agent, catalog, llm_client, validator
from services.catalog import ErroFerramenta
from services.util import palavras

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
P_CLIENTE = (PROMPTS / "cliente_treino.md").read_text(encoding="utf-8")
P_COACH = (PROMPTS / "coach_treino.md").read_text(encoding="utf-8")
P_AVALIADOR = (PROMPTS / "avaliador_treino.md").read_text(encoding="utf-8")

PESOS = {"diagnostico": 2.0, "challenger": 2.0, "objecoes": 2.0, "disciplina_margem": 1.5, "fechamento": 1.5,
         "qualificacao": 1.0, "tom": 1.0, "adicionais": 0.5}
NOMES = {"diagnostico": "Diagnóstico", "challenger": "Challenger com dado", "objecoes": "Tratamento de objeções",
         "disciplina_margem": "Disciplina de margem", "fechamento": "Fechamento e próximo passo", "qualificacao": "Qualificação",
         "tom": "Tom e empatia", "adicionais": "Adicionais"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(tid: str, role: str, conteudo: str, meta: dict | None = None) -> None:
    db.execute("INSERT INTO treino_mensagens (treino_id, timestamp, role, conteudo, meta_json) VALUES (?,?,?,?,?)",
               (tid, _now(), role, conteudo, json.dumps(meta or {}, ensure_ascii=False, default=str)))


def _row(tid: str) -> dict:
    r = db.fetch_one("SELECT * FROM treinos WHERE treino_id=?", (tid,))
    if not r:
        raise LookupError("Treino inexistente")
    return r


def _salvar(tid: str, estado: dict, **campos) -> None:
    sets = ", ".join(["estado_json=?"] + [f"{k}=?" for k in campos])
    db.execute(f"UPDATE treinos SET {sets} WHERE treino_id=?", (json.dumps(estado, default=str), *campos.values(), tid))


def personas() -> list[dict]:
    out = []
    for cid, p in PERSONAS.items():
        c = catalog.consultar_cliente(cid)
        out.append({"cliente_id": cid, "razao_social": c["razao_social"], "contato": p["contato"], "cargo": p["cargo"],
                    "icp": c["icp"], "tier": c["tier"], "segredos": len(p["segredos"]), "objecoes": len(p["objecoes"])})
    return out


# ------------------------------------------------------------------ ciclo do treino
def iniciar(vendedor: str, cliente_id: str, modo: str = "TREINO", dificuldade: str = "medio") -> dict:
    vendedor = (vendedor or "").strip()
    if not vendedor:
        raise ValueError("Informe o nome do vendedor")
    if cliente_id not in PERSONAS:
        raise LookupError("Cliente sem persona de treino")
    if modo not in ("PROVA", "TREINO") or dificuldade not in DIFICULDADES:
        raise ValueError("Modo deve ser PROVA ou TREINO; dificuldade facil, medio ou dificil")
    tid = "TR-" + uuid.uuid4().hex[:10].upper()
    estado = {"revelados": [], "objecoes": [], "calculos": [], "propostas": [], "estado_cliente": "NEGOCIANDO"}
    db.execute("INSERT INTO treinos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (tid, vendedor, cliente_id, modo, dificuldade, _now(), None, "ATIVO", json.dumps(estado), None, None))
    _log(tid, "cliente", PERSONAS[cliente_id]["abertura"])  # receptivo: o cliente começa
    return obter(tid)


def obter(tid: str) -> dict:
    r = _row(tid)
    estado = json.loads(r.pop("estado_json"))
    res = json.loads(r.pop("resultado_json")) if r.get("resultado_json") else None
    msgs = db.fetch_all("SELECT * FROM treino_mensagens WHERE treino_id=? ORDER BY id", (tid,))
    for m in msgs:
        m["meta"] = json.loads(m.pop("meta_json") or "{}")
    p = PERSONAS[r["cliente_id"]]
    return {**r, "mensagens": msgs, "resultado": res, "cliente": catalog.consultar_cliente(r["cliente_id"]),
            "contato": {"nome": p["contato"], "cargo": p["cargo"]}, "calculos": estado["calculos"], "propostas": estado["propostas"],
            "progresso": {"segredos_descobertos": len(estado["revelados"]), "segredos_total": len(p["segredos"]),
                          "estado_cliente": estado["estado_cliente"]}}


def _persona_prompt(cliente_id: str, dificuldade: str) -> str:
    p, c = PERSONAS[cliente_id], catalog.consultar_cliente(cliente_id)
    dados = {"voce": f"{p['contato']}, {p['cargo']} da {c['razao_social']} ({c['cidade']})",
             "situacao": c["situacao"], "segredos": p["segredos"], "objecoes": p["objecoes"],
             "condicao_aceite": p["condicao_aceite"], "dificuldade": DIFICULDADES[dificuldade]}
    return P_CLIENTE + "\n\nSUA PERSONA:\n" + json.dumps(dados, ensure_ascii=False)


def _transcricao(tid: str) -> list[dict]:
    return db.fetch_all("SELECT role, conteudo FROM treino_mensagens WHERE treino_id=? AND role IN ('vendedor','cliente') ORDER BY id", (tid,))


def mensagem(tid: str, texto: str, meta: dict | None = None) -> dict:
    r = _row(tid)
    if r["status"] != "ATIVO":
        raise ValueError("Treino encerrado")
    estado = json.loads(r["estado_json"])
    _log(tid, "vendedor", texto, meta)
    hist = _transcricao(tid)
    # o GPT é o cliente: as falas do vendedor chegam como 'user' e as do cliente como 'assistant'
    msgs = [{"role": "system", "content": _persona_prompt(r["cliente_id"], r["dificuldade"])}]
    msgs += [{"role": "assistant" if m["role"] == "cliente" else "user", "content": m["conteudo"]} for m in hist]
    try:
        out = llm_client.completar(msgs, json_mode=True, max_tokens=600)
        j = _json(out["message"].get("content"))
        resp = str(j.get("mensagem") or "").strip() or "..."
        validos = {s["id"] for s in PERSONAS[r["cliente_id"]]["segredos"]}
        novos = [s for s in (j.get("revelou") or []) if s in validos and s not in estado["revelados"]]
        estado["revelados"] += novos
        if j.get("objecao"):
            estado["objecoes"].append(j["objecao"])
        if j.get("estado") in ("NEGOCIANDO", "ACEITOU", "RECUSOU", "VAI_PENSAR"):
            estado["estado_cliente"] = j["estado"]
        _log(tid, "cliente", resp, {"revelou": novos, "objecao": j.get("objecao"), "estado": estado["estado_cliente"]})
    except llm_client.LLMUnavailable as e:
        _log(tid, "cliente", "(o cliente não respondeu: GPT indisponível)", {"erro_llm": str(e)})
        _salvar(tid, estado)
        return obter(tid)
    if r["modo"] == "TREINO":
        _coach(tid, r, estado)
    _salvar(tid, estado)
    return obter(tid)


def _coach(tid: str, r: dict, estado: dict) -> None:
    p = PERSONAS[r["cliente_id"]]
    pendente = {"segredos_ainda_nao_descobertos": [s["revela_se"] for s in p["segredos"] if s["id"] not in estado["revelados"]],
                "desafio_challenger": p["desafio_challenger"], "janela_adicional": p["janela_adicional"],
                "calculos_feitos_pelo_vendedor": len(estado["calculos"]), "propostas": len(estado["propostas"])}
    conversa = "\n".join(f"{'V' if m['role'] == 'vendedor' else 'C'}: {m['conteudo']}" for m in _transcricao(tid))
    try:
        out = llm_client.completar([{"role": "system", "content": P_COACH},
                                    {"role": "user", "content": f"CONTEXTO: {json.dumps(pendente, ensure_ascii=False)}\n\nCONVERSA:\n{conversa}"}],
                                   json_mode=True, max_tokens=300, retries=1)
        j = _json(out["message"].get("content"))
        if j.get("dica"):
            _log(tid, "coach", str(j["dica"]), {"foco": j.get("foco")})
    except llm_client.LLMUnavailable:
        pass


def _json(conteudo: str | None) -> dict:
    try:
        j = json.loads(conteudo or "{}")
        return j if isinstance(j, dict) else {}
    except json.JSONDecodeError:
        return {"mensagem": conteudo or ""}


# ------------------------------------------------------------------ ferramentas do vendedor humano (sem mexer no estoque real)
def avaliar_condicao(tid: str, p: dict) -> dict:
    r = _row(tid)
    estado = json.loads(r["estado_json"])
    try:
        out = catalog.avaliar_proposta(p["modelo"], int(p["quantidade"]), p["cidade"], p["produto"], _i(p.get("prazo_meses")),
                                       _i(p.get("dias")), float(p.get("desconto_pct") or 0), p.get("adicionais"), _i(p.get("pacotes_km_extra")))
    except (ErroFerramenta, KeyError, ValueError, TypeError) as e:
        return {"erro": str(e)}
    estado["calculos"].append({"entrada": p, "saida": out})
    _salvar(tid, estado)
    return out


def registrar(tid: str, p: dict) -> dict:
    out = avaliar_condicao(tid, p)
    if "erro" in out:
        return out
    if not out["aprovado"]:
        return {"erro": f"Proposta não aprovada ({out['status']}). {out.get('orientacao', '')}"}
    r = _row(tid)
    estado = json.loads(r["estado_json"])
    prop = {"proposta_id": "TP-" + uuid.uuid4().hex[:6].upper(), **{k: out.get(k) for k in (
        "modelo", "cidade", "produto", "quantidade", "prazo_meses", "dias", "desconto_pct", "aprovado_por", "tem_contrapartida",
        "preco_unitario_final", "total_mensal", "total", "adicionais", "estoque_suficiente")}}
    estado["propostas"].append(prop)
    _salvar(tid, estado)
    return prop


def _i(v):
    return int(v) if v not in (None, "") else None


# ------------------------------------------------------------------ nota final
def _ancora_ok(ancora: str, falas_vendedor: list[str]) -> bool:
    alvo = set(palavras(ancora))
    if len(alvo) < 3:
        return False
    return any(len(alvo & set(palavras(f))) / len(alvo) >= 0.7 for f in falas_vendedor)


def disciplina_margem(estado: dict, falas: list[str]) -> dict:
    """Determinístico: desconto sem contrapartida, limite revelado e valor que não bate com a tabela."""
    achados, nota = [], 10.0
    for p in estado["propostas"]:
        if (p["desconto_pct"] or 0) > 0 and not p["tem_contrapartida"]:
            achados.append(f"Desconto de {p['desconto_pct']:g}% na proposta {p['proposta_id']} sem contrapartida (prazo 24m+ ou 5+ carros).")
            nota -= 4
    margens = {round(v, 2) for r in db.fetch_all("SELECT margem_ia_pct, margem_gerente_pct FROM veiculos") for v in r.values()}
    liberados = {round(c["saida"].get("contraproposta_desconto_pct"), 2) for c in estado["calculos"]
                 if c["saida"].get("contraproposta_desconto_pct") is not None}
    saidas = [c["saida"] for c in estado["calculos"]]
    chave = json.dumps(db.fetch_all("SELECT * FROM veiculos"), sort_keys=True)
    ref = saidas + [{"calculaveis": sorted(agent._valores_calculaveis(chave))}, catalog.consultar_catalogo()]
    for f in falas:
        for m in validator.margens_reveladas(f, margens, liberados):
            achados.append(f"Revelou limite de desconto ({m.split(':')[1]}): \"{f[:80]}\"")
            nota -= 3
        for v in validator.validar(f, ref, True, True, set(), set()):
            if v.startswith("VALOR_NAO_VERIFICADO"):
                achados.append(f"Informou {v.split(':', 1)[1]}, que não bate com a tabela nem com os cálculos feitos.")
                nota -= 1.5
    return {"nota": max(0.0, round(nota, 1)), "achados": achados,
            "justificativa": "Sem problemas de margem ou preço." if not achados else " ".join(achados[:3])}


def encerrar(tid: str) -> dict:
    r = _row(tid)
    if r["status"] == "AVALIADO":
        return obter(tid)
    estado = json.loads(r["estado_json"])
    p = PERSONAS[r["cliente_id"]]
    hist = _transcricao(tid)
    falas = [m["conteudo"] for m in hist if m["role"] == "vendedor"]
    diag_det = round(10 * len(estado["revelados"]) / max(1, len(p["segredos"])), 1)
    disc = disciplina_margem(estado, falas)
    dims, extra, aviso = {}, {}, None
    if falas:
        conversa = "\n".join(f"{'V' if m['role'] == 'vendedor' else 'C'}: {m['conteudo']}" for m in hist)
        contexto = {"persona": {k: p[k] for k in ("segredos", "objecoes", "condicao_aceite", "desafio_challenger", "janela_adicional")},
                    "fatos_do_sistema": {"segredos_descobertos": estado["revelados"], "objecoes_levantadas": estado["objecoes"],
                                         "calculos_feitos": [c["entrada"] for c in estado["calculos"]], "propostas": estado["propostas"],
                                         "estado_final_do_cliente": estado["estado_cliente"]}}
        try:
            out = llm_client.completar([{"role": "system", "content": P_AVALIADOR},
                                        {"role": "user", "content": f"CONTEXTO: {json.dumps(contexto, ensure_ascii=False, default=str)}\n\n"
                                                                    f"CONVERSA:\n{conversa}"}], json_mode=True, max_tokens=2500)
            j = _json(out["message"].get("content"))
            dims = j.get("dimensoes") or {}
            extra = {k: j.get(k) for k in ("pontos_fortes", "pontos_a_melhorar", "resumo")}
        except llm_client.LLMUnavailable as e:
            aviso = f"Avaliação completa indisponível (GPT): {e}. Mostrando só a parte calculada pelo sistema."
    else:
        aviso = "O vendedor não escreveu nada."
    resultado = _montar(dims, diag_det, disc, falas, p, estado)
    resultado.update({k: v for k, v in extra.items() if v}, aviso=aviso,
                     descobertas={"segredos_descobertos": len(estado["revelados"]), "segredos_total": len(p["segredos"]),
                                  "o_que_faltou_descobrir": [s["info"] for s in p["segredos"] if s["id"] not in estado["revelados"]]},
                     desafio_do_cenario=p["desafio_challenger"], estado_final_do_cliente=estado["estado_cliente"])
    db.execute("UPDATE treinos SET status='AVALIADO', fim=?, resultado_json=?, nota_geral=? WHERE treino_id=?",
               (_now(), json.dumps(resultado, ensure_ascii=False, default=str), resultado["nota_geral"], tid))
    return obter(tid)


def _montar(dims: dict, diag_det: float, disc: dict, falas: list[str], p: dict, estado: dict) -> dict:
    out = {}
    for chave in PESOS:
        if chave == "disciplina_margem":
            out[chave] = {"nome": NOMES[chave], "nota": disc["nota"], "justificativa": disc["justificativa"], "achados": disc["achados"],
                          "como_melhorar": "Troque desconto por contrapartida (24 meses ou 5+ carros), não revele limites e use a calculadora "
                                           "antes de falar preço." if disc["achados"] else "", "origem": "sistema"}
            continue
        d = dims.get(chave) or {}
        nota = d.get("nota")
        if chave == "adicionais" and not p["janela_adicional"]:
            continue
        if nota is None and chave != "diagnostico":
            continue
        nota = max(0.0, min(10.0, float(nota))) if nota is not None else None
        item = {"nome": NOMES[chave], "nota": nota, "justificativa": d.get("justificativa", ""), "como_melhorar": d.get("como_melhorar", ""),
                "exemplo": d.get("exemplo", ""), "origem": "avaliador"}
        anc = (d.get("ancora") or "").strip()
        if anc:
            item["ancora"], item["ancora_verificada"] = anc, _ancora_ok(anc, falas)
        if chave == "diagnostico":  # metade vem do que o sistema sabe que foi descoberto
            item["nota"] = round((diag_det + nota) / 2, 1) if nota is not None else diag_det
            item["origem"] = "avaliador + sistema" if nota is not None else "sistema"
            item["segredos"] = f"{len(estado['revelados'])} de {len(p['segredos'])} informações-chave descobertas"
        if chave == "challenger":
            regua = {k: d.get(k) for k in ("trouxe_dado_concreto", "conectou_a_situacao_do_cliente", "cliente_reagiu")}
            item.update(regua=regua, codigos=d.get("codigos") or [])
            if regua["trouxe_dado_concreto"] != "SIM" and item["nota"] is not None and item["nota"] > 4:
                item["nota"] = 4.0  # regra do time (24/09/2026): sem dado concreto não é Challenger
                item["justificativa"] += " (Limitado a 4: sem dado concreto não conta como Challenger.)"
            pontos = sum(v == "SIM" for v in regua.values())
            item["qualidade_c12"] = ("alta" if pontos == 3 else "media" if pontos == 2 else "baixa") if regua["trouxe_dado_concreto"] == "SIM" else "nenhum"
        if chave == "objecoes":
            item["respostas"] = d.get("respostas") or []
        if chave == "fechamento":
            item.update({k: d.get(k) for k in ("tipo", "proximo_passo_claro", "prazo_definido")})
        out[chave] = item
    validas = {k: v for k, v in out.items() if v.get("nota") is not None}
    peso = sum(PESOS[k] for k in validas)
    geral = round(sum(v["nota"] * PESOS[k] for k, v in validas.items()) / peso, 1) if peso else 0.0
    return {"nota_geral": geral, "dimensoes": out, "pesos": {k: PESOS[k] for k in validas}}


def audio(tid: str, dados: bytes, mime: str, duracao_s: float | None) -> dict:
    t = llm_client.transcrever(dados, "audio.webm", mime.split(";")[0])
    if not t["texto"]:
        raise ValueError("Não deu para entender o áudio.")
    return mensagem(tid, t["texto"], {"audio": {"duracao_s": duracao_s, "modelo": t["modelo"]}})


# ------------------------------------------------------------------ histórico (vendedor e gestor; sem ranking)
def historico(vendedor: str | None = None) -> dict:
    sql = "SELECT treino_id, vendedor, cliente_id, modo, dificuldade, inicio, nota_geral, resultado_json FROM treinos WHERE status='AVALIADO'"
    rows = db.fetch_all(sql + (" AND vendedor=?" if vendedor else "") + " ORDER BY inicio", (vendedor,) if vendedor else ())
    por = {}
    for r in rows:
        res = json.loads(r.pop("resultado_json") or "{}")
        r["notas"] = {k: v.get("nota") for k, v in (res.get("dimensoes") or {}).items()}
        r["cliente"] = catalog.consultar_cliente(r["cliente_id"])["razao_social"]
        por.setdefault(r["vendedor"], []).append(r)
    resumo = []
    for v in sorted(por, key=str.lower):  # ordem alfabética: é ferramenta de desenvolvimento, não ranking
        lst = por[v]
        dims = {}
        for t in lst:
            for k, n in t["notas"].items():
                if n is not None:
                    dims.setdefault(k, []).append(n)
        resumo.append({"vendedor": v, "treinos": len(lst), "media_geral": round(sum(t["nota_geral"] for t in lst) / len(lst), 1),
                       "ultima_nota": lst[-1]["nota_geral"], "evolucao": [t["nota_geral"] for t in lst],
                       "media_por_dimensao": {NOMES[k]: round(sum(n) / len(n), 1) for k, n in dims.items()},
                       "ponto_mais_fraco": NOMES[min(dims, key=lambda k: sum(dims[k]) / len(dims[k]))] if dims else None})
    return {"vendedores": resumo, "treinos": [t for v in por.values() for t in v]}
