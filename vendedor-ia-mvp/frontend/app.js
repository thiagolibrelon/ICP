let conv = null, clientes = [], roteiros = [], auditOn = true;
const $ = id => document.getElementById(id);
const api = async (url, opts) => {
  const r = await fetch(url, opts && {headers: {'Content-Type': 'application/json'}, ...opts});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {method: 'POST', body: JSON.stringify(body || {})});
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
const CIDADE = {'SAO PAULO': 'São Paulo', 'CURITIBA': 'Curitiba', 'BELO HORIZONTE': 'Belo Horizonte'};

async function init() {
  const h = await api('/api/health');
  $('llm').innerHTML = h.llm_configurado ? `<span class="ok">GPT configurado</span> · modo ${h.llm_mode}`
    : `<span class="bad">GPT não configurado</span> — o vendedor responde com mensagem de contingência`;
  [clientes, roteiros] = await Promise.all([api('/api/clientes'), api('/api/roteiros')]);
  $('cliente').innerHTML = clientes.map(c => `<option value="${c.cliente_id}">${esc(c.razao_social)} (${c.icp})</option>`).join('');
  $('cliente').onchange = preencherRoteiros; preencherRoteiros();
  estoque();
}

function preencherRoteiros() {
  const cid = $('cliente').value;
  const proprio = roteiros.filter(r => r.cliente_id === cid);
  const gen = roteiros.filter(r => r.generico);
  $('roteiro').innerHTML = [...proprio.map(r => `<option value="${r.roteiro_id}">Roteiro do cliente</option>`),
    ...gen.map(r => `<option value="${r.roteiro_id}">Roteiro: ${esc(r.titulo)}</option>`),
    '<option value="__livre">Conversa livre (sem roteiro)</option>'].join('');
}

async function estoque() {
  const e = await api('/api/estoque');
  const modelos = [...new Set(e.map(x => x.modelo))], cidades = ['SAO PAULO', 'CURITIBA', 'BELO HORIZONTE'];
  const cel = (m, c) => { const x = e.find(y => y.modelo === m && y.cidade === c); const cls = x.unidades === 0 ? 'zero' : x.unidades < x.unidades_iniciais ? 'baixo' : '';
    return `<td class="${cls}" title="inicial ${x.unidades_iniciais} · entrega ${x.prazo_entrega_dias} dias se faltar">${x.unidades}</td>`; };
  $('estoque').innerHTML = `<table><tr><th></th>${cidades.map(c => `<th>${CIDADE[c].replace('Belo Horizonte', 'BH').replace('São Paulo', 'SP')}</th>`).join('')}</tr>` +
    modelos.map(m => `<tr><td>${m[0] + m.slice(1).toLowerCase()}</td>${cidades.map(c => cel(m, c)).join('')}</tr>`).join('') + '</table>';
}

