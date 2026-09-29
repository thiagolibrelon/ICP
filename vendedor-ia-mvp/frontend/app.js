let conv = null, auditOn = true, cenarios = [];
const $ = id => document.getElementById(id);
const api = async (url, opts) => {
  const r = await fetch(url, opts && {headers: {'Content-Type': 'application/json'}, ...opts});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {method: 'POST', body: JSON.stringify(body || {})});
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
const pct = v => v == null ? '—' : (v * 100).toFixed(1).replace('.0', '').replace('.', ',') + '%';
const brl = v => v == null ? '—' : v.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});

async function init() {
  const h = await api('/api/health');
  $('llm').textContent = `LLM: ${h.llm_configurado ? 'configurado' : 'não configurado (vendedor offline)'} · modo ${h.llm_mode}`;
  cenarios = await api('/api/scenarios');
  $('cenario').innerHTML = cenarios.map(c => `<option value="${c.cenario_id}">${esc(c.titulo)}</option>`).join('');
}

function renderCliente() {
  if (!conv) return;
  const c = conv.cliente, r = conv.regra, o = conv.oportunidade;
  $('cliente').innerHTML = `<dl>
    <dt>Cliente</dt><dd>${esc(c.razao_social)}</dd><dt>Status</dt><dd>${esc(c.status_relacionamento)}</dd>
    <dt>Volume atual</dt><dd>${c.volume_medio_ad + c.volume_medio_am} veículos (AD ${c.volume_medio_ad} / AM ${c.volume_medio_am})</dd>
    <dt>Receita 12m</dt><dd>${brl(c.receita_12m)}</dd><dt>Perfil preço</dt><dd>${esc(c.perfil_preco)}</dd>
    <dt>Oportunidade</dt><dd>${o ? esc(o.tipo) + ': ' + esc(o.motivo_oportunidade) : '—'}</dd>
    <dt>Risco churn</dt><dd>${esc(c.risco_churn)}</dd><dt>Desconto máx.</dt><dd>${pct(r && r.desconto_maximo)}</dd>
    <dt>Desfecho</dt><dd>${esc(conv.desfecho)}</dd></dl>`;
}

function renderChat() {
  $('chat').innerHTML = conv.mensagens.map(m => `<div class="m ${m.role}" data-id="${m.message_id}">
    <div class="who">${m.role === 'vendedor' ? 'Vendedor IA' : 'Cliente'}</div>${esc(m.conteudo)}</div>`).join('');
  $('chat').scrollTop = 1e9;
  document.querySelectorAll('.m.vendedor').forEach(el => el.onclick = () => showAudit(+el.dataset.id));
  const ativa = conv.status === 'ATIVA';
  $('msg').disabled = !ativa; $('form').querySelector('button').disabled = !ativa;
  const last = [...conv.mensagens].reverse().find(m => m.role === 'vendedor');
  if (last) showAudit(last.message_id);
  renderCliente();
}

function showAudit(id) {
  document.querySelectorAll('.m').forEach(e => e.classList.toggle('sel', +e.dataset.id === id));
  const m = conv.mensagens.find(x => x.message_id === id), a = m && m.auditoria;
  if (!a) { $('audit').textContent = '—'; return; }
  const ferr = (a.ferramentas || []).map(f => `<b>${esc(f.nome)}</b>\n${esc(JSON.stringify(f.entrada))}\n→ ${esc(JSON.stringify(f.saida))}`).join('\n\n');
  $('audit').innerHTML = `<dl>
    <dt>Intenção</dt><dd>${esc(a.intencao)}</dd><dt>Confiança</dt><dd>${esc(a.confianca)}</dd>
    <dt>Ação</dt><dd>${esc(a.acao)}</dd><dt>Regra</dt><dd>${esc(a.regra || '—')}</dd>
    <dt>Alçada</dt><dd>${a.alcada == null ? '—' : 'Até ' + pct(a.alcada)}</dd><dt>Preço retornado</dt><dd>${brl(a.preco_retornado)}</dd>
    <dt>Handoff</dt><dd>${a.handoff ? 'Sim' : 'Não'}</dd><dt>Fonte</dt><dd>${esc(a.fonte)}</dd>${a.erro_llm ? `<dt>Erro LLM</dt><dd class="bad">${esc(a.erro_llm)}</dd>` : ''}
    <dt>Validação</dt><dd class="${a.validacao === 'OK' ? 'ok' : 'bad'}">${esc(a.validacao)}</dd></dl>
    <h2 style="margin-top:10px">Ferramentas</h2><pre>${ferr || 'nenhuma'}</pre>`;
  $('audit').style.display = auditOn ? '' : 'none';
}

