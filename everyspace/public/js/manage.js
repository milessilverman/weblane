// Owner's "Manage listing" screen, and the public "How pricing works" page.
import { $, $$, api, esc, state, term, icon, money, fmtDate, topbar, bindBack, errorBox, toast, TERM_ORDER } from './core.js';
import { art } from './art.js';
import { calendarPicker } from './calendar.js';

export async function renderManage(view, [id]) {
  let s;
  try { s = await api(`spaces/${id}/manage?userId=${state.user}`); }
  catch (e) { view.innerHTML = `${topbar('Manage listing')}<div class="page">${errorBox(e)}</div>`; bindBack(view); return; }
  const c = s.categoryInfo;
  const pricing = await api('pricing');
  const platforms = Object.entries(pricing.platforms);
  const terms = TERM_ORDER.filter((t) => c.terms.includes(t));
  const payout = (v) => money(v * (1 - pricing.hostFee));
  const renterPays = (v) => money(v * (1 + pricing.serviceFee));
  let blackouts = [...(s.blackouts ?? [])];
  let externals = [...(s.externalListings ?? [])];
  let pick = { start: '', end: '' };

  view.innerHTML = `${topbar('Manage listing', { right: `<a class="icon-btn" href="#/space/${s.id}" aria-label="View public page">${icon.chevron}</a>` })}
    <div class="page narrow manage">
      <div class="summary-card">${art(s, { className: 'art thumb-sm' })}<div><div class="muted small">${c.icon} ${esc(c.label)}</div>
        <strong>${esc(s.title)}</strong><div class="small">${s.upcomingCount} upcoming booking${s.upcomingCount === 1 ? '' : 's'} · <a class="link-text" href="#/space/${s.id}">See what renters see</a></div></div></div>

      <section class="block row-between"><div><h2>${s.paused ? '⏸️ Paused' : '🟢 Taking bookings'}</h2>
        <div class="muted small">${s.paused ? 'Hidden from search. Existing bookings are not affected.' : 'Pausing hides it from search instantly. Existing bookings stay.'}</div></div>
        <label class="switch"><input type="checkbox" id="live" ${s.paused ? '' : 'checked'}><span></span></label></section>

      ${s.parity.length ? `<div class="notice warn">⚖️ <div><strong>It's cheaper on ${esc(s.parity[0].cheapest.name)}.</strong>
        Renters here pay ${money(s.parity[0].ours)} per ${term(s.parity[0].term).unit} all-in; on ${esc(s.parity[0].cheapest.name)} about ${money(s.parity[0].cheapest.theirs)}.
        We give up our own cut to compete, and <strong>your payout never changes</strong>. Set the price below that pays you the same as there, and renters pay less here.</div></div>` : ''}

      ${s.takeHome.length ? `<section class="block"><h2>You earn the same everywhere</h2>
        <p class="muted small">What you take home per unit after each site's owner fee (their fees are estimates). Matching your take-home here makes Everyspace the cheapest place to book you, because our fees are lower.</p>
        <div class="compare">${s.takeHome.map((r, i) => `<div class="compare-row take-row"><span><strong>${esc(r.name)} · ${term(r.term).label}</strong>
            <span class="muted small">You get ${r.there != null ? money(r.there) : r.thereRange ? `${money(r.thereRange[0])}–${money(r.thereRange[1])}` : 'an unpublished amount'} there
              · ${r.here != null ? `${money(r.here)} here` : 'not offered here'}${r.renterThere != null ? ` · renters pay ~${money(r.renterThere)} there` : ''}</span>
            ${r.sameRate != null ? `<span class="small payout">Price here for the same take-home: ${money(r.sameRate)} → renters pay ${money(r.renterAtSame)}</span>`
              : `<span class="small muted">${esc(r.name)} doesn't publish one owner fee, so we can't work out a same-take-home price.</span>`}</span>
            ${r.sameRate == null ? '' : r.here == null || Math.abs(r.sameRate - (s.rates?.[r.term] ?? 0)) > 0.01 ? `<button class="btn small" data-same="${i}">Use ${money(r.sameRate)}</button>` : '<span class="badge ok">Matched</span>'}</div>`).join('')}</div></section>` : ''}
      ${s.notices.length ? `<div class="notice">📄 <div><strong>Before you compare prices</strong>${s.notices.map((n) => `<div class="small">${esc(n.text)}</div>`).join('')}</div></div>` : ''}

      ${c.audience === 'business' ? '' : `<section class="block row-between"><div><h2>${(s.mode ?? c.mode) === 'instant' ? '⚡ Instant book' : '✋ You approve each request'}</h2>
        <div class="muted small">${(s.mode ?? c.mode) === 'instant' ? 'Renters book right away. Most bookings, least work.' : 'You get 24 hours to accept or decline. Dates are held meanwhile.'}</div></div>
        <label class="switch" title="Instant book"><input type="checkbox" id="instant" ${(s.mode ?? c.mode) === 'instant' ? 'checked' : ''}><span></span></label></section>`}

      <section class="block"><h2>Prices</h2>
        <div class="price-list">${terms.map((t) => {
          const m = s.market[t];
          const v = s.rates?.[t] ?? '';
          return `<div class="price-item manage-price"><div><strong>${term(t).label}</strong>
            <div class="muted small">${m?.count ? `Nearby: ${money(m.min)}–${money(m.max)} · median ${money(m.median)}` : m?.typical ? `Typical: ${money(m.typical)}` : 'No nearby data yet'}</div>
            <div class="small payout" data-payout="${t}">${v ? `Renter pays ${renterPays(v)} · <strong>you get ${payout(v)}</strong>` : 'Off'}</div></div>
            <label class="money-input">$<input type="number" min="0" step="1" data-rate="${t}" value="${esc(v)}" placeholder="off"><span>/${term(t).unit}</span></label></div>`;
        }).join('')}</div>
        <p class="muted small">Leave a length blank to turn it off. You keep ${100 - pricing.hostFee * 100}% of your price; renters pay a ${pricing.serviceFee * 100}% service fee that's always shown up front.</p>
        <button class="btn" id="save-prices">Save prices</button><div id="price-msg"></div></section>

      <section class="block"><h2>Block dates</h2>
        <p class="muted small">Using it yourself, or booked somewhere else? Block it so nobody can book it here.</p>
        <div id="cal"></div>
        <div class="two"><label class="form">Reason (optional)<input id="bo-reason" placeholder="Family visiting"></label><button class="btn ghost" id="add-bo" disabled>Block these dates</button></div>
        <div id="bo-list"></div></section>

      <section class="block"><h2>Also listed elsewhere?</h2>
        <p class="muted small">Link your listing on other sites so renters can see the comparison. It's honest, it builds trust, and if we're cheaper we say so. If another site is cheaper, we beat it and cover the difference.</p>
        <div id="ext-list"></div>
        <div class="card pad form" id="ext-form">
          <label>Link to your listing<input id="ext-url" placeholder="https://www.airbnb.com/rooms/…"></label>
          <div class="two"><label>Your price there<select id="ext-term">${terms.map((t) => `<option value="${t}">${term(t).label}</option>`).join('')}</select></label>
            <label class="money-input">$<input id="ext-price" type="number" min="0"></label></div>
          ${['hourly', 'daily', 'weekly'].some((t) => terms.includes(t)) ? '<label>Cleaning or extra fee they charge per booking<input id="ext-clean" type="number" min="0" placeholder="0"></label>' : ''}
          <div class="muted small">Works with ${platforms.map(([, p]) => esc(p.name)).join(', ')}.</div>
          <button class="btn ghost" id="add-ext">Add link</button><div id="ext-msg"></div></div></section>
    </div>`;
  bindBack(view);

  const save = async (changes, msgEl, okText) => {
    try { await api(`spaces/${s.id}/update`, { actorId: state.user, changes }); toast(okText); return true; }
    catch (e) { if (msgEl) msgEl.innerHTML = errorBox(e); else toast(e.message); return false; }
  };

  for (const b of $$('[data-same]', view)) b.onclick = async () => {
    const r = s.takeHome[+b.dataset.same];
    if (await save({ rates: { ...s.rates, [r.term]: r.sameRate } }, null, `${term(r.term).label} price set to ${money(r.sameRate)}`)) renderManage(view, [id]);
  };
  if ($('#instant')) $('#instant').onchange = async (e) => {
    if (await save({ mode: e.target.checked ? 'instant' : 'request' }, null, e.target.checked ? 'Instant book on' : 'You\'ll approve each request')) renderManage(view, [id]);
  };
  $('#live').onchange = async (e) => { if (await save({ paused: !e.target.checked }, null, e.target.checked ? 'Listing is live' : 'Listing paused')) renderManage(view, [id]); };
  for (const inp of $$('[data-rate]', view)) inp.oninput = () => {
    const v = Number(inp.value);
    $(`[data-payout="${inp.dataset.rate}"]`, view).innerHTML = v > 0 ? `Renter pays ${renterPays(v)} · <strong>you get ${payout(v)}</strong>` : 'Off';
  };
  $('#save-prices').onclick = async () => {
    const rates = Object.fromEntries($$('[data-rate]', view).map((i) => [i.dataset.rate, i.value]));
    if (await save({ rates }, $('#price-msg'), 'Prices saved')) renderManage(view, [id]);
  };

  const drawBlackouts = () => {
    $('#bo-list').innerHTML = blackouts.length ? blackouts.map((b, i) => `<div class="list-row"><span class="pkg-icon">🚫</span><div><strong>${fmtDate(b.start)} → ${fmtDate(b.end, { year: true })}</strong>
      <div class="muted small">${esc(b.reason)}</div></div><button class="btn small ghost" data-unblock="${i}">Unblock</button></div>`).join('') : '<div class="muted small">No blocked dates.</div>';
    for (const b of $$('[data-unblock]', view)) b.onclick = async () => {
      const next = blackouts.filter((_, i) => i !== +b.dataset.unblock);
      if (await save({ blackouts: next }, null, 'Dates unblocked')) { blackouts = next; drawBlackouts(); cal.set('', ''); }
    };
  };
  const cal = calendarPicker($('#cal'), { spaceId: s.id, mode: 'range', onChange: (r) => { pick = r; $('#add-bo').disabled = !(r.start && r.end); } });
  $('#add-bo').onclick = async () => {
    const next = [...blackouts, { start: pick.start, end: pick.end, reason: $('#bo-reason').value || 'Blocked by owner' }];
    if (await save({ blackouts: next }, null, 'Dates blocked')) { blackouts = next; drawBlackouts(); pick = { start: '', end: '' }; cal.set('', ''); $('#add-bo').disabled = true; }
  };
  drawBlackouts();

  const drawExt = () => {
    $('#ext-list').innerHTML = externals.map((e, i) => {
      const p = pricing.platforms[e.platform];
      return `<div class="list-row"><span class="pkg-icon">🔗</span><div><strong>${esc(p?.name ?? e.platform)}</strong>
        <div class="muted small">${Object.entries(e.rates).map(([t, v]) => `${money(v)}/${term(t).unit}`).join(' · ')}${e.cleaningFee ? ` + ${money(e.cleaningFee)} fee` : ''} · your price, checked ${e.verifiedAt ? fmtDate(e.verifiedAt) : 'pending'}${e.verifiedAt && (Date.now() - Date.parse(e.verifiedAt)) / 864e5 > pricing.staleDays ? ' · <b>out of date, update it</b>' : ''}${e.demo ? ' · demo link' : ''}</div></div>
        <button class="btn small ghost" data-unlink="${i}">Remove</button></div>`;
    }).join('');
    for (const b of $$('[data-unlink]', view)) b.onclick = async () => {
      const next = externals.filter((_, i) => i !== +b.dataset.unlink);
      if (await save({ externalListings: next }, $('#ext-msg'), 'Link removed')) { externals = next; drawExt(); }
    };
  };
  $('#add-ext').onclick = async () => {
    const item = { url: $('#ext-url').value.trim(), rates: { [$('#ext-term').value]: $('#ext-price').value }, cleaningFee: $('#ext-clean')?.value || 0 };
    const next = [...externals, item];
    if (await save({ externalListings: next }, $('#ext-msg'), 'Link added')) renderManage(view, [id]);
  };
  drawExt();
}

