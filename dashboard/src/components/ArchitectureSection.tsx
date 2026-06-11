'use client';

import { COLORS } from '@/lib/palette';

interface Stage {
  id: string;
  title: string;
  rows: string[];
  accent?: string;
}

const STAGES: Stage[] = [
  {
    id: 'data',
    title: 'Data layer',
    rows: ['CoinMarketCap OHLCV + market', 'DeFiLlama BSC TVL · Pancake share', 'GeckoTerminal DEX volume', 'cache-first · parquet'],
  },
  {
    id: 'features',
    title: 'Features',
    rows: ['trend_strength · realized_vol', 'breadth · dispersion', '+ tvl_mom20 · tvl_dd', 'pancake_share_mom20'],
  },
  {
    id: 'regime',
    title: 'Regime · HMM',
    rows: ['3-state Gaussian · 8 restarts', 'posterior + confidence', 'per-feature attribution', '→ trending / ranging / high-vol'],
    accent: COLORS.helm,
  },
  {
    id: 'gate',
    title: 'Risk-off gate',
    rows: ['50d-MA filter', 'OR >10% off peak', 'override → defensive', 'hysteresis = 3'],
    accent: COLORS.amber,
  },
  {
    id: 'router',
    title: 'Router',
    rows: ['trending → momentum', 'ranging → market port.', 'high-vol → defensive', 'RISK-OFF → cash'],
  },
  {
    id: 'valid',
    title: 'Backtest + validation',
    rows: ['engine · metrics · P&L attr.', 'walk-forward windows', 'deflated Sharpe', 'block-bootstrap CIs'],
  },
];

export function ArchitectureSection() {
  return (
    <section id="arch">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">06 · How it&rsquo;s wired</span>
          <h2>Data to read to route to proof — nothing in a black box.</h2>
          <p className="section-lede">
            CMC market data fused with on-chain TVL becomes causal features; a
            3-state HMM reads the regime; a hard-coded trend filter gates it; the
            router picks a sub-strategy; the backtest + validation harness keeps
            every claim honest. A native Agent Hub skill exposes the live read to
            any MCP-connected agent.
          </p>
        </div>

        <div className="arch panel ticked panel-pad reveal">
          <div className="arch-flow">
            {STAGES.map((s, i) => (
              <div key={s.id} className="arch-stage-wrap">
                <div
                  className="arch-stage"
                  style={{
                    borderColor: s.accent ? `${s.accent}55` : 'var(--line)',
                    boxShadow: s.accent ? `inset 0 0 0 1px ${s.accent}22` : 'none',
                  }}
                >
                  <div className="arch-stage__num mono">{String(i + 1).padStart(2, '0')}</div>
                  <div
                    className="arch-stage__title"
                    style={{ color: s.accent ?? 'var(--ink)' }}
                  >
                    {s.title}
                  </div>
                  <ul className="arch-stage__rows">
                    {s.rows.map((r) => (
                      <li key={r} className="mono">{r}</li>
                    ))}
                  </ul>
                </div>
                {i < STAGES.length - 1 && (
                  <span className="arch-arrow" aria-hidden="true">→</span>
                )}
              </div>
            ))}
          </div>

          <div className="arch-skill">
            <span className="arch-skill__icon" aria-hidden="true">⌁</span>
            <div>
              <div className="arch-skill__title mono">CMC AGENT HUB SKILL · helm-regime-read</div>
              <p className="arch-skill__sub">
                Composes Helm&rsquo;s regime read into any LLM agent on the
                cmc-mcp server — live mode (MCP-only heuristics) or full mode
                (local HMM engine).
              </p>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .arch-flow {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 14px 36px;
        }
        .arch-stage-wrap { position: relative; display: flex; }
        .arch-stage {
          flex: 1; background: var(--panel-2); border: 1px solid var(--line);
          border-radius: 12px; padding: 18px 18px 16px; position: relative;
          transition: transform 0.25s, border-color 0.25s;
        }
        .arch-stage:hover { transform: translateY(-3px); }
        .arch-stage__num {
          position: absolute; top: 14px; right: 16px; font-size: 11px; color: var(--faint);
        }
        .arch-stage__title {
          font-family: var(--font-display); font-size: 18px; margin-bottom: 12px;
          letter-spacing: -0.01em;
        }
        .arch-stage__rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
        .arch-stage__rows li {
          font-size: 11.5px; color: var(--ink-dim); line-height: 1.4;
          padding-left: 12px; position: relative;
        }
        .arch-stage__rows li::before {
          content: ''; position: absolute; left: 0; top: 7px;
          width: 4px; height: 4px; border-radius: 50%; background: var(--faint);
        }
        .arch-arrow {
          position: absolute; right: -28px; top: 50%; transform: translateY(-50%);
          color: var(--helm); font-size: 20px; opacity: 0.6;
        }
        /* hide the arrow at the end of each visual row (every 3rd) */
        .arch-stage-wrap:nth-child(3n) .arch-arrow { display: none; }

        .arch-skill {
          margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--line);
          display: flex; gap: 18px; align-items: flex-start;
        }
        .arch-skill__icon {
          font-size: 26px; color: var(--helm); line-height: 1;
          width: 48px; height: 48px; flex: none; display: grid; place-items: center;
          border: 1px solid rgba(46,230,200,0.3); border-radius: 12px;
          background: rgba(46,230,200,0.06); box-shadow: var(--glow-helm);
        }
        .arch-skill__title { font-size: 12px; letter-spacing: 0.1em; color: var(--helm); margin-bottom: 6px; }
        .arch-skill__sub { font-size: 13px; color: var(--ink-dim); max-width: 640px; margin: 0; }

        @media (max-width: 880px) {
          .arch-flow { grid-template-columns: 1fr; }
          .arch-arrow { display: none !important; }
        }
      `}</style>
    </section>
  );
}
