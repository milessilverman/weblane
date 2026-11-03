// Demo data: a single-family house near a fairground, and a small apartment building.

export function seed() {
  const users = [
    { id: 'u_maya', name: 'Maya (host, house)' },
    { id: 'u_jordan', name: 'Jordan (host, apartments)' },
    { id: 'u_sam', name: 'Sam (renter)' },
    { id: 'u_priya', name: 'Priya (renter)' },
    { id: 'u_sunco', name: 'SunCo Solar (infrastructure partner)' },
  ];

  const properties = [
    { id: 'p_maple', hostId: 'u_maya', title: '412 Maple St', city: 'Riverside', type: 'single_family',
      hoa: false, notes: '3 blocks from the county fairgrounds.' },
    { id: 'p_oak', hostId: 'u_jordan', title: 'Oak Court Apartments', city: 'Riverside', type: 'multi_unit',
      hoa: false, notes: '6-unit building with a 12-space garage and storage lockers.' },
  ];

  const harvest = { name: 'Harvest Festival', start: '2026-11-20', end: '2026-11-22' };

  const spaces = [
    // --- 412 Maple St ---------------------------------------------------
    { id: 's_maple_home', propertyId: 'p_maple', category: 'entire_home', title: 'Whole house (3 bd)',
      quantity: 1, rates: { daily: 210, weekly: 1300, monthly: 3900, lease: 3600 }, minDuration: { daily: 2 },
      description: 'Entire 3-bedroom home. Includes backyard.' },
    { id: 's_maple_backyard', propertyId: 'p_maple', parentId: 's_maple_home', category: 'backyard',
      title: 'Backyard with fire pit', quantity: 1, rates: { hourly: 35, daily: 180 },
      eventRates: [{ ...harvest, hourly: 55 }], description: 'Lawn, string lights, fire pit. Quiet hours after 10pm.' },
    { id: 's_maple_room', propertyId: 'p_maple', parentId: 's_maple_home', category: 'private_room',
      title: 'Back bedroom', quantity: 1, rates: { daily: 75, weekly: 450, monthly: 1300 } },
    { id: 's_maple_driveway', propertyId: 'p_maple', category: 'parking_spot', title: 'Driveway parking',
      quantity: 3, rates: { hourly: 4, daily: 15, weekly: 80, monthly: 140 },
      eventRates: [{ ...harvest, daily: 40, hourly: 12 }], conflictsWith: ['s_maple_rv'],
      description: 'Three uncovered spots, 5-minute walk to the fairgrounds.' },
    { id: 's_maple_rv', propertyId: 'p_maple', category: 'rv_parking', title: 'RV pad (uses the driveway)',
      quantity: 1, rates: { weekly: 120, monthly: 380 }, description: 'Up to 30 ft. Takes over the whole driveway.' },
    { id: 's_maple_garage', propertyId: 'p_maple', category: 'building', title: 'Detached garage', rentable: false, quantity: 1 },
    { id: 's_maple_bay', propertyId: 'p_maple', parentId: 's_maple_garage', category: 'garage_storage',
      title: 'Garage storage bay (100 sq ft)', quantity: 3, size: { sqft: 100 },
      rates: { weekly: 30, monthly: 95, lease: 85 }, description: 'Shelved bays, access 7am–9pm.' },
    { id: 's_maple_attic', propertyId: 'p_maple', category: 'attic_storage', title: 'Attic storage (80 sq ft)',
      quantity: 1, size: { sqft: 80 }, rates: { monthly: 55, lease: 50 }, description: 'Pull-down ladder, boxes under 40 lb.' },
    { id: 's_maple_garden', propertyId: 'p_maple', category: 'garden_plot', title: 'Front-yard garden plot (10×10)',
      quantity: 2, size: { sqft: 100 }, rates: { monthly: 30, lease: 25 }, description: 'Hose bib included. Organic only.' },
    { id: 's_maple_roof', propertyId: 'p_maple', category: 'rooftop_solar', title: 'South-facing roof (~600 sq ft)',
      quantity: 1, size: { sqft: 600 }, rates: { infrastructure: 1100 },
      description: '2019 roof. ~9 kW potential. Partner owns panels, pays annual rent.' },
    { id: 's_maple_battery', propertyId: 'p_maple', category: 'battery_site', title: 'Side-yard battery pad',
      quantity: 1, rates: { infrastructure: 600 }, description: '4×8 ft concrete pad, 12 ft from the house.' },

    // --- Oak Court Apartments ---------------------------------------------
    { id: 's_oak_bldg', propertyId: 'p_oak', category: 'building', title: 'Oak Court building', rentable: false, quantity: 1 },
    { id: 's_oak_1a', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 1A (1 bd)',
      quantity: 1, rates: { monthly: 2150, lease: 1950 } },
    { id: 's_oak_1b', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 1B (2 bd)',
      quantity: 1, rates: { monthly: 2750, lease: 2500 } },
    { id: 's_oak_2a', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'apartment_unit', title: 'Unit 2A (studio, furnished)',
      quantity: 1, rates: { daily: 140, monthly: 1900, lease: 1700 }, minDuration: { daily: 3 } },
    { id: 's_oak_parking', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'parking_spot', title: 'Garage parking space',
      quantity: 12, policy: 'addon', rates: { daily: 20, monthly: 150, lease: 140 },
      addon: { anchorCategories: ['apartment_unit'], maxPerAnchor: 2 },
      description: 'Tenants only — up to 2 per unit.' },
    { id: 's_oak_locker', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'basement_storage', title: 'Storage locker (5×5)',
      quantity: 8, policy: 'both', size: { sqft: 25 },
      rates: { weekly: 30, monthly: 90, lease: 80 }, addonRates: { monthly: 60, lease: 55 },
      addon: { anchorCategories: ['apartment_unit'], maxPerAnchor: 1 },
      description: '$90/mo for anyone, $60/mo for tenants (1 per unit).' },
    { id: 's_oak_ev', propertyId: 'p_oak', parentId: 's_oak_bldg', category: 'ev_charging', title: 'Level 2 EV charger',
      quantity: 2, rates: { hourly: 6, daily: 30 }, description: 'Open to the public 6am–11pm.' },
  ];

  const packages = [
    { id: 'pk_1a_2park', propertyId: 'p_oak', name: 'Unit 1A + 2 parking spaces',
      items: [{ spaceId: 's_oak_1a', qty: 1 }, { spaceId: 's_oak_parking', qty: 2 }],
      pricing: { type: 'fixed', rates: { monthly: 2400, lease: 2190 } } },
    { id: 'pk_1b_park_locker', propertyId: 'p_oak', name: 'Unit 1B + parking + locker (10% off)',
      items: [{ spaceId: 's_oak_1b', qty: 1 }, { spaceId: 's_oak_parking', qty: 1 }, { spaceId: 's_oak_locker', qty: 1 }],
      pricing: { type: 'percent', percent: 10 } },
  ];

  const bookings = [
    { id: 'bk_seed_1', renterId: 'u_priya', hostId: 'u_jordan', items: [{ spaceId: 's_oak_1b', qty: 1 }],
      term: 'lease', start: '2026-09-01', end: '2027-09-01', mode: 'request', status: 'confirmed', packageId: null,
      quote: null, note: '', history: [{ at: '2026-08-10T00:00:00Z', status: 'confirmed', by: 'u_jordan' }], createdAt: '2026-08-10T00:00:00Z' },
    { id: 'bk_seed_2', renterId: 'u_sam', hostId: 'u_maya', items: [{ spaceId: 's_maple_driveway', qty: 2 }],
      term: 'daily', start: '2026-11-21', end: '2026-11-22', mode: 'instant', status: 'confirmed', packageId: null,
      quote: null, note: 'Festival Saturday', history: [{ at: '2026-10-30T00:00:00Z', status: 'confirmed', by: 'u_sam' }], createdAt: '2026-10-30T00:00:00Z' },
  ];

  return { users, properties, spaces, packages, bookings, seq: 1 };
}
