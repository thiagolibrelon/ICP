let tr = null, micIndisponivel = false, coachInicial = true;
const $ = id => document.getElementById(id);
const api = async (url, opts) => {
  const r = await fetch(url, opts && {headers: {'Content-Type': 'application/json'}, ...opts});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {method: 'POST', body: JSON.stringify(body || {})});
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const brl = v => v == null ? '—' : Number(v).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
const cor = n => n == null ? 'var(--muted)' : n >= 8 ? 'var(--win)' : n >= 5 ? 'var(--amber)' : 'var(--red)';
const sleep = ms => new Promise(r => setTimeout(r, ms));
try { $('vendedor').value = localStorage.getItem('vendedor') || ''; } catch (e) {}

async function init() {
  const h = await api('/api/health');
  $('llm').className = 'tb-status' + (h.llm_configurado ? '' : ' off');
  $('llm').innerHTML = `<span class="dot"></span>${h.llm_configurado ? 'GPT conectado' : 'GPT não configurado'}`;
  const ps = await api('/api/treino/personas');
  $('cliente').innerHTML = ps.map(p => `<option value="${p.cliente_id}">${esc(p.razao_social)} — ${esc(p.contato)} (${p.icp})</option>`).join('');
}

function render() {
  const c = tr.cliente, pr = tr.progresso;
  $('info').innerHTML = `<dl><dt>Empresa</dt><dd>${esc(c.razao_social)}</dd><dt>Contato</dt><dd>${esc(tr.contato.nome)} · ${esc(tr.contato.cargo)}</dd>
    <dt>Cidade</dt><dd>${esc(c.cidade)}</dd><dt>Perfil</dt><dd>${esc(c.icp)} · Tier ${esc(c.tier)}</dd>
    <dt>Uso atual</dt><dd>${esc(c.situacao)}</dd><dt>Treino</dt><dd>${tr.modo === 'PROVA' ? 'Prova' : 'Treino'}${tr.modo === 'TREINO' ? (tr.coach ? ' (coach ligado)' : ' (coach desligado)') : ''} · ${esc(tr.dificuldade)} · ${tr.frente === 'ativa' ? 'contato ativo' : 'receptivo'}</dd></dl>
    ${tr.frente === 'ativa' && tr.motivo ? `<div class="roteiro" style="margin-top:8px"><b>Motivo do contato (carteira):</b> ${esc(tr.motivo.titulo)} · ${esc(tr.motivo.resumo)}.<br>Você inicia a conversa: diga quem é, traga o motivo e faça uma pergunta.</div>` : ''}`;
  $('progresso').innerHTML = `Informações-chave descobertas: <b>${pr.segredos_descobertos} de ${pr.segredos_total}</b> · cliente: <b>${esc(pr.estado_cliente)}</b>`;
  $('chat').innerHTML = tr.mensagens.map(m => m.role === 'coach'
      ? `<div class="m coach">${icon('bulb')} <b>Coach:</b> ${esc(m.conteudo)}</div>`
      : `<div class="m ${m.role === 'vendedor' ? 'cliente' : 'vendedor'}"><div class="who">${m.role === 'vendedor' ? 'Você (vendedor)' : esc(tr.contato.nome) + ' · cliente'}</div>${m.meta && m.meta.audio ? icon('mic') + ' ' : ''}${esc(m.conteudo)}</div>`).join('');
  if (!tr.mensagens.length) $('chat').innerHTML = '<div class="nota">Contato ativo: você começa. Escreva a primeira mensagem para o cliente.</div>';
  $('chat').scrollTop = 1e9;
  const dicas = tr.mensagens.filter(m => m.role === 'coach');
  pintarCoach();
  $('coach').innerHTML = tr.modo === 'PROVA' ? 'Modo prova: sem dicas. Boa sorte!' : !tr.coach ? 'Coach IA desligado: sem dicas neste treino.' + (dicas.length ? ` Última dica: ${esc(dicas[dicas.length - 1].conteudo)}` : '') : dicas.length ? `${icon('bulb')} ${esc(dicas[dicas.length - 1].conteudo)}` : 'A primeira dica aparece depois da sua primeira resposta.';
  const ativo = tr.status === 'ATIVO';
  ['msg', 'btn-enviar', 'btn-encerrar'].forEach(id => $(id).disabled = !ativo);
  $('btn-mic').disabled = !ativo || micIndisponivel;
  if (tr.resultado) mostrarResultado(tr.resultado, false);
}

