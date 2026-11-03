// Demo UI for the Everyspace prototype. No build step, no dependencies.
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (n) => `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 })}`;

async function api(path, body) {
  if (window.everyspaceApi) return window.everyspaceApi(path, body); // single-file build
  const res = await fetch(`/api/${path}`, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
  const data = await res.json();
  if (!res.ok) { const e = new Error(data.error); e.details = data.details; throw e; }
  return data;
}

const state = { catalog: null, users: [], user: 'u_sam', group: '', selected: null, booking: null };
const TERM_ORDER = ['hourly', 'daily', 'weekly', 'monthly', 'lease', 'infrastructure'];

// ---------- dates ----------
const addDays = (d, n) => { const t = new Date(`${d}T00:00:00Z`); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };
const addMonths = (d, n) => { const t = new Date(`${d}T00:00:00Z`); t.setUTCMonth(t.getUTCMonth() + n); return t.toISOString().slice(0, 10); };
function defaultRange(term, start) {
  switch (term) {
    case 'hourly': return [`${start}T18:00`, `${start}T22:00`];
    case 'daily': return [start, addDays(start, 1)];
    case 'weekly': return [start, addDays(start, 7)];
    case 'monthly': return [start, addMonths(start, 1)];
    case 'lease': return [start, addMonths(start, 12)];
    case 'infrastructure': return [start, addMonths(start, 240)];
  }
}
const toApi = (term, v) => (term === 'hourly' ? `${v}:00Z` : v);

// ---------- boot ----------
async function boot() {
  [state.catalog, state.users] = await Promise.all([api('catalog'), api('users')]);
  $('#user').innerHTML = state.users.map((u) => `<option value="${u.id}">${esc(u.name)}</option>`).join('');
  $('#user').value = state.user;
  $('#user').onchange = () => { state.user = $('#user').value; refreshAll(); };
  $('#reset').onclick = async () => { await api('reset', {}); state.selected = null; refreshAll(); };

  for (const b of $('#tabs').children) b.onclick = () => showTab(b.dataset.tab);

  $('#groups').innerHTML = [['', 'Everything'], ...Object.entries(state.catalog.groups).filter(([k]) => k !== 'container')]
    .map(([k, v]) => `<button type="button" data-group="${k}" class="${k === '' ? 'on' : ''}">${esc(v)}</button>`).join('');
  $('#groups').onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    state.group = b.dataset.group;
    for (const x of $('#groups').children) x.classList.toggle('on', x === b);
    runSearch();
  };
  $('#f-term').innerHTML += TERM_ORDER.map((t) => `<option value="${t}">${state.catalog.terms[t].label}</option>`).join('');
  $('#f-start').value = '2026-11-21';
  $('#f-end').value = '2026-11-22';
  $('#filters').oninput = debounce(runSearch, 200);
  $('#filters').onsubmit = (e) => e.preventDefault();

  setupHostForms();
  renderCatalog();
  refreshAll();
  if (window.EVERYSPACE_START_TAB) showTab(window.EVERYSPACE_START_TAB);
}

function showTab(tab) {
  for (const b of $('#tabs').children) b.classList.toggle('on', b.dataset.tab === tab);
  for (const s of document.querySelectorAll('.view')) s.hidden = s.id !== tab;
  if (tab === 'bookings') renderBookings();
  if (tab === 'host') renderHost();
  if (tab === 'plan' && !$('#plan-body').innerHTML.trim()) api('spec').then((r) => { $('#plan-body').innerHTML = r.html; });
  window.scrollTo(0, 0);
}

function refreshAll() { runSearch(); renderHost(); renderBookings(); }

