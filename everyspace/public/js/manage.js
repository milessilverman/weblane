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
        We automatically beat their price and <strong>pay the difference ourselves</strong>. Your payout doesn't change, but lowering your price here gets you more bookings.</div></div>` : ''}

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
        <div class="muted small">${Object.entries(e.rates).map(([t, v]) => `${money(v)}/${term(t).unit}`).join(' · ')}${e.cleaningFee ? ` + ${money(e.cleaningFee)} fee` : ''} · checked ${e.verifiedAt ? fmtDate(e.verifiedAt) : 'pending'}${e.demo ? ' · demo link' : ''}</div></div>
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
  view.innerHTML = `${topbar('How pricing works')}
    <div class="page narrow plan">
      <h1 class="page-title">Honest prices, every time</h1>
      <p class="lead">The price you see is the price you pay. Owners keep more. And if the same space is cheaper somewhere else, we beat it.</p>

      <h2>What you pay, and where it goes</h2>
      <div class="money-flow"><div style="flex:${(1 - p.hostFee) * 100}"><strong>${pct(1 - p.hostFee)}</strong><span>to the owner</span></div>
        <div style="flex:${p.hostFee * 100 + 6}"><strong>${pct(p.hostFee)}</strong><span>owner fee</span></div>
        <div style="flex:${p.serviceFee * 100 + 6}" class="fee"><strong>+${pct(p.serviceFee)}</strong><span>service fee</span></div></div>
      <ul>
        <li><strong>All-in prices.</strong> Every price in search already includes our ${pct(p.serviceFee)} service fee. No surprise fees at checkout, no hidden cleaning fees.</li>
        <li><strong>Owners keep ${pct(1 - p.hostFee)}.</strong> We take ${pct(p.hostFee)} from the owner's price, and the breakdown is on every receipt.</li>
        <li><strong>Deposits are held, never charged</strong>, unless there's damage the owner documents with check-in/out photos.</li>
      </ul>

      <h2>Price-beat guarantee</h2>
      <ol>
        <li><strong>Before you book:</strong> if the owner also lists the space on another site, we show you both prices side by side. If theirs is lower, we automatically beat it by ${pct(p.beatPct)} at checkout.</li>
        <li><strong>After you book:</strong> found the same space cheaper for the same dates? Send us the link and the total within ${p.claimWindowHours} hours of booking, or any time before it starts. We refund the difference plus ${pct(p.beatPct)} of the other price.</li>
        <li><strong>Everyspace pays for it, not the owner.</strong> The owner's payout never changes.</li>
        <li>It has to be the same space, the same dates and the full total including that site's fees.</li>
      </ol>

      <h2>How we compare totals</h2>
      <p class="muted">Other sites add their own fees on top of the owner's price. We include them so the comparison is fair. These are estimates and are labeled that way.</p>
      <div class="table-wrap"><table><thead><tr><th>Site</th><th>Renter fee we assume</th><th>Per booking</th></tr></thead><tbody>
        <tr><td><strong>Everyspace</strong></td><td><strong>${pct(p.serviceFee)}</strong></td><td>$0</td></tr>
        ${Object.values(p.platforms).map((x) => `<tr><td>${esc(x.name)}</td><td>${pct(x.guestFeePct)}${x.verified ? '' : ' <span class="muted">(estimate)</span>'}</td><td>${money(x.perBookingFee)}</td></tr>`).join('')}
      </tbody></table></div>
      <p class="muted small">We never copy listings from other sites. Comparisons come from links owners add themselves and from links renters send us, and we re-check them regularly.</p>
    </div>`;
  bindBack(view);
}
