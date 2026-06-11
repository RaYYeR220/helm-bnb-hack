'use client';

import type { HelmData } from '@/lib/types';
import { signedNum, signedPct, pct, num } from '@/lib/format';

export function Hero({ data }: { data: HelmData }) {
  const oos = data.onchain.per_config_oos;
  const helm = oos.helm_gated_tvl;
  const market = oos.equal_weight;
  const dsr = data.onchain.deflated_sharpe.value;

  // "8-month bear: 100% cash" — derive the cash share of the 1y bear window.
  const eq = data.regime.strategies.helm.equity;
  let flat = 0;
  for (let i = 1; i < eq.length; i += 1) {
    if (Math.abs(eq[i].value - eq[i - 1].value) < 1e-6) flat += 1;
  }
  const cashShare = flat / (eq.length - 1);

  const sharpeEdge = helm.mean_sharpe - market.mean_sharpe;
  const ddRatio = market.mean_max_drawdown / helm.mean_max_drawdown;

  const cards = [
    {
      k: 'OOS Sharpe',
      v: signedNum(helm.mean_sharpe, 2),
      sub: `${signedNum(sharpeEdge, 2)} vs market · same class`,
      tone: 'good' as const,
    },
    {
      k: 'Max drawdown',
      v: signedPct(helm.mean_max_drawdown, 1),
      sub: `vs market ${signedPct(market.mean_max_drawdown, 1)} · ${ddRatio.toFixed(1)}× smaller`,
      tone: 'good' as const,
    },
    {
      k: 'Deflated Sharpe',
      v: num(dsr, 3),
      sub: `corrected for ${data.onchain.deflated_sharpe.n_trials} trials`,
      tone: 'good' as const,
    },
    {
      k: '8-month bear',
      v: `${Math.round(cashShare * 100)}%`,
      sub: `cash days — risk-off gate held`,
      tone: 'warn' as const,
    },
  ];

  return (
    <section id="top" className="hero">
      <SonarBackdrop />
      <div className="wrap hero__inner">
        <p className="eyebrow reveal">BNB Hack · CoinMarketCap × Trust Wallet</p>

        <h1 className="hero__title reveal" style={{ transitionDelay: '60ms' }}>
          Read the regime.
          <br />
          <span className="hero__title-em">Hold the course.</span>
        </h1>

        <p className="hero__lede reveal" style={{ transitionDelay: '130ms' }}>
          Helm is a regime-switching BSC trading engine. It classifies the
          market&rsquo;s character each day — <em>trending</em>,{' '}
          <em>ranging</em>, <em>high-volatility</em> — routes to the strategy
          that fits, and a transparent trend-filter gate overrides the whole
          thing to <strong>cash</strong> on a confirmed downtrend. Same Sharpe
          class as the market, a <strong>3.6× smaller</strong> worst loss.
        </p>

        <div className="hero__cards">
          {cards.map((c, i) => (
            <div
              key={c.k}
              className={`hero__card panel ticked reveal tone-${c.tone}`}
              style={{ transitionDelay: `${200 + i * 80}ms` }}
            >
              <span className="hero__card-k mono">{c.k}</span>
              <span className={`hero__card-v readout`}>{c.v}</span>
              <span className="hero__card-sub mono">{c.sub}</span>
            </div>
          ))}
        </div>

        <div className="hero__meta reveal" style={{ transitionDelay: '560ms' }}>
          <span className="mono">
            WALK-FORWARD · {data.onchain.panel.days} DAYS ·{' '}
            {data.onchain.panel.symbols.length} BSC MAJORS
          </span>
          <span className="hero__scroll mono">SCROLL ↓</span>
        </div>
      </div>

      <style>{`
        .hero {
          padding-top: clamp(140px, 18vh, 220px);
          padding-bottom: clamp(72px, 10vw, 130px);
          border-top: none;
          overflow: hidden;
        }
        .hero__inner { position: relative; z-index: 2; }
        .hero__title {
          font-size: clamp(44px, 9vw, 110px);
          margin: 22px 0 0;
          letter-spacing: -0.03em;
          font-weight: 500;
        }
        .hero__title-em {
          font-style: italic;
          color: var(--helm);
          font-variation-settings: 'SOFT' 40, 'WONK' 1, 'opsz' 110;
          text-shadow: 0 0 40px rgba(46, 230, 200, 0.30);
        }
        .hero__lede {
          margin: 30px 0 0;
          max-width: 660px;
          font-size: clamp(16px, 2vw, 20px);
          color: var(--ink-dim);
          line-height: 1.6;
        }
        .hero__lede em { font-style: italic; color: var(--ink); }
        .hero__lede strong { color: var(--helm); font-weight: 600; }
        .hero__cards {
          margin-top: clamp(40px, 6vw, 64px);
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
        }
        .hero__card {
          padding: 22px 20px 18px;
          display: flex; flex-direction: column; gap: 8px;
          min-height: 148px;
          justify-content: space-between;
          overflow: hidden;
        }
        .hero__card::after {
          content: '';
          position: absolute; left: 0; bottom: 0; height: 2px; width: 100%;
          background: linear-gradient(90deg, transparent, currentColor, transparent);
          opacity: 0.0;
        }
        .hero__card.tone-good { color: var(--helm); }
        .hero__card.tone-warn { color: var(--amber); }
        .hero__card-k {
          font-size: 10.5px; letter-spacing: 0.18em; text-transform: uppercase;
          color: var(--mute);
        }
        .hero__card-v {
          font-size: clamp(30px, 4vw, 44px);
          font-weight: 500;
          line-height: 1;
          color: currentColor;
          text-shadow: 0 0 26px color-mix(in srgb, currentColor 35%, transparent);
        }
        .hero__card-sub {
          font-size: 11px; color: var(--ink-dim); letter-spacing: 0.01em;
          line-height: 1.45;
        }
        .hero__meta {
          margin-top: 40px;
          display: flex; justify-content: space-between; align-items: center;
          color: var(--faint); font-size: 11px; letter-spacing: 0.14em;
          border-top: 1px solid var(--line);
          padding-top: 18px;
        }
        .hero__scroll { animation: bob 2.4s ease-in-out infinite; color: var(--mute); }
        @keyframes bob { 50% { transform: translateY(4px); } }
        @media (max-width: 880px) {
          .hero__cards { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 460px) {
          .hero__cards { grid-template-columns: 1fr; }
        }
      `}</style>
    </section>
  );
}