// ---------- find ----------
async function runSearch() {
  const f = new FormData($('#filters'));
  const params = new URLSearchParams();
  for (const [k, v] of f) if (v) params.set(k, v);
  if (state.group) params.set('group', state.group);
  const { spaces, packages } = await api(`search?${params}`);
  const cards = [
    ...packages.map((p) => `<button class="result ${state.selected?.id === p.id ? 'on' : ''}" data-pkg="${p.id}">
        <span class="cat">Package · ${esc(p.property.title)}</span><strong>${esc(p.name)}</strong>
        <span class="price">${p.pricing.type === 'fixed' ? `${money(p.pricing.rates.monthly ?? Object.values(p.pricing.rates)[0])}/mo` : `${p.pricing.percent}% off together`}</span></button>`),
    ...spaces.map((s) => {
      const qtyNote = params.get('start') && params.get('end') ? (s.unitsFree ? `${s.unitsFree} of ${s.quantity ?? 1} free` : 'Booked for those dates') : `${s.quantity ?? 1} available`;
      return `<button class="result ${state.selected?.id === s.id ? 'on' : ''}" data-space="${s.id}">
        <span class="cat">${esc(s.categoryLabel)} · ${esc(s.property.title)}</span>
        <strong>${esc(s.title)}</strong>
        ${s.fromPrice ? `<span class="price">from ${money(s.fromPrice.amount)}/${s.fromPrice.unit}</span>` : ''}
        <span>${s.policy === 'addon' ? '<span class="tag warn">Add-on only</span>' : ''}${s.policy === 'both' ? '<span class="tag">Add-on discount</span>' : ''}<span class="tag ${s.unitsFree ? 'ok' : 'warn'}">${qtyNote}</span></span>
      </button>`;
    }),
  ];
  $('#results').innerHTML = cards.join('') || '<p class="muted">Nothing matches. Try another term or category.</p>';
  $('#results').onclick = (e) => {
    const b = e.target.closest('.result'); if (!b) return;
    if (b.dataset.space) selectSpace(b.dataset.space); else selectPackage(b.dataset.pkg, packages.find((p) => p.id === b.dataset.pkg));
    for (const x of $('#results').children) x.classList.toggle('on', x === b);
  };
}

async function selectSpace(id) {
  const space = await api(`spaces/${id}`);
  const terms = TERM_ORDER.filter((t) => space.rates?.[t] != null || space.addonRates?.[t] != null);
  const filterTerm = $('#f-term').value;
  const term = terms.includes(filterTerm) ? filterTerm : terms[0];
  state.selected = { kind: 'space', id, space, terms };
  state.booking = { term, qty: 1, addons: {}, range: initialRange(term) };
  renderDetail();
}

function selectPackage(id, pkg) {
  const terms = pkg.pricing.type === 'fixed' ? TERM_ORDER.filter((t) => pkg.pricing.rates[t] != null) : ['monthly', 'lease'];
  state.selected = { kind: 'package', id, pkg, terms };
  state.booking = { term: terms[0], range: initialRange(terms[0]) };
  renderDetail();
}

function initialRange(term) {
  const start = $('#f-start').value || '2026-12-01';
  const end = $('#f-end').value;
  if ((term === 'daily' || term === 'weekly') && end > start) return [start, end];
  return defaultRange(term, start);
}

