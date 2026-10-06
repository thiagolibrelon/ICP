// Tema claro/escuro e ícones SVG — mesma linguagem do Simulador Estratégico de Frota (V3).
(function () {
  const SPRITE = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true"><defs>
    <g id="i-sun"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/></g>
    <g id="i-moon"><path d="M20 14.5A8 8 0 019.5 4a8 8 0 105.6 15.4A8 8 0 0020 14.5z"/></g>
    <g id="i-car"><path d="M4 13l1.6-4.4A2 2 0 017.5 7h9a2 2 0 011.9 1.3L20 13M4 13h16v4a1 1 0 01-1 1h-1.5a1 1 0 01-1-1v-1h-9v1a1 1 0 01-1 1H4a1 1 0 01-1-1v-4z"/><circle cx="7" cy="16" r="1"/><circle cx="17" cy="16" r="1"/></g>
    <g id="i-user"><circle cx="12" cy="8" r="3.4"/><path d="M5.5 19.5c1-3.5 3.6-5 6.5-5s5.5 1.5 6.5 5"/></g>
    <g id="i-target"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/></g>
    <g id="i-mic"><rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0013 0M12 17.5V21M9 21h6"/></g>
    <g id="i-stop"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/></g>
    <g id="i-bulb"><path d="M9 18h6M10 21h4M12 3a6 6 0 00-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0012 3z"/></g>
    <g id="i-flag"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></g>
    <g id="i-chart"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></g>
    <g id="i-download"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></g>
    <g id="i-refresh"><path d="M20 11a8 8 0 10-2.3 5.6M20 4v7h-7"/></g>
    <g id="i-send"><path d="M4 12l16-8-6 16-2.5-6.5z"/></g>
    <g id="i-book"><path d="M5 4.5A1.5 1.5 0 016.5 3H19v15H6.5A1.5 1.5 0 005 19.5v-15zM5 19.5A1.5 1.5 0 006.5 21H19"/></g>
    <g id="i-flask"><path d="M9.5 3h5M10 3v6.2L4.8 18.3A1.8 1.8 0 006.4 21h11.2a1.8 1.8 0 001.6-2.7L14 9.2V3M7.5 14.5h9"/></g>
    <g id="i-x"><path d="M6 6l12 12M18 6L6 18"/></g>
    <g id="i-play"><path d="M7 4.5v15l12-7.5z"/></g>
    <g id="i-arrow-left"><path d="M15 5l-7 7 7 7"/></g>
  </defs></svg>`;
  document.body.insertAdjacentHTML('afterbegin', SPRITE);
  window.icon = (nome, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24"><use href="#i-${nome}"/></svg>`;
  document.querySelectorAll('[data-ic]').forEach(el => el.insertAdjacentHTML('afterbegin', window.icon(el.dataset.ic)));

  const html = document.documentElement;
  let tema;
  try { tema = localStorage.getItem('sim-theme'); } catch (e) {}
  if (!tema) tema = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const aplicar = t => {
    html.setAttribute('data-theme', t); tema = t;
    const k = document.querySelector('.tt-k'); if (k) k.innerHTML = window.icon(t === 'dark' ? 'moon' : 'sun');
    try { localStorage.setItem('sim-theme', t); } catch (e) {}
  };
  aplicar(tema);
  const b = document.getElementById('theme-btn');
  if (b) b.onclick = () => aplicar(tema === 'dark' ? 'light' : 'dark');
})();
