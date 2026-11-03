# Everyspace: product spec (working name)

Everyspace is a marketplace for renting out **any part of a property** for **any length of time**. You could rent out a backyard for one night, a driveway spot for fair weekend, a garage corner for a month, a whole house like a vacation rental, a front yard for a garden, or a roof for 20 years to someone who pays for solar panels on it.

It also handles **multi-unit buildings**. A renter can take just an apartment, or an apartment plus two parking spaces and a storage locker, under rules the owner sets.

This document covers what can be rented and how renting works. It comes before the build. The prototype in `src/` implements the core rules described here.

---

## 1. What can be rented

Every listing is a **space**, and every space has a **category**. The category sets which rental lengths are allowed, how the space is measured and priced, the default booking mode, and the checklist a host has to complete before going live.

Rental lengths (terms):

| Term | Unit | Typical use |
|---|---|---|
| Hourly | hour | Backyard party, pool, studio session, EV charging |
| Nightly / daily | day | Vacation stay, event-day parking, overnight camping |
| Weekly | week | Longer stay, temporary storage |
| Month-to-month | month | Parking, storage, garden plot, room |
| Fixed lease | month, 6–24 mo | Apartment, ADU, long-term parking |
| Infrastructure agreement | year, 5–25 yr | Rooftop solar, battery, charger, antenna |

### Catalog

**Living**

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Entire home | daily, weekly, monthly, lease | whole | Works like Airbnb. Needs a short-term-rental permit and occupancy tax where the city requires them. |
| Apartment / unit | daily, monthly, lease | whole | A unit in a multi-unit building. It can anchor add-ons (§3). |
| ADU / guest house | daily, weekly, monthly, lease | whole | |
| Private room | daily, weekly, monthly, lease | whole | Shared common areas are listed in the house rules. |

**Outdoor and activity**

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Backyard | hourly, daily | whole | Parties, gatherings, dog play, photo shoots. Noise curfew and guest cap are required. |
| Yard campsite | daily, weekly | site | Tent or small RV overnight. Requires restroom access. |
| Pool | hourly | whole | Lifeguard and waiver rules. Host must confirm insurance. |
| Workspace / studio / workshop | hourly, daily, monthly | whole | Home office, music room, wood shop. |
| Filming / photo location | hourly, daily | whole | Always request-to-book. City film permit may be needed. |

**Parking**

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Parking spot | hourly, daily, weekly, monthly, lease | spot (quantity) | Driveway, garage, or carport. **Event pricing** covers fair, stadium, and parade days. |
| RV / boat / trailer parking | weekly, monthly, lease | spot | Length limit and HOA check. |
| EV charging | hourly, daily, monthly | charger | Host's own charger. Price covers time and electricity. |

**Storage**

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Garage storage | weekly, monthly, lease | sq ft (quantity of bays) | Hazardous materials are not allowed. Host sets access hours. |
| Attic storage | monthly, lease | sq ft | Weight limit and ladder access must be disclosed. |
| Basement / closet / shed | weekly, monthly, lease | sq ft | |

**Land and growing**

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Garden plot | monthly, lease | sq ft (quantity of plots) | Front or back yard. Water access, HOA front-yard rules, and chemical policy. |
| Beehive / small-ag site | monthly, lease | site | Local apiary rules apply. |

**Energy and infrastructure.** These spaces are rented to companies, not people, through long agreements.

| Category | Terms | Measured by | Notes |
|---|---|---|---|
| Rooftop solar | infrastructure, 10–25 yr | sq ft of roof | A third party pays for, owns, and maintains the panels and pays the owner rent or a share of the power. Requires a roof-age and structural check, utility interconnection (net metering, community solar, or virtual net metering), a removal and re-roof clause, and a recorded lease or easement. |
| Battery site | infrastructure, 5–20 yr | site | Garage wall, side yard, or pad. Requires fire code setbacks (NFPA 855), a utility or virtual-power-plant program, and permits. |
| Public EV charger site | infrastructure, 5–15 yr | site | A third party installs a charger in a driveway or curb cut. |
| Telecom / sensor site | infrastructure, 5–25 yr | site | Small-cell antenna, mesh node, or weather station. |

**Later:** signage and billboards (heavily regulated), dock or slip space, horse paddock, and laundry or kitchen time.

**Not allowed:** public streets and curbs, shared HOA common areas the host doesn't control, and any space whose required permit the host can't show.

---

## 2. How it works

### Properties and spaces

```
Host ─┬─ Property (address, type, rules, HOA y/n, insurance)
      └─ Space (category, quantity, rates per term, availability, parent?)
            └─ Space (child) ...
```

* **Quantity.** One listing can stand for several identical units, such as 4 driveway spots, 3 garage bays, or 8 storage lockers. Bookings use up quantity, and the listing stays available until all units are taken.
* **Hierarchy (parent/child).** A space can sit inside another one. For example, a garage bay is inside the garage, a room is inside the house, and an apartment is inside the building.
  * Booking a parent blocks all of its children. If the whole house is booked, its rooms and backyard are not.
  * Booking any child blocks the parent as a whole. Rooms 1 and 2 can be rented separately, but then the whole house can't be.
  * Structural containers such as a building or a garage can be marked **not rentable**. They organize the listing and never block anything.
* **Explicit conflicts.** Some spaces overlap without one sitting inside the other, such as "driveway parking" and "RV parking" in the same driveway. A host can mark them as conflicting.
* **Independent spaces.** A roof leased for solar does not conflict with the house being rented nightly. It isn't a child of the house, so the two never block each other.

### Pricing

