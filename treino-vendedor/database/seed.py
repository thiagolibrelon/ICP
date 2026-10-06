"""Mundo simulado do Treino: catálogo, estoque e os 30 clientes das personas. Carrega o SQLite do Treino.

Uso (a partir de treino-vendedor/):  python -m database.seed
Nasceu como cópia do mundo do vendedor-ia-mvp (Fernanda); as duas frentes evoluem separadas.
Tudo é FICTÍCIO: preços, margens, estoque, clientes e CNPJs. Os perfis de cliente seguem os ICPs de
icp_segmentacao/icps_definidos.md (ICP1 operação móvel, ICP2 mobilidade comercial, ICP3 frota própria, ICP5 grupo).
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from database import db

BASE = Path(__file__).resolve().parent.parent
VERSAO_MUNDO = "treino-v1"  # 30 clientes

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
         "C10": "A", "C11": "B", "C12": "A", "C12B": "A",
         "C13": "B", "C14": "C", "C15": "B", "C16": "B", "C17": "C", "C18": "C", "C19": "C", "C20": "C", "C21": "C",
         "C22": "B", "C23": "B", "C24": "C", "C25": "C", "C26": "C", "C27": "B", "C28": "C", "C29": "B", "C30": "C"}

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
    # C13–C30 (v5): ampliam o mundo para a trilha de treinamento. Cada um exercita competências que o C12 mede nas ligações
    # reais: suporte que vira oportunidade, churn, concorrência, promessa, objeções OB1–OB7, janelas de adicional.
    ("C13", "Nu Farmacêutica", "ICP2", "SAO PAULO", "", "NEUTRO", 1800, "AM", "POLO", 8, 0, 150, 0,
     "8 Polo no mensal para propagandistas; liga por causa de uma multa.",
     "Você liga só por causa de uma multa que veio no condutor errado. Quer saber como resolver. Não fale de compra a menos que perguntem sobre a frota ou os planos da empresa."),
    ("C14", "Xi Construtora", "ICP1", "BELO HORIZONTE", "", "SENSIVEL", 2600, "AM", "ONIX", 6, 0, 45, 0,
     "6 Onix no mensal em obras; um carro bateu no canteiro.",
     "Um dos seus Onix bateu no canteiro de obra e você quer saber quanto vai pagar. Reclame que a franquia pesa. Ache a proteção total cara até mostrarem a conta."),
    ("C15", "Ômicron Distribuidora", "ICP1", "CURITIBA", "", "MUITO_SENSIVEL", 2100, "AM", "ONIX", 10, 0, 25, 0,
     "10 Onix no mensal; reclamou de carro substituto que demorou; contrato vence em 25 dias.",
     "Você está irritado: o carro substituto demorou 5 dias e prometeram retorno que nunca veio. Diga que outra locadora está te procurando. Só fala de renovação se sentir que vão resolver."),
    ("C16", "Pi Alimentos", "ICP3", "SAO PAULO", "", "NEUTRO", 2300, "AM", "ONIX", 4, 0, 200, 8,
     "4 Onix locados e 8 carros próprios.",
     "Você tem 4 Onix locados e 8 carros próprios. Ligou para incluir um condutor. Se perguntarem da frota própria, conte que os carros dão muita manutenção, mas diga que o financeiro prefere comprar."),
    ("C17", "Rô Engenharia", "ICP1", "BELO HORIZONTE", "", "NEUTRO", 1200, "AD", "CRETA", 2, 18, None, 0,
     "Usa 2 Creta na diária cerca de 18 dias por mês.",
     "Você usa 2 Creta na diária quase todo dia útil. Peça só para estender a diária de novo. Resista a contrato: 'o projeto pode acabar'."),
    ("C18", "Sigma Tecnologia", "ICP2", "SAO PAULO", "", "NEUTRO", 1500, "AM", "CRETA", 3, 0, 300, 0,
     "3 Creta no mensal; trocou o responsável pela frota há pouco.",
     "Você acabou de assumir a frota e não conhece o contrato. Ligou para se apresentar e entender o que tem. Não precisa de nada agora."),
    ("C19", "Tau Agronegócio", "ICP3", "CURITIBA", "", "SENSIVEL", 3800, "AM", "POLO", 5, 0, 70, 0,
     "5 Polo no mensal; agrônomos rodam 3.800 km/mês por carro.",
     "Você reclama que a fatura veio com km excedente alto de novo. Pergunte se tem como baixar o valor."),
    ("C20", "Úpsilon Clínicas", "ICP2", "BELO HORIZONTE", "", "NEUTRO", 1600, "AM", "POLO", 4, 0, 10, 0,
     "4 Polo no mensal; contrato vence em 10 dias; liga por um boleto.",
     "Você liga por uma dúvida no boleto. Não sabe que o contrato vence em 10 dias. Se avisarem, agradeça e queira renovar sem complicação."),
    ("C21", "Fi Eventos", "ICP1", "SAO PAULO", "", "SENSIVEL", 800, "AD", "ONIX", 3, 5, None, 0,
     "Usa diária poucos dias por mês; vai precisar de 10 carros num evento.",
     "Você usa diária poucos dias por mês. Agora tem um evento grande e vai precisar de 10 carros por 4 dias, mas o seu cliente ainda não confirmou. Diga 'vou confirmar e te aviso'."),
    ("C22", "Chi Logística Urbana", "ICP1", "SAO PAULO", "", "NEUTRO", 2400, "AM", "DOLPHIN", 6, 0, 120, 0,
     "6 Dolphin no mensal; cliente satisfeito; operação crescendo.",
     "Você está muito satisfeito com os Dolphin. Ligou para tirar dúvida de recarga. Se perguntarem, conte que vai abrir uma nova rota e que uma empresa parceira quer conhecer a locadora."),
    ("C23", "Psi Cosméticos", "ICP2", "CURITIBA", "", "MUITO_SENSIVEL", 2000, "AM", "POLO", 7, 0, 40, 0,
     "7 Polo no mensal; recebeu proposta de concorrente com telemetria inclusa.",
     "Um concorrente te ofereceu os Polo com telemetria 'de graça'. Peça para cobrirem. Tente arrancar o desconto máximo e diga que conhece o diretor."),
    ("C24", "Ômega Serviços", "ICP1", "BELO HORIZONTE", "", "NEUTRO", 2000, "NENHUM", "", 0, 0, None, 0,
     "Prospect: veio por indicação; nunca alugou.",
     "Você nunca alugou carro para a empresa. Um conhecido indicou. Pergunte 'quanto custa um carro por mês' logo de cara. Tem 5 técnicos de manutenção que hoje usam o carro próprio com reembolso."),
    ("C25", "Órion Transportes", "ICP3", "SAO PAULO", "", "NEUTRO", 2500, "AM", "ONIX", 2, 0, 200, 0,
     "2 Onix no mensal para supervisores; frota própria de caminhões.",
     "Você pede caminhões para a sua operação. Se disserem que não tem, pergunte o que tem. Seus supervisores usam carro próprio e reclamam."),
    ("C26", "Vega Alimentos", "ICP1", "CURITIBA", "", "SENSIVEL", 1900, "AM", "ONIX", 5, 0, 60, 0,
     "5 Onix no mensal; quer 3 carros a mais para a equipe de vendas.",
     "Você quer 3 carros a mais, mas tudo precisa passar pelo financeiro. Peça 'manda por e-mail que eu vejo'. Não diga quando o financeiro decide a menos que perguntem."),
    ("C27", "Atlas Engenharia", "ICP1", "SAO PAULO", "", "NEUTRO", 3000, "AM", "CRETA", 3, 0, 15, 0,
     "3 Creta no mensal; contrato vence em 15 dias.",
     "Seu contrato vence em 15 dias. Diga que vai deixar vencer e ficar na diária enquanto decide se renova."),
    ("C28", "Lyra Saúde", "ICP2", "BELO HORIZONTE", "", "NEUTRO", 1400, "AM", "ONIX", 2, 0, 100, 0,
     "2 Onix no mensal; reclamação de cobrança em duplicidade.",
     "Você está bravo: a fatura veio cobrada em dobro. Exija solução. Se tentarem vender alguma coisa antes de resolver, fique mais irritado."),
    ("C29", "Draco Segurança", "ICP1", "CURITIBA", "", "NEUTRO", 2800, "AD", "CRETA", 4, 25, None, 0,
     "Usa 4 Creta na diária cerca de 25 dias por mês, rodando 24 h.",
     "Você usa 4 Creta na diária quase o mês todo para rondas. Diga que 'sempre foi assim e funciona'. Só muda se mostrarem a conta."),
    ("C30", "Cassini Educação", "ICP2", "SAO PAULO", "", "SENSIVEL", 1000, "AM", "POLO", 3, 0, 75, 0,
     "3 Polo no mensal; escolas entram em férias.",
     "Você quer devolver 2 dos 3 Polo porque as escolas entram em férias. Diga que está gastando à toa."),
]

def _versao_do_banco(path: Path) -> str | None:
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("SELECT valor FROM meta WHERE chave='versao_mundo'").fetchone()
        finally:
            conn.close()
        return row[0] if row else None
    except sqlite3.Error:
        return None


def backup_antes_de_recriar(path: Path) -> Path | None:
    """Nunca apaga o banco sem guardar uma cópia: treinos e notas ficam em database/backups."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    destino = path.parent / "backups" / f"{path.stem}_{datetime.now():%Y-%m-%d_%H%M%S}_{_versao_do_banco(path) or 'sem-versao'}{path.suffix}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destino)
    print(f"Backup do banco anterior salvo em: {destino}")
    return destino


def load(db_path=None) -> None:
    path = Path(db_path) if db_path else db.get_db_path()
    if path.exists():
        backup_antes_de_recriar(path)
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
        # Mu Holding: segundo CNPJ do grupo (filial BH), cadastrado mas sem locação
        conn.execute("INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("C12B", "CLI-2112", "11.111.012/0002-99", "Mu Holding Filial BH", "ICP5", "BELO HORIZONTE", "Grupo Mu",
                      "NEUTRO", 2000, "NENHUM", "", 0, 0, None, 0, "Filial do Grupo Mu, cadastrada, sem locação.", "", "A"))
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
        print("Banco de outra versão: recriando o mundo simulado (com backup)...")
    load(path)


if __name__ == "__main__":
    load()
    print(f"Banco criado em {db.get_db_path()}")
