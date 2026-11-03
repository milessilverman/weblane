// Explore: search, category chips, dates, events, list and map.
import { $, $$, api, esc, state, cat, term, icon, cheapestRate, priceTag, stars, fmtDate, today, openSheet, closeSheet, debounce, TERM_ORDER, TERM_SHORT, money } from './core.js';
import { art } from './art.js';

export async function renderExplore(view) {
  const f = state.filters;
  const groups = Object.entries(state.catalog.groups).filter(([k]) => k !== 'container');
  const whenLabel = f.start && f.end ? `${fmtDate(f.start)} – ${fmtDate(f.end)}` : 'Any dates';
  view.innerHTML = `
    <div class="explore-head">
      <div class="brand-row"><div class="brand">every<b>space</b></div>
        <button class="icon-btn" id="toggle-view" aria-label="Toggle map">${state.view === 'map' ? icon.list : icon.map}</button></div>
      <label class="searchbar">${icon.search}<input id="q" placeholder="Backyard, parking near the fair, solar…" value="${esc(f.q)}" autocomplete="off"></label>
      <div class="when-row">
        <button class="when" id="when">${icon.calendar}<span>${esc(whenLabel)}</span></button>
        <button class="when ${f.term ? 'set' : ''}" id="how-long"><span>${f.term ? TERM_SHORT[f.term] : 'Any length'}</span></button>
      </div>
      <div class="chips scroll" id="groups">
        <button class="chip ${!f.group ? 'on' : ''}" data-group="">✨ All</button>
        ${groups.map(([k, v]) => `<button class="chip ${f.group === k ? 'on' : ''}" data-group="${k}">${state.catalog.groupIcons[k]} ${esc(v)}</button>`).join('')}
      </div>
      ${f.group ? `<div class="chips scroll sub" id="cats">
        <button class="chip small ${!f.category ? 'on' : ''}" data-cat="">All ${esc(state.catalog.groups[f.group].toLowerCase())}</button>
        ${Object.entries(state.catalog.categories).filter(([, c]) => c.group === f.group).map(([k, c]) => `<button class="chip small ${f.category === k ? 'on' : ''}" data-cat="${k}">${c.icon} ${esc(c.label)}</button>`).join('')}
      </div>` : ''}
    </div>
    <div id="explore-body" class="explore-body"><div class="skeleton-grid">${'<div class="skeleton"></div>'.repeat(6)}</div></div>`;

  $('#q').oninput = debounce((e) => { f.q = e.target.value; loadResults(); }, 220);
  $('#groups').onclick = (e) => { const b = e.target.closest('[data-group]'); if (!b) return; f.group = b.dataset.group; f.category = ''; renderExplore(view); };
  if ($('#cats')) $('#cats').onclick = (e) => { const b = e.target.closest('[data-cat]'); if (!b) return; f.category = b.dataset.cat; renderExplore(view); };
  $('#toggle-view').onclick = () => { state.view = state.view === 'map' ? 'list' : 'map'; renderExplore(view); };
  $('#when').onclick = () => datesSheet(() => renderExplore(view));
  $('#how-long').onclick = () => termSheet(() => renderExplore(view));
  await loadResults();
}

async function loadResults() {
  const f = state.filters;
  const params = new URLSearchParams();
  for (const k of ['group', 'category', 'term', 'start', 'end', 'q']) if (f[k]) params.set(k, f[k]);
  const { spaces, packages } = await api(`search?${params}`);
  const body = $('#explore-body');
  if (!body) return;
  const filtered = Object.values(f).some(Boolean);

  if (state.view === 'map') { renderMap(body, spaces); return; }

  const sections = [];
  if (!filtered) {
    sections.push(eventsSection(spaces));
    sections.push(`<a class="host-cta" href="#/host/new" data-hostcta><div><strong>Have a spare driveway, yard or roof?</strong>
      <span>List any part of your place in a few minutes.</span></div><span class="cta-btn">Start earning</span></a>`);
  }
  const visiblePkgs = packages.filter(() => !f.category && (!f.group || f.group === 'living'));
  if (visiblePkgs.length) {
    sections.push(`<h2 class="section-title">Bundles</h2><div class="hscroll">${visiblePkgs.map(packageCard).join('')}</div>`);
  }
  sections.push(`<h2 class="section-title">${filtered ? `${spaces.length} space${spaces.length === 1 ? '' : 's'}` : 'All spaces nearby'}</h2>
    ${spaces.length ? `<div class="grid">${spaces.map(spaceCard).join('')}</div>` : '<div class="empty">Nothing matches. Try another category, length or dates.</div>'}`);
  body.innerHTML = sections.join('');
  const cta = $('[data-hostcta]', body);
  if (cta) cta.onclick = () => state.setMode('host');
}

