// Laboratório: IA-cliente (personas do Treino) conversa sozinha com a Fernanda (modos A e B); o sistema confere cada conversa.
let cat = null, rodadaId = null, execId = null, timer = null;
const $ = id => document.getElementById(id);
const api = async (url, opts) => {
  const r = await fetch(url, opts && {headers: {'Content-Type': 'application/json'}, ...opts});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {method: 'POST', body: JSON.stringify(body || {})});
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const cor = n => n == null ? 'var(--muted)' : n >= 8 ? 'var(--win)' : n >= 5 ? 'var(--amber)' : 'var(--red)';
const pct = v => v == null ? '—' : `${String(v).replace('.', ',')}%`;
const num = v => v == null ? '—' : String(v).replace('.', ',');
const STATUS = {PENDENTE: 'Na fila', EM_ANDAMENTO: 'Rodando', CONCLUIDA: 'Concluída', CANCELADA: 'Cancelada', ERRO: 'Erro', INTERROMPIDA: 'Interrompida'};
const FIM = {CLIENTE_ACEITOU: 'Cliente aceitou', CLIENTE_RECUSOU: 'Cliente recusou', CLIENTE_VAI_PENSAR: 'Cliente vai pensar', PROPOSTA: 'Proposta registrada',
  HANDOFF: 'Transferiu para humano', LIMITE_DE_TURNOS: 'Limite de turnos', LOOP: 'Conversa em loop', CANCELADA: 'Cancelada'};

async function init() {
  const h = await api('/api/health');
  $('llm').className = 'tb-status' + (h.llm_configurado ? '' : ' off');
  $('llm').innerHTML = `<span class="dot"></span>${h.llm_configurado ? 'GPT conectado' : 'GPT não configurado (modo demonstração)'}`;
  cat = await api('/api/lab/catalogo');
  $('preset').innerHTML = cat.presets.map(p => `<option value="${p.id}">${esc(p.titulo)} — ${p.execucoes} conversas</option>`).join('')
    + '<option value="">Personalizada (escolher clientes e comportamentos)</option>';
  $('cli').innerHTML = cat.personas.map(p => `<label><input type="checkbox" value="${p.cliente_id}">${p.cliente_id} · ${esc(p.razao_social)}</label>`).join('');
  const grupos = {base: 'Comportamentos', longa: 'Conversa longa', red_team: 'Red team (ataques)'};
  $('comp').innerHTML = cat.comportamentos.map(c => `<label title="${esc(c.instrucao)}"><input type="checkbox" value="${c.id}">${esc(c.titulo)}${c.grupo === 'base' ? '' : `<span class="badge"> · ${grupos[c.grupo]}</span>`}</label>`).join('');
  document.querySelectorAll('.lab-form select, .lab-form input').forEach(el => el.addEventListener('change', estimar));
  document.querySelectorAll('[data-todos],[data-nenhum]').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    const alvo = a.dataset.todos || a.dataset.nenhum;
    $(alvo).querySelectorAll('input').forEach(i => { i.checked = !!a.dataset.todos; });
    estimar();
  });
  await estimar();
  await listar();
  const ultima = (await api('/api/lab/rodadas'))[0];
  if (ultima) abrirRodada(ultima.rodada_id);
}

function corpo() {
  const preset = $('preset').value || null;
  const marcados = id => [...$(id).querySelectorAll('input:checked')].map(i => i.value);
  return {preset, personas: marcados('cli'), comportamentos: marcados('comp'),
    modos: [...document.querySelectorAll('input[name=modo]:checked')].map(i => i.value),
    repeticoes: +$('repeticoes').value || 1, max_turnos: +$('max_turnos').value || 12, dificuldade: $('dificuldade').value,
    avaliar_ia: $('avaliar_ia').checked, workers: +$('workers').value, nome: $('nome').value.trim() || null};
}

async function estimar() {
  $('custom').hidden = !!$('preset').value;
  try {
    const e = await post('/api/lab/estimar', corpo());
    $('estimativa').innerHTML = e.execucoes
      ? `<b>${e.execucoes} conversas · ~${e.turnos_estimados} turnos</b>Custo estimado ~US$ ${num(e.custo_estimado_usd)} · tempo ~${e.minutos_estimados} min (${$('workers').value} em paralelo). A primeira rodada real calibra esses números.`
      : 'Escolha ao menos 1 cliente, 1 comportamento e 1 modo.';
    $('btn-criar').disabled = !e.execucoes;
  } catch (err) { $('estimativa').textContent = err.message; }
}

