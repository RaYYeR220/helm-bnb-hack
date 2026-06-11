'use client';

import type { HelmData } from '@/lib/types';
import { COLORS, CONFIG_LABELS } from '@/lib/palette';
import { signedPct } from '@/lib/format';

const DQ_CAP = 0.3; // Track 1 disqualifies any agent breaching 30% drawdown.

export function DqSection({ data }: { data: HelmData }) {
  const cfg = data.onchain.per_config_oos;

  // Bars: Helm + the static baselines, by absolute OOS max drawdown.
  const bars = [
    { key: 'helm_gated_tvl', dd: Math.abs(cfg.helm_gated_tvl.mean_max_drawdown) },
    { key: 'equal_weight', dd: Math.abs(cfg.equal_weight.mean_max_drawdown) },
    // From the 3y harness: momentum + a naive mean-reversion-class bled ~42%.
    { key: 'momentum', dd: Math.abs(data.validation.per_config_oos.momentum.mean_max_drawdown) },
    { key: 'helm_ungated', dd: Math.abs(data.validation.per_config_oos.helm_ungated.mean_max_drawdown) },
  ].sort((a, b) => a.dd - b.dd);

  const scaleMax = Math.max(...bars.map((b) => b.dd), DQ_CAP) * 1.08;

  return (
    <section id="dq">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">05 · The DQ-survival argument</span>
          <h2>Every static baseline breaches the 30% drawdown DQ. Helm doesn&rsquo;t.</h2>
          <p className="section-lede">
            Track 1 disqualifies any agent that breaches a{' '}
            <strong style={{ color: COLORS.danger }}>30% drawdown cap</strong>. We
            didn&rsquo;t enter it — it needs live capital — but the cap is the
            right risk bar, and it&rsquo;s the cleanest way to state the edge.
            Regime-switching isn&rsquo;t a flashier return; it&rsquo;s surviving
            the regime that kills single-mode bots.
          </p>
        </div>

        <div className="panel ticked panel-pad dq-chart reveal">
          <div className="dq-rows">
            {bars.map((b) => {
              const breaches = b.dd > DQ_CAP;
              const widthPct = (b.dd / scaleMax) * 100;
              return (
                <div key={b.key} className="dq-row">
                  <span className={`dq-row__name ${b.key === 'helm_gated_tvl' ? 'lead' : ''}`}>
                    {b.key === 'helm_gated_tvl' && <span className="dq-star">◆</span>}
                    {CONFIG_LABELS[b.key] ?? b.key}
                  </span>
                  <div className="dq-row__track">
                    <span
                      className={`dq-row__fill ${breaches ? 'breach' : 'safe'}`}
                      style={{ width: `${widthPct}%` }}
                    />
                    <span className={`dq-row__val mono ${breaches ? 'neg' : 'pos'}`}>
                      −{(b.dd * 100).toFixed(1)}%
                      {breaches ? ' · DQ' : ' · clear'}
                    </span>
                  </div>
                </div>
              );
            })}
            {/* The DQ line */}
            <div
              className="dq-line"
              style={{ left: `calc(var(--label-w) + (100% - var(--label-w)) * ${DQ_CAP / scaleMax})` }}
            >
              <span className="dq-line__label mono">30% DQ CAP</span>
            </div>
          </div>
        </div>

        <div className="dq-cards reveal">
          <div className="dq-card panel ticked panel-pad">
            <span className="dq-card__v readout pos">
              {signedPct(cfg.helm_gated_tvl.mean_max_drawdown, 1)}
            </span>
            <span className="dq-card__k mono">Helm · gated + TVL — well under the cap</span>
          </div>
          <div className="dq-card panel ticked panel-pad">
            <span className="dq-card__v readout neg">
              {signedPct(cfg.equal_weight.mean_max_drawdown, 1)}
            </span>
            <span className="dq-card__k mono">Equal-weight market — breaches by 11.8 pts</span>
          </div>
          <div className="dq-card panel ticked panel-pad">
            <span className="dq-card__v readout">
              {(Math.abs(cfg.equal_weight.mean_max_drawdown) / Math.abs(cfg.helm_gated_tvl.mean_max_drawdown)).toFixed(1)}×
            </span>
            <span className="dq-card__k mono">smaller worst loss, same Sharpe class</span>
          </div>
        </div>
      </div>

      <style>{`
        .dq-chart { --label-w: 220px; }
        .dq-rows { position: relative; display: flex; flex-direction: column; gap: 22px; padding: 8px 0; }
        .dq-row { display: grid; grid-template-columns: var(--label-w) 1fr; align-items: center; gap: 16px; }
        .dq-row__name {
          font-size: 14px; color: var(--ink-dim); text-align: right;
          display: inline-flex; align-items: center; gap: 7px; justify-content: flex-end;
        }
        .dq-row__name.lead { color: var(--ink); font-weight: 600; }
        .dq-star { color: var(--helm); font-size: 9px; }
        .dq-row__track { position: relative; height: 30px; display: flex; align-items: center; }
        .dq-row__fill {
          height: 30px; border-radius: 6px; transition: width 1s cubic-bezier(0.16,1,0.3,1);
        }
        .dq-row__fill.safe {
          background: linear-gradient(90deg, var(--helm-deep), var(--helm));
          box-shadow: 0 0 18px rgba(46,230,200,0.4);
        }
        .dq-row__fill.breach {
          background: linear-gradient(90deg, rgba(255,93,93,0.5), var(--danger));
        }
        .dq-row__val { position: absolute; left: calc(100% + 0px); padding-left: 12px; white-space: nowrap; font-size: 12.5px; transform: translateX(0); }
        .dq-row__fill.safe + .dq-row__val { color: var(--helm); }

        .dq-line {
          position: absolute; top: -4px; bottom: -4px; width: 0;
          border-left: 2px dashed var(--danger); pointer-events: none;
        }
        .dq-line__label {
          position: absolute; top: -2px; left: 8px; font-size: 10px;
          letter-spacing: 0.14em; color: var(--danger);
          background: rgba(255,93,93,0.10); border: 1px solid rgba(255,93,93,0.3);
          padding: 2px 7px; border-radius: 5px; white-space: nowrap;
        }

        .dq-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 22px; }
        .dq-card { display: flex; flex-direction: column; gap: 8px; }
        .dq-card__v { font-size: clamp(28px, 4vw, 40px); }
        .dq-card__k { font-size: 11.5px; color: var(--mute); line-height: 1.5; }

        @media (max-width: 760px) {
          .dq-chart { --label-w: 130px; }
          .dq-row__name { font-size: 12px; }
          .dq-cards { grid-template-columns: 1fr; }
          .dq-row__val { font-size: 11px; padding-left: 8px; }
        }
      `}</style>
    </section>
  );
}
