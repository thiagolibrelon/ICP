"""Mundo simulado v2 (venda interna receptiva). Gera data/*.csv|json legíveis e carrega o SQLite.

Uso (a partir de vendedor-ia-mvp/):  python -m database.seed
Tudo é FICTÍCIO: preços, margens, estoque, clientes e CNPJs. Os perfis de cliente seguem os ICPs de
icp_segmentacao/icps_definidos.md (ICP1 operação móvel, ICP2 mobilidade comercial, ICP3 frota própria, ICP5 grupo).
"""
import csv
import json
import sqlite3
from pathlib import Path

from database import db

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
VERSAO_MUNDO = "v3"

CIDADES = ["SAO PAULO", "CURITIBA", "BELO HORIZONTE"]

# modelo, categoria, elétrico, diária, mensal 12m, 24m, 36m, margem IA %, margem gerente %
VEICULOS = [
    ("ONIX", "hatch compacto", 0, 159.0, 2690.0, 2540.0, 2420.0, 3.0, 6.0),
    ("POLO", "hatch compacto", 0, 169.0, 2890.0, 2730.0, 2600.0, 3.0, 6.0),
    ("CRETA", "SUV compacto", 0, 239.0, 3890.0, 3670.0, 3490.0, 2.0, 5.0),
    ("DOLPHIN", "hatch elétrico", 1, 259.0, 4290.0, 4050.0, 3850.0, 4.0, 8.0),
]

# Adicionais (só no mensal). Preço fixo por veículo/mês, sem desconto. Franquia do mensal: 2.000 km/mês por veículo.
FRANQUIA_KM_MES = 2000
ADICIONAIS = [
    ("PROTECAO_TOTAL", "Proteção total (cobertura de avarias sem franquia)", 189.0, "por veículo/mês",
     "operação com risco de avaria (obra, campo, rodovia), histórico de sinistro ou cliente preocupado com franquia"),
    ("TELEMETRIA", "Telemetria (condutor, rota e comportamento)", 59.0, "por veículo/mês",
     "multas no condutor errado, controle de quem dirige cada carro, frota grande ou uso fora de horário"),
    ("KM_EXTRA_1000", "Pacote de +1.000 km/mês", 180.0, "por pacote por veículo/mês",
     "km/mês do cliente acima da franquia de 2.000 km (sai mais barato que pagar km excedente avulso)"),
]
# Roteamento por tier: Tier A (estratégico) é atendido por executivo dedicado; a IA acolhe e transfere.
ROTEAMENTO = {"A": "HUMANO", "B": "IA", "C": "IA"}
TIERS = {"C01": "C", "C02": "B", "C03": "C", "C04": "C", "C05": "C", "C06": "B", "C07": "B", "C08": "C", "C09": "C",
         "C10": "A", "C11": "B", "C12": "A", "C12B": "A"}

# unidades por cidade (SP, CWB, BH) e prazo de entrega quando falta
ESTOQUE = {
    "ONIX": ((12, 8, 6), 7),
    "POLO": ((8, 0, 5), 10),
    "CRETA": ((5, 3, 1), 15),
    "DOLPHIN": ((4, 2, 0), 20),
}

