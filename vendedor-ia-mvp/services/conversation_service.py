"""Orquestração da conversa: intenção -> ferramentas determinísticas -> resposta -> validação -> auditoria."""
import json
import re
import uuid
from datetime import datetime, timezone

from database import db
from database.db import BASE_DIR
from services import customer_service, pricing_service, rules_service, seller, tools
from services.textutil import any_word, norm, to_int

LOG_FILE = BASE_DIR / "logs" / "conversations.jsonl"
PRAZO_PROPOSTA = "2 dias úteis"
PRAZO_HANDOFF = "1 dia útil"

# Texto voltado ao cliente (o mesmo conteúdo que a regra recomenda ao vendedor, sem tom de instrução interna)
ARGUMENTOS = {
    "C001": "Com 5 veículos e contrato de 6 meses você ganha previsibilidade de custo e acesso às condições de volume.",
    "C002": "A modalidade mensal dá previsibilidade de custo e evita a variação das diárias; o compromisso é apenas o prazo do contrato.",
    "C003": "Você é nosso cliente e queremos manter a parceria dentro das condições autorizadas para o seu caso.",
    "C004": "Na renovação valem as condições contratuais em vigor.",
    "C005": "O piloto permite testar a operação com poucos veículos antes de qualquer compromisso maior.",
    "C006": "Posso registrar a proposta sujeita à confirmação de disponibilidade.",
    "C007": "Sinto muito pela experiência anterior; queremos ouvir e resolver antes de qualquer oferta.",
    "C008": "Como o período é curto, a cotação por diária já reflete o prazo; a validade é a da própria cotação.",
    "C009": "Os preços variam por praça e posso cotar até duas praças para você comparar.",
    "C010": "Você é nosso cliente e queremos manter a parceria dentro das condições autorizadas; pedidos maiores passam por atendimento humano.",
}
REGRAS_TXT = {
    "C004": ("Na renovação valem as condições contratuais em vigor; cancelamento antes do prazo e eventual multa seguem o contrato vigente, "
             "e não vou citar valores que não constem nas condições oficiais. Para detalhes formais posso acionar o time de contratos."),
}
DEFAULT_REGRAS = "Vou me basear apenas nas condições oficiais vigentes para o seu caso."

