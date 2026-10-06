"""Motivo do contato na frente ATIVA do Treino: o vendedor chama o cliente com um motivo verdadeiro, tirado do cadastro."""
from datetime import datetime, timedelta

from services import catalog

FRANQUIA_KM = catalog.FRANQUIA_KM_MES
NOMES_MOTIVO = {"RENOVACAO": "Contrato vencendo", "DIARIA_ALTA": "Diária com uso alto", "FROTA_PROPRIA": "Frota própria",
                "KM_ACIMA_FRANQUIA": "Km acima da franquia", "RELACIONAMENTO": "Relacionamento"}


def motivos(cliente_id: str) -> list[dict]:
    """Motivos de contato tirados do cadastro, do mais forte para o mais fraco. Todo número aqui é real (do sistema)."""
    c = catalog.consultar_cliente(cliente_id)
    modelo = (c.get("modelo_atual") or "").title()
    qtd, out = c.get("qtd_atual") or 0, []
    vence = c.get("contrato_vence_dias")
    if c.get("produto_atual") == "AM" and vence is not None and vence <= 90:
        data = (datetime.now() + timedelta(days=vence)).strftime("%d/%m/%Y")
        out.append({"motivo": "RENOVACAO", "prioridade": 100 if vence <= 30 else 70,
                    "resumo": f"contrato de {qtd} {modelo} no mensal vence em {vence} dias ({data})",
                    "dados": {"qtd": qtd, "modelo": modelo, "vence_em_dias": vence, "data_vencimento": data}})
    if c.get("produto_atual") == "AD" and (c.get("dias_diaria_mes") or 0) >= 15:
        out.append({"motivo": "DIARIA_ALTA", "prioridade": 80,
                    "resumo": f"usa {qtd} {modelo} na diária cerca de {c['dias_diaria_mes']} dias por mês",
                    "dados": {"qtd": qtd, "modelo": modelo, "dias_por_mes": c["dias_diaria_mes"]}})
    if (c.get("frota_propria") or 0) > 0:
        out.append({"motivo": "FROTA_PROPRIA", "prioridade": 60,
                    "resumo": f"tem frota própria de {c['frota_propria']} carros",
                    "dados": {"frota_propria": c["frota_propria"]}})
    if c.get("produto_atual") == "AM" and (c.get("km_mes") or 0) > FRANQUIA_KM:
        out.append({"motivo": "KM_ACIMA_FRANQUIA", "prioridade": 50,
                    "resumo": f"roda cerca de {c['km_mes']} km/mês por carro, acima da franquia de {FRANQUIA_KM} km",
                    "dados": {"km_mes": c["km_mes"], "franquia_km": FRANQUIA_KM, "qtd": qtd, "modelo": modelo}})
    if not out:
        out.append({"motivo": "RELACIONAMENTO", "prioridade": 20, "resumo": f"cliente com {qtd} {modelo} ({c.get('produto_atual')})".strip(),
                    "dados": {"qtd": qtd, "modelo": modelo}})
    for m in out:
        m["titulo"] = NOMES_MOTIVO[m["motivo"]]
    return sorted(out, key=lambda m: -m["prioridade"])