$('btn-criar').onclick = async () => {
  $('btn-criar').disabled = true;
  try {
    const r = await post('/api/lab/rodadas', corpo());
    $('nome').value = '';
    await listar();
    abrirRodada(r.rodada_id);
  } catch (err) { alert(err.message); }
  $('btn-criar').disabled = false;
};

async function listar() {
  const rs = await api('/api/lab/rodadas');
  $('rodadas').innerHTML = rs.length ? rs.map(r => `<div class="rod ${r.rodada_id === rodadaId ? 'sel' : ''}" data-id="${r.rodada_id}">
      <div class="lab-top"><span>${esc(r.nome)}</span><span class="st st-${r.status}">${STATUS[r.status] || r.status}</span></div>
      <div class="badge">${r.rodada_id} · ${r.feitas}/${r.total} feitas · ${r.aprovadas} aprovadas</div>
      <div class="barra"><i style="width:${r.total ? 100 * r.feitas / r.total : 0}%;background:var(--green-l)"></i></div></div>`).join('')
    : 'Nenhuma rodada ainda.';
  $('rodadas').querySelectorAll('.rod').forEach(el => el.onclick = () => abrirRodada(el.dataset.id));
}

async function abrirRodada(id) {
  rodadaId = id;
  clearTimeout(timer);
  let r;
  try { r = await api(`/api/lab/rodadas/${id}`); } catch (err) { $('rodada').innerHTML = `<div class="bad">${esc(err.message)}</div>`; return; }
  renderRodada(r);
  listar();
  if (execId && r.execucoes.some(x => x.exec_id === execId && ['EM_ANDAMENTO', 'CONCLUIDA'].includes(x.status))) abrirExecucao(execId, true);
  if (r.rodando || r.status === 'EM_ANDAMENTO') timer = setTimeout(() => abrirRodada(id), 3000);
}

function bloco(b) {
  if (!b || !b.n) return '<td>—</td><td>—</td><td>—</td>';
  return `<td>${pct(b.aprovadas_pct)}</td><td style="color:${cor(b.nota_media)}">${num(b.nota_media)}</td><td>${num(b.turnos_medios)}</td>`;
}

