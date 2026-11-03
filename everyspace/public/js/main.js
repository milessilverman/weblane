// App shell: boot, hash router, bottom navigation for the three sides (renting, hosting, business).
import { $, api, state, icon, go, bindSaves } from './core.js';
import { renderExplore } from './explore.js';
import { renderSpace } from './space.js';
import { renderBook } from './book.js';
import { renderTrips, renderTrip } from './trips.js';
import { renderInbox, renderChat } from './inbox.js';
import { renderHostToday, renderHostListings, renderHostEarnings } from './host.js';
import { renderWizard } from './wizard.js';
import { renderProfile, renderPlan, renderCatalog } from './profile.js';
import { renderBizHome, renderPipeline } from './biz.js';
import { renderEarn, renderSaved } from './earn.js';

// [pattern, render, meta]. meta.mode switches the app into that side; meta.nav shows the tab bar.
const ROUTES = [
  [/^\/?$/, null, { redirect: true }],
  [/^\/explore$/, renderExplore, { nav: true, mode: 'guest' }],
  [/^\/saved$/, renderSaved, { nav: true, mode: 'guest' }],
  [/^\/space\/([\w-]+)$/, renderSpace, {}],
  [/^\/book\/(pkg)\/([\w-]+)$/, renderBook, {}],
  [/^\/book\/([\w-]+)$/, renderBook, {}],
  [/^\/trips$/, renderTrips, { nav: true, mode: 'guest' }],
  [/^\/trip\/([\w-]+)$/, renderTrip, {}],
  [/^\/inbox$/, renderInbox, { nav: true }],
  [/^\/chat\/([\w-]+)$/, renderChat, { chat: true }],
  [/^\/host$/, renderHostToday, { nav: true, mode: 'host' }],
  [/^\/host\/listings$/, renderHostListings, { nav: true, mode: 'host' }],
  [/^\/host\/earnings$/, renderHostEarnings, { nav: true, mode: 'host' }],
  [/^\/host\/new$/, renderWizard, { mode: 'host' }],
  [/^\/biz$/, renderBizHome, { nav: 'business', mode: 'business' }],
  [/^\/biz\/pipeline$/, renderPipeline, { nav: true, mode: 'business' }],
  [/^\/earn$/, renderEarn, {}],
  [/^\/profile$/, renderProfile, { nav: true }],
  [/^\/plan$/, renderPlan, {}],
  [/^\/catalog$/, renderCatalog, {}],
];

const NAV = {
  guest: [['#/explore', 'Explore', icon.explore], ['#/saved', 'Saved', icon.heart], ['#/trips', 'Trips', icon.trips], ['#/inbox', 'Inbox', icon.inbox], ['#/profile', 'Profile', icon.user]],
  host: [['#/host', 'Today', icon.today], ['#/host/listings', 'Listings', icon.listings], ['#/inbox', 'Inbox', icon.inbox], ['#/host/earnings', 'Earnings', icon.earnings], ['#/profile', 'Profile', icon.user]],
  business: [['#/biz', 'Sites', icon.briefcase], ['#/biz/pipeline', 'Pipeline', icon.pipeline], ['#/inbox', 'Inbox', icon.inbox], ['#/profile', 'Profile', icon.user]],
};

const home = () => (state.mode === 'host' ? '#/host' : state.mode === 'business' ? '#/biz' : '#/explore');

async function route() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, qs] = raw.split('?');
  const found = ROUTES.find(([re]) => re.test(path));
  if (!found || found[2].redirect) { go(home()); return; }
  const [re, render, meta] = found;
  const isBiz = state.me.kind === 'business';

  // Companies only use the business side; people never enter it (they see a landing page instead).
  if (isBiz && (meta.mode === 'guest' || meta.mode === 'host')) { go('#/biz'); return; }
  let nav = meta.nav;
  if (meta.mode === 'business' && !isBiz) {
    if (path !== '/biz') { go('#/biz'); return; }
    nav = false; // landing page for people
  } else if (meta.mode && meta.mode !== state.mode) state.setMode(meta.mode);
  if (isBiz && state.mode !== 'business') state.setMode('business');

  const view = $('#view');
  view.className = `view ${nav ? 'with-nav' : ''} ${meta.chat ? 'chat-view' : ''} enter`;
  document.body.dataset.mode = state.mode;
  drawNav(nav ? `#${path}` : null);
  try {
    await render(view, path.match(re).slice(1), new URLSearchParams(qs));
  } catch (e) {
    console.error(e);
    view.innerHTML = `<div class="page"><div class="error">Something went wrong: ${e.message}</div><a class="btn" href="#/">Home</a></div>`;
  }
  window.scrollTo(0, 0);
  requestAnimationFrame(() => view.classList.remove('enter'));
}

function drawNav(active) {
  const nav = $('#nav');
  if (!active) { nav.hidden = true; return; }
  nav.hidden = false;
  nav.innerHTML = NAV[state.mode].map(([href, label, svg]) => `<a href="${href}" class="${href === active ? 'on' : ''}" ${href === active ? 'aria-current="page"' : ''}>${svg}<span>${label}</span></a>`).join('');
}

async function boot() {
  [state.catalog, state.users] = await Promise.all([api('catalog'), api('users')]);
  window.everyspaceCatalog = state.catalog;
  if (!state.users.some((u) => u.id === state.user)) state.setUser('u_sam');
  bindSaves();
  window.addEventListener('hashchange', route);
  await route();
  document.body.classList.add('ready');
}

window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); window.deferredInstall = e; });
if ('serviceWorker' in navigator && location.protocol.startsWith('http') && !window.everyspaceApi) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

boot();
