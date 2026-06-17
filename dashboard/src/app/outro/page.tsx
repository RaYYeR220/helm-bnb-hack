import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Helm — repo',
  description: 'Read the regime. Hold the course.',
};

const REPO = 'github.com/RaYYeR220/helm-bnb-hack';

const CHIPS = [
  ['3 sponsor SDKs', 'live'],
  ['ERC-8004 agent', '1368'],
  ['Deflated Sharpe', '0.94'],
  ['273 tests', 'green'],
] as const;

export default function OutroPage() {
  return (
    <main className="outro">
      <div className="outro__center">
        <div className="outro__mark">
          <span className="outro__halo" aria-hidden="true" />
          <Wheel size={104} />
        </div>

        <h1 className="outro__word">HELM</h1>
        <p className="outro__tag">Read the regime. Hold the course.</p>

        <a className="outro__repo" href={`https://${REPO}`}>
          <GitGlyph />
          <span className="outro__repo-url mono">{REPO}</span>
          <span className="outro__repo-arrow" aria-hidden="true">→</span>
        </a>

        <div className="outro__chips">
          {CHIPS.map(([k, v]) => (
            <span key={k} className="outro__chip mono">
              <span className="outro__dot" aria-hidden="true" />
              {k} <span className="outro__chip-v">· {v}</span>
            </span>
          ))}
        </div>

        <div className="outro__base mono">
          <span>BNB Hack · Track 2 — Strategy Skills</span>
          <span className="outro__sep">·</span>
          <span>CoinMarketCap × BNB Chain × Trust Wallet</span>
        </div>
        <p className="outro__nfa mono">Research tooling — not financial advice.</p>
      </div>

      <style>{`
        .outro {
          min-height: 100vh;
          display: grid; place-items: center;
          padding: 64px 32px;
          position: relative; overflow: hidden;
        }
        /* a faint horizon line + extra teal wash on top of the body atmosphere */
        .outro::before {
          content: ''; position: absolute; left: 0; right: 0; top: 50%;
          height: 1px; transform: translateY(-50%);
          background: linear-gradient(90deg, transparent, rgba(46,230,200,0.18), transparent);
          opacity: 0.6; pointer-events: none;
        }
        .outro__center {
          position: relative; z-index: 1;
          display: flex; flex-direction: column; align-items: center; text-align: center;
        }

        .outro__mark { position: relative; display: grid; place-items: center; margin-bottom: 26px; }
        .outro__halo {
          position: absolute; width: 220px; height: 220px; border-radius: 50%;
          background: radial-gradient(circle, rgba(46,230,200,0.22), transparent 62%);
          filter: blur(6px);
          animation: outroPulse 4.5s ease-in-out infinite;
        }
        @keyframes outroPulse {
          0%, 100% { transform: scale(0.92); opacity: 0.65; }
          50%      { transform: scale(1.08); opacity: 1; }
        }

        .outro__word {
          font-family: var(--font-mono); font-weight: 700;
          letter-spacing: 0.42em; font-size: 40px; line-height: 1;
          margin: 0 0 0 0.42em; /* optical centering for tracking */
          color: var(--ink);
        }
        .outro__tag {
          font-family: var(--font-display);
          font-size: clamp(22px, 2.4vw, 30px); font-style: italic;
          color: var(--ink-dim); margin: 18px 0 0;
        }

        .outro__repo {
          margin-top: 40px;
          display: inline-flex; align-items: center; gap: 14px;
          padding: 16px 26px;
          border: 1px solid rgba(46,230,200,0.45); border-radius: 14px;
          background: linear-gradient(180deg, rgba(46,230,200,0.08), rgba(46,230,200,0.02));
          box-shadow: 0 0 34px rgba(46,230,200,0.20), inset 0 0 22px rgba(46,230,200,0.05);
          text-decoration: none;
        }
        .outro__repo-url {
          font-size: clamp(20px, 2.2vw, 28px); font-weight: 600;
          letter-spacing: 0.01em; color: var(--helm);
          text-shadow: 0 0 18px rgba(46,230,200,0.45);
        }
        .outro__repo-arrow { color: var(--helm); font-size: 22px; opacity: 0.8; }

        .outro__chips {
          margin-top: 30px;
          display: flex; flex-wrap: wrap; justify-content: center; gap: 12px;
        }
        .outro__chip {
          display: inline-flex; align-items: center; gap: 8px;
          font-size: 13px; letter-spacing: 0.04em; color: var(--ink-dim);
          padding: 8px 14px; border: 1px solid var(--line);
          border-radius: 999px; background: rgba(12,19,27,0.6);
        }
        .outro__chip-v { color: var(--helm); }
        .outro__dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: var(--helm); box-shadow: 0 0 8px var(--helm);
        }

        .outro__base {
          margin-top: 46px;
          display: flex; align-items: center; gap: 12px; flex-wrap: wrap; justify-content: center;
          font-size: 12px; letter-spacing: 0.10em; color: var(--mute);
        }
        .outro__sep { color: var(--faint); }
        .outro__nfa {
          margin-top: 12px; font-size: 11px; letter-spacing: 0.08em;
          color: var(--amber); opacity: 0.75;
        }

        @media (max-width: 720px) {
          .outro__word { font-size: 30px; }
          .outro__repo { padding: 14px 18px; gap: 10px; }
          .outro__base { flex-direction: column; gap: 4px; }
          .outro__sep { display: none; }
        }
      `}</style>
    </main>
  );
}

// Ship's-wheel mark (matches the nav), parameterized by size.
function Wheel({ size = 104 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <circle cx="24" cy="24" r="9" stroke="var(--helm)" strokeWidth="1.6" />
      <circle cx="24" cy="24" r="3" fill="var(--helm)" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const rad = (a * Math.PI) / 180;
        const x1 = 24 + 9 * Math.cos(rad);
        const y1 = 24 + 9 * Math.sin(rad);
        const x2 = 24 + 21 * Math.cos(rad);
        const y2 = 24 + 21 * Math.sin(rad);
        return (
          <line
            key={a}
            x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="var(--helm)" strokeWidth="1.6" strokeLinecap="round"
            opacity={a % 90 === 0 ? 1 : 0.5}
          />
        );
      })}
      <circle
        cx="24" cy="24" r="21"
        stroke="var(--helm)" strokeWidth="0.8" opacity="0.4" strokeDasharray="2 4"
      />
    </svg>
  );
}

function GitGlyph() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="var(--helm)" aria-hidden="true" opacity="0.92">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.37-3.37-1.37-.46-1.18-1.11-1.5-1.11-1.5-.91-.64.07-.62.07-.62 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.36-2.22-.26-4.55-1.14-4.55-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05a9.32 9.32 0 0 1 5 0c1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.82 0 .27.18.6.69.49A10.02 10.02 0 0 0 22 12.25C22 6.58 17.52 2 12 2z" />
    </svg>
  );
}