function renderDetail() {
  const sel = state.selected, bk = state.booking;
  const el = $('#detail');
  el.classList.remove('empty');
  const cat = state.catalog;
  let head;
  if (sel.kind === 'space') {
    const s = sel.space;
    head = `<div class="muted">${esc(s.categoryInfo.label)} · ${esc(s.property.title)}, ${esc(s.property.city)}</div>
      <h2>${esc(s.title)}</h2>
      ${s.description ? `<div>${esc(s.description)}</div>` : ''}
      <div class="rates">${TERM_ORDER.filter((t) => s.rates?.[t] != null).map((t) => `<span class="tag">${money(s.rates[t])}/${cat.terms[t].unit} · ${cat.terms[t].label}</span>`).join('')}
        ${Object.entries(s.addonRates || {}).map(([t, v]) => `<span class="tag ok">${money(v)}/${cat.terms[t].unit} as add-on</span>`).join('')}</div>
      ${(s.eventRates || []).map((e) => `<div class="muted">Event pricing: ${esc(e.name)} ${e.start} → ${e.end}${e.daily ? ` · ${money(e.daily)}/day` : ''}${e.hourly ? ` · ${money(e.hourly)}/hr` : ''}</div>`).join('')}
      ${s.addonNote ? `<div class="tag warn">${esc(s.addonNote)}</div>` : ''}`;
  } else {
    const p = sel.pkg;
    head = `<div class="muted">Package · ${esc(p.property.title)}</div><h2>${esc(p.name)}</h2>
      <div class="muted">${p.pricing.type === 'fixed' ? Object.entries(p.pricing.rates).map(([t, v]) => `${money(v)}/${cat.terms[t].unit} (${cat.terms[t].label})`).join(' · ') : `${p.pricing.percent}% off the separate prices`}</div>`;
  }

  const hourly = bk.term === 'hourly';
  const s = sel.space;
  const qtyInput = sel.kind === 'space' && (s.quantity ?? 1) > 1
    ? `<label>How many <input id="d-qty" type="number" min="1" max="${s.quantity}" value="${bk.qty}"></label>` : '';
  const addons = sel.kind === 'space' && s.addons?.length ? `<div><strong>Add to this rental</strong>
      ${s.addons.map((a) => `<div class="addon"><div>${esc(a.title)}<div class="muted">${esc(a.addonNote)}</div></div>
        <input type="number" min="0" max="${a.addon.maxPerAnchor ?? a.quantity}" value="${bk.addons[a.id] ?? 0}" data-addon="${a.id}"></div>`).join('')}</div>` : '';
  const pkgs = sel.kind === 'space' && s.packages?.length
    ? `<div class="muted">Also in: ${s.packages.map((p) => `<a href="#" data-usepkg="${p.id}">${esc(p.name)}</a>`).join(', ')}</div>` : '';

  el.innerHTML = `${head}
    <div class="row">
      <label>Term <select id="d-term">${sel.terms.map((t) => `<option value="${t}" ${t === bk.term ? 'selected' : ''}>${cat.terms[t].label}</option>`).join('')}</select></label>
      ${qtyInput}
    </div>
    <div class="row">
      <label>Start <input id="d-start" type="${hourly ? 'datetime-local' : 'date'}" value="${bk.range[0]}"></label>
      <label>End <input id="d-end" type="${hourly ? 'datetime-local' : 'date'}" value="${bk.range[1]}"></label>
    </div>
    ${addons}${pkgs}
    <div class="quote" id="quote"></div>
    <label>Note to host <input id="d-note" placeholder="optional"></label>
    <button id="d-book">Book</button>
    <div id="d-msg"></div>`;

  $('#d-term').onchange = () => { bk.term = $('#d-term').value; bk.range = defaultRange(bk.term, bk.range[0].slice(0, 10)); renderDetail(); };
  $('#d-start').onchange = () => { bk.range[0] = $('#d-start').value; updateQuote(); };
  $('#d-end').onchange = () => { bk.range[1] = $('#d-end').value; updateQuote(); };
  if ($('#d-qty')) $('#d-qty').oninput = () => { bk.qty = Math.max(1, +$('#d-qty').value || 1); updateQuote(); };
  for (const inp of el.querySelectorAll('[data-addon]')) inp.oninput = () => { bk.addons[inp.dataset.addon] = Math.max(0, +inp.value || 0); updateQuote(); };
  for (const a of el.querySelectorAll('[data-usepkg]')) a.onclick = async (e) => {
    e.preventDefault();
    const { packages } = await api('search');
    selectPackage(a.dataset.usepkg, packages.find((p) => p.id === a.dataset.usepkg));
  };
  $('#d-book').onclick = book;
  updateQuote();
}

function cartFromState() {
  const sel = state.selected, bk = state.booking;
  const cart = { renterId: state.user, term: bk.term, start: toApi(bk.term, bk.range[0]), end: toApi(bk.term, bk.range[1]) };
  if (sel.kind === 'package') cart.packageId = sel.id;
  else cart.items = [{ spaceId: sel.id, qty: bk.qty }, ...Object.entries(bk.addons).filter(([, q]) => q > 0).map(([spaceId, qty]) => ({ spaceId, qty }))];
  return cart;
}

const modeLabel = { instant: 'Instant book', request: 'Request to book — host approves', proposal: 'Proposal — site assessment, then contract' };

