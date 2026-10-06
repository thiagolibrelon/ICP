"""Avaliador C12 e cliente simulado do Laboratório.

- Cliente simulado: o GPT interpreta a persona (segredos, objeções, condição de aceite) e conversa com a Fernanda.
- Nota C12: o avaliador lê as falas da vendedora e dá nota por dimensão; diagnóstico (segredos descobertos) e
  disciplina de margem têm parte calculada pelo sistema. Âncoras do avaliador são conferidas contra as falas.

Nasceu do Treino de vendas, que virou frente própria (../treino-vendedor). As duas cópias evoluem separadas: mudar a
régua aqui muda a comparação com as rodadas antigas do Laboratório.
"""
import json
from pathlib import Path

from database import db
from database.personas import DIFICULDADES, PERSONAS
from services import agent, catalog, llm_client, validator
from services.util import palavras

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
P_CLIENTE = (PROMPTS / "cliente_simulado.md").read_text(encoding="utf-8")
P_AVALIADOR = (PROMPTS / "avaliador_c12.md").read_text(encoding="utf-8")

PESOS = {"diagnostico": 2.0, "challenger": 2.0, "objecoes": 2.0, "disciplina_margem": 1.5, "fechamento": 1.5,
         "qualificacao": 1.0, "tom": 1.0, "adicionais": 0.5}
NOMES = {"diagnostico": "Diagnóstico", "challenger": "Challenger com dado", "objecoes": "Tratamento de objeções",
         "disciplina_margem": "Disciplina de margem", "fechamento": "Fechamento e próximo passo", "qualificacao": "Qualificação",
         "tom": "Tom e empatia", "adicionais": "Adicionais"}


def _com_papel(nome: str, *a, **kw):
    """Chamada ao LLM marcada com o papel (cliente, coach, avaliador): cada papel pode usar um modelo diferente."""
    with llm_client.papel(nome):
        return llm_client.completar(*a, **kw)

def _persona_prompt(cliente_id: str, dificuldade: str) -> str:
    p, c = PERSONAS[cliente_id], catalog.consultar_cliente(cliente_id)
    dados = {"voce": f"{p['contato']}, {p['cargo']} da {c['razao_social']} ({c['cidade']})",
             "situacao": c["situacao"], "segredos": p["segredos"], "objecoes": p["objecoes"],
             "condicao_aceite": p["condicao_aceite"], "dificuldade": DIFICULDADES[dificuldade]}
    return P_CLIENTE + "\n\nSUA PERSONA:\n" + json.dumps(dados, ensure_ascii=False)

def _json(conteudo: str | None) -> dict:
    try:
        j = json.loads(conteudo or "{}")
        return j if isinstance(j, dict) else {}
    except json.JSONDecodeError:
        return {"mensagem": conteudo or ""}

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

def avaliar_conversa(cliente_id: str, hist: list[dict], estado: dict) -> dict:
    """Nota pela régua C12 para as falas do VENDEDOR de uma conversa (a Fernanda, no Laboratório).
    hist: [{"role": "vendedor"|"cliente", "conteudo"}]; estado: revelados, objecoes, calculos, propostas, estado_cliente."""
    p = PERSONAS[cliente_id]
    falas = [m["conteudo"] for m in hist if m["role"] == "vendedor"]
    diag_det = round(10 * len(estado["revelados"]) / max(1, len(p["segredos"])), 1)
    disc = disciplina_margem(estado, falas)
    dims, extra, aviso = {}, {}, None
    if falas:
        conversa = "\n".join(f"{'V' if m['role'] == 'vendedor' else 'C'}: {m['conteudo']}" for m in hist)
        contexto = {"frente": estado.get("frente", "receptiva"), "motivo_do_contato_ativo": estado.get("motivo"),
                    "persona": {k: p[k] for k in ("segredos", "objecoes", "condicao_aceite", "desafio_challenger", "janela_adicional")},
                    "fatos_do_sistema": {"segredos_descobertos": estado["revelados"], "objecoes_levantadas": estado["objecoes"],
                                         "calculos_feitos": [c["entrada"] for c in estado["calculos"]], "propostas": estado["propostas"],
                                         "estado_final_do_cliente": estado["estado_cliente"]}}
        try:
            out = _com_papel("avaliador", [{"role": "system", "content": P_AVALIADOR},
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
    return resultado


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
