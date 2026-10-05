// Laboratório: IA-cliente (personas do Treino) conversa sozinha com a Fernanda (modos A e B); o sistema confere cada conversa.
let cat = null, rodadaId = null, execId = null, timer = null;
const marcadas = new Set();
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
  HANDOFF: 'Transferiu para humano', LIMITE_DE_TURNOS: 'Limite de turnos', LOOP: 'Conversa em loop', CANCELADA: 'Cancelada',
  SEM_RESPOSTA: 'Cliente não respondeu', ATIVO_DESCADASTRO: 'Pediu para parar', ATIVO_PESSOA_ERRADA: 'Pessoa errada',
  ATIVO_RETORNAR_DEPOIS: 'Retorno combinado', ATIVO_PERDIDO_CONCORRENTE: 'Perdido p/ concorrente', ATIVO_SEM_INTERESSE: 'Sem interesse'};

async function init() {
  const h = await api('/api/health');
  $('llm').className = 'tb-status' + (h.llm_configurado ? '' : ' off');
  $('llm').innerHTML = `<span class="dot"></span>${h.llm_configurado ? 'GPT conectado' : 'GPT não configurado (modo demonstração)'}`;
  cat = await api('/api/lab/catalogo');
  $('preset').innerHTML = cat.presets.map(p => `<option value="${p.id}">${esc(p.titulo)} — ${p.execucoes} conversas</option>`).join('')
    + '<option value="">Personalizada (escolher clientes e comportamentos)</option>';
  $('cli').innerHTML = cat.personas.map(p => `<label><input type="checkbox" value="${p.cliente_id}">${p.cliente_id} · ${esc(p.razao_social)}</label>`).join('');
  $('modelos-lista').innerHTML = cat.modelos_disponiveis.map(m => `<option value="${esc(m)}">`).join('');
  $('modelo_vendedora').placeholder = `padrão: ${cat.modelos.vendedora}`;
  $('modelos-fixos').textContent = `IA-cliente: ${cat.modelos.cliente} · avaliador: ${cat.modelos.avaliador} (fixos, para a comparação ser justa)`;
  $('aberturas').innerHTML = cat.aberturas.map(a => `<label><input type="checkbox" name="abertura" value="${a.id}" ${a.id === cat.abertura_padrao ? 'checked' : ''}>${esc(a.titulo)}</label>`).join('');
  const grupos = {base: 'Comportamentos', negociacao: 'Negociação', ativa: 'Frente ativa', longa: 'Conversa longa', red_team: 'Red team (ataques)'};
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
    aberturas: [...document.querySelectorAll('input[name=abertura]:checked')].map(i => i.value),
    repeticoes: +$('repeticoes').value || 1, max_turnos: +$('max_turnos').value || 12, dificuldade: $('dificuldade').value,
    avaliar_ia: $('avaliar_ia').checked, modelos: $('modelo_vendedora').value.trim() ? {vendedora: $('modelo_vendedora').value.trim()} : {}, workers: +$('workers').value, nome: $('nome').value.trim() || null};
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
      <div class="lab-top"><span><input type="checkbox" class="marca-comp" data-id="${r.rodada_id}" ${marcadas.has(r.rodada_id) ? 'checked' : ''} title="Comparar"> ${esc(r.nome)}</span><span class="st st-${r.status}">${STATUS[r.status] || r.status}</span></div>
      <div class="badge">${r.rodada_id} · ${r.feitas}/${r.total} feitas · ${r.aprovadas} aprovadas${r.modelo_vendedora ? ` · ${esc(r.modelo_vendedora)}` : ''}</div>
      <div class="barra"><i style="width:${r.total ? 100 * r.feitas / r.total : 0}%;background:var(--green-l)"></i></div></div>`).join('')
    : 'Nenhuma rodada ainda.';
  $('rodadas').querySelectorAll('.rod').forEach(el => el.onclick = () => abrirRodada(el.dataset.id));
  $('rodadas').querySelectorAll('.marca-comp').forEach(cb => {
    cb.onclick = ev => ev.stopPropagation();
    cb.onchange = () => { cb.checked ? marcadas.add(cb.dataset.id) : marcadas.delete(cb.dataset.id); $('btn-comparar').disabled = marcadas.size < 2 || marcadas.size > 4; };
  });
  $('btn-comparar').disabled = marcadas.size < 2 || marcadas.size > 4;
}

$('btn-comparar').onclick = async () => {
  clearTimeout(timer);
  let c;
  try { c = await api(`/api/lab/comparar?ids=${[...marcadas].join(',')}`); } catch (err) { alert(err.message); return; }
  const DIM = {diagnostico: 'Diagnóstico', challenger: 'Challenger com dado', objecoes: 'Objeções', qualificacao: 'Qualificação',
    adicionais: 'Adicionais', fechamento: 'Fechamento', tom: 'Tom', disciplina_margem: 'Disciplina de margem'};
  const linhas = [
    ['Modelo da Fernanda', r => esc(r.modelos.vendedora || '—')], ['IA-cliente / avaliador', r => esc(`${r.modelos.cliente || '—'} / ${r.modelos.avaliador || '—'}`)],
    ['Conversas concluídas', r => r.conversas], ['Erros técnicos', r => r.erros],
    ['Aprovadas nas checagens (B)', r => pct(r.por_modo.B.aprovadas_pct)], ['Nota C12 média (B)', r => num(r.por_modo.B.nota_media), r => r.por_modo.B.nota_media],
    ...Object.entries(DIM).map(([k, n]) => [`↳ ${n}`, r => num(r.dimensoes_b[k]), r => r.dimensoes_b[k]]),
    ['Aprovadas nas checagens (A, controle)', r => pct(r.por_modo.A.aprovadas_pct)],
    ['Checagens reprovadas', r => r.checagens_reprovadas], ['Tentativas barradas pela trava (B)', r => r.tentativas_barradas_b],
    ['Desconto médio concedido (B)', r => r.concessoes_b && r.concessoes_b.desconto_medio_concedido != null ? pct(r.concessoes_b.desconto_medio_concedido) : '—'],
    ['Segundos por turno', r => num(r.segundos_por_turno)], ['Custo por conversa', r => r.custo_por_conversa_usd != null ? 'US$ ' + num(r.custo_por_conversa_usd) : '—'],
    ['Custo total', r => 'US$ ' + num(r.custo_total_usd)],
  ];
  $('rodada').innerHTML = `<div class="lab-top"><h1 class="lab-h1">Comparação de rodadas</h1></div>
    <div class="badge">Compare só rodadas com o mesmo tipo de teste: o que deve mudar entre elas é o que você quer medir (ex.: o modelo da Fernanda).</div>
    <table class="comparacao"><tr><th></th>${c.map(r => `<th>${esc(r.nome)}<br><span class="badge">${r.rodada_id}</span></th>`).join('')}</tr>
      ${linhas.map(([n, f, cc]) => `<tr><td>${n}</td>${c.map(r => `<td${cc ? ` style="color:${cor(cc(r))};font-weight:700"` : ''}>${f(r)}</td>`).join('')}</tr>`).join('')}</table>`;
};

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
    ${r.config.modelos ? `<div class="badge">Modelos: Fernanda <b>${esc(r.config.modelos.vendedora)}</b> · IA-cliente ${esc(r.config.modelos.cliente)} · avaliador ${esc(r.config.modelos.avaliador)}</div>` : ''}
    <div class="barra grossa"><i style="width:${s.total ? 100 * feitas / s.total : 0}%;background:var(--green-l)"></i></div>
    <div class="acoes">${botoes}<a href="/api/lab/rodadas/${r.rodada_id}/export.csv"><button data-ic="download">Exportar CSV</button></a><a href="/api/lab/rodadas/${r.rodada_id}/roteiro.csv" title="Mesmas colunas da planilha do Roteiro de Testes (0.5): junta com os testes manuais"><button data-ic="download">Exportar no formato do roteiro</button></a></div>
    <div class="kpis">
      <div class="kpi"><b>${feitas}/${s.total}</b><span>conversas feitas</span></div>
      <div class="kpi"><b>${s.erros}</b><span>com erro técnico</span></div>
      <div class="kpi"><b>${s.falhas.length}</b><span>checagens reprovadas</span></div>
      <div class="kpi"><b>${s.tokens.toLocaleString('pt-BR')}</b><span>tokens</span></div>
      <div class="kpi"><b>US$ ${num(s.custo_gate_usd)}</b><span>custo no gate</span></div>
      <div class="kpi"><b>${s.custo_por_conversa_usd != null ? 'US$ ' + num(s.custo_por_conversa_usd) : '—'}</b><span>por conversa</span></div>
      <div class="kpi"><b>${s.segundos_por_turno != null ? num(s.segundos_por_turno) + ' s' : '—'}</b><span>por turno</span></div>
    </div>
    <h2>Modo A × Modo B</h2>
    <table><tr><th></th><th>Conversas</th><th>Aprovadas</th><th>Nota C12</th><th>Turnos médios</th></tr>
      ${['A', 'B'].map(m => `<tr><td><b>${m}</b> · ${m === 'A' ? 'LLM pura (controle)' : 'com ferramentas'}</td><td>${s.por_modo[m].n || 0}</td>${bloco(s.por_modo[m])}</tr>`).join('')}</table>
    ${s.longas ? `<h2>Conversas longas (até 24 turnos)</h2><table><tr><th></th><th>Conversas</th><th>Aprovadas</th><th>Nota C12</th><th>Turnos médios</th></tr>
      <tr><td>Longas</td><td>${s.longas.n}</td>${bloco(s.longas)}</tr></table>` : ''}
    ${comps.length > 1 ? `<h2>Por comportamento</h2><table><tr><th>Comportamento</th><th>A aprov.</th><th>A nota</th><th>A turnos</th><th>B aprov.</th><th>B nota</th><th>B turnos</th></tr>
      ${comps.map(([c, v]) => `<tr><td>${esc((cat.comportamentos.find(x => x.id === c) || {}).titulo || c)}</td>${bloco(v.A)}${bloco(v.B)}</tr>`).join('')}</table>` : ''}
    ${aberturas(s.aberturas)}
    ${blocoAtiva(s.ativa)}
    ${concessoes(s.concessoes)}
    ${Object.keys(s.fim).length ? `<h2>Como as conversas terminaram</h2><div class="chips">${Object.entries(s.fim).map(([f, n]) => `<span class="chip">${esc(FIM[f] || f)} <b>${n}</b></span>`).join('')}</div>` : ''}
    ${s.falhas.length ? `<h2>Checagens reprovadas</h2><table class="falhas"><tr><th>Execução</th><th>Modo</th><th>Checagem</th><th>Detalhe</th></tr>
      ${s.falhas.map(f => `<tr class="clicavel" data-exec="${f.exec_id}"><td>${f.cliente_id} · ${esc(f.comportamento)}</td><td>${f.modo}</td><td class="bad">${esc(f.check)}</td><td>${esc(f.detalhe)}</td></tr>`).join('')}</table>` : ''}
    <h2>Execuções</h2>
    <table class="execs"><tr><th>#</th><th>Cliente</th><th>Comportamento</th><th>Modo</th>${s.aberturas ? '<th>Abert.</th>' : ''}<th>Turnos</th><th>Fim</th><th>Checagens</th><th>Nota</th></tr>
      ${r.execucoes.map(x => `<tr class="clicavel ${x.exec_id === execId ? 'sel' : ''}" data-exec="${x.exec_id}">
        <td>${x.ordem}</td><td>${x.cliente_id} · ${esc(x.razao_social)}</td><td>${esc(x.comportamento_titulo)}${x.repeticao > 1 ? ` (${x.repeticao}ª)` : ''}</td><td>${x.modo}</td>${s.aberturas ? `<td>${esc(x.abertura || '1')}</td>` : ''}
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

