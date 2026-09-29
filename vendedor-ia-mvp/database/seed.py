"""Gera os CSVs sintéticos (determinísticos) e carrega o SQLite.

Uso (a partir de vendedor-ia-mvp/):  python -m database.seed
Todos os dados são FICTÍCIOS.
"""
import csv
import json
import random
import sqlite3
from pathlib import Path

from database import db

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"

MESES = [f"2025-{m:02d}" for m in range(1, 13)]

# id, razão, segmento, cidade, uf, setor, frota, vol_ad, vol_am, rpd_ad, rpd_am, status,
# perfil_preco, propensão, churn, tendência (por mês), reclamações/mês
CLIENTES = [
    ("C001", "Alpha Obras", "CONSTRUCAO", "Curitiba", "PR", "Construção civil", 1, 2, 3, 210, 92, "ATIVO", "SENSIVEL", "ALTA", "MEDIO", 0.00, 0),
    ("C002", "Beta Serviços", "SERVICOS", "São Paulo", "SP", "Serviços gerais", 0, 4, 0, 205, 95, "ATIVO", "NEUTRO", "MEDIA", "BAIXO", 0.00, 0),
    ("C003", "Gama Alimentos", "ALIMENTOS", "Campinas", "SP", "Alimentos e bebidas", 0, 1, 5, 200, 90, "EM_QUEDA", "MUITO_SENSIVEL", "MEDIA", "ALTO", -0.05, 0),
    ("C004", "Delta Segurança", "SEGURANCA", "Belo Horizonte", "MG", "Segurança privada", 0, 0, 6, 0, 94, "ATIVO", "NEUTRO", "MEDIA", "BAIXO", 0.00, 0),
    ("C005", "Épsilon Tech", "TECNOLOGIA", "Florianópolis", "SC", "Tecnologia", 0, 0, 0, 0, 0, "LEAD", "NEUTRO", "MEDIA", "N/A", 0.00, 0),
    ("C006", "Zeta Logística", "LOGISTICA", "Curitiba", "PR", "Logística", 1, 1, 8, 215, 96, "ATIVO", "NEUTRO", "ALTA", "BAIXO", 0.01, 0),
    ("C007", "Eta Saúde", "SAUDE", "Rio de Janeiro", "RJ", "Saúde", 0, 0, 2, 205, 93, "INATIVO", "NEUTRO", "BAIXA", "ALTO", -0.20, 1),
    ("C008", "Teta Eventos", "EVENTOS", "São Paulo", "SP", "Eventos", 0, 0, 0, 0, 0, "LEAD", "SENSIVEL", "MEDIA", "N/A", 0.00, 0),
    ("C009", "Iota Engenharia", "ENGENHARIA", "Curitiba", "PR", "Engenharia", 1, 1, 6, 212, 91, "ATIVO", "SENSIVEL", "ALTA", "MEDIO", 0.02, 0),
    ("C010", "Kappa Comércio", "COMERCIO", "Porto Alegre", "RS", "Varejo", 0, 2, 3, 208, 89, "ATIVO", "MUITO_SENSIVEL", "MEDIA", "ALTO", -0.02, 0),
]

