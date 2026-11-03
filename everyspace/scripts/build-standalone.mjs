// Builds dist/everyspace.html: the plan + the full demo in one self-contained file.
// The API runs in the browser (same route code as the server); data is kept in localStorage.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { markdownToHtml } from '../src/markdown.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const read = (p) => readFileSync(join(ROOT, p), 'utf8');

// Pure domain modules in dependency order, with import/export stripped, inside one scope.
const MODULES = ['catalog', 'time', 'describe', 'pricing', 'availability', 'booking', 'seed', 'listings', 'routes'];
const domain = MODULES.map((m) => `// --- src/${m}.js ---\n${read(`src/${m}.js`)
  .replace(/^import .*;\n/gm, '')
  .replace(/^export /gm, '')}`).join('\n');

const shim = `
const Domain = (() => {
${domain}
return { handleApi, isUserError, NotFound, seed };
})();

(() => {
  const KEY = 'everyspace-demo-v1';
  let db;
  try { db = JSON.parse(localStorage.getItem(KEY)); } catch {}
  if (!db) db = Domain.seed();
  const store = {
    get db() { return db; },
    newId: (prefix) => \`\${prefix}_\${db.seq++}\`,
    save() { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch {} },
    reset() { db = Domain.seed(); this.save(); },
  };
  window.everyspaceApi = async (path, body) => {
    const [p, qs] = path.split('?');
    try {
      return JSON.parse(JSON.stringify(Domain.handleApi(store, body ? 'POST' : 'GET', p, body ?? {}, new URLSearchParams(qs))));
    } catch (err) {
      if (!Domain.isUserError(err) && !(err instanceof Domain.NotFound)) console.error(err);
      const e = new Error(err.message); e.details = err.details ?? []; throw e;
    }
  };
  window.EVERYSPACE_START_TAB = 'plan';
})();
`;

const guard = (s) => { if (/<\/script/i.test(s)) throw new Error('Inline script contains </script'); return s; };

let html = read('public/index.html');
const swap = (from, to) => { if (!html.includes(from)) throw new Error(`Missing in index.html: ${from}`); html = html.replace(from, () => to); };
swap('<link rel="stylesheet" href="styles.css">', `<style>\n${read('public/styles.css')}</style>`);
swap('<article id="plan-body" class="plan"></article>', `<article id="plan-body" class="plan">\n${markdownToHtml(read('SPEC.md'))}\n</article>`);
swap('<script type="module" src="app.js"></script>',
  `<script>\n${guard(shim)}</script>\n<script type="module">\n${guard(read('public/app.js'))}</script>`);

mkdirSync(join(ROOT, 'dist'), { recursive: true });
writeFileSync(join(ROOT, 'dist', 'everyspace.html'), html);
console.log(`dist/everyspace.html (${(html.length / 1024).toFixed(0)} KB)`);
