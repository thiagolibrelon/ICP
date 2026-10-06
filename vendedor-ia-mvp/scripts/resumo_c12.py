"""Resumo AGREGADO do classificador C12 (ligações reais) para a referência do time (roadmap S1-03).

Roda na máquina do time, sobre o JSON consolidado do classificar_ligacoes_diario.py:
    python scripts/resumo_c12.py classificacao_setembro_2026_consolidado.json
Gera só números (contagens e percentuais): nenhum trecho, transcrição, nome ou identificador de ligação sai daqui.
Usa só ligações com o formato C12 ("foco": P1.era_venda, P2, P3, P5).
"""
import json
import sys
from collections import Counter
from pathlib import Path

PROBLEMAS = {"P1": "Acesso/sistema", "P2": "Faturamento/cobrança", "P3": "Multa/infração", "P4": "Manutenção/substituto",
             "P5": "Condutor/cadastro", "P6": "Km excedente", "P7": "Disponibilidade", "P8": "Franquia/agência", "P9": "Sinistro",
             "P10": "Reserva/sistema", "P11": "Outro", "P12": "Manipulação de pesquisa/NPS", "P13": "Crédito/cadastro PJ",
             "P14": "Preço/competitividade", "P15": "Tag de pedágio"}
CHALLENGER = {"CH1": "Custo oculto revelado", "CH2": "ROI calculado", "CH3": "Urgência por regra real",
              "CH4": "Concorrente/alternativa superado com dado", "CH5": "Dor conectada a produto",
              "CH6": "Antecipação de problema", "CH7": "Necessidade não declarada descoberta"}
VENDA = {"nova_venda", "renovacao", "upsell", "misto", "retencao"}


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def bloco(regs):
    n = len(regs)
    p1 = [r["classificacao"]["P1"] for r in regs]
    p2 = [r["classificacao"]["P2"] for r in regs]
    p3 = [r["classificacao"]["P3"] for r in regs]
    p5 = [r["classificacao"]["P5"] for r in regs]
    venda = [i for i, x in enumerate(p1) if x.get("era_venda") == "SIM"]
    fechou = sum(1 for i in venda if p1[i].get("desfecho") in ("fechou_novo", "fechou_renovacao"))
    ch = [x for x in p5 if x.get("teve_challenger") == "SIM"]
    cods = Counter(c for x in ch for c in x.get("codigos_challenger") or [])
    probs = Counter(c for x in p3 for c in x.get("problemas_identificados") or [])
    com_prob = [x for x in p3 if x.get("tem_problema") == "SIM"]
    return {
        "ligacoes": n,
        "tipo_de_ligacao_pct": {k: pct(v, n) for k, v in Counter(x.get("tipo") for x in p2).most_common()},
        "venda": {
            "eram_venda": len(venda), "eram_venda_pct": pct(len(venda), n),
            "desfecho_nas_de_venda_pct": {k: pct(v, len(venda)) for k, v in Counter(p1[i].get("desfecho") for i in venda).most_common()},
            "fechou_pct_das_de_venda": pct(fechou, len(venda)),
            "tentativa_comercial_pct_das_de_venda": pct(sum(1 for i in venda if p1[i].get("tentativa_comercial") == "SIM"), len(venda)),
            "tentativa_comercial_pct_das_que_nao_eram_venda": pct(
                sum(1 for i, x in enumerate(p1) if i not in set(venda) and x.get("tentativa_comercial") == "SIM"), n - len(venda)),
        },
        "challenger": {
            "com_dado_pct_de_todas": pct(len(ch), n),
            "com_dado_pct_das_de_venda": pct(sum(1 for i in venda if p5[i].get("teve_challenger") == "SIM"), len(venda)),
            "descartados_por_falta_de_dado": sum(1 for x in p5 if x.get("challenger_sem_dado") == "SIM"),
            "qualidade_pct_dos_challengers": {k: pct(v, len(ch)) for k, v in Counter(x.get("qualidade") for x in ch).most_common()},
            "trouxe_dado_concreto_pct": pct(sum(1 for x in p5 if x.get("trouxe_dado_concreto") == "SIM"), n),
            "conectou_a_situacao_do_cliente_pct": pct(sum(1 for x in p5 if x.get("conectou_a_situacao_do_cliente") == "SIM"), n),
            "cliente_reagiu_pct": pct(sum(1 for x in p5 if x.get("cliente_reagiu") == "SIM"), n),
            "tipos_pct_dos_challengers": {f"{k} {CHALLENGER.get(k, '')}": pct(v, len(ch)) for k, v in cods.most_common()},
        },
        "problemas": {
            "com_problema_pct": pct(len(com_prob), n),
            "resolvido_na_ligacao_pct_dos_problemas": {k: pct(v, len(com_prob)) for k, v in
                                                       Counter(str(x.get("foi_resolvido_na_ligacao")).upper() for x in com_prob).most_common()},
            "mais_frequentes_pct_das_ligacoes": {f"{k} {PROBLEMAS.get(k, '')}": pct(v, n) for k, v in probs.most_common(8)},
        },
    }


def resumir(caminho):
    d = json.load(open(caminho, encoding="utf-8"))
    todas = d["ligacoes"]
    c12 = [r for r in todas if r.get("fonte_classificacao") == "gpt" and "era_venda" in (r.get("classificacao") or {}).get("P1", {})]
    out = {
        "fonte": "classificador C12 (classificar_ligacoes_diario.py), números agregados, sem trechos nem identificadores",
        "periodo": d["_meta"].get("periodo"),
        "total_ligacoes": len(todas),
        "por_direcao": dict(Counter(r.get("direcao") for r in todas)),
        "por_fonte": dict(Counter(r.get("fonte_classificacao") for r in todas)),
        "fora_do_formato_c12": sum(1 for r in todas if r.get("fonte_classificacao") == "gpt") - len(c12),
        "modelos_do_classificador": dict(Counter(r.get("modelo") for r in c12)),
        "receptivas_inbound": bloco([r for r in c12 if r.get("direcao") == "Inbound"]),
        "receptivas_inbound_so_venda": bloco([r for r in c12 if r.get("direcao") == "Inbound"
                                              and r["classificacao"]["P2"].get("tipo") in VENDA]),
        "ativas_outbound": bloco([r for r in c12 if r.get("direcao") == "Outbound"]),
        "por_modelo_do_classificador": {m: bloco([r for r in c12 if r.get("modelo") == m and r.get("direcao") == "Inbound"])
                                         for m in sorted({r.get("modelo") for r in c12})},
    }
    # Referência recomendada: receptivas de venda, classificadas pelo MESMO modelo que a Fernanda usa (a régua muda com o modelo)
    modelo_ref = "gpt-5.4-mini"
    ref = [r for r in c12 if r.get("direcao") == "Inbound" and r.get("modelo") == modelo_ref
           and r["classificacao"]["P2"].get("tipo") in VENDA]
    datas = sorted(r.get("data") for r in ref)
    out["referencia_recomendada"] = {"criterio": f"Inbound, ligações de venda (nova venda, renovação, upsell, misto, retenção), classificadas por {modelo_ref}",
                                     "periodo_efetivo": f"{datas[0]} a {datas[-1]}" if datas else None, **bloco(ref)}
    return out


if __name__ == "__main__":
    origem = Path(sys.argv[1])
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else origem.with_name(origem.stem + "_resumo.json")
    destino.write_text(json.dumps(resumir(origem), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resumo agregado salvo em {destino}")
