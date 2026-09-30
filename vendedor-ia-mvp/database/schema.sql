PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
  cliente_id TEXT PRIMARY KEY, codigo_cliente TEXT UNIQUE, cnpj_ficticio TEXT UNIQUE,
  razao_social TEXT, segmento TEXT, cidade TEXT, estado TEXT, setor TEXT,
  frota_propria INTEGER, volume_medio_ad REAL, volume_medio_am REAL, receita_12m REAL,
  rpd_medio REAL, status_relacionamento TEXT, perfil_preco TEXT, propensao_compra TEXT,
  risco_churn TEXT
);
CREATE TABLE IF NOT EXISTS historico_mensal (
  cliente_id TEXT REFERENCES clientes(cliente_id), mes_referencia TEXT,
  diarias_ad INTEGER, volume_medio_ad REAL, volume_medio_am REAL, receita_ad REAL,
  receita_am REAL, rpd_ad REAL, rpd_am REAL, cancelamentos INTEGER, reclamacoes INTEGER
);
CREATE TABLE IF NOT EXISTS oportunidades (
  oportunidade_id TEXT PRIMARY KEY, cliente_id TEXT REFERENCES clientes(cliente_id),
  tipo TEXT, produto TEXT, quantidade_sugerida INTEGER, prazo_dias INTEGER, valor_base REAL,
  motivo_oportunidade TEXT, probabilidade_inicial REAL, objecao_esperada TEXT,
  resultado_esperado TEXT
);
CREATE TABLE IF NOT EXISTS regras_negociacao (
  regra_id TEXT PRIMARY KEY, segmento TEXT, produto TEXT, quantidade_minima INTEGER,
  quantidade_maxima INTEGER, prazo_minimo INTEGER, prazo_maximo INTEGER,
  desconto_maximo REAL, exige_handoff INTEGER, mensagem_recomendada TEXT,
  vigencia_inicio TEXT, vigencia_fim TEXT, max_cotacoes INTEGER, permite_credito INTEGER,
  versao TEXT
);
CREATE TABLE IF NOT EXISTS ofertas (
  oferta_id TEXT PRIMARY KEY, cliente_id TEXT REFERENCES clientes(cliente_id),
  produto TEXT, quantidade INTEGER, prazo INTEGER, preco_tabela REAL, desconto_maximo REAL,
  preco_minimo REAL, beneficio_adicional TEXT, validade_dias INTEGER, status TEXT
);
CREATE TABLE IF NOT EXISTS cenarios (
  cenario_id TEXT PRIMARY KEY, cliente_id TEXT, titulo TEXT, descricao TEXT,
  abertura_comercial INTEGER, objecao_texto TEXT, desfechos_esperados TEXT, meta_json TEXT
);
CREATE TABLE IF NOT EXISTS conversas (
  conversation_id TEXT PRIMARY KEY, cliente_id TEXT, inicio TEXT, fim TEXT, cenario_id TEXT,
  status TEXT, desfecho TEXT, proposta_gerada INTEGER DEFAULT 0, handoff INTEGER DEFAULT 0,
  desconto_final REAL, fora_da_alcada INTEGER DEFAULT 0, estado_json TEXT
);
CREATE TABLE IF NOT EXISTS mensagens (
  message_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT REFERENCES conversas(conversation_id),
  timestamp TEXT, role TEXT, conteudo TEXT, intencao TEXT, acao_sugerida TEXT,
  ferramenta_chamada TEXT, regra_aplicada TEXT, validacao TEXT, tokens_entrada INTEGER,
  tokens_saida INTEGER, auditoria_json TEXT
);
CREATE TABLE IF NOT EXISTS avaliacoes (
  avaliacao_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, cenario_id TEXT,
  diagnostico INTEGER, aderencia_regras INTEGER, tratamento_objecao INTEGER, proximo_passo INTEGER,
  informacao_inventada INTEGER, desconto_fora_alcada INTEGER, handoff_correto INTEGER,
  desfecho_esperado TEXT, desfecho_observado TEXT, observacoes TEXT
);
CREATE TABLE IF NOT EXISTS propostas (
  proposta_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, produto TEXT,
  quantidade INTEGER, prazo INTEGER, preco_unitario REAL, desconto REAL, validade_dias INTEGER,
  observacao TEXT, criado_em TEXT
);
CREATE TABLE IF NOT EXISTS handoffs (
  handoff_id TEXT PRIMARY KEY, conversation_id TEXT, cliente_id TEXT, motivo TEXT,
  resumo TEXT, criado_em TEXT
);
