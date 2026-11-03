// Listing detail page.
import { $, api, esc, state, cat, term, icon, money, stars, avatar, fmtDate, today, bindBack, cheapestRate, priceTag, TERM_ORDER } from './core.js';
import { art } from './art.js';
import { calendarPicker } from './calendar.js';

const MODE_TEXT = {
  instant: ['Instant book', 'Book and get access details right away.'],
  request: ['Request to book', 'The host has 24 hours to approve. Your dates are held while they decide.'],
  proposal: ['Proposal', 'Companies send a proposal, then a site assessment and contract. Rent starts once the system is installed.'],
};

export async function renderSpace(view, [id]) {
  const s = await api(`spaces/${id}`);
  const c = s.categoryInfo;
  const mine = s.property.hostId === state.user;
  const rates = TERM_ORDER.filter((t) => s.rates?.[t] != null);
  const upcomingEvents = (s.eventRates ?? []).filter((e) => e.end >= today());
  const r = cheapestRate(s);
  const mode = s.mode ?? c.mode;

  view.innerHTML = `
    <div class="hero">${art(s, { className: 'art hero-art' })}
      <button class="icon-btn floating" data-back aria-label="Back">${icon.back}</button></div>
    <div class="page">
      <div class="muted small">${c.icon} ${esc(c.label)} · ${esc(s.property.city)}</div>
      <h1 class="page-title">${esc(s.title)}</h1>
      <div class="meta-row">${stars(s.rating)}<span>·</span><span>${esc(s.property.title)}</span>
        ${(s.quantity ?? 1) > 1 ? `<span>·</span><span>${s.quantity} available</span>` : ''}</div>
      ${s.addonNote ? `<div class="notice warn">🔗 ${esc(s.addonNote)}</div>` : ''}
      ${s.parent ? `<div class="notice">Part of <strong>${esc(s.parent)}</strong>. When that whole space is booked, this one is too.</div>` : ''}

      <div class="host-row">${avatar(s.host, 44)}<div><strong>Hosted by ${esc(s.host.name)}</strong>
        <div class="muted small">On everyspace since ${esc(s.host.joined)}</div></div></div>

      ${s.description ? `<p>${esc(s.description)}</p>` : ''}
      ${s.amenities?.length ? `<div class="amenities">${s.amenities.map((a) => `<span>${esc(a)}</span>`).join('')}</div>` : ''}

      <h2 class="section-title">Prices</h2>
      <div class="rate-table">
        ${rates.map((t) => `<div><span>${term(t).label}</span><strong>${money(s.rates[t])}<span class="muted">/${term(t).unit}</span></strong></div>`).join('')}
        ${Object.entries(s.addonRates ?? {}).map(([t, v]) => `<div class="ok"><span>${term(t).label} with a rental here</span><strong>${money(v)}<span class="muted">/${term(t).unit}</span></strong></div>`).join('')}
      </div>
      ${upcomingEvents.length ? `<div class="notice event">🎟️ <div><strong>Event pricing</strong>${upcomingEvents.map((e) => `<div class="small">${esc(e.name)}, ${fmtDate(e.start)}${e.end !== e.start ? `–${fmtDate(e.end)}` : ''}: ${[e.daily && `${money(e.daily)}/day`, e.hourly && `${money(e.hourly)}/hr`].filter(Boolean).join(' · ')}</div>`).join('')}</div></div>` : ''}

      ${s.addons.length || s.packages.length ? `<h2 class="section-title">Make it a bundle</h2>
        ${s.addons.map((a) => `<div class="list-row">${art(a, { className: 'art mini' })}<div><strong>${esc(a.title)}</strong>
          <div class="muted small">${esc(a.addonNote)}</div></div><span class="small">${(() => { const x = cheapestRate({ rates: a.addonRates ?? a.rates }); return x ? `${money(x.amount)}/${x.unit}` : ''; })()}</span></div>`).join('')}
        ${s.packages.map((p) => `<a class="list-row link" href="#/book/pkg/${p.id}"><span class="pkg-icon">📦</span><div><strong>${esc(p.name)}</strong>
          <div class="muted small">${p.pricing.type === 'fixed' ? Object.entries(p.pricing.rates).map(([t, v]) => `${money(v)}/${term(t).unit} ${t === 'lease' ? 'on lease' : ''}`).join(' · ') : `${p.pricing.percent}% off together`}</div></div>${icon.chevron}</a>`).join('')}` : ''}

      ${c.group !== 'energy' ? '<h2 class="section-title">Availability</h2><div id="cal"></div>' : ''}

      <h2 class="section-title">Things to know</h2>
      <div class="facts">
        <div><strong>${MODE_TEXT[mode][0]}</strong><span>${MODE_TEXT[mode][1]}</span></div>
        ${c.deposit ? `<div><strong>Deposit</strong><span>${money(c.deposit)} held, not charged, released after checkout.</span></div>` : ''}
        <div><strong>Cancellation</strong><span>${rates.some((t) => ['lease', 'infrastructure'].includes(t)) ? 'Leases and agreements follow their contract terms.' : 'Free cancellation until 24 hours before start.'}</span></div>
        <div><strong>Host confirmed</strong><span>${c.checklist.map(esc).join(' · ')}</span></div>
        ${s.minDuration ? `<div><strong>Minimum</strong><span>${Object.entries(s.minDuration).map(([t, n]) => `${n} ${term(t).unit}s ${term(t).label.toLowerCase()}`).join(', ')}</span></div>` : ''}
      </div>

      <h2 class="section-title">${s.rating.count ? `★ ${s.rating.avg.toFixed(1)} · ${s.rating.count} review${s.rating.count > 1 ? 's' : ''}` : 'Reviews'}</h2>
      ${s.reviews.length ? `<div class="reviews">${s.reviews.map((rv) => `<div class="review">${avatar(rv.author, 32)}<div>
        <div><strong>${esc(rv.author?.name)}</strong> <span class="muted small">${fmtDate(rv.at, { year: true })}</span></div>
        <div class="stars-line">${'★'.repeat(rv.rating)}${'☆'.repeat(5 - rv.rating)}</div><p>${esc(rv.text)}</p></div></div>`).join('')}</div>`
        : '<div class="muted">No reviews yet. Be the first.</div>'}

      ${s.nearby.length ? `<h2 class="section-title">More at ${esc(s.property.title)}</h2>
        <div class="hscroll">${s.nearby.map((n) => `<a class="card mini-card" href="#/space/${n.id}">${art(n)}<div class="card-body"><strong class="title">${esc(n.title)}</strong>
          <div class="muted small">${cat(n.category).icon} ${esc(cat(n.category).label)}</div><div class="price small">${(() => { const x = cheapestRate(n); return x ? `from ${priceTag(x)}` : ''; })()}</div></div></a>`).join('')}</div>` : ''}
    </div>
    <div class="reserve-bar">
      ${mine ? `<div><strong>This is your listing</strong><div class="muted small">Switch to traveling mode to see it as a renter.</div></div><a class="btn ghost" href="#/host/listings">My listings</a>`
        : `<div><div class="price">${r ? `from ${priceTag(r)}` : ''}</div><div class="muted small">${MODE_TEXT[mode][0]}</div></div>
           <a class="btn" href="#/book/${s.id}">${mode === 'proposal' ? 'Send proposal' : s.policy === 'addon' ? 'Add to my rental' : 'Reserve'}</a>`}
    </div>`;
  bindBack(view);
  if ($('#cal')) calendarPicker($('#cal'), { spaceId: s.id, mode: 'view', start: state.filters.start || '' });
}
