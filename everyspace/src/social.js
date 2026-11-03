// Messages between renter and host (one thread per booking), reviews, and display status.
import { BookingError } from './booking.js';
import { toMs } from './time.js';

// Status as a person would describe it right now: a confirmed booking whose dates have passed is completed.
export function effectiveStatus(b, now = Date.now()) {
  if (b.status !== 'confirmed' && b.status !== 'active') return b.status;
  if (toMs(b.end) <= toMs(now)) return 'completed';
  if (toMs(b.start) <= toMs(now)) return 'active';
  return 'confirmed';
}

function participant(db, bookingId, userId) {
  const b = db.bookings.find((x) => x.id === bookingId);
  if (!b) throw new BookingError('Booking not found');
  if (userId !== b.renterId && userId !== b.hostId) throw new BookingError('Only the renter and host can see this conversation');
  return b;
}

export function systemMessage(db, bookingId, text, { now = new Date().toISOString(), newId }) {
  const msg = { id: newId('m'), bookingId, from: 'system', text, at: now };
  db.messages.push(msg);
  return msg;
}

export function postMessage(db, bookingId, from, text, { now = new Date().toISOString(), newId }) {
  participant(db, bookingId, from);
  const clean = String(text ?? '').trim();
  if (!clean) throw new BookingError('Message is required');
  if (clean.length > 2000) throw new BookingError('Message must be under 2000 characters');
  const msg = { id: newId('m'), bookingId, from, text: clean, at: now };
  db.messages.push(msg);
  return msg;
}

export function messagesFor(db, bookingId, userId) {
  participant(db, bookingId, userId);
  return db.messages.filter((m) => m.bookingId === bookingId).sort((a, b) => (a.at < b.at ? -1 : 1));
}

export function threadsFor(db, userId) {
  return db.bookings
    .filter((b) => b.renterId === userId || b.hostId === userId)
    .map((b) => {
      const msgs = db.messages.filter((m) => m.bookingId === b.id).sort((x, y) => (x.at < y.at ? -1 : 1));
      const otherId = b.renterId === userId ? b.hostId : b.renterId;
      const space = db.spaces.find((s) => s.id === b.items[0].spaceId);
      return { bookingId: b.id, other: db.users.find((u) => u.id === otherId), space: { id: space.id, title: space.title, category: space.category },
        last: msgs.at(-1) ?? null, count: msgs.length, status: b.status };
    })
    .filter((t) => t.last)
    .sort((a, b) => (a.last.at < b.last.at ? 1 : -1));
}

export function canReview(db, b, userId, now = Date.now()) {
  return b.renterId === userId && effectiveStatus(b, now) === 'completed' && !db.reviews.some((r) => r.bookingId === b.id);
}

export function addReview(db, bookingId, by, rating, text, { now = new Date().toISOString(), newId }) {
  const b = db.bookings.find((x) => x.id === bookingId);
  if (!b) throw new BookingError('Booking not found');
  if (b.renterId !== by) throw new BookingError('Only the renter can review this booking');
  if (effectiveStatus(b, now) !== 'completed') throw new BookingError("You can review once the booking has ended");
  if (db.reviews.some((r) => r.bookingId === bookingId)) throw new BookingError('You already reviewed this booking');
  const stars = Number(rating);
  if (!Number.isInteger(stars) || stars < 1 || stars > 5) throw new BookingError('Rating must be 1–5 stars');
  const review = { id: newId('r'), spaceId: b.items[0].spaceId, bookingId, by, rating: stars, text: String(text ?? '').trim().slice(0, 1000), at: now.slice(0, 10) };
  db.reviews.push(review);
  return review;
}

export function ratingFor(db, spaceId) {
  const rs = db.reviews.filter((r) => r.spaceId === spaceId);
  if (!rs.length) return { avg: null, count: 0 };
  return { avg: Math.round((rs.reduce((s, r) => s + r.rating, 0) / rs.length) * 10) / 10, count: rs.length };
}
