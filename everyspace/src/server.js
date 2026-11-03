// JSON API + static demo UI. Run: node src/server.js  (PORT, DB_FILE env vars optional)
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CATEGORIES, GROUPS, MODES, TERMS } from './catalog.js';
import { BookingError, createBooking, isAnchorFor, quote, transition } from './booking.js';
import { createPackage, createProperty, createSpace, search } from './listings.js';
import { describeAddon } from './describe.js';
import { openStore } from './store.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const PUBLIC = join(ROOT, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };

export function createApp(store) {
  const routes = [
    ['GET', /^\/api\/catalog$/, () => ({ terms: TERMS, groups: GROUPS, categories: CATEGORIES, modes: MODES })],
    ['GET', /^\/api\/users$/, () => store.db.users],
    ['GET', /^\/api\/search$/, (_m, _b, url) => search(store.db, Object.fromEntries(url.searchParams))],
    ['GET', /^\/api\/properties$/, (_m, _b, url) => {
      const hostId = url.searchParams.get('hostId');
      const db = store.db;
      return db.properties.filter((p) => !hostId || p.hostId === hostId).map((p) => ({
        ...p,
        spaces: db.spaces.filter((s) => s.propertyId === p.id).map((s) => ({ ...s, addonNote: describeAddon(db, s) })),
        packages: db.packages.filter((k) => k.propertyId === p.id),
      }));
    }],
    ['GET', /^\/api\/spaces\/([\w-]+)$/, ([, id]) => spaceDetail(store.db, id)],
    ['POST', /^\/api\/properties$/, (_m, body) => mutate(() => createProperty(store.db, body, store.newId))],
    ['POST', /^\/api\/spaces$/, (_m, body) => mutate(() => createSpace(store.db, body, store.newId))],
    ['POST', /^\/api\/packages$/, (_m, body) => mutate(() => createPackage(store.db, body, store.newId))],
    ['POST', /^\/api\/quote$/, (_m, body) => quote(store.db, body)],
    ['POST', /^\/api\/bookings$/, (_m, body) => mutate(() => createBooking(store.db, body, { newId: store.newId }))],
    ['GET', /^\/api\/bookings$/, (_m, _b, url) => listBookings(store.db, url.searchParams.get('userId'))],
    ['POST', /^\/api\/bookings\/([\w-]+)\/(approve|decline|advance|cancel)$/, ([, id, action], body) =>
      mutate(() => transition(store.db, id, action, body.actorId))],
    ['POST', /^\/api\/reset$/, () => { store.reset(); return { ok: true }; }],
  ];

  function mutate(fn) { const out = fn(); store.save(); return out; }

  return async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    try {
      if (url.pathname.startsWith('/api/')) {
        const route = routes.find(([m, re]) => m === req.method && re.test(url.pathname));
        if (!route) return send(res, 404, { error: 'Not found' });
        const body = req.method === 'POST' ? await readJson(req) : null;
        return send(res, 200, await route[2](url.pathname.match(route[1]), body, url));
      }
      return serveStatic(url.pathname, res);
    } catch (err) {
      const status = err instanceof BookingError || err instanceof SyntaxError || /required|not found|must|can't|Unknown|Invalid|Set at least|need/i.test(err.message) ? 400 : 500;
      if (status === 500) console.error(err);
      return send(res, status, { error: err.message, details: err.details ?? [] });
    }
  };
}

function spaceDetail(db, id) {
  const s = db.spaces.find((x) => x.id === id);
  if (!s) throw new BookingError('Space not found');
  return {
    ...s,
    category: s.category,
    categoryInfo: CATEGORIES[s.category],
    property: db.properties.find((p) => p.id === s.propertyId),
    addonNote: describeAddon(db, s),
    // Add-ons this space can carry (e.g. parking/lockers for an apartment)
    addons: db.spaces.filter((a) => a.policy && a.policy !== 'standalone' && isAnchorFor(a, s))
      .map((a) => ({ ...a, addonNote: describeAddon(db, a) })),
    packages: db.packages.filter((p) => p.items.some((i) => i.spaceId === id)),
  };
}

function listBookings(db, userId) {
  const title = (id) => db.spaces.find((s) => s.id === id)?.title ?? id;
  const name = (id) => db.users.find((u) => u.id === id)?.name ?? id;
  return db.bookings
    .filter((b) => !userId || b.renterId === userId || b.hostId === userId)
    .map((b) => ({ ...b, role: b.hostId === userId ? 'host' : 'renter', renterName: name(b.renterId), hostName: name(b.hostId),
      itemsLabel: b.items.map((i) => `${i.qty > 1 ? `${i.qty}× ` : ''}${title(i.spaceId)}`).join(' + '),
      packageName: db.packages.find((p) => p.id === b.packageId)?.name ?? null }))
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

async function readJson(req) {
  let raw = '';
  for await (const chunk of req) { raw += chunk; if (raw.length > 1e6) throw new Error('Body too large'); }
  return raw ? JSON.parse(raw) : {};
}

function send(res, status, data) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(data));
}

async function serveStatic(pathname, res) {
  const rel = normalize(pathname === '/' ? '/index.html' : pathname).replace(/^(\.\.[/\\])+/, '');
  const file = join(PUBLIC, rel);
  if (!file.startsWith(PUBLIC)) return send(res, 403, { error: 'Forbidden' });
  try {
    const data = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' });
    res.end(data);
  } catch {
    send(res, 404, { error: 'Not found' });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const store = openStore(process.env.DB_FILE ?? join(ROOT, 'data', 'db.json'));
  const port = Number(process.env.PORT ?? 3000);
  createServer(createApp(store)).listen(port, () => console.log(`Everyspace on http://localhost:${port}`));
}
