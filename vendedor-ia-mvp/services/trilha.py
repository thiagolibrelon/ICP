"""Trilha de treinamento do vendedor: competências, de onde cada uma vem nos 15 prompts de análise de ligações e quais
cenários do Treino a exercitam.

Os 15 prompts medem as ligações reais (o C12 roda hoje P1+P2, P3 e P5). A trilha usa as MESMAS taxonomias (B, CH, OB/R,
AB/FC, PM, OP, PR, IC) para treinar: o que o classificador mede na ligação real é o que o vendedor pratica no Treino.
P13 (padrões emergentes) e P14 (o que os melhores fazem) não viram módulo: são exploratórios, rodam sobre a base inteira e
servem ao gestor para atualizar a trilha (ex.: um comportamento novo dos melhores vira exercício).
"""
import json

from database import db
from database.personas import PERSONAS

# ordem = ordem sugerida da trilha (do básico ao avançado)
COMPETENCIAS = [
    {"id": "abertura", "nome": "Abertura e contexto",
     "prompts": ["P9", "P2"], "codigos": ["AB1", "AB2", "AB3", "AB4", "AB5"],
     "objetivo": "Abrir dizendo quem é e por que está falando (AB1), usar o nome, mostrar que consultou a conta e fazer uma "
                 "pergunta de diagnóstico, não de confirmação. Evitar a abertura genérica (AB3) e a reativa (AB4).",
     "dimensoes_da_nota": ["tom", "diagnostico"],
     "observacao": "Todo cenário na frente ATIVA exercita a abertura (o vendedor começa)."},
    {"id": "diagnostico", "nome": "Diagnóstico e qualificação",
     "prompts": ["P1", "P12"], "codigos": ["B1", "B3", "B9", "B10"],
     "objetivo": "Perguntar antes de apresentar produto (B1), usar o histórico do cliente (B3), perguntar sobre frota própria "
                 "e concorrência (B10), descobrir quem decide e quando. Perguntas abertas; o cliente fala mais que o vendedor.",
     "dimensoes_da_nota": ["diagnostico", "qualificacao"]},
    {"id": "challenger", "nome": "Challenger com dado",
     "prompts": ["P5"], "codigos": ["CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7"],
     "objetivo": "Ensinar algo que o cliente não sabia, adaptado à situação dele e SEMPRE com dado concreto (número, prazo, "
                 "regra, valor). Régua C12: trouxe dado, conectou ao que o cliente disse nesta conversa, o cliente reagiu.",
     "dimensoes_da_nota": ["challenger"]},
    {"id": "objecoes", "nome": "Tratamento de objeções",
     "prompts": ["P8"], "codigos": ["OB1", "OB2", "OB3", "OB4", "OB5", "OB6", "OB7", "R1", "R2", "R3", "R4", "R5", "R6"],
     "objetivo": "Validar e explorar o que está por trás (R1), usar dado do cliente (R2) e urgência verdadeira (R3). "
                 "Não capitular sem explorar (R5) nem argumentar sem ouvir (R6).",
     "dimensoes_da_nota": ["objecoes"]},
    {"id": "portfolio", "nome": "Portfólio e janelas de oferta",
     "prompts": ["P7", "P6"], "codigos": ["OP2", "OP6", "B5"],
     "objetivo": "Reconhecer a janela (o cliente disse algo que se conecta a um produto) e oferecer o adicional ligado à dor "
                 "(B5): multa no condutor errado → telemetria; avaria → proteção; km acima da franquia → pacote de km.",
     "dimensoes_da_nota": ["adicionais", "challenger"]},
    {"id": "suporte_oportunidade", "nome": "Suporte que vira oportunidade",
     "prompts": ["P3", "P6"], "codigos": ["OP1", "OP8", "P1–P15 (problemas)"],
     "objetivo": "Resolver ou encaminhar o problema primeiro, sem escalar à toa (OP8), e só então fazer a pergunta comercial "
                 "que a ligação de suporte abre (evitar OP1: resolveu e desligou sem perguntar nada).",
     "dimensoes_da_nota": ["tom", "diagnostico", "adicionais"]},
    {"id": "fechamento", "nome": "Fechamento e promessas",
     "prompts": ["P9", "P10", "P6"], "codigos": ["FC1", "FC2", "FC3", "FC4", "FC5", "PM1", "PM2", "PM3", "PM4", "PM5", "PM6", "OP3"],
     "objetivo": "Fechar com compromisso duplo (FC1: o que o vendedor faz, o que o cliente faz e até quando). Toda promessa "
                 "com prazo e rastreável; nada de 'se precisar me chama' (FC3) ou fechamento aberto (FC4).",
     "dimensoes_da_nota": ["fechamento"]},
    {"id": "conta", "nome": "Saúde da conta, concorrência e retenção",
     "prompts": ["P4", "P11", "P15", "P6"], "codigos": ["IC1", "IC2", "IC3", "IC4", "IC5", "IC6", "IC7", "R1–R5 (eventos raros)", "OP4", "OP5", "OP7"],
     "objetivo": "Ler sinais de risco e de expansão: concorrente na mesa, insatisfação, troca de gestor, crescimento. "
                 "Sondar concorrência, pedir indicação a cliente satisfeito (OP4) e não deixar churn passar (OP7).",
     "dimensoes_da_nota": ["diagnostico", "objecoes", "fechamento"]},
    {"id": "margem", "nome": "Disciplina de margem e alçada",
     "prompts": [], "codigos": [],
     "objetivo": "Usar a calculadora antes de falar preço, trocar desconto por contrapartida (24 meses ou 5+ carros) e "
                 "nunca revelar limite. Regra do sistema, não vem dos prompts de análise.",
     "dimensoes_da_nota": ["disciplina_margem"]},
]
POR_ID = {c["id"]: c for c in COMPETENCIAS}

