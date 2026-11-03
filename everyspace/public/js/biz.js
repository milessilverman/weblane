// Everyspace for Business: companies lease roofs, pads, road frontage, walls and lots.
// Everyday renters never see these listings in Explore.
import { $, $$, api, esc, state, cat, term, icon, money, avatar, fmtRange, topbar, bindBack, statusPill, go, toast, saveBtn, TERM_ORDER } from './core.js';
import { art } from './art.js';
import { renderMap } from './explore.js';

const BIZ_GROUPS = ['energy', 'commercial'];
const bizCategories = () => Object.entries(state.catalog.categories).filter(([, c]) => c.audience === 'business');

export async function renderBizHome(view) {
  if (state.me.kind !== 'business') return renderBizLanding(view);
  const f = state.bizFilters ??= { category: '', view: 'list' };
  const { spaces } = await api(`search?audience=business&userId=${state.user}`);
  const shown = spaces.filter((s) => !f.category || s.category === f.category);
  const counts = Object.fromEntries(bizCategories().map(([k]) => [k, spaces.filter((s) => s.category === k).length]));
  const annual = spaces.reduce((sum, s) => sum + annualValue(s), 0);

  view.innerHTML = `
    <div class="biz-hero">
      <div class="brand-row"><div class="brand light">every<b>space</b> <span class="biz-tag">Business</span></div>
        <button class="icon-btn light" id="toggle-view" aria-label="${f.view === 'map' ? 'Show list' : 'Show map'}">${f.view === 'map' ? icon.list : icon.map}</button></div>
      <h1>Sites for ${esc(state.me.name)}</h1>
      <p>Roofs, pads, road frontage, walls and lots, leased straight from owners. No brokers.</p>
      <div class="biz-stats"><div><strong>${spaces.length}</strong><span>sites open</span></div>
        <div><strong>${money(Math.round(annual))}</strong><span>asking rent / yr</span></div>
        <div><strong>${new Set(spaces.map((s) => s.property.id)).size}</strong><span>properties</span></div></div>
    </div>
    <nav class="cat-bar biz" id="types">
      <button class="${!f.category ? 'on' : ''}" data-cat=""><span>🧭</span>All sites</button>
      ${bizCategories().filter(([k]) => counts[k]).map(([k, c]) => `<button class="${f.category === k ? 'on' : ''}" data-cat="${k}"><span>${c.icon}</span>${esc(c.label)}</button>`).join('')}
    </nav>
    <div class="explore-body" id="biz-body"></div>`;
  const body = $('#biz-body');
  if (f.view === 'map') renderMap(body, shown, siteCard);
  else body.innerHTML = shown.length ? `<div class="site-list">${shown.map(siteCard).join('')}</div>` : '<div class="empty">No sites of this type yet.</div>';
  $('#types').onclick = (e) => { const b = e.target.closest('[data-cat]'); if (!b) return; f.category = b.dataset.cat; renderBizHome(view); };
  $('#toggle-view').onclick = () => { f.view = f.view === 'map' ? 'list' : 'map'; renderBizHome(view); };
}

function annualValue(s) {
  if (s.rates?.infrastructure) return s.rates.infrastructure;
  if (s.rates?.lease) return s.rates.lease * 12 * (s.quantity ?? 1);
  if (s.rates?.monthly) return s.rates.monthly * 12 * (s.quantity ?? 1);
  return 0;
}

