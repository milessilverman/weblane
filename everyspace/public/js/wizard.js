// Step-by-step "list a space" flow for hosts.
import { $, $$, api, esc, state, cat, term, icon, money, topbar, bindBack, bindSteppers, stepper, errorBox, go, toast } from './core.js';
import { art } from './art.js';

const DEFAULT_TITLE = { parking_spot: 'Driveway parking spot', backyard: 'Backyard for gatherings', garage_storage: 'Garage storage space',
  attic_storage: 'Attic storage', garden_plot: 'Garden plot', rooftop_solar: 'Roof space for solar', entire_home: 'Whole home', private_room: 'Private room' };
const ANCHOR_CATS = ['apartment_unit', 'adu', 'entire_home', 'private_room'];
const STEPS = ['What', 'Where', 'Details', 'Prices', 'Who', 'Checklist', 'Review'];

let draft = null;
const fresh = (propertyId) => ({ step: 0, category: '', propertyId: propertyId ?? '', newProp: { title: '', city: 'Riverside', type: 'single_family' },
  title: '', description: '', quantity: 1, sqft: '', parentId: '', amenities: '', rates: {}, on: {},
  event: { name: '', start: '', end: '', daily: '', hourly: '' }, policy: 'standalone', anchorCats: [], anchorIds: [], maxPerAnchor: 1, addonMonthly: '',
  checklist: [], access: '' });

export async function renderWizard(view, _params, query) {
  if (!draft || query.get('property') || query.get('fresh')) {
    draft = fresh(query.get('property'));
    draft.tab = query.get('audience') === 'business' ? 'business' : 'consumer';
    const pre = query.get('category');
    if (pre && state.catalog.categories[pre]) { draft.category = pre; draft.tab = cat(pre).audience; }
  }
  const props = await api(`properties?hostId=${state.user}`);
  if (!draft.propertyId && props.length) draft.propertyId = props[0].id;
  draw(view, props);
}

