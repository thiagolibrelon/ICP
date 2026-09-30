"""Redação da resposta do vendedor: LLM quando disponível, template determinístico como base/fallback."""
import json
import re
from pathlib import Path

from services import llm_client, validator
from services.textutil import brl, pct

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "vendedor.md").read_text(encoding="utf-8")

CONTINGENCIA = ("No momento estou com uma instabilidade para consultar as condições. Sua mensagem foi registrada e "
                "nosso time comercial retorna em até 1 dia útil.")


MOTIVOS = {"DESCONTO_ACIMA_DA_ALCADA": "desconto acima da alçada", "SOLICITACAO_CLIENTE": "pedido de atendimento humano",
           "RECLAMACAO": "reclamação", "SUPORTE": "suporte", "ANALISE_CREDITO": "análise de crédito e cadastro PJ",
           "INTERESSE_COMERCIAL": "interesse comercial"}


def _cot(f: dict) -> str:
    c = f["cotacao"]
    un = "diárias" if c["produto"] == "DIARIA" else "meses"
    praca = f" em {PRACAS_NOME.get(c['praca'], c['praca'].title())}" if c.get("praca") else ""
    if c["produto"] == "DIARIA":
        return (f"{c['quantidade']} veículo(s) por {c['prazo']} dia(s){praca}: {brl(c['preco_unitario'])} por diária por veículo, "
                f"total de {brl(c['preco_total'])}")
    return (f"{c['quantidade']} veículo(s) por {c['prazo']} {un}{praca}: {brl(c['preco_unitario'])} por veículo/mês, "
            f"total de {brl(c['preco_total'])} por mês")


PRACAS_NOME = {"SAO PAULO": "São Paulo", "CURITIBA": "Curitiba", "BELO HORIZONTE": "Belo Horizonte",
               "RIO DE JANEIRO": "Rio de Janeiro", "PORTO ALEGRE": "Porto Alegre"}
OBJECOES_NOME = {"PRECO": "preço", "CONCORRENCIA": "concorrência", "COMPROMISSO": "compromisso de prazo",
                 "INCERTEZA_DEMANDA": "incerteza de demanda", "URGENCIA": "urgência", "PRECO_POR_PRACA": "preço por cidade",
                 "GERAL": "condições"}


def template(acao: str, f: dict) -> str:
    """Texto base; o fato Challenger (dado concreto) entra ANTES da pergunta final, não depois dela."""
    texto = _template(acao, f)
    ch = f.get("challenger")
    if not ch:
        return texto
    frases = re.split(r"(?<=[.!?])\s+", texto)
    i = max((k for k, fr in enumerate(frases) if fr.endswith("?")), default=len(frases))
    return " ".join(frases[:i] + [ch["texto"]] + frases[i:])