function renderRodada(r) {
  const s = r.resumo, feitas = s.concluidas + s.erros;
  const botoes = r.rodando ? `<button id="btn-cancelar" data-ic="x">Cancelar</button>`
    : ['INTERROMPIDA', 'CANCELADA'].includes(r.status) && s.pendentes + r.execucoes.filter(x => x.status === 'CANCELADA').length
      ? `<button id="btn-retomar" data-ic="play">Retomar</button>` : '';
  const comps = Object.entries(s.por_comportamento);
  $('rodada').innerHTML = `
    <div class="lab-top"><h1 class="lab-h1">${esc(r.nome)}</h1><span class="st st-${r.status}">${STATUS[r.status] || r.status}</span></div>
    <div class="badge">${r.rodada_id} · dificuldade ${esc(r.config.dificuldade)} · ${r.config.workers} em paralelo · nota C12 ${r.config.avaliar_ia ? 'ligada' : 'desligada'}</div>
    <div class="barra grossa"><i style="width:${s.total ? 100 * feitas / s.total : 0}%;background:var(--green-l)"></i></div>
    <div class="acoes">${botoes}<a href="/api/lab/rodadas/${r.rodada_id}/export.csv"><button data-ic="download">Exportar CSV</button></a></div>
    <div class="kpis">
      <div class="kpi"><b>${feitas}/${s.total}</b><span>conversas feitas</span></div>
      <div class="kpi"><b>${s.erros}</b><span>com erro técnico</span></div>
      <div class="kpi"><b>${s.falhas.length}</b><span>checagens reprovadas</span></div>
      <div class="kpi"><b>${s.tokens.toLocaleString('pt-BR')}</b><span>tokens</span></div>
      <div class="kpi"><b>US$ ${num(s.custo_gate_usd)}</b><span>custo no gate</span></div>
    </div>
    <h2>Modo A × Modo B</h2>
    <table><tr><th></th><th>Conversas</th><th>Aprovadas</th><th>Nota C12</th><th>Turnos médios</th></tr>
      ${['A', 'B'].map(m => `<tr><td><b>${m}</b> · ${m === 'A' ? 'LLM pura (controle)' : 'com ferramentas'}</td><td>${s.por_modo[m].n || 0}</td>${bloco(s.por_modo[m])}</tr>`).join('')}</table>
    ${s.longas ? `<h2>Conversas longas (até 24 turnos)</h2><table><tr><th></th><th>Conversas</th><th>Aprovadas</th><th>Nota C12</th><th>Turnos médios</th></tr>
      <tr><td>Longas</td><td>${s.longas.n}</td>${bloco(s.longas)}</tr></table>` : ''}
    ${comps.length > 1 ? `<h2>Por comportamento</h2><table><tr><th>Comportamento</th><th>A aprov.</th><th>A nota</th><th>A turnos</th><th>B aprov.</th><th>B nota</th><th>B turnos</th></tr>
      ${comps.map(([c, v]) => `<tr><td>${esc((cat.comportamentos.find(x => x.id === c) || {}).titulo || c)}</td>${bloco(v.A)}${bloco(v.B)}</tr>`).join('')}</table>` : ''}
    ${Object.keys(s.fim).length ? `<h2>Como as conversas terminaram</h2><div class="chips">${Object.entries(s.fim).map(([f, n]) => `<span class="chip">${esc(FIM[f] || f)} <b>${n}</b></span>`).join('')}</div>` : ''}
    ${s.falhas.length ? `<h2>Checagens reprovadas</h2><table class="falhas"><tr><th>Execução</th><th>Modo</th><th>Checagem</th><th>Detalhe</th></tr>
      ${s.falhas.map(f => `<tr class="clicavel" data-exec="${f.exec_id}"><td>${f.cliente_id} · ${esc(f.comportamento)}</td><td>${f.modo}</td><td class="bad">${esc(f.check)}</td><td>${esc(f.detalhe)}</td></tr>`).join('')}</table>` : ''}
    <h2>Execuções</h2>
    <table class="execs"><tr><th>#</th><th>Cliente</th><th>Comportamento</th><th>Modo</th><th>Turnos</th><th>Fim</th><th>Checagens</th><th>Nota</th></tr>
      ${r.execucoes.map(x => `<tr class="clicavel ${x.exec_id === execId ? 'sel' : ''}" data-exec="${x.exec_id}">
        <td>${x.ordem}</td><td>${x.cliente_id} · ${esc(x.razao_social)}</td><td>${esc(x.comportamento_titulo)}${x.repeticao > 1 ? ` (${x.repeticao}ª)` : ''}</td><td>${x.modo}</td>
        <td>${x.turnos || 0}/${x.max_turnos}</td>
        <td>${x.status === 'CONCLUIDA' ? esc(FIM[x.fim_motivo] || x.fim_motivo) : `<span class="st st-${x.status}">${STATUS[x.status]}</span>`}</td>
        <td>${x.status !== 'CONCLUIDA' ? (x.erro ? `<span class="bad" title="${esc(x.erro)}">erro</span>` : '') : x.aprovado ? '<span class="ok">✅ ok</span>' : `<span class="bad">❌ ${x.checks.filter(c => !c.ok).length}</span>`}</td>
        <td style="color:${cor(x.nota_geral)};font-weight:700">${num(x.nota_geral)}</td></tr>`).join('')}</table>`;
  document.querySelectorAll('#rodada [data-ic]').forEach(el => el.insertAdjacentHTML('afterbegin', icon(el.dataset.ic)));
  $('rodada').querySelectorAll('[data-exec]').forEach(el => el.onclick = () => abrirExecucao(el.dataset.exec));
  if ($('btn-cancelar')) $('btn-cancelar').onclick = async () => { await post(`/api/lab/rodadas/${r.rodada_id}/cancelar`); abrirRodada(r.rodada_id); };
  if ($('btn-retomar')) $('btn-retomar').onclick = async () => {
    try { await post(`/api/lab/rodadas/${r.rodada_id}/retomar`); } catch (err) { alert(err.message); }
    abrirRodada(r.rodada_id);
  };
}