function draw(view, props) {
  const d = draft;
  const c = d.category ? cat(d.category) : null;
  const isContainer = c?.group === 'container';
  // Business sites skip "who can rent it": they're always leased to companies on their own.
  const steps = isContainer ? [0, 1, 2, 6] : c?.audience === 'business' ? [0, 1, 2, 3, 5, 6] : [0, 1, 2, 3, 4, 5, 6];
  const pos = steps.indexOf(d.step);
  const prop = props.find((p) => p.id === d.propertyId);
  let body = '';

  if (d.step === 0) {
    const tab = d.tab ?? 'consumer';
    const cats = state.catalog.categories;
    const groups = Object.entries(state.catalog.groups).filter(([g]) => g !== 'container' && Object.values(cats).some((x) => x.group === g && x.audience === tab));
    const typical = (x) => (x.typical ? (([t, v]) => `Typical ${money(v)}/${term(t).unit}`)(Object.entries(x.typical).at(-1)) : '');
    body = `<h1 class="page-title">What do you want to rent out?</h1>
      <div class="segmented wide" id="aud"><button type="button" data-aud="consumer" class="${tab === 'consumer' ? 'on' : ''}">🙋 Rent to people</button>
        <button type="button" data-aud="business" class="${tab === 'business' ? 'on' : ''}">🏢 Lease to companies</button></div>
      <p class="muted">${tab === 'consumer'
        ? 'Neighbors and visitors book by the hour, night, month or lease. Pick the closest match; you can list more later.'
        : 'Solar installers, charging networks, telecoms and fleets sign multi-year agreements and handle installation, insurance and removal. These listings only appear on Everyspace for Business.'}</p>
      ${groups.map(([g, label]) => `<h2 class="section-title">${state.catalog.groupIcons[g]} ${esc(label)}</h2>
        <div class="tiles">${Object.entries(cats).filter(([, x]) => x.group === g).map(([k, x]) => `<button type="button" class="tile ${d.category === k ? 'on' : ''}" data-cat="${k}">
          <span class="tile-icon">${x.icon}</span><strong>${esc(x.label)}</strong><span class="muted small">${typical(x)}</span></button>`).join('')}</div>`).join('')}
      ${tab === 'consumer' ? `<h2 class="section-title">🏗️ Organize</h2><div class="tiles"><button type="button" class="tile ${d.category === 'building' ? 'on' : ''}" data-cat="building"><span class="tile-icon">🏗️</span>
        <strong>Building or garage (group)</strong><span class="muted small">Holds other spaces, like an apartment building or a garage with bays. Not rented itself.</span></button></div>` : ''}`;
  } else if (d.step === 1) {
    body = `<h1 class="page-title">Where is it?</h1>
      <div class="option-list">${props.map((p) => `<button type="button" class="option ${d.propertyId === p.id ? 'on' : ''}" data-prop="${p.id}"><strong>${esc(p.title)}</strong>
        <span class="muted small">${esc(p.city)} · ${p.spaces.length} space${p.spaces.length === 1 ? '' : 's'}</span></button>`).join('')}
        <button type="button" class="option ${d.propertyId === 'new' ? 'on' : ''}" data-prop="new"><strong>${icon.plus} A new property</strong></button></div>
      ${d.propertyId === 'new' ? `<div class="form card pad"><label>Address or name<input id="np-title" value="${esc(d.newProp.title)}" placeholder="123 Main St"></label>
        <label>City<input id="np-city" value="${esc(d.newProp.city)}"></label>
        <label>Type<select id="np-type">${[['single_family', 'House'], ['multi_unit', 'Apartment building'], ['condo', 'Condo / townhouse'], ['land', 'Land / lot']].map(([v, l]) => `<option value="${v}" ${d.newProp.type === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label></div>` : ''}`;
  } else if (d.step === 2) {
    const parents = prop?.spaces ?? [];
    const measure = c.measure;
    if (!d.title) d.title = DEFAULT_TITLE[d.category] ?? c.label;
    body = `<h1 class="page-title">Describe your ${esc(c.label.toLowerCase())}</h1><div class="form">
      <label>Title<input id="w-title" value="${esc(d.title)}" maxlength="80"></label>
      <label>Description<textarea id="w-desc" rows="3" placeholder="What's it like? What's it good for?">${esc(d.description)}</textarea></label>
      ${isContainer ? '' : `<div class="field row-between"><div><strong>How many identical ${measure === 'spot' ? 'spots' : measure === 'sqft' ? 'units' : 'ones'}?</strong>
        <div class="muted small">E.g. 3 driveway spots, 4 garden beds. Each can be booked separately.</div></div>${stepper('quantity', d.quantity, { min: 1, max: 50 })}</div>`}
      ${measure === 'sqft' ? `<label>Size (sq ft each)<input id="w-sqft" type="number" min="1" value="${esc(d.sqft)}"></label>` : ''}
      ${parents.length && d.propertyId !== 'new' ? `<label>Inside another space? <span class="muted small">Booking the outer one will block this one, and vice versa.</span>
        <select id="w-parent"><option value="">No, it's separate</option>${parents.map((s) => `<option value="${s.id}" ${d.parentId === s.id ? 'selected' : ''}>${esc(s.title)}</option>`).join('')}</select></label>` : ''}
      ${isContainer ? '' : `<label>Highlights <span class="muted small">comma separated</span><input id="w-amen" value="${esc(d.amenities)}" placeholder="Covered, Lockable, Fits SUVs"></label>`}
    </div>`;
  } else if (d.step === 3) {
    const sug = c.typical ?? {};
    // What similar listings nearby charge (fetched once per category).
    if (d.market?.cat !== d.category) {
      d.market = { cat: d.category, data: {} };
      api(`market?category=${d.category}`).then((m) => { d.market = { cat: d.category, data: m }; if (d.step === 3) draw(view, props); });
    }
    const near = (t) => { const m = d.market.data[t]; return m?.count ? ` · Nearby ${money(m.min)}–${money(m.max)}` : ''; };
    for (const t of c.terms) { if (d.rates[t] == null) d.rates[t] = sug[t] ?? ''; if (d.on[t] == null) d.on[t] = true; }
    const eventy = ['parking', 'outdoor'].includes(c.group) && c.terms.some((t) => t === 'daily' || t === 'hourly');
    body = `<h1 class="page-title">Set your prices</h1><p class="muted">Starting points are typical for your area. Turn off any length you don't want.</p>
      <div class="price-list">${c.terms.map((t) => `<div class="price-item ${d.on[t] ? '' : 'off'}">
        <label class="switch"><input type="checkbox" data-on="${t}" ${d.on[t] ? 'checked' : ''}><span></span></label>
        <div><strong>${term(t).label}</strong><div class="muted small">${sug[t] ? `Typical: ${money(sug[t])}/${term(t).unit}` : ''}${near(t)}</div>
          ${d.on[t] && Number(d.rates[t]) > 0 ? `<div class="small payout">You get ${money(d.rates[t] * 0.97)} · renter pays ${money(d.rates[t] * 1.1)}</div>` : ''}</div>
        <label class="money-input">$<input type="number" min="0" step="1" data-rate="${t}" value="${esc(d.rates[t])}" ${d.on[t] ? '' : 'disabled'}><span>/${term(t).unit}</span></label></div>`).join('')}</div>
      ${eventy ? `<div class="card pad"><strong>🎟️ Event pricing (optional)</strong><p class="muted small">Charge more on fair, game or parade days.</p>
        <div class="form"><label>Event name<input id="ev-name" value="${esc(d.event.name)}" placeholder="County Fair"></label>
        <div class="two"><label>From<input type="date" id="ev-start" value="${d.event.start}"></label><label>To<input type="date" id="ev-end" value="${d.event.end}"></label></div>
        <div class="two">${c.terms.includes('daily') ? `<label>Event day price<input type="number" id="ev-daily" value="${esc(d.event.daily)}"></label>` : ''}
        ${c.terms.includes('hourly') ? `<label>Event hourly price<input type="number" id="ev-hourly" value="${esc(d.event.hourly)}"></label>` : ''}</div></div></div>` : ''}`;
  } else if (d.step === 4) {
    const others = (prop?.spaces ?? []).filter((s) => s.rentable !== false && ANCHOR_CATS.includes(s.category));
    body = `<h1 class="page-title">Who can rent it?</h1>
      <div class="option-list">
        ${[['standalone', 'Anyone', 'People can book it on its own.'], ['addon', 'Only with another rental', 'E.g. parking only for your tenants or your ADU guest.'],
          ['both', 'Anyone, cheaper with a rental', 'E.g. a locker that costs less for tenants.']].map(([v, l, h]) => `<button type="button" class="option ${d.policy === v ? 'on' : ''}" data-policy="${v}"><strong>${l}</strong><span class="muted small">${h}</span></button>`).join('')}
      </div>
      ${d.policy !== 'standalone' ? `<div class="card pad form"><strong>Which rentals can include it?</strong>
        ${ANCHOR_CATS.map((k) => `<label class="check"><input type="checkbox" data-anchorcat="${k}" ${d.anchorCats.includes(k) ? 'checked' : ''}> Any ${esc(cat(k).label.toLowerCase())} at this property</label>`).join('')}
        ${others.map((s) => `<label class="check"><input type="checkbox" data-anchorid="${s.id}" ${d.anchorIds.includes(s.id) ? 'checked' : ''}> Only ${esc(s.title)}</label>`).join('')}
        <div class="field row-between"><span>Max per rental</span>${stepper('maxPerAnchor', d.maxPerAnchor, { min: 1, max: 10 })}</div>
        ${d.policy === 'both' && c.terms.includes('monthly') ? `<label>Monthly price for renters here<input type="number" id="w-addon" value="${esc(d.addonMonthly)}" placeholder="Lower than ${money(d.rates.monthly || 0)}"></label>` : ''}
      </div>` : ''}`;
  } else if (d.step === 5) {
    body = `<h1 class="page-title">Before you go live</h1><p class="muted">Renters see that you've confirmed these. Each is required.</p>
      <div class="checklist">${c.checklist.map((item, i) => `<label class="check big"><input type="checkbox" data-check="${i}" ${d.checklist.includes(item) ? 'checked' : ''}><span>${esc(item)}</span></label>`).join('')}</div>
      <label class="form">How renters get in <span class="muted small">Shown only after a booking is confirmed</span>
        <textarea id="w-access" rows="3" placeholder="Gate code, lockbox, where to park…">${esc(d.access)}</textarea></label>`;
  } else if (d.step === 6) {
    const enabled = c.terms.filter((t) => d.on[t] && d.rates[t]);
    body = `<h1 class="page-title">Review and publish</h1>
      <div class="card space-card preview">${art({ id: 'preview', category: d.category, quantity: d.quantity })}<div class="card-body">
        <div class="muted small">${c.icon} ${esc(c.label)} · ${esc(prop?.title ?? d.newProp.title)}</div><strong class="title">${esc(d.title)}</strong>
        ${isContainer ? '<div class="muted small">Groups other spaces. Not rented itself.</div>' : `<div class="small">${enabled.map((t) => `${money(d.rates[t])}/${term(t).unit}`).join(' · ')}</div>
        ${d.quantity > 1 ? `<div class="small">${d.quantity} available</div>` : ''}${d.policy !== 'standalone' ? `<span class="badge warn">${d.policy === 'addon' ? 'Add-on only' : 'Tenant discount'}</span>` : ''}`}</div></div>
      <div id="pub-msg"></div>`;
  }

  const canNext = validate(d, c);
  view.innerHTML = `${topbar('New listing', { right: `<span class="muted small">${pos + 1}/${steps.length}</span>` })}
    <div class="progress"><i style="width:${((pos + 1) / steps.length) * 100}%"></i></div>
    <div class="page narrow wizard">${body}</div>
    <div class="reserve-bar"><button class="btn ghost" id="prev" ${pos === 0 ? 'disabled' : ''}>Back</button>
      <button class="btn" id="next" ${canNext ? '' : 'disabled'}>${d.step === 6 ? 'Publish listing' : 'Next'}</button></div>`;
  bindBack(view);

  const redraw = () => draw(view, props);
  const sync = () => { const n = $('#next'); if (n) n.disabled = !validate(d, c); };
  for (const b of $$('[data-cat]', view)) b.onclick = () => { if (d.category !== b.dataset.cat) { Object.assign(d, { category: b.dataset.cat, title: '', rates: {}, on: {}, checklist: [] }); } redraw(); };
  for (const b of $$('[data-aud]', view)) b.onclick = () => { d.tab = b.dataset.aud; redraw(); };
  for (const b of $$('[data-prop]', view)) b.onclick = () => { d.propertyId = b.dataset.prop; d.parentId = ''; redraw(); };
  for (const b of $$('[data-policy]', view)) b.onclick = () => { d.policy = b.dataset.policy; redraw(); };
  const bindInput = (sel, fn) => { const el = $(sel, view); if (el) el.oninput = () => { fn(el.value); sync(); }; };
  bindInput('#np-title', (v) => { d.newProp.title = v; });
  bindInput('#np-city', (v) => { d.newProp.city = v; });
  bindInput('#np-type', (v) => { d.newProp.type = v; });
  bindInput('#w-title', (v) => { d.title = v; });
  bindInput('#w-desc', (v) => { d.description = v; });
  bindInput('#w-sqft', (v) => { d.sqft = v; });
  bindInput('#w-parent', (v) => { d.parentId = v; });
  bindInput('#w-amen', (v) => { d.amenities = v; });
  bindInput('#w-addon', (v) => { d.addonMonthly = v; });
  bindInput('#w-access', (v) => { d.access = v; });
  for (const k of ['name', 'start', 'end', 'daily', 'hourly']) bindInput(`#ev-${k}`, (v) => { d.event[k] = v; });
  for (const el of $$('[data-rate]', view)) el.oninput = () => { d.rates[el.dataset.rate] = el.value; sync(); };
  for (const el of $$('[data-on]', view)) el.onchange = () => { d.on[el.dataset.on] = el.checked; redraw(); };
  for (const el of $$('[data-anchorcat]', view)) el.onchange = () => { toggle(d.anchorCats, el.dataset.anchorcat, el.checked); sync(); };
  for (const el of $$('[data-anchorid]', view)) el.onchange = () => { toggle(d.anchorIds, el.dataset.anchorid, el.checked); sync(); };
  for (const el of $$('[data-check]', view)) el.onchange = () => { toggle(d.checklist, c.checklist[+el.dataset.check], el.checked); sync(); };
  bindSteppers(view, (name, v) => { d[name] = v; });

  $('#prev').onclick = () => { d.step = steps[Math.max(0, pos - 1)]; redraw(); window.scrollTo(0, 0); };
  $('#next').onclick = async () => {
    if (d.step !== 6) { d.step = steps[pos + 1]; redraw(); window.scrollTo(0, 0); return; }
    $('#next').disabled = true;
    try {
      const space = await publish(d, c, isContainer);
      draft = null;
      toast('Your listing is live 🎉');
      go(isContainer ? '#/host/listings' : `#/space/${space.id}`);
    } catch (e) { $('#pub-msg').innerHTML = errorBox(e); $('#next').disabled = false; }
  };
}

function toggle(list, v, on) { const i = list.indexOf(v); if (on && i < 0) list.push(v); if (!on && i >= 0) list.splice(i, 1); }

function validate(d, c) {
  switch (d.step) {
    case 0: return !!d.category;
    case 1: return d.propertyId === 'new' ? !!(d.newProp.title.trim() && d.newProp.city.trim()) : !!d.propertyId;
    case 2: return !!d.title.trim();
    case 3: return c.terms.some((t) => d.on[t] && Number(d.rates[t]) > 0);
    case 4: return d.policy === 'standalone' || d.anchorCats.length + d.anchorIds.length > 0;
    case 5: return c.checklist.every((i) => d.checklist.includes(i));
    default: return true;
  }
}

async function publish(d, c, isContainer) {
  let propertyId = d.propertyId;
  if (propertyId === 'new') {
    const p = await api('properties', { hostId: state.user, ...d.newProp });
    propertyId = p.id;
    d.propertyId = p.id;
  }
  const rates = {};
  if (!isContainer) for (const t of c.terms) if (d.on[t] && Number(d.rates[t]) > 0) rates[t] = Number(d.rates[t]);
  const body = {
    propertyId, category: d.category, title: d.title.trim(), description: d.description.trim(), quantity: d.quantity,
    parentId: d.parentId || undefined, rates, rentable: !isContainer, checklist: d.checklist, access: d.access.trim() || undefined,
    amenities: d.amenities.split(',').map((x) => x.trim()).filter(Boolean), policy: isContainer ? 'standalone' : d.policy,
  };
  if (d.sqft) body.size = { sqft: Number(d.sqft) };
  if (d.event.name && d.event.start && (d.event.daily || d.event.hourly)) {
    body.eventRates = [{ name: d.event.name, start: d.event.start, end: d.event.end || d.event.start,
      ...(d.event.daily ? { daily: Number(d.event.daily) } : {}), ...(d.event.hourly ? { hourly: Number(d.event.hourly) } : {}) }];
  }
  if (d.policy !== 'standalone' && !isContainer) {
    body.addon = { anchorCategories: d.anchorCats, anchorIds: d.anchorIds, maxPerAnchor: d.maxPerAnchor };
    if (d.addonMonthly) body.addonRates = { monthly: Number(d.addonMonthly) };
  }
  return api('spaces', body);
}
