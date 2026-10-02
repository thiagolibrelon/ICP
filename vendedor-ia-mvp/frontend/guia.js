const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const api = async (url, opts) => {
  const r = await fetch(url, opts && {headers: {'Content-Type': 'application/json'}, ...opts});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {method: 'POST', body: JSON.stringify(body || {})});
const del = url => api(url, {method: 'DELETE'});
const semAcento = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const data = iso => iso ? new Date(iso).toLocaleDateString('pt-BR') : '';
const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sem armazenamento: segue sem lembrar */ } };
const lembrar = (k, padrao) => { try { const v = localStorage.getItem(k); return v === null ? padrao : JSON.parse(v); } catch (e) { return padrao; } };
const aviso = msg => { const a = $('aviso'); a.textContent = msg || ''; a.hidden = !msg; };
const erro = e => aviso(`Não deu certo: ${e.message}`);

const ABAS = ['roadmap', 'como-funciona', 'glossario', 'como-utilizar', 'laboratorio'];
const carregadas = {};
let rm = null;                                   // último roadmap recebido do servidor
let soFalta = lembrar('guia.soFalta', false);
let abertas = null;                              // fases abertas (Set); null = ainda não decidido
const notasAbertas = new Set();                  // itens com o painel de notas aberto
const formsAbertos = new Set();                  // fases com o formulário de novo item aberto

function abrirAba(nome) {
  if (!ABAS.includes(nome)) nome = 'roadmap';
  aviso('');
  ABAS.forEach(a => {
    $('painel-' + a).hidden = a !== nome;
    $('tab-' + a).classList.toggle('ativo', a === nome);
    $('tab-' + a).setAttribute('aria-selected', a === nome);
  });
  if (location.hash !== '#' + nome) history.replaceState(null, '', '#' + nome);
  if (!carregadas[nome]) { carregadas[nome] = true; ({'roadmap': carregarRoadmap, 'glossario': carregarGlossario, 'como-funciona': carregarComoFunciona, 'como-utilizar': carregarComoUtilizar, 'laboratorio': carregarLaboratorio})[nome]().catch(e => { carregadas[nome] = false; erro(e); }); }
}

// ------------------------------------------------------------------ GLOSSÁRIO
let glos = null, catAtiva = 'todas';
async function carregarGlossario() {
  glos = await api('/api/guia/glossario');
  const p = $('painel-glossario');
  p.innerHTML = `<div class="barra-busca"><input id="busca" type="search" placeholder="Buscar termo ou explicação (${glos.total_termos} termos)..." autocomplete="off">
    <div class="chips" id="chips"></div></div><div id="termos"></div>`;
  $('busca').oninput = renderGlossario;
  renderGlossario();
}
function renderGlossario() {
  const q = semAcento($('busca').value.trim());
  const contagem = c => c.termos.filter(t => !q || semAcento(t.termo + ' ' + t.definicao).includes(q)).length;
  $('chips').innerHTML = [`<button class="chip ${catAtiva === 'todas' ? 'ativo' : ''}" data-cat="todas">Todas</button>`,
    ...glos.categorias.map(c => `<button class="chip ${catAtiva === c.id ? 'ativo' : ''}" data-cat="${c.id}">${esc(c.titulo)} <span>${contagem(c)}</span></button>`)].join('');
  $('chips').querySelectorAll('.chip').forEach(b => b.onclick = () => { catAtiva = b.dataset.cat; renderGlossario(); });
  const blocos = glos.categorias.filter(c => catAtiva === 'todas' || c.id === catAtiva).map(c => {
    const termos = c.termos.filter(t => !q || semAcento(t.termo + ' ' + t.definicao).includes(q));
    if (!termos.length) return '';
    return `<h2 class="cat">${esc(c.titulo)} <small>${esc(c.descricao)}</small></h2>` +
      termos.map(t => `<div class="termo"><b>${esc(t.termo)}</b><p>${esc(t.definicao)}</p></div>`).join('');
  }).join('');
  $('termos').innerHTML = blocos || '<p class="nota">Nenhum termo encontrado.</p>';
}