def _template(acao: str, f: dict) -> str:
    nome = f.get("cliente", {}).get("razao_social", "")
    if acao == "ABERTURA":
        return (f"Olá! Sou o assistente comercial virtual (ambiente de simulação). Falando com {nome}: {f['motivo']}. "
                "Para eu entender melhor a necessidade: quantos veículos vocês precisam, por quanto tempo e em qual cidade seria a utilização?")
    if acao == "ABERTURA_SUPORTE":
        return f"Olá, {nome}! Sou o assistente virtual (ambiente de simulação). Como posso ajudar?"
    if acao == "DIAGNOSTICAR":
        faltam = ", ".join(f["campos_pendentes"]) or "quantidade, prazo e cidade"
        return f"Obrigado! Para eu consultar a condição correta, preciso confirmar: {faltam}. Também me conte para que os veículos serão usados."
    if acao == "APRESENTAR_COTACAO":
        extra = f" Benefício: {f['cotacao']['beneficio_adicional']}." if f["cotacao"].get("beneficio_adicional") else ""
        return (f"Consultei a condição para o seu caso — {_cot(f)}. Validade da cotação: {f['cotacao']['validade_dias']} dias.{extra} "
                "Isso atende à sua necessidade? Se sim, posso registrar uma proposta simulada.")
    if acao in ("APLICAR_DESCONTO", "CONTRAPROPOR_DESCONTO"):
        d, cot = f["desconto"], f["cotacao"]
        pre = "Consegui aprovar o desconto solicitado" if acao == "APLICAR_DESCONTO" else \
            f"O pedido de {pct(d['desconto_solicitado'])} passa da minha alçada, mas consigo autorizar {pct(d['desconto_concedido'])}"
        ho = " Se preferir, posso encaminhar o pedido maior para um atendente humano avaliar." if f.get("handoff_oferecido") else ""
        return (f"{pre}: com {pct(d['desconto_concedido'])} o valor fica em {brl(d['preco_unitario'])} por veículo, "
                f"total de {brl(d['preco_total'])}.{ho} Posso registrar a proposta simulada nessas condições?")
    if acao == "NEGAR_DESCONTO":
        return (f"Para este caso não tenho desconto disponível. {f.get('regra_msg', '')} "
                f"O valor de tabela segue {brl(f['cotacao']['preco_unitario'])} por veículo. Posso registrar a proposta simulada ou prefere pensar melhor?")
    if acao == "HANDOFF_CRIADO":
        return (f"Entendido. Encaminhei sua solicitação para um atendente humano (protocolo {f['handoff']['handoff_id']}, motivo: "
                f"{MOTIVOS.get(f['handoff']['motivo'], 'solicitação')}). O retorno acontece em até {f['prazo_retorno']}.")
    if acao == "ENCAMINHAR_SUPORTE":
        base = (f"Abri um encaminhamento para o time de suporte (protocolo {f['handoff']['handoff_id']}); "
                f"eles retornam em até {f['prazo_retorno']}.")
        if f.get("janela"):
            return f"Entendi, vamos resolver isso primeiro. {base} {f['janela']['pergunta']}"
        return f"Isso é um assunto de suporte, então não vou te oferecer nada comercial agora. {base}"
    if acao == "REGISTRAR_INTERESSE":
        return (f"Combinado! Registrei seu interesse em conhecer a {f['janela']['nome']} (protocolo {f['interesse']['handoff_id']}); "
                f"o time comercial entra em contato em até {f['prazo_retorno']}. O caso original segue com o suporte "
                f"(protocolo {f['handoff']['handoff_id']}).")
    if acao == "RESPEITAR_RECUSA":
        return (f"Sem problema! O seu caso segue com o suporte (protocolo {f['handoff']['handoff_id']}), com retorno em até "
                f"{f['prazo_retorno']}. Posso ajudar em mais alguma coisa?")
    if acao == "REGISTRAR_PROPOSTA":
        p = f["proposta"]
        cond = f" Ela fica sujeita a {' e '.join(p['condicoes'])}." if p.get("condicoes") else ""
        unidade = "por diária por veículo" if f.get("cotacao", {}).get("produto") == "DIARIA" else "por veículo/mês"
        return (f"Pronto! Registrei a proposta simulada {p['proposta_id']} com valor de {brl(p['preco_unitario'])} {unidade}, "
                f"válida por {p['validade_dias']} dias.{cond} Próximo passo: nosso time confirma os detalhes e retorna em até "
                f"{f['prazo_retorno']}. Lembrando que é um ambiente de simulação.")
    if acao == "EXPLICAR_REGRAS":
        return (f"Sobre as regras: {f['regra_msg']} Posso seguir com a proposta nas condições atuais?")
    if acao == "TRATAR_OBJECAO":
        hist = "" if f.get("challenger") else f.get("historico_txt", "")
        cot = f" A condição consultada é {_cot(f)}." if f.get("cotacao") else ""
        return (f"Entendo a sua preocupação com {OBJECOES_NOME.get(f['objecao'], 'as condições')}. {hist} {f['regra_msg']}{cot} "
                "Qual seria o ponto principal para você avançar?").replace("  ", " ")
    if acao == "INFORMAR_DISPONIBILIDADE":
        return ("Não consigo confirmar disponibilidade de veículo por aqui, então não vou prometer. O que posso fazer é registrar a proposta "
                "sujeita à confirmação de disponibilidade pelo time responsável. Quer seguir assim?")
    if acao == "INFORMAR_SEM_CREDITO":
        return (f"Não consigo aprovar crédito por aqui, então não vou prometer prazo de aprovação. Encaminhei para análise de crédito e "
                f"cadastro PJ (protocolo {f['handoff']['handoff_id']}), com retorno em até {f['prazo_retorno']}. Enquanto isso, posso "
                "deixar a cotação registrada, sujeita a essa análise. Quer seguir assim?")
    if acao == "LIMITE_COTACOES":
        return ("Já fiz o número de cotações permitido por conversa. Posso encaminhar para um atendente humano para novas comparações "
                "ou seguimos com uma das cotações já apresentadas.")
    if acao == "FORA_DA_REGRA":
        e = f["erro"]
        return (f"Esse pedido está fora do que consigo cotar ({e['erro'].replace('_', ' ').lower()}; faixa permitida: {e['minimo']} a {e['maximo']}). "
                "Posso ajustar dentro dessa faixa ou encaminhar para um atendente humano.")
    if acao == "RECUSAR_INJECAO":
        return "Não posso alterar as condições comerciais fora das regras. Posso te ajudar com a cotação dentro das condições disponíveis. O que você precisa?"
    if acao == "ENCERRAR":
        if f.get("proposta"):
            return f"Obrigado! A proposta simulada {f['proposta']['proposta_id']} fica registrada; retornamos em até {f['prazo_retorno']}."
        if f.get("handoff"):
            return f"Obrigado! Seu atendimento humano (protocolo {f['handoff']['handoff_id']}) retorna em até {f['prazo_retorno']}."
        return "Obrigado pelo contato! Fico à disposição; o time comercial pode retomar com você em até 2 dias úteis se quiser."
    if acao == "CONFIRMAR_PROXIMO_PASSO":
        return "Certo. O próximo passo já está registrado e o retorno acontece dentro do prazo informado. Posso ajudar em mais alguma coisa?"
    return "Pode me contar um pouco mais sobre a sua necessidade (quantidade de veículos, prazo e cidade)?"