function renderCliente() {
  const c = conv.cliente;
  const mod = (c.modelo_atual || '').charAt(0) + (c.modelo_atual || '').slice(1).toLowerCase();
  const uso = c.produto_atual === 'AD' ? `${c.qtd_atual} ${mod} na diária, ~${c.dias_diaria_mes} dias/mês`
    : c.produto_atual === 'AM' ? `${c.qtd_atual} ${mod} no mensal${c.contrato_vence_dias ? `, vence em ${c.contrato_vence_dias} dias` : ''}`
    : c.frota_propria ? `frota própria de ${c.frota_propria} carros` : 'sem locação';
  $('info-cliente').innerHTML = `<dl><dt>Empresa</dt><dd>${esc(c.razao_social)}</dd><dt>CNPJ</dt><dd>${esc(c.cnpj)}</dd>
    <dt>Perfil</dt><dd>${esc(c.icp)} · ${esc(c.cidade)}</dd><dt>Uso atual</dt><dd>${esc(uso)}</dd><dt>km/mês</dt><dd>${c.km_mes}</dd>
    <dt>Preço</dt><dd>${esc(c.perfil_preco)}</dd><dt>Conversa</dt><dd>modo <b>${conv.modo}</b>${conv.livre ? ' · livre' : ''} · ${esc(conv.desfecho)}</dd></dl>`;
  $('box-roteiro').hidden = !conv.roteiro;
  if (conv.roteiro) $('roteiro-texto').textContent = conv.roteiro.texto;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
const baloes = t => String(t || '').split(/\n\s*\n/).map(x => x.trim()).filter(Boolean);
// pausa de "digitando" proporcional ao tamanho do balão (humano no WhatsApp não responde instantâneo)
const tempoDigitando = t => Math.min(3500, Math.max(700, t.length * 28));

function htmlMensagem(m, ate) {
  if (m.role === 'cliente') return `<div class="m cliente"><div class="who">Cliente</div>${esc(m.conteudo)}</div>`;
  const a = m.auditoria || {}, bs = baloes(m.conteudo).slice(0, ate ?? 99);
  const flag = (a.violacoes || []).length
    ? `<div class="flag ${conv.modo === 'A' ? 'bad' : 'warn'}">${conv.modo === 'A' ? '⚑ marcado' : '⚑ corrigido pelo sistema'}: ${esc(a.violacoes.join(', '))}</div>` : '';
  return bs.map((b, i) => `<div class="m vendedor" data-id="${m.message_id}">${i === 0 ? '<div class="who">Fernanda · Vendedor IA</div>' : ''}${esc(b)}${i === bs.length - 1 ? flag : ''}</div>`).join('');
}

function renderChat(esconderId) {
  renderCliente();
  const vazia = !conv.mensagens.length;
  $('chat').innerHTML = (vazia ? `<div class="nota">Atendimento receptivo: mande a primeira mensagem como <b>${esc(conv.cliente.razao_social)}</b>.</div>` : '') +
    conv.mensagens.filter(m => m.message_id !== esconderId).map(m => htmlMensagem(m)).join('');
  $('chat').scrollTop = 1e9;
  ligarCliques();
  const ativa = conv.status === 'ATIVA';
  $('msg').disabled = !ativa; $('form').querySelector('button').disabled = !ativa;
  const last = [...conv.mensagens].reverse().find(m => m.role === 'vendedor' && m.message_id !== esconderId);
  if (last) showAudit(last.message_id); else $('audit').textContent = 'Sem respostas ainda.';
  estoque();
}

function ligarCliques() {
  document.querySelectorAll('.m.vendedor').forEach(el => el.onclick = () => showAudit(+el.dataset.id));
}

async function animarResposta(m) {
  const bs = baloes(m.conteudo);
  for (let i = 0; i < bs.length; i++) {
    $('chat').insertAdjacentHTML('beforeend', '<div class="nota digitando">Fernanda está digitando…</div>');
    $('chat').scrollTop = 1e9;
    await sleep(tempoDigitando(bs[i]));
    document.querySelectorAll('.digitando').forEach(e => e.remove());
    document.querySelectorAll(`.m.vendedor[data-id="${m.message_id}"]`).forEach(e => e.remove());
    $('chat').insertAdjacentHTML('beforeend', htmlMensagem(m, i + 1));
    $('chat').scrollTop = 1e9;
    if (i < bs.length - 1) await sleep(350);
  }
  ligarCliques();
  showAudit(m.message_id);
}

function showAudit(id) {
  document.querySelectorAll('.m').forEach(e => e.classList.toggle('sel', +e.dataset.id === id));
  const m = conv.mensagens.find(x => x.message_id === id), a = (m && m.auditoria) || {};
  const val = {ok: ['ok', 'OK'], corrigida: ['warn', 'Corrigida pelo sistema (1 reescrita)'], mensagem_segura: ['bad', 'Bloqueada: mensagem segura enviada'],
    limite_de_passos: ['bad', 'Limite de passos: mensagem segura'], marcado: ['bad', 'Marcada (modo A não corrige)'], contingencia: ['bad', 'Contingência (GPT indisponível)']}[a.resultado_validacao] || ['', a.resultado_validacao];
  const tools = (a.chamadas || []).map(c => `<div class="tool"><b>${esc(c.nome)}</b>entrada: ${esc(JSON.stringify(c.entrada))}<pre>${esc(JSON.stringify(c.saida, null, 1))}</pre></div>`).join('');
  $('audit').innerHTML = `<dl><dt>Modo</dt><dd>${esc(a.modo)} ${a.modo_ferramentas ? '· ' + esc(a.modo_ferramentas) : ''}</dd>
    <dt>Validação</dt><dd class="${val[0]}">${esc(val[1])}</dd>
    ${(a.violacoes || []).length ? `<dt>Achados</dt><dd class="bad">${esc(a.violacoes.join(', '))}</dd>` : ''}
    ${(a.tiques || []).length ? `<dt>Tiques de robô</dt><dd class="warn">${esc(a.tiques.join(', '))}</dd>` : ''}
    ${a.erro_llm ? `<dt>Erro GPT</dt><dd class="bad">${esc(a.erro_llm)}</dd>` : ''}
    <dt>Tokens</dt><dd>${(m.tokens_entrada || 0)} + ${(m.tokens_saida || 0)}</dd><dt>Custo gate</dt><dd>${m.custo_gate ? 'US$ ' + m.custo_gate : '—'}</dd></dl>
    <h2>${conv.modo === 'A' ? 'Ações decididas pelo modelo' : 'Ferramentas chamadas'} (${(a.chamadas || []).length})</h2>${tools || '<div class="badge">nenhuma</div>'}`;
}

async function novo() {
  const r = $('roteiro').value;
  conv = await post('/api/conversations', {cliente_id: $('cliente').value, modo: $('modo').value, livre: r === '__livre', roteiro_id: r === '__livre' ? null : r});
  $('aval').textContent = '—'; renderChat(); $('msg').focus();
}

const sim = v => v ? 'Sim' : 'Não';
$('btn-novo').onclick = () => novo().catch(e => alert(e.message));
$('btn-reset').onclick = async () => { if (conv) { conv = await post(`/api/conversations/${conv.conversation_id}/reset`); $('aval').textContent = '—'; renderChat(); } };
$('btn-fechar').onclick = async () => { if (conv) { conv = await post(`/api/conversations/${conv.conversation_id}/close`); renderChat(); } };
$('btn-estoque').onclick = async () => { if (confirm('Voltar o estoque ao inicial? (afeta todas as conversas)')) { await post('/api/estoque/reiniciar'); estoque(); } };
$('btn-audit').onclick = () => { auditOn = !auditOn; $('audit-box').hidden = !auditOn; $('btn-audit').textContent = auditOn ? 'Ocultar auditoria' : 'Mostrar auditoria'; };
$('btn-aval').onclick = async () => {
  if (!conv) return;
  const r = await post(`/api/conversations/${conv.conversation_id}/evaluate`);
  $('aval').innerHTML = `<dl><dt>Desfecho</dt><dd>${esc(r.desfecho)} (${r.turnos_cliente} turnos)</dd>
    <dt>Diagnóstico antes do preço</dt><dd>${r.diagnostico_antes_do_preco == null ? '—' : sim(r.diagnostico_antes_do_preco)}</dd>
    <dt>Próximo passo</dt><dd>${sim(r.proximo_passo_definido)}</dd><dt>Usou comparação (Challenger)</dt><dd>${sim(r.usou_comparacao)}</dd>
    <dt>Problemas entregues</dt><dd class="${r.mensagens_com_problema_entregues ? 'bad' : 'ok'}">${r.mensagens_com_problema_entregues}</dd>
    <dt>Correções automáticas (B)</dt><dd>${r.correcoes_automaticas_b}</dd>
    <dt>Valor não verificado</dt><dd>${r.valores_nao_verificados}</dd><dt>Margem revelada</dt><dd class="${r.margem_revelada ? 'bad' : ''}">${r.margem_revelada}</dd>
    <dt>Proposta fora da regra</dt><dd class="${r.propostas_fora_da_regra.length ? 'bad' : ''}">${r.propostas_fora_da_regra.length}</dd>
    <dt>Concessão sem contrapartida</dt><dd>${r.concessao_sem_contrapartida.length}</dd><dt>Além do estoque</dt><dd>${r.alem_do_estoque}</dd>
    <dt>Tiques de robô</dt><dd class="${r.tiques_de_robo ? 'warn' : 'ok'}">${r.tiques_de_robo}</dd><dt>Balões por resposta</dt><dd>${r.baloes_por_resposta ?? '—'}</dd>
    <dt>Tokens / custo</dt><dd>${r.tokens} / ${r.custo_gate ? 'US$ ' + r.custo_gate : '—'}</dd></dl>`;
};
$('btn-comp').onclick = async () => {
  const r = await api('/api/comparativo'), A = r.A_llm_pura, B = r.B_llm_com_ferramentas;
  const linhas = [['Conversas', 'conversas'], ['Com proposta %', 'com_proposta_pct'], ['Problema entregue ao cliente %', 'com_problema_entregue_ao_cliente_pct'],
    ['Valor não verificado %', 'valor_nao_verificado_pct'], ['Margem revelada %', 'margem_revelada_pct'], ['Proposta fora da regra %', 'proposta_fora_da_regra_pct'],
    ['Concessão sem contrapartida %', 'concessao_sem_contrapartida_pct'], ['Além do estoque %', 'alem_do_estoque_pct'],
    ['Diagnóstico antes do preço %', 'diagnostico_antes_do_preco_pct'], ['Próximo passo %', 'proximo_passo_definido_pct'],
    ['Com tique de robô %', 'com_tique_de_robo_pct'], ['Turnos médios', 'media_turnos'], ['Tokens/conversa', 'tokens_por_conversa'], ['Custo gate/conversa', 'custo_gate_por_conversa']];
  $('aval').innerHTML = `<table><tr><th>Comparativo</th><th>A puro</th><th>B ferramentas</th></tr>${linhas.map(([n, k]) => `<tr><td>${n}</td><td>${A[k] ?? '—'}</td><td>${B[k] ?? '—'}</td></tr>`).join('')}</table>
    <div class="badge">Só conversas com roteiro. ${r.conversas_livres_fora_do_comparativo} conversas livres ficaram fora.</div>`;
};
$('btn-json').onclick = () => conv && window.open(`/api/conversations/${conv.conversation_id}/export?formato=json`);
$('btn-txt').onclick = () => conv && window.open(`/api/conversations/${conv.conversation_id}/export?formato=txt`);
$('btn-cls').onclick = () => window.open('/api/export/classificador.csv');
$('form').onsubmit = async e => {
  e.preventDefault();
  const t = $('msg').value.trim(); if (!t || !conv) return;
  $('msg').value = ''; $('msg').disabled = true;
  $('chat').insertAdjacentHTML('beforeend', `<div class="m cliente"><div class="who">Cliente</div>${esc(t)}</div><div class="nota digitando">Fernanda está digitando…</div>`);
  $('chat').scrollTop = 1e9;
  try {
    conv = await post(`/api/conversations/${conv.conversation_id}/messages`, {conteudo: t});
    const nova = [...conv.mensagens].reverse().find(m => m.role === 'vendedor');
    renderChat(nova && nova.message_id);
    $('msg').disabled = true;
    if (nova) await animarResposta(nova);
    $('msg').disabled = conv.status !== 'ATIVA';
  } catch (err) { alert(err.message); $('msg').disabled = false; }
  $('msg').focus();
};
init();
