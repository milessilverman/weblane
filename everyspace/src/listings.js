// Search, and creating properties / spaces / packages with validation.
import { category, CATEGORIES, TERMS } from './catalog.js';
import { unitsFree } from './availability.js';
import { describeAddon } from './describe.js';
import { ratingFor } from './social.js';

export function search(db, { group, category: cat, term, start, end, q, city } = {}) {
  const text = q?.toLowerCase();
  const results = [];
  for (const s of db.spaces) {
    if (s.rentable === false) continue;
    const c = CATEGORIES[s.category];
    const prop = db.properties.find((p) => p.id === s.propertyId);
    if (group && c.group !== group) continue;
    if (cat && s.category !== cat) continue;
    if (term && !(c.terms.includes(term) && (s.rates?.[term] != null || s.addonRates?.[term] != null))) continue;
    if (city && prop.city.toLowerCase() !== city.toLowerCase()) continue;
    if (text && !`${s.title} ${s.description ?? ''} ${c.label} ${prop.title}`.toLowerCase().includes(text)) continue;
    const free = start && end ? unitsFree(db, s, start, end) : s.quantity ?? 1;
    results.push({
      ...s,
      categoryLabel: c.label,
      group: c.group,
      property: { id: prop.id, title: prop.title, city: prop.city, lat: prop.lat, lng: prop.lng, hostId: prop.hostId },
      icon: c.icon,
      rating: ratingFor(db, s.id),
      unitsFree: free,
      policy: s.policy ?? 'standalone',
      addonNote: describeAddon(db, s),
      fromPrice: cheapest(s),
    });
  }
  const packages = db.packages
    .filter((p) => !text || p.name.toLowerCase().includes(text))
    .filter((p) => !group || p.items.some((i) => CATEGORIES[db.spaces.find((s) => s.id === i.spaceId).category].group === group))
    .map((p) => ({ ...p, property: db.properties.find((x) => x.id === p.propertyId),
      items: p.items.map((i) => ({ ...i, category: db.spaces.find((x) => x.id === i.spaceId)?.category })) }));
  return { spaces: results, packages };
}

function cheapest(s) {
  const order = Object.keys(TERMS);
  const t = order.find((k) => s.rates?.[k] != null) ?? order.find((k) => s.addonRates?.[k] != null);
  return t ? { term: t, amount: s.rates?.[t] ?? s.addonRates[t], unit: TERMS[t].unit } : null;
}

export function createProperty(db, input, newId) {
  for (const k of ['hostId', 'title', 'city']) if (!input[k]) throw new Error(`${k} is required`);
  const p = { id: newId('p'), type: 'single_family', hoa: false, notes: '', ...pick(input, ['hostId', 'title', 'city', 'type', 'hoa', 'notes']) };
  db.properties.push(p);
  return p;
}

export function createSpace(db, input, newId) {
  const prop = db.properties.find((p) => p.id === input.propertyId);
  if (!prop) throw new Error('Property not found');
  const cat = category(input.category);
  if (!input.title) throw new Error('title is required');
  const rentable = input.rentable !== false && cat.group !== 'container';
  const rates = {};
  for (const [t, v] of Object.entries(input.rates || {})) {
    if (v === '' || v == null) continue;
    if (!cat.terms.includes(t)) throw new Error(`${cat.label} can't be rented ${TERMS[t]?.label ?? t}`);
    if (!(Number(v) > 0)) throw new Error(`Rate for ${t} must be positive`);
    rates[t] = Number(v);
  }
  if (rentable && !Object.keys(rates).length && !input.addonRates) throw new Error('Set at least one price');
  const missing = rentable ? cat.checklist.filter((item) => !input.checklist?.includes(item)) : [];
  if (missing.length) throw new Error(`Confirm before publishing: ${missing.join('; ')}`);
  if (input.parentId) {
    const parent = db.spaces.find((s) => s.id === input.parentId);
    if (!parent || parent.propertyId !== prop.id) throw new Error('Parent must be a space on the same property');
  }
  const policy = input.policy ?? 'standalone';
  if (policy !== 'standalone' && !input.addon?.anchorCategories?.length && !input.addon?.anchorIds?.length) {
    throw new Error('Add-on spaces need at least one anchor');
  }
  const s = {
    id: newId('s'),
    ...pick(input, ['propertyId', 'parentId', 'category', 'title', 'description', 'size', 'addonRates', 'eventRates', 'conflictsWith', 'blackouts', 'minDuration', 'mode', 'amenities', 'access']),
    ...(rentable ? { checklist: cat.checklist } : {}),
    quantity: Math.max(1, Number(input.quantity) || 1),
    rates,
    policy,
    ...(policy !== 'standalone' ? { addon: input.addon } : {}),
    ...(rentable ? {} : { rentable: false }),
  };
  db.spaces.push(s);
  return s;
}

export function createPackage(db, input, newId) {
  if (!input.name) throw new Error('name is required');
  if (!input.items?.length) throw new Error('A package needs spaces');
  for (const it of input.items) {
    const s = db.spaces.find((x) => x.id === it.spaceId);
    if (!s || s.propertyId !== input.propertyId) throw new Error('Package spaces must be on the same property');
  }
  const p = { id: newId('pk'), ...pick(input, ['propertyId', 'name', 'items', 'pricing']) };
  db.packages.push(p);
  return p;
}

function pick(o, keys) {
  const out = {};
  for (const k of keys) if (o[k] !== undefined) out[k] = o[k];
  return out;
}