$('btn-iniciar').onclick = async () => {
  const v = $('vendedor').value.trim();
  if (!v) { alert('Informe seu nome.'); return; }
  try { localStorage.setItem('vendedor', v); } catch (e) {}
  tr = await post('/api/treino', {vendedor: v, cliente_id: $('cliente').value, modo: $('modo').value, dificuldade: $('dificuldade').value, frente: $('frente').value,
    coach: $('modo').value === 'TREINO' ? coachInicial : false});
  $('resultado').innerHTML = '<div class="badge">A nota aparece quando você encerra.</div>'; $('calc-res').textContent = 'Calculadora pronta.';
  render(); $('msg').focus();
};

// coach IA: liga/desliga antes de iniciar (vale para o próximo treino) ou no meio (vale a partir da próxima resposta)
function pintarCoach() {
  const prova = (tr && tr.status === 'ATIVO' ? tr.modo : $('modo').value) === 'PROVA';
  const ligado = !prova && (tr && tr.status === 'ATIVO' ? tr.coach : coachInicial);
  $('btn-coach').disabled = prova;
  $('btn-coach').setAttribute('aria-pressed', String(ligado));
  $('btn-coach').classList.toggle('primary', ligado);
  $('btn-coach').lastChild.textContent = prova ? 'Coach IA: desligado na prova' : ligado ? 'Coach IA: ligado' : 'Coach IA: desligado';
}
$('modo').onchange = () => { if (!tr || tr.status !== 'ATIVO') pintarCoach(); };
$('btn-coach').onclick = async () => {
  if (tr && tr.status === 'ATIVO') {
    try { tr = await post(`/api/treino/${tr.treino_id}/coach`, {ligado: !tr.coach}); coachInicial = tr.coach; render(); }
    catch (err) { alert(err.message); }
  } else { coachInicial = !coachInicial; pintarCoach(); }
};

async function enviar(chamada, previa) {
  $('msg').disabled = true;
  $('chat').insertAdjacentHTML('beforeend', `<div class="m cliente"><div class="who">Você (vendedor)</div>${previa}</div><div class="nota digitando">${esc(tr.contato.nome)} está digitando…</div>`);
  $('chat').scrollTop = 1e9;
  try { const novo = await chamada(); await sleep(600); tr = novo; render(); }
  catch (err) { alert(err.message); render(); }
  $('msg').focus();
}
$('form').onsubmit = e => {
  e.preventDefault();
  const t = $('msg').value.trim(); if (!t || !tr) return;
  $('msg').value = '';
  enviar(() => post(`/api/treino/${tr.treino_id}/mensagem`, {conteudo: t}), esc(t));
};

