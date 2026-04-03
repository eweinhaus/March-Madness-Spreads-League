/**
 * Lock-of-the-day: each period runs 3:00 AM ET → next day 3:00 AM ET
 * (matches backend get_lock_day_bounds).
 */
const NY = 'America/New_York';

function nyParts(ms) {
  const f = new Intl.DateTimeFormat('en-US', {
    timeZone: NY,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const o = {};
  for (const x of f.formatToParts(new Date(ms))) {
    if (x.type !== 'literal') o[x.type] = parseInt(x.value, 10);
  }
  return o;
}

/** UTC millis for a given civil date/time in America/New_York */
function utcMillisForNyWallClock(y, mo, d, hour, minute, sec = 0) {
  const base = Date.UTC(y, mo - 1, d, 12, 0, 0);
  for (let deltaMin = -15 * 60; deltaMin <= 15 * 60; deltaMin++) {
    const ms = base + deltaMin * 60 * 1000;
    const p = nyParts(ms);
    if (
      p.year === y &&
      p.month === mo &&
      p.day === d &&
      p.hour === hour &&
      p.minute === minute &&
      p.second === sec
    ) {
      return ms;
    }
  }
  return base;
}

/**
 * @param {string|Date} gameDateIso
 * @returns {{ dayStart: Date, dayEnd: Date }}
 */
export function getLockDayBounds(gameDateIso) {
  const t = new Date(gameDateIso).getTime();
  let { year: y, month: mo, day: d, hour: h } = nyParts(t);
  if (h < 3) {
    const jd = new Date(Date.UTC(y, mo - 1, d));
    jd.setUTCDate(jd.getUTCDate() - 1);
    y = jd.getUTCFullYear();
    mo = jd.getUTCMonth() + 1;
    d = jd.getUTCDate();
  }
  const dayStartMs = utcMillisForNyWallClock(y, mo, d, 3, 0, 0);
  const next = new Date(Date.UTC(y, mo - 1, d));
  next.setUTCDate(next.getUTCDate() + 1);
  const ny = next.getUTCFullYear();
  const nm = next.getUTCMonth() + 1;
  const nd = next.getUTCDate();
  const dayEndMs = utcMillisForNyWallClock(ny, nm, nd, 3, 0, 0);
  return { dayStart: new Date(dayStartMs), dayEnd: new Date(dayEndMs) };
}

export function sameLockDay(dateIsoA, dateIsoB) {
  const a = getLockDayBounds(dateIsoA).dayStart.getTime();
  const b = getLockDayBounds(dateIsoB).dayStart.getTime();
  return a === b;
}

/** Tip-offs before this instant (ET Mar 24 2026 00:00) = first half */
export function getSecondHalfStartDate() {
  return new Date(utcMillisForNyWallClock(2026, 3, 24, 0, 0, 0));
}

export function groupPicksByTournamentHalf(picks) {
  const boundary = getSecondHalfStartDate().getTime();
  return {
    first_half: {
      key: 'first_half',
      label: 'First Half (through Mar 23)',
      picks: picks.filter((p) => new Date(p.game_date).getTime() < boundary),
    },
    second_half: {
      key: 'second_half',
      label: 'Second Half (Mar 24+)',
      picks: picks.filter((p) => new Date(p.game_date).getTime() >= boundary),
    },
  };
}
