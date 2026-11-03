// Inbox: one conversation per booking. Hosts can approve or decline right from the chat.
import { $, $$, api, esc, state, icon, money, avatar, ago, fmtRange, topbar, bindBack, statusPill, errorBox, toast } from './core.js';
import { art } from './art.js';

export async function renderInbox(view) {
  const threads = await api(`threads?userId=${state.user}`);
  view.innerHTML = `${topbar('Inbox', { back: false })}
    <div class="page">${threads.length ? `<div class="threads">${threads.map((t) => `<a class="thread" href="#/chat/${t.bookingId}">
        ${avatar(t.other, 48)}<div class="thread-body"><div class="row-between"><strong>${esc(t.other?.name)}</strong><span class="muted small">${ago(t.last.at)}</span></div>
        <div class="muted small">${esc(t.space.title)} · ${statusPill(t.status)}</div>
        <div class="snippet">${t.last.from === 'system' ? '<span class="muted">●</span> ' : t.last.from === state.user ? 'You: ' : ''}${esc(t.last.text)}</div></div></a>`).join('')}</div>`
      : '<div class="empty"><div class="empty-icon">💬</div>Messages with hosts and renters show up here.</div>'}</div>`;
}

const NEXT_LABEL = { proposed: 'Accept & schedule site visit', site_assessment: 'Site passed: send contract', contract: 'Contract signed: confirm' };

export async function renderChat(view, [bookingId]) {
  const [msgs, bookings] = await Promise.all([api(`bookings/${bookingId}/messages?userId=${state.user}`), api(`bookings?userId=${state.user}`)]);
  const b = bookings.find((x) => x.id === bookingId);
  const isHost = b.role === 'host';
  const other = isHost ? b.renter : b.host;
  const actions = isHost && b.status === 'pending' ? [['approve', 'Approve'], ['decline', 'Decline']]
    : isHost && NEXT_LABEL[b.status] ? [['advance', NEXT_LABEL[b.status]], ['decline', 'Decline']] : [];

  view.innerHTML = `<header class="topbar chat-top"><button class="icon-btn" data-back aria-label="Back">${icon.back}</button>
      <a class="chat-who" href="#/trip/${b.id}">${avatar(other, 34)}<div><strong>${esc(other?.name)}</strong><div class="muted small">${esc(b.packageName ?? b.itemsLabel)}</div></div></a>
      <span></span></header>
    <a class="chat-booking" href="#/trip/${b.id}">${art(b.primary, { className: 'art mini' })}<div><div class="small">${fmtRange(b)}</div>
      <div class="muted small">${money(b.quote?.total ?? 0)} total</div></div>${statusPill(b.effective)}</a>
    ${actions.length ? `<div class="action-bar"><span>${b.status === 'pending' ? `${esc(b.renter.name)} is waiting for your answer` : 'Infrastructure proposal'}</span>
      <div>${actions.map(([a, l]) => `<button class="btn small ${a === 'decline' ? 'ghost' : ''}" data-act="${a}">${l}</button>`).join('')}</div></div>` : ''}
    <div class="chat" id="chat">${msgs.map((m) => bubble(m, b)).join('')}</div>
    <form class="composer" id="composer"><input id="text" placeholder="Message ${esc(other?.name)}…" autocomplete="off">
      <button class="icon-btn send" aria-label="Send">${icon.send}</button></form>`;
  bindBack(view);
  const chat = $('#chat');
  chat.scrollTop = chat.scrollHeight;
  requestAnimationFrame(() => window.scrollTo(0, document.body.scrollHeight));

  $('#composer').onsubmit = async (e) => {
    e.preventDefault();
    const text = $('#text').value.trim();
    if (!text) return;
    try {
      const m = await api(`bookings/${bookingId}/messages`, { from: state.user, text });
      $('#text').value = '';
      chat.insertAdjacentHTML('beforeend', bubble(m, b));
      window.scrollTo(0, document.body.scrollHeight);
    } catch (err) { toast(err.message); }
  };
  for (const btn of $$('[data-act]', view)) btn.onclick = async () => {
    if (btn.dataset.act === 'decline' && !confirm('Decline this request?')) return;
    try { await api(`bookings/${bookingId}/${btn.dataset.act}`, { actorId: state.user }); toast('Updated'); renderChat(view, [bookingId]); }
    catch (err) { chat.insertAdjacentHTML('beforeend', errorBox(err)); }
  };
}

function bubble(m, b) {
  if (m.from === 'system') return `<div class="bubble system">${esc(m.text)}</div>`;
  const mine = m.from === state.user;
  const who = m.from === b.renterId ? b.renter : b.host;
  return `<div class="bubble-row ${mine ? 'mine' : ''}">${mine ? '' : avatar(who, 28)}<div class="bubble">${esc(m.text)}<time>${ago(m.at)}</time></div></div>`;
}
