// Demo data: five properties around one town, from a house by the fairgrounds to a ranch
// with a barn roof for solar. Dates are around November 2026.
import { priceLine, totals } from './pricing.js';

export function seed() {
  const users = [
    { id: 'u_sam', name: 'Sam', tagline: 'Renter', joined: '2025-03', color: '#3b7dd8' },
    { id: 'u_priya', name: 'Priya', tagline: 'Renter, Oak Court tenant', joined: '2024-08', color: '#b84d8a' },
    { id: 'u_maya', name: 'Maya', tagline: 'Host, 412 Maple St', joined: '2023-05', color: '#2f6f4f' },
    { id: 'u_jordan', name: 'Jordan', tagline: 'Host, Oak Court Apartments', joined: '2022-11', color: '#8a5a2b' },
    { id: 'u_luis', name: 'Luis', tagline: 'Host, Elm Ave bungalow & Hillcrest ranch', joined: '2024-02', color: '#6a4fb3' },
    { id: 'u_ana', name: 'Ana', tagline: 'Host, Stadium Lofts condo', joined: '2025-01', color: '#c2552d' },
    { id: 'u_rosa', name: 'Rosa', tagline: 'Host, Lakeview cottage', joined: '2023-09', color: '#1f7a8c' },
    { id: 'u_sunco', name: 'SunCo Solar', tagline: 'Business · solar installer', joined: '2021-06', color: '#d39b16', kind: 'business' },
    { id: 'u_voltway', name: 'VoltWay Charging', tagline: 'Business · EV charging network', joined: '2022-03', color: '#2f6fb3', kind: 'business' },
    { id: 'u_parcel', name: 'ParcelPoint', tagline: 'Business · parcel lockers', joined: '2023-01', color: '#b3402f', kind: 'business' },
    { id: 'u_greenleaf', name: 'Greenleaf Delivery', tagline: 'Business · delivery fleet', joined: '2024-06', color: '#3d8a3d', kind: 'business' },
    { id: 'u_dev', name: 'Dev', tagline: 'Renter', joined: '2024-04', color: '#2c8c8c' },
    { id: 'u_kim', name: 'Kim', tagline: 'Renter', joined: '2025-07', color: '#7a7a2a' },
  ];

  const properties = [
    { id: 'p_maple', hostId: 'u_maya', title: '412 Maple St', city: 'Riverside', type: 'single_family', hoa: false,
      lat: 33.975, lng: -117.375, notes: '3 blocks from the county fairgrounds.' },
    { id: 'p_oak', hostId: 'u_jordan', title: 'Oak Court Apartments', city: 'Riverside', type: 'multi_unit', hoa: false,
      lat: 33.981, lng: -117.369, notes: '6-unit building with a 12-space garage and storage lockers.' },
    { id: 'p_elm', hostId: 'u_luis', title: 'Elm Ave bungalow', city: 'Riverside', type: 'single_family', hoa: false,
      lat: 33.969, lng: -117.381, notes: '1950s bungalow with a big backyard, pool and garden ADU.' },
    { id: 'p_lofts', hostId: 'u_ana', title: 'Stadium Lofts #4C', city: 'Riverside', type: 'condo', hoa: true,
      lat: 33.986, lng: -117.362, notes: 'Condo two blocks from the stadium. HOA allows rentals of owned parking.' },
    { id: 'p_hill', hostId: 'u_luis', title: 'Hillcrest ranch', city: 'Riverside', type: 'land', hoa: false,
      lat: 33.962, lng: -117.392, notes: '5 acres on the edge of town. Barn, hilltop, road frontage.' },
    { id: 'p_lake', hostId: 'u_rosa', title: 'Lakeview cottage', city: 'Riverside', type: 'single_family', hoa: false,
      lat: 33.958, lng: -117.372, notes: 'Cottage on the river with a private dock.' },
  ];

  const harvest = { name: 'Harvest Festival', start: '2026-11-20', end: '2026-11-22' };
  const gameDays = ['2026-11-08', '2026-11-15', '2026-11-29', '2026-12-06']
    .map((d) => ({ name: 'Home game', start: d, end: d, daily: 45, hourly: 15 }));

  const spaces = [
    // --- 412 Maple St (Maya) ---------------------------------------------
    { id: 's_maple_home', propertyId: 'p_maple', category: 'entire_home', title: 'Whole house (3 bd)',
      quantity: 1, rates: { daily: 210, weekly: 1300, monthly: 3900, lease: 3600 }, minDuration: { daily: 2 },
      description: 'Entire 3-bedroom home. Includes the backyard and back bedroom.',
      amenities: ['Sleeps 6', 'Wi-Fi', 'Washer/dryer', 'Backyard'], access: 'Smart lock — code sent the morning of check-in.' },
    { id: 's_maple_backyard', propertyId: 'p_maple', parentId: 's_maple_home', category: 'backyard',
      title: 'Backyard with fire pit', quantity: 1, rates: { hourly: 35, daily: 180 },
      eventRates: [{ ...harvest, hourly: 55 }], description: 'Lawn, string lights, fire pit. Quiet hours after 10pm.',
      amenities: ['Up to 25 guests', 'Fire pit', 'String lights', 'Half bath access'], access: 'Side gate, code 2468.' },
    { id: 's_maple_room', propertyId: 'p_maple', parentId: 's_maple_home', category: 'private_room',
      title: 'Back bedroom', quantity: 1, rates: { daily: 75, weekly: 450, monthly: 1300 },
      amenities: ['Queen bed', 'Shared bath', 'Desk'], access: 'Host greets you at the front door.' },
    { id: 's_maple_driveway', propertyId: 'p_maple', category: 'parking_spot', title: 'Driveway parking',
      quantity: 3, rates: { hourly: 4, daily: 15, weekly: 80, monthly: 140 },
      eventRates: [{ ...harvest, daily: 40, hourly: 12 }], conflictsWith: ['s_maple_rv'],
      description: 'Three uncovered spots, 5-minute walk to the fairgrounds.',
      amenities: ['Uncovered', 'Fits SUVs', '5 min walk to fair'], access: 'Pull straight in; spot number is on the confirmation.' },
    { id: 's_maple_rv', propertyId: 'p_maple', category: 'rv_parking', title: 'RV pad (uses the driveway)',
      quantity: 1, rates: { weekly: 120, monthly: 380 }, description: 'Up to 30 ft. Takes over the whole driveway.',
      amenities: ['Up to 30 ft', '30A hookup'], access: 'Text Maya on arrival to move the gate.' },
    { id: 's_maple_garage', propertyId: 'p_maple', category: 'building', title: 'Detached garage', rentable: false, quantity: 1 },
    { id: 's_maple_bay', propertyId: 'p_maple', parentId: 's_maple_garage', category: 'garage_storage',
      title: 'Garage storage bay (100 sq ft)', quantity: 3, size: { sqft: 100 },
      rates: { weekly: 30, monthly: 95, lease: 85 }, description: 'Shelved bays, access 7am–9pm.',
      amenities: ['Shelving', 'Lockable', 'Dry'], access: 'Garage keypad 1357, bays are numbered.' },
    { id: 's_maple_attic', propertyId: 'p_maple', category: 'attic_storage', title: 'Attic storage (80 sq ft)',
      quantity: 1, size: { sqft: 80 }, rates: { monthly: 55, lease: 50 }, description: 'Pull-down ladder, boxes under 40 lb.',
      amenities: ['Boxes only', 'Climate: hot in summer'], access: 'By appointment with Maya.' },
    { id: 's_maple_garden', propertyId: 'p_maple', category: 'garden_plot', title: 'Front-yard garden plot (10×10)',
      quantity: 2, size: { sqft: 100 }, rates: { monthly: 30, lease: 25 }, description: 'Hose bib included. Organic only.',
      amenities: ['Water included', 'Full sun'], access: 'Walk-up; hose bib on the left of the porch.' },
    { id: 's_maple_roof', propertyId: 'p_maple', category: 'rooftop_solar', title: 'South-facing roof (~600 sq ft)',
      quantity: 1, size: { sqft: 600 }, rates: { infrastructure: 1100 },
      description: '2019 roof. ~9 kW potential. Partner owns panels, pays annual rent.',
      specs: { 'Usable roof': '600 sq ft', 'Est. system': '9 kW', Faces: 'South', 'Roof installed': '2019', Shading: 'None', 'Electrical service': '200 A', Utility: 'Riverside Public Utilities' },
      amenities: ['South-facing', '2019 roof', 'No shading'], access: 'Site visit scheduled after proposal.' },
    { id: 's_maple_battery', propertyId: 'p_maple', category: 'battery_site', title: 'Side-yard battery pad',
      quantity: 1, rates: { infrastructure: 600 }, description: '4×8 ft concrete pad, 12 ft from the house.',
      specs: { Pad: '4×8 ft concrete', 'Distance to house': '12 ft', 'Electrical service': '200 A', 'Est. capacity': '13–27 kWh', Utility: 'Riverside Public Utilities' },
      amenities: ['Concrete pad', '200A panel'], access: 'Site visit scheduled after proposal.' },

    // --- Oak Court Apartments (Jordan) -------------------------------------
    { id: 's_oak_bldg', propertyId: 'p_oak', category: 'building', title: 'Oak Court building', rentable: false, quantity: 1 },
    { id: 's_oak_1a', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 1A (1 bd)',
      quantity: 1, rates: { monthly: 2150, lease: 1950 }, amenities: ['1 bed / 1 bath', 'In-unit laundry', 'Pets OK'],
      access: 'Keys at move-in with the building manager.' },
    { id: 's_oak_1b', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 1B (2 bd)',
      quantity: 1, rates: { monthly: 2750, lease: 2500 }, amenities: ['2 bed / 1 bath', 'Balcony'],
      access: 'Keys at move-in with the building manager.' },
    { id: 's_oak_2a', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 2A (studio, furnished)',
      quantity: 1, rates: { daily: 140, monthly: 1900, lease: 1700 }, minDuration: { daily: 3 },
      amenities: ['Furnished', 'Wi-Fi', 'Kitchenette'], access: 'Lockbox at the lobby door, code on the confirmation.' },
    { id: 's_oak_parking', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'parking_spot', title: 'Garage parking space',
      quantity: 12, policy: 'addon', rates: { daily: 20, monthly: 150, lease: 140 },
      addon: { anchorCategories: ['apartment_unit'], maxPerAnchor: 2 },
      description: 'Tenants only, up to 2 per unit.', amenities: ['Covered', 'Gated'], access: 'Garage fob issued with your keys.' },
    { id: 's_oak_locker', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'basement_storage', title: 'Storage locker (5×5)',
      quantity: 8, policy: 'both', size: { sqft: 25 },
      rates: { weekly: 30, monthly: 90, lease: 80 }, addonRates: { monthly: 60, lease: 55 },
      addon: { anchorCategories: ['apartment_unit'], maxPerAnchor: 1 },
      description: '$90/mo for anyone, $60/mo for tenants (1 per unit).', amenities: ['Lockable cage', 'Basement'],
      access: 'Basement door code 8080, bring your own padlock.' },
    { id: 's_oak_ev', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'ev_charging', title: 'Level 2 EV charger',
      quantity: 2, rates: { hourly: 6, daily: 30 }, description: 'Open to the public 6am–11pm.',
      amenities: ['J1772 + Tesla adapter', '7 kW'], access: 'Street-side bays marked EV.' },

    // --- Elm Ave bungalow (Luis) -----------------------------------------
    { id: 's_elm_adu', propertyId: 'p_elm', category: 'adu', title: 'Garden ADU (studio)', quantity: 1,
      rates: { daily: 120, weekly: 700, monthly: 2000, lease: 1850 }, minDuration: { daily: 2 },
      description: 'Detached studio behind the house with its own entrance.',
      amenities: ['Queen bed', 'Kitchenette', 'Private patio'], access: 'Lockbox on the ADU door.' },
    { id: 's_elm_adu_parking', propertyId: 'p_elm', category: 'parking_spot', title: 'Driveway spot for the ADU guest',
      quantity: 1, policy: 'addon', rates: { daily: 10, weekly: 50, monthly: 75, lease: 70 },
      addon: { anchorIds: ['s_elm_adu'], maxPerAnchor: 1 }, description: 'Only for whoever is renting the ADU.',
      amenities: ['Off-street'], access: 'Left side of the driveway.' },
    { id: 's_elm_pool', propertyId: 'p_elm', category: 'pool', title: 'Saltwater pool & patio', quantity: 1,
      rates: { hourly: 45 }, description: 'Heated saltwater pool, shaded patio, outdoor shower.',
      amenities: ['Heated', 'Up to 12 guests', 'Outdoor shower'], access: 'Side gate code 7300.' },
    { id: 's_elm_shop', propertyId: 'p_elm', category: 'workspace', title: 'Woodshop with table saw', quantity: 1,
      rates: { hourly: 18, daily: 90, monthly: 450 }, description: 'Table saw, bandsaw, dust collection. Safety brief required.',
      amenities: ['Table saw', 'Bandsaw', 'Dust collection'], access: 'Luis meets you for the first session.' },
    { id: 's_elm_garden', propertyId: 'p_elm', category: 'garden_plot', title: 'Raised garden bed (4×8)', quantity: 4,
      size: { sqft: 32 }, rates: { monthly: 25, lease: 20 }, description: 'Drip irrigation on a timer.',
      amenities: ['Drip irrigation', 'Tool shed'], access: 'Back gate, beds are labeled.' },
    { id: 's_elm_hive', propertyId: 'p_elm', category: 'beehive_site', title: 'Beehive spot by the orange trees', quantity: 2,
      rates: { monthly: 15, lease: 12 }, amenities: ['Water source', 'Morning sun'], access: 'Back gate.' },
    { id: 's_elm_film', propertyId: 'p_elm', category: 'film_location', title: 'Mid-century living room & yard', quantity: 1,
      rates: { hourly: 150, daily: 900 }, description: 'Original 1950s interior, pool, and big lawn.',
      amenities: ['Street parking for crew', 'Natural light'], access: 'Location walkthrough before the shoot.' },

    // --- Stadium Lofts (Ana) ---------------------------------------------
    { id: 's_ana_park', propertyId: 'p_lofts', category: 'parking_spot', title: 'Garage spot 2 blocks from the stadium',
      quantity: 2, rates: { hourly: 5, daily: 18, monthly: 175, lease: 160 }, eventRates: gameDays,
      description: 'Covered spots in a secure garage. Game-day pricing applies.',
      amenities: ['Covered', 'Secure garage', '2 blocks to stadium'], access: 'Garage code sent 1 hour before start.' },
    { id: 's_ana_ev', propertyId: 'p_lofts', category: 'ev_charging', title: 'Level 2 charger (11 kW)', quantity: 1,
      rates: { hourly: 5 }, amenities: ['11 kW', 'J1772'], access: 'Spot 14 in the garage.' },
    { id: 's_ana_closet', propertyId: 'p_lofts', category: 'basement_storage', title: 'Hall closet storage (20 sq ft)',
      quantity: 1, size: { sqft: 20 }, rates: { weekly: 15, monthly: 40 }, amenities: ['Climate controlled'],
      access: 'By appointment.' },
    { id: 's_ana_room', propertyId: 'p_lofts', category: 'private_room', title: 'Guest room with ensuite', quantity: 1,
      rates: { daily: 95, weekly: 560, monthly: 1500 }, amenities: ['Private bath', 'Stadium view', 'Wi-Fi'],
      access: 'Front desk has your key.' },

    // --- Hillcrest ranch (Luis) ------------------------------------------
    { id: 's_hill_rv', propertyId: 'p_hill', category: 'rv_parking', title: 'Gravel RV & boat lot', quantity: 3,
      rates: { weekly: 70, monthly: 220, lease: 200 }, amenities: ['Up to 40 ft', 'Gated', 'Camera'],
      access: 'Gate code on the confirmation.' },
    { id: 's_hill_camp', propertyId: 'p_hill', category: 'yard_campsite', title: 'Hilltop tent site', quantity: 2,
      rates: { daily: 35, weekly: 200 }, amenities: ['Fire ring', 'Composting toilet', 'Sunset views'],
      access: 'Follow the yellow posts from the gate.' },
    { id: 's_hill_solar', propertyId: 'p_hill', category: 'rooftop_solar', title: 'Barn roof (~1,800 sq ft)', quantity: 1,
      size: { sqft: 1800 }, rates: { infrastructure: 2800 }, description: 'Metal roof, 2021. ~30 kW potential.',
      specs: { 'Usable roof': '1,800 sq ft', 'Est. system': '30 kW', Faces: 'South / southwest', 'Roof installed': '2021 (metal)', 'Electrical service': '400 A', Utility: 'SCE' },
      amenities: ['Metal roof', '400A service'], access: 'Site visit scheduled after proposal.' },
    { id: 's_hill_tower', propertyId: 'p_hill', category: 'telecom_site', title: 'Hilltop antenna / sensor site', quantity: 1,
      rates: { infrastructure: 4000 }, amenities: ['Highest point in town', 'Power nearby'],
      specs: { Elevation: '1,240 ft', 'Line of sight': 'Downtown + I-215', Power: '200 A at barn, 300 ft', 'Road access': 'Gravel, 4WD not needed' }, access: 'Site visit scheduled after proposal.' },
    { id: 's_hill_charger', propertyId: 'p_hill', category: 'charger_site', title: 'Road-frontage EV charger site', quantity: 1,
      rates: { infrastructure: 1800 }, amenities: ['On a state highway', '400A service'],
      specs: { Frontage: '180 ft on Hwy 91 frontage road', 'Daily traffic': '~22,000 vehicles', 'Electrical service': '400 A, 3-phase nearby', 'Room for': '4–6 DC fast chargers' }, access: 'Site visit scheduled after proposal.' },

    // --- More everyday spaces ------------------------------------------
    { id: 's_elm_kitchen', propertyId: 'p_elm', category: 'kitchen', title: "Baker's kitchen with double oven", quantity: 1,
      rates: { hourly: 25, daily: 150, monthly: 900 }, description: 'Big island, double convection oven, stand mixer. Great for cottage-food bakers.',
      amenities: ['Double oven', 'Stand mixer', '8 ft island'], access: 'Side door code 4402; kitchen only.' },
    { id: 's_hill_pasture', propertyId: 'p_hill', category: 'pasture', title: 'Fenced horse pasture (1 acre)', quantity: 2,
      rates: { monthly: 120, lease: 100 }, description: 'Irrigated pasture with a run-in shed and water trough.',
      amenities: ['Run-in shed', 'Auto waterer', 'Trailer parking'], access: 'Ranch gate, code on the confirmation.' },
    { id: 's_lake_home', propertyId: 'p_lake', category: 'entire_home', title: 'Lakeview cottage (2 bd)', quantity: 1,
      rates: { daily: 165, weekly: 1000, monthly: 3000 }, minDuration: { daily: 2 }, description: 'Cozy cottage with river views and a private dock.',
      amenities: ['Sleeps 4', 'Kayaks', 'Fire pit', 'Dock access'], access: 'Keypad on the front door.' },
    { id: 's_lake_dock', propertyId: 'p_lake', category: 'dock_slip', title: 'Private boat slip (up to 24 ft)', quantity: 2,
      rates: { daily: 40, weekly: 220, monthly: 350, lease: 320 }, description: 'Covered slip with power and water.',
      amenities: ['Up to 24 ft', 'Shore power', 'Water'], access: 'Dock gate code on the confirmation.' },
    { id: 's_lake_court', propertyId: 'p_lake', category: 'sport_court', title: 'Lakeside pickleball court', quantity: 1,
      rates: { hourly: 20 }, eventRates: [], description: 'Lit court with paddles and balls to borrow.',
      amenities: ['Lights until 10pm', 'Paddles included'], access: 'Court gate code 1122.' },

    // --- Business side: commercial & fleet --------------------------------
    { id: 's_hill_fleet', propertyId: 'p_hill', category: 'fleet_parking', title: 'Overnight van lot (8 vans)', quantity: 8,
      rates: { monthly: 180, lease: 160 }, description: 'Lit gravel lot next to the highway on-ramp. Suits delivery vans.',
      amenities: ['Lighting', 'Camera', '2 min to highway'], access: 'Gate code issued per vehicle.',
      specs: { Spaces: '8 van-sized', Surface: 'Compacted gravel', Lighting: 'LED, dusk to dawn', 'Highway access': 'Hwy 91, 0.4 mi', 'Hours': '24/7' } },
    { id: 's_hill_sign', propertyId: 'p_hill', category: 'signage', title: 'Highway-facing sign site', quantity: 1,
      rates: { lease: 400, infrastructure: 4200 }, description: 'Road frontage facing ~22,000 cars a day.',
      amenities: ['Permitted zone', 'Power nearby'], access: 'Site visit scheduled after proposal.',
      specs: { 'Daily traffic': '~22,000 vehicles', Facing: 'Eastbound Hwy 91', 'Max sign': '12×24 ft (city code)', Power: 'Yes, 50 ft' } },
    { id: 's_oak_locker_wall', propertyId: 'p_oak', category: 'parcel_locker', title: 'Lobby wall for a parcel locker', quantity: 1,
      rates: { lease: 75, infrastructure: 900 }, description: 'Covered lobby wall by the mailboxes, open 6am–11pm.',
      amenities: ['Covered', 'Outlet nearby', 'Foot traffic'], access: 'Building manager meets the installer.',
      specs: { Wall: '10 ft wide × 8 ft tall', Power: '120 V outlet, 4 ft', Access: '6am–11pm, residents + couriers', 'Units nearby': '~400 households within 0.5 mi' } },
    { id: 's_oak_roof', propertyId: 'p_oak', category: 'rooftop_solar', title: 'Apartment flat roof (~2,400 sq ft)', quantity: 1,
      size: { sqft: 2400 }, rates: { infrastructure: 3600 }, description: 'Flat membrane roof, replaced 2020. Could host community solar for the tenants.',
      amenities: ['Flat roof', 'Roof hatch'], access: 'Site visit scheduled after proposal.',
      specs: { 'Usable roof': '2,400 sq ft', 'Est. system': '38 kW', Faces: 'Flat (tilt racks)', 'Roof installed': '2020', 'Electrical service': '600 A, 3-phase', Utility: 'Riverside Public Utilities' } },
  ];

  // Owners' own listings of the same space on other sites (demo links, not real listings).
  // The pool is deliberately cheaper on Swimply so the price beat shows up at checkout.
  const xl = (platform, slug, rates, cleaningFee = 0) => ({ platform, url: `https://www.${{ airbnb: 'airbnb.com', vrbo: 'vrbo.com', spothero: 'spothero.com', neighbor: 'neighbor.com', swimply: 'swimply.com', peerspace: 'peerspace.com' }[platform]}/demo/${slug}`,
    rates, cleaningFee, verifiedAt: '2026-10-28', demo: true });
  const cross = {
    s_maple_home: [xl('airbnb', 'maple-st-house', { daily: 225, weekly: 1400 }, 75), xl('vrbo', 'maple-st-house', { daily: 230, weekly: 1450 }, 85)],
    s_maple_driveway: [xl('spothero', 'maple-driveway', { hourly: 6, daily: 45 })],
    s_maple_bay: [xl('neighbor', 'maple-garage-bay', { monthly: 99 })],
    s_elm_pool: [xl('swimply', 'elm-saltwater-pool', { hourly: 38 })],
    s_elm_adu: [xl('airbnb', 'elm-garden-adu', { daily: 125, weekly: 760 }, 50)],
    s_elm_shop: [xl('peerspace', 'elm-woodshop', { hourly: 25, daily: 140 })],
    s_ana_room: [xl('airbnb', 'stadium-lofts-room', { daily: 89, weekly: 600 }, 20)],
    s_lake_home: [xl('airbnb', 'lakeview-cottage', { daily: 170, weekly: 1050 }, 60), xl('vrbo', 'lakeview-cottage', { daily: 175 }, 70)],
  };
  for (const s of spaces) if (cross[s.id]) s.externalListings = cross[s.id];

  const packages = [
    { id: 'pk_1a_2park', propertyId: 'p_oak', name: 'Unit 1A + 2 parking spaces',
      items: [{ spaceId: 's_oak_1a', qty: 1 }, { spaceId: 's_oak_parking', qty: 2 }],
      pricing: { type: 'fixed', rates: { monthly: 2400, lease: 2190 } } },
    { id: 'pk_1b_park_locker', propertyId: 'p_oak', name: 'Unit 1B + parking + locker (10% off)',
      items: [{ spaceId: 's_oak_1b', qty: 1 }, { spaceId: 's_oak_parking', qty: 1 }, { spaceId: 's_oak_locker', qty: 1 }],
      pricing: { type: 'percent', percent: 10 } },
    { id: 'pk_adu_park', propertyId: 'p_elm', name: 'Garden ADU + driveway spot',
      items: [{ spaceId: 's_elm_adu', qty: 1 }, { spaceId: 's_elm_adu_parking', qty: 1 }],
      pricing: { type: 'percent', percent: 5 } },
  ];

  const b = (id, renterId, hostId, items, term, start, end, status, note = '', createdAt = '2026-10-01T00:00:00Z') =>
    ({ id, renterId, hostId, items, term, start, end, status, note, packageId: null, mode: 'instant', quote: null,
      history: [{ at: createdAt, status, by: renterId }], createdAt });

  const bookings = [
    b('bk_seed_1', 'u_priya', 'u_jordan', [{ spaceId: 's_oak_1b', qty: 1 }], 'lease', '2026-09-01', '2027-09-01', 'confirmed', '', '2026-08-10T00:00:00Z'),
    b('bk_seed_2', 'u_sam', 'u_maya', [{ spaceId: 's_maple_driveway', qty: 2 }], 'daily', '2026-11-21', '2026-11-22', 'confirmed', 'Festival Saturday', '2026-10-30T00:00:00Z'),
    b('bk_seed_3', 'u_dev', 'u_maya', [{ spaceId: 's_maple_bay', qty: 1 }], 'monthly', '2026-10-01', '2027-01-01', 'confirmed', '', '2026-09-20T00:00:00Z'),
    b('bk_seed_4', 'u_kim', 'u_luis', [{ spaceId: 's_elm_garden', qty: 2 }], 'lease', '2026-09-01', '2027-03-01', 'confirmed', '', '2026-08-25T00:00:00Z'),
    b('bk_seed_5', 'u_dev', 'u_ana', [{ spaceId: 's_ana_park', qty: 1 }], 'daily', '2026-11-08', '2026-11-09', 'confirmed', 'Game day', '2026-10-28T00:00:00Z'),
    b('bk_seed_6', 'u_kim', 'u_maya', [{ spaceId: 's_maple_home', qty: 1 }], 'daily', '2026-12-18', '2026-12-21', 'pending', 'Family visit for the holidays, 4 adults.', '2026-11-01T00:00:00Z'),
    b('bk_seed_7', 'u_sam', 'u_luis', [{ spaceId: 's_elm_pool', qty: 1 }], 'hourly', '2026-10-11T19:00:00Z', '2026-10-11T22:00:00Z', 'completed', 'Birthday swim', '2026-10-02T00:00:00Z'),
    b('bk_seed_8', 'u_dev', 'u_jordan', [{ spaceId: 's_oak_ev', qty: 1 }], 'hourly', '2026-10-20T16:00:00Z', '2026-10-20T19:00:00Z', 'completed', '', '2026-10-20T00:00:00Z'),
    b('bk_seed_9', 'u_voltway', 'u_luis', [{ spaceId: 's_hill_charger', qty: 1 }], 'infrastructure', '2027-03-01', '2039-03-01', 'site_assessment', 'Planning 4 × 150 kW chargers.', '2026-10-15T00:00:00Z'),
    b('bk_seed_10', 'u_sunco', 'u_maya', [{ spaceId: 's_maple_battery', qty: 1 }], 'infrastructure', '2026-06-01', '2041-06-01', 'confirmed', 'Home battery in our VPP program.', '2026-04-02T00:00:00Z'),
  ];
  bookings.find((x) => x.id === 'bk_seed_6').mode = 'request';
  for (const id of ['bk_seed_9', 'bk_seed_10']) bookings.find((x) => x.id === id).mode = 'proposal';

  const db = { users, properties, spaces, packages, bookings, messages: [], reviews: [], saves: [{ userId: 'u_sam', spaceId: 's_elm_pool' }, { userId: 'u_sam', spaceId: 's_lake_home' }], seq: 1 };

  // Price the seed bookings the same way a real booking is priced.
  for (const bk of bookings) {
    const lines = bk.items.map((it) => priceLine(spaces.find((s) => s.id === it.spaceId), it.qty, bk.term, bk.start, bk.end));
    const q = totals(lines, bk.term, bk.start, bk.end, null);
    bk.quote = { total: q.total, rent: q.rent, serviceFee: q.serviceFee, hostPayout: q.hostPayout, packageDiscount: 0,
      deposit: q.deposit, schedule: q.schedule, lines: q.lines };
  }

  const m = (bookingId, from, text, at) => db.messages.push({ id: `m_seed_${db.messages.length + 1}`, bookingId, from, text, at });
  m('bk_seed_2', 'system', 'Booking confirmed: 2 × Driveway parking, Sat Nov 21.', '2026-10-30T00:00:00Z');
  m('bk_seed_2', 'u_sam', 'Hi Maya! Can we arrive around 8am to beat the festival traffic?', '2026-10-30T01:10:00Z');
  m('bk_seed_2', 'u_maya', 'Of course. Pull all the way up so the third spot stays free. Enjoy the fair!', '2026-10-30T02:05:00Z');
  m('bk_seed_6', 'system', 'Kim requested Whole house (3 bd), Dec 18 → Dec 21.', '2026-11-01T00:00:00Z');
  m('bk_seed_6', 'u_kim', 'Hi! Visiting my parents for the holidays. We are quiet and tidy, 4 adults, no pets.', '2026-11-01T00:02:00Z');
  m('bk_seed_7', 'system', 'Booking confirmed: Saltwater pool & patio, Oct 11, 7–10pm.', '2026-10-02T00:00:00Z');
  m('bk_seed_7', 'u_luis', 'Pool will be heated to 84°. Towels are in the cabana.', '2026-10-10T18:00:00Z');
  m('bk_seed_9', 'system', 'VoltWay Charging sent a proposal for Road-frontage EV charger site.', '2026-10-15T00:00:00Z');
  m('bk_seed_9', 'u_voltway', 'We would like to install 4 DC fast chargers. Rent is $1,800/yr plus 5% of charging revenue.', '2026-10-15T00:05:00Z');
  m('bk_seed_9', 'system', 'Proposal accepted, site assessment is next.', '2026-10-18T00:00:00Z');
  m('bk_seed_9', 'u_luis', 'Site visit any weekday morning works. Gate code 9191.', '2026-10-18T02:00:00Z');

  const r = (spaceId, by, rating, text, at, bookingId = null) => db.reviews.push({ id: `r_seed_${db.reviews.length + 1}`, spaceId, bookingId, by, rating, text, at });
  r('s_maple_driveway', 'u_dev', 5, 'Walked to the fair in 5 minutes. Way better than the $40 lots.', '2025-08-18');
  r('s_maple_driveway', 'u_kim', 5, 'Easy in, easy out. Maya even left water bottles out.', '2025-08-19');
  r('s_maple_driveway', 'u_priya', 4, 'Spot was a bit tight for my truck but worked.', '2026-03-02');
  r('s_maple_backyard', 'u_kim', 5, 'Hosted a 20-person birthday here. The string lights are magic.', '2026-06-12');
  r('s_maple_backyard', 'u_sam', 5, 'Perfect for a fire pit night with friends.', '2026-09-05');
  r('s_maple_bay', 'u_dev', 5, 'Dry, clean, and I can get to my stuff any evening.', '2026-10-25');
  r('s_elm_pool', 'u_kim', 5, 'Warm pool, great host, kids loved it.', '2026-09-12');
  r('s_elm_pool', 'u_dev', 4, 'Lovely, a little leafy.', '2026-07-30');
  r('s_elm_shop', 'u_kim', 5, 'Luis gave a great safety walkthrough. Built my bookshelf in a day.', '2026-05-20');
  r('s_ana_park', 'u_dev', 5, 'Two blocks from the gate and no post-game traffic jam.', '2026-09-14');
  r('s_ana_park', 'u_priya', 5, 'Secure and covered. Will book every home game.', '2026-10-04');
  r('s_ana_room', 'u_kim', 4, 'Comfy room with a view of the stadium lights.', '2026-08-02');
  r('s_hill_camp', 'u_sam', 5, 'Best sunset in the county. Bring a warm sleeping bag.', '2026-10-05');
  r('s_oak_2a', 'u_dev', 4, 'Clean furnished studio, quick check-in.', '2026-07-11');
  r('s_lake_home', 'u_priya', 5, 'Morning coffee on the dock was unreal. Kayaks were a bonus.', '2026-08-21');
  r('s_lake_home', 'u_dev', 5, 'Spotless and so peaceful.', '2026-09-30');
  r('s_lake_dock', 'u_kim', 5, 'Easy slip, Rosa was super helpful.', '2026-07-04');
  r('s_elm_kitchen', 'u_priya', 5, 'Baked 12 dozen cookies for my market stall here. Ovens are amazing.', '2026-10-02');

  return db;
}
