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
  kitchen: c('outdoor', 'Kitchen', ['hourly', 'daily', 'monthly'], 'whole', 'request',
    ['Cottage food / food handler rules', 'Cleaning checklist', 'Allergen disclosure']),
  sport_court: c('outdoor', 'Sport court', ['hourly'], 'whole', 'instant',
    ['Lighting hours', 'Liability waiver']),

  // Parking
  parking_spot: c('parking', 'Parking spot', ['hourly', 'daily', 'weekly', 'monthly', 'lease'], 'spot', 'instant',
    ['Spot photos & dimensions', 'Access instructions']),
  rv_parking: c('parking', 'RV / boat / trailer parking', ['weekly', 'monthly', 'lease'], 'spot', 'request',
    ['Max length', 'HOA allows RV storage']),
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
    ['Roof age & structural assessment', 'Utility interconnection path', 'Removal / re-roof clause',
      'Recorded lease or easement', 'HOA solar rights'], { minYears: 10 }),
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

// Typical local prices: starting points for new listings and the earnings estimator.
export const TYPICAL = {
  entire_home: { daily: 180, weekly: 1100, monthly: 3500, lease: 3200 }, apartment_unit: { daily: 120, monthly: 2000, lease: 1850 },
  adu: { daily: 110, weekly: 650, monthly: 1800, lease: 1700 }, private_room: { daily: 70, weekly: 420, monthly: 1100, lease: 1000 },
  backyard: { hourly: 30, daily: 150 }, yard_campsite: { daily: 30, weekly: 180 }, pool: { hourly: 40 },
  workspace: { hourly: 15, daily: 80, monthly: 400 }, film_location: { hourly: 150, daily: 900 },
  kitchen: { hourly: 25, daily: 150, monthly: 900 }, sport_court: { hourly: 20 },
  parking_spot: { hourly: 4, daily: 15, weekly: 70, monthly: 130, lease: 120 }, rv_parking: { weekly: 70, monthly: 220, lease: 200 },
  ev_charging: { hourly: 5, daily: 25, monthly: 120 }, dock_slip: { daily: 40, weekly: 220, monthly: 350, lease: 320 },
  garage_storage: { weekly: 25, monthly: 90, lease: 80 }, attic_storage: { monthly: 50, lease: 45 }, basement_storage: { weekly: 20, monthly: 60, lease: 55 },
  garden_plot: { monthly: 25, lease: 20 }, beehive_site: { monthly: 15, lease: 12 }, pasture: { monthly: 120, lease: 100 },
  rooftop_solar: { infrastructure: 1000 }, battery_site: { infrastructure: 600 }, charger_site: { infrastructure: 1500 }, telecom_site: { infrastructure: 3500 },
  fleet_parking: { monthly: 180, lease: 160 }, signage: { lease: 400, infrastructure: 4200 }, parcel_locker: { lease: 75, infrastructure: 900 },
};

for (const [k, cat] of Object.entries(CATEGORIES)) {
  cat.icon = ICONS[k];
  cat.audience = GROUP_AUDIENCE[cat.group] ?? 'consumer';
  if (TYPICAL[k]) cat.typical = TYPICAL[k];
}

export const GROUP_ICONS = { living: '🏠', outdoor: '🎉', parking: '🅿️', storage: '📦', land: '🌱', energy: '☀️', commercial: '🚚', container: '🏗️' };

export function category(key) {
  const cat = CATEGORIES[key];
  if (!cat) throw new Error(`Unknown category: ${key}`);
  return cat;
}