// ------------------------------------------------------------------ COMO FUNCIONA (as 3 imagens de docs/como_funciona)
const IMAGENS = [
  ['1_chat_x_fernanda.png', 'De um chat com IA para uma vendedora que consulta o sistema', 'Por que mudou: a IA conversa, o sistema decide preço, desconto, estoque e aprovação.'],
  ['2_uma_mensagem_por_dentro.png', 'Uma mensagem por dentro', 'O caminho de cada mensagem: entrada, contexto, decisão do GPT, ferramentas e bases, trava e saída.'],
  ['3_ferramentas_e_bases.png', 'Quando e por que ela consulta cada base', 'As 9 ferramentas (consultar, calcular, registrar) e as bases que cada uma lê ou grava.'],
];
async function carregarComoFunciona() {
  $('painel-como-funciona').innerHTML = `<p class="nota">Como a Fernanda funciona, em 3 imagens prontas para slide (1920×1080). Clique para abrir em tamanho real.
    Arquivo editável: <code>docs/como_funciona/arquitetura.html</code>.</p>` + IMAGENS.map(([arq, titulo, txt], i) => `
    <figure class="figura"><figcaption><b>${i + 1}. ${esc(titulo)}</b><span>${esc(txt)}</span>
      <a href="/como-funciona/${arq}" download><button>${icon('download')} Baixar</button></a></figcaption>
      <a href="/como-funciona/${arq}" target="_blank" rel="noopener"><img src="/como-funciona/${arq}" alt="${esc(titulo)}" loading="lazy"></a></figure>`).join('');
}

// ------------------------------------------------------------------ DOCUMENTOS (Roteiro de Testes e Laboratório, lidos dos .md)
async function carregarDoc(url, painel) {
  const r = await api(url);
  $(painel).innerHTML = `<div class="doc-layout"><nav class="toc"><b>Nesta página</b>${r.toc.map(t => `<a href="#${esc(t.id)}">${esc(t.titulo)}</a>`).join('')}</nav>
    <article class="doc">${r.html}<p class="nota">Texto do arquivo ${esc(r.arquivo)}, atualizado em ${data(r.atualizado_em)}. Para mudar, edite o arquivo.</p></article></div>`;
  $(painel).querySelectorAll('.toc a').forEach(a => a.onclick = ev => {
    ev.preventDefault(); const alvo = $(painel).querySelector(`[id="${a.getAttribute('href').slice(1)}"]`); if (alvo) alvo.scrollIntoView({behavior: 'smooth', block: 'start'});
  });
}
const carregarComoUtilizar = () => carregarDoc('/api/guia/como-utilizar', 'painel-como-utilizar');
const carregarLaboratorio = () => carregarDoc('/api/guia/laboratorio', 'painel-laboratorio');

// ------------------------------------------------------------------ ROADMAP
const ROTULO = {nao_iniciado: 'Não iniciado', em_andamento: 'Em andamento', concluido: 'Concluído', bloqueado: 'Bloqueado'};

async function carregarRoadmap() { rm = await api('/api/roadmap'); renderRoadmap(); }
async function agir(promessa) { try { rm = await promessa; aviso(''); renderRoadmap(); } catch (e) { erro(e); } }

