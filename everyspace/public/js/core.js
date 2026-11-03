// Shared helpers: API access, app state, formatting, icons, sheets and toasts.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const money = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 })}`;

export async function api(path, body) {
  if (window.everyspaceApi) return window.everyspaceApi(path, body); // single-file build: API runs in the page
  const res = await fetch(`/api/${path}`, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
  const data = await res.json();
  if (!res.ok) { const e = new Error(data.error); e.details = data.details; throw e; }
  return data;
}

const store = {
  get(k, d) { try { const v = localStorage.getItem(`everyspace:${k}`); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(`everyspace:${k}`, JSON.stringify(v)); } catch { /* private mode */ } },
};

export const state = {
  catalog: null,
  users: [],
  user: store.get('user', 'u_sam'),
  mode: store.get('mode', 'guest'), // 'guest' | 'host'
  filters: { group: '', category: '', term: '', start: '', end: '', q: '' },
  view: 'list',
  get me() { return this.users.find((u) => u.id === this.user) ?? this.users[0]; },
  setUser(id) { this.user = id; store.set('user', id); },
  setMode(m) { this.mode = m; store.set('mode', m); },
};

export const cat = (key) => state.catalog.categories[key];
export const term = (key) => state.catalog.terms[key];
export const TERM_ORDER = ['hourly', 'daily', 'weekly', 'monthly', 'lease', 'infrastructure'];
export const TERM_SHORT = { hourly: 'Hourly', daily: 'Nightly', weekly: 'Weekly', monthly: 'Monthly', lease: 'Lease', infrastructure: 'Long-term deal' };

export function cheapestRate(s) {
  const t = TERM_ORDER.find((k) => s.rates?.[k] != null) ?? TERM_ORDER.find((k) => s.addonRates?.[k] != null);
  return t ? { term: t, amount: s.rates?.[t] ?? s.addonRates[t], unit: term(t).unit } : null;
}
export const priceTag = (r) => (r ? `${money(r.amount)}<span>/${r.unit === 'day' ? 'night' : r.unit}</span>` : '');

// ---------- dates (UTC, YYYY-MM-DD) ----------
export const today = () => new Date().toISOString().slice(0, 10);
export const addDays = (d, n) => { const t = new Date(`${d}T00:00:00Z`); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };
export function addMonths(d, n) {
  const t = new Date(`${d}T00:00:00Z`);
  const day = t.getUTCDate();
  t.setUTCDate(1); t.setUTCMonth(t.getUTCMonth() + n);
  const last = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
  t.setUTCDate(Math.min(day, last));
  return t.toISOString().slice(0, 10);
}
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function fmtDate(iso, { year = false } = {}) {
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso);
  return `${MON[d.getUTCMonth()]} ${d.getUTCDate()}${year ? `, ${d.getUTCFullYear()}` : ''}`;
}
export function fmtTime(iso) {
  const d = new Date(iso); const h = d.getUTCHours(); const m = d.getUTCMinutes();
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, '0')}` : ''}${h < 12 ? 'am' : 'pm'}`;
}
export function fmtRange(b) {
  if (b.term === 'hourly') return `${fmtDate(b.start)}, ${fmtTime(b.start)}–${fmtTime(b.end)}`;
  const crossYear = b.start.slice(0, 4) !== b.end.slice(0, 4);
  return `${fmtDate(b.start, { year: crossYear })} → ${fmtDate(b.end, { year: true })}`;
}
export function ago(iso) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 60) return 'now';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`;
  return fmtDate(iso);
}

// ---------- small components ----------
export const avatar = (u, size = 36) => `<span class="avatar" style="--size:${size}px;background:${esc(u?.color ?? '#888')}">${esc((u?.name ?? '?')[0])}</span>`;
export const stars = (r) => (r?.count ? `<span class="stars">★ ${r.avg.toFixed(1)} <span class="muted">(${r.count})</span></span>` : '<span class="stars new">New</span>');

const STATUS = {
  pending: ['Awaiting host', 'warn'], proposed: ['Proposal sent', 'warn'], site_assessment: ['Site assessment', 'warn'],
  contract: ['Contract out', 'warn'], confirmed: ['Confirmed', 'ok'], active: ['Happening now', 'ok'],
  completed: ['Completed', ''], declined: ['Declined', 'bad'], cancelled: ['Cancelled', 'bad'],
};
export const statusPill = (s) => `<span class="pill ${STATUS[s]?.[1] ?? ''}">${STATUS[s]?.[0] ?? esc(s)}</span>`;

export const errorBox = (e) => `<div class="error">${esc(e.message)}${e.details?.length ? `<ul>${e.details.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>` : ''}</div>`;

export const icon = {
  back: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>',
  explore: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/></svg>',
  trips: '<svg viewBox="0 0 24 24"><rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M9 7.5V5.5a1.5 1.5 0 011.5-1.5h3A1.5 1.5 0 0115 5.5v2"/></svg>',
  inbox: '<svg viewBox="0 0 24 24"><path d="M4 5.5h16v10H9l-5 4z"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c1-4 4-6 7-6s6 2 7 6"/></svg>',
  today: '<svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>',
  listings: '<svg viewBox="0 0 24 24"><path d="M4 11l8-6 8 6v8.5H4z"/><path d="M10 19.5v-5h4v5"/></svg>',
  earnings: '<svg viewBox="0 0 24 24"><path d="M5 19V11M10 19V6M15 19v-5M20 19V9"/></svg>',
  map: '<svg viewBox="0 0 24 24"><path d="M9 4.5l-5 2v13l5-2 6 2 5-2v-13l-5 2z"/><path d="M9 4.5v13M15 6.5v13"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01"/></svg>',
  lock: '<svg viewBox="0 0 24 24"><rect x="5" y="10.5" width="14" height="9.5" rx="2"/><path d="M8 10.5V8a4 4 0 018 0v2.5"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M4 12l16-7-6 16-2.5-6.5z"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  calendar: '<svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16"/></svg>',
  chevron: '<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
};

export function topbar(title, { back = true, right = '' } = {}) {
  return `<header class="topbar">${back ? `<button class="icon-btn" data-back aria-label="Back">${icon.back}</button>` : '<span></span>'}
    <h1>${esc(title)}</h1><div class="topbar-right">${right}</div></header>`;
}

export function bindBack(root) {
  for (const b of $$('[data-back]', root)) b.onclick = () => (history.length > 1 ? history.back() : go('#/'));
}

export const go = (hash) => { location.hash = hash; };

let toastTimer;
export function toast(text) {
  const el = $('#toast');
  el.textContent = text;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}

// Bottom sheet. Returns the sheet body element; close with closeSheet().
export function openSheet(html, { title = '' } = {}) {
  const wrap = $('#sheet');
  wrap.innerHTML = `<div class="sheet-backdrop" data-close></div><div class="sheet" role="dialog" aria-modal="true">
    <div class="sheet-head"><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Close">${icon.close}</button></div>
    <div class="sheet-body">${html}</div></div>`;
  wrap.hidden = false;
  requestAnimationFrame(() => wrap.classList.add('open'));
  for (const c of $$('[data-close]', wrap)) c.onclick = closeSheet;
  return $('.sheet-body', wrap);
}
export function closeSheet() {
  const wrap = $('#sheet');
  wrap.classList.remove('open');
  setTimeout(() => { wrap.hidden = true; wrap.innerHTML = ''; }, 200);
}

export function stepper(name, value, { min = 0, max = 99 } = {}) {
  return `<div class="stepper" data-stepper="${esc(name)}" data-min="${min}" data-max="${max}">
    <button type="button" data-step="-1" aria-label="Fewer">−</button><output>${value}</output><button type="button" data-step="1" aria-label="More">+</button></div>`;
}
// Wire every stepper under root; onChange(name, value)
export function bindSteppers(root, onChange) {
  for (const s of $$('[data-stepper]', root)) {
    const out = $('output', s);
    const update = (v) => {
      const min = +s.dataset.min, max = +s.dataset.max;
      v = Math.max(min, Math.min(max, v));
      out.textContent = v;
      $('[data-step="-1"]', s).disabled = v <= min;
      $('[data-step="1"]', s).disabled = v >= max;
      return v;
    };
    update(+out.textContent);
    for (const b of $$('[data-step]', s)) b.onclick = () => onChange(s.dataset.stepper, update(+out.textContent + +b.dataset.step));
  }
}

export function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