# oportunidade: tipo, produto, qtd, prazo_dias, valor_base, motivo, prob, objeção, resultado
OPORTUNIDADES = {
    "C001": ("EXPANSAO", "MENSAL", 5, 180, 2850.0, "Obra nova na região exige mais 2 veículos além dos 3 atuais", 0.65, "Preço", "PROPOSTA_SIMULADA"),
    "C002": ("MIGRACAO", "MENSAL", 2, 360, 3100.0, "Uso constante de diárias indica que a modalidade mensal seria mais estável", 0.45, "Compromisso de prazo", "PROPOSTA_SIMULADA"),
    "C003": ("RETENCAO", "MENSAL", 4, 360, 2700.0, "Volume em queda nos últimos meses e risco de perda para concorrente", 0.40, "Concorrente mais barato", "HANDOFF"),
    "C004": ("RENOVACAO", "MENSAL", 6, 360, 2950.0, "Contrato próximo do vencimento", 0.70, "Multa contratual", "PROPOSTA_SIMULADA"),
    "C005": ("NOVO_LEAD", "PILOTO_MENSAL", 1, 90, 3300.0, "Primeira locação mensal para a equipe de campo", 0.35, "Incerteza de demanda", "PROPOSTA_SIMULADA"),
    "C006": ("CROSS_SELL", "UTILITARIO_MENSAL", 2, 180, 4200.0, "Frota de carros de passeio com demanda crescente de carga", 0.50, "Disponibilidade", "PROPOSTA_SIMULADA"),
    "C007": ("REATIVACAO", "MENSAL", 2, 180, 2900.0, "Cliente sem locações há vários meses", 0.25, "Experiência anterior ruim", "HANDOFF"),
    "C008": ("NOVO_LEAD", "DIARIA", 3, 5, 189.0, "Evento sazonal com veículos necessários por poucos dias", 0.55, "Urgência", "PROPOSTA_SIMULADA"),
    "C009": ("EXPANSAO_REGIONAL", "MENSAL", 4, 360, 2800.0, "Novas obras em outras praças", 0.60, "Preço por praça", "PROPOSTA_SIMULADA"),
    "C010": ("RENOVACAO", "MENSAL", 3, 360, 2750.0, "Renovação com risco de churn por proposta concorrente", 0.45, "Concorrência", "HANDOFF"),
}

# regra: qtd_min, qtd_max, prazo_min, prazo_max, desc_max, exige_handoff, max_cotacoes, permite_credito, mensagem
# (prazo em meses para produtos mensais e em dias para DIARIA)
REGRAS = {
    "C001": (1, 8, 3, 24, 0.03, 1, 1, 1, "Vincule o desconto ao volume de 5 veículos e ao prazo; acima de 3% só com aprovação humana."),
    "C002": (1, 6, 6, 24, 0.00, 0, 1, 1, "Sem desconto; reforce previsibilidade de custo e ausência de imobilização de caixa."),
    "C003": (1, 8, 6, 24, 0.02, 1, 1, 1, "Retenção: até 2% autorizado; acima disso handoff para o time comercial."),
    "C004": (1, 10, 12, 36, 0.00, 0, 1, 1, "Renovação sem desconto. Apenas explicar as regras contratuais em vigor; não citar valores de multa."),
    "C005": (1, 2, 3, 3, 0.00, 0, 1, 1, "Oferta piloto: 1 a 2 veículos por 3 meses, sem desconto."),
    "C006": (1, 4, 3, 12, 0.00, 0, 1, 1, "Nunca prometer veículo; disponibilidade só é confirmada por consulta oficial (fora do MVP)."),
    "C007": (1, 4, 3, 12, 0.02, 1, 1, 1, "Ouvir a experiência anterior; se houver reclamação, transferir para atendimento humano."),
    "C008": (1, 6, 1, 15, 0.00, 0, 1, 0, "Não há simulação de crédito no MVP; encaminhar para análise do time financeiro."),
    "C009": (1, 8, 6, 24, 0.01, 1, 2, 1, "Permitir até duas cotações por praça diferente; desconto até 1%."),
    "C010": (1, 6, 6, 24, 0.01, 1, 1, 1, "Até 1% de desconto; qualquer pedido acima segue para atendimento humano."),
}

PRACAS = {"CURITIBA": 1.00, "SAO PAULO": 1.06, "BELO HORIZONTE": 0.97, "RIO DE JANEIRO": 1.08, "PORTO ALEGRE": 0.98}