export function siteCard(s) {
  const facts = Object.entries(s.specs ?? {}).slice(0, 3);
  const t = TERM_ORDER.find((k) => s.rates?.[k] != null);
  return `<a class="card site-card space-card" href="#/space/${s.id}">
    <div class="thumb">${art(s)}${saveBtn(s.id, s.saved)}</div>
    <div class="card-body">
      <div class="muted small">${s.icon} ${esc(s.categoryLabel)} · ${esc(s.property.title)}</div>
      <strong class="title">${esc(s.title)}</strong>
      ${facts.length ? `<dl class="mini-specs">${facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>` : ''}
      <div class="row-between"><div class="price">${t ? `${money(s.rates[t])}<span>/${term(t).unit}${(s.quantity ?? 1) > 1 ? ' each' : ''}</span>` : ''}</div>
        <span class="link-text">View site ${icon.chevron}</span></div>
    </div></a>`;
}

export async function renderPipeline(view) {
  const all = (await api(`bookings?userId=${state.user}`)).filter((b) => b.role === 'renter');
  const stages = [
    ['proposed', 'Proposed', ['proposed', 'pending']],
    ['site_assessment', 'Site assessment', ['site_assessment']],
    ['contract', 'Contract', ['contract']],
    ['live', 'Active', ['confirmed', 'active']],
  ];
  const yearly = (b) => (b.quote?.schedule?.every === 'year' ? b.quote.schedule.recurring : (b.quote?.schedule?.recurring ?? 0) * 12);
  const live = all.filter((b) => ['confirmed', 'active'].includes(b.status));
  const open = all.filter((b) => ['proposed', 'pending', 'site_assessment', 'contract'].includes(b.status));
  view.innerHTML = `${topbar('Pipeline', { back: false })}
    <div class="page">
      <div class="stats">
        <div><span>Active sites</span><strong>${live.length}</strong></div>
        <div><span>Rent / yr (active)</span><strong>${money(Math.round(live.reduce((s, b) => s + yearly(b), 0)))}</strong></div>
        <div><span>Open proposals</span><strong>${open.length}</strong></div>
      </div>
      <div class="kanban">${stages.map(([key, label, statuses]) => {
        const items = all.filter((b) => statuses.includes(b.status));
        return `<section class="lane"><h2>${label} <span class="muted">${items.length}</span></h2>
          ${items.map((b) => `<a class="card lane-card" href="#/trip/${b.id}">${art(b.primary, { className: 'art lane-art' })}<div class="card-body">
            <strong>${esc(b.itemsLabel)}</strong><div class="muted small">${esc(b.property?.title)} · ${esc(b.host?.name)}</div>
            <div class="small">${term(b.term).label} · ${fmtRange(b)}</div>
            <div class="row-between"><span class="small"><strong>${money(Math.round(yearly(b)))}</strong>/yr</span>${statusPill(b.effective)}</div></div></a>`).join('') || '<div class="lane-empty">Nothing here</div>'}
        </section>`;
      }).join('')}</div>
      ${all.length ? '' : '<div class="empty"><div class="empty-icon">🗂️</div>No proposals yet.<a class="btn" href="#/biz">Find sites</a></div>'}
      ${all.filter((b) => ['declined', 'cancelled'].includes(b.status)).length ? `<h2 class="section-title">Closed</h2>${all.filter((b) => ['declined', 'cancelled'].includes(b.status)).map((b) => `<a class="list-row link" href="#/trip/${b.id}"><div><strong>${esc(b.itemsLabel)}</strong><div class="muted small">${esc(b.property?.title)}</div></div>${statusPill(b.status)}</a>`).join('')}` : ''}
    </div>`;
}

function renderBizLanding(view) {
  const companies = state.users.filter((u) => u.kind === 'business');
  const typical = state.catalog.typical;
  view.innerHTML = `${topbar('Everyspace for Business')}
    <div class="biz-hero landing">
      <div class="brand light">every<b>space</b> <span class="biz-tag">Business</span></div>
      <h1>Lease the sites your business needs, straight from owners.</h1>
      <p>Solar installers, charging networks, telecoms, parcel-locker and delivery companies find roofs, pads, frontage, walls and lots,
        and sign multi-year agreements in one place. These listings are kept off the everyday app, so homeowners' renters never see them.</p>
    </div>
    <div class="page narrow">
      <h2 class="section-title">What you can lease</h2>
      <div class="biz-types">${bizCategories().map(([k, c]) => {
        const t = Object.entries(typical[k] ?? {})[0];
        return `<div class="biz-type"><span>${c.icon}</span><div><strong>${esc(c.label)}</strong>
          <div class="muted small">${t ? `Typical: ${money(t[1])}/${term(t[0]).unit}` : ''} · ${c.terms.map((x) => term(x).label).join(', ')}</div></div></div>`;
      }).join('')}</div>
      <h2 class="section-title">How it works</h2>
      <ol class="steps">
        <li><strong>Find a site.</strong> Filter by type and see the facts that matter: roof size and age, electrical service, traffic, access.</li>
        <li><strong>Send a proposal.</strong> Rent, term and what you'll install. The owner accepts or declines.</li>
        <li><strong>Assess and sign.</strong> Schedule the site visit, then sign a recorded lease with removal and insurance clauses.</li>
        <li><strong>Install and pay.</strong> Rent starts at commissioning and is paid to the owner automatically.</li>
      </ol>
      <h2 class="section-title">Try it as a company <span class="muted small">(demo)</span></h2>
      <div class="people">${companies.map((u) => `<button class="person" data-user="${u.id}">${avatar(u, 40)}<span><strong>${esc(u.name)}</strong><span class="muted small">${esc(u.tagline)}</span></span></button>`).join('')}</div>
      <div class="notice">🏡 <div><strong>Own a roof, lot or wall?</strong> <span class="muted">List it from hosting mode under “Lease to companies”.</span>
        <div style="margin-top:8px"><a class="btn small" href="#/host/new?fresh=1&audience=business">List a site</a></div></div></div>
    </div>`;
  bindBack(view);
  for (const b of $$('[data-user]', view)) b.onclick = () => {
    state.setUser(b.dataset.user); state.setMode('business');
    toast(`Now using Everyspace for Business as ${state.me.name}`);
    go('#/biz');
  };
}
