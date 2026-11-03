// JSON API + static demo UI. Run: node src/server.js  (PORT, DB_FILE env vars optional)
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { handleApi, isUserError, NotFound } from './routes.js';
import { markdownToHtml } from './markdown.js';
import { openStore } from './store.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const PUBLIC = join(ROOT, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
const spec = () => markdownToHtml(readFileSync(join(ROOT, 'SPEC.md'), 'utf8'));

export function createApp(store) {
  return async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    try {
      if (url.pathname.startsWith('/api/')) {
        const body = req.method === 'POST' ? await readJson(req) : {};
        return send(res, 200, handleApi(store, req.method, url.pathname.slice(5), body, url.searchParams, { spec }));
      }
      return serveStatic(url.pathname, res);
    } catch (err) {
      const status = err instanceof NotFound ? 404 : isUserError(err) ? 400 : 500;
      if (status === 500) console.error(err);
      return send(res, status, { error: err.message, details: err.details ?? [] });
    }
  };
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