# Níveis da trilha, por competência. Só conta PROVA (sem coach) num cenário da competência, na dificuldade do nível ou
# acima. Prova aprovada = nota geral e nota da dimensão principal da competência ≥ nota mínima.
NIVEIS = [
    {"id": "bronze", "nome": "Bronze", "dificuldade": "facil", "nota_minima": 6.0, "provas": 1, "ativa": False,
     "regra": "1 prova aprovada com nota ≥ 6, dificuldade fácil ou acima."},
    {"id": "prata", "nome": "Prata", "dificuldade": "medio", "nota_minima": 7.0, "provas": 1, "ativa": False,
     "regra": "1 prova aprovada com nota ≥ 7, dificuldade média ou acima."},
    {"id": "ouro", "nome": "Ouro", "dificuldade": "dificil", "nota_minima": 8.0, "provas": 2, "ativa": True,
     "regra": "2 provas aprovadas com nota ≥ 8, dificuldade difícil, pelo menos uma na frente ativa."},
]
_ORDEM_DIF = {"facil": 0, "medio": 1, "dificil": 2}

# Os 15 prompts e o papel de cada um na trilha (o que mede → onde entra)
PROMPTS = {
    "P1": ("Conversão", "diagnostico"), "P2": ("Tipo de ligação", "abertura"), "P3": ("Problemas recorrentes", "suporte_oportunidade"),
    "P4": ("Health score do cliente", "conta"), "P5": ("Comportamentos Challenger", "challenger"),
    "P6": ("Oportunidades perdidas", "portfolio"), "P7": ("Cross-sell e upsell", "portfolio"), "P8": ("Objeções", "objecoes"),
    "P9": ("Abertura e fechamento", "fechamento"), "P10": ("Promessas", "fechamento"), "P11": ("Inteligência competitiva", "conta"),
    "P12": ("Talk/listen ratio e duração", "diagnostico"), "P13": ("Surpresas e padrões emergentes", None),
    "P14": ("Diferenças entre os melhores vendedores", None), "P15": ("Eventos raros de alto impacto", "conta"),
}


