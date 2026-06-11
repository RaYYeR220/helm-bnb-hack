'use client';

import { useMemo, useState } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  ReferenceDot,
  ResponsiveContainer,
} from 'recharts';
import type { HelmData, StrategyKey } from '@/lib/types';
import { buildEquityDataset, toReturnRows } from '@/lib/equity';
import { STRATEGY_META, REGIME_META, COLORS } from '@/lib/palette';
import { monthYear, signedPct } from '@/lib/format';

const FLASH_CRASH = '2025-10-10';

export function EquitySection({ data }: { data: HelmData }) {
  const [view, setView] = useState<'return' | 'usd'>('return');
  const [active, setActive] = useState<StrategyKey | null>(null);

  const { rows, bands, strategies } = useMemo(
    () => buildEquityDataset(data.regime),
    [data]
  );
  const plotRows = useMemo(
    () => (view === 'return' ? toReturnRows(rows, strategies) : rows),
    [rows, strategies, view]
  );

  const tFirst = rows[0]?.t ?? 0;
  const tLast = rows[rows.length - 1]?.t ?? 0;

  const flash = rows.find((r) => r.date === FLASH_CRASH);
  const flashHelm = view === 'return'
    ? plotRows.find((r) => r.date === FLASH_CRASH)?.helm
    : flash?.helm;

  return (
    <section id="equity">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">02 · One year, one bear</span>
          <h2>The curve that survived the regime that killed the others.</h2>
          <p className="section-lede">
            A 1-year window over {data.regime.strategies.helm.equity.length} days
            of 8 BSC majors — and it happens to be a brutal bear. Every static
            bot bleeds. The point isn&rsquo;t that Helm printed; it&rsquo;s that
            the risk-off gate kept it{' '}
            <strong style={{ color: COLORS.helm }}>in cash</strong> while
            mean-reversion bought the falling knife. Regime bands sit behind the
            curves; the marker is the Oct&nbsp;10 flash-crash.
          </p>
        </div>

        <div className="eq-toolbar reveal">
          <div className="eq-legend">
            {strategies.map((s) => {
              const meta = STRATEGY_META[s];
              const on = active === null || active === s;
              return (
                <button
                  key={s}
                  className={`eq-legend__item ${on ? '' : 'dim'} ${meta.emphasis ? 'lead' : ''}`}
                  onMouseEnter={() => setActive(s)}
                  onMouseLeave={() => setActive(null)}
                  type="button"
                >
                  <span
                    className="eq-swatch"
                    style={{ background: meta.color }}
                  />
                  {meta.label}
                </button>
              );
            })}
          </div>
          <div className="eq-toggle" role="group" aria-label="Y axis units">
            <button
              type="button"
              className={view === 'return' ? 'on' : ''}
              onClick={() => setView('return')}
            >
              % return
            </button>
            <button
              type="button"
              className={view === 'usd' ? 'on' : ''}
              onClick={() => setView('usd')}
            >
              $10k base
            </button>
          </div>
        </div>

        <div className="panel ticked panel-pad eq-chart reveal">
          <ResponsiveContainer width="100%" height={440}>
            <ComposedChart
              data={plotRows}
              margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
            >
              <defs>
                <linearGradient id="helmGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.helm} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={COLORS.helm} stopOpacity={0} />
                </linearGradient>
              </defs>

              {/* Regime background bands */}
              {bands.map((b, i) => (
                <ReferenceArea
                  key={i}
                  x1={Date.parse(b.from + 'T00:00:00Z')}
                  x2={Date.parse(b.to + 'T00:00:00Z')}
                  fill={REGIME_META[b.regime].band}
                  fillOpacity={1}
                  stroke="none"
                  ifOverflow="extendDomain"
                />
              ))}

              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={[tFirst, tLast]}
                scale="time"
                tickFormatter={(t) =>
                  monthYear(new Date(t).toISOString().slice(0, 10))
                }
                tickCount={7}
                stroke="var(--line-strong)"
                tickLine={false}
              />
              <YAxis
                stroke="var(--line-strong)"
                tickLine={false}
                width={56}
                tickFormatter={(v) =>
                  view === 'return'
                    ? `${v > 0 ? '+' : ''}${Math.round(v)}%`
                    : `$${Math.round(v / 1000)}k`
                }
              />
              <Tooltip
                content={<EquityTooltip view={view} />}
                cursor={{ stroke: 'var(--line-strong)', strokeDasharray: '4 4' }}
              />

              {view === 'return' && (
                <ReferenceLine y={0} stroke="var(--line-strong)" strokeWidth={1} />
              )}

              {/* Flash-crash marker */}
              <ReferenceLine
                x={Date.parse(FLASH_CRASH + 'T00:00:00Z')}
                stroke={COLORS.danger}
                strokeDasharray="3 4"
                strokeOpacity={0.7}
              />
              {typeof flashHelm === 'number' && (
                <ReferenceDot
                  x={Date.parse(FLASH_CRASH + 'T00:00:00Z')}
                  y={flashHelm}
                  r={4}
                  fill={COLORS.danger}
                  stroke="#fff"
                  strokeWidth={1}
                />
              )}

              {strategies.map((s) => {
                const meta = STRATEGY_META[s];
                const dim = active !== null && active !== s;
                return (
                  <Line
                    key={s}
                    type="monotone"
                    dataKey={s}
                    stroke={meta.color}
                    strokeWidth={meta.emphasis ? 2.6 : 1.4}
                    strokeOpacity={dim ? 0.12 : meta.emphasis ? 1 : 0.7}
                    dot={false}
                    isAnimationActive={false}
                    connectNulls
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>

          <div className="eq-regimekey">
            {(['trending', 'ranging', 'high_volatility', 'unclassified'] as const).map(
              (r) => (
                <span key={r} className="eq-regimekey__item mono">
                  <i style={{ background: REGIME_META[r].band, borderColor: REGIME_META[r].color }} />
                  {REGIME_META[r].label}
                </span>
              )
            )}
            <span className="eq-regimekey__item mono">
              <i style={{ background: 'transparent', borderColor: COLORS.danger }} />
              Oct&nbsp;10 flash-crash
            </span>
          </div>
        </div>

        <p className="eq-note reveal mono">
          Helm finishes {signedPct(data.regime.strategies.helm.metrics.total_return)} —
          the least-bad line on the board — vs equal-weight{' '}
          {signedPct(data.regime.strategies.equal_weight.metrics.total_return)} and
          mean-reversion{' '}
          {signedPct(data.regime.strategies.mean_reversion.metrics.total_return)}.
          The validated edge (Sharpe + drawdown) lives in the walk-forward run
          below; this window shows the gate doing its job.
        </p>
      </div>

      <style>{`
        .eq-toolbar {
          display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
          justify-content: space-between; margin-bottom: 18px;
        }
        .eq-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; }
        .eq-legend__item {
          display: inline-flex; align-items: center; gap: 8px;
          background: none; border: none; cursor: pointer;
          font-family: var(--font-mono); font-size: 12px; color: var(--ink-dim);
          padding: 4px 2px; transition: color 0.2s, opacity 0.2s;
        }
        .eq-legend__item.lead { color: var(--ink); font-weight: 500; }
        .eq-legend__item.dim { opacity: 0.4; }
        .eq-legend__item:hover { color: var(--ink); }
        .eq-swatch { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
        .eq-toggle {
          display: inline-flex; border: 1px solid var(--line-strong);
          border-radius: 999px; overflow: hidden;
        }
        .eq-toggle button {
          background: none; border: none; cursor: pointer;
          font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.04em;
          color: var(--mute); padding: 7px 14px; transition: all 0.2s;
        }
        .eq-toggle button.on { background: rgba(46,230,200,0.12); color: var(--helm); }
        .eq-chart { padding-bottom: 14px; }
        .eq-regimekey {
          display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 14px;
          padding-top: 14px; border-top: 1px solid var(--line);
        }
        .eq-regimekey__item {
          display: inline-flex; align-items: center; gap: 7px;
          font-size: 11px; color: var(--mute); letter-spacing: 0.04em;
        }
        .eq-regimekey__item i {
          width: 13px; height: 13px; border-radius: 3px;
          border: 1px solid; display: inline-block;
        }
        .eq-note {
          margin-top: 20px; font-size: 12.5px; color: var(--mute);
          max-width: 760px; line-height: 1.7;
        }
        .eq-note strong { color: var(--ink); }
      `}</style>
    </section>
  );
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number; color: string }>;
  label?: number;
  view: 'return' | 'usd';
}

function EquityTooltip({ active, payload, label, view }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const date = new Date(label as number).toISOString().slice(0, 10);
  const order = payload
    .filter((p) => typeof p.value === 'number')
    .sort((a, b) => b.value - a.value);
  return (
    <div className="eq-tip">
      <div className="eq-tip__date mono">{date}</div>
      {order.map((p) => {
        const meta = STRATEGY_META[p.dataKey as StrategyKey];
        return (
          <div key={p.dataKey} className="eq-tip__row mono">
            <span className="eq-tip__dot" style={{ background: p.color }} />
            <span className="eq-tip__name">{meta?.label ?? p.dataKey}</span>
            <span className="eq-tip__val">
              {view === 'return'
                ? `${p.value > 0 ? '+' : ''}${p.value.toFixed(1)}%`
                : `$${Math.round(p.value).toLocaleString('en-US')}`}
            </span>
          </div>
        );
      })}
      <style>{`
        .eq-tip {
          background: var(--panel-2); border: 1px solid var(--line-strong);
          border-radius: 10px; padding: 10px 12px; min-width: 200px;
          box-shadow: 0 18px 40px rgba(0,0,0,0.5);
        }
        .eq-tip__date { font-size: 11px; color: var(--mute); margin-bottom: 8px;
          letter-spacing: 0.1em; }
        .eq-tip__row { display: flex; align-items: center; gap: 8px;
          font-size: 12px; padding: 2px 0; }
        .eq-tip__dot { width: 8px; height: 8px; border-radius: 2px; flex: none; }
        .eq-tip__name { color: var(--ink-dim); flex: 1; }
        .eq-tip__val { color: var(--ink); font-weight: 500; }
      `}</style>
    </div>
  );
}