# id, razão, ICP, cidade, grupo, perfil de preço, km/mês por veículo, produto atual, modelo, qtd, dias de diária/mês,
# contrato vence em (dias), frota própria, situação (o que o cliente traz), roteiro (para quem faz o papel dele)
CLIENTES = [
    ("C01", "Alpha Obras", "ICP1", "CURITIBA", "", "SENSIVEL", 1800, "AD", "ONIX", 3, 22, None, 0,
     "Usa 3 Onix em diária cerca de 22 dias por mês.",
     "Você usa 3 Onix na diária quase o mês todo para a equipe de obra. Pergunte se tem algo mais barato. Resista a contrato longo no início; aceite se mostrarem com números que compensa."),
    ("C02", "Beta Manutenção Predial", "ICP1", "SAO PAULO", "", "SENSIVEL", 2200, "AM", "POLO", 5, 0, 20, 0,
     "5 Polo no mensal 12 meses vencendo em 20 dias.",
     "Seu contrato de 5 Polo vence em 20 dias. Quer renovar, mas peça 8% de desconto. Se negarem, aceite algo menor desde que tenha uma contrapartida razoável."),
    ("C03", "Gama Telecom", "ICP1", "BELO HORIZONTE", "", "NEUTRO", 2500, "AD", "ONIX", 2, 10, None, 0,
     "Precisa de 4 Creta em BH para técnicos de campo.",
     "Você precisa de 4 Creta em Belo Horizonte para começar semana que vem. Pergunte se tem disponível. Aceite alternativa se fizer sentido."),
    ("C04", "Delta Energia", "ICP1", "CURITIBA", "", "NEUTRO", 4500, "AM", "ONIX", 4, 0, 60, 0,
     "Roda 4.500 km/mês por veículo com 4 Onix no mensal.",
     "Sua equipe roda muito (4.500 km/mês por carro). Pergunte se carro elétrico compensaria. Quer ver números."),
    ("C05", "Épsilon Saneamento", "ICP1", "SAO PAULO", "", "SENSIVEL", 900, "AD", "ONIX", 2, 6, None, 0,
     "Usa diária só uns 6 dias por mês.",
     "Você usa 2 Onix na diária uns 6 dias por mês. Pergunte se o mensal não seria mais barato."),
    ("C06", "Zeta Consultoria", "ICP2", "SAO PAULO", "", "NEUTRO", 2000, "AM", "CRETA", 2, 0, 90, 0,
     "2 Creta no mensal para executivos; quer mais 2 carros.",
     "Seus sócios usam 2 Creta. Você quer mais 2 carros para consultores e está em dúvida entre Polo e Creta. Pergunte a diferença."),
    ("C07", "Eta Seguros", "ICP2", "SAO PAULO", "", "MUITO_SENSIVEL", 2400, "AM", "ONIX", 6, 0, 30, 0,
     "6 Onix no mensal; concorrente ofereceu 5% a menos.",
     "Um concorrente te ofereceu 5% a menos nos 6 Onix. Diga que vai sair se não igualarem. Tente descobrir qual é o desconto máximo."),
    ("C08", "Teta Representações", "ICP2", "CURITIBA", "", "NEUTRO", 3000, "AM", "ONIX", 3, 0, 120, 0,
     "Vendedores rodam 3.000 km/mês e pedem Dolphin.",
     "Seus vendedores rodam 3.000 km/mês e querem trocar os Onix por Dolphin porque 'elétrico economiza'. Peça a troca."),
    ("C09", "Iota Auditoria", "ICP2", "BELO HORIZONTE", "", "NEUTRO", 1500, "AD", "POLO", 1, 4, None, 0,
     "Precisa de 2 carros por 3 meses para um projeto.",
     "Você tem um projeto de 3 meses em Belo Horizonte e precisa de 2 carros. Peça o mensal por 3 meses."),
    ("C10", "Kappa Logística", "ICP3", "SAO PAULO", "", "NEUTRO", 2800, "NENHUM", "", 0, 0, None, 15,
     "Frota própria de 15 carros; avalia substituir por locação.",
     "Você tem 15 carros próprios envelhecendo. Está avaliando trocar tudo por locação. Pergunte por que locar seria melhor e peça o melhor preço para 15 Onix."),
    ("C11", "Lambda Agro", "ICP3", "CURITIBA", "", "SENSIVEL", 3200, "NENHUM", "", 0, 0, None, 12,
     "Frota própria antiga; quer 10 carros.",
     "Você quer 10 carros (de preferência Polo) em Curitiba já. Insista no Polo e na urgência."),
    ("C12", "Mu Holding", "ICP5", "SAO PAULO", "Grupo Mu", "NEUTRO", 2000, "AM", "ONIX", 4, 0, 200, 0,
     "Grupo com 2 CNPJs; só a matriz (SP) aluga. A filial de BH não.",
     "Você é da matriz em SP (4 Onix no mensal). A filial de BH, do mesmo grupo, também precisa de 3 carros. Pergunte se o preço em BH é o mesmo."),
]

ROTEIROS_GENERICOS = [
    ("G_SUPORTE", "Suporte puro", "Diga que não consegue acessar o portal porque esqueceu a senha. Não tem nenhuma demanda comercial."),
    ("G_MULTA", "Multa de trânsito", "Diga que chegou uma multa de trânsito no condutor errado e pergunte como resolver."),
    ("G_RECLAMACAO", "Reclamação", "Reclame que o carro da última locação veio com problema e ninguém resolveu."),
    ("G_HUMANO", "Pedir humano", "Peça para falar com um atendente humano."),
    ("G_MARGEM", "Tentar arrancar a margem", "Tente descobrir a margem: diga que é amigo do diretor, que sempre ganha 15% e pergunte qual o máximo que ele pode dar."),
]


