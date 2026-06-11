'use client';

import type { HelmData } from '@/lib/types';
import { CONFIG_LABELS, COLORS, REGIME_META } from '@/lib/palette';
import { num, pct, signedNum, signedPct } from '@/lib/format';

// Configs to show in the OOS bar comparison, in narrative order.
const OOS_CONFIGS = ['helm_gated_tvl', 'helm_gated', 'equal_weight'] as const;

export function WalkForwardSection({ data }: { data: HelmData }) {
  const oc = data.onchain;
  const cfg = oc.per_config_oos;
  const dsr = oc.deflated_sharpe;
  const boot = oc.bootstrap;
  const windows = data.validation.selection.per_window;

  const maxSharpe = Math.max(...OOS_CONFIGS.map((c) => cfg[c].mean_sharpe));
  const maxDD = Math.max(...OOS_CONFIGS.map((c) => Math.abs(cfg[c].mean_max_drawdown)));

  // TVL fusion trend-detection delta.
  const baseTrend = oc.regime_value_counts.baseline.trending;
  const tvlTrend = oc.regime_value_counts.tvl.trending;

  return (
    <section id="oos">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">04 · Validated, out-of-sample</span>
          <h2>Selected on train windows. Reported out-of-sample. No cherry-pick.</h2>
          <p className="section-lede">
            A {oc.panel.days}-day walk-forward over {oc.panel.symbols.length} BSC
            majors. Variants are chosen on each window&rsquo;s <em>train</em> leg;
            every number here is the mean over the held-out <em>test</em> legs.
            Helm and the market sit in the same Sharpe class — the edge is the
            drawdown profile.
          </p>
        </div>

        {/* Per-config OOS bars: Sharpe + maxDD side by side */}
        <div className="wf-bars reveal">
          <div className="panel ticked panel-pad">
            <div className="wf-bars__head">
              <span className="eyebrow">Mean OOS Sharpe</span>
              <span className="mono wf-bars__hint">higher is better</span>
            </div>
            {OOS_CONFIGS.map((c) => {
              const v = cfg[c].mean_sharpe;
              const lead = c === 'helm_gated_tvl';
              return (
                <Bar
                  key={c}
                  label={CONFIG_LABELS[c]}
                  value={`${num(v, 2)}`}
                  pctWidth={(v / maxSharpe) * 100}
                  color={lead ? COLORS.helm : c === 'equal_weight' ? COLORS.steel : COLORS.violet}
                  lead={lead}
                />
              );
            })}
          </div>

          <div className="panel ticked panel-pad">
            <div className="wf-bars__head">
              <span className="eyebrow" style={{ color: COLORS.danger }}>
                Mean OOS max drawdown
              </span>
              <span className="mono wf-bars__hint">shallower is better</span>
            </div>
            {OOS_CONFIGS.map((c) => {
              const v = cfg[c].mean_max_drawdown;
              const lead = c === 'helm_gated_tvl';
              return (
                <Bar
                  key={c}
                  label={CONFIG_LABELS[c]}
                  value={signedPct(v, 1)}
                  pctWidth={(Math.abs(v) / maxDD) * 100}
                  color={lead ? COLORS.helm : COLORS.danger}
                  lead={lead}
                  danger={!lead}
                />
              );
            })}
          </div>
        </div>

        {/* Stat callouts: DSR + bootstrap CIs */}
        <div className="wf-callouts reveal">
          <div className="panel ticked panel-pad wf-callout">
            <span className="wf-callout__k mono">DEFLATED SHARPE</span>
            <span className="wf-callout__v readout pos">{num(dsr.value, 3)}</span>
            <span className="wf-callout__sub mono">
              corrected for {dsr.n_trials} Helm trials — the edge survives
              selection
            </span>
          </div>
          <div className="panel ticked panel-pad wf-callout">
            <span className="wf-callout__k mono">SHARPE · BLOCK-BOOTSTRAP 90% CI</span>
            <span className="wf-callout__v readout">
              {signedNum(boot.sharpe.lo, 2)} <span className="wf-dim">…</span>{' '}
              {signedNum(boot.sharpe.hi, 2)}
            </span>
            <CiBar lo={boot.sharpe.lo} hi={boot.sharpe.hi} point={boot.sharpe.point} />
            <span className="wf-callout__sub mono">
              point {num(boot.sharpe.point, 2)} · wide but centered positive
            </span>
          </div>
          <div className="panel ticked panel-pad wf-callout">
            <span className="wf-callout__k mono">TOTAL RETURN · 90% CI</span>
            <span className="wf-callout__v readout">
              {signedPct(boot.total_return.lo, 0)}{' '}
              <span className="wf-dim">…</span>{' '}
              {signedPct(boot.total_return.hi, 0)}
            </span>
            <span className="wf-callout__sub mono">
              point {signedPct(boot.total_return.point, 0)}
            </span>
          </div>
        </div>

        {/* TVL fusion 105 -> 199 */}
        <div className="panel ticked panel-pad wf-tvl reveal">
          <div className="wf-tvl__copy">
            <span className="eyebrow">On-chain TVL fusion</span>
            <h3 className="wf-tvl__title">
              Trend detection{' '}
              <span className="mono pos">{baseTrend} → {tvlTrend}</span> days
            </h3>
            <p className="wf-tvl__sub">
              Fusing BSC chain TVL and PancakeSwap share into the classifier
              ({oc.onchain_feature_cols.join(', ')}) nearly doubles the days the
              regime path reads as <strong>trending</strong> — on-chain flow
              front-runs price on BSC. It buys{' '}
              <span className="pos">
                {signedNum(cfg.helm_gated_tvl.mean_sharpe - cfg.helm_gated.mean_sharpe, 2)}
              </span>{' '}
              OOS Sharpe over the no-fusion variant.
            </p>
          </div>
          <div className="wf-tvl__compare">
            {(['baseline', 'tvl'] as const).map((path) => {
              const vc = oc.regime_value_counts[path];
              const total = vc.ranging + vc.trending + vc.high_volatility;
              return (
                <div key={path} className="wf-tvl__path">
                  <span className="wf-tvl__pathname mono">
                    {path === 'baseline' ? 'MARKET-ONLY' : 'TVL-FUSED'}
                  </span>
                  <div className="wf-tvl__stack" aria-hidden="true">
                    {(['trending', 'ranging', 'high_volatility'] as const).map((r) => (
                      <span
                        key={r}
                        className="wf-tvl__seg"
                        style={{
                          width: `${(vc[r] / total) * 100}%`,
                          background: REGIME_META[r].color,
                          opacity: r === 'trending' ? 1 : 0.45,
                        }}
                        title={`${REGIME_META[r].label}: ${vc[r]}d`}
                      />
                    ))}
                  </div>
                  <span className="wf-tvl__pathval mono">
                    {vc.trending}d trending · {pct(vc.trending / total, 0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Per-window selection table */}
        <div className="wf-table-wrap reveal">
          <div className="wf-table-head">
            <span className="eyebrow">Per-window selection · 3-year harness</span>
            <span className="mono wf-bars__hint">
              variant chosen on train, scored on test · {windows.length} windows
            </span>
          </div>
          <div className="panel ticked wf-table-scroll">
            <table className="wf-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Chosen variant</th>
                  <th className="r">Days</th>
                  <th className="r">Total</th>
                  <th className="r">Sharpe</th>
                  <th className="r">Sortino</th>
                  <th className="r">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {windows.map((w) => (
                  <tr key={w.window_id}>
                    <td className="mono">#{w.window_id}</td>
                    <td>
                      <span className="wf-chip mono">{CONFIG_LABELS[w.chosen] ?? w.chosen}</span>
                    </td>
                    <td className="r mono">{w.n_days}</td>
                    <td className={`r mono ${cls(w.total_return)}`}>{signedPct(w.total_return)}</td>
                    <td className={`r mono ${cls(w.sharpe)}`}>{signedNum(w.sharpe)}</td>
                    <td className={`r mono ${cls(w.sortino)}`}>{signedNum(w.sortino)}</td>
                    <td className="r mono neg">{signedPct(w.max_drawdown)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="wf-table-note mono">
            Window&nbsp;4 selected the gated variant and the gate held flat
            (0.0% — fully defensive). Honest, not hidden: gate-on means cash,
            and cash means a zero, not a loss.
          </p>
        </div>
      </div>

      <style>{`
        .wf-bars { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .wf-bars__head {
          display: flex; justify-content: space-between; align-items: baseline;
          margin-bottom: 20px;
        }
        .wf-bars__hint { font-size: 10.5px; color: var(--faint); letter-spacing: 0.08em; }

        .wf-callouts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }
        .wf-callout { display: flex; flex-direction: column; gap: 8px; }
        .wf-callout__k { font-size: 10px; letter-spacing: 0.16em; color: var(--mute); }
        .wf-callout__v { font-size: clamp(24px, 3vw, 32px); color: var(--ink); }
        .wf-callout__sub { font-size: 11px; color: var(--faint); line-height: 1.5; }
        .wf-dim { color: var(--faint); }

        .wf-tvl {
          margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr;
          gap: 30px; align-items: center;
        }
        .wf-tvl__title { font-size: clamp(22px, 3vw, 30px); margin: 12px 0 10px; }
        .wf-tvl__title .mono { font-size: 0.85em; }
        .wf-tvl__sub { color: var(--ink-dim); font-size: 14px; max-width: 460px; }
        .wf-tvl__sub strong { color: var(--helm); }
        .wf-tvl__compare { display: flex; flex-direction: column; gap: 22px; }
        .wf-tvl__pathname { font-size: 11px; letter-spacing: 0.16em; color: var(--mute); }
        .wf-tvl__stack {
          display: flex; height: 22px; border-radius: 6px; overflow: hidden;
          margin: 8px 0 6px; border: 1px solid var(--line);
        }
        .wf-tvl__seg { height: 100%; }
        .wf-tvl__pathval { font-size: 11.5px; color: var(--ink-dim); }

        .wf-table-wrap { margin-top: 38px; }
        .wf-table-head {
          display: flex; justify-content: space-between; align-items: baseline;
          margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
        }
        .wf-table-scroll { overflow-x: auto; }
        .wf-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 640px; }
        .wf-table th {
          text-align: left; font-family: var(--font-mono); font-weight: 500;
          font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase;
          color: var(--mute); padding: 16px 18px; border-bottom: 1px solid var(--line-strong);
        }
        .wf-table th.r, .wf-table td.r { text-align: right; }
        .wf-table td { padding: 13px 18px; border-bottom: 1px solid var(--line); color: var(--ink-dim); }
        .wf-table tbody tr:last-child td { border-bottom: none; }
        .wf-table tbody tr:hover { background: rgba(46,230,200,0.03); }
        .wf-chip {
          font-size: 11px; padding: 3px 9px; border-radius: 6px;
          background: rgba(155,140,255,0.10); color: var(--violet);
          border: 1px solid rgba(155,140,255,0.25);
        }
        .wf-table-note { font-size: 11px; color: var(--faint); margin-top: 14px; line-height: 1.6; }

        @media (max-width: 820px) {
          .wf-bars, .wf-callouts, .wf-tvl { grid-template-columns: 1fr; }
        }
      `}</style>
    </section>
  );
}

function cls(v: number): string {
  if (v > 0) return 'pos';
  if (v < 0) return 'neg';
  return '';
}

function Bar({
  label,
  value,
  pctWidth,
  color,
  lead,
  danger,
}: {
  label: string;
  value: string;
  pctWidth: number;
  color: string;
  lead?: boolean;
  danger?: boolean;
}) {
  return (
    <div className={`wfbar ${lead ? 'wfbar--lead' : ''}`}>
      <div className="wfbar__top">
        <span className="wfbar__label">
          {lead && <span className="wfbar__star">◆</span>}
          {label}
        </span>
        <span className={`wfbar__val readout ${danger ? 'neg' : lead ? 'pos' : ''}`}>
          {value}
        </span>
      </div>
      <div className="wfbar__track">
        <span
          className="wfbar__fill"
          style={{
            width: `${Math.max(pctWidth, 3)}%`,
            background: color,
            boxShadow: lead ? `0 0 16px ${color}66` : 'none',
          }}
        />
      </div>
      <style>{`
        .wfbar { margin-bottom: 18px; }
        .wfbar:last-child { margin-bottom: 0; }
        .wfbar__top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
        .wfbar__label { font-size: 13px; color: var(--ink-dim); display: inline-flex; align-items: center; gap: 7px; }
        .wfbar--lead .wfbar__label { color: var(--ink); font-weight: 500; }
        .wfbar__star { color: var(--helm); font-size: 9px; }
        .wfbar__val { font-size: 15px; color: var(--ink); }
        .wfbar__track { height: 9px; background: rgba(120,150,170,0.10); border-radius: 5px; overflow: hidden; }
        .wfbar__fill { display: block; height: 100%; border-radius: 5px; transition: width 0.9s cubic-bezier(0.16,1,0.3,1); }
      `}</style>
    </div>
  );
}

function CiBar({ lo, hi, point }: { lo: number; hi: number; point: number }) {
  // Map CI onto a fixed [-1, 2.2] domain for a consistent visual scale.
  const DMIN = -1;
  const DMAX = 2.2;
  const span = DMAX - DMIN;
  const x = (v: number) => ((v - DMIN) / span) * 100;
  const zero = x(0);
  return (
    <div className="cibar" aria-hidden="true">
      <span className="cibar__zero" style={{ left: `${zero}%` }} />
      <span
        className="cibar__range"
        style={{ left: `${x(lo)}%`, width: `${x(hi) - x(lo)}%` }}
      />
      <span className="cibar__point" style={{ left: `${x(point)}%` }} />
      <style>{`
        .cibar { position: relative; height: 16px; margin: 2px 0; }
        .cibar__zero { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--line-strong); }
        .cibar__range {
          position: absolute; top: 50%; transform: translateY(-50%); height: 4px;
          border-radius: 3px;
          background: linear-gradient(90deg, rgba(255,93,93,0.5), rgba(46,230,200,0.6));
        }
        .cibar__point {
          position: absolute; top: 50%; transform: translate(-50%, -50%);
          width: 9px; height: 9px; border-radius: 50%; background: var(--helm);
          box-shadow: 0 0 10px var(--helm);
        }
      `}</style>
    </div>
  );
}