INTENTS = [
    ("INJECAO", ["ignore", "esqueca as instrucoes", "esqueca suas instrucoes", "system prompt", "seu prompt", "instrucoes internas",
                 "voce agora e", "modo desenvolvedor", "revele suas regras", "aja como", "finja que"]),
    ("HUMANO", ["atendente", "humano", "falar com uma pessoa", "falar com alguem", "gerente", "supervisor", "pessoa de verdade"]),
    ("SUPORTE", ["senha", "acessar o portal", "acesso ao portal", "login", "nao consigo entrar", "atualizar cadastro", "segunda via",
                 "boleto", "nota fiscal", "email de cadastro", "redefinir"]),
    ("RECLAMACAO", ["reclama", "pessimo", "horrivel", "insatisf", "experiencia ruim", "mau atendimento", "ninguem resolveu",
                    "atrasaram", "descaso", "processar"]),
    ("ACEITE", ["fechado", "pode enviar a proposta", "aceito", "vamos fechar", "pode gerar a proposta", "quero a proposta",
                "pode registrar", "fechamos", "pode seguir", "combinado", "ok, pode", "topo"]),
    ("DESCONTO", ["desconto", "abatimento", "baixar o preco", "melhorar o preco", "mais barato", "abaixar"]),
    ("DISPONIBILIDADE", ["disponivel", "disponibilidade", "tem carro", "tem utilitario", "garantem", "garante", "voces tem"]),
    ("CREDITO", ["credito", "financiamento", "limite de credito", "aprovacao de credito", "parcelar"]),
    ("MULTA", ["multa", "rescisao", "rescindir", "cancelar antes", "cancelamento", "renovar as regras", "regras do contrato"]),
    ("OBJECAO", ["caro", "preco alto", "alto demais", "concorrente", "outra locadora", "nao sei se", "incerteza", "receio", "medo",
                 "comprometer", "compromisso", "fidelidade", "urgente", "urgencia", "para ontem", "melhor de outra",
                 "preco por cidade", "diferente em cada", "comparar", "achei o preco"]),
    ("ENCERRAR", ["obrigado", "obrigada", "tchau", "ate mais", "encerrar", "era so isso", "valeu"]),
    ("PRECO", ["preco", "valor", "quanto", "cotacao", "custa", "orcamento", "simular", "proposta"]),
]
OBJECAO_TIPOS = {
    "PRECO": ["caro", "preco alto", "alto demais", "achei o preco"], "CONCORRENCIA": ["concorrente", "outra locadora", "melhor de outra"],
    "COMPROMISSO": ["comprometer", "compromisso", "fidelidade"], "INCERTEZA_DEMANDA": ["nao sei se", "incerteza", "receio", "medo"],
    "URGENCIA": ["urgente", "urgencia", "para ontem"], "PRECO_POR_PRACA": ["preco por cidade", "diferente em cada", "comparar"],
}
PRACAS = ["curitiba", "sao paulo", "belo horizonte", "rio de janeiro", "porto alegre"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- classificação e extração ----------
def classificar(texto: str, state: dict) -> tuple[str, str]:
    t = norm(texto)
    achados = [nome for nome, palavras in INTENTS if any_word(t, palavras)]
    if re.search(r"\d+(?:[.,]\d+)?\s*(?:%|por cento)", t) and "DESCONTO" not in achados:
        achados.append("DESCONTO")
    if not achados:
        if set(extrair_slots(t, {}, {})) & {"quantidade", "prazo", "praca"}:
            return "INFORMA_NECESSIDADE", "MEDIA"
        return "OUTRO", "BAIXA"
    # prioridade = ordem da lista; ACEITE só vale se não for pedido de handoff/desconto explícito
    intent = achados[0]
    if intent == "SUPORTE" and state.get("cotacao"):
        intent = achados[1] if len(achados) > 1 else intent
    if intent == "ACEITE" and "DESCONTO" in achados and re.search(r"\d+\s*%", t):
        intent = "DESCONTO"
    return intent, "ALTA" if len(achados) == 1 else "MEDIA"


def extrair_slots(t: str, cliente: dict, state: dict) -> dict:
    out: dict = {}
    m = re.search(r"\b(mais\s+)?(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+(?:carros?|veiculos?|unidades?|utilitarios?|automoveis)", t)
    if m:
        n = to_int(m.group(2))
        if n:
            base = round(cliente.get("volume_medio_am") or cliente.get("volume_medio_ad") or 0) if m.group(1) else 0
            out["quantidade"] = base + n
    m = re.search(r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|doze)\s+(meses|mes)\b", t)
    if m and to_int(m.group(1)):
        out["prazo"], out["prazo_unidade"] = to_int(m.group(1)), "meses"
    m = re.search(r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+(dias|dia)\b", t)
    if m and to_int(m.group(1)) and "prazo" not in out:
        out["prazo"], out["prazo_unidade"] = to_int(m.group(1)), "dias"
    if re.search(r"\bum ano\b", t):
        out["prazo"], out["prazo_unidade"] = 12, "meses"
    if re.search(r"\bsemestre\b", t):
        out["prazo"], out["prazo_unidade"] = 6, "meses"
    for p in PRACAS:
        if p in t:
            out["praca"] = p.upper()
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|por cento)", t)
    if m:
        out["desconto"] = round(float(m.group(1).replace(",", ".")) / 100, 4)
    return out


def _tipo_objecao(t: str) -> str:
    for tipo, palavras in OBJECAO_TIPOS.items():
        if any_word(t, palavras):
            return tipo
    return "GERAL"


# ---------- persistência ----------
def _estado(conv_id: str) -> dict:
    row = db.fetch_one("SELECT estado_json FROM conversas WHERE conversation_id=?", (conv_id,))
    return json.loads(row["estado_json"])


def _salvar_estado(conv_id: str, state: dict) -> None:
    proposta = 1 if state.get("proposta") else 0
    handoff = 1 if state.get("handoff") else 0
    db.execute("UPDATE conversas SET estado_json=?, desfecho=?, proposta_gerada=?, handoff=?, desconto_final=?, fora_da_alcada=?, status=? "
               "WHERE conversation_id=?",
               (json.dumps(state, ensure_ascii=False), state["desfecho"], proposta, handoff, state.get("desconto_aplicado", 0.0),
                1 if state.get("fora_da_alcada") else 0, state.get("status", "ATIVA"), conv_id))


def _log_msg(conv_id: str, role: str, conteudo: str, audit: dict | None = None, tokens=(0, 0)) -> int:
    a = audit or {}
    conn = db.connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO mensagens (conversation_id,timestamp,role,conteudo,intencao,acao_sugerida,ferramenta_chamada,regra_aplicada,"
                "validacao,tokens_entrada,tokens_saida,auditoria_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (conv_id, _now(), role, conteudo, a.get("intencao"), a.get("acao"),
                 ",".join(t["nome"] for t in a.get("ferramentas", [])) or None, a.get("regra"), a.get("validacao"),
                 tokens[0], tokens[1], json.dumps(a, ensure_ascii=False, default=str) if a else None))
            mid = cur.lastrowid
    finally:
        conn.close()
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"conversation_id": conv_id, "role": role, "conteudo": conteudo, "auditoria": a},
                               ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return mid