async function novo() {
  const ident = $('ident').value.trim();
  conv = await post('/api/conversations', ident ? {identificador: ident} : {cenario_id: $('cenario').value});
  $('aval').textContent = '—'; renderChat();
}

$('btn-novo').onclick = () => novo().catch(e => alert(e.message));
$('btn-reset').onclick = async () => { if (conv) { conv = await post(`/api/conversations/${conv.conversation_id}/reset`); $('aval').textContent = '—'; renderChat(); } };
$('btn-obj').onclick = () => {
  const c = conv && cenarios.find(x => x.cenario_id === conv.cenario_id);
  if (c) { $('msg').value = c.objecao_texto; $('msg').focus(); }
};
$('btn-dados').onclick = async () => {
  if (!conv) return;
  const box = $('dados');
  if (!box.hidden) { box.hidden = true; return; }
  const h = await api(`/api/customers/${conv.cliente_id}/history`);
  box.innerHTML = '<h2>Histórico mensal</h2><pre>' + esc(h.map(x => `${x.mes_referencia} AD ${x.volume_medio_ad} AM ${x.volume_medio_am} rec ${brl(x.receita_ad + x.receita_am)} recl ${x.reclamacoes}`).join('\n')) + '</pre>';
  box.hidden = false;
};
$('btn-audit').onclick = () => { auditOn = !auditOn; $('btn-audit').textContent = auditOn ? 'Ocultar auditoria' : 'Mostrar auditoria'; $('audit').style.display = auditOn ? '' : 'none'; };
$('btn-aval').onclick = async () => {
  if (!conv) return;
  const r = await post(`/api/conversations/${conv.conversation_id}/evaluate`);
  $('aval').innerHTML = `<dl><dt>Diagnóstico</dt><dd>${r.diagnostico}/5</dd><dt>Regras</dt><dd>${r.aderencia_regras}/5</dd>
    <dt>Objeção</dt><dd>${r.tratamento_objecao ?? 'n/a'}</dd><dt>Próx. passo</dt><dd>${r.proximo_passo}/5</dd>
    <dt>Inventou info</dt><dd>${r.informacao_inventada ? 'Sim' : 'Não'}</dd><dt>Desc. fora alçada</dt><dd>${r.desconto_fora_alcada ? 'Sim' : 'Não'}</dd>
    <dt>Handoff correto</dt><dd>${r.handoff_correto ? 'Sim' : 'Não'}</dd><dt>Desfecho</dt><dd class="${r.desfecho_ok ? 'ok' : 'bad'}">${esc(r.desfecho_observado)} (esperado: ${esc(r.desfecho_esperado)})</dd></dl>
    <ul>${r.observacoes.map(o => `<li>${esc(o)}</li>`).join('')}</ul>`;
};
$('btn-json').onclick = () => conv && window.open(`/api/conversations/${conv.conversation_id}/export?formato=json`);
$('btn-txt').onclick = () => conv && window.open(`/api/conversations/${conv.conversation_id}/export?formato=txt`);
$('form').onsubmit = async e => {
  e.preventDefault();
  const t = $('msg').value.trim(); if (!t || !conv) return;
  $('msg').value = '';
  try { conv = await post(`/api/conversations/${conv.conversation_id}/messages`, {conteudo: t}); renderChat(); } catch (err) { alert(err.message); }
};
init();