function renderRoadmap() {
  if (abertas === null) {   // abre a fase em que estamos (a primeira com algo pendente) e as que têm andamento ou bloqueio
    abertas = new Set(rm.fases.filter(f => f.resumo.em_andamento || f.resumo.bloqueado).map(f => f.id));
    const primeira = rm.fases.find(f => f.resumo.falta); if (primeira) abertas.add(primeira.id);
  }
  const r = rm.resumo;
  const agora = rm.fases.flatMap(f => f.itens.filter(i => i.status === 'em_andamento' || i.status === 'bloqueado').map(i => ({...i, fase: f.titulo, faseId: f.id})));
  $('painel-roadmap').innerHTML = `
    <div class="kpis">
      <div class="kpi"><b>${r.pct}%</b><span>${r.concluido} de ${r.total} itens concluídos</span></div>
      <div class="kpi"><b>${r.em_andamento}</b><span>em andamento</span></div>
      <div class="kpi"><b class="${r.bloqueado ? 'bad' : ''}">${r.bloqueado}</b><span>bloqueados</span></div>
      <div class="kpi"><b>${r.falta}</b><span>ainda faltam</span></div>
    </div>
    <div class="barra grande"><i style="width:${r.pct}%;background:var(--win)"></i></div>
    <div class="agora"><h2>Onde estou agora</h2>${agora.length ? agora.map(i => `<div class="agora-item"><span class="st ${i.status}">${ROTULO[i.status]}</span> <a href="#" data-ir="${esc(i.id)}">${esc(i.titulo)}</a> <small>${esc(i.fase)}</small></div>`).join('')
      : '<p class="nota">Nenhum item em andamento. Mude o status de um item para marcá-lo aqui.</p>'}</div>
    <div class="controles"><label><input type="checkbox" id="so-falta" ${soFalta ? 'checked' : ''}> Mostrar só o que falta</label>
      <button id="exp-tudo">Expandir tudo</button><button id="rec-tudo">Recolher tudo</button>
      <small class="badge">O que você marca fica salvo neste computador (guia/roadmap_progresso.json).</small></div>
    <div id="fases">${rm.fases.map(renderFase).join('')}</div>`;
  ligarRoadmap();
}

function renderFase(f) {
  const r = f.resumo, itens = f.itens.filter(i => !soFalta || i.status !== 'concluido');
  const aberta = abertas.has(f.id);
  return `<details class="fase" data-fase="${f.id}" ${aberta ? 'open' : ''}>
    <summary><span class="fase-titulo">${esc(f.titulo)}</span> <span class="periodo">${esc(f.periodo)}</span>
      <span class="fase-res">${r.concluido}/${r.total}${r.bloqueado ? ` · <span class="bad">${r.bloqueado} bloqueado(s)</span>` : ''}</span>
      <span class="barra"><i style="width:${r.pct}%;background:var(--win)"></i></span></summary>
    ${f.descricao ? `<p class="fase-desc">${esc(f.descricao)}</p>` : ''}
    ${itens.length ? itens.map(renderItem).join('') : '<p class="nota">Tudo concluído nesta fase.</p>'}
    <div class="novo">${formsAbertos.has(f.id) ? `<form data-novo="${f.id}"><input name="titulo" placeholder="Título do novo item" maxlength="200" required>
        <input name="descricao" placeholder="Descrição (opcional)" maxlength="1000"><button class="primary">Adicionar</button><button type="button" data-cancelar="${f.id}">Cancelar</button></form>`
      : `<button data-mais="${f.id}">+ Adicionar item</button>`}</div></details>`;
}

function renderItem(i) {
  const notas = i.notas || [], aberto = notasAbertas.has(i.id);
  return `<div class="item st-${i.status}" id="item-${esc(i.id)}">
    <div class="item-topo">
      <select data-status="${esc(i.id)}" class="st ${i.status}" aria-label="Status">${Object.entries(ROTULO).map(([k, v]) => `<option value="${k}" ${k === i.status ? 'selected' : ''}>${v}</option>`).join('')}</select>
      <div class="item-corpo"><b>${i.marco ? '🏁 ' : ''}${esc(i.titulo)}</b>
        <div class="meta">${i.trilha ? `<span class="tag">${esc(i.trilha)}</span>` : ''}${i.prazo ? `<span class="tag prazo">prazo ${esc(i.prazo)}</span>` : ''}${i.concluido_em ? `<span class="tag ok-tag">concluído em ${data(i.concluido_em)}</span>` : ''}${i.fonte ? `<span class="fonte">${esc(i.fonte)}</span>` : ''}</div>
        ${i.descricao ? `<p class="item-desc">${esc(i.descricao)}</p>` : ''}</div>
      <div class="item-acoes"><button data-notas="${esc(i.id)}">Notas${notas.length ? ` (${notas.length})` : ''}</button>${i.custom ? `<button data-remover="${esc(i.id)}" title="Remover este item">✕</button>` : ''}</div>
    </div>
    ${aberto ? `<div class="notas">${notas.map(n => `<div class="nota-linha"><span>${data(n.em)}</span> <p>${esc(n.texto)}</p><button data-rmnota="${esc(i.id)}|${esc(n.id)}" title="Apagar nota">✕</button></div>`).join('') || '<p class="nota">Sem notas ainda.</p>'}
      <form data-anotar="${esc(i.id)}"><input name="texto" placeholder="O que avançou? (ex.: reunião feita, aguardando resposta do gate...)" maxlength="1000" required><button class="primary">Anotar</button></form></div>` : ''}
  </div>`;
}