def _historico(conv_id: str) -> list[dict]:
    return db.fetch_all("SELECT role, conteudo FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))


# ---------- ciclo de vida ----------
def listar_cenarios() -> list[dict]:
    rows = db.fetch_all("SELECT c.*, cl.razao_social FROM cenarios c JOIN clientes cl USING (cliente_id) ORDER BY cenario_id")
    for r in rows:
        r["desfechos_esperados"] = json.loads(r["desfechos_esperados"])
    return rows


def _estado_inicial(cliente: dict, cenario_id: str) -> dict:
    op = (customer_service.consultar_oportunidades(cliente["cliente_id"]) or [None])[0]
    return {"cliente_id": cliente["cliente_id"], "cenario_id": cenario_id, "produto": op["produto"] if op else "MENSAL",
            "informados": [], "quantidade": None, "prazo": None, "praca": None, "cotacao": None, "pracas_cotadas": [],
            "desconto_aplicado": 0.0, "pedidos_acima": 0, "handoff_oferecido": False, "perguntas_feitas": 0,
            "proposta": None, "handoff": None, "desfecho": "EM_ANDAMENTO", "status": "ATIVA", "fora_da_alcada": False,
            "sem_disponibilidade_confirmada": False}


def iniciar_conversa(cenario_id: str | None = None, identificador: str | None = None) -> dict:
    cenario = None
    if cenario_id:
        cenario = db.fetch_one("SELECT * FROM cenarios WHERE cenario_id=?", (cenario_id,))
        if not cenario:
            raise ValueError("Cenário inexistente")
        cliente = customer_service.consultar_perfil(cenario["cliente_id"])
    elif identificador:
        cliente = customer_service.identificar_cliente(identificador)
        if not cliente:
            raise ValueError("Cliente não encontrado")
    else:
        raise ValueError("Informe cenario_id ou identificador")
    conv_id = "CV-" + uuid.uuid4().hex[:10].upper()
    state = _estado_inicial(cliente, cenario["cenario_id"] if cenario else "LIVRE")
    db.execute("INSERT INTO conversas (conversation_id,cliente_id,inicio,cenario_id,status,desfecho,estado_json) VALUES (?,?,?,?,?,?,?)",
               (conv_id, cliente["cliente_id"], _now(), state["cenario_id"], "ATIVA", "EM_ANDAMENTO", json.dumps(state, ensure_ascii=False)))
    comercial = bool(cenario["abertura_comercial"]) if cenario else True
    _abrir(conv_id, cliente, state, comercial)
    return obter_conversa(conv_id)


def _abrir(conv_id: str, cliente: dict, state: dict, comercial: bool) -> None:
    ops = customer_service.consultar_oportunidades(cliente["cliente_id"])
    fatos = {"cliente": {"razao_social": cliente["razao_social"], "status": cliente["status_relacionamento"]},
             "motivo": (ops[0]["motivo_oportunidade"] if ops else "vamos entender a sua necessidade").rstrip(".")}
    acao = "ABERTURA" if comercial else "ABERTURA_SUPORTE"
    if comercial:
        state["perguntas_feitas"] = 1
    r = seller.responder(acao, fatos, [], "")
    audit = {"intencao": "INICIO", "confianca": "ALTA", "acao": acao,
             "ferramentas": [{"nome": "consultar_perfil", "entrada": {"cliente_id": cliente["cliente_id"]}, "saida": "ok"},
                             {"nome": "consultar_oportunidades", "entrada": {"cliente_id": cliente["cliente_id"]}, "saida": ops[:1]}],
             "regra": None, "validacao": _rotulo(r), "fonte": r["fonte"], "erro_llm": r.get("erro"), "fatos": fatos, "handoff": False}
    _log_msg(conv_id, "vendedor", r["texto"], audit, (r["tokens_entrada"], r["tokens_saida"]))
    _salvar_estado(conv_id, state)


def reiniciar(conv_id: str) -> dict:
    row = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    db.execute("DELETE FROM mensagens WHERE conversation_id=?", (conv_id,))
    db.execute("DELETE FROM propostas WHERE conversation_id=?", (conv_id,))
    db.execute("DELETE FROM handoffs WHERE conversation_id=?", (conv_id,))
    db.execute("DELETE FROM avaliacoes WHERE conversation_id=?", (conv_id,))
    cliente = customer_service.consultar_perfil(row["cliente_id"])
    state = _estado_inicial(cliente, row["cenario_id"])
    cen = db.fetch_one("SELECT abertura_comercial FROM cenarios WHERE cenario_id=?", (row["cenario_id"],))
    db.execute("UPDATE conversas SET fim=NULL, estado_json=? WHERE conversation_id=?", (json.dumps(state, ensure_ascii=False), conv_id))
    _abrir(conv_id, cliente, state, bool(cen["abertura_comercial"]) if cen else True)
    return obter_conversa(conv_id)


def obter_conversa(conv_id: str) -> dict:
    row = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not row:
        raise LookupError("Conversa inexistente")
    state = json.loads(row.pop("estado_json"))
    msgs = db.fetch_all("SELECT * FROM mensagens WHERE conversation_id=? ORDER BY message_id", (conv_id,))
    for m in msgs:
        m["auditoria"] = json.loads(m.pop("auditoria_json")) if m.get("auditoria_json") else None
    return {**row, "estado": state, "mensagens": msgs,
            "cliente": customer_service.consultar_perfil(row["cliente_id"]),
            "regra": rules_service.get_rule(row["cliente_id"]),
            "oportunidade": (customer_service.consultar_oportunidades(row["cliente_id"]) or [None])[0]}


def _rotulo(r: dict) -> str:
    if r["fonte"] == "template_reescrito":
        return "REESCRITO_TEMPLATE:" + ";".join(r["violacoes_brutas"])
    if r["fonte"] == "contingencia":
        return "CONTINGENCIA"
    return "OK"


# ---------- decisão ----------
def _cotar(state: dict, cliente: dict, ferramentas: list) -> dict | None:
    """Simula o preço com os slots conhecidos (ou defaults da oportunidade). Atualiza o estado."""
    op = (customer_service.consultar_oportunidades(cliente["cliente_id"]) or [None])[0]
    produto = state["produto"]
    qtd = state["quantidade"] or (op["quantidade_sugerida"] if op else 1)
    if state["prazo"]:
        prazo = state["prazo"]
    else:
        prazo = (op["prazo_dias"] if produto == "DIARIA" else max(1, op["prazo_dias"] // 30)) if op else 6
    praca = state["praca"] or cliente["cidade"].upper().replace("Ã", "A").replace("Í", "I")
    entrada = {"cliente_id": cliente["cliente_id"], "produto": produto, "quantidade": qtd, "prazo": prazo, "praca": praca}
    cot = pricing_service.simular_preco(**entrada)
    ferramentas.append({"nome": "simular_preco", "entrada": entrada, "saida": cot})
    if "erro" in cot:
        return cot
    state["cotacao"] = cot
    state["quantidade"], state["prazo"] = qtd, prazo
    if cot["praca"] and cot["praca"] not in state["pracas_cotadas"]:
        state["pracas_cotadas"].append(cot["praca"])
    return cot


def _handoff(conv_id: str, state: dict, motivo: str, ferramentas: list, resumo: str) -> dict:
    if state.get("handoff"):
        return state["handoff"]
    h = tools.criar_handoff(conv_id, state["cliente_id"], motivo, resumo)
    ferramentas.append({"nome": "criar_handoff", "entrada": {"motivo": motivo}, "saida": h})
    state["handoff"] = h
    return h


def _atualizar_slots(state: dict, cliente: dict, texto: str) -> dict:
    slots = extrair_slots(norm(texto), cliente, state)
    if "quantidade" in slots:
        state["quantidade"] = slots["quantidade"]
        state["informados"].append("quantidade")
    if "prazo" in slots:
        prazo, un = slots["prazo"], slots["prazo_unidade"]
        if state["produto"] == "DIARIA" and un == "meses":
            prazo *= 30
        elif state["produto"] != "DIARIA" and un == "dias":
            prazo = max(1, prazo // 30)
        state["prazo"] = prazo
        state["informados"].append("prazo")
    if "praca" in slots:
        state["praca"] = slots["praca"]
        state["informados"].append("praca")
    return slots


def processar_mensagem(conv_id: str, texto: str) -> dict:
    conv = db.fetch_one("SELECT * FROM conversas WHERE conversation_id=?", (conv_id,))
    if not conv:
        raise LookupError("Conversa inexistente")
    state = json.loads(conv["estado_json"])
    if state["status"] != "ATIVA":
        raise ValueError("Conversa encerrada; reinicie para continuar")
    cliente = customer_service.consultar_perfil(state["cliente_id"])
    historico = _historico(conv_id)
    _log_msg(conv_id, "cliente", texto)

    intent, conf = classificar(texto, state)
    slots = _atualizar_slots(state, cliente, texto)
    ferramentas: list = []
    fatos: dict = {"cliente": {"razao_social": cliente["razao_social"], "status": cliente["status_relacionamento"]}}
    regra = rules_service.get_rule(cliente["cliente_id"], state["produto"]) or {}
    acao = "PEDIR_CLARIFICACAO"

    def cot_ou_erro() -> dict | None:
        c = _cotar(state, cliente, ferramentas)
        if c and "erro" in c:
            fatos["erro"] = c
            return None
        return c

    def diagnosticar() -> None:
        nonlocal acao
        state["perguntas_feitas"] += 1
        faltam = [n for n, k in (("quantidade de veículos", "quantidade"), ("prazo", "prazo"), ("cidade de utilização", "praca"))
                  if k not in state["informados"]]
        fatos["campos_pendentes"] = faltam
        acao = "DIAGNOSTICAR"

    def pronto_para_cotar() -> bool:
        return ({"quantidade", "prazo"} <= set(state["informados"])) or state["perguntas_feitas"] >= 2

    def limite_cotacoes() -> bool:
        praca_alvo = (state["praca"] or cliente["cidade"].upper()).upper()
        return (len(state["pracas_cotadas"]) >= (regra.get("max_cotacoes") or 1)
                and praca_alvo not in state["pracas_cotadas"] and bool(state["pracas_cotadas"]))

    if intent == "INJECAO":
        acao = "RECUSAR_INJECAO"
    elif intent == "HUMANO":
        fatos["handoff"] = _handoff(conv_id, state, "SOLICITACAO_CLIENTE", ferramentas, "Cliente pediu atendimento humano.")
        fatos["prazo_retorno"], acao, state["desfecho"] = PRAZO_HANDOFF, "HANDOFF_CRIADO", "HANDOFF"
    elif intent == "SUPORTE":
        fatos["handoff"] = _handoff(conv_id, state, "SUPORTE", ferramentas, "Solicitação de suporte, sem intenção comercial.")
        fatos["prazo_retorno"], acao, state["desfecho"] = PRAZO_HANDOFF, "ENCAMINHAR_SUPORTE", "ENCAMINHADO_SUPORTE"
    elif intent == "RECLAMACAO":
        fatos["handoff"] = _handoff(conv_id, state, "RECLAMACAO", ferramentas, "Cliente relatou reclamação/experiência negativa.")
        fatos["prazo_retorno"], acao, state["desfecho"] = PRAZO_HANDOFF, "HANDOFF_CRIADO", "HANDOFF"
    elif intent == "ACEITE":
        if state.get("proposta"):
            fatos["proposta"], fatos["prazo_retorno"], acao = state["proposta"], PRAZO_PROPOSTA, "CONFIRMAR_PROXIMO_PASSO"
        elif state["cotacao"] is None and not pronto_para_cotar():
            diagnosticar()
        elif state["cotacao"] is None:
            c = cot_ou_erro()
            if c:
                fatos["cotacao"], acao = c, "APRESENTAR_COTACAO"
            else:
                acao = "FORA_DA_REGRA"
        else:
            c = state["cotacao"]
            prop = tools.registrar_proposta(conv_id, cliente["cliente_id"], c, state["desconto_aplicado"],
                                            "Sujeita à confirmação de disponibilidade" if state["sem_disponibilidade_confirmada"] else "")
            ferramentas.append({"nome": "registrar_proposta", "entrada": {"desconto": state["desconto_aplicado"]}, "saida": prop})
            state["proposta"], state["desfecho"] = prop, "PROPOSTA_SIMULADA"
            fatos.update(cotacao=c, proposta=prop, prazo_retorno=PRAZO_PROPOSTA)
            acao = "REGISTRAR_PROPOSTA"
    elif intent == "DESCONTO":
        if state["cotacao"] is None and not pronto_para_cotar() and not slots.get("quantidade"):
            diagnosticar()
        else:
            c = state["cotacao"] if state["cotacao"] and not (slots.keys() & {"quantidade", "prazo", "praca"}) else cot_ou_erro()
            if c is None:
                acao = "FORA_DA_REGRA"
            else:
                pedido = slots.get("desconto")
                if pedido is None:
                    pedido = regra.get("desconto_maximo", 0.0)
                av = rules_service.avaliar_desconto(cliente["cliente_id"], c["oferta_id"], pedido)
                ferramentas.append({"nome": "avaliar_desconto", "entrada": {"oferta_id": c["oferta_id"], "desconto_solicitado": pedido}, "saida": av})
                av["desconto_solicitado"] = pedido
                fatos.update(cotacao=c, regra_msg=ARGUMENTOS.get(cliente["cliente_id"], ""))
                if av["aprovado"] and av["desconto_concedido"] > 0:
                    state["desconto_aplicado"] = av["desconto_concedido"]
                    fatos["desconto"] = {**av, **pricing_service.aplicar_desconto(c, av["desconto_concedido"])}
                    acao = "APLICAR_DESCONTO"
                elif av["aprovado"] or av["desconto_maximo"] == 0:
                    state["pedidos_acima"] += 1 if not av["aprovado"] else 0
                    acao = "NEGAR_DESCONTO"
                else:
                    state["pedidos_acima"] += 1
                    if av["exige_handoff"] and state["pedidos_acima"] >= 2:
                        fatos["handoff"] = _handoff(conv_id, state, "DESCONTO_ACIMA_DA_ALCADA", ferramentas,
                                                    f"Cliente pediu {pedido:.0%}; alçada {av['desconto_maximo']:.0%}.")
                        fatos["prazo_retorno"], acao, state["desfecho"] = PRAZO_HANDOFF, "HANDOFF_CRIADO", "HANDOFF"
                    else:
                        state["desconto_aplicado"] = av["desconto_concedido"]
                        state["handoff_oferecido"] = av["exige_handoff"]
                        fatos["handoff_oferecido"] = av["exige_handoff"]
                        fatos["desconto"] = {**av, **pricing_service.aplicar_desconto(c, av["desconto_concedido"])}
                        acao = "CONTRAPROPOR_DESCONTO"
    elif intent == "DISPONIBILIDADE":
        state["sem_disponibilidade_confirmada"] = True
        fatos["disponibilidade_confirmada"] = False
        acao = "INFORMAR_DISPONIBILIDADE"
    elif intent == "CREDITO":
        fatos["credito_simulado"] = False
        acao = "INFORMAR_SEM_CREDITO"
    elif intent == "MULTA":
        fatos["regra_msg"] = REGRAS_TXT.get(cliente["cliente_id"], DEFAULT_REGRAS)
        acao = "EXPLICAR_REGRAS"
    elif intent == "OBJECAO":
        tipo = _tipo_objecao(norm(texto))
        h = customer_service.resumo_historico(cliente["cliente_id"])
        hist_txt = ""
        if h.get("meses") and h.get("receita_12m"):
            hist_txt = {"CRESCENTE": "Vi que a sua operação vem crescendo conosco.", "EM_QUEDA": "Notei que o volume vem caindo e quero entender o motivo.",
                        "ESTAVEL": "Vi que a sua operação é estável conosco."}[h["tendencia"]]
        fatos.update(objecao=tipo, historico_txt=hist_txt, regra_msg=ARGUMENTOS.get(cliente["cliente_id"], ""), historico=h)
        if state["cotacao"] is None and {"quantidade", "prazo"} <= set(state["informados"]):
            cot_ou_erro()
        if state["cotacao"]:
            fatos["cotacao"] = state["cotacao"]
        acao = "TRATAR_OBJECAO"
    elif intent == "ENCERRAR":
        state["status"] = "ENCERRADA"
        if state.get("proposta"):
            fatos["proposta"] = state["proposta"]
        if state.get("handoff"):
            fatos["handoff"] = state["handoff"]
        fatos["prazo_retorno"] = PRAZO_PROPOSTA if state.get("proposta") else PRAZO_HANDOFF
        if state["desfecho"] == "EM_ANDAMENTO":
            state["desfecho"] = "ENCERRADO_SEM_ACORDO"
        acao = "ENCERRAR"
    else:  # PRECO / INFORMA_NECESSIDADE / OUTRO
        if state.get("proposta") and intent == "OUTRO":
            fatos["proposta"], fatos["prazo_retorno"], acao = state["proposta"], PRAZO_PROPOSTA, "CONFIRMAR_PROXIMO_PASSO"
        elif not pronto_para_cotar() and (intent in ("PRECO", "INFORMA_NECESSIDADE", "OUTRO")):
            diagnosticar()
        elif limite_cotacoes():
            acao = "LIMITE_COTACOES"
        else:
            c = cot_ou_erro()
            if c:
                fatos["cotacao"], acao = c, "APRESENTAR_COTACAO"
            else:
                acao = "FORA_DA_REGRA"

    r = seller.responder(acao, {**fatos, "argumento": ARGUMENTOS.get(cliente["cliente_id"], "")}, historico, texto)
    if r["fonte"] == "contingencia":
        state["desfecho"] = state["desfecho"] if state["desfecho"] != "EM_ANDAMENTO" else "EM_ANDAMENTO"
    audit = {"intencao": intent, "confianca": conf, "acao": acao, "ferramentas": ferramentas,
             "regra": regra.get("regra_id"), "alcada": regra.get("desconto_maximo"), "fonte": r["fonte"], "erro_llm": r.get("erro"),
             "validacao": _rotulo(r), "violacoes_brutas": r["violacoes_brutas"], "fatos": fatos,
             "preco_retornado": (fatos.get("desconto") or fatos.get("cotacao") or {}).get("preco_unitario"),
             "handoff": bool(state.get("handoff")), "slots": slots}
    _log_msg(conv_id, "vendedor", r["texto"], audit, (r["tokens_entrada"], r["tokens_saida"]))
    if state["status"] == "ENCERRADA":
        tools.encerrar_conversa(conv_id)
    _salvar_estado(conv_id, state)
    return obter_conversa(conv_id)
