// Renter's trips: list and detail (status, access details, receipt, cancel, review).
import { $, $$, api, esc, state, term, icon, money, avatar, fmtRange, topbar, bindBack, statusPill, errorBox, toast } from './core.js';
import { art } from './art.js';

const UPCOMING = new Set(['pending', 'proposed', 'site_assessment', 'contract', 'confirmed', 'active']);

export async function renderTrips(view) {
  const all = (await api(`bookings?userId=${state.user}`)).filter((b) => b.role === 'renter');
  const tab = state.tripsTab ?? 'upcoming';
  const list = all.filter((b) => (tab === 'upcoming' ? UPCOMING.has(b.effective) : !UPCOMING.has(b.effective)))
    .sort((a, b) => (tab === 'upcoming' ? (a.start < b.start ? -1 : 1) : (a.start < b.start ? 1 : -1)));
  view.innerHTML = `${topbar('Trips', { back: false })}
    <div class="page">
      <div class="segmented wide" id="tabs"><button data-t="upcoming" class="${tab === 'upcoming' ? 'on' : ''}">Upcoming</button><button data-t="past" class="${tab === 'past' ? 'on' : ''}">Past</button></div>
      ${list.length ? list.map(tripCard).join('') : `<div class="empty"><div class="empty-icon">🧳</div>${tab === 'upcoming' ? 'No trips booked yet.' : 'Nothing here yet.'}
        <a class="btn" href="#/explore">Find a space</a></div>`}
    </div>`;
  for (const b of $$('#tabs [data-t]', view)) b.onclick = () => { state.tripsTab = b.dataset.t; renderTrips(view); };
}

function tripCard(b) {
  return `<a class="card trip-card" href="#/trip/${b.id}">${art(b.primary, { className: 'art thumb-md' })}
    <div class="card-body"><div class="row-between">${statusPill(b.effective)}${b.canReview ? '<span class="badge event">Leave a review</span>' : ''}</div>
      <strong class="title">${esc(b.packageName ?? b.itemsLabel)}</strong>
      <div class="muted small">${esc(b.property?.title)} · ${term(b.term).label}</div>
      <div class="small">${fmtRange(b)}</div></div></a>`;
}

const FLOW = {
  instant: ['confirmed'],
  request: ['pending', 'confirmed'],
  proposal: ['proposed', 'site_assessment', 'contract', 'confirmed'],
};
const STEP_LABEL = { pending: 'Requested', proposed: 'Proposal', site_assessment: 'Site visit', contract: 'Contract', confirmed: 'Confirmed' };

