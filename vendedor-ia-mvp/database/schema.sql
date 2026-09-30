PRAGMA foreign_keys = ON;

-- Mundo simulado v2: venda interna receptiva, só clientes cadastrados. Tudo fictício.
CREATE TABLE IF NOT EXISTS clientes (
  cliente_id TEXT PRIMARY KEY, codigo TEXT UNIQUE, cnpj TEXT UNIQUE, razao_social TEXT, icp TEXT, cidade TEXT,
  grupo TEXT, perfil_preco TEXT, km_mes INTEGER, produto_atual TEXT, modelo_atual TEXT, qtd_atual INTEGER,
  dias_diaria_mes INTEGER, contrato_vence_dias INTEGER, frota_propria INTEGER, situacao TEXT, roteiro TEXT
);
CREATE TABLE IF NOT EXISTS veiculos (
  modelo TEXT PRIMARY KEY, categoria TEXT, eletrico INTEGER, preco_ad REAL, preco_am_12 REAL, preco_am_24 REAL,
  preco_am_36 REAL, margem_ia_pct REAL, margem_gerente_pct REAL
);
CREATE TABLE IF NOT EXISTS estoque (
  modelo TEXT REFERENCES veiculos(modelo), cidade TEXT, unidades_iniciais INTEGER, unidades INTEGER,
  prazo_entrega_dias INTEGER, PRIMARY KEY (modelo, cidade)
);
CREATE TABLE IF NOT EXISTS roteiros (
  roteiro_id TEXT PRIMARY KEY, cliente_id TEXT, titulo TEXT, texto TEXT, generico INTEGER
);
CREATE TABLE IF NOT EXISTS conversas (
  conversation_id TEXT PRIMARY KEY, cliente_id TEXT REFERENCES clientes(cliente_id), modo TEXT, livre INTEGER,
  roteiro_id TEXT, inicio TEXT, fim TEXT, status TEXT, desfecho TEXT, estoque_inicio_json TEXT, estado_json TEXT
);
CREATE TABLE IF NOT EXISTS mensagens (
  message_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT REFERENCES conversas(conversation_id),
  timestamp TEXT, role TEXT, conteudo TEXT, tokens_entrada INTEGER, tokens_saida INTEGER, custo_gate REAL,
  auditoria_json TEXT
);
CREATE TABLE IF NOT EXISTS propostas (
  proposta_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, modo TEXT, modelo TEXT, cidade TEXT,
  produto TEXT, quantidade INTEGER, prazo_meses INTEGER, dias INTEGER, desconto_pct REAL, preco_unitario REAL,
  total_mensal REAL, total REAL, aprovado_por TEXT, unidades_reservadas INTEGER, entrega_futura INTEGER,
  checagem_json TEXT, criado_em TEXT
);
CREATE TABLE IF NOT EXISTS handoffs (
  handoff_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, motivo TEXT, resumo TEXT, criado_em TEXT
);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
