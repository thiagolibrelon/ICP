PRAGMA foreign_keys = ON;

-- Mundo simulado do Treino (cópia própria; tudo fictício). Evolui separado do mundo da Fernanda.
CREATE TABLE IF NOT EXISTS clientes (
  cliente_id TEXT PRIMARY KEY, codigo TEXT UNIQUE, cnpj TEXT UNIQUE, razao_social TEXT, icp TEXT, cidade TEXT,
  grupo TEXT, perfil_preco TEXT, km_mes INTEGER, produto_atual TEXT, modelo_atual TEXT, qtd_atual INTEGER,
  dias_diaria_mes INTEGER, contrato_vence_dias INTEGER, frota_propria INTEGER, situacao TEXT, roteiro TEXT, tier TEXT
);
CREATE TABLE IF NOT EXISTS veiculos (
  modelo TEXT PRIMARY KEY, categoria TEXT, eletrico INTEGER, preco_ad REAL, preco_am_12 REAL, preco_am_24 REAL,
  preco_am_36 REAL, margem_ia_pct REAL, margem_gerente_pct REAL
);
CREATE TABLE IF NOT EXISTS adicionais (
  codigo TEXT PRIMARY KEY, nome TEXT, preco_mensal_por_veiculo REAL, unidade TEXT, quando_oferecer TEXT
);
CREATE TABLE IF NOT EXISTS estoque (
  modelo TEXT REFERENCES veiculos(modelo), cidade TEXT, unidades_iniciais INTEGER, unidades INTEGER,
  prazo_entrega_dias INTEGER, PRIMARY KEY (modelo, cidade)
);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);

-- MODO TREINO: vendedor humano x cliente simulado pelo GPT
CREATE TABLE IF NOT EXISTS treinos (
  treino_id TEXT PRIMARY KEY, vendedor TEXT, cliente_id TEXT, modo TEXT, dificuldade TEXT, inicio TEXT, fim TEXT,
  status TEXT, estado_json TEXT, resultado_json TEXT, nota_geral REAL
);
CREATE TABLE IF NOT EXISTS treino_mensagens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, treino_id TEXT, timestamp TEXT, role TEXT, conteudo TEXT, meta_json TEXT
);