function blocoAtiva(at) {
  if (!at) return '';
  const RES = {INTERESSADO: 'Interessado', RETORNAR_DEPOIS: 'Retorno combinado', SEM_INTERESSE: 'Sem interesse', PERDIDO_CONCORRENTE: 'Perdido p/ concorrente',
    PESSOA_ERRADA: 'Pessoa errada', DESCADASTRO: 'Pediu para parar', SEM_REGISTRO: 'Sem registro'};
  const linhas = [['Contatos', a => a.contatos], ['Responderam', a => pct(a.responderam_pct)], ['Pediram para parar', a => pct(a.descadastro_pct)],
    ['Chegaram a proposta', a => pct(a.proposta_pct)], ['Follow-ups enviados', a => a.follow_ups], ['Aprovadas nas checagens', a => pct(a.aprovadas_pct)],
    ['Resultados registrados', a => Object.entries(a.resultados).map(([k, n]) => `${esc(RES[k] || k)} ${n}`).join(' · ')]];
  return `<h2>Frente ativa (a Fernanda iniciou)</h2>
    <table class="aberturas"><tr><th></th><th>A · LLM pura</th><th>B · com ferramentas</th></tr>
      ${linhas.map(([n, f]) => `<tr><td>${n}</td>${['A', 'B'].map(m => `<td>${at[m] ? f(at[m]) : '—'}</td>`).join('')}</tr>`).join('')}</table>
    <div class="badge">Taxa de resposta e descadastro aqui são da IA-cliente (simulação): servem para comparar versões da Fernanda, não para prever o mundo real.</div>`;
}