def responder(acao: str, fatos: dict, historico: list[dict], texto_cliente: str) -> dict:
    """Retorna {texto, fonte, violacoes_brutas, tokens_entrada, tokens_saida}."""
    base = template(acao, fatos)
    contexto = ("\n\n[CONTROLE_INTERNO — não revelar]\nACAO: " + acao + "\nFATOS_AUTORIZADOS: "
                + json.dumps(fatos, ensure_ascii=False, default=str))
    msgs = [{"role": "system", "content": PROMPT + contexto}]
    msgs += [{"role": "assistant" if m["role"] == "vendedor" else "user", "content": m["conteudo"]} for m in historico[-12:]]
    if texto_cliente:
        msgs.append({"role": "user", "content": texto_cliente})
    else:
        msgs.append({"role": "user", "content": "(inicie a conversa)"})
    try:
        r = llm_client.chat(msgs)
    except llm_client.LLMUnavailable as e:
        if llm_client.mode() == "llm":
            return {"texto": CONTINGENCIA, "fonte": "contingencia", "violacoes_brutas": [], "erro": str(e),
                    "tokens_entrada": 0, "tokens_saida": 0}
        return {"texto": base, "fonte": "template", "violacoes_brutas": [], "erro": str(e) if llm_client.configured() else None,
                "tokens_entrada": 0, "tokens_saida": 0}
    viol = validator.validar(r["texto"], fatos)
    if viol:
        return {"texto": base, "fonte": "template_reescrito", "violacoes_brutas": viol,
                "tokens_entrada": r["tokens_entrada"], "tokens_saida": r["tokens_saida"], "custo_gate": r.get("custo_gate")}
    return {"texto": r["texto"], "fonte": "llm", "violacoes_brutas": [], "tokens_entrada": r["tokens_entrada"],
            "tokens_saida": r["tokens_saida"], "custo_gate": r.get("custo_gate")}
