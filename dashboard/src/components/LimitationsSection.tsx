'use client';

const LIMITS = [
  {
    title: 'DEX-volume depth is ~182 days.',
    body: 'The free GeckoTerminal tier caps per-token daily candles at 182. On older panel dates the on-chain-confirmed momentum variant degrades gracefully to plain momentum (keep-if-no-data fallback). TVL history is deep; per-token DEX volume is not.',
  },
  {
    title: 'A flash-crash tail day exists in the sample.',
    body: 'Single-day extreme moves are in the data; Helm’s defensive / risk-off stance mitigates but does not erase tail-day P&L. The reported drawdowns include it.',
  },
  {
    title: 'Market-data-only reads are weaker pre-fusion.',
    body: 'Without the on-chain TVL features the bare 3-state HMM is less able to separate a grinding bear from a true range — which is exactly why the risk-off gate is a separate, hard-coded trend filter, not something we ask the HMM to learn.',
  },
  {
    title: '8-major universe for the headline numbers.',
    body: 'The full BEP-20 universe ships in the repo; the validated headline run uses the liquid, data-rich 8-major subset for clean OHLCV coverage.',
  },
];

export function LimitationsSection() {
  return (
    <section id="limits">
      <div className="wrap">
        <div className="section-head reveal">
          <span className="eyebrow">07 · Honest limitations</span>
          <h2>We&rsquo;d rather state these than have a judge find them.</h2>
        </div>
        <div className="limits-grid">
          {LIMITS.map((l, i) => (
            <div key={l.title} className="limit reveal" style={{ transitionDelay: `${i * 70}ms` }}>
              <span className="limit__mark mono">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <h3 className="limit__title">{l.title}</h3>
                <p className="limit__body">{l.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        .limits-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
        .limit {
          display: flex; gap: 16px; padding: 28px 30px;
          background: var(--panel); border: 0.5px solid var(--line);
        }
        .limit__mark {
          font-size: 13px; color: var(--helm); flex: none;
          padding-top: 3px; opacity: 0.7;
        }
        .limit__title {
          font-family: var(--font-display); font-size: 19px; margin-bottom: 8px;
          line-height: 1.2; color: var(--ink);
        }
        .limit__body { font-size: 13.5px; color: var(--ink-dim); margin: 0; line-height: 1.6; }
        @media (max-width: 720px) { .limits-grid { grid-template-columns: 1fr; } }
      `}</style>
    </section>
  );
}
