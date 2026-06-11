import type { RegimeArtifact, RegimeLabel, StrategyKey } from './types';

export interface MergedRow {
  date: string;
  t: number; // epoch ms (numeric x for ReferenceArea math)
  regime: RegimeLabel | null;
  [strategy: string]: number | string | null;
}

export interface RegimeBand {
  from: string;
  to: string;
  regime: RegimeLabel;
}

// Build a single row-per-date dataset with one column per strategy equity,
// plus a regime label per date (joined from the regime_path, which starts
// later than the equity curves — earlier dates get null/"unclassified").
export function buildEquityDataset(reg: RegimeArtifact): {
  rows: MergedRow[];
  bands: RegimeBand[];
  strategies: StrategyKey[];
} {
  const strategies = Object.keys(reg.strategies) as StrategyKey[];
  const regimeByDate = new Map<string, RegimeLabel>();
  for (const p of reg.regime_path) regimeByDate.set(p.date, p.regime);

  // Union of all equity dates (they share the same axis, but be safe).
  const dateSet = new Set<string>();
  for (const s of strategies) {
    for (const e of reg.strategies[s].equity) dateSet.add(e.date);
  }
  const dates = Array.from(dateSet).sort();

  const equityMaps: Record<string, Map<string, number>> = {};
  for (const s of strategies) {
    const m = new Map<string, number>();
    for (const e of reg.strategies[s].equity) m.set(e.date, e.value);
    equityMaps[s] = m;
  }

  const rows: MergedRow[] = dates.map((date) => {
    const row: MergedRow = {
      date,
      t: Date.parse(date + 'T00:00:00Z'),
      regime: regimeByDate.get(date) ?? null,
    };
    for (const s of strategies) {
      row[s] = equityMaps[s].get(date) ?? null;
    }
    return row;
  });

  // Collapse consecutive same-regime dates into bands for the background.
  const bands: RegimeBand[] = [];
  let cur: RegimeBand | null = null;
  for (const row of rows) {
    const r = row.regime;
    if (r == null) {
      // warm-up region before the regime path begins
      if (cur && cur.regime !== 'unclassified') {
        bands.push(cur);
        cur = null;
      }
      if (!cur) cur = { from: row.date, to: row.date, regime: 'unclassified' };
      else cur.to = row.date;
      continue;
    }
    if (cur && cur.regime === r) {
      cur.to = row.date;
    } else {
      if (cur) bands.push(cur);
      cur = { from: row.date, to: row.date, regime: r };
    }
  }
  if (cur) bands.push(cur);

  return { rows, bands, strategies };
}

// Convert absolute equity ($10k base) to percent return for a cleaner axis.
export function toReturnRows(rows: MergedRow[], strategies: string[]): MergedRow[] {
  const base: Record<string, number> = {};
  for (const s of strategies) {
    const first = rows.find((r) => typeof r[s] === 'number');
    base[s] = first ? (first[s] as number) : 10000;
  }
  return rows.map((r) => {
    const out: MergedRow = { date: r.date, t: r.t, regime: r.regime };
    for (const s of strategies) {
      const v = r[s];
      out[s] = typeof v === 'number' ? (v / base[s] - 1) * 100 : null;
    }
    return out;
  });
}
