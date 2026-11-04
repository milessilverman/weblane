// Builds dist/everyspace.html: the whole app in one self-contained file.
// The API runs in the browser (the same route code as the server) and data is kept in localStorage.
//
// A tiny bundler: each ES module becomes a function scope; `import { a } from './x.js'` turns into
// `const { a } = __m.x;` and the module's `export`ed names are collected into `__m.<name>`.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { markdownToHtml } from '../src/markdown.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const read = (p) => readFileSync(join(ROOT, p), 'utf8');

function bundle(dir, names) {
  return names.map((name) => {
    let src = read(`${dir}/${name}.js`);
    const exported = [];
    src = src.replace(/^import \{([^}]+)\} from '\.\/([\w-]+)\.js';$/gm, (_, list, from) => {
      if (!names.includes(from)) throw new Error(`${name}.js imports ${from}.js, which is not in the bundle list`);
      return `const {${list}} = __m['${from}'];`;
    });
    if (/^import /m.test(src)) throw new Error(`${name}.js has an import the bundler can't handle`);
    src = src.replace(/^export (async function|function|const|let|class) ([\w$]+)/gm, (_, kind, id) => { exported.push(id); return `${kind} ${id}`; });
    if (/^export /m.test(src)) throw new Error(`${name}.js has an export the bundler can't handle`);
    return `// ---- ${dir}/${name}.js ----\n(() => {\n${src}\n__m['${name}'] = { ${exported.join(', ')} };\n})();`;
  }).join('\n');
}

const DOMAIN = ['catalog', 'time', 'describe', 'pricing', 'compare', 'tax', 'availability', 'booking', 'social', 'host', 'owner', 'seed', 'listings', 'routes'];
const UI = ['core', 'art', 'calendar', 'explore', 'space', 'book', 'trips', 'inbox', 'host', 'wizard', 'profile', 'biz', 'earn', 'manage', 'main'];

const specHtml = markdownToHtml(read('SPEC.md'));

const domain = `(() => {
const __m = {};
${bundle('src', DOMAIN)}
const { handleApi, isUserError, NotFound } = __m.routes;
const { seed } = __m.seed;
const SPEC_HTML = ${JSON.stringify(specHtml).replace(/<\//g, '<\\/')};
const KEY = 'everyspace-demo-v5';
let db;
try { db = JSON.parse(localStorage.getItem(KEY)); } catch {}
if (!db) db = seed();
const store = {
  get db() { return db; },
  newId: (prefix) => \`\${prefix}_\${db.seq++}\`,
  save() { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch {} },
  reset() { db = seed(); this.save(); },
};
window.everyspaceApi = async (path, body) => {
  const [p, qs] = path.split('?');
  try {
    return JSON.parse(JSON.stringify(handleApi(store, body ? 'POST' : 'GET', p, body ?? {}, new URLSearchParams(qs), { spec: () => SPEC_HTML })));
  } catch (err) {
    if (!isUserError(err) && !(err instanceof NotFound)) console.error(err);
    const e = new Error(err.message); e.details = err.details ?? []; throw e;
  }
};
})();`;

const ui = `(() => {
const __m = {};
${bundle('public/js', UI)}
})();`;

const guard = (s) => { if (/<\/script/i.test(s)) throw new Error('Inline script contains </script'); return s; };

let html = read('public/index.html');
const swap = (from, to) => { if (!html.includes(from)) throw new Error(`Missing in index.html: ${from}`); html = html.replace(from, () => to); };
const iconData = `data:image/svg+xml,${encodeURIComponent(read('public/icon.svg'))}`;
swap('<link rel="stylesheet" href="styles.css">', `<style>\n${read('public/styles.css')}</style>`);
swap('<link rel="manifest" href="manifest.webmanifest">\n', '');
swap('<link rel="icon" href="icon.svg" type="image/svg+xml">', `<link rel="icon" href="${iconData}" type="image/svg+xml">`);
swap('<link rel="apple-touch-icon" href="icon.svg">', `<link rel="apple-touch-icon" href="${iconData}">`);
swap('<script type="module" src="js/main.js"></script>', `<script>\n${guard(domain)}\n</script>\n<script type="module">\n${guard(ui)}\n</script>`);

mkdirSync(join(ROOT, 'dist'), { recursive: true });
writeFileSync(join(ROOT, 'dist', 'everyspace.html'), html);
console.log(`dist/everyspace.html (${(html.length / 1024).toFixed(0)} KB)`);