export function spaceCard(s) {
  const r = cheapestRate(s);
  const datesSet = state.filters.start && state.filters.end;
  const badges = [
    s.policy === 'addon' ? '<span class="badge warn">Add-on only</span>' : '',
    s.policy === 'both' ? '<span class="badge">Tenant discount</span>' : '',
    datesSet && s.unitsFree === 0 ? '<span class="badge bad">Booked</span>' : '',
    datesSet && s.unitsFree > 0 && (s.quantity ?? 1) > 1 ? `<span class="badge ok">${s.unitsFree} left</span>` : '',
    s.eventRates?.some((e) => e.end >= today()) ? '<span class="badge event">Event pricing</span>' : '',
  ].join('');
  return `<a class="card space-card" href="#/space/${s.id}">
    <div class="thumb">${art(s)}<span class="cat-tag">${s.icon} ${esc(s.categoryLabel)}</span></div>
    <div class="card-body">
      <div class="row-between"><strong class="title">${esc(s.title)}</strong>${stars(s.rating)}</div>
      <div class="muted small">${esc(s.property.title)} · ${esc(s.property.city)}</div>
      <div class="price">${r ? `from ${priceTag(r)}` : ''}</div>
      ${badges ? `<div class="badges">${badges}</div>` : ''}
    </div></a>`;
}

function packageCard(p) {
  const price = p.pricing.type === 'fixed'
    ? `${money(p.pricing.rates.monthly ?? Object.values(p.pricing.rates)[0])}<span>/month</span>` : `<span>Save ${p.pricing.percent}%</span>`;
  return `<a class="card pkg-card" href="#/book/pkg/${p.id}">
    <div class="pkg-art n${Math.min(3, p.items.length)}">${p.items.slice(0, 3).map((i) => `<div>${art({ id: i.spaceId, category: i.category })}</div>`).join('')}</div>
    <div class="card-body"><span class="badge">Bundle</span><strong class="title">${esc(p.name)}</strong>
    <div class="muted small">${esc(p.property.title)}</div><div class="price">${price}</div></div></a>`;
}

function eventsSection(spaces) {
  const events = new Map();
  for (const s of spaces) for (const e of s.eventRates ?? []) {
    if (e.end < today()) continue;
    const key = `${e.name}|${e.start}`;
    if (!events.has(key)) events.set(key, { ...e, spaces: [] });
    events.get(key).spaces.push(s);
  }
  const list = [...events.values()].sort((a, b) => (a.start < b.start ? -1 : 1)).slice(0, 4);
  if (!list.length) return '';
  return `<h2 class="section-title">Coming up nearby</h2><div class="hscroll">${list.map((e) => `<a class="card event-card" href="#/space/${e.spaces[0].id}">
      <div class="event-date"><span>${fmtDate(e.start).split(' ')[0]}</span><b>${e.start.slice(8)}${e.end !== e.start ? `–${e.end.slice(8)}` : ''}</b></div>
      <div><strong>${esc(e.name)}</strong><div class="muted small">${e.spaces.map((s) => esc(s.title)).join(' · ')}</div>
      <div class="small">${e.daily ? `${money(e.daily)}/day` : ''}${e.daily && e.hourly ? ' · ' : ''}${e.hourly ? `${money(e.hourly)}/hr` : ''} event rate</div></div></a>`).join('')}</div>`;
}