* There is one rate per allowed term, such as $12/hour, $45/day, or $180/month. Weekly stays use the weekly rate plus extra days at the daily rate. Partial months are prorated at the monthly rate divided by 30.
* **Event pricing.** Hosts can set date-range overrides, for example "County Fair, Aug 14–17, $40/day" for a driveway spot. When a booking covers those dates, the override replaces the daily rate for those days.
* **Add-on price.** A space can cost less when it is attached to an anchor rental (§3).
* **Packages** have their own price, either a fixed amount per period or a % discount (§3).
* **Fees (prototype values).** Renters pay a 10% service fee, and hosts pay 3%. Long and infrastructure agreements are charged per period rather than all at once.
* **Deposits** are set by category, such as a whole home or storage, and are held, not charged.

### Booking modes

| Mode | When | Flow |
|---|---|---|
| Instant | Short, low-risk rentals: parking, storage, hourly yard | Pay, then **confirmed** |
| Request | Whole homes, filming, leases, anything the host flags | **pending** (dates held 24h), then host approves (**confirmed**) or declines |
| Proposal | Infrastructure agreements | **proposed**, then **site assessment**, then **contract**, then **confirmed**. Rent starts when the system is commissioned. |

A cart with several items uses its strictest mode. For example, instant parking plus a request-to-book apartment becomes a request.

States: `pending | proposed | site_assessment | contract | confirmed | active | completed | declined | cancelled`. Pending and proposal-stage bookings hold the space, so nobody can double-book while the host decides.

### Payments schedule

* **Hourly, daily, or weekly:** the full amount is charged at booking. The host is paid out 24h after check-in.
* **Month-to-month or lease:** the first period plus the deposit is charged at booking, then autopay each period. Month-to-month ends with 30 days' notice.
* **Infrastructure:** annual (or monthly) rent paid by the company. The platform takes its fee on each payment.

### Access and handoff

Each space has access instructions that are revealed after confirmation, such as a gate code, a lockbox, or a smart-lock code generated per booking. It also has access hours (storage 7am–9pm, for example) and a check-in/out photo log, which is used for disputes about storage contents and yard condition.

---

## 3. Multi-unit buildings, add-ons, and packages

The owner of an apartment building lists the **building** as a non-rentable container. Inside it go the **units**, a **parking pool** (for example 12 spots), a **storage locker pool**, and maybe EV chargers. The owner then decides how each one can be rented:

| Rental policy | Meaning | Example |
|---|---|---|
| `standalone` | Anyone can rent it alone | Apartment 2A, EV charger by the hour |
| `addon` | Can be rented only with an anchor | Garage parking only for building tenants |
| `both` | Rentable alone, with a lower price as an add-on | Storage locker: $90/mo alone or $60/mo with a unit |

**Add-on rules** are set on the add-on space:

* `anchors`: which spaces can carry this add-on, such as "any unit in this building" (by category) or specific unit IDs.
* `maxPerAnchor`: the most of this add-on one anchor can carry, such as 2 parking spaces per apartment.
* The anchor can be in the **same cart** or be an **existing booking** of the same renter that covers the whole add-on period. A tenant who signed a lease in March can add a second parking spot in June.
* The add-on can't outlast the anchor. If the lease ends, the add-on has to end with it.

**Packages** are bundles defined by the host, like "Unit 1A + 2 parking" at $2,650/mo fixed or "Any unit + locker" at 10% off. A package is listed as one item in search results. When booked, it becomes the underlying spaces, so availability and conflicts are still checked for each space.

That gives a renter these choices:

1. Apartment only.
2. Apartment plus 1 or 2 parking spaces (add-ons, capped at 2).
3. A package, such as Apartment 1A plus 2 parking at a fixed price.
4. Later, add a locker to their existing lease.
5. A non-tenant can rent a locker alone at the standalone price, but cannot rent parking, which is add-on only.

The same model works for a single house. For example, an owner can rent the ADU and offer the driveway spot only to whoever rents the ADU.

---

## 4. Trust, safety, and legal

* **Host checklist per category** must be complete before a listing goes live: permits, HOA approval, insurance, and safety items such as smoke/CO detectors, pool fencing, NFPA 855, and roof assessment.
* **Identity verification** is required for both sides. Leases and infrastructure agreements also need a business or credit check.
* **Agreements.** Short rentals use platform terms of service. Leases use a state-specific lease template. Infrastructure uses a recorded lease or easement with removal, insurance, and indemnity clauses.
* **Insurance.** A host protection policy for short rentals. Infrastructure partners must name the owner as additional insured.
* **Reviews** in both directions, plus disputes backed by the check-in/out photos.
* **Local rules engine (later).** Look up the address to see short-term-rental caps, parking ordinances, and garden and front-yard rules, then turn off terms that aren't allowed.

---

## 5. Build plan

| Phase | Scope |
|---|---|
| **0: prototype (this commit)** | Catalog, data model, availability with quantity, hierarchy, and conflicts, add-on and package rules, pricing with event rates, booking modes and states, JSON API, demo web UI, tests |
| 1: MVP | Real auth, Postgres, Stripe Connect payouts, photo uploads, map search, messaging, notifications |
| 2: Trust | ID verification, reviews, check-in/out photo log, disputes, insurance partner |
| 3: Long-term | Lease templates and e-sign, autopay, move-in/out, maintenance requests |
| 4: Infrastructure marketplace | Solar, battery, and charger partner portal, roof and site assessment scheduling, rent from commissioning, revenue share |
| 5: Local rules engine | Permit and ordinance lookup by address, automatic term limits |
