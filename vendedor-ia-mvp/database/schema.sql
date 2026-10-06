PRAGMA foreign_keys = ON;

-- Mundo simulado v2: venda interna receptiva, só clientes cadastrados. Tudo fictício.
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
  checagem_json TEXT, criado_em TEXT, adicionais_json TEXT, total_adicionais_mensal REAL
);
CREATE TABLE IF NOT EXISTS handoffs (
  handoff_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, motivo TEXT, resumo TEXT, criado_em TEXT,
  briefing_json TEXT, status TEXT DEFAULT 'ABERTO'
);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);

-- LABORATÓRIO: rodadas de testes em lote (IA-cliente x Fernanda)
CREATE TABLE IF NOT EXISTS lab_rodadas (
  rodada_id TEXT PRIMARY KEY, nome TEXT, criado_em TEXT, inicio TEXT, fim TEXT, status TEXT, config_json TEXT
);
CREATE TABLE IF NOT EXISTS lab_execucoes (
  exec_id TEXT PRIMARY KEY, rodada_id TEXT, ordem INTEGER, cliente_id TEXT, comportamento TEXT, modo TEXT, repeticao INTEGER,
  max_turnos INTEGER, status TEXT, conversation_id TEXT, turnos INTEGER DEFAULT 0, fim_motivo TEXT, aprovado INTEGER,
  checks_json TEXT, avaliacao_json TEXT, nota_geral REAL, tokens_cliente INTEGER DEFAULT 0, custo_cliente REAL DEFAULT 0,
  erro TEXT, inicio TEXT, fim TEXT, abertura TEXT DEFAULT '1', revelados INTEGER
);

-- ATIVA: carteira de contatos ativos (a Fernanda inicia a conversa)
CREATE TABLE IF NOT EXISTS ativo_contatos (
  contato_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, motivo TEXT, motivo_json TEXT, origem TEXT,
  criado_em TEXT, follow_ups INTEGER DEFAULT 0, respondeu INTEGER DEFAULT 0, resultado TEXT, detalhe TEXT,
  retorno_em TEXT, atualizado_em TEXT
);
CREATE TABLE IF NOT EXISTS ativo_descadastros (
  cliente_id TEXT PRIMARY KEY, criado_em TEXT, origem TEXT, conversation_id TEXT
);
