// Tiny JSON-file store for the prototype. Phase 1 replaces this with Postgres.
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { seed } from './seed.js';

export function openStore(file) {
  let db = file && existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : seed();
  return {
    get db() { return db; },
    newId(prefix) { return `${prefix}_${db.seq++}`; },
    save() {
      if (!file) return;
      mkdirSync(dirname(file), { recursive: true });
      writeFileSync(file, JSON.stringify(db, null, 2));
    },
    reset() { db = seed(); this.save(); },
  };
}