function ligarRoadmap() {
  const p = $('painel-roadmap');
  $('so-falta').onchange = e => { soFalta = e.target.checked; guardar('guia.soFalta', soFalta); renderRoadmap(); };
  $('exp-tudo').onclick = () => { abertas = new Set(rm.fases.map(f => f.id)); renderRoadmap(); };
  $('rec-tudo').onclick = () => { abertas = new Set(); renderRoadmap(); };
  p.querySelectorAll('details.fase').forEach(d => d.addEventListener('toggle', () => { d.open ? abertas.add(d.dataset.fase) : abertas.delete(d.dataset.fase); }));
  p.querySelectorAll('[data-ir]').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    const fase = rm.fases.find(f => f.itens.some(i => i.id === a.dataset.ir));
    if (fase && !abertas.has(fase.id)) { abertas.add(fase.id); renderRoadmap(); }
    const el = document.getElementById('item-' + a.dataset.ir); if (el) { el.scrollIntoView({behavior: 'smooth', block: 'center'}); el.classList.add('destaque'); setTimeout(() => el.classList.remove('destaque'), 1500); }
  });
  p.querySelectorAll('[data-status]').forEach(s => s.onchange = () => agir(post(`/api/roadmap/${encodeURIComponent(s.dataset.status)}/status`, {status: s.value})));
  p.querySelectorAll('[data-notas]').forEach(b => b.onclick = () => { const id = b.dataset.notas; notasAbertas.has(id) ? notasAbertas.delete(id) : notasAbertas.add(id); renderRoadmap(); });
  p.querySelectorAll('[data-anotar]').forEach(f => f.onsubmit = ev => { ev.preventDefault(); agir(post(`/api/roadmap/${encodeURIComponent(f.dataset.anotar)}/notas`, {texto: f.texto.value})); });
  p.querySelectorAll('[data-rmnota]').forEach(b => b.onclick = () => { const [i, n] = b.dataset.rmnota.split('|'); if (confirm('Apagar esta nota?')) agir(del(`/api/roadmap/${encodeURIComponent(i)}/notas/${encodeURIComponent(n)}`)); });
  p.querySelectorAll('[data-mais]').forEach(b => b.onclick = () => { formsAbertos.add(b.dataset.mais); abertas.add(b.dataset.mais); renderRoadmap(); });
  p.querySelectorAll('[data-cancelar]').forEach(b => b.onclick = () => { formsAbertos.delete(b.dataset.cancelar); renderRoadmap(); });
  p.querySelectorAll('[data-novo]').forEach(f => f.onsubmit = ev => { ev.preventDefault(); formsAbertos.delete(f.dataset.novo); agir(post('/api/roadmap/itens', {fase_id: f.dataset.novo, titulo: f.titulo.value, descricao: f.descricao.value})); });
  p.querySelectorAll('[data-remover]').forEach(b => b.onclick = () => { if (confirm('Remover este item?')) agir(del(`/api/roadmap/itens/${encodeURIComponent(b.dataset.remover)}`)); });
}

ABAS.forEach(a => $('tab-' + a).onclick = () => abrirAba(a));
window.addEventListener('hashchange', () => { const h = location.hash.slice(1); if (ABAS.includes(h)) abrirAba(h); });
abrirAba(ABAS.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'roadmap');