function condicao() {
  const f = new FormData($('calc'));
  const produto = f.get('produto');
  return {modelo: f.get('modelo'), cidade: f.get('cidade'), produto, quantidade: +f.get('quantidade') || 1,
    prazo_meses: produto === 'AM' ? +f.get('prazo_meses') : null, dias: produto === 'AD' ? (+f.get('dias') || 1) : null,
    desconto_pct: +f.get('desconto_pct') || 0, pacotes_km_extra: produto === 'AM' ? (+f.get('pacotes_km_extra') || null) : null,
    adicionais: produto === 'AM' ? ['PROTECAO_TOTAL', 'TELEMETRIA'].filter(a => f.get(a)) : []};
}
function mostrarCalc(r) {
  if (r.erro) { $('calc-res').innerHTML = `<span class="bad">${esc(r.erro)}</span>`; return; }
  if (r.proposta_id) { $('calc-res').innerHTML = `<b class="ok">Proposta ${esc(r.proposta_id)} registrada</b> · ${r.quantidade} ${esc(r.modelo)} · ${brl(r.total_mensal ?? r.total)}${r.total_mensal ? '/mês' : ''}. Agora confirme com o cliente.`; return; }
  const st = {APROVADO: ['ok', 'Aprovado na sua alçada'], APROVADO_GERENTE: ['ok', 'Aprovado pelo gerente (com contrapartida)'],
    NEGADO_GERENTE: ['bad', 'Gerente negou: falta contrapartida'], ACIMA_DO_LIMITE: ['bad', 'Acima do que pode ser aprovado']}[r.status] || ['', r.status];
  $('calc-res').innerHTML = `<b class="${st[0]}">${st[1]}</b><br>${r.quantidade} ${esc(r.modelo)} · ${esc(r.cidade)} · ${r.produto === 'AM' ? r.prazo_meses + ' meses' : r.dias + ' dias'}
    <br>Unitário: ${brl(r.preco_unitario_final)} (tabela ${brl(r.preco_tabela_unitario)}${r.desconto_volume_pct ? ', volume −' + r.desconto_volume_pct + '%' : ''})
    ${r.adicionais_total_mensal ? `<br>Adicionais: ${brl(r.adicionais_total_mensal)}/mês` : ''}
    <br><b>Total: ${brl(r.total_mensal ?? r.total)}${r.total_mensal ? '/mês' : ''}</b>
    <br>Estoque: ${r.estoque_disponivel}${r.estoque_suficiente ? '' : ` <span class="bad">(faltam ${r.falta_unidades}; entrega em ${r.prazo_entrega_se_faltar_dias} dias)</span>`}
    ${r.contraproposta_desconto_pct != null ? `<br><span class="warn">Pode oferecer até ${r.contraproposta_desconto_pct}% nestas condições. ${esc(r.orientacao)}</span>` : ''}`;
}
$('btn-avaliar').onclick = async () => { if (tr) mostrarCalc(await post(`/api/treino/${tr.treino_id}/avaliar-condicao`, condicao())); };
$('btn-registrar').onclick = async () => { if (tr) mostrarCalc(await post(`/api/treino/${tr.treino_id}/registrar-proposta`, condicao())); };

$('btn-encerrar').onclick = async () => {
  if (!tr || !confirm('Encerrar a conversa e ver sua nota?')) return;
  $('btn-encerrar').disabled = true; $('resultado').innerHTML = '<div class="badge">Avaliando sua conversa…</div>';
  try { tr = await post(`/api/treino/${tr.treino_id}/encerrar`); render(); mostrarResultado(tr.resultado, true); }
  catch (err) { alert(err.message); $('btn-encerrar').disabled = false; }
};