async function updateQuote() {
  const box = $('#quote');
  try {
    const q = await api('quote', cartFromState());
    const cat = state.catalog;
    box.innerHTML = `<table>
      ${q.lines.map((l) => `<tr><td>${l.qty > 1 ? `${l.qty} × ` : ''}${esc(l.title)}${l.asAddon ? ' <span class="tag ok">add-on price</span>' : ''}
        <div class="muted">${esc(l.detail)} @ ${money(l.unitRate)}/${cat.terms[l.term].unit}${l.events.length ? ` · ${esc(l.events.join(', '))} pricing` : ''}</div></td><td>${money(l.amount)}</td></tr>`).join('')}
      ${q.packageDiscount ? `<tr><td>Package discount</td><td>−${money(q.packageDiscount)}</td></tr>` : ''}
      <tr><td>Service fee</td><td>${money(q.serviceFee)}</td></tr>
      <tr class="total"><td>Total</td><td>${money(q.total)}</td></tr>
      <tr><td class="muted">Due now${q.schedule.recurring ? `, then ${money(q.schedule.recurring)}/${q.schedule.every}` : ''}</td><td>${money(q.schedule.dueNow)}</td></tr>
      ${q.deposit ? `<tr><td class="muted">Deposit</td><td class="muted">${money(q.deposit)}</td></tr>` : ''}
    </table>
    <div class="muted">${esc(q.schedule.note)}</div>
    <div><span class="tag">${modeLabel[q.mode]}</span></div>
    ${q.availability.ok ? '<div class="okmsg">Available ✓</div>' : `<div class="err">Not available<ul>${q.availability.conflicts.map((c) => `<li>${esc(c.reason)}</li>`).join('')}</ul></div>`}`;
    $('#d-book').disabled = !q.availability.ok;
    $('#d-book').textContent = q.mode === 'instant' ? 'Book now' : q.mode === 'request' ? 'Request to book' : 'Send proposal';
  } catch (e) {
    box.innerHTML = errorHtml(e);
    $('#d-book').disabled = true;
  }
}

async function book() {
  const cart = cartFromState();
  cart.note = $('#d-note').value;
  try {
    const b = await api('bookings', cart);
    $('#d-msg').innerHTML = `<div class="okmsg">Booking ${b.id} is <strong>${b.status.replace('_', ' ')}</strong>. See the Bookings tab.</div>`;
    runSearch();
    updateQuote();
  } catch (e) {
    $('#d-msg').innerHTML = errorHtml(e);
  }
}