def cenarios(competencia: str) -> list[str]:
    """Clientes do Treino que exercitam a competência (na ordem do cadastro)."""
    return [cid for cid, p in PERSONAS.items() if competencia in (p.get("competencias") or [])]


def mapa() -> dict:
    """A trilha inteira: competências com os cenários, níveis e o papel de cada um dos 15 prompts."""
    return {"competencias": [{**c, "cenarios": cenarios(c["id"])} for c in COMPETENCIAS],
            "niveis": NIVEIS,
            "prompts": [{"prompt": k, "nome": n, "competencia": c, "uso": "módulo da trilha" if c else "exploratório (gestor)"}
                        for k, (n, c) in PROMPTS.items()]}


def _provas(vendedor: str) -> list[dict]:
    rows = db.fetch_all("SELECT treino_id, cliente_id, dificuldade, nota_geral, estado_json, resultado_json FROM treinos "
                        "WHERE status='AVALIADO' AND modo='PROVA' AND vendedor=? ORDER BY inicio", (vendedor,))
    out = []
    for r in rows:
        estado, res = json.loads(r["estado_json"] or "{}"), json.loads(r["resultado_json"] or "{}")
        out.append({"treino_id": r["treino_id"], "cliente_id": r["cliente_id"], "dificuldade": r["dificuldade"],
                    "nota_geral": r["nota_geral"], "frente": estado.get("frente", "receptiva"),
                    "notas": {k: v.get("nota") for k, v in (res.get("dimensoes") or {}).items()}})
    return out


def _aprovada(prova: dict, comp: dict, nivel: dict) -> bool:
    if _ORDEM_DIF.get(prova["dificuldade"], -1) < _ORDEM_DIF[nivel["dificuldade"]] or prova["nota_geral"] < nivel["nota_minima"]:
        return False
    principal = next((prova["notas"][d] for d in comp["dimensoes_da_nota"] if prova["notas"].get(d) is not None), None)
    return principal is None or principal >= nivel["nota_minima"]


def progresso(vendedor: str) -> dict:
    """Nível de cada competência para um vendedor. É para o próprio desenvolvimento: não é ranking nem cobrança."""
    vendedor = (vendedor or "").strip()
    if not vendedor:
        raise ValueError("Informe o nome do vendedor")
    provas = _provas(vendedor)
    comps = []
    for c in COMPETENCIAS:
        cen = set(cenarios(c["id"]))
        if c["id"] == "abertura":  # toda prova na frente ativa exercita a abertura
            minhas = [p for p in provas if p["cliente_id"] in cen or p["frente"] == "ativa"]
        else:
            minhas = [p for p in provas if p["cliente_id"] in cen]
        nivel, proximo = None, None
        for n in NIVEIS:
            ok = [p for p in minhas if _aprovada(p, c, n)]
            if len(ok) >= n["provas"] and (not n["ativa"] or any(p["frente"] == "ativa" for p in ok)):
                nivel = n["id"]
            else:
                proximo = {"nivel": n["id"], "regra": n["regra"], "aprovadas": len(ok)}
                break
        comps.append({"id": c["id"], "nome": c["nome"], "provas": len(minhas), "nivel": nivel, "proximo": proximo,
                      "melhor_nota": max((p["nota_geral"] for p in minhas), default=None), "cenarios": sorted(cen)})
    ordem = [n["id"] for n in NIVEIS]
    alcancado = [ordem.index(c["nivel"]) for c in comps if c["nivel"]]
    # quantas competências já estão em cada nível (ou acima): "Prata em 4 de 9"
    return {"vendedor": vendedor, "provas": len(provas), "competencias": comps,
            "por_nivel": {n: sum(1 for i in alcancado if i >= ordem.index(n)) for n in ordem}, "total": len(comps)}