function aberturas(ab) {
  if (!ab) return '';
  const ids = Object.keys(ab), DIM = {diagnostico: 'Diagnóstico', challenger: 'Challenger com dado', objecoes: 'Objeções',
    qualificacao: 'Qualificação', fechamento: 'Fechamento', tom: 'Tom'};
  const linhas = [
    ['Conversas', a => a.n], ['Aprovadas nas checagens', a => pct(a.aprovadas_pct)], ['Nota C12 média', a => num(a.nota_media), a => a.nota_media],
    ...Object.entries(DIM).map(([k, n]) => [`↳ ${n}`, a => num(a.dimensoes[k]), a => a.dimensoes[k]]),
    ['Informações-chave descobertas', a => pct(a.descobertas_pct)], ['Turnos médios', a => num(a.turnos_medios)],
    ['Turnos até a proposta', a => num(a.turnos_ate_proposta)], ['Aceitou ou fechou proposta', a => pct(a.aceitou_ou_proposta_pct)],
    ['Vai pensar', a => pct(a.vai_pensar_pct)], ['Recusou', a => pct(a.recusou_pct)], ['Chegou ao limite de turnos', a => pct(a.limite_de_turnos_pct)],
  ];
  return `<h2>Abertura 1 × Abertura 2</h2>
    <table class="aberturas"><tr><th></th>${ids.map(i => `<th>${esc(ab[i].titulo)}</th>`).join('')}</tr>
      ${linhas.map(([n, f, c]) => `<tr><td>${n}</td>${ids.map(i => `<td${c ? ` style="color:${cor(c(ab[i]))};font-weight:700"` : ''}>${f(ab[i])}</td>`).join('')}</tr>`).join('')}</table>
    <div class="badge">O que a abertura deve mudar é o diagnóstico: mais informações descobertas e nota de diagnóstico maior, sem perder o fechamento. Leia também 3 ou 4 conversas de cada lado.</div>`;
}

