// Drawn illustrations for every kind of space, so the prototype looks like an app without stock photos.
// Deterministic: the same space always gets the same palette.

const PALETTES = [
  { sky: ['#bfe1ff', '#eef7ff'], ground: '#9fcf8a', accent: '#e8835a', wall: '#f3e6d3', roof: '#b5523b' },
  { sky: ['#ffd9b8', '#fff4e8'], ground: '#a9c97d', accent: '#4f7fd6', wall: '#e9eef6', roof: '#3f5a7a' },
  { sky: ['#d6d0ff', '#f5f3ff'], ground: '#8fc39a', accent: '#d39b16', wall: '#fbf1e1', roof: '#6b4f9e' },
  { sky: ['#c3efe2', '#f0fbf7'], ground: '#8bbf7c', accent: '#c4547a', wall: '#f6e8e8', roof: '#2f6f4f' },
];

function hash(s) { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; }

const car = (x, y, color, s = 1) => `<g transform="translate(${x} ${y}) scale(${s})">
  <path d="M0 18 L6 6 Q8 2 13 2 L37 2 Q42 2 44 6 L50 18 Z" fill="${color}"/><rect x="-2" y="16" width="54" height="12" rx="4" fill="${color}"/>
  <path d="M10 7 L13 3.5 L24 3.5 L24 15 L7 15 Z M27 3.5 L37 3.5 L42 15 L27 15 Z" fill="#dff1ff" opacity=".9"/>
  <circle cx="10" cy="28" r="5" fill="#2b2b2b"/><circle cx="40" cy="28" r="5" fill="#2b2b2b"/></g>`;
const tree = (x, y, s = 1, c = '#4f9a5b') => `<g transform="translate(${x} ${y}) scale(${s})"><rect x="-3" y="0" width="6" height="22" fill="#7a5532"/>
  <circle cx="0" cy="-8" r="16" fill="${c}"/><circle cx="-10" cy="2" r="11" fill="${c}"/><circle cx="10" cy="1" r="12" fill="${c}"/></g>`;
const box = (x, y, w, h, c = '#c99a62') => `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}" stroke="#8a6338" stroke-width="1.5"/>
  <path d="M${x} ${y + h * 0.3} H${x + w}" stroke="#8a6338" stroke-width="1.5"/><rect x="${x + w * 0.4}" y="${y}" width="${w * 0.2}" height="${h * 0.3}" fill="#e8c999"/></g>`;
const house = (p, x = 95, w = 110, h = 70) => `<rect x="${x}" y="${150 - h}" width="${w}" height="${h}" fill="${p.wall}"/>
  <path d="M${x - 10} ${152 - h} L${x + w / 2} ${105 - h} L${x + w + 10} ${152 - h} Z" fill="${p.roof}"/>
  <rect x="${x + w / 2 - 11}" y="${150 - 38}" width="22" height="38" fill="${p.accent}"/>
  <rect x="${x + 12}" y="${150 - h + 18}" width="22" height="20" fill="#cfe9ff" stroke="#fff" stroke-width="3"/>
  <rect x="${x + w - 34}" y="${150 - h + 18}" width="22" height="20" fill="#cfe9ff" stroke="#fff" stroke-width="3"/>`;

