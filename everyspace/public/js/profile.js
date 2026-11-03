// Profile (switch demo user, hosting/traveling), the plan, and the catalog of what can be rented.
import { $$, api, esc, state, term, icon, avatar, topbar, bindBack, go, toast } from './core.js';

export async function renderProfile(view) {
  const me = state.me;
  const hosting = state.mode === 'host';
  view.innerHTML = `${topbar('Profile', { back: false })}
    <div class="page narrow">
      <div class="profile-head">${avatar(me, 72)}<div><h1>${esc(me.name)}</h1><div class="muted">${esc(me.tagline)}</div>
        <div class="muted small">Member since ${esc(me.joined)}</div></div></div>
      <button class="btn wide" id="switch-mode">${hosting ? '🧳 Switch to renting' : '🏡 Switch to hosting'}</button>

      <h2 class="section-title">Try it as someone else <span class="muted small">(demo)</span></h2>
      <div class="people">${state.users.map((u) => `<button class="person ${u.id === state.user ? 'on' : ''}" data-user="${u.id}">${avatar(u, 40)}
        <span><strong>${esc(u.name)}</strong><span class="muted small">${esc(u.tagline)}</span></span></button>`).join('')}</div>

      <h2 class="section-title">About everyspace</h2>
      <div class="menu">
        <a href="#/plan">📄 <span>The plan</span>${icon.chevron}</a>
        <a href="#/catalog">🧭 <span>Everything you can rent out</span>${icon.chevron}</a>
        <button id="install" hidden>📲 <span>Install the app</span>${icon.chevron}</button>
        <button id="reset">↺ <span>Reset demo data</span>${icon.chevron}</button>
      </div>
      <p class="muted small fine">Prototype. Payments, ID checks and insurance are simulated.</p>
    </div>`;

  $$('#switch-mode', view)[0].onclick = () => { state.setMode(hosting ? 'guest' : 'host'); go(hosting ? '#/explore' : '#/host'); };
  for (const b of $$('[data-user]', view)) b.onclick = () => {
    state.setUser(b.dataset.user);
    const hostish = /^Host/.test(state.me.tagline);
    state.setMode(hostish ? 'host' : 'guest');
    toast(`Now using everyspace as ${state.me.name}`);
    go(state.mode === 'host' ? '#/host' : '#/explore');
  };
  $$('#reset', view)[0].onclick = async () => {
    if (!confirm('Reset all demo data? Bookings and listings you made will be removed.')) return;
    await api('reset', {});
    toast('Demo data reset');
    renderProfile(view);
  };
  const install = $$('#install', view)[0];
  if (window.deferredInstall) {
    install.hidden = false;
    install.onclick = async () => { window.deferredInstall.prompt(); window.deferredInstall = null; install.hidden = true; };
  }
}

export async function renderPlan(view) {
  view.innerHTML = `${topbar('The plan')}<article class="page narrow plan" id="plan-body"><div class="skeleton line"></div></article>`;
  bindBack(view);
  const { html } = await api('spec');
  $$('#plan-body', view)[0].innerHTML = html || '<p class="muted">The plan is in SPEC.md in the repository.</p>';
}

export function renderCatalog(view) {
  const c = state.catalog;
  const MODE = { instant: 'Instant book', request: 'Host approves', proposal: 'Proposal & contract' };
  view.innerHTML = `${topbar('What can I rent out?')}
    <div class="page">
      <p class="muted">Every kind of space, how long it can be rented for, and what a host confirms before listing it.</p>
      ${Object.entries(c.groups).filter(([g]) => g !== 'container').map(([g, label]) => `<h2 class="section-title">${c.groupIcons[g]} ${esc(label)}</h2>
        <div class="catalog-grid">${Object.entries(c.categories).filter(([, x]) => x.group === g).map(([, x]) => `<div class="card pad">
          <div class="row-between"><strong>${x.icon} ${esc(x.label)}</strong><span class="badge">${MODE[x.mode]}</span></div>
          <div class="term-tags">${x.terms.map((t) => `<span>${esc(term(t).label)}</span>`).join('')}</div>
          <ul>${x.checklist.map((i) => `<li>${esc(i)}</li>`).join('')}</ul></div>`).join('')}</div>`).join('')}
      <a class="btn wide" href="#/host/new" id="list-cta">List a space</a>
    </div>`;
  bindBack(view);
  $$('#list-cta', view)[0].onclick = () => state.setMode('host');
}
