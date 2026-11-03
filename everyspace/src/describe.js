import { CATEGORIES } from './catalog.js';

// Plain-language add-on rule, e.g. "Only with an apartment / unit here, up to 2 each".
export const withArticle = (label) => `${/^[aeiou]/i.test(label) ? 'an' : 'a'} ${label.toLowerCase()}`;

export function describeAddon(db, s) {
  if (!s.addon || (s.policy ?? 'standalone') === 'standalone') return null;
  const anchors = [
    ...(s.addon.anchorCategories || []).map((c) => `${withArticle(CATEGORIES[c].label)} here`),
    ...(s.addon.anchorIds || []).map((id) => db.spaces.find((x) => x.id === id)?.title ?? id),
  ].join(' or ');
  const cap = s.addon.maxPerAnchor ? `, up to ${s.addon.maxPerAnchor} each` : '';
  return s.policy === 'addon'
    ? `Only with ${anchors}${cap}`
    : `Anyone can rent; cheaper with ${anchors}${cap}`;
}