const SCENES = {
  living: (p, c) => c === 'apartment_unit'
    ? `<rect x="80" y="30" width="140" height="125" fill="${p.wall}" stroke="${p.roof}" stroke-width="4"/>
       ${[0, 1, 2, 3].map((r) => [0, 1, 2, 3].map((k) => `<rect x="${94 + k * 32}" y="${42 + r * 26}" width="20" height="16" fill="${(r + k) % 3 ? '#cfe9ff' : '#ffe9a8'}"/>`).join('')).join('')}
       <rect x="138" y="128" width="24" height="27" fill="${p.accent}"/>${tree(60, 130, .8)}${tree(250, 132, .7)}`
    : c === 'private_room'
      ? `<rect x="0" y="0" width="300" height="200" fill="${p.wall}"/><rect x="0" y="150" width="300" height="50" fill="#d9c2a0"/>
         <rect x="190" y="35" width="70" height="60" fill="#cfe9ff" stroke="#fff" stroke-width="5"/>
         <rect x="40" y="110" width="150" height="45" rx="6" fill="${p.accent}"/><rect x="40" y="95" width="45" height="25" rx="8" fill="#fff"/>
         <rect x="30" y="80" width="12" height="80" fill="#8a6338"/><rect x="212" y="125" width="30" height="35" fill="#8a6338"/>`
      : c === 'film_location'
        ? `${house(p, 80, 140, 75)}<rect x="210" y="128" width="50" height="16" rx="3" fill="#333"/><circle cx="252" cy="122" r="12" fill="#444"/>
           <rect x="226" y="144" width="4" height="12" fill="#333"/>${tree(45, 128, .8)}`
        : `${house(p, c === 'adu' ? 115 : 90, c === 'adu' ? 75 : 120, c === 'adu' ? 55 : 72)}${tree(50, 128, .9)}${tree(255, 130, .75)}`,
  outdoor: (p, c) => ({
    pool: `<rect x="40" y="110" width="220" height="60" rx="14" fill="#5fc3e8"/>
      ${[0, 1, 2].map((i) => `<path d="M${60 + i * 60} ${135 + (i % 2) * 8} q12 -8 24 0 t24 0" stroke="#fff" stroke-width="3" fill="none" opacity=".8"/>`).join('')}
      <path d="M210 98 L250 98 L262 80" stroke="${p.accent}" stroke-width="6" fill="none" stroke-linecap="round"/>${tree(40, 92, .7)}
      <circle cx="80" cy="52" r="16" fill="#ffd25e"/>`,
    yard_campsite: `<path d="M0 150 Q80 95 160 140 T300 120 V200 H0 Z" fill="${p.ground}"/><path d="M110 150 L150 85 L190 150 Z" fill="${p.accent}"/>
      <path d="M150 85 L150 150 M140 150 L150 120 L160 150" stroke="#fff" stroke-width="3" fill="none"/>
      <circle cx="235" cy="50" r="14" fill="#fff6c8"/><circle cx="80" cy="152" r="6" fill="#f7a23b"/>${tree(40, 120, .7, '#3d7d4a')}`,
    workspace: `<rect x="0" y="0" width="300" height="200" fill="${p.wall}"/><rect x="40" y="30" width="220" height="70" fill="#c9a77c"/>
      ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => `<circle cx="${55 + i * 21}" cy="45" r="2" fill="#7a5532"/>`).join('')}
      <path d="M70 55 v28 M100 55 l10 25 M140 52 v30 M180 56 h22 v18" stroke="#555" stroke-width="5" stroke-linecap="round"/>
      <rect x="30" y="125" width="240" height="14" fill="#8a6338"/><rect x="40" y="139" width="10" height="50" fill="#8a6338"/><rect x="250" y="139" width="10" height="50" fill="#8a6338"/>
      <circle cx="150" cy="118" r="14" fill="#bbb"/><rect x="120" y="116" width="60" height="9" fill="${p.accent}"/>`,
    film_location: SCENES.living(p, 'film_location'),
    backyard: `<path d="M0 105 h300" stroke="#c9a77c" stroke-width="3"/>${Array.from({ length: 16 }, (_, i) => `<rect x="${i * 19 + 3}" y="88" width="10" height="34" fill="#e8d5b7"/>`).join('')}
      <path d="M20 40 Q150 85 280 40" stroke="#555" stroke-width="1.5" fill="none"/>${Array.from({ length: 9 }, (_, i) => { const x = 35 + i * 29; const y = 40 + Math.sin((i / 8) * Math.PI) * 22; return `<circle cx="${x}" cy="${y}" r="4.5" fill="#ffd25e"/>`; }).join('')}
      ${tree(250, 120, .9)}<ellipse cx="130" cy="160" rx="26" ry="8" fill="#6b6b6b"/><path d="M118 156 q12 -30 24 0" fill="#f7a23b"/>`,
  })[c] ?? '',
  parking: (p, c, s) => {
    const asphalt = '<path d="M60 200 L110 95 H190 L240 200 Z" fill="#8d9096"/><path d="M150 100 V200" stroke="#f2f2f2" stroke-width="4" stroke-dasharray="14 10"/>';
    if (c === 'rv_parking') return `<rect x="0" y="120" width="300" height="80" fill="#c7b89a"/><g transform="translate(55 70)"><rect width="170" height="72" rx="10" fill="#f4f1ea" stroke="#999"/>
      <rect x="130" y="12" width="32" height="26" rx="4" fill="#cfe9ff"/><rect x="20" y="16" width="60" height="16" fill="#cfe9ff"/><rect x="0" y="44" width="170" height="8" fill="${p.accent}"/>
      <circle cx="40" cy="74" r="12" fill="#2b2b2b"/><circle cx="135" cy="74" r="12" fill="#2b2b2b"/></g>${tree(260, 118, .7)}`;
    if (c === 'ev_charging') return `${asphalt}${car(118, 128, p.accent, 1.2)}<rect x="210" y="85" width="26" height="70" rx="5" fill="#2f6f4f"/>
      <path d="M226 98 l-8 14 h8 l-6 14" stroke="#ffd25e" stroke-width="3.5" fill="none"/><path d="M210 120 q-25 5 -35 22" stroke="#222" stroke-width="3" fill="none"/>`;
    const n = Math.min(3, s?.quantity ?? 1);
    const cars = [car(78, 140, p.accent), car(124, 104, '#5b8bd9', .9), car(178, 140, '#e2b33b')].slice(0, n).join('');
    return `${house(p, 175, 110, 60)}<path d="M20 200 L80 92 H190 L260 200 Z" fill="#9a9da3"/>${cars}`;
  },
  storage: (p, c) => c === 'attic_storage'
    ? `<path d="M20 180 L150 40 L280 180 Z" fill="#d9bf98"/><path d="M150 40 V180" stroke="#b89a70" stroke-width="5"/><circle cx="150" cy="80" r="12" fill="#cfe9ff" stroke="#fff" stroke-width="3"/>
       ${box(70, 140, 40, 34)}${box(112, 148, 32, 26)}${box(170, 136, 44, 38)}${box(90, 110, 30, 30, '#d8b27c')}`
    : c === 'basement_storage'
      ? `<rect x="0" y="0" width="300" height="200" fill="#d9dde3"/>${[0, 1].map((r) => `<rect x="40" y="${70 + r * 60}" width="220" height="7" fill="#7d8592"/>`).join('')}
         ${box(55, 38, 50, 32)}${box(115, 44, 40, 26)}${box(175, 34, 60, 36)}${box(60, 98, 40, 32)}${box(110, 102, 55, 28)}${box(190, 96, 45, 34)}
         <rect x="38" y="30" width="6" height="150" fill="#7d8592"/><rect x="256" y="30" width="6" height="150" fill="#7d8592"/>`
      : `<rect x="50" y="55" width="200" height="110" fill="${p.wall}"/><path d="M40 60 L150 20 L260 60 Z" fill="${p.roof}"/>
         <rect x="70" y="75" width="160" height="90" fill="#6d6f73"/>${[0, 1, 2, 3, 4].map((i) => `<path d="M70 ${82 + i * 9} H230" stroke="#8a8c90" stroke-width="2"/>`).join('')}
         ${box(85, 120, 40, 45)}${box(130, 132, 34, 33)}${box(170, 115, 46, 50)}${box(95, 92, 28, 28, '#d8b27c')}`,
  land: (p, c) => c === 'beehive_site'
    ? `${tree(70, 120, 1, '#5aa05f')}<circle cx="60" cy="100" r="5" fill="#f7a23b"/><circle cx="82" cy="108" r="5" fill="#f7a23b"/>
       ${[0, 1, 2].map((i) => `<rect x="150" y="${140 - i * 24}" width="70" height="22" fill="${i === 2 ? p.accent : '#f2d27a'}" stroke="#b08a2e" stroke-width="2"/>`).join('')}
       <rect x="144" y="68" width="82" height="8" fill="#b08a2e"/>${[0, 1, 2, 3].map((i) => `<circle cx="${120 + i * 40}" cy="${50 + (i % 2) * 15}" r="3.5" fill="#333"/>`).join('')}`
    : `<rect x="0" y="105" width="300" height="95" fill="#8a6644"/>${[0, 1, 2, 3].map((r) => `<path d="M0 ${118 + r * 22} H300" stroke="#6f5034" stroke-width="5"/>
       ${Array.from({ length: 9 }, (_, i) => `<g transform="translate(${18 + i * 33 + (r % 2) * 14} ${114 + r * 22})"><path d="M0 0 q-8 -10 -2 -16 M0 0 q8 -10 2 -18" stroke="#4f9a5b" stroke-width="4" fill="none"/></g>`).join('')}`).join('')}
       <rect x="230" y="70" width="40" height="35" fill="${p.accent}"/>`,
  energy: (p, c) => ({
    rooftop_solar: `<circle cx="60" cy="45" r="20" fill="#ffd25e"/><rect x="70" y="120" width="170" height="60" fill="${p.wall}"/><path d="M50 125 L155 55 L260 125 Z" fill="${p.roof}"/>
      ${Array.from({ length: 3 }, (_, r) => Array.from({ length: 5 }, (_, k) => `<path d="M${112 + k * 18 + r * 12} ${108 - r * 15} l16 0 l9 -12 l-16 0 z" fill="#1f3c66" stroke="#9cc4ff" stroke-width="1"/>`).join('')).join('')}`,
    battery_site: `${house(p, 40, 120, 72)}<rect x="185" y="95" width="60" height="62" rx="6" fill="#f1f1f1" stroke="#aaa" stroke-width="2"/>
      <path d="M218 108 l-12 20 h12 l-8 18" stroke="${p.accent}" stroke-width="5" fill="none"/><rect x="178" y="155" width="74" height="6" fill="#bbb"/>`,
    charger_site: `<rect x="0" y="150" width="300" height="50" fill="#8d9096"/><path d="M0 175 H300" stroke="#f2f2f2" stroke-width="4" stroke-dasharray="18 12"/>
      ${[0, 1, 2].map((i) => `<rect x="${70 + i * 60}" y="85" width="26" height="65" rx="5" fill="#2f6f4f"/><path d="M${86 + i * 60} 98 l-8 14 h8 l-6 14" stroke="#ffd25e" stroke-width="3.5" fill="none"/>`).join('')}
      <rect x="60" y="72" width="180" height="10" fill="#555"/>`,
    telecom_site: `<path d="M0 170 Q150 110 300 170 V200 H0 Z" fill="${p.ground}"/><path d="M150 30 L125 150 M150 30 L175 150 M132 115 L168 115 M137 85 L163 85 M142 58 L158 58" stroke="#666" stroke-width="4" fill="none"/>
      ${[1, 2, 3].map((i) => `<path d="M${150 - i * 18} ${30 - i * 6} q${i * 18} -${i * 12} ${i * 36} 0" stroke="${p.accent}" stroke-width="3" fill="none"/>`).join('')}`,
  })[c] ?? '',
  commercial: (p, c) => ({
    fleet_parking: `<rect x="0" y="120" width="300" height="80" fill="#a7a59c"/>${[0, 1, 2, 3].map((i) => `<path d="M${30 + i * 70} 200 L${45 + i * 70} 125" stroke="#f2f2f2" stroke-width="3"/>`).join('')}
      ${[0, 1, 2].map((i) => van(42 + i * 72, 112, i === 1 ? p.accent : '#f4f4f2')).join('')}
      <rect x="268" y="40" width="5" height="110" fill="#555"/><path d="M262 40 h22" stroke="#555" stroke-width="5"/><ellipse cx="282" cy="46" rx="9" ry="4" fill="#ffe9a8"/>`,
    signage: `<rect x="0" y="165" width="300" height="35" fill="#8d9096"/><path d="M0 182 H300" stroke="#f2f2f2" stroke-width="3" stroke-dasharray="16 12"/>
      <rect x="132" y="92" width="8" height="74" fill="#6b6b6b"/><rect x="170" y="92" width="8" height="74" fill="#6b6b6b"/>
      <rect x="70" y="28" width="170" height="70" rx="4" fill="#fff" stroke="#444" stroke-width="4"/><rect x="78" y="36" width="154" height="54" fill="${p.accent}" opacity=".9"/>
      <rect x="92" y="50" width="70" height="9" rx="4" fill="#fff"/><rect x="92" y="66" width="110" height="7" rx="3" fill="#fff" opacity=".8"/>${tree(40, 140, .7)}${tree(270, 142, .6)}`,
    parcel_locker: `<rect x="0" y="0" width="300" height="200" fill="${p.wall}"/><rect x="0" y="160" width="300" height="40" fill="#cfc7b8"/>
      <rect x="60" y="34" width="180" height="128" rx="6" fill="${p.accent}"/>
      ${Array.from({ length: 4 }, (_, r) => Array.from({ length: 5 }, (_, k) => (k === 2 && r < 2) ? '' : `<rect x="${70 + k * 33}" y="${44 + r * 29}" width="28" height="24" rx="2" fill="#fff" opacity=".88"/><circle cx="${93 + k * 33}" cy="${56 + r * 29}" r="1.8" fill="#888"/>`).join('')).join('')}
      <rect x="136" y="46" width="28" height="48" rx="3" fill="#1d2a3a"/><rect x="140" y="50" width="20" height="16" fill="#7fd1ff"/>`,
  })[c] ?? '',
  container: (p) => `<rect x="70" y="40" width="160" height="120" fill="${p.wall}"/>`,
};

