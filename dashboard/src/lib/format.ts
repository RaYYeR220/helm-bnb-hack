// Number formatting helpers — all display numbers derive from artifacts.

export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

export function signedPct(x: number, digits = 1): string {
  const s = (x * 100).toFixed(digits);
  return x >= 0 ? `+${s}%` : `${s}%`;
}

export function num(x: number, digits = 2): string {
  return x.toFixed(digits);
}

export function signedNum(x: number, digits = 2): string {
  return x >= 0 ? `+${x.toFixed(digits)}` : x.toFixed(digits);
}

export function usd(x: number): string {
  return `$${Math.round(x).toLocaleString('en-US')}`;
}

// Short month-year label for dense time axes.
export function shortDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export function monthYear(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}