// ---------- map ----------
function renderMap(body, spaces) {
  const byProp = new Map();
  for (const s of spaces) {
    if (!byProp.has(s.property.id)) byProp.set(s.property.id, { prop: s.property, spaces: [] });
    byProp.get(s.property.id).spaces.push(s);
  }
  const pts = [...byProp.values()];
  if (!pts.length) { body.innerHTML = '<div class="empty">Nothing to show on the map.</div>'; return; }
  const lats = pts.map((p) => p.prop.lat), lngs = pts.map((p) => p.prop.lng);
  const pad = 0.006;
  const [minLat, maxLat] = [Math.min(...lats) - pad, Math.max(...lats) + pad];
  const [minLng, maxLng] = [Math.min(...lngs) - pad, Math.max(...lngs) + pad];
  const W = 400, H = 480;
  const x = (lng) => ((lng - minLng) / (maxLng - minLng || 1)) * W;
  const y = (lat) => H - ((lat - minLat) / (maxLat - minLat || 1)) * H;
  const streets = [];
  for (let i = 0; i < 9; i++) streets.push(`<path d="M0 ${40 + i * 55} L${W} ${20 + i * 58}" class="street ${i % 3 === 1 ? 'major' : ''}"/>`);
  for (let i = 0; i < 8; i++) streets.push(`<path d="M${30 + i * 52} 0 L${50 + i * 50} ${H}" class="street ${i % 3 === 2 ? 'major' : ''}"/>`);
  body.innerHTML = `<div class="map-wrap"><svg class="map" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice">
      <rect width="${W}" height="${H}" class="land"/><path d="M-10 380 Q120 330 200 400 T410 360 V490 H-10 Z" class="water"/>
      <rect x="250" y="70" width="90" height="70" rx="12" class="park"/><rect x="40" y="200" width="70" height="60" rx="10" class="park"/>
      ${streets.join('')}
      <text x="295" y="110" class="map-label">Fairgrounds</text><text x="60" y="235" class="map-label">Park</text><text x="140" y="440" class="map-label">River</text>
      ${pts.map((p, i) => { const r = p.spaces.map(cheapestRate).filter(Boolean).sort((a, b) => a.amount - b.amount)[0];
        return `<g class="pin" data-pin="${i}" transform="translate(${x(p.prop.lng)} ${y(p.prop.lat)})" tabindex="0" role="button">
          <rect x="-30" y="-36" width="60" height="26" rx="13"/><text y="-18">${r ? money(r.amount) : '—'}</text><path d="M-6 -11 L0 -2 L6 -11 Z"/>
          ${p.spaces.length > 1 ? `<circle class="pin-count" cx="28" cy="-36" r="10"/><text class="pin-count-text" x="28" y="-32">${p.spaces.length}</text>` : ''}</g>`; }).join('')}
    </svg><div class="map-panel" id="map-panel"><div class="muted">Tap a pin to see what's there.</div></div></div>`;
  const show = (i) => {
    const p = pts[i];
    for (const g of $$('.pin', body)) g.classList.toggle('on', g.dataset.pin === String(i));
    $('#map-panel').innerHTML = `<div class="row-between"><strong>${esc(p.prop.title)}</strong><span class="muted small">${p.spaces.length} space${p.spaces.length > 1 ? 's' : ''}</span></div>
      <div class="hscroll">${p.spaces.map(spaceCard).join('')}</div>`;
  };
  for (const g of $$('.pin', body)) { g.onclick = () => show(+g.dataset.pin); g.onkeydown = (e) => { if (e.key === 'Enter') show(+g.dataset.pin); }; }
  show(0);
}

// ---------- filter sheets ----------
function datesSheet(done) {
  const f = state.filters;
  const body = openSheet(`<div class="form">
      <div class="two"><label>From<input type="date" id="s-start" value="${f.start}" min="${today()}"></label>
      <label>To<input type="date" id="s-end" value="${f.end}" min="${today()}"></label></div>
      <div class="quick chips">${[['Tonight', 0, 1], ['This weekend', null, null], ['Next 7 days', 0, 7], ['Next month', 0, 30]].map(([l, a, b]) => `<button class="chip small" data-q="${l}" data-a="${a}" data-b="${b}">${l}</button>`).join('')}</div>
      <div class="sheet-actions"><button class="btn ghost" id="s-clear">Any dates</button><button class="btn" id="s-apply">Show spaces</button></div></div>`, { title: 'When?' });
  for (const b of $$('[data-q]', body)) b.onclick = () => {
    const t = today();
    if (b.dataset.q === 'This weekend') {
      const d = new Date(`${t}T00:00:00Z`); const toSat = (6 - d.getUTCDay() + 7) % 7;
      $('#s-start').value = new Date(d.getTime() + toSat * 864e5).toISOString().slice(0, 10);
      $('#s-end').value = new Date(d.getTime() + (toSat + 2) * 864e5).toISOString().slice(0, 10);
    } else {
      $('#s-start').value = new Date(Date.parse(`${t}T00:00:00Z`) + b.dataset.a * 864e5).toISOString().slice(0, 10);
      $('#s-end').value = new Date(Date.parse(`${t}T00:00:00Z`) + b.dataset.b * 864e5).toISOString().slice(0, 10);
    }
  };
  $('#s-clear').onclick = () => { f.start = ''; f.end = ''; closeSheet(); done(); };
  $('#s-apply').onclick = () => {
    const s = $('#s-start').value, e = $('#s-end').value;
    if (s && e && e > s) { f.start = s; f.end = e; } else { f.start = ''; f.end = ''; }
    closeSheet(); done();
  };
}

function termSheet(done) {
  const f = state.filters;
  const hints = { hourly: 'Parties, pool time, a few hours of parking', daily: 'Overnight stays, event-day parking, camping', weekly: 'Short stays, moving-week storage',
    monthly: 'Parking, storage, garden plots, rooms', lease: 'Apartments and long-term spaces, 6–24 months', infrastructure: 'Solar, batteries, chargers, antennas — for companies' };
  const body = openSheet(`<div class="option-list">
      <button class="option ${!f.term ? 'on' : ''}" data-t=""><strong>Any length</strong></button>
      ${TERM_ORDER.map((t) => `<button class="option ${f.term === t ? 'on' : ''}" data-t="${t}"><strong>${term(t).label}</strong><span class="muted small">${hints[t]}</span></button>`).join('')}
    </div>`, { title: 'How long?' });
  for (const b of $$('[data-t]', body)) b.onclick = () => { f.term = b.dataset.t; closeSheet(); done(); };
}