const van = (x, y, color) => `<g transform="translate(${x} ${y})"><rect x="0" y="0" width="58" height="34" rx="5" fill="${color}" stroke="#777" stroke-width="1.5"/>
  <path d="M58 10 h10 l8 12 v12 h-18 z" fill="${color}" stroke="#777" stroke-width="1.5"/><path d="M60 13 h7 l5 8 h-12 z" fill="#cfe9ff"/>
  <circle cx="14" cy="36" r="6" fill="#2b2b2b"/><circle cx="62" cy="36" r="6" fill="#2b2b2b"/></g>`;

// Extra scenes for newer categories, merged into their groups.
const EXTRA = {
  kitchen: (p) => `<rect x="0" y="0" width="300" height="200" fill="${p.wall}"/>
    ${Array.from({ length: 6 }, (_, r) => Array.from({ length: 15 }, (_, k) => `<rect x="${k * 20 + (r % 2) * 10}" y="${70 + r * 10}" width="19" height="9" fill="#fff" opacity=".55"/>`).join('')).join('')}
    <rect x="0" y="128" width="300" height="12" fill="#d9c9b0"/><rect x="0" y="140" width="300" height="60" fill="#8a6338"/>
    <rect x="170" y="140" width="80" height="60" fill="#3a3a3a"/><rect x="180" y="152" width="60" height="30" rx="3" fill="#ffb066" opacity=".85"/>
    <path d="M40 20 v24 M110 20 v24" stroke="#555" stroke-width="2"/><path d="M28 44 h24 l-4 10 h-16z M98 44 h24 l-4 10 h-16z" fill="${p.accent}"/>
    <rect x="62" y="104" width="22" height="24" rx="4" fill="${p.accent}"/><circle cx="73" cy="102" r="8" fill="#ddd"/>`,
  sport_court: (p) => `<path d="M30 200 L80 100 H220 L270 200 Z" fill="#4c8f6a"/><path d="M50 196 L92 108 H208 L250 196 Z" fill="none" stroke="#fff" stroke-width="3"/>
    <path d="M150 108 V196 M71 152 H229" stroke="#fff" stroke-width="2.5"/><rect x="60" y="140" width="180" height="14" fill="none" stroke="#333" stroke-width="2"/>
    ${Array.from({ length: 12 }, (_, i) => `<path d="M${64 + i * 15} 140 v14" stroke="#333" stroke-width="1"/>`).join('')}
    <rect x="262" y="40" width="5" height="150" fill="#555"/><ellipse cx="258" cy="44" rx="12" ry="5" fill="#ffe9a8"/>${tree(28, 120, .7)}`,
  dock_slip: (p) => `<rect x="0" y="118" width="300" height="82" fill="#5aa8d8"/>
    ${[0, 1, 2, 3].map((i) => `<path d="M${10 + i * 70} ${150 + (i % 2) * 12} q15 -6 30 0" stroke="#fff" stroke-width="2" fill="none" opacity=".7"/>`).join('')}
    <rect x="150" y="110" width="150" height="14" fill="#a0784b"/>${[0, 1, 2, 3, 4].map((i) => `<rect x="${156 + i * 30}" y="110" width="6" height="40" fill="#7a5532"/>`).join('')}
    <path d="M40 140 h90 l-14 22 h-62 z" fill="#fff" stroke="#999"/><rect x="66" y="122" width="34" height="18" rx="3" fill="${p.accent}"/><path d="M84 70 v52" stroke="#777" stroke-width="3"/><path d="M86 74 l30 40 h-30 z" fill="#fff"/>
    <path d="M0 118 Q60 96 120 112" fill="${p.ground}"/>`,
  pasture: (p) => `<path d="M0 130 Q90 95 180 125 T300 115 V200 H0 Z" fill="#8ec27a"/>
    <rect x="200" y="78" width="60" height="44" fill="#b5523b"/><path d="M194 80 L230 56 L266 80 Z" fill="#7d3426"/><rect x="222" y="98" width="16" height="24" fill="#f3e6d3"/>
    ${Array.from({ length: 9 }, (_, i) => `<rect x="${10 + i * 34}" y="150" width="5" height="34" fill="#8a6338"/>`).join('')}<path d="M10 158 H300 M10 172 H300" stroke="#8a6338" stroke-width="4"/>
    <g transform="translate(70 112)" fill="#6b4226"><ellipse cx="30" cy="20" rx="30" ry="13"/><path d="M50 14 l18 -18 l8 4 l-12 22 z"/><rect x="6" y="28" width="6" height="22"/><rect x="16" y="28" width="6" height="22"/><rect x="40" y="28" width="6" height="22"/><rect x="50" y="28" width="6" height="22"/><path d="M0 16 q-12 8 -6 22" stroke="#4a2c18" stroke-width="5" fill="none"/></g>`,
};
const EXTRA_PALETTES = [
  { sky: ['#ffc6a8', '#ffeede'], ground: '#9dc584', accent: '#d9603b', wall: '#fbeee0', roof: '#8a3d2a' },
  { sky: ['#a9d4f5', '#e9f5ff'], ground: '#94c98f', accent: '#2f6fb3', wall: '#f1efe9', roof: '#4a4a6a' },
];
const ALL_PALETTES = [...PALETTES, ...EXTRA_PALETTES];
const INTERIOR = new Set(['private_room', 'workspace', 'kitchen', 'basement_storage', 'parcel_locker']);

