"""Ferramentas determinísticas do vendedor. O Python calcula e decide; o LLM só conversa.

Percentuais são devolvidos em pontos percentuais (3.0 = 3%). A margem (IA/gerente) NUNCA sai destas funções:
o LLM recebe apenas o resultado (aprovado, aprovado pelo gerente, negado) e, quando negado, uma contraproposta.
"""
import json
import math
import uuid
from datetime import datetime, timezone

from database import db
from services.util import norm

CIDADES = {"sao paulo": "SAO PAULO", "sp": "SAO PAULO", "curitiba": "CURITIBA", "cwb": "CURITIBA",
           "belo horizonte": "BELO HORIZONTE", "bh": "BELO HORIZONTE"}
CIDADE_NOME = {"SAO PAULO": "São Paulo", "CURITIBA": "Curitiba", "BELO HORIZONTE": "Belo Horizonte"}
PRAZOS_AM = (12, 24, 36)
VALIDADE_DIAS = 5
FRANQUIA_KM_MES = 2000  # km/mês por veículo incluídos no mensal
# Parâmetros fictícios de energia/combustível (R$ por km) para a comparação do elétrico
CUSTO_KM_COMBUSTAO = 0.56
CUSTO_KM_ELETRICO = 0.13


class ErroFerramenta(Exception):
    """Erro de entrada: vira resposta estruturada para o LLM, não exceção para o usuário."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cidade(valor: str | None) -> str:
    c = CIDADES.get(norm(valor))
    if not c:
        raise ErroFerramenta(f"Cidade sem atendimento no simulador: '{valor}'. Atendemos São Paulo, Curitiba e Belo Horizonte.")
    return c


def veiculo(modelo: str) -> dict:
    m = norm(modelo).replace("byd", "").strip().upper()
    v = db.fetch_one("SELECT * FROM veiculos WHERE modelo=?", (m,))
    if not v:
        modelos = ", ".join(r["modelo"].title() for r in db.fetch_all("SELECT modelo FROM veiculos"))
        raise ErroFerramenta(f"Modelo '{modelo}' não está no catálogo. Disponíveis: {modelos}.")
    return v


def _produto(produto: str) -> str:
    p = norm(produto).upper()
    if p in ("AM", "MENSAL"):
        return "AM"
    if p in ("AD", "DIARIA"):
        return "AD"
    raise ErroFerramenta("Produto deve ser 'AM' (mensal) ou 'AD' (diária).")


def desconto_volume_pct(quantidade: int) -> float:
    return 4.0 if quantidade >= 10 else 2.0 if quantidade >= 5 else 0.0


def preco_tabela(v: dict, produto: str, prazo_meses: int | None) -> float:
    if produto == "AD":
        return v["preco_ad"]
    if prazo_meses not in PRAZOS_AM:
        raise ErroFerramenta("Mensal (AM) só em 12, 24 ou 36 meses. Para períodos menores, use diária (AD).")
    return v[f"preco_am_{prazo_meses}"]


def tem_contrapartida(produto: str, quantidade: int, prazo_meses: int | None) -> bool:
    return quantidade >= 5 or (produto == "AM" and (prazo_meses or 0) >= 24)


def _estoque(modelo: str, cid: str) -> dict:
    return db.fetch_one("SELECT unidades, prazo_entrega_dias FROM estoque WHERE modelo=? AND cidade=?", (modelo, cid))


# ---------------------------------------------------------------- consultas
def consultar_cliente(cliente_id: str) -> dict:
    c = db.fetch_one("SELECT * FROM clientes WHERE cliente_id=?", (cliente_id,))
    if not c:
        raise ErroFerramenta("Cliente não encontrado.")
    out = {k: c[k] for k in ("cliente_id", "razao_social", "cnpj", "icp", "grupo", "perfil_preco", "km_mes", "produto_atual",
                             "modelo_atual", "qtd_atual", "dias_diaria_mes", "contrato_vence_dias", "frota_propria", "situacao")}
    out["cidade"] = CIDADE_NOME.get(c["cidade"], c["cidade"])
    out["tier"] = c["tier"]
    out["atendimento"] = "EXECUTIVO_DEDICADO" if c["tier"] == "A" else "VENDA_INTERNA"
    if c["km_mes"] and c["km_mes"] > FRANQUIA_KM_MES:
        out["km_acima_da_franquia_por_veiculo"] = c["km_mes"] - FRANQUIA_KM_MES
    if c["grupo"]:
        out["outros_cnpjs_do_grupo"] = [
            {"cliente_id": r["cliente_id"], "razao_social": r["razao_social"], "cidade": CIDADE_NOME.get(r["cidade"], r["cidade"]),
             "produto_atual": r["produto_atual"]}
            for r in db.fetch_all("SELECT * FROM clientes WHERE grupo=? AND cliente_id<>?", (c["grupo"], cliente_id))]
    return out


def identificar_cliente(identificador: str) -> dict:
    ident = str(identificador or "").strip()
    digitos = "".join(ch for ch in ident if ch.isdigit())
    for c in db.fetch_all("SELECT * FROM clientes"):
        if ident.upper() in (c["cliente_id"], c["codigo"]) or (digitos and "".join(ch for ch in c["cnpj"] if ch.isdigit()) == digitos):
            return consultar_cliente(c["cliente_id"])
    raise ErroFerramenta("Nenhum cliente cadastrado com esse CNPJ/código. O time de venda interna só atende clientes cadastrados.")


def consultar_catalogo(cidade_nome: str | None = None, modelo: str | None = None) -> dict:
    veiculos = [veiculo(modelo)] if modelo else db.fetch_all("SELECT * FROM veiculos ORDER BY preco_am_12")
    cid = cidade(cidade_nome) if cidade_nome else None
    itens = []
    for v in veiculos:
        item = {"modelo": v["modelo"].title(), "categoria": v["categoria"], "eletrico": bool(v["eletrico"]),
                "preco_diaria": v["preco_ad"], "preco_mensal_12m": v["preco_am_12"], "preco_mensal_24m": v["preco_am_24"],
                "preco_mensal_36m": v["preco_am_36"]}
        if cid:
            e = _estoque(v["modelo"], cid)
            item.update(estoque_disponivel=e["unidades"], prazo_entrega_se_faltar_dias=e["prazo_entrega_dias"])
        itens.append(item)
    return {"cidade": CIDADE_NOME.get(cid) if cid else None, "veiculos": itens, "adicionais_mensal": listar_adicionais(),
            "regras_publicas": {"prazos_mensal_meses": list(PRAZOS_AM),
                                "franquia_km_mes_por_veiculo": FRANQUIA_KM_MES,
                                "desconto_volume": "5 a 9 veículos: 2% de tabela; 10 ou mais: 4% (automático)",
                                "validade_proposta_dias": VALIDADE_DIAS}}


def listar_adicionais() -> list[dict]:
    return [{"codigo": a["codigo"], "nome": a["nome"], "preco_mensal": a["preco_mensal_por_veiculo"], "unidade": a["unidade"],
             "quando_oferecer": a["quando_oferecer"]} for a in db.fetch_all("SELECT * FROM adicionais ORDER BY codigo")]


def _adicionais(produto: str, codigos: list | None, pacotes_km: int | None, quantidade: int) -> dict:
    codigos = [str(c).upper().strip() for c in (codigos or []) if str(c).strip()]
    if pacotes_km and "KM_EXTRA_1000" not in codigos:
        codigos.append("KM_EXTRA_1000")
    if not codigos:
        return {"itens": [], "por_veiculo": 0.0, "total_mensal": 0.0}
    if produto != "AM":
        raise ErroFerramenta("Adicionais só existem no mensal (AM).")
    tabela = {a["codigo"]: a for a in db.fetch_all("SELECT * FROM adicionais")}
    itens, por_veiculo = [], 0.0
    for cod in dict.fromkeys(codigos):
        if cod not in tabela:
            raise ErroFerramenta(f"Adicional '{cod}' não existe. Disponíveis: {', '.join(tabela)}.")
        n = max(1, int(pacotes_km or 1)) if cod == "KM_EXTRA_1000" else 1
        valor = round(tabela[cod]["preco_mensal_por_veiculo"] * n, 2)
        itens.append({"codigo": cod, "nome": tabela[cod]["nome"], "quantidade_por_veiculo": n, "mensal_por_veiculo": valor})
        por_veiculo += valor
    return {"itens": itens, "por_veiculo": round(por_veiculo, 2), "total_mensal": round(por_veiculo * quantidade, 2)}


def pacotes_km_necessarios(km_mes: int | None) -> int:
    return max(0, math.ceil(((km_mes or 0) - FRANQUIA_KM_MES) / 1000))


# ---------------------------------------------------------------- comparações (Challenger com dado)
def comparar_diaria_mensal(modelo: str, dias_por_mes: int, quantidade: int = 1) -> dict:
    v = veiculo(modelo)
    if not 1 <= int(dias_por_mes) <= 31:
        raise ErroFerramenta("dias_por_mes deve estar entre 1 e 31.")
    custo_diaria = round(v["preco_ad"] * dias_por_mes * quantidade, 2)
    custo_mensal = round(v["preco_am_12"] * quantidade, 2)
    equilibrio = math.ceil(v["preco_am_12"] / v["preco_ad"])
    mais_barato = "MENSAL" if custo_mensal < custo_diaria else "DIARIA"
    return {"modelo": v["modelo"].title(), "quantidade": quantidade, "dias_por_mes": dias_por_mes,
            "custo_diaria_por_mes": custo_diaria, "custo_mensal_12m_por_mes": custo_mensal,
            "diferenca_por_mes": round(abs(custo_diaria - custo_mensal), 2), "mais_barato": mais_barato,
            "dias_de_equilibrio": equilibrio,
            "leitura": (f"Acima de {equilibrio} dias de uso por mês o mensal sai mais barato que a diária."
                        + ("" if mais_barato == "MENSAL" else " Com este uso, a diária é mais barata: não recomende o mensal por preço."))}


def comparar_eletrico(km_mes: int, modelo_comparado: str, prazo_meses: int = 12, quantidade: int = 1) -> dict:
    d, c = veiculo("DOLPHIN"), veiculo(modelo_comparado)
    if c["eletrico"]:
        raise ErroFerramenta("Compare o Dolphin com um modelo a combustão (Onix, Polo ou Creta).")
    alug_d, alug_c = preco_tabela(d, "AM", prazo_meses), preco_tabela(c, "AM", prazo_meses)
    energia_d, comb_c = round(km_mes * CUSTO_KM_ELETRICO, 2), round(km_mes * CUSTO_KM_COMBUSTAO, 2)
    total_d, total_c = round(alug_d + energia_d, 2), round(alug_c + comb_c, 2)
    equilibrio = math.ceil((alug_d - alug_c) / (CUSTO_KM_COMBUSTAO - CUSTO_KM_ELETRICO))
    compensa = total_d < total_c
    return {"km_mes_por_veiculo": km_mes, "prazo_meses": prazo_meses, "quantidade": quantidade,
            "dolphin": {"aluguel_mensal": alug_d, "energia_mensal": energia_d, "total_mensal": total_d},
            modelo_comparado.title(): {"aluguel_mensal": alug_c, "combustivel_mensal": comb_c, "total_mensal": total_c},
            "economia_mensal_por_veiculo_com_dolphin": round(total_c - total_d, 2),
            "economia_mensal_total": round((total_c - total_d) * quantidade, 2),
            "compensa": compensa, "km_de_equilibrio": equilibrio,
            "premissas": f"Parâmetros fictícios do simulador: combustão R$ {CUSTO_KM_COMBUSTAO:.2f}/km, elétrico R$ {CUSTO_KM_ELETRICO:.2f}/km.",
            "leitura": (f"O Dolphin compensa a partir de {equilibrio} km/mês por veículo."
                        + ("" if compensa else " Com este uso NÃO compensa: diga isso ao cliente."))}


# ---------------------------------------------------------------- negociação
def calcular(modelo: str, quantidade: int, cidade_nome: str, produto: str, prazo_meses: int | None = None,
             dias: int | None = None, desconto_pct: float = 0.0, adicionais: list | None = None,
             pacotes_km_extra: int | None = None) -> dict:
    """Preço correto para uma combinação (sem decidir alçada). Usado por avaliar/registrar e pela checagem do modo A."""
    v, cid, prod = veiculo(modelo), cidade(cidade_nome), _produto(produto)
    quantidade = int(quantidade)
    if quantidade < 1:
        raise ErroFerramenta("Quantidade deve ser pelo menos 1.")
    if prod == "AD" and not dias:
        raise ErroFerramenta("Para diária (AD), informe 'dias'.")
    tabela = preco_tabela(v, prod, prazo_meses)
    vol = desconto_volume_pct(quantidade)
    unit = round(tabela * (1 - vol / 100) * (1 - float(desconto_pct) / 100), 2)
    out = {"modelo": v["modelo"].title(), "cidade": CIDADE_NOME[cid], "produto": prod, "quantidade": quantidade,
           "preco_tabela_unitario": tabela, "desconto_volume_pct": vol, "desconto_pct": float(desconto_pct),
           "preco_unitario_final": unit}
    if prod == "AM":
        ad = _adicionais(prod, adicionais, pacotes_km_extra, quantidade)
        veic = round(unit * quantidade, 2)
        out.update(prazo_meses=prazo_meses, total_mensal_veiculos=veic)
        if ad["itens"]:
            out.update(adicionais=ad["itens"], adicionais_mensal_por_veiculo=ad["por_veiculo"], adicionais_total_mensal=ad["total_mensal"])
        out.update(total_mensal=round(veic + ad["total_mensal"], 2),
                   total_contrato=round((veic + ad["total_mensal"]) * prazo_meses, 2))
    elif adicionais or pacotes_km_extra:
        _adicionais(prod, adicionais, pacotes_km_extra, quantidade)  # levanta o erro explicativo
    else:
        out.update(dias=int(dias), total=round(unit * quantidade * int(dias), 2))
    return out


def avaliar_proposta(modelo: str, quantidade: int, cidade_nome: str, produto: str, prazo_meses: int | None = None,
                     dias: int | None = None, desconto_pct: float = 0.0, adicionais: list | None = None,
                     pacotes_km_extra: int | None = None) -> dict:
    v = veiculo(modelo)
    prod = _produto(produto)
    desconto_pct = max(0.0, float(desconto_pct or 0))
    contrapartida = tem_contrapartida(prod, int(quantidade), prazo_meses)
    ia, ger = v["margem_ia_pct"], v["margem_gerente_pct"]
    if desconto_pct <= ia + 1e-9:
        status, aprovado_por = "APROVADO", "vendedor"
    elif desconto_pct <= ger + 1e-9 and contrapartida:
        status, aprovado_por = "APROVADO_GERENTE", "gerente_simulado"
    elif desconto_pct <= ger + 1e-9:
        status, aprovado_por = "NEGADO_GERENTE", None
    else:
        status, aprovado_por = "ACIMA_DO_LIMITE", None
    aprovado = status.startswith("APROVADO")
    base = calcular(modelo, quantidade, cidade_nome, prod, prazo_meses, dias, desconto_pct if aprovado else 0.0, adicionais,
                    pacotes_km_extra)
    e = _estoque(v["modelo"], cidade(cidade_nome))
    out = {"status": status, "aprovado": aprovado, "aprovado_por": aprovado_por, "desconto_solicitado_pct": desconto_pct,
           "tem_contrapartida": contrapartida, **base,
           "estoque_disponivel": e["unidades"], "estoque_suficiente": e["unidades"] >= int(quantidade),
           "falta_unidades": max(0, int(quantidade) - e["unidades"]), "prazo_entrega_se_faltar_dias": e["prazo_entrega_dias"],
           "validade_proposta_dias": VALIDADE_DIAS}
    if not aprovado:
        # Contraproposta: o maior desconto aprovável NESTAS condições (não revela o teto com contrapartida se não houver)
        contra = ger if contrapartida else ia
        out["contraproposta_desconto_pct"] = contra
        out["contraproposta"] = calcular(modelo, quantidade, cidade_nome, prod, prazo_meses, dias, contra, adicionais, pacotes_km_extra)
        out["orientacao"] = ("Gerente negou: sem contrapartida. Com prazo de 24 meses ou mais, ou 5 veículos ou mais, o gerente pode avaliar."
                             if status == "NEGADO_GERENTE" else "Pedido acima do que pode ser aprovado nestas condições.")
    return out


def exige_humano(cliente_id: str) -> bool:
    c = db.fetch_one("SELECT tier FROM clientes WHERE cliente_id=?", (cliente_id,))
    return bool(c and c["tier"] == "A")


def registrar_proposta(conversation_id: str, cliente_id: str, modo: str, modelo: str, quantidade: int, cidade_nome: str,
                       produto: str, prazo_meses: int | None = None, dias: int | None = None, desconto_pct: float = 0.0,
                       aceita_prazo_entrega: bool = False, adicionais: list | None = None, pacotes_km_extra: int | None = None) -> dict:
    """Modo B: só registra o que avaliar_proposta aprova. Reserva o estoque (compartilhado entre conversas)."""
    if exige_humano(cliente_id):
        raise ErroFerramenta("Cliente Tier A (estratégico): proposta é exclusiva do executivo dedicado. Faça o handoff.")
    av = avaliar_proposta(modelo, quantidade, cidade_nome, produto, prazo_meses, dias, desconto_pct, adicionais, pacotes_km_extra)
    if not av["aprovado"]:
        raise ErroFerramenta(f"Proposta não aprovada ({av['status']}). Use avaliar_proposta e ofereça a contraproposta.")
    if not av["estoque_suficiente"] and not aceita_prazo_entrega:
        raise ErroFerramenta(f"Faltam {av['falta_unidades']} unidades nesta cidade (entrega em {av['prazo_entrega_se_faltar_dias']} dias). "
                             "Pergunte ao cliente se aceita o prazo de entrega e registre com aceita_prazo_entrega=true.")
    return _gravar(conversation_id, cliente_id, modo, av, checagem={"valida": True})


def _gravar(conversation_id: str, cliente_id: str, modo: str, calc: dict, checagem: dict, reservar: int | None = None) -> dict:
    modelo = calc["modelo"].upper()
    cid = cidade(calc["cidade"])
    e = _estoque(modelo, cid)
    qtd = calc["quantidade"]
    reserva = min(qtd, e["unidades"]) if reservar is None else reservar
    db.execute("UPDATE estoque SET unidades = unidades - ? WHERE modelo=? AND cidade=?", (reserva, modelo, cid))
    pid = "PROP-" + uuid.uuid4().hex[:8].upper()
    db.execute("INSERT INTO propostas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (pid, conversation_id, cliente_id, modo, modelo, cid, calc["produto"], qtd, calc.get("prazo_meses"), calc.get("dias"),
                calc["desconto_pct"], calc["preco_unitario_final"], calc.get("total_mensal"), calc.get("total"), calc.get("aprovado_por"),
                reserva, int(reserva < qtd), json.dumps(checagem, ensure_ascii=False), _now(),
                json.dumps(calc.get("adicionais") or [], ensure_ascii=False), calc.get("adicionais_total_mensal") or 0.0))
    return {"proposta_id": pid, "registrada": True, "simulada": True, "unidades_reservadas": reserva,
            "entrega_futura_unidades": qtd - reserva, "prazo_entrega_dias": e["prazo_entrega_dias"] if reserva < qtd else 0,
            "validade_dias": VALIDADE_DIAS, **{k: calc[k] for k in ("modelo", "cidade", "produto", "quantidade", "desconto_pct",
                                                                    "preco_unitario_final") if k in calc},
            **{k: calc[k] for k in ("prazo_meses", "total_mensal_veiculos", "adicionais", "adicionais_total_mensal", "total_mensal",
                                    "total_contrato", "dias", "total") if k in calc}}


PRAZO_RETORNO = {"CLIENTE_ESTRATEGICO": "hoje, em até 2 horas úteis"}


def criar_handoff(conversation_id: str, cliente_id: str, motivo: str, resumo: str = "", briefing: dict | None = None) -> dict:
    hid = "HO-" + uuid.uuid4().hex[:8].upper()
    db.execute("INSERT INTO handoffs (handoff_id, conversation_id, cliente_id, motivo, resumo, criado_em, briefing_json, status) "
               "VALUES (?,?,?,?,?,?,?,'ABERTO')",
               (hid, conversation_id, cliente_id, motivo, resumo, _now(), json.dumps(briefing or {}, ensure_ascii=False, default=str)))
    return {"protocolo": hid, "motivo": motivo, "prazo_retorno": PRAZO_RETORNO.get(motivo, "1 dia útil"), "simulado": True,
            "briefing_enviado_ao_time": bool(briefing)}


def registrar_qualificacao(eh_decisor: bool | None = None, decisor: str | None = None, outros_envolvidos: str | None = None,
                           prazo_decisao: str | None = None) -> dict:
    campos = {"eh_decisor": eh_decisor, "decisor": decisor, "outros_envolvidos": outros_envolvidos, "prazo_decisao": prazo_decisao}
    faltando = [k for k, v in campos.items() if v in (None, "")]
    return {"qualificacao_registrada": True, **campos, "faltando": faltando}


# ---------------------------------------------------------------- estoque compartilhado
def estoque_atual() -> list[dict]:
    return db.fetch_all("SELECT * FROM estoque ORDER BY modelo, cidade")


def reiniciar_estoque() -> None:
    db.execute("UPDATE estoque SET unidades = unidades_iniciais")