export async function renderFairPrice(view) {
  const p = await api('pricing');
  const pct = (n) => `${Math.round(n * 1000) / 10}%`;
  const share = p.serviceFee + p.hostFee, ofTotal = share / (1 + p.serviceFee);
  const fee = (v) => (v == null ? '<span class="muted">not published</span>' : pct(v));
  view.innerHTML = `${topbar('How pricing works')}
    <div class="page narrow plan">
      <h1 class="page-title">Honest prices, every time</h1>
      <p class="lead">The price you see is the price you pay, including taxes we can calculate. Owners keep more here. And if the same space is cheaper somewhere else, we cut our own fees to beat it, up to everything we earn on that booking.</p>

      <h2>What you pay, and where it goes</h2>
      <div class="money-flow"><div style="flex:${(1 - p.hostFee) * 100}"><strong>${pct(1 - p.hostFee)}</strong><span>to the owner</span></div>
        <div style="flex:${p.hostFee * 100 + 6}"><strong>${pct(p.hostFee)}</strong><span>owner fee</span></div>
        <div style="flex:${p.serviceFee * 100 + 6}" class="fee"><strong>+${pct(p.serviceFee)}</strong><span>service fee</span></div></div>
      <ul>
        <li><strong>All-in prices.</strong> Every price includes our ${pct(p.serviceFee)} service fee. Lodging tax is added up front where we know it (for example San Diego's 11.75% transient occupancy tax on stays under a month). Where a tax isn't set up yet, checkout says so instead of showing it as $0.</li>
        <li><strong>Owners keep ${pct(1 - p.hostFee)}</strong> of their price. In total, Everyspace keeps ${pct(ofTotal)} of what you pay (our ${pct(p.serviceFee)} + ${pct(p.hostFee)} fees). Every receipt shows the exact amount.</li>
        <li><strong>Deposits are separate from what you're charged.</strong> Short stays: a temporary card hold, released after checkout unless the owner documents damage. Leases: a refundable deposit collected under the rental agreement.</li>
      </ul>

      <h2>Price-beat guarantee: the full terms</h2>
      <p><strong>The limit, up front:</strong> we fund the beat from our own fees on that booking (the ${pct(p.serviceFee)} service fee and the ${pct(p.hostFee)} owner fee), never from the owner's payout. If a lower price elsewhere is more than those fees can cover, we give up all of them and tell you it's still cheaper there.</p>
      <ol>
        <li><strong>Before you book:</strong> if the owner has told us their price on another site, we show both totals side by side, before tax. If theirs is lower and we know that site's renter fees, checkout beats it by ${pct(p.beatPct)} automatically, within the limit above.</li>
        <li><strong>After you book:</strong> send us the link and the total within ${p.claimWindowHours} hours of booking, or any time before your booking starts. Include a screenshot of their checkout total. We refund the difference plus ${pct(p.beatPct)} of their price, within the limit above.</li>
        <li><strong>What counts:</strong> the same space, the same dates and times, the same number of guests, vehicles or units, and the full total including that site's mandatory fees. Member-only prices, coupons and different cancellation terms don't count.</li>
        <li><strong>How we check:</strong> claims matching the owner's own current listing are approved instantly. Others are reviewed by a person within 24 hours. Refunds go back to your original payment method.</li>
        <li><strong>Disagree with a decision?</strong> Reply in the booking's chat and a different person reviews it.</li>
      </ol>

      <h2>How we compare totals</h2>
      <p class="muted">Other sites' prices come from what owners tell us, dated, and are only used while they're under ${p.staleDays} days old. We never copy listings from other sites. Fees below were researched on ${esc(p.researched)} from each site's own help pages. Where a site doesn't publish a renter fee, we can't total its price, so those listings are shown but not compared.</p>
      <div class="table-wrap"><table><thead><tr><th>Site</th><th>Renter fee</th><th>Owner fee</th><th>Notes</th></tr></thead><tbody>
        <tr><td><strong>Everyspace</strong></td><td><strong>${pct(p.serviceFee)}</strong></td><td><strong>${pct(p.hostFee)}</strong></td><td>No cleaning or booking fees.</td></tr>
        ${Object.values(p.platforms).map((x) => `<tr><td>${esc(x.name)}</td><td>${fee(x.guestFeePct)}</td><td>${x.hostFeePct != null ? pct(x.hostFeePct) : x.hostFeeRange ? `${pct(x.hostFeeRange[0])}–${pct(x.hostFeeRange[1])}` : '<span class="muted">not published</span>'}</td><td class="small muted">${esc(x.plan || '')}</td></tr>`).join('')}
      </tbody></table></div>
      <p class="muted small">Everyspace isn't affiliated with any of these sites. Names are used only to identify where a price came from.</p>
    </div>`;
  bindBack(view);
}
