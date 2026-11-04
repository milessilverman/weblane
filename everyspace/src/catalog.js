// What can be rented, and the defaults each kind of space carries.
// See SPEC.md §1.

export const TERMS = {
  hourly: { label: 'Hourly', unit: 'hour' },
  daily: { label: 'Nightly / daily', unit: 'day' },
  weekly: { label: 'Weekly', unit: 'week' },
  monthly: { label: 'Month-to-month', unit: 'month' },
  lease: { label: 'Fixed lease', unit: 'month', min: 6, max: 24 },
  infrastructure: { label: 'Infrastructure agreement', unit: 'year', min: 5, max: 25 },
};

// Strictness order: a cart takes the strictest mode of its items.
export const MODES = ['instant', 'request', 'proposal'];

export const GROUPS = {
  living: 'Stays',
  outdoor: 'Activities & events',
  parking: 'Parking & docks',
  storage: 'Storage',
  land: 'Land & growing',
  energy: 'Energy & infrastructure',
  commercial: 'Commercial & fleet',
  container: 'Building / container',
};

// Who the listing is for. Everyday renters never see business categories; those are
// leased to companies (solar installers, charging networks, telecoms, fleets) on the business side.
export const AUDIENCES = { consumer: 'Everyone', business: 'Businesses' };
const GROUP_AUDIENCE = { energy: 'business', commercial: 'business' };

const c = (group, label, terms, measure, mode, checklist, extra = {}) => ({
  group, label, terms, measure, mode, checklist, ...extra,
});

export const CATEGORIES = {
  // Living
  entire_home: c('living', 'Entire home', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['Short-term rental license and number (San Diego: STRO tier; whole homes need Tier 3/4 and a 2-night minimum)', 'Occupancy tax registration (or confirmed platform collection)', 'Smoke & CO detectors'],
    { deposit: 300 }),
  apartment_unit: c('living', 'Apartment / unit', ['daily', 'monthly', 'lease'], 'whole', 'request',
    ['Rental registration', 'Habitability inspection', 'Smoke & CO detectors'], { deposit: 500 }),
  adu: c('living', 'ADU / guest house', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['Permitted ADU', 'Short-term rental permit (if < 30 nights)', 'Smoke & CO detectors'], { deposit: 300 }),
  private_room: c('living', 'Private room', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['House rules for shared areas', 'Smoke & CO detectors'], { deposit: 150 }),

  // Outdoor & activity
  backyard: c('outdoor', 'Backyard', ['hourly', 'daily'], 'whole', 'instant',
    ['City allows paid gatherings at this address (zoning / event permit)', 'Noise curfew (San Diego: quieter limits 10 pm–7 am)', 'Max guests', 'Restroom access plan']),
  yard_campsite: c('outdoor', 'Yard campsite', ['daily', 'weekly'], 'site', 'request',
    ['Restroom access', 'Fire policy']),
  pool: c('outdoor', 'Pool', ['hourly'], 'whole', 'request',
    ['County health classification confirmed (a paid private pool may count as a public pool)', 'Pool fencing / gate', 'Liability waiver']),
  workspace: c('outdoor', 'Workspace / studio / workshop', ['hourly', 'daily', 'monthly'], 'whole', 'instant',
    ['Tool / equipment rules']),
  film_location: c('outdoor', 'Filming / photo location', ['hourly', 'daily'], 'whole', 'request',
    ['City film permit (if required)', 'Neighbor notice']),
  kitchen: c('outdoor', 'Kitchen', ['hourly', 'daily', 'monthly'], 'whole', 'request',
    ['Kitchen is permitted for this use (cottage food / health department)', 'Cleaning checklist', 'Allergen disclosure']),
  sport_court: c('outdoor', 'Sport court', ['hourly'], 'whole', 'instant',
    ['Lighting hours', 'Liability waiver']),

  // Parking
  parking_spot: c('parking', 'Parking spot', ['hourly', 'daily', 'weekly', 'monthly', 'lease'], 'spot', 'instant',
    ['City allows paid parking at this address', 'Spot photos & dimensions', 'Access instructions']),
  rv_parking: c('parking', 'RV / boat / trailer parking', ['weekly', 'monthly', 'lease'], 'spot', 'request',
    ['Storage only: no one sleeps in the RV', 'Max length', 'HOA allows RV storage']),
  ev_charging: c('parking', 'EV charging', ['hourly', 'daily', 'monthly'], 'charger', 'instant',
    ['Charger type & kW']),
  dock_slip: c('parking', 'Boat dock / slip', ['daily', 'weekly', 'monthly', 'lease'], 'slip', 'request',
    ['Max boat length & draft', 'Dock condition & insurance']),

  // Storage
  garage_storage: c('storage', 'Garage storage', ['weekly', 'monthly', 'lease'], 'sqft', 'instant',
    ['No hazardous materials policy', 'Access hours'], { deposit: 50 }),
  attic_storage: c('storage', 'Attic storage', ['monthly', 'lease'], 'sqft', 'instant',
    ['Weight limit', 'Ladder / access disclosure'], { deposit: 50 }),
  basement_storage: c('storage', 'Basement / closet / shed', ['weekly', 'monthly', 'lease'], 'sqft', 'instant',
    ['Moisture disclosure', 'Access hours'], { deposit: 50 }),

  // Land & growing
  garden_plot: c('land', 'Garden plot', ['monthly', 'lease'], 'sqft', 'request',
    ['Water access', 'HOA front-yard rules', 'Chemical policy']),
  beehive_site: c('land', 'Beehive / small-ag site', ['monthly', 'lease'], 'site', 'request',
    ['Local apiary rules']),
  pasture: c('land', 'Pasture / paddock', ['monthly', 'lease'], 'acre', 'request',
    ['Fencing & water', 'Livestock zoning']),

  // Energy & infrastructure
  rooftop_solar: c('energy', 'Rooftop solar', ['infrastructure'], 'sqft', 'proposal',
    ['Usable roof area measured (most programs need 40,000+ sq ft)', 'Roof age & structural assessment', 'Utility interconnection path',
      'Removal / re-roof clause', 'Recorded lease or easement', 'HOA solar rights'], { minYears: 10 }),
  battery_site: c('energy', 'Battery site', ['infrastructure'], 'site', 'proposal',
    ['NFPA 855 setbacks', 'Utility / VPP program', 'Electrical permit']),
  charger_site: c('energy', 'Public EV charger site', ['infrastructure'], 'site', 'proposal',
    ['Curb cut / access', 'Electrical service capacity']),
  telecom_site: c('energy', 'Telecom / sensor site', ['infrastructure'], 'site', 'proposal',
    ['RF exposure compliance', 'Structural mount assessment']),

  // Commercial & fleet (business side)
  fleet_parking: c('commercial', 'Fleet & van parking', ['monthly', 'lease'], 'spot', 'proposal',
    ['Zoning allows commercial vehicles', 'Overnight access & lighting', 'Neighbor notice']),
  signage: c('commercial', 'Sign / billboard site', ['lease', 'infrastructure'], 'site', 'proposal',
    ['Local sign ordinance permit', 'Structural / wind load review', 'Illumination hours']),
  parcel_locker: c('commercial', 'Parcel locker host', ['lease', 'infrastructure'], 'site', 'proposal',
    ['Power outlet within 6 ft', '24/7 or posted access', 'Property insurance notice']),

  // Non-rentable structure used to organize spaces (apartment building, garage)
  building: c('container', 'Building / container', [], 'whole', 'instant', []),
};

