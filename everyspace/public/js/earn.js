// "What could my place earn?" estimator, then Saved (wishlist).
import { $, $$, api, esc, state, cat, term, money, topbar, bindBack, bindSteppers, stepper } from './core.js';
import { spaceCard } from './explore.js';

// Each row: what you have, how much of it, and how it turns into monthly income at typical local prices.
const ROWS = [
  { key: 'parking', category: 'parking_spot', label: 'Driveway or garage parking spots', unit: 'spots', max: 6, def: 2, monthly: (n, t) => n * t.monthly * 0.75 },
  { key: 'garage', category: 'garage_storage', label: 'Garage storage bays (~100 sq ft)', unit: 'bays', max: 6, def: 1, monthly: (n, t) => n * t.monthly * 0.8 },
  { key: 'attic', category: 'attic_storage', label: 'Attic or basement storage', unit: 'areas', max: 2, def: 0, monthly: (n, t) => n * t.monthly * 0.75 },
  { key: 'yard', category: 'backyard', label: 'Backyard rentals', unit: 'hours / month', max: 60, def: 8, step: 4, monthly: (n, t) => n * t.hourly },
  { key: 'room', category: 'private_room', label: 'Spare room', unit: 'nights / month', max: 30, def: 0, step: 2, monthly: (n, t) => n * t.daily },
  { key: 'pool', category: 'pool', label: 'Pool', unit: 'hours / month', max: 60, def: 0, step: 4, monthly: (n, t) => n * t.hourly },
  { key: 'garden', category: 'garden_plot', label: 'Garden plots', unit: 'plots', max: 8, def: 0, monthly: (n, t) => n * t.monthly * 0.9 },
  { key: 'roof', category: 'rooftop_solar', label: 'Sunny roof area', unit: 'sq ft', max: 3000, def: 0, step: 100, business: true, monthly: (n, t) => (n / 600) * t.infrastructure / 12 },
  { key: 'battery', category: 'battery_site', label: 'Pad or wall for a battery', unit: 'sites', max: 1, def: 0, business: true, monthly: (n, t) => n * t.infrastructure / 12 },
  { key: 'frontage', category: 'charger_site', label: 'Road frontage for EV chargers', unit: 'sites', max: 1, def: 0, business: true, monthly: (n, t) => n * t.infrastructure / 12 },
  { key: 'locker', category: 'parcel_locker', label: 'Wall for a parcel locker', unit: 'sites', max: 1, def: 0, business: true, monthly: (n, t) => n * t.infrastructure / 12 },
];

export function renderEarn(view) {
  const have = state.earn ??= Object.fromEntries(ROWS.map((r) => [r.key, r.def]));
  const row = (r) => `<div class="earn-row" data-row="${r.key}"><span class="earn-icon">${cat(r.category).icon}</span>
      <div><strong>${esc(r.label)}</strong><div class="muted small" data-amount="${r.key}"></div></div>
      ${stepper(r.key, have[r.key], { min: 0, max: r.max, inc: r.step ?? 1 })}</div>`;
  view.innerHTML = `${topbar('What could you earn?')}
    <div class="page narrow">
      <div class="earn-total"><span>Estimated income</span><strong id="total-month">$0</strong><em id="total-year"></em>
        <div class="earn-split"><div><i class="dot consumer"></i>Everyday renters <b id="t-consumer"></b></div><div><i class="dot business"></i>From companies <b id="t-business"></b></div></div>
        <div class="split-bar"><i id="bar-consumer"></i><i id="bar-business"></i></div></div>
      <h2 class="section-title">Spaces you could rent to people</h2>
      <div class="earn-list">${ROWS.filter((r) => !r.business).map(row).join('')}</div>
      <h2 class="section-title">Spaces companies lease <span class="muted small">multi-year, paid yearly</span></h2>
      <div class="earn-list">${ROWS.filter((r) => r.business).map(row).join('')}</div>
      <p class="muted small">Estimates use typical prices near you and realistic occupancy (about 75% for parking and storage). Actual earnings depend on demand, season and your prices. Everyspace keeps 3%.</p>
      <div id="earn-cta" class="earn-cta"></div>
    </div>`;
  bindBack(view);

  const update = () => {
    let consumer = 0, business = 0;
    for (const r of ROWS) {
      const n = have[r.key];
      const m = r.monthly(n, cat(r.category).typical);
      if (r.business) business += m; else consumer += m;
      $(`[data-amount="${r.key}"]`, view).innerHTML = n
        ? `${n.toLocaleString()} ${esc(r.unit)} · <strong>≈ ${money(Math.round(m))}/mo</strong>`
        : (([t, v]) => `${esc(r.unit)} · typical ${money(v)}/${term(t).unit}`)(Object.entries(cat(r.category).typical)[0]);
    }
    const total = consumer + business;
    $('#total-month').textContent = `${money(Math.round(total))}/mo`;
    $('#total-year').textContent = `≈ ${money(Math.round(total * 12))} a year`;
    $('#t-consumer').textContent = money(Math.round(consumer));
    $('#t-business').textContent = money(Math.round(business));
    $('#bar-consumer').style.width = `${total ? (consumer / total) * 100 : 50}%`;
    $('#bar-business').style.width = `${total ? (business / total) * 100 : 50}%`;
    const picked = ROWS.filter((r) => have[r.key] > 0);
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
