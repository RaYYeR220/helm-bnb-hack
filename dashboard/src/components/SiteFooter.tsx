'use client';

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="wrap footer__inner">
        <div className="footer__brand">
          <span className="footer__word mono">HELM</span>
          <p className="footer__tag">
            Read the regime. Hold the course. A regime-switching BSC
            trading-strategy engine.
          </p>
        </div>
        <div className="footer__cols">
          <div className="footer__col">
            <span className="footer__h mono">HACKATHON</span>
            <span>BNB Hack · Track 2 — Strategy Skills</span>
            <span>CoinMarketCap × Trust Wallet</span>
            <span>Targeting Best Use of Agent Hub</span>
          </div>
          <div className="footer__col">
            <span className="footer__h mono">PROJECT</span>
            <span>MIT licensed</span>
            <span>171 tests, fully green</span>
            <span>No live network calls in tests</span>
          </div>
          <div className="footer__col">
            <span className="footer__h mono">STACK</span>
            <span>Python · hmmlearn · pandas</span>
            <span>Next.js · TypeScript · recharts</span>
            <span>Static export — runs anywhere</span>
          </div>
        </div>
      </div>
      <div className="wrap footer__base mono">
        <span>© 2026 Helm · MIT</span>
        <span className="footer__nfa">Research tooling — not financial advice.</span>
      </div>
      <style>{`
        .footer {
          border-top: 1px solid var(--line-strong);
          padding: 70px 0 40px;
          background: linear-gradient(180deg, transparent, rgba(46,230,200,0.03));
          position: relative;
        }
        .footer::before {
          content: ''; position: absolute; top: -1px; left: 0; right: 0; height: 1px;
          background: linear-gradient(90deg, transparent, var(--helm), transparent);
          opacity: 0.5;
        }
        .footer__inner { display: grid; grid-template-columns: 1fr 1.4fr; gap: 50px; }
        .footer__word { font-size: 22px; font-weight: 700; letter-spacing: 0.34em; }
        .footer__tag { color: var(--mute); font-size: 14px; max-width: 320px; margin: 14px 0 0; line-height: 1.6; }
        .footer__cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
        .footer__col { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--ink-dim); }
        .footer__h { font-size: 10px; letter-spacing: 0.16em; color: var(--mute); margin-bottom: 4px; }
        .footer__base {
          display: flex; justify-content: space-between; margin-top: 50px;
          padding-top: 24px; border-top: 1px solid var(--line);
          font-size: 11px; color: var(--faint); letter-spacing: 0.06em;
        }
        .footer__nfa { color: var(--amber); opacity: 0.8; }
        @media (max-width: 760px) {
          .footer__inner { grid-template-columns: 1fr; gap: 32px; }
          .footer__cols { grid-template-columns: 1fr 1fr; }
          .footer__base { flex-direction: column; gap: 8px; }
        }
      `}</style>
    </footer>
  );
}