const ICONS = {
  entire_home: '🏠', apartment_unit: '🏢', adu: '🏡', private_room: '🛏️',
  backyard: '🌳', yard_campsite: '⛺', pool: '🏊', workspace: '🛠️', film_location: '🎬',
  parking_spot: '🅿️', rv_parking: '🚐', ev_charging: '⚡',
  garage_storage: '📦', attic_storage: '🧳', basement_storage: '🗄️',
  garden_plot: '🥕', beehive_site: '🐝',
  rooftop_solar: '☀️', battery_site: '🔋', charger_site: '🔌', telecom_site: '📡',
  kitchen: '🍳', sport_court: '🎾', dock_slip: '⛵', pasture: '🐴',
  fleet_parking: '🚚', signage: '🪧', parcel_locker: '📮',
  building: '🏗️',
};

// Local example prices (San Diego, researched 2026-11-04, RESEARCH_RESULTS.md §8). Starting points for new listings
// and the earnings illustration. These are EXAMPLE LISTINGS or ASSUMPTIONS, not typical income or medians:
// TYPICAL_META says which, with the source. Unknown cells are simply absent.
export const TYPICAL = {
  entire_home: { daily: 180, weekly: 1100, monthly: 3400, lease: 3200 }, apartment_unit: { daily: 120, monthly: 2950, lease: 2600 },
  adu: { daily: 110, weekly: 650, monthly: 3500, lease: 3000 }, private_room: { daily: 70, weekly: 420, monthly: 1650, lease: 1500 },
  backyard: { hourly: 145, daily: 400 }, yard_campsite: { daily: 30, weekly: 180 }, pool: { hourly: 33 },
  workspace: { hourly: 30, daily: 33, monthly: 250 }, film_location: { hourly: 105, daily: 900 },
  kitchen: { hourly: 25, daily: 150, monthly: 900 }, sport_court: { hourly: 20 },
  parking_spot: { hourly: 4, daily: 20, weekly: 70, monthly: 167, lease: 160 }, rv_parking: { weekly: 70, monthly: 190, lease: 180 },
  ev_charging: { hourly: 5, daily: 25, monthly: 120 }, dock_slip: { daily: 60, weekly: 220, monthly: 350, lease: 320 },
  garage_storage: { weekly: 25, monthly: 250, lease: 230 }, attic_storage: { monthly: 39, lease: 36 }, basement_storage: { weekly: 20, monthly: 60, lease: 55 },
  garden_plot: { monthly: 25, lease: 16 }, beehive_site: {}, pasture: { monthly: 120, lease: 100 },
  rooftop_solar: {}, battery_site: {}, charger_site: {}, telecom_site: {},
  fleet_parking: { monthly: 180, lease: 160 }, signage: { lease: 406, infrastructure: 4869 }, parcel_locker: {},
};
// basis: "example" = a dated local listing or operator price; "assumption" = our placeholder, not researched.
const EX = (terms, source, note = '') => ({ basis: 'example', terms, source, note });
export const TYPICAL_META = {
  entire_home: EX(['monthly'], 'Furnished Finder San Diego listings ($3,400 2BR; $3,800 bungalow)'),
  apartment_unit: EX(['monthly'], 'Furnished Finder San Diego 1BR example ($2,950)'),
  adu: EX(['monthly'], 'Furnished Finder San Diego ADU listing ($3,500 base; utilities unclear)'),
  private_room: EX(['monthly'], 'Furnished Finder San Diego private room ($1,650)'),
  backyard: EX(['hourly'], 'Peerspace San Diego backyard venues ($140–150/hr, 2-hour minimum)', 'Event-venue backyards; a plain backyard may rent for much less.'),
  pool: EX(['hourly'], 'Swimply Clairemont saltwater pool ($33/hr, up to 5 guests)'),
  workspace: EX(['hourly', 'daily', 'monthly'], 'LiquidSpace San Diego (offices $30+/hr, day passes $30–35, desks $195–300/mo)'),
  film_location: EX(['hourly'], 'Peerspace San Diego filming locations (platform-reported average $105/hr)'),
  kitchen: EX(['hourly'], 'Park 734 commissary kitchen ($22–27/hr)', 'A licensed commercial kitchen, not a home kitchen.'),
  parking_spot: EX(['daily', 'monthly'], 'Park It On Market garage ($20–25/24h; $200/mo) and Neighbor monthly spaces ($157–189)', 'Event days near Petco Park: $10/hr meters, $15 per 12h garage event rate.'),
  rv_parking: EX(['monthly'], 'Neighbor San Diego RV storage ($190/mo, 10×35)'),
  dock_slip: EX(['daily'], 'Port of San Diego guest dock ($1.51/ft/day; 40 ft = $60.40)', 'Public guest dock, not a private marina lease.'),
  garage_storage: EX(['monthly'], 'Neighbor San Diego garages ($250/mo, 10×20)'),
  attic_storage: EX(['monthly'], 'Neighbor Vista attic listing ($39/mo, 4×7)'),
  garden_plot: EX(['lease'], 'Sweetwater Community Garden permit ($195/yr for 10×20 = $16.25/mo)'),
  beehive_site: { basis: 'unknown', terms: [], source: 'Local hive-hosting programs', note: 'In some programs the homeowner pays the beekeeper, not the other way round.' },
  rooftop_solar: { basis: 'unknown', terms: [], source: 'Solar Landscape, Nexamp', note: 'No standard rent for ordinary house roofs. Commercial programs usually want 40,000+ sq ft and paid about $0.25–0.85 per sq ft per year (Dec 2024).' },
  battery_site: { basis: 'unknown', terms: [], source: 'Enel X, Nine Energy', note: 'Rent is negotiated; programs screen for large outdoor pads and big electrical service.' },
  charger_site: { basis: 'unknown', terms: [], source: 'EVgo', note: 'Rent is negotiated; EVgo-owned sites need a 10-year minimum lease.' },
  telecom_site: { basis: 'unknown', terms: [], source: 'Crown Castle', note: 'Rent is negotiated; new tower demand is currently minimal.' },
  signage: { basis: 'benchmark', terms: ['lease', 'infrastructure'], source: 'Lamar 2025 10-K', note: 'Portfolio average ≈ $4,869 per site per year ($406/mo), calculated; not a local offer.' },
  parcel_locker: { basis: 'unknown', terms: [], source: 'Amazon Locker via UNFI', note: 'Some programs pay retailers monthly by locker size; amounts aren\'t published.' },
  fleet_parking: { basis: 'assumption', terms: [], source: 'Neighbor fleet program', note: 'Fleet contract rents aren\'t published.' },
};

for (const [k, cat] of Object.entries(CATEGORIES)) {
  cat.icon = ICONS[k];
  cat.audience = GROUP_AUDIENCE[cat.group] ?? 'consumer';
  if (TYPICAL[k] && Object.keys(TYPICAL[k]).length) cat.typical = TYPICAL[k];
  cat.typicalMeta = TYPICAL_META[k] ?? { basis: 'assumption', terms: [], source: 'Everyspace placeholder (not researched)' };
  // Every rentable use needs the owner's insurance confirmed (homeowner policies often exclude rentals; NAIC).
  if (cat.group !== 'container') cat.checklist = [...cat.checklist, 'Insurance covers this use (homeowner policies may not)'];
}

export const GROUP_ICONS = { living: '🏠', outdoor: '🎉', parking: '🅿️', storage: '📦', land: '🌱', energy: '☀️', commercial: '🚚', container: '🏗️' };

export function category(key) {
  const cat = CATEGORIES[key];
  if (!cat) throw new Error(`Unknown category: ${key}`);
  return cat;
}