async function abrirExecucao(id, silencioso) {
  execId = id;
  document.querySelectorAll('#rodada tr.sel').forEach(el => el.classList.remove('sel'));
  document.querySelectorAll(`#rodada .execs tr[data-exec="${id}"]`).forEach(el => el.classList.add('sel'));
  const x = await api(`/api/lab/execucoes/${id}`);
  const c = x.conversa, msgs = c ? c.mensagens.filter(m => ['cliente', 'vendedor'].includes(m.role)) : [];
  const a = x.avaliacao;
  const rolarFim = !silencioso || $('conversa').scrollTop + $('conversa').clientHeight >= $('conversa').scrollHeight - 30;
  $('conversa').className = '';
  $('conversa').innerHTML = `
    <div class="lab-top"><span>${x.cliente_id} · ${esc(c ? c.cliente.razao_social : '')}</span><span class="tier">Modo ${x.modo}</span></div>
    <div class="badge">${esc(x.comportamento_titulo)} · ${x.turnos || 0}/${x.max_turnos} turnos · ${x.status === 'CONCLUIDA' ? esc(FIM[x.fim_motivo] || x.fim_motivo) : STATUS[x.status]}</div>
    ${x.erro ? `<div class="bad">${esc(x.erro)}</div>` : ''}
    ${x.checks.length ? `<h2>Checagens do sistema</h2><ul class="checklist">${x.checks.map(ch => `<li>${ch.ok ? '✅' : '❌'} ${esc(ch.check)}${ch.detalhe ? ` <span class="badge">— ${esc(ch.detalhe)}</span>` : ''}</li>`).join('')}</ul>` : ''}
    ${a ? `<h2>Nota C12</h2><div class="dim"><div class="dim-top"><span>${esc(a.resumo || 'Avaliação')}</span><span style="color:${cor(a.nota_geral)}">${num(a.nota_geral)}</span></div>
      <table>${Object.values(a.dimensoes).map(d => `<tr><td>${esc(d.nome)}</td><td style="color:${cor(d.nota)};font-weight:700">${num(d.nota)}</td></tr>`).join('')}</table>
      ${(a.pontos_a_melhorar || []).length ? `<div class="rotulo">Onde a Fernanda pode melhorar</div><ul>${a.pontos_a_melhorar.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}</div>` : ''}
    <h2>Conversa</h2>
    <div class="lab-chat">${msgs.map(m => {
      const au = m.auditoria || {};
      const marca = m.role === 'vendedor' && au.resultado_validacao && au.resultado_validacao !== 'ok'
        ? `<div class="flag ${['contingencia', 'corrigida'].includes(au.resultado_validacao) ? 'warn' : 'bad'}">${esc(au.resultado_validacao)}${(au.violacoes || []).length ? ': ' + au.violacoes.map(v => esc(v.tipo || v)).join(', ') : ''}</div>` : '';
      return `<div class="m ${m.role === 'cliente' ? 'cliente' : 'vendedor'}"><div class="who">${m.role === 'cliente' ? 'IA-cliente · ' + esc(x.contato) : 'Fernanda'}</div>${esc(m.conteudo)}${marca}</div>`;
    }).join('') || '<div class="nota">Aguardando a primeira mensagem…</div>'}
    ${x.status === 'EM_ANDAMENTO' ? '<div class="nota digitando">conversa em andamento…</div>' : ''}</div>
    ${c && (c.propostas.length || c.handoffs.length) ? `<h2>Registros</h2>${c.propostas.map(p => `<div class="tool"><b>Proposta ${esc(p.proposta_id)}</b>${esc(p.modelo)} · ${p.quantidade} un · ${esc(p.produto)} · desconto ${num(p.desconto_pct)}%</div>`).join('')}
      ${c.handoffs.map(h => `<div class="tool"><b>Transferência · ${esc(h.motivo)}</b>${esc(h.resumo || '')}</div>`).join('')}` : ''}`;
  if (rolarFim) $('conversa').scrollTop = $('conversa').scrollHeight;
}

init();
