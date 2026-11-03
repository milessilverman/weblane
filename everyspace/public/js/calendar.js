// Month calendar showing free units per day. Modes: 'view', 'single' (pick a day), 'range' (pick start + end).
import { $$, api, today } from './core.js';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export function calendarPicker(el, { spaceId, mode = 'view', start = '', end = '', onChange = () => {} }) {
  let anchor = (start || today()).slice(0, 7); // YYYY-MM shown first
  let sel = { start: start.slice(0, 10), end: end.slice(0, 10) };

  async function draw() {
    const first = `${anchor}-01`;
    const days = await api(`spaces/${spaceId}/calendar?from=${first}&days=62`);
    const byDate = Object.fromEntries(days.map((d) => [d.date, d]));
    const t = today();
    const month = (ym) => {
      const [y, m] = ym.split('-').map(Number);
      const lead = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
      const count = new Date(Date.UTC(y, m, 0)).getUTCDate();
      const cells = Array(lead).fill('<span></span>');
      for (let d = 1; d <= count; d++) {
        const date = `${ym}-${String(d).padStart(2, '0')}`;
        const info = byDate[date];
        const past = date < t;
        const full = info && info.free === 0;
        const partial = info && info.free > 0 && info.free < info.total;
        const inRange = sel.start && sel.end && date > sel.start && date < sel.end;
        const cls = [past && 'past', full && 'full', partial && 'partial', (date === sel.start || date === sel.end) && 'sel', inRange && 'range'].filter(Boolean).join(' ');
        cells.push(`<button type="button" class="day ${cls}" data-date="${date}" ${past || mode === 'view' ? 'disabled' : ''}
          title="${info ? `${info.free} of ${info.total} free` : ''}">${d}</button>`);
      }
      return `<div class="cal-month"><div class="cal-title">${MONTHS[m - 1]} ${y}</div>
        <div class="cal-grid">${['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((x) => `<span class="dow">${x}</span>`).join('')}${cells.join('')}</div></div>`;
    };
    const next = nextMonth(anchor);
    el.innerHTML = `<div class="cal">
      <div class="cal-nav"><button type="button" class="icon-btn" data-nav="-1" ${anchor <= t.slice(0, 7) ? 'disabled' : ''} aria-label="Previous month">‹</button>
      <button type="button" class="icon-btn" data-nav="1" aria-label="Next month">›</button></div>
      <div class="cal-months">${month(anchor)}${month(next)}</div>
      <div class="cal-legend"><span><i class="free"></i>Open</span><span><i class="partial"></i>Some units left</span><span><i class="full"></i>Booked</span></div></div>`;
    for (const b of $$('[data-nav]', el)) b.onclick = () => { anchor = b.dataset.nav === '1' ? next : prevMonth(anchor); draw(); };
    for (const b of $$('.day[data-date]', el)) b.onclick = () => pick(b.dataset.date);
  }

  function pick(date) {
    if (mode === 'single') sel = { start: date, end: '' };
    else if (!sel.start || sel.end || date <= sel.start) sel = { start: date, end: '' };
    else sel = { start: sel.start, end: date };
    onChange({ ...sel });
    draw();
  }

  draw();
  return { set(s, e) { sel = { start: s, end: e }; draw(); } };
}

function nextMonth(ym) { const [y, m] = ym.split('-').map(Number); return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`; }
function prevMonth(ym) { const [y, m] = ym.split('-').map(Number); return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`; }
export const nights = (s, e) => Math.round((Date.parse(e) - Date.parse(s)) / 864e5);