function sky(h, p) {
  const cloud = (x, y, s) => `<g transform="translate(${x} ${y}) scale(${s})" fill="#fff" opacity=".85"><ellipse cx="0" cy="0" rx="18" ry="9"/><ellipse cx="14" cy="-5" rx="14" ry="10"/><ellipse cx="28" cy="1" rx="14" ry="8"/></g>`;
  const sunX = 30 + (h % 240);
  return `${h % 3 ? `<circle cx="${sunX}" cy="${28 + (h % 20)}" r="16" fill="#fff4c2" opacity=".9"/>` : ''}
    ${cloud(20 + (h % 90), 30 + (h % 25), 0.8)}${cloud(170 + (h % 80), 18 + (h % 30), 0.6)}`;
}

export function art(space, { className = 'art' } = {}) {
  const c = space.category;
  const group = window.everyspaceCatalog?.categories?.[c]?.group ?? 'living';
  const h = hash(space.id ?? c);
  const p = ALL_PALETTES[h % ALL_PALETTES.length];
  const id = `sky${h}`;
  const scene = EXTRA[c]?.(p) || SCENES[group]?.(p, c, space) || SCENES.living(p, 'entire_home');
  const outside = !INTERIOR.has(c);
  return `<svg class="${className}" viewBox="0 0 300 200" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${(space.title ?? '').replace(/"/g, '')}">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.sky[0]}"/><stop offset="1" stop-color="${p.sky[1]}"/></linearGradient>
      <linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.ground}"/><stop offset="1" stop-color="${p.ground}" stop-opacity=".75"/></linearGradient></defs>
    <rect width="300" height="200" fill="url(#${id})"/>${outside ? sky(h, p) : ''}<rect y="150" width="300" height="50" fill="url(#g${id})"/>
    ${outside ? '<ellipse cx="150" cy="156" rx="120" ry="6" fill="#000" opacity=".06"/>' : ''}${scene}</svg>`;
}