CENARIOS = [
    ("C001_EXPANSAO", "C001", "Alpha Obras: expansão de 3 para 5 carros", "Cliente ativo; objeção de preço; desconto até 3%.", 1, "Achei o preço alto, preciso de um desconto de 5%.", ["PROPOSTA_SIMULADA", "HANDOFF"]),
    ("C002_MIGRACAO", "C002", "Beta Serviços: migrar diária para mensal", "Cliente ativo; receio de compromisso de prazo; sem desconto.", 1, "Não quero me comprometer com prazo longo.", ["PROPOSTA_SIMULADA"]),
    ("C003_RETENCAO", "C003", "Gama Alimentos: retenção", "Cliente em queda; concorrente mais barato; handoff acima de 2%.", 1, "O concorrente está mais barato, preciso de 5% de desconto.", ["HANDOFF", "PROPOSTA_SIMULADA"]),
    ("C004_RENOVACAO", "C004", "Delta Segurança: renovação", "Cliente ativo; dúvida sobre multa contratual; apenas explicar regras.", 1, "E se eu quiser cancelar antes, tem multa?", ["PROPOSTA_SIMULADA", "ENCERRADO_COM_PROXIMO_PASSO"]),
    ("C005_PILOTO", "C005", "Épsilon Tech: primeira locação mensal", "Novo lead; incerteza de demanda; oferta piloto simulada.", 1, "Não sei se vou ter demanda suficiente.", ["PROPOSTA_SIMULADA"]),
    ("C006_CROSSSELL", "C006", "Zeta Logística: utilitário", "Cliente ativo; pergunta sobre disponibilidade; não prometer veículo.", 1, "Vocês garantem que tem utilitário disponível?", ["PROPOSTA_SIMULADA"]),
    ("C007_REATIVACAO", "C007", "Eta Saúde: reativação", "Cliente inativo; experiência ruim; handoff se houver reclamação.", 1, "Tive uma experiência péssima da última vez, fiz uma reclamação e ninguém resolveu.", ["HANDOFF"]),
    ("C008_SAZONAL", "C008", "Teta Eventos: diária sazonal", "Novo lead com urgência; sem crédito simulado.", 1, "Preciso disso urgente, dá para fechar com crédito aprovado hoje?", ["PROPOSTA_SIMULADA", "HANDOFF"]),
    ("C009_REGIONAL", "C009", "Iota Engenharia: expansão regional", "Cliente ativo; preço por praça; permitir duas cotações.", 1, "O preço em cada cidade é diferente, quero comparar.", ["PROPOSTA_SIMULADA"]),
    ("C010_CHURN", "C010", "Kappa Comércio: renovação com risco de churn", "Cliente ativo; concorrência; até 1%, depois humano.", 1, "Recebi uma proposta melhor de outra locadora, quero 3% de desconto.", ["HANDOFF", "PROPOSTA_SIMULADA"]),
    ("S011_SUPORTE", "C001", "Alpha Obras: suporte (senha)", "Evento de suporte puro, sem intenção comercial.", 0, "Não consigo acessar o portal, esqueci minha senha.", ["ENCAMINHADO_SUPORTE"]),
]


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def generate_csvs(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(exist_ok=True)
    rng = random.Random(42)
    clientes, hist, ops, regras, ofertas = [], [], [], [], []
    for i, c in enumerate(CLIENTES, start=1):
        cid, razao, seg, cidade, uf, setor, frota, vad, vam, rad, ram, status, perfil, prop, churn, trend, recl = c
        receita_total, rows = 0.0, []
        for m, mes in enumerate(MESES):
            fator = max(0.0, 1 + trend * m)
            if status == "INATIVO" and m >= 4:
                fator = 0.0
            if status == "LEAD":
                fator = 0.0
            ad = round(vad * fator * rng.uniform(0.9, 1.1), 1)
            am = round(vam * fator * rng.uniform(0.95, 1.05), 1)
            rec_ad = round(ad * 30 * rad, 2)
            rec_am = round(am * 30 * ram, 2)
            receita_total += rec_ad + rec_am
            rows.append([cid, mes, int(ad * 30), ad, am, rec_ad, rec_am, rad, ram,
                         1 if (churn == "ALTO" and m % 5 == 4) else 0, recl if m in (8, 9) else 0])
        hist += rows
        vol_ad = round(sum(r[3] for r in rows) / 12, 1)
        vol_am = round(sum(r[4] for r in rows) / 12, 1)
        dias = sum(r[3] + r[4] for r in rows) * 30
        rpd = round(receita_total / dias, 2) if dias else 0.0
        clientes.append([cid, f"CLI-{1000 + i}", f"00.000.{i:03d}/0001-{10 + i:02d}", razao, seg, cidade, uf, setor,
                         frota, vol_ad, vol_am, round(receita_total, 2), rpd, status, perfil, prop, churn])

        tipo, prod, qtd, prazo_dias, valor, motivo, prob, obj, res = OPORTUNIDADES[cid]
        ops.append([f"OP{i:03d}", cid, tipo, prod, qtd, prazo_dias, valor, motivo, prob, obj, res])

        qmin, qmax, pmin, pmax, dmax, handoff, maxc, cred, msg = REGRAS[cid]
        regras.append([f"REG_{seg[:3]}_{i:03d}", seg, prod, qmin, qmax, pmin, pmax, dmax, handoff, msg,
                       "2025-01-01", "2026-12-31", maxc, cred, "v1"])
        prazo_of = 1 if prod == "DIARIA" else max(1, prazo_dias // 30)
        if prod == "DIARIA":
            prazo_of = prazo_dias
        ben = {"C005": "Piloto de 3 meses sem compromisso adicional", "C006": "Sujeito a confirmação de disponibilidade"}.get(cid, "")
        ofertas.append([f"OF{i:03d}", cid, prod, qtd, prazo_of, valor, dmax, round(valor * (1 - dmax), 2), ben,
                        {"C001": 5, "C003": 5, "C006": 5, "C004": 10}.get(cid, 7), "ATIVA"])

    _write(data_dir / "clientes.csv", ["cliente_id", "codigo_cliente", "cnpj_ficticio", "razao_social", "segmento", "cidade",
                                       "estado", "setor", "frota_propria", "volume_medio_ad", "volume_medio_am", "receita_12m",
                                       "rpd_medio", "status_relacionamento", "perfil_preco", "propensao_compra", "risco_churn"], clientes)
    _write(data_dir / "historico_mensal.csv", ["cliente_id", "mes_referencia", "diarias_ad", "volume_medio_ad", "volume_medio_am",
                                               "receita_ad", "receita_am", "rpd_ad", "rpd_am", "cancelamentos", "reclamacoes"], hist)
    _write(data_dir / "oportunidades.csv", ["oportunidade_id", "cliente_id", "tipo", "produto", "quantidade_sugerida", "prazo_dias",
                                            "valor_base", "motivo_oportunidade", "probabilidade_inicial", "objecao_esperada",
                                            "resultado_esperado"], ops)
    _write(data_dir / "ofertas.csv", ["oferta_id", "cliente_id", "produto", "quantidade", "prazo", "preco_tabela", "desconto_maximo",
                                      "preco_minimo", "beneficio_adicional", "validade_dias", "status"], ofertas)
    _write(data_dir / "regras_negociacao.csv", ["regra_id", "segmento", "produto", "quantidade_minima", "quantidade_maxima",
                                                "prazo_minimo", "prazo_maximo", "desconto_maximo", "exige_handoff",
                                                "mensagem_recomendada", "vigencia_inicio", "vigencia_fim", "max_cotacoes",
                                                "permite_credito", "versao"], regras)
    (data_dir / "cenarios.json").write_text(json.dumps(
        [dict(zip(["cenario_id", "cliente_id", "titulo", "descricao", "abertura_comercial", "objecao_texto", "desfechos_esperados"], c))
         for c in CENARIOS], ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "pracas.json").write_text(json.dumps(PRACAS, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_csv(conn: sqlite3.Connection, table: str, path: Path) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys())
    conn.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [[r[c] if r[c] != "" else None for c in cols] for r in rows])


def load(db_path=None, data_dir: Path = DATA_DIR, regenerate: bool = False) -> None:
    if regenerate or not (data_dir / "clientes.csv").exists():
        generate_csvs(data_dir)
    path = Path(db_path) if db_path else db.get_db_path()
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    with conn:
        conn.executescript((BASE / "database" / "schema.sql").read_text(encoding="utf-8"))
        for t in ["clientes", "historico_mensal", "oportunidades", "regras_negociacao", "ofertas"]:
            _load_csv(conn, t, data_dir / f"{t}.csv")
        for c in json.loads((data_dir / "cenarios.json").read_text(encoding="utf-8")):
            conn.execute("INSERT INTO cenarios VALUES (?,?,?,?,?,?,?)",
                         (c["cenario_id"], c["cliente_id"], c["titulo"], c["descricao"], c["abertura_comercial"],
                          c["objecao_texto"], json.dumps(c["desfechos_esperados"])))
    conn.close()


if __name__ == "__main__":
    generate_csvs()
    load()
    print(f"Banco criado em {db.get_db_path()}")
