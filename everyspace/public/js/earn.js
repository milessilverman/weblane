// "What could my place earn?" estimator, then Saved (wishlist).
import { $, $$, api, esc, state, cat, term, money, topbar, bindBack, bindSteppers, stepper } from './core.js';
import { spaceCard } from './explore.js';

// Each row: what you have, how much of it, and how it turns into monthly income at local EXAMPLE prices
// (TYPICAL + TYPICAL_META in src/catalog.js; San Diego examples researched 2026-11-04). This is an illustration,
// not typical income: the research found no city medians for most of these. Company leases with no published
// rent are "ask for a quote" rows with no dollar figure (research §9: avoid income promises for ordinary roofs).
const ROWS = [
  { key: 'parking', category: 'parking_spot', label: 'Driveway or garage parking spots', unit: 'spots', max: 6, def: 2, monthly: (n, t) => n * t.monthly * 0.75 },
  { key: 'garage', category: 'garage_storage', label: 'Garage storage space (10×20)', unit: 'spaces', max: 4, def: 1, monthly: (n, t) => n * t.monthly * 0.8 },
  { key: 'attic', category: 'attic_storage', label: 'Attic storage', unit: 'areas', max: 2, def: 0, monthly: (n, t) => n * t.monthly * 0.75 },
  { key: 'yard', category: 'backyard', label: 'Backyard for gatherings', unit: 'hours / month', max: 60, def: 4, step: 2, monthly: (n, t) => n * t.hourly },
  { key: 'room', category: 'private_room', label: 'Spare room, rented monthly', unit: 'rooms', max: 3, def: 0, monthly: (n, t) => n * t.monthly },
  { key: 'pool', category: 'pool', label: 'Pool', unit: 'hours / month', max: 60, def: 0, step: 4, monthly: (n, t) => n * t.hourly },
  { key: 'garden', category: 'garden_plot', label: 'Garden plots', unit: 'plots', max: 8, def: 0, monthly: (n, t) => n * t.lease },
  { key: 'sign', category: 'signage', label: 'Road frontage for a billboard', unit: 'site', max: 1, def: 0, business: true, monthly: (n, t) => n * t.lease },
  { key: 'roof', category: 'rooftop_solar', label: 'Large roof for solar', business: true, quote: true },
  { key: 'battery', category: 'battery_site', label: 'Pad for a battery', business: true, quote: true },
  { key: 'frontage', category: 'charger_site', label: 'Lot for EV fast chargers', business: true, quote: true },
  { key: 'locker', category: 'parcel_locker', label: 'Wall for a parcel locker', business: true, quote: true },
];

const basisLabel = (meta) => ({ example: 'example listing', benchmark: 'benchmark', assumption: 'our assumption', unknown: 'no published rent' })[meta.basis] || meta.basis;

export function renderEarn(view) {
  const have = state.earn2 ??= Object.fromEntries(ROWS.filter((r) => !r.quote).map((r) => [r.key, r.def]));
  const row = (r) => {
    const meta = cat(r.category).typicalMeta;
    if (r.quote) return `<div class="earn-row quote-row"><span class="earn-icon">${cat(r.category).icon}</span>
      <div><strong>${esc(r.label)}</strong><div class="muted small">${esc(meta.note || 'Rent is negotiated with each company.')}</div></div>
      <a class="btn small ghost" href="#/host/new?fresh=1&category=${r.category}">Ask for quotes</a></div>`;
    return `<div class="earn-row" data-row="${r.key}"><span class="earn-icon">${cat(r.category).icon}</span>
      <div><strong>${esc(r.label)}</strong><div class="muted small" data-amount="${r.key}"></div>
        <div class="muted small src">${esc(basisLabel(meta))}: ${esc(meta.source)}</div></div>
      ${stepper(r.key, have[r.key], { min: 0, max: r.max, inc: r.step ?? 1 })}</div>`;
  };
  view.innerHTML = `${topbar('What could you earn?')}
    <div class="page narrow">
      <div class="earn-total"><span>Illustration, at local example prices</span><strong id="total-month">$0</strong><em id="total-year"></em>
        <div class="earn-split"><div><i class="dot consumer"></i>Everyday renters <b id="t-consumer"></b></div><div><i class="dot business"></i>From companies <b id="t-business"></b></div></div>
        <div class="split-bar"><i id="bar-consumer"></i><i id="bar-business"></i></div></div>
      <p class="muted small">This isn't typical income. It multiplies what you have by dated example listings in San Diego (each source is shown), with about 75% occupancy for parking and storage. Your price, demand and local rules decide the real number. Everyspace keeps 3% of your price.</p>
      <h2 class="section-title">Spaces you could rent to people</h2>
      <div class="earn-list">${ROWS.filter((r) => !r.business).map(row).join('')}</div>
      <h2 class="section-title">Spaces companies lease <span class="muted small">multi-year, negotiated</span></h2>
      <div class="earn-list">${ROWS.filter((r) => r.business).map(row).join('')}</div>
      <p class="muted small">Most companies don't publish what they pay. Ordinary house roofs have no standard rent: solar programs mostly lease roofs over 40,000 sq ft. List the site and companies send proposals.</p>
      <div id="earn-cta" class="earn-cta"></div>
    </div>`;
  bindBack(view);

  const update = () => {
    let consumer = 0, business = 0;
    for (const r of ROWS.filter((x) => !x.quote)) {
      const n = have[r.key], t = cat(r.category).typical || {};
      const m = r.monthly(n, t) || 0;
      if (r.business) business += m; else consumer += m;
      const first = Object.entries(t)[0];
      $(`[data-amount="${r.key}"]`, view).innerHTML = n
        ? `${n.toLocaleString()} ${esc(r.unit)} · <strong>≈ ${money(Math.round(m))}/mo</strong>`
        : first ? `${esc(r.unit)} · example ${money(first[1])}/${term(first[0]).unit}` : esc(r.unit);
    }
    const total = consumer + business;
    $('#total-month').textContent = `${money(Math.round(total))}/mo`;
    $('#total-year').textContent = `≈ ${money(Math.round(total * 12))} a year`;
    $('#t-consumer').textContent = money(Math.round(consumer));
    $('#t-business').textContent = money(Math.round(business));
    $('#bar-consumer').style.width = `${total ? (consumer / total) * 100 : 50}%`;
    $('#bar-business').style.width = `${total ? (business / total) * 100 : 50}%`;
    const picked = ROWS.filter((r) => !r.quote && have[r.key] > 0);
    $('#earn-cta').innerHTML = picked.length
      ? `<h2 class="section-title">Start with one</h2><div class="chips wrap">${picked.map((r) => `<a class="chip" href="#/host/new?fresh=1&category=${r.category}">${cat(r.category).icon} List ${esc(cat(r.category).label.toLowerCase())}</a>`).join('')}</div>`
      : '';
  };
  bindSteppers(view, (name, v) => { have[name] = v; update(); });
  update();
}

export async function renderSaved(view) {
  const saved = await api(`saves?userId=${state.user}`);
  view.innerHTML = `${topbar('Saved', { back: false })}
    <div class="page">${saved.length
      ? `<p class="muted">${saved.length} space${saved.length === 1 ? '' : 's'} you're keeping an eye on.</p><div class="grid">${saved.map((s) => spaceCard({ ...s, saved: true })).join('')}</div>`
      : '<div class="empty"><div class="empty-icon">♡</div>Tap the heart on any space to save it here.<a class="btn" href="#/explore">Explore</a></div>'}</div>`;
  for (const a of $$('.space-card', view)) a.setAttribute('data-saved-card', '');
}
