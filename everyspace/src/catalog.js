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
  living: 'Living',
  outdoor: 'Outdoor & activity',
  parking: 'Parking',
  storage: 'Storage',
  land: 'Land & growing',
  energy: 'Energy & infrastructure',
  container: 'Building / container',
};

const c = (group, label, terms, measure, mode, checklist, extra = {}) => ({
  group, label, terms, measure, mode, checklist, ...extra,
});

export const CATEGORIES = {
  // Living
  entire_home: c('living', 'Entire home', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['Short-term rental permit / registration', 'Occupancy tax account', 'Smoke & CO detectors', 'Host insurance'],
    { deposit: 300 }),
  apartment_unit: c('living', 'Apartment / unit', ['daily', 'monthly', 'lease'], 'whole', 'request',
    ['Rental registration', 'Habitability inspection', 'Smoke & CO detectors'], { deposit: 500 }),
  adu: c('living', 'ADU / guest house', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['Permitted ADU', 'Short-term rental permit (if < 30 nights)', 'Smoke & CO detectors'], { deposit: 300 }),
  private_room: c('living', 'Private room', ['daily', 'weekly', 'monthly', 'lease'], 'whole', 'request',
    ['House rules for shared areas', 'Smoke & CO detectors'], { deposit: 150 }),

  // Outdoor & activity
  backyard: c('outdoor', 'Backyard', ['hourly', 'daily'], 'whole', 'instant',
    ['Noise curfew', 'Max guests', 'Restroom access plan']),
  yard_campsite: c('outdoor', 'Yard campsite', ['daily', 'weekly'], 'site', 'request',
    ['Restroom access', 'Fire policy']),
  pool: c('outdoor', 'Pool', ['hourly'], 'whole', 'request',
    ['Pool fencing / gate', 'Liability waiver', 'Insurance confirmation']),
  workspace: c('outdoor', 'Workspace / studio / workshop', ['hourly', 'daily', 'monthly'], 'whole', 'instant',
    ['Tool / equipment rules']),
  film_location: c('outdoor', 'Filming / photo location', ['hourly', 'daily'], 'whole', 'request',
    ['City film permit (if required)', 'Neighbor notice']),

  // Parking
  parking_spot: c('parking', 'Parking spot', ['hourly', 'daily', 'weekly', 'monthly', 'lease'], 'spot', 'instant',
    ['Spot photos & dimensions', 'Access instructions']),
  rv_parking: c('parking', 'RV / boat / trailer parking', ['weekly', 'monthly', 'lease'], 'spot', 'request',
    ['Max length', 'HOA allows RV storage']),
  ev_charging: c('parking', 'EV charging', ['hourly', 'daily', 'monthly'], 'charger', 'instant',
    ['Charger type & kW']),

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

  // Energy & infrastructure
  rooftop_solar: c('energy', 'Rooftop solar', ['infrastructure'], 'sqft', 'proposal',
    ['Roof age & structural assessment', 'Utility interconnection path', 'Removal / re-roof clause',
      'Recorded lease or easement', 'HOA solar rights'], { minYears: 10 }),
  battery_site: c('energy', 'Battery site', ['infrastructure'], 'site', 'proposal',
    ['NFPA 855 setbacks', 'Utility / VPP program', 'Electrical permit']),
  charger_site: c('energy', 'Public EV charger site', ['infrastructure'], 'site', 'proposal',
    ['Curb cut / access', 'Electrical service capacity']),
  telecom_site: c('energy', 'Telecom / sensor site', ['infrastructure'], 'site', 'proposal',
    ['RF exposure compliance', 'Structural mount assessment']),

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
  building: '🏗️',
};
for (const [k, icon] of Object.entries(ICONS)) CATEGORIES[k].icon = icon;

export const GROUP_ICONS = { living: '🏠', outdoor: '🌳', parking: '🅿️', storage: '📦', land: '🥕', energy: '☀️', container: '🏗️' };

export function category(key) {
  const cat = CATEGORIES[key];
  if (!cat) throw new Error(`Unknown category: ${key}`);
  return cat;
}
