// Checkout: pick how long, when, how many, add-ons or a bundle; see the live price; confirm.
import { $, $$, api, esc, state, cat, term, icon, money, stars, today, addDays, addMonths, fmtDate, fmtRange, topbar, bindBack, bindSteppers, stepper, errorBox, statusPill, debounce, TERM_ORDER, TERM_SHORT } from './core.js';
import { art } from './art.js';
import { calendarPicker } from './calendar.js';

const BUTTON = { instant: 'Confirm and pay', request: 'Request to book', proposal: 'Send proposal' };

export async function renderBook(view, params) {
  const isPkg = params[0] === 'pkg';
  const id = isPkg ? params[1] : params[0];
  let space, pkg, terms;
  if (isPkg) {
    pkg = (await api('search')).packages.find((p) => p.id === id);
    if (!pkg) { view.innerHTML = `${topbar('Bundle')}<div class="page"><div class="empty">That bundle no longer exists.</div></div>`; bindBack(view); return; }
    const items = await Promise.all(pkg.items.map((i) => api(`spaces/${i.spaceId}`)));
    space = items[0];
    terms = pkg.pricing.type === 'fixed'
      ? TERM_ORDER.filter((t) => pkg.pricing.rates[t] != null)
      : TERM_ORDER.filter((t) => items.every((s) => s.rates?.[t] != null || s.addonRates?.[t] != null));
    pkg.spaces = items;
  } else {
    space = await api(`spaces/${id}`);
    terms = TERM_ORDER.filter((t) => space.rates?.[t] != null || space.addonRates?.[t] != null);
  }

  const f = state.filters;
  const startTerm = terms.includes(f.term) ? f.term : (f.start && terms.includes('daily') ? 'daily' : terms[0]);
  const tomorrow = addDays(today(), 1);
  const b = {
    term: startTerm, qty: 1, addons: {}, choice: isPkg ? id : 'solo', note: '',
    date: f.start && f.start > today() ? f.start : tomorrow,
    end: f.end && f.start && f.end > f.start ? f.end : '',
    hourStart: 18, hours: 3, months: 1, leaseMonths: 12, years: 20,
  };
  if (!b.end) b.end = addDays(b.date, b.term === 'weekly' ? 7 : 1);
  const minYears = Math.max(5, cat(space.category).minYears ?? 0);
  if (b.years < minYears) b.years = minYears;

  const title = isPkg ? pkg.name : space.title;
  view.innerHTML = `${topbar('Review and book')}
    <div class="page narrow">
      <div class="summary-card">${art(space, { className: 'art thumb-sm' })}<div>
        <div class="muted small">${isPkg ? '📦 Bundle' : `${cat(space.category).icon} ${esc(cat(space.category).label)}`} · ${esc(space.property.title)}</div>
        <strong>${esc(title)}</strong><div>${stars(space.rating)}</div></div></div>

      <section class="block"><h2>How long?</h2>
        <div class="segmented" id="terms">${terms.map((t) => `<button type="button" data-term="${t}" class="${t === b.term ? 'on' : ''}">${TERM_SHORT[t]}</button>`).join('')}</div>
        <div id="when"></div>
      </section>

      ${!isPkg && (space.quantity ?? 1) > 1 ? `<section class="block row-between"><div><h2>How many?</h2><div class="muted small">${space.quantity} identical ${esc(cat(space.category).measure === 'spot' ? 'spots' : 'units')} here</div></div>${stepper('qty', 1, { min: 1, max: space.quantity })}</section>` : ''}

      ${!isPkg && (space.addons.length || space.packages.length) ? `<section class="block"><h2>Add to your booking</h2>
        ${space.packages.length ? `<div class="option-list compact" id="choices">
          <button type="button" class="option on" data-choice="solo"><strong>Just ${esc(space.title)}</strong></button>
          ${space.packages.map((p) => `<button type="button" class="option" data-choice="${p.id}"><strong>📦 ${esc(p.name)}</strong>
            <span class="muted small">${p.pricing.type === 'fixed' ? Object.entries(p.pricing.rates).map(([t, v]) => `${money(v)}/${term(t).unit} ${t === 'lease' ? 'lease' : ''}`).join(' · ') : `${p.pricing.percent}% off together`}</span></button>`).join('')}
        </div>` : ''}
        <div id="addons">${space.addons.map((a) => `<div class="list-row">${art(a, { className: 'art mini' })}<div><strong>${esc(a.title)}</strong>
          <div class="muted small">${esc(a.addonNote)}</div></div>${stepper(`addon:${a.id}`, 0, { min: 0, max: Math.min(a.quantity ?? 1, a.addon?.maxPerAnchor ?? 9) })}</div>`).join('')}</div>
      </section>` : ''}
      ${isPkg ? `<section class="block"><h2>What's included</h2>${pkg.spaces.map((s, i) => `<div class="list-row">${art(s, { className: 'art mini' })}<div><strong>${pkg.items[i].qty > 1 ? `${pkg.items[i].qty} × ` : ''}${esc(s.title)}</strong>
        <div class="muted small">${cat(s.category).icon} ${esc(cat(s.category).label)}</div></div></div>`).join('')}</section>` : ''}

      <section class="block"><h2>Price details</h2><div id="quote" class="quote"><div class="skeleton line"></div></div></section>

      <section class="block"><h2>${cat(space.category).group === 'energy' ? 'About your project' : 'Message the host'}</h2>
        <textarea id="note" rows="3" placeholder="${cat(space.category).group === 'energy' ? 'System size, timeline, how rent is calculated…' : 'Say hi and share what you need the space for.'}"></textarea></section>

      <section class="block"><h2>Payment</h2><div class="list-row" id="pay"></div></section>
      <p class="muted small fine">This is a prototype — no real payment is taken.</p>
    </div>
    <div class="reserve-bar"><div id="bar-total"></div><button class="btn" id="confirm" disabled>…</button></div>`;
  bindBack(view);

  const range = () => {
    switch (b.term) {
      case 'hourly': {
        const s = `${b.date}T${String(b.hourStart).padStart(2, '0')}:00:00Z`;
        return [s, new Date(Date.parse(s) + b.hours * 3600e3).toISOString().replace('.000', '')];
      }
      case 'daily': case 'weekly': return [b.date, b.end];
      case 'monthly': return [b.date, addMonths(b.date, b.months)];
      case 'lease': return [b.date, addMonths(b.date, b.leaseMonths)];
      case 'infrastructure': return [b.date, addMonths(b.date, b.years * 12)];
    }
  };
  const cart = () => {
    const [start, end] = range();
    const c = { renterId: state.user, term: b.term, start, end, note: b.note };
    if (b.choice !== 'solo') c.packageId = b.choice;
    else c.items = [{ spaceId: space.id, qty: b.qty }, ...Object.entries(b.addons).filter(([, q]) => q > 0).map(([spaceId, qty]) => ({ spaceId, qty }))];
    return c;
  };

  function drawWhen() {
    const el = $('#when');
    const t = b.term;
    if (t === 'daily' || t === 'weekly') {
      el.innerHTML = `<div class="when-summary" id="when-sum"></div><div id="picker"></div>`;
      const sum = () => { $('#when-sum').innerHTML = b.end ? `${fmtDate(b.date)} → ${fmtDate(b.end)} <span class="muted">· ${((n) => `${n} night${n === 1 ? '' : 's'}`)(Math.round((Date.parse(b.end) - Date.parse(b.date)) / 864e5))}</span>` : `${fmtDate(b.date)} → <span class="muted">pick an end date</span>`; };
      sum();
      calendarPicker($('#picker'), { spaceId: space.id, mode: 'range', start: b.date, end: b.end, onChange: (r) => { b.date = r.start; b.end = r.end; sum(); if (r.end) refresh(); } });
      return;
    }
    const datePart = `<label>Start date<input type="date" id="w-date" value="${b.date}" min="${today()}"></label>`;
    if (t === 'hourly') {
      el.innerHTML = `<div class="form">${datePart}<div class="two">
        <label>Start time<select id="w-hour">${Array.from({ length: 17 }, (_, i) => i + 6).map((h) => `<option value="${h}" ${h === b.hourStart ? 'selected' : ''}>${h % 12 || 12}:00 ${h < 12 ? 'am' : 'pm'}</option>`).join('')}</select></label>
        <div class="field"><span>Hours</span>${stepper('hours', b.hours, { min: 1, max: 12 })}</div></div></div>`;
      $('#w-hour').onchange = (e) => { b.hourStart = +e.target.value; refresh(); };
    } else if (t === 'monthly') {
      el.innerHTML = `<div class="form"><div class="two">${datePart}<div class="field"><span>Months</span>${stepper('months', b.months, { min: 1, max: 12 })}</div></div>
        <p class="muted small">Month-to-month: renews automatically, cancel with 30 days' notice.</p></div>`;
    } else if (t === 'lease') {
      el.innerHTML = `<div class="form"><div class="two">${datePart}<label>Lease length<select id="w-lease">${[6, 12, 18, 24].map((m) => `<option ${m === b.leaseMonths ? 'selected' : ''} value="${m}">${m} months</option>`).join('')}</select></label></div></div>`;
      $('#w-lease').onchange = (e) => { b.leaseMonths = +e.target.value; refresh(); };
    } else if (t === 'infrastructure') {
      const opts = [5, 10, 15, 20, 25].filter((y) => y >= minYears);
      el.innerHTML = `<div class="form"><div class="two">${datePart}<label>Agreement<select id="w-years">${opts.map((y) => `<option ${y === b.years ? 'selected' : ''} value="${y}">${y} years</option>`).join('')}</select></label></div>
        <p class="muted small">Rent starts once the system is commissioned. Includes removal and restoration at the end.</p></div>`;
      $('#w-years').onchange = (e) => { b.years = +e.target.value; refresh(); };
    }
    $('#w-date').onchange = (e) => { if (e.target.value) { b.date = e.target.value; refresh(); } };
    bindSteppers(el, (name, v) => { b[name] = v; refresh(); });
  }

  for (const btn of $$('#terms [data-term]', view)) btn.onclick = () => {
    b.term = btn.dataset.term;
    for (const x of $$('#terms [data-term]', view)) x.classList.toggle('on', x === btn);
    if ((b.term === 'daily' || b.term === 'weekly') && (!b.end || b.end <= b.date)) b.end = addDays(b.date, b.term === 'weekly' ? 7 : 1);
    if (b.term === 'weekly' && Date.parse(b.end) - Date.parse(b.date) < 7 * 864e5) b.end = addDays(b.date, 7);
    drawWhen(); refresh();
  };
  for (const btn of $$('#choices [data-choice]', view)) btn.onclick = () => {
    b.choice = btn.dataset.choice;
    for (const x of $$('#choices [data-choice]', view)) x.classList.toggle('on', x === btn);
    $('#addons').hidden = b.choice !== 'solo';
    refresh();
  };
  bindSteppers(view.querySelector('.page'), (name, v) => {
    if (name === 'qty') b.qty = v;
    else if (name.startsWith('addon:')) b.addons[name.slice(6)] = v;
    else return;
    refresh();
  });
  $('#note').oninput = (e) => { b.note = e.target.value; };
  $('#pay').innerHTML = cat(space.category).group === 'energy'
    ? `<span class="pay-icon">🏢</span><div><strong>Invoiced to your company</strong><div class="muted small">Annual rent once the system is live</div></div>`
    : `<span class="pay-icon">💳</span><div><strong>Visa •••• 4242</strong><div class="muted small">Demo card</div></div>`;

  let lastMode = 'instant';
  const refresh = debounce(async () => {
    const q$ = $('#quote'); if (!q$) return;
    const btn = $('#confirm');
    try {
      const q = await api('quote', cart());
      lastMode = q.mode;
      q$.innerHTML = `${q.lines.map((l) => `<div class="qline"><div>${l.qty > 1 ? `${l.qty} × ` : ''}${esc(l.title)}${l.asAddon ? ' <span class="badge ok">tenant price</span>' : ''}
          <div class="muted small">${esc(l.detail)} × ${money(l.unitRate)}${l.events.length ? ` · <span class="event-text">${esc(l.events.join(', '))} rate</span>` : ''}</div></div><span>${money(l.amount)}</span></div>`).join('')}
        ${q.packageDiscount ? `<div class="qline ok"><span>Bundle discount</span><span>−${money(q.packageDiscount)}</span></div>` : ''}
        <div class="qline"><span>Service fee</span><span>${money(q.serviceFee)}</span></div>
        <div class="qline total"><span>Total</span><span>${money(q.total)}</span></div>
        <div class="qline muted"><span>Due today${q.schedule.recurring ? `, then ${money(q.schedule.recurring)}/${q.schedule.every}` : ''}</span><span>${money(q.schedule.dueNow)}</span></div>
        ${q.deposit ? `<div class="qline muted"><span>Refundable deposit (held)</span><span>${money(q.deposit)}</span></div>` : ''}
        <div class="muted small">${esc(q.schedule.note)}</div>
        ${q.availability.ok ? '<div class="avail ok">✓ Available</div>' : `<div class="error">Not available for these dates<ul>${q.availability.conflicts.map((c) => `<li>${esc(c.reason)}</li>`).join('')}</ul></div>`}`;
      $('#bar-total').innerHTML = `<div class="price">${money(q.schedule.recurring ?? q.total)}${q.schedule.recurring ? `<span>/${q.schedule.every}</span>` : ''}</div><div class="muted small">${q.schedule.recurring ? `${money(q.total)} total` : 'Total'}</div>`;
      btn.disabled = !q.availability.ok;
      btn.textContent = BUTTON[q.mode];
    } catch (e) {
      q$.innerHTML = errorBox(e);
      $('#bar-total').innerHTML = '';
      btn.disabled = true;
      btn.textContent = BUTTON[lastMode];
    }
  }, 120);

  $('#confirm').onclick = async () => {
    const btn = $('#confirm');
    btn.disabled = true;
    try {
      const booking = await api('bookings', cart());
      success(view, booking, title);
    } catch (e) {
      $('#quote').insertAdjacentHTML('afterbegin', errorBox(e));
      btn.disabled = false;
    }
  };

  drawWhen();
  refresh();
}

function success(view, b, title) {
  const head = { confirmed: ["You're booked!", 'Access details are in your trip.'], pending: ['Request sent', 'The host has 24 hours to respond. We\'ll hold your dates until then.'],
    proposed: ['Proposal sent', 'Next: the host reviews it and schedules a site assessment.'] }[b.status] ?? ['Done', ''];
  view.innerHTML = `<div class="success page narrow">
    <div class="success-icon">${icon.check}</div><h1>${head[0]}</h1><p class="muted">${head[1]}</p>
    <div class="card pad"><strong>${esc(title)}</strong><div class="muted small">${term(b.term).label} · ${fmtRange(b)}</div>
      <div class="row-between" style="margin-top:8px">${statusPill(b.status)}<strong>${money(b.quote.total)}</strong></div></div>
    <div class="stack"><a class="btn" href="#/trip/${b.id}">View trip</a><a class="btn ghost" href="#/chat/${b.id}">Message the host</a>
    <a class="btn link" href="#/explore">Keep exploring</a></div></div>`;
}
