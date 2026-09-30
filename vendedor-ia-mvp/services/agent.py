"""Agente vendedor.

Modo B (oficial): o LLM conduz a conversa inteira e decide quando consultar; números e decisões vêm das ferramentas
(services.catalog). Margens nunca chegam ao LLM. Mensagem com dado não verificado -> 1 reescrita; persistindo, mensagem segura.
Modo A (controle): LLM "pura" — recebe toda a tabela, margens, regra do gerente e estoque no prompt e decide sozinho.
Nada é corrigido; tudo é MARCADO para medir o risco.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from database import db
from services import catalog, llm_client, validator
from services.catalog import ErroFerramenta

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
BASE = (PROMPTS / "vendedor_base.md").read_text(encoding="utf-8")
REGRAS_B = (PROMPTS / "vendedor_b.md").read_text(encoding="utf-8")
REGRAS_A = (PROMPTS / "vendedor_a.md").read_text(encoding="utf-8")
MAX_PASSOS = 8
CONTINGENCIA = ("Opa, meu sistema deu uma travada aqui e não tô conseguindo consultar agora 😕\n\n"
                "Já anotei sua mensagem e te retorno ainda hoje ou, no máximo, em 1 dia útil, tá?")
MENSAGEM_SEGURA = ("Deixa eu confirmar isso certinho no sistema antes de te passar valor, pra não te falar nada errado.\n\n"
                   "Me confirma só qual modelo, quantos carros e por quanto tempo?")

_num = {"type": "integer"}
_str = {"type": "string"}
TOOLS = [
    ("consultar_cliente", "Dados cadastrais e de uso do cliente desta conversa (ou de outro CNPJ do mesmo grupo).",
     {"cliente_id": {**_str, "description": "Opcional: outro CNPJ do mesmo grupo"}}, []),
    ("identificar_cliente", "Localiza um cliente cadastrado pelo CNPJ ou código.", {"identificador": _str}, ["identificador"]),
    ("consultar_catalogo", "Modelos, preços de tabela (diária e mensal 12/24/36) e estoque por cidade.",
     {"cidade": _str, "modelo": _str}, []),
    ("comparar_diaria_mensal", "Compara o custo mensal de usar diária X dias/mês contra o mensal de 12 meses.",
     {"modelo": _str, "dias_por_mes": _num, "quantidade": _num}, ["modelo", "dias_por_mes"]),
    ("comparar_eletrico", "Compara Dolphin (elétrico) com um modelo a combustão: aluguel + energia/combustível pelo km/mês.",
     {"km_mes": _num, "modelo_comparado": _str, "prazo_meses": _num, "quantidade": _num}, ["km_mes", "modelo_comparado"]),
    ("avaliar_proposta", "Calcula preço e decide se um desconto é aprovado (pelo vendedor ou gerente). Mostra estoque. "
                         "Use SEMPRE antes de falar de desconto ou preço final.",
     {"modelo": _str, "quantidade": _num, "cidade": _str, "produto": {**_str, "enum": ["AM", "AD"]},
      "prazo_meses": {**_num, "description": "AM: 12, 24 ou 36"}, "dias": {**_num, "description": "AD: número de dias"},
      "desconto_pct": {"type": "number", "description": "Desconto pedido, em pontos percentuais (3 = 3%)"}},
     ["modelo", "quantidade", "cidade", "produto"]),
    ("registrar_proposta", "Registra a proposta aceita pelo cliente e reserva o estoque. Só depois do aceite explícito.",
     {"modelo": _str, "quantidade": _num, "cidade": _str, "produto": {**_str, "enum": ["AM", "AD"]}, "prazo_meses": _num,
      "dias": _num, "desconto_pct": {"type": "number"}, "aceita_prazo_entrega": {"type": "boolean"},
      "cliente_id": {**_str, "description": "Opcional: outro CNPJ do mesmo grupo"}},
     ["modelo", "quantidade", "cidade", "produto"]),
    ("criar_handoff", "Encaminha para atendimento humano (suporte, reclamação, pedido do cliente) e devolve protocolo.",
     {"motivo": {**_str, "enum": ["SUPORTE", "RECLAMACAO", "SOLICITACAO_CLIENTE", "OUTRO"]}, "resumo": _str}, ["motivo"]),
]
TOOLS_SCHEMA = [{"type": "function", "function": {"name": n, "description": d,
                                                  "parameters": {"type": "object", "properties": p, "required": r}}}
                for n, d, p, r in TOOLS]
PROTOCOLO_JSON = ("\n\nFERRAMENTAS (responda SEMPRE um objeto JSON):\n"
                  '- para consultar: {"acao": "ferramenta", "nome": "<nome>", "argumentos": {...}}\n'
                  '- para falar com o cliente: {"acao": "responder", "texto": "<mensagem>"}\n'
                  "Depois de cada consulta você recebe o RESULTADO e decide o próximo passo.\n"
                  + "\n".join(f"* {n}({', '.join(p)}): {d}" for n, d, p, _ in TOOLS))

_modo_ferramentas = {"atual": os.getenv("LLM_TOOLS", "auto")}  # auto -> native, cai para json se o gate recusar


# ------------------------------------------------------------------ execução das ferramentas
def _int(v):
    return int(v) if v not in (None, "") else None


def executar(nome: str, args: dict, ctx: dict) -> dict:
    a = args or {}
    try:
        if nome == "consultar_cliente":
            return catalog.consultar_cliente(_cliente_do_grupo(a.get("cliente_id"), ctx))
        if nome == "identificar_cliente":
            return catalog.identificar_cliente(a["identificador"])
        if nome == "consultar_catalogo":
            return catalog.consultar_catalogo(a.get("cidade"), a.get("modelo"))
        if nome == "comparar_diaria_mensal":
            return catalog.comparar_diaria_mensal(a["modelo"], _int(a["dias_por_mes"]), _int(a.get("quantidade")) or 1)
        if nome == "comparar_eletrico":
            return catalog.comparar_eletrico(_int(a["km_mes"]), a["modelo_comparado"], _int(a.get("prazo_meses")) or 12,
                                             _int(a.get("quantidade")) or 1)
        if nome == "avaliar_proposta":
            return catalog.avaliar_proposta(a["modelo"], _int(a["quantidade"]), a["cidade"], a["produto"], _int(a.get("prazo_meses")),
                                            _int(a.get("dias")), float(a.get("desconto_pct") or 0))
        if nome == "registrar_proposta":
            return catalog.registrar_proposta(ctx["conversation_id"], _cliente_do_grupo(a.get("cliente_id"), ctx), "B", a["modelo"],
                                              _int(a["quantidade"]), a["cidade"], a["produto"], _int(a.get("prazo_meses")),
                                              _int(a.get("dias")), float(a.get("desconto_pct") or 0), bool(a.get("aceita_prazo_entrega")))
        if nome == "criar_handoff":
            return catalog.criar_handoff(ctx["conversation_id"], ctx["cliente_id"], a.get("motivo") or "OUTRO", a.get("resumo") or "")
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    except ErroFerramenta as e:
        return {"erro": str(e)}
    except (KeyError, TypeError, ValueError) as e:
        return {"erro": f"Parâmetros inválidos para {nome}: {e}"}


def _cliente_do_grupo(cliente_id: str | None, ctx: dict) -> str:
    if not cliente_id or cliente_id == ctx["cliente_id"]:
        return ctx["cliente_id"]
    atual = db.fetch_one("SELECT grupo FROM clientes WHERE cliente_id=?", (ctx["cliente_id"],))
    outro = db.fetch_one("SELECT grupo FROM clientes WHERE cliente_id=?", (cliente_id,))
    if not atual or not outro or not atual["grupo"] or atual["grupo"] != outro["grupo"]:
        raise ErroFerramenta("Só é possível usar outro CNPJ do mesmo grupo econômico do cliente em atendimento.")
    return cliente_id


def margens_gerente() -> set:
    return {round(r["margem_gerente_pct"], 2) for r in db.fetch_all("SELECT margem_gerente_pct FROM veiculos")}


# ------------------------------------------------------------------ modo B
def _contexto(ctx: dict) -> str:
    c = db.fetch_one("SELECT razao_social, cidade FROM clientes WHERE cliente_id=?", (ctx["cliente_id"],))
    memoria = json.dumps(ctx["memoria"][-10:], ensure_ascii=False, default=str)[-8000:] if ctx["memoria"] else "nenhuma ainda"
    return (f"\n\nATENDIMENTO ATUAL: mensagem recebida do WhatsApp cadastrado de {c['razao_social']} (cliente_id {ctx['cliente_id']}, "
            f"{catalog.CIDADE_NOME.get(c['cidade'], c['cidade'])}). Consulte o cadastro antes de ofertar.\n"
            f"CONSULTAS JÁ FEITAS NESTA CONVERSA (resultados reais): {memoria}")


def turno_b(ctx: dict, historico: list[dict], texto_cliente: str) -> dict:
    uso = {"tokens_entrada": 0, "tokens_saida": 0, "custo_gate": 0.0}
    chamadas, violacoes_brutas = [], []
    sistema = BASE + "\n" + REGRAS_B + _contexto(ctx)
    msgs = [{"role": "user" if m["role"] == "cliente" else "assistant", "content": m["conteudo"]} for m in historico[-16:]]
    msgs.append({"role": "user", "content": texto_cliente})
    corrigiu, texto, final = False, "", "ok"

    def somar(r):
        uso["tokens_entrada"] += r["tokens_entrada"] or 0
        uso["tokens_saida"] += r["tokens_saida"] or 0
        uso["custo_gate"] += r["custo_gate"] or 0

    def rodar(nome, args):
        out = executar(nome, args, ctx)
        chamadas.append({"nome": nome, "entrada": args, "saida": out})
        ctx["memoria"].append({"ferramenta": nome, "entrada": args, "saida": out})
        return out

    for _ in range(MAX_PASSOS):
        nativo = _modo_ferramentas["atual"] in ("auto", "native")
        try:
            if nativo:
                r = llm_client.completar([{"role": "system", "content": sistema}] + msgs, tools=TOOLS_SCHEMA)
            else:
                r = llm_client.completar([{"role": "system", "content": sistema + PROTOCOLO_JSON}] + msgs, json_mode=True)
        except llm_client.ToolsNaoSuportadas:
            _modo_ferramentas["atual"] = "json"
            continue
        somar(r)
        msg = r["message"]
        if nativo and msg.get("tool_calls"):
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg["tool_calls"]})
            for call in msg["tool_calls"]:
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = rodar(call["function"]["name"], args)
                msgs.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(out, ensure_ascii=False, default=str)})
            continue
        conteudo = (msg.get("content") or "").strip()
        if not nativo:
            try:
                j = json.loads(conteudo)
            except json.JSONDecodeError:
                j = {"acao": "responder", "texto": conteudo}
            if j.get("acao") == "ferramenta":
                out = rodar(j.get("nome", ""), j.get("argumentos") or {})
                msgs.append({"role": "assistant", "content": conteudo})
                msgs.append({"role": "user", "content": f"RESULTADO de {j.get('nome')}: {json.dumps(out, ensure_ascii=False, default=str)}"})
                continue
            conteudo = str(j.get("texto") or "").strip()
        viol = _validar(conteudo, ctx)
        if viol and not corrigiu:
            corrigiu = True
            violacoes_brutas += viol
            msgs.append({"role": "assistant", "content": conteudo if nativo else json.dumps({"acao": "responder", "texto": conteudo})})
            msgs.append({"role": "user", "content": "[CORREÇÃO DO SISTEMA — não é o cliente, não mencione] Sua última mensagem não passou "
                                                    f"na checagem: {', '.join(viol)}. Reescreva usando apenas dados devolvidos pelas "
                                                    "ferramentas (consulte-as se precisar) e sem revelar limites internos."})
            continue
        if viol:
            violacoes_brutas += viol
            texto, final = MENSAGEM_SEGURA, "mensagem_segura"
        else:
            texto, final = formatar_baloes(conteudo), ("corrigida" if corrigiu else "ok")
        break
    else:
        texto, final = MENSAGEM_SEGURA, "limite_de_passos"
    return {"texto": texto, "chamadas": chamadas, "violacoes": violacoes_brutas, "resultado_validacao": final,
            "modo_ferramentas": _modo_ferramentas["atual"], "tiques": validator.tiques_de_robo(texto), **uso}


def formatar_baloes(texto: str, maximo: int = 3) -> str:
    """Estilo WhatsApp: sem markdown, 1 a 3 balões separados por linha em branco."""
    t = texto.replace("**", "").replace("__", "")
    t = "\n".join(ln[2:] if ln.startswith(("- ", "• ", "* ")) else ln for ln in t.splitlines())
    baloes = [b.strip() for b in t.split("\n\n") if b.strip()]
    if len(baloes) > maximo:
        baloes = baloes[: maximo - 1] + [" ".join(baloes[maximo - 1:])]
    return "\n\n".join(baloes)


def _validar(texto: str, ctx: dict) -> list[str]:
    saidas = [m["saida"] for m in ctx["memoria"]]
    houve_prop = any(m["ferramenta"] == "registrar_proposta" and m["saida"].get("registrada") for m in ctx["memoria"])
    houve_ho = any(m["ferramenta"] == "criar_handoff" and m["saida"].get("protocolo") for m in ctx["memoria"])
    _, pct = validator.permitidos(saidas)
    return validator.validar(texto, saidas, houve_prop, houve_ho, margens_gerente(), pct)


# ------------------------------------------------------------------ modo A (controle)
def dados_internos(cliente_id: str) -> dict:
    return {"veiculos": db.fetch_all("SELECT * FROM veiculos"),
            "regras": {"prazos_mensal_meses": list(catalog.PRAZOS_AM),
                       "desconto_volume": "5 a 9 veículos: 2% de tabela; 10 ou mais: 4% (automático, não consome margem)",
                       "margem": "margem_ia_pct = você aprova sozinho; até margem_gerente_pct o gerente aprova SOMENTE com contrapartida "
                                 "(prazo >= 24 meses ou 5+ veículos); acima disso, negado",
                       "validade_proposta_dias": catalog.VALIDADE_DIAS,
                       "custo_km": {"combustao": catalog.CUSTO_KM_COMBUSTAO, "eletrico": catalog.CUSTO_KM_ELETRICO}},
            "estoque": catalog.estoque_atual(), "cliente": catalog.consultar_cliente(cliente_id)}


@lru_cache(maxsize=4)
def _valores_calculaveis(chave_veiculos: str) -> frozenset:
    """Todos os preços que o motor produziria (modelo × produto × prazo × qtd × desconto inteiro): o que o modo A pode citar
    sem ser 'não verificado'."""
    vals = set()
    for v in json.loads(chave_veiculos):
        for qtd in range(1, 21):
            vol = catalog.desconto_volume_pct(qtd)
            for d in range(0, 11):
                f = (1 - vol / 100) * (1 - d / 100)
                for prazo in catalog.PRAZOS_AM:
                    u = round(v[f"preco_am_{prazo}"] * f, 2)
                    vals |= {u, round(u * qtd, 2), round(u * qtd * prazo, 2)}
                u = round(v["preco_ad"] * f, 2)
                vals.add(u)
                vals |= {round(u * qtd * dias, 2) for dias in range(1, 32)}
    return frozenset(vals)


def turno_a(ctx: dict, historico: list[dict], texto_cliente: str) -> dict:
    internos = dados_internos(ctx["cliente_id"])
    sistema = (BASE + "\n" + REGRAS_A + "\n\nDADOS INTERNOS:\n" + json.dumps(internos, ensure_ascii=False, default=str)
               + f"\n\nATENDIMENTO ATUAL: WhatsApp cadastrado de {internos['cliente']['razao_social']}.")
    msgs = [{"role": "system", "content": sistema}]
    msgs += [{"role": "user" if m["role"] == "cliente" else "assistant", "content": m["conteudo"]} for m in historico[-16:]]
    msgs.append({"role": "user", "content": texto_cliente})
    r = llm_client.completar(msgs, json_mode=True)
    conteudo = (r["message"].get("content") or "").strip()
    try:
        j = json.loads(conteudo)
    except json.JSONDecodeError:
        j = {"resposta": conteudo}
    texto = formatar_baloes(str(j.get("resposta") or "").strip())
    acoes, marcas = [], []
    prop = j.get("registrar_proposta")
    if isinstance(prop, dict):
        out, m = _registrar_a(ctx, prop)
        acoes.append({"nome": "registrar_proposta (decidido pelo modelo)", "entrada": prop, "saida": out})
        marcas += m
        ctx["memoria"].append({"ferramenta": "registrar_proposta", "entrada": prop, "saida": out})
    ho = j.get("handoff")
    if isinstance(ho, dict):
        out = catalog.criar_handoff(ctx["conversation_id"], ctx["cliente_id"], ho.get("motivo") or "OUTRO", ho.get("resumo") or "")
        acoes.append({"nome": "criar_handoff (decidido pelo modelo)", "entrada": ho, "saida": out})
        ctx["memoria"].append({"ferramenta": "criar_handoff", "entrada": ho, "saida": out})
    # Checagem (só marca): valores citados precisam existir na tabela/estoque/cadastro ou ser um preço que o motor produziria
    chave = json.dumps(internos["veiculos"], sort_keys=True)
    # referência = só o motor (tabela, estoque, cadastro, preços calculáveis); nunca os números que o próprio modelo decidiu
    extras = [internos, {"calculaveis": sorted(_valores_calculaveis(chave))}]
    cli = internos["cliente"]
    for modelo in ("ONIX", "POLO", "CRETA"):
        for prazo in catalog.PRAZOS_AM:
            extras.append(catalog.comparar_eletrico(cli["km_mes"] or 1, modelo, prazo, max(1, cli["qtd_atual"] or 1)))
    if cli["dias_diaria_mes"]:
        extras += [catalog.comparar_diaria_mensal(m, cli["dias_diaria_mes"], q) for m in ("ONIX", "POLO", "CRETA", "DOLPHIN")
                   for q in range(1, 21)]
    houve_prop = any(a["saida"].get("registrada") for a in acoes) or any(
        m["ferramenta"] == "registrar_proposta" for m in ctx["memoria"])
    houve_ho = any(m["ferramenta"] == "criar_handoff" for m in ctx["memoria"])
    # % de desconto é decisão do próprio modelo no modo A: a regra é checada na proposta registrada, não no texto
    marcas += [v for v in validator.validar(texto, extras, houve_prop, houve_ho, margens_gerente(), set())
               if not v.startswith("PERCENTUAL_NAO_VERIFICADO")]
    return {"texto": texto or conteudo, "chamadas": acoes, "violacoes": marcas, "resultado_validacao": "marcado" if marcas else "ok",
            "modo_ferramentas": "sem_ferramentas", "tiques": validator.tiques_de_robo(texto or conteudo), "tokens_entrada": r["tokens_entrada"] or 0, "tokens_saida": r["tokens_saida"] or 0,
            "custo_gate": r["custo_gate"] or 0.0}


def _registrar_a(ctx: dict, p: dict) -> tuple[dict, list[str]]:
    """Registra o que o modelo decidiu (sem bloquear) e compara com o que o motor teria feito."""
    marcas = []
    try:
        qtd, prazo, dias = _int(p.get("quantidade")) or 1, _int(p.get("prazo_meses")), _int(p.get("dias"))
        desc = float(p.get("desconto_pct") or 0)
        correto = catalog.avaliar_proposta(p["modelo"], qtd, p["cidade"], p.get("produto") or "AM", prazo, dias, desc)
    except (ErroFerramenta, KeyError, TypeError, ValueError) as e:
        return {"registrada": False, "erro": str(e)}, [f"PROPOSTA_INVALIDA:{e}"]
    if not correto["aprovado"]:
        marcas.append(f"DESCONTO_FORA_DA_REGRA:{desc}% ({correto['status']})")
    informado = p.get("preco_unitario_informado")
    certo = catalog.calcular(p["modelo"], qtd, p["cidade"], correto["produto"], prazo, dias, desc)
    if informado is not None and abs(float(informado) - certo["preco_unitario_final"]) > 0.011:
        marcas.append(f"PRECO_DIVERGENTE:informou {informado}, correto {certo['preco_unitario_final']}")
    if not correto["estoque_suficiente"]:
        marcas.append(f"ALEM_DO_ESTOQUE:faltam {correto['falta_unidades']}")
    calc = {**certo, "aprovado_por": p.get("aprovado_por") or "modelo"}
    if informado is not None:
        calc["preco_unitario_final"] = float(informado)
    out = catalog._gravar(ctx["conversation_id"], ctx["cliente_id"], "A", calc,
                          checagem={"valida": not marcas, "marcas": marcas, "status_motor": correto["status"]})
    return out, marcas
