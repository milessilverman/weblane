// Hosting: Today (requests to answer, upcoming), Listings, Earnings.
import { $, $$, api, esc, state, cat, term, icon, money, fmtRange, topbar, statusPill, errorBox, toast, stars, TERM_ORDER } from './core.js';
import { art } from './art.js';

const NEXT_LABEL = { proposed: 'Accept proposal', site_assessment: 'Site passed', contract: 'Mark signed' };

export async function renderHostToday(view) {
  const s = await api(`host/summary?hostId=${state.user}`);
  const me = state.me;
  const hour = new Date().getHours();
  view.innerHTML = `${topbar('Today', { back: false, right: `<a class="icon-btn" href="#/host/new" aria-label="New listing">${icon.plus}</a>` })}
    <div class="page">
      <h1 class="greeting">Good ${hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'}, ${esc(me.name)}</h1>
      <div class="stats">
        <a href="#/host/earnings"><span>This month</span><strong>${money(s.earnings.thisMonth)}</strong></a>
        <a href="#/host/earnings"><span>Next 6 months</span><strong>${money(s.earnings.next6)}</strong></a>
        <a href="#/host/listings"><span>Listings</span><strong>${s.listingCount}<small> · ${s.unitsListed} units</small></strong></a>
      </div>
      ${s.listingCount === 0 ? `<a class="host-cta" href="#/host/new"><div><strong>List your first space</strong><span>Driveway, backyard, garage, roof — anything you're not using.</span></div><span class="cta-btn">Start</span></a>` : ''}

      <h2 class="section-title">Needs your answer ${s.needsAction.length ? `<span class="count">${s.needsAction.length}</span>` : ''}</h2>
      ${s.needsAction.length ? s.needsAction.map((b) => `<div class="card pad request" data-id="${b.id}">
          <div class="row-between"><strong>${esc(b.itemsLabel)}</strong>${statusPill(b.status)}</div>
          <div class="muted small">${esc(b.renterName)} · ${term(b.term).label} · ${fmtRange(b)}</div>
          ${b.note ? `<p class="small">“${esc(b.note)}”</p>` : ''}
          <div class="row-between"><strong>${money(b.quote?.hostPayout ?? 0)} <span class="muted small">your payout${b.quote?.schedule?.recurring ? ' total' : ''}</span></strong>
          <div class="btn-row">${b.status === 'pending' ? '<button class="btn small" data-act="approve">Approve</button>' : `<button class="btn small" data-act="advance">${NEXT_LABEL[b.status]}</button>`}
          <button class="btn small ghost" data-act="decline">Decline</button><a class="btn small ghost" href="#/chat/${b.id}">Message</a></div></div></div>`).join('')
        : '<div class="muted-block">You\'re all caught up. ✨</div>'}

      ${s.active.length ? `<h2 class="section-title">Happening now</h2>${s.active.map(row).join('')}` : ''}
      <h2 class="section-title">Coming up</h2>
      ${s.upcoming.length ? s.upcoming.map(row).join('') : '<div class="muted-block">No check-ins in the next 45 days.</div>'}
      <div id="msg"></div>
    </div>`;
  for (const btn of $$('[data-act]', view)) btn.onclick = async () => {
    const id = btn.closest('[data-id]').dataset.id;
    if (btn.dataset.act === 'decline' && !confirm('Decline this request?')) return;
    try { await api(`bookings/${id}/${btn.dataset.act}`, { actorId: state.user }); toast(btn.dataset.act === 'decline' ? 'Declined' : 'Updated'); renderHostToday(view); }
    catch (e) { $('#msg').innerHTML = errorBox(e); }
  };
}

const row = (b) => `<a class="list-row link" href="#/trip/${b.id}">${art(b.primary, { className: 'art mini' })}
  <div><strong>${esc(b.itemsLabel)}</strong><div class="muted small">${esc(b.renterName)} · ${fmtRange(b)}</div></div>${icon.chevron}</a>`;

export async function renderHostListings(view) {
  const props = await api(`properties?hostId=${state.user}`);
  const tree = (spaces) => {
    const out = [];
    const walk = (pid, d) => spaces.filter((s) => (s.parentId ?? null) === pid).forEach((s) => { out.push([s, d]); walk(s.id, d + 1); });
    walk(null, 0);
    return out;
  };
  view.innerHTML = `${topbar('Listings', { back: false, right: `<a class="icon-btn" href="#/host/new" aria-label="New listing">${icon.plus}</a>` })}
    <div class="page">
      ${props.length ? props.map((p) => `<section class="property">
        <div class="row-between"><div><h2>${esc(p.title)}</h2><div class="muted small">${esc(p.city)} · ${esc(p.type.replace('_', ' '))}${p.hoa ? ' · HOA' : ''}</div></div>
          <a class="btn small ghost" href="#/host/new?property=${p.id}">${icon.plus} Add space</a></div>
        ${tree(p.spaces).map(([s, d]) => s.rentable === false
          ? `<div class="container-row" style="--d:${d}">🏗️ <strong>${esc(s.title)}</strong> <span class="muted small">groups the spaces below, not rented itself</span></div>`
          : `<a class="list-row link listing-row" style="--d:${d}" href="#/space/${s.id}">${art(s, { className: 'art mini' })}
            <div><strong>${esc(s.title)}</strong><div class="muted small">${cat(s.category).icon} ${esc(cat(s.category).label)}${(s.quantity ?? 1) > 1 ? ` · ×${s.quantity}` : ''} · ${stars(s.rating)}</div>
            <div class="small">${TERM_ORDER.filter((t) => s.rates?.[t] != null).map((t) => `${money(s.rates[t])}/${term(t).unit}${t === 'lease' ? ' lease' : ''}`).join(' · ')}</div>
            ${s.addonNote ? `<span class="badge warn">${esc(s.addonNote)}</span>` : ''}</div>${icon.chevron}</a>`).join('')}
        ${p.packages.length ? `<div class="pkgs">${p.packages.map((k) => `<span class="badge">📦 ${esc(k.name)}</span>`).join('')}</div>` : ''}
      </section>`).join('') : `<div class="empty"><div class="empty-icon">🏡</div>You haven't listed anything yet.<a class="btn" href="#/host/new">Create a listing</a></div>`}
    </div>`;
}

export async function renderHostEarnings(view) {
  const s = await api(`host/summary?hostId=${state.user}`);
  const e = s.earnings;
  const max = Math.max(1, ...e.byMonth.map((m) => m.amount));
  const thisMonth = new Date().toISOString().slice(0, 7);
  const MON = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  view.innerHTML = `${topbar('Earnings', { back: false })}
    <div class="page">
      <div class="earn-hero"><span>Booked for the next 6 months</span><strong>${money(e.next6)}</strong>
        <div class="muted small">After the 3% host fee. All-time booked: ${money(e.allTime)}</div></div>
      <div class="bars" role="img" aria-label="Payouts by month">${e.byMonth.map((m) => `<div class="bar ${m.month === thisMonth ? 'now' : m.month < thisMonth ? 'past' : ''}">
        <span class="bar-val">${m.amount ? money(Math.round(m.amount)) : ''}</span><i style="height:${Math.max(2, (m.amount / max) * 100)}%"></i><span>${MON[+m.month.slice(5) - 1]}</span></div>`).join('')}</div>
      <h2 class="section-title">By listing</h2>
      ${e.perSpace.length ? e.perSpace.map((p) => `<a class="list-row link" href="#/space/${p.spaceId}"><div><strong>${esc(p.title)}</strong></div><strong>${money(p.amount)}</strong></a>`).join('')
        : '<div class="muted-block">No bookings yet. Earnings show up as soon as someone books.</div>'}
      <h2 class="section-title">Payout method</h2>
      <div class="list-row"><span class="pay-icon">🏦</span><div><strong>Checking •••• 6789</strong><div class="muted small">Paid 24h after check-in, or monthly for leases (demo)</div></div></div>
    </div>`;
}