function concessoes(c) {
  if (!c || (!c.A && !c.B)) return '';
  const linhas = [
    ['Cliente pediu desconto (conversas)', 'pediram_desconto'],
    ['Consultas de desconto à alçada', 'consultas_de_desconto', true],
    ['↳ aprovadas pela vendedora', 'aprovadas_pela_vendedora', true],
    ['↳ aprovadas pelo gerente (com contrapartida)', 'aprovadas_pelo_gerente', true],
    ['↳ negadas (com contraproposta)', 'negadas', true],
    ['Propostas registradas', 'propostas'], ['↳ com desconto', 'propostas_com_desconto'],
    ['Desconto médio concedido', 'desconto_medio_concedido', false, v => v == null ? '—' : pct(v)],
    ['Acima da alçada da vendedora, com contrapartida', 'acima_da_alcada_com_contrapartida'],
    ['Acima da alçada da vendedora, sem contrapartida', 'acima_da_alcada_sem_contrapartida', false, null, 'ruim'],
    ['Disse que o gerente aprovou sem aprovação', 'aprovacao_inventada', false, null, 'ruim'],
  ];
  const cel = (m, [, k, soB, fmt, tipo]) => {
    if (!c[m]) return '<td>—</td>';
    const v = c[m][k];
    if (v == null) return `<td class="badge">${soB ? 'sem ferramentas' : '—'}</td>`;
    const txt = fmt ? fmt(v) : v;
    if (tipo === 'ruim' && v > 0) {
      const nota = k === 'aprovacao_inventada' && m === 'B' ? ' <span class="badge">barradas pela trava</span>' : '';
      return `<td class="${nota ? 'warn' : 'bad'}">${txt}${nota}</td>`;
    }
    return `<td>${txt}</td>`;
  };
  return `<h2>Concessões e alçada</h2>
    <table class="concessoes"><tr><th></th><th>A · LLM pura</th><th>B · com ferramentas</th></tr>
      ${linhas.map(l => `<tr><td>${l[0]}</td>${cel('A', l)}${cel('B', l)}</tr>`).join('')}</table>
    <div class="badge">No B, quem decide o desconto é a regra (vendedora, gerente simulado com contrapartida ou negado). No A, o próprio GPT decide.</div>`;
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
    <div class="lab-top"><span>${x.cliente_id} · ${esc(c ? c.cliente.razao_social : '')}</span><span class="tier">Modo ${x.modo} · Abertura ${esc(x.abertura || '1')}</span></div>
    <div class="badge">${esc(x.comportamento_titulo)} · ${x.turnos || 0}/${x.max_turnos} turnos · ${x.status === 'CONCLUIDA' ? esc(FIM[x.fim_motivo] || x.fim_motivo) : STATUS[x.status]}</div>
    ${x.erro ? `<div class="bad">${esc(x.erro)}</div>` : ''}
    ${x.checks.length ? `<h2>Checagens do sistema</h2><ul class="checklist">${x.checks.map(ch => `<li>${ch.ok ? '✅' : '❌'} ${esc(ch.check)}${ch.fonte === 'auditor' ? ' <span class="tier">auditor</span>' : ''}${ch.detalhe ? ` <span class="badge">— ${esc(ch.detalhe)}</span>` : ''}</li>`).join('')}</ul>` : ''}
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