export async function renderTrip(view, [id]) {
  const b = (await api(`bookings?userId=${state.user}`)).find((x) => x.id === id);
  if (!b) { view.innerHTML = `${topbar('Trip')}<div class="page"><div class="empty">Trip not found for this account.</div></div>`; bindBack(view); return; }
  const isHost = b.role === 'host';
  const other = isHost ? b.renter : b.host;
  const steps = FLOW[b.mode] ?? FLOW.instant;
  const reached = steps.indexOf(b.status === 'active' || b.status === 'completed' ? 'confirmed' : b.status);
  const cancellable = ['pending', 'proposed', 'site_assessment', 'contract', 'confirmed'].includes(b.status) && b.effective !== 'completed';
  const q = b.quote;

  view.innerHTML = `${topbar(isHost ? 'Booking' : 'Your trip')}
    <div class="hero short">${art(b.primary, { className: 'art hero-art' })}</div>
    <div class="page narrow">
      <div class="row-between">${statusPill(b.effective)}<span class="muted small">#${esc(b.id)}</span></div>
      <h1 class="page-title">${esc(b.packageName ?? b.itemsLabel)}</h1>
      <div class="muted">${esc(b.property?.title)}, ${esc(b.property?.city)} · ${term(b.term).label}</div>
      <div class="when-big">${icon.calendar}<span>${fmtRange(b)}</span></div>

      ${['declined', 'cancelled'].includes(b.status) ? '' : `<div class="timeline">${steps.map((s, i) => `<div class="${i <= reached ? 'done' : ''}"><i></i><span>${STEP_LABEL[s]}</span></div>`).join('')}</div>`}

      ${b.access ? `<section class="block access"><h2>${icon.lock} Access details</h2>${b.access.map((a) => `<div><strong>${esc(a.title)}</strong><p>${esc(a.text)}</p></div>`).join('')}</section>`
        : UPCOMING.has(b.effective) ? `<section class="block muted-block">${icon.lock} Access details appear here once the booking is confirmed.</section>` : ''}

      <section class="block"><div class="host-row">${avatar(other, 44)}<div><strong>${isHost ? 'Renter' : 'Host'}: ${esc(other?.name)}</strong>
        <div class="muted small">${esc(other?.tagline ?? '')}</div></div><a class="btn small ghost" href="#/chat/${b.id}">Message</a></div></section>

      ${q ? `<section class="block"><h2>Receipt</h2><div class="quote">
        ${q.lines.map((l) => `<div class="qline"><div>${l.qty > 1 ? `${l.qty} × ` : ''}${esc(l.title)}<div class="muted small">${esc(l.detail)} × ${money(l.unitRate)}</div></div><span>${money(l.amount)}</span></div>`).join('')}
        ${q.packageDiscount ? `<div class="qline ok"><span>Bundle discount</span><span>−${money(q.packageDiscount)}</span></div>` : ''}
        ${q.serviceFee != null ? `<div class="qline"><span>Service fee</span><span>${money(q.serviceFee)}</span></div>` : ''}
        <div class="qline total"><span>Total</span><span>${money(q.total)}</span></div>
        ${q.schedule?.recurring ? `<div class="qline muted"><span>Billed every ${q.schedule.every}</span><span>${money(q.schedule.recurring)}</span></div>` : ''}
        ${isHost && q.hostPayout != null ? `<div class="qline ok"><span>Your payout (after 3% host fee)</span><span>${money(q.hostPayout)}</span></div>` : ''}
      </div></section>` : ''}

      ${b.canReview ? `<section class="block" id="review"><h2>How was it?</h2>
        <div class="star-input" id="stars">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-star="${n}" aria-label="${n} stars">★</button>`).join('')}</div>
        <textarea id="review-text" rows="3" placeholder="What should the next renter know?"></textarea>
        <button class="btn" id="send-review" disabled>Post review</button><div id="review-msg"></div></section>` : ''}
      ${b.reviewed ? '<div class="notice ok">✓ You reviewed this booking. Thanks!</div>' : ''}

      ${b.note ? `<section class="block"><h2>Note</h2><p class="muted">“${esc(b.note)}”</p></section>` : ''}
      ${cancellable ? `<button class="btn danger-ghost wide" id="cancel">${b.status === 'pending' || b.status === 'proposed' ? 'Withdraw request' : 'Cancel booking'}</button>` : ''}
      <div id="msg"></div>
    </div>`;
  bindBack(view);

  if (cancellable) $('#cancel').onclick = async () => {
    if (!confirm('Cancel this booking?')) return;
    try { await api(`bookings/${b.id}/cancel`, { actorId: state.user }); toast('Booking cancelled'); renderTrip(view, [id]); }
    catch (e) { $('#msg').innerHTML = errorBox(e); }
  };
  if (b.canReview) {
    let rating = 0;
    for (const s of $$('[data-star]', view)) s.onclick = () => {
      rating = +s.dataset.star;
      for (const x of $$('[data-star]', view)) x.classList.toggle('on', +x.dataset.star <= rating);
      $('#send-review').disabled = false;
    };
    $('#send-review').onclick = async () => {
      try { await api(`bookings/${b.id}/review`, { by: state.user, rating, text: $('#review-text').value }); toast('Review posted'); renderTrip(view, [id]); }
      catch (e) { $('#review-msg').innerHTML = errorBox(e); }
    };
  }
}

