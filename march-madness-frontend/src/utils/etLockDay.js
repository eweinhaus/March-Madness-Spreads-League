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
    hourCycle: 'h23',  // Ensure midnight is hour 0, not 24
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

/**
 * Football week bounds: Wednesday 00:00 ET → next Wednesday 00:00 ET
 * (matches backend get_week_bounds).
 * 
 * @param {string|Date} gameDateIso
 * @returns {{ weekStart: Date, weekEnd: Date }}
 */
export function getWeekBounds(gameDateIso) {
  const t = new Date(gameDateIso).getTime();
  const { year: y, month: mo, day: d } = nyParts(t);
  
  // Find the most recent Wednesday 00:00 ET on or before this date
  // getDay(): 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
  const localDate = new Date(Date.UTC(y, mo - 1, d));
  const dayOfWeek = localDate.getUTCDay();
  const daysSinceWed = (dayOfWeek + 4) % 7; // Days since last Wednesday
  
  const weekStartDate = new Date(Date.UTC(y, mo - 1, d));
  weekStartDate.setUTCDate(weekStartDate.getUTCDate() - daysSinceWed);
  
  const wy = weekStartDate.getUTCFullYear();
  const wm = weekStartDate.getUTCMonth() + 1;
  const wd = weekStartDate.getUTCDate();
  
  const weekStartMs = utcMillisForNyWallClock(wy, wm, wd, 0, 0, 0);
  
  // Next Wednesday (7 days later)
  const nextWeekDate = new Date(weekStartDate);
  nextWeekDate.setUTCDate(nextWeekDate.getUTCDate() + 7);
  const nwy = nextWeekDate.getUTCFullYear();
  const nwm = nextWeekDate.getUTCMonth() + 1;
  const nwd = nextWeekDate.getUTCDate();
  const weekEndMs = utcMillisForNyWallClock(nwy, nwm, nwd, 0, 0, 0);
  
  return { weekStart: new Date(weekStartMs), weekEnd: new Date(weekEndMs) };
}

export function sameWeek(dateIsoA, dateIsoB) {
  const a = getWeekBounds(dateIsoA).weekStart.getTime();
  const b = getWeekBounds(dateIsoB).weekStart.getTime();
  return a === b;
}

/**
 * Get the current football week key (week_0 through week_14).
 * 
 * Football season: 2026-08-26 (Wed Week 0 start) through 2026-12-09 (end of Week 14).
 * Before season start → clamp to week_0. After season end → clamp to week_14.
 * Uses ET civil date math (handles DST correctly).
 * 
 * @returns {string} Week key (e.g., "week_3")
 */
export function getCurrentFootballWeek() {
  const now = Date.now();
  
  // Football season starts Wed 2026-08-26 00:00 ET
  const seasonStartMs = utcMillisForNyWallClock(2026, 8, 26, 0, 0, 0);
  
  // Before season starts → clamp to week_0
  if (now < seasonStartMs) {
    return 'week_0';
  }
  
  // Find which week contains now by computing week bounds for each week
  // Use ET civil date increments (handles DST correctly)
  for (let i = 0; i < 15; i++) {
    // Start date for week i: 2026-08-26 + i weeks (ET civil)
    const weekStartDate = new Date(Date.UTC(2026, 7, 26)); // Aug 26 UTC (adjusted below)
    weekStartDate.setUTCDate(weekStartDate.getUTCDate() + (i * 7));
    
    const weekStartYear = weekStartDate.getUTCFullYear();
    const weekStartMonth = weekStartDate.getUTCMonth() + 1;
    const weekStartDay = weekStartDate.getUTCDate();
    
    const weekStartMs = utcMillisForNyWallClock(weekStartYear, weekStartMonth, weekStartDay, 0, 0, 0);
    
    // End date for week i: start + 7 days (ET civil)
    const weekEndDate = new Date(Date.UTC(2026, 7, 26));
    weekEndDate.setUTCDate(weekEndDate.getUTCDate() + ((i + 1) * 7));
    
    const weekEndYear = weekEndDate.getUTCFullYear();
    const weekEndMonth = weekEndDate.getUTCMonth() + 1;
    const weekEndDay = weekEndDate.getUTCDate();
    
    const weekEndMs = utcMillisForNyWallClock(weekEndYear, weekEndMonth, weekEndDay, 0, 0, 0);
    
    if (now >= weekStartMs && now < weekEndMs) {
      return `week_${i}`;
    }
  }
  
  // After season ends → clamp to week_14
  return 'week_14';
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

/**
 * Group picks by football week for Overall view.
 * Uses ET civil date math (handles DST correctly).
 * 
 * @param {Array} picks - Array of pick objects with game_date
 * @returns {Object} Map of week keys to {key, label, picks} objects
 */
export function groupPicksByWeek(picks) {
  const weekLabels = [
    "CFB Week 0",
    "CFB Week 1",
    "CFB Week 2, NFL Week 1",
    "CFB Week 3, NFL Week 2",
    "CFB Week 4, NFL Week 3",
    "CFB Week 5, NFL Week 4",
    "CFB Week 6, NFL Week 5",
    "CFB Week 7, NFL Week 6",
    "CFB Week 8, NFL Week 7",
    "CFB Week 9, NFL Week 8",
    "CFB Week 10, NFL Week 9",
    "CFB Week 11, NFL Week 10",
    "CFB Week 12, NFL Week 11",
    "CFB Week 13, NFL Week 12",
    "CFB Week 14, NFL Week 13",
  ];
  
  const weeks = {};
  
  for (let i = 0; i < 15; i++) {
    // Start date for week i: 2026-08-26 + i weeks (ET civil)
    const weekStartDate = new Date(Date.UTC(2026, 7, 26)); // Aug 26
    weekStartDate.setUTCDate(weekStartDate.getUTCDate() + (i * 7));
    
    const weekStartYear = weekStartDate.getUTCFullYear();
    const weekStartMonth = weekStartDate.getUTCMonth() + 1;
    const weekStartDay = weekStartDate.getUTCDate();
    
    const weekStartMs = utcMillisForNyWallClock(weekStartYear, weekStartMonth, weekStartDay, 0, 0, 0);
    
    // End date for week i: start + 7 days (ET civil)
    const weekEndDate = new Date(Date.UTC(2026, 7, 26));
    weekEndDate.setUTCDate(weekEndDate.getUTCDate() + ((i + 1) * 7));
    
    const weekEndYear = weekEndDate.getUTCFullYear();
    const weekEndMonth = weekEndDate.getUTCMonth() + 1;
    const weekEndDay = weekEndDate.getUTCDate();
    
    const weekEndMs = utcMillisForNyWallClock(weekEndYear, weekEndMonth, weekEndDay, 0, 0, 0);
    
    const weekPicks = picks.filter((p) => {
      const pickTime = new Date(p.game_date).getTime();
      return pickTime >= weekStartMs && pickTime < weekEndMs;
    });
    
    weeks[`week_${i}`] = {
      key: `week_${i}`,
      label: weekLabels[i],
      picks: weekPicks,
    };
  }
  
  return weeks;
}