const errorHtml = (e) => `<div class="err">${esc(e.message)}${e.details?.length ? `<ul>${e.details.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>` : ''}</div>`;

// ---------- host ----------
let hostProps = [];
async function renderHost() {
  hostProps = await api(`properties?hostId=${state.user}`);
  const cat = state.catalog;
  $('#host-props').innerHTML = hostProps.length ? hostProps.map((p) => `<div class="card prop">
      <h3>${esc(p.title)} <span class="muted">· ${esc(p.city)} · ${esc(p.type.replace('_', ' '))}</span></h3>
      <ul class="tree">${orderTree(p.spaces).map(({ s, depth }) => `<li class="depth-${Math.min(depth, 2)}">
        <strong>${esc(s.title)}</strong> <span class="muted">${esc(cat.categories[s.category].label)}${(s.quantity ?? 1) > 1 ? ` · ×${s.quantity}` : ''}</span>
        ${s.rentable === false ? '<span class="tag">container, not rentable</span>' : ''}
        ${s.addonNote ? `<span class="tag warn">${esc(s.addonNote)}</span>` : ''}
        <div class="muted">${TERM_ORDER.filter((t) => s.rates?.[t] != null).map((t) => `${money(s.rates[t])}/${cat.terms[t].unit}${t === 'lease' ? ' on lease' : ''}`).join(' · ')}</div></li>`).join('')}</ul>
      ${p.packages.length ? `<div class="muted" style="margin-top:8px">Packages: ${p.packages.map((k) => esc(k.name)).join(' · ')}</div>` : ''}
    </div>`).join('') : '<p class="muted">You have no properties yet. Add one below — or switch to Maya or Jordan to see example hosts.</p>';

  const propOpts = hostProps.map((p) => `<option value="${p.id}">${esc(p.title)}</option>`).join('');
  for (const sel of document.querySelectorAll('#new-space [name=propertyId], #new-package [name=propertyId]')) {
    const prev = sel.value; sel.innerHTML = propOpts; if (hostProps.some((p) => p.id === prev)) sel.value = prev;
  }
  syncSpaceForm();
  syncPackageForm();
}

function orderTree(spaces) {
  const out = [];
  const walk = (parentId, depth) => spaces.filter((s) => (s.parentId ?? null) === parentId).forEach((s) => { out.push({ s, depth }); walk(s.id, depth + 1); });
  walk(null, 0);
  return out;
}

function setupHostForms() {
  const cat = state.catalog;
  const f = $('#new-space');
  f.category.innerHTML = Object.entries(cat.groups).map(([g, label]) => `<optgroup label="${esc(label)}">${Object.entries(cat.categories)
    .filter(([, c]) => c.group === g).map(([k, c]) => `<option value="${k}">${esc(c.label)}</option>`).join('')}</optgroup>`).join('');
  f.anchorCategory.innerHTML = Object.entries(cat.categories).filter(([, c]) => c.group === 'living')
    .map(([k, c]) => `<option value="${k}">${esc(c.label)}</option>`).join('');
  f.onchange = (e) => { if (['category', 'propertyId', 'policy'].includes(e.target.name)) syncSpaceForm(); };
  f.onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(f));
    const rates = {};
    for (const inp of f.querySelectorAll('[data-rate]')) if (inp.value) rates[inp.dataset.rate] = +inp.value;
    const body = { propertyId: d.propertyId, category: d.category, title: d.title, description: d.description,
      quantity: +d.quantity, parentId: d.parentId || undefined, rates, policy: d.policy };
    if (d.policy !== 'standalone') {
      body.addon = { anchorCategories: [d.anchorCategory], maxPerAnchor: +d.maxPerAnchor || undefined };
      if (d.addonMonthly) body.addonRates = { monthly: +d.addonMonthly };
    }
    await submit(f, () => api('spaces', body), 'Published.');
  };

  const pf = $('#new-property');
  pf.onsubmit = async (e) => {
    e.preventDefault();
    await submit(pf, () => api('properties', { ...Object.fromEntries(new FormData(pf)), hostId: state.user }), 'Property added.');
  };

  const kf = $('#new-package');
  kf.onchange = (e) => { if (e.target.name === 'propertyId') syncPackageForm(); };
  kf.onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(kf));
    const items = [...kf.querySelectorAll('[data-pkgspace]')].filter((c) => c.checked)
      .map((c) => ({ spaceId: c.dataset.pkgspace, qty: +kf.querySelector(`[data-pkgqty="${c.dataset.pkgspace}"]`).value || 1 }));
    const pricing = d.ptype === 'fixed' ? { type: 'fixed', rates: { monthly: +d.pvalue } } : { type: 'percent', percent: +d.pvalue };
    await submit(kf, () => api('packages', { propertyId: d.propertyId, name: d.name, items, pricing }), 'Package created.');
  };
}

async function submit(form, fn, okText) {
  const msg = form.querySelector('[data-msg]');
  try { await fn(); msg.innerHTML = `<span class="okmsg">${okText}</span>`; form.reset(); await renderHost(); runSearch(); }
  catch (e) { msg.innerHTML = errorHtml(e); }
}

function syncSpaceForm() {
  const f = $('#new-space');
  const c = state.catalog.categories[f.category.value];
  if (!c) return;
  $('#cat-hint').textContent = c.group === 'container'
    ? 'A container just groups other spaces (a building, a garage). It is never rented itself.'
    : `Default booking: ${c.mode}. Before going live you'll confirm: ${c.checklist.join('; ')}.`;
  $('#rate-inputs').innerHTML = c.terms.map((t) => `<label>${state.catalog.terms[t].label} ($/${state.catalog.terms[t].unit})
    <input type="number" min="0" step="0.01" data-rate="${t}"></label>`).join('') || '<span class="muted">No prices — not rentable.</span>';
  const prop = hostProps.find((p) => p.id === f.propertyId.value);
  f.parentId.innerHTML = '<option value="">— nothing —</option>' + (prop?.spaces ?? []).map((s) => `<option value="${s.id}">${esc(s.title)}</option>`).join('');
  $('#addon-opts').hidden = f.policy.value === 'standalone';
}