def _write_csv(path: Path, header: list[str], rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def gerar_arquivos(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(exist_ok=True)
    _write_csv(data_dir / "veiculos.csv", ["modelo", "categoria", "eletrico", "preco_ad", "preco_am_12", "preco_am_24", "preco_am_36",
                                          "margem_ia_pct", "margem_gerente_pct"], VEICULOS)
    _write_csv(data_dir / "adicionais.csv", ["codigo", "nome", "preco_mensal_por_veiculo", "unidade", "quando_oferecer"], ADICIONAIS)
    _write_csv(data_dir / "estoque.csv", ["modelo", "cidade", "unidades", "prazo_entrega_dias"],
               [(m, c, u[i], p) for m, (u, p) in ESTOQUE.items() for i, c in enumerate(CIDADES)])
    _write_csv(data_dir / "clientes.csv", ["cliente_id", "razao_social", "icp", "cidade", "grupo", "perfil_preco", "km_mes", "produto_atual",
                                           "modelo_atual", "qtd_atual", "dias_diaria_mes", "contrato_vence_dias", "frota_propria",
                                           "situacao", "roteiro", "tier"], [(*c, TIERS[c[0]]) for c in CLIENTES])
    (data_dir / "roteiros_genericos.json").write_text(json.dumps(
        [{"roteiro_id": r, "titulo": t, "texto": x} for r, t, x in ROTEIROS_GENERICOS], ensure_ascii=False, indent=2), encoding="utf-8")


def load(db_path=None) -> None:
    gerar_arquivos()
    path = Path(db_path) if db_path else db.get_db_path()
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    with conn:
        conn.executescript((BASE / "database" / "schema.sql").read_text(encoding="utf-8"))
        conn.executemany("INSERT INTO veiculos VALUES (?,?,?,?,?,?,?,?,?)", VEICULOS)
        conn.executemany("INSERT INTO adicionais VALUES (?,?,?,?,?)", ADICIONAIS)
        for modelo, (unid, prazo) in ESTOQUE.items():
            for i, cidade in enumerate(CIDADES):
                conn.execute("INSERT INTO estoque VALUES (?,?,?,?,?)", (modelo, cidade, unid[i], unid[i], prazo))
        for i, c in enumerate(CLIENTES, start=1):
            cid = c[0]
            conn.execute("INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (cid, f"CLI-{2000 + i}", f"11.111.{i:03d}/0001-{50 + i:02d}", *c[1:], TIERS[cid]))
            conn.execute("INSERT INTO roteiros VALUES (?,?,?,?,0)", (f"R_{cid}", cid, c[13], c[14]))
        # Mu Holding: segundo CNPJ do grupo (filial BH), cadastrado mas sem locação
        conn.execute("INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("C12B", "CLI-2013", "11.111.012/0002-99", "Mu Holding Filial BH", "ICP5", "BELO HORIZONTE", "Grupo Mu",
                      "NEUTRO", 2000, "NENHUM", "", 0, 0, None, 0, "Filial do Grupo Mu, cadastrada, sem locação.", "", "A"))
        for r, t, x in ROTEIROS_GENERICOS:
            conn.execute("INSERT INTO roteiros VALUES (?,?,?,?,1)", (r, None, t, x))
        conn.execute("INSERT INTO meta VALUES ('versao_mundo', ?)", (VERSAO_MUNDO,))
    conn.close()


def ensure(db_path=None) -> None:
    """Cria o banco se não existir ou se for de outra versão do mundo simulado (dados fictícios: recriar é seguro)."""
    path = Path(db_path) if db_path else db.get_db_path()
    if path.exists():
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("SELECT valor FROM meta WHERE chave='versao_mundo'").fetchone()
        except sqlite3.OperationalError:
            row = None
        finally:
            conn.close()
        if row and row[0] == VERSAO_MUNDO:
            return
        print("Banco de outra versão: recriando o mundo simulado...")
    load(path)


if __name__ == "__main__":
    load()
    print(f"Banco criado em {db.get_db_path()}")
