'use client';

import { useMemo } from 'react';
import type { HelmData, RegimeLabel } from '@/lib/types';
import { REGIME_META, COLORS } from '@/lib/palette';
import { signedPct, pct } from '@/lib/format';

const ORDER: RegimeLabel[] = ['trending', 'ranging', 'high_volatility', 'unclassified'];

export function GateSection({ data }: { data: HelmData }) {
  const attr = data.regime.regime_attribution;
  const totalDays = useMemo(
    () => Object.values(attr).reduce((s, a) => s + a.days, 0),
    [attr]
  );

  // Cash share of the bear window (gate held = flat equity day-over-day).
  const eq = data.regime.strategies.helm.equity;
  let cashDays = 0;
  for (let i = 1; i < eq.length; i += 1) {
    if (Math.abs(eq[i].value - eq[i - 1].value) < 1e-6) cashDays += 1;
  }
  const cashShare = cashDays / (eq.length - 1);

  return (
    <section id="gate">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">03 · The guardrail</span>
          <h2>A grinding bear reads as &ldquo;ranging.&rdquo; The gate knows better.</h2>
          <p className="section-lede">
            The 3-state taxonomy can&rsquo;t tell an uptrend from a downtrend — a
            slow bear looks like a range and would route to mean-reversion,
            buying the knife. A textbook trend filter (market index below its
            50-day MA, <em>or</em> &gt;10% off its peak) overrides the regime to{' '}
            <strong style={{ color: COLORS.amber }}>defensive / cash</strong> on
            positive evidence of a downtrend.
          </p>
        </div>

        <div className="gate-grid">
          {/* Gate = cash readout */}
          <div className="panel ticked panel-pad gate-cash reveal">
            <span className="eyebrow" style={{ color: COLORS.amber }}>
              Risk-off gate
            </span>
            <div className="gate-cash__big readout">
              {Math.round(cashShare * 100)}%
            </div>
            <p className="gate-cash__cap mono">
              of the 8-month bear window held in <strong>CASH</strong>
            </p>
            <div className="gate-cash__bar" aria-hidden="true">
              <span
                className="gate-cash__fill"
                style={{ width: `${cashShare * 100}%` }}
              />
            </div>
            <div className="gate-cash__legend mono">
              <span><i className="cash" /> gate ON · cash {Math.round(cashShare * 100)}%</span>
              <span><i className="risk" /> deployed {Math.round((1 - cashShare) * 100)}%</span>
            </div>
            <p className="gate-cash__foot mono">
              {cashDays} of {eq.length - 1} days flat — the override doing its job,
              not a curve-fit.
            </p>
          </div>

          {/* Regime P&L attribution */}
          <div className="panel ticked panel-pad gate-attr reveal">
            <span className="eyebrow">Regime P&amp;L attribution</span>
            <p className="gate-attr__sub mono">
              Where the {totalDays} classified days landed, and the P&amp;L each
              regime owns over the bear window.
            </p>
            <div className="gate-attr__rows">
              {ORDER.map((r) => {
                const a = attr[r];
                if (!a) return null;
                const meta = REGIME_META[r];
                const dayShare = a.days / totalDays;
                return (
                  <div key={r} className="gate-row">
                    <div className="gate-row__head">
                      <span className="gate-row__name">
                        <i style={{ background: meta.color }} />
                        {meta.label}
                      </span>
                      <span className="gate-row__days mono">{a.days}d</span>
                    </div>
                    <div className="gate-row__bar">
                      <span
                        className="gate-row__fill"
                        style={{
                          width: `${Math.max(dayShare * 100, 1.5)}%`,
                          background: meta.color,
                        }}
                      />
                    </div>
                    <div className="gate-row__meta mono">
                      <span>{pct(dayShare, 0)} of days</span>
                      <span
                        className={a.total_return < 0 ? 'neg' : a.total_return > 0 ? 'pos' : ''}
                      >
                        {a.total_return === 0 ? 'flat' : signedPct(a.total_return)} P&amp;L
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="gate-attr__foot mono">
              Nearly all the realized P&amp;L sits in <strong>ranging</strong> —
              the regime the gate watches most closely. Trending and
              high-volatility days were largely spent out of the market.
            </p>
          </div>
        </div>
      </div>

      <style>{`
        .gate-grid {
          display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 20px;
        }
        .gate-cash { display: flex; flex-direction: column; gap: 4px; }
        .gate-cash__big {
          font-size: clamp(56px, 9vw, 92px); line-height: 0.95; color: var(--amber);
          margin-top: 14px;
          text-shadow: 0 0 36px rgba(245,165,36,0.35);
        }
        .gate-cash__cap { font-size: 13px; color: var(--ink-dim); margin: 6px 0 18px; }
        .gate-cash__cap strong { color: var(--amber); letter-spacing: 0.06em; }
        .gate-cash__bar {
          height: 16px; border-radius: 6px; overflow: hidden; display: flex;
          background: repeating-linear-gradient(
            45deg, rgba(245,165,36,0.10), rgba(245,165,36,0.10) 7px,
            rgba(245,165,36,0.04) 7px, rgba(245,165,36,0.04) 14px);
          border: 1px solid rgba(245,165,36,0.3);
        }
        .gate-cash__fill {
          height: 100%; background: linear-gradient(90deg, var(--amber), #ffce6a);
          box-shadow: 0 0 18px rgba(245,165,36,0.45);
        }
        .gate-cash__legend {
          display: flex; justify-content: space-between; font-size: 11px;
          color: var(--mute); margin-top: 10px;
        }
        .gate-cash__legend i {
          width: 9px; height: 9px; border-radius: 2px; display: inline-block;
          margin-right: 5px; vertical-align: middle;
        }
        .gate-cash__legend i.cash { background: var(--amber); }
        .gate-cash__legend i.risk { background: #2a3d4d; }
        .gate-cash__foot { font-size: 11px; color: var(--faint); margin-top: 14px; }

        .gate-attr__sub { font-size: 12px; color: var(--mute); margin: 10px 0 18px; }
        .gate-attr__rows { display: flex; flex-direction: column; gap: 16px; }
        .gate-row__head { display: flex; justify-content: space-between; align-items: baseline; }
        .gate-row__name {
          display: inline-flex; align-items: center; gap: 9px;
          font-size: 14px; color: var(--ink);
        }
        .gate-row__name i { width: 10px; height: 10px; border-radius: 3px; }
        .gate-row__days { color: var(--mute); font-size: 12px; }
        .gate-row__bar {
          height: 8px; background: rgba(120,150,170,0.10); border-radius: 5px;
          overflow: hidden; margin: 7px 0 5px;
        }
        .gate-row__fill { height: 100%; border-radius: 5px; display: block; }
        .gate-row__meta { display: flex; justify-content: space-between; font-size: 11px; color: var(--mute); }
        .gate-attr__foot {
          font-size: 11.5px; color: var(--faint); margin-top: 20px; line-height: 1.7;
          border-top: 1px solid var(--line); padding-top: 16px;
        }
        .gate-attr__foot strong { color: var(--steel); }
        @media (max-width: 820px) {
          .gate-grid { grid-template-columns: 1fr; }
        }
      `}</style>
    </section>
  );
}