// Faint rotating sonar sweep + concentric rings behind the hero.
function SonarBackdrop() {
  return (
    <div className="sonar" aria-hidden="true">
      <svg viewBox="0 0 600 600" preserveAspectRatio="xMidYMid slice">
        {[80, 150, 220, 290].map((r) => (
          <circle
            key={r}
            cx="300"
            cy="300"
            r={r}
            fill="none"
            stroke="rgba(46,230,200,0.10)"
            strokeWidth="1"
          />
        ))}
        <line
          x1="300"
          y1="300"
          x2="300"
          y2="10"
          stroke="rgba(46,230,200,0.18)"
          strokeWidth="1.5"
          className="sonar__sweep"
        />
        {[0, 45, 90, 135].map((a) => (
          <line
            key={a}
            x1="300"
            y1="300"
            x2={300 + 290 * Math.cos((a * Math.PI) / 180)}
            y2={300 + 290 * Math.sin((a * Math.PI) / 180)}
            stroke="rgba(120,150,170,0.06)"
            strokeWidth="1"
          />
        ))}
      </svg>
      <style>{`
        .sonar {
          position: absolute; top: -8%; right: -14%;
          width: min(720px, 78vw); aspect-ratio: 1;
          z-index: 1; opacity: 0.85;
          mask-image: radial-gradient(circle at center, #000 30%, transparent 72%);
          pointer-events: none;
        }
        .sonar__sweep { transform-origin: 300px 300px; animation: sweep 8s linear infinite; }
        @keyframes sweep { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) { .sonar__sweep { animation: none; } }
        @media (max-width: 760px) { .sonar { opacity: 0.4; right: -30%; } }
      `}</style>
    </div>
  );
}