function syncPackageForm() {
  const kf = $('#new-package');
  const prop = hostProps.find((p) => p.id === kf.propertyId.value);
  $('#pkg-items').innerHTML = (prop?.spaces ?? []).filter((s) => s.rentable !== false).map((s) => `<label>
    <input type="checkbox" data-pkgspace="${s.id}"> <span style="flex:1">${esc(s.title)}</span>
    <input type="number" min="1" max="${s.quantity ?? 1}" value="1" data-pkgqty="${s.id}"></label>`).join('') || '<span class="muted">Add spaces first.</span>';
}

// ---------- bookings ----------
const NEXT = { proposed: 'Start site assessment', site_assessment: 'Send contract', contract: 'Sign & confirm' };
async function renderBookings() {
  const list = await api(`bookings?userId=${state.user}`);
  const cat = state.catalog;
  $('#booking-list').innerHTML = list.length ? list.map((b) => {
    const acts = [];
    if (b.role === 'host' && b.status === 'pending') acts.push(['approve', 'Approve'], ['decline', 'Decline']);
    if (b.role === 'host' && NEXT[b.status]) acts.push(['advance', NEXT[b.status]], ['decline', 'Decline']);
    if (['pending', 'proposed', 'site_assessment', 'contract', 'confirmed', 'active'].includes(b.status)) acts.push(['cancel', 'Cancel']);
    const range = b.term === 'hourly' ? `${b.start.slice(0, 16).replace('T', ' ')} → ${b.end.slice(11, 16)}` : `${b.start} → ${b.end}`;
    return `<div class="card booking">
      <div class="head"><strong>${esc(b.packageName ?? b.itemsLabel)}</strong><span class="status tag ${b.status === 'confirmed' ? 'ok' : b.status === 'declined' || b.status === 'cancelled' ? 'warn' : ''}">${b.status.replace('_', ' ')}</span></div>
      <div class="muted">${b.role === 'host' ? `Renter: ${esc(b.renterName)}` : `Host: ${esc(b.hostName)}`} · ${cat.terms[b.term].label} · ${range}
        ${b.quote ? ` · ${money(b.quote.total)} total${b.quote.schedule?.recurring ? ` (${money(b.quote.schedule.recurring)}/${b.quote.schedule.every})` : ''}` : ''}</div>
      ${b.note ? `<div class="muted">“${esc(b.note)}”</div>` : ''}
      <div class="actions">${acts.map(([a, l]) => `<button class="${a === 'cancel' || a === 'decline' ? 'ghost' : ''}" data-act="${a}" data-id="${b.id}">${l}</button>`).join('')}</div>
    </div>`;
  }).join('') : '<p class="muted">No bookings yet for this user.</p>';
  $('#booking-list').onclick = async (e) => {
    const btn = e.target.closest('[data-act]'); if (!btn) return;
    try { await api(`bookings/${btn.dataset.id}/${btn.dataset.act}`, { actorId: state.user }); }
    catch (err) { alert(err.message); }
    renderBookings(); runSearch();
  };
}

// ---------- catalog ----------
function renderCatalog() {
  const cat = state.catalog;
  $('#catalog-list').innerHTML = Object.entries(cat.groups).filter(([g]) => g !== 'container').map(([g, label]) => `<div class="catalog-group">
    <h2>${esc(label)}</h2><div class="catalog-grid">${Object.values(cat.categories).filter((c) => c.group === g).map((c) => `<div class="card">
      <strong>${esc(c.label)}</strong>
      <div>${c.terms.map((t) => `<span class="tag">${cat.terms[t].label}</span>`).join('')}</div>
      <div class="muted">${{ instant: 'Instant book', request: 'Request to book', proposal: 'Proposal & contract' }[c.mode]} · priced per ${c.measure}</div>
      <ul>${c.checklist.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`).join('')}</div></div>`).join('');
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

boot();