function mostrarResultado(r, abrir) {
  $('resultado').innerHTML = `<div class="eyebrow">Sua nota</div><div class="nota-geral" style="color:${cor(r.nota_geral)}">${r.nota_geral}<small>/10</small></div><button id="btn-ver" class="primary" style="margin-top:10px">Ver justificativa completa</button>`;
  $('btn-ver').onclick = () => abrirResultado(r);
  if (abrir) abrirResultado(r);
}
function abrirResultado(r) {
  $('modal-titulo').textContent = 'Seu resultado';
  const dims = Object.values(r.dimensoes);
  $('modal-conteudo').innerHTML = `${r.aviso ? `<div class="bad">${esc(r.aviso)}</div>` : ''}
    <div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap"><div class="nota-geral" style="color:${cor(r.nota_geral)}">${r.nota_geral}<small>/10</small></div>
      <div>${esc(r.resumo || '')}<div class="badge">Cliente terminou: ${esc(r.estado_final_do_cliente)} · ${r.descobertas.segredos_descobertos} de ${r.descobertas.segredos_total} informações-chave descobertas</div></div></div>
    ${r.coach ? `<div class="rotulo">Coach: ${esc(NOME_COACH[r.coach.situacao] || r.coach.situacao)} · ${r.coach.dicas} dica(s)${r.coach.trocas.length ? ` · ${r.coach.trocas.length} troca(s) no meio do treino` : ''}</div>` : ''}
    ${(r.pontos_fortes || []).length ? `<h2>Pontos fortes</h2><ul>${r.pontos_fortes.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    ${(r.pontos_a_melhorar || []).length ? `<h2>Onde melhorar</h2><ul>${r.pontos_a_melhorar.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    <h2>Nota por dimensão (régua C12)</h2>
    ${dims.map(d => `<div class="dim"><div class="dim-top"><span>${esc(d.nome)}</span><span style="color:${cor(d.nota)}">${d.nota ?? '—'}</span></div>
      <div class="barra"><i style="width:${(d.nota || 0) * 10}%;background:${cor(d.nota)}"></i></div>
      <div>${esc(d.justificativa)}</div>
      ${d.segredos ? `<div class="rotulo">${esc(d.segredos)}</div>` : ''}
      ${d.qualidade_c12 ? `<div class="rotulo">Challenger C12: qualidade ${esc(d.qualidade_c12)}${(d.codigos || []).length ? ' · ' + d.codigos.map(esc).join(', ') : ''}</div>` : ''}
      ${d.tipo ? `<div class="rotulo">Fechamento: ${esc(d.tipo)} · próximo passo ${esc(d.proximo_passo_claro)} · prazo ${esc(d.prazo_definido)}</div>` : ''}
      ${d.ancora ? `<div class="rotulo">Trecho seu${d.ancora_verificada ? '' : ' (não localizado exatamente)'}:</div><div class="citacao">“${esc(d.ancora)}”</div>` : ''}
      ${(d.achados || []).length ? `<ul>${d.achados.map(a => `<li>${esc(a)}</li>`).join('')}</ul>` : ''}
      ${d.como_melhorar ? `<div class="rotulo">Como melhorar</div><div>${esc(d.como_melhorar)}</div>` : ''}
      ${d.exemplo ? `<div class="rotulo">Você poderia ter dito</div><div class="citacao">“${esc(d.exemplo)}”</div>` : ''}</div>`).join('')}
    ${r.descobertas.o_que_faltou_descobrir.length ? `<h2>O que você não descobriu</h2><ul>${r.descobertas.o_que_faltou_descobrir.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    <h2>Desafio deste cenário</h2><div>${esc(r.desafio_do_cenario)}</div>`;
  $('modal').hidden = false;
}
$('btn-fechar-modal').onclick = () => { $('modal').hidden = true; };

// trilha de treinamento: competências (dos 15 prompts de análise), níveis e cenários; nível só conta PROVA
const NIVEL = {bronze: 'Bronze', prata: 'Prata', ouro: 'Ouro'};
$('btn-trilha').onclick = async () => {
  const v = $('vendedor').value.trim();
  const t = await api('/api/treino/trilha' + (v ? '?vendedor=' + encodeURIComponent(v) : ''));
  const prog = {}; ((t.progresso || {}).competencias || []).forEach(c => prog[c.id] = c);
  const nomes = {}; [...$('cliente').options].forEach(o => nomes[o.value] = o.textContent.split(' — ')[0]);
  $('modal-titulo').textContent = 'Trilha de treinamento' + (v ? ' · ' + v : '');
  $('modal-conteudo').innerHTML = `<div class="badge">Nível conta só provas (modo prova, sem coach). É para o seu desenvolvimento, não é ranking.</div>
    ${t.progresso ? `<div class="rotulo" style="margin:8px 0">${t.progresso.provas} prova(s) · ${t.niveis.map(n => `${NIVEL[n.id]} em ${t.progresso.por_nivel[n.id]} de ${t.progresso.total}`).join(' · ')}</div>` : '<div class="rotulo" style="margin:8px 0">Informe seu nome para ver o seu nível.</div>'}
    <div class="rotulo">${t.niveis.map(n => `<b>${NIVEL[n.id]}:</b> ${esc(n.regra)}`).join('<br>')}</div>
    ${t.competencias.map(c => { const p = prog[c.id]; return `<div class="dim"><div class="dim-top"><span>${esc(c.nome)}</span><span>${p ? (p.nivel ? NIVEL[p.nivel] : 'sem nível') : ''}</span></div>
      <div>${esc(c.objetivo)}</div>
      <div class="rotulo">${c.prompts.length ? 'Medido nas ligações por ' + c.prompts.join(', ') + (c.codigos.length ? ' · códigos ' + c.codigos.slice(0, 8).map(esc).join(', ') + (c.codigos.length > 8 ? '…' : '') : '') : 'Regra do sistema'}${c.observacao ? ' · ' + esc(c.observacao) : ''}</div>
      ${p && p.proximo ? `<div class="rotulo">Próximo: ${NIVEL[p.proximo.nivel]} — ${esc(p.proximo.regra)} (${p.proximo.aprovadas} aprovada(s))</div>` : ''}
      <div class="rotulo">Cenários: ${c.cenarios.map(id => `<a href="#" data-cenario="${id}">${esc(nomes[id] || id)}</a>`).join(' · ')}</div></div>`; }).join('')}
    <h2>Os 15 prompts na trilha</h2><table>${t.prompts.map(x => `<tr><td>${x.prompt}</td><td>${esc(x.nome)}</td><td>${x.competencia ? esc((t.competencias.find(c => c.id === x.competencia) || {}).nome) : esc(x.uso)}</td></tr>`).join('')}</table>`;
  $('modal-conteudo').querySelectorAll('[data-cenario]').forEach(a => a.onclick = e => { e.preventDefault(); $('cliente').value = a.dataset.cenario; $('modal').hidden = true; });
  $('modal').hidden = false;
};

const NOME_COACH = {ligado: 'coach IA ligado', desligado: 'coach IA desligado', misto: 'trocado no meio', prova: 'prova'};
$('btn-historico').onclick = async () => {
  const v = $('vendedor').value.trim();
  const h = await api('/api/treino/historico');
  $('modal-titulo').textContent = 'Evolução nos treinos';
  const pc = Object.entries(h.por_coach || {});
  $('modal-conteudo').innerHTML = `<div class="badge">Ordem alfabética — é ferramenta de desenvolvimento, não ranking.</div>
    ${pc.length ? `<div class="rotulo" style="margin:8px 0">Todos os treinos, por coach: ${pc.map(([k, g]) => `${esc(NOME_COACH[k] || k)}: média ${g.media} em ${g.treinos}`).join(' · ')}</div>` : ''}
    ${h.vendedores.map(x => `<div class="dim" style="${x.vendedor === v ? 'border-color:var(--green-l)' : ''}"><div class="dim-top"><span>${esc(x.vendedor)}</span><span>média ${x.media_geral} · última ${x.ultima_nota}</span></div>
      <div class="rotulo">${x.treinos} treinos · evolução: ${x.evolucao.join(' → ')} · ponto a desenvolver: <b>${esc(x.ponto_mais_fraco || '—')}</b></div>
      ${x.por_coach && Object.keys(x.por_coach).length > 1 ? `<div class="rotulo">Média por coach: ${Object.entries(x.por_coach).map(([k, g]) => `${esc(NOME_COACH[k] || k)} ${g.media} (${g.treinos})`).join(' · ')}</div>` : ''}
      <table>${Object.entries(x.media_por_dimensao).map(([k, n]) => `<tr><td>${esc(k)}</td><td style="color:${cor(n)}">${n}</td></tr>`).join('')}</table></div>`).join('') || 'Nenhum treino avaliado ainda.'}`;
  $('modal').hidden = false;
};

// áudio do vendedor (transcrição pelo llm-gate)
let gravador = null, pedacos = [], t0 = 0;
$('btn-mic').onclick = async () => {
  if (gravador && gravador.state === 'recording') { gravador.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    gravador = new MediaRecorder(stream); pedacos = []; t0 = Date.now();
    gravador.ondataavailable = e => pedacos.push(e.data);
    gravador.onstop = async () => {
      stream.getTracks().forEach(t => t.stop()); $('btn-mic').classList.remove('gravando'); $('btn-mic').innerHTML = icon('mic');
      const blob = new Blob(pedacos, {type: gravador.mimeType || 'audio/webm'}), dur = (Date.now() - t0) / 1000;
      const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
      await enviar(async () => {
        const r = await fetch(`/api/treino/${tr.treino_id}/audio`, {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({audio_base64: b64, mime: blob.type, duracao_s: dur})});
        if (r.status === 503) { micIndisponivel = true; throw new Error((await r.json()).detail); }
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
        return r.json();
      }, icon('mic') + ' áudio… <span class="transc">transcrevendo</span>');
    };
    gravador.start(); $('btn-mic').classList.add('gravando'); $('btn-mic').innerHTML = icon('stop');
  } catch (err) { alert('Não consegui acessar o microfone: ' + err.message); }
};
pintarCoach();
init();
