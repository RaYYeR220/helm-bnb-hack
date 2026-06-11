'use client';

import { useEffect, useState } from 'react';

const LINKS = [
  ['equity', 'Equity'],
  ['gate', 'The gate'],
  ['oos', 'Walk-forward'],
  ['dq', 'DQ survival'],
  ['arch', 'Architecture'],
];

export function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={`nav ${scrolled ? 'nav--solid' : ''}`}>
      <div className="wrap nav__inner">
        <a href="#top" className="nav__brand" aria-label="Helm — back to top">
          <WheelMark />
          <span className="nav__word">HELM</span>
        </a>
        <nav className="nav__links" aria-label="Sections">
          {LINKS.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </nav>
        <span className="nav__badge mono">TRACK 2 · STRATEGY SKILLS</span>
      </div>
      <style>{`
        .nav {
          position: fixed; top: 0; left: 0; right: 0; z-index: 40;
          transition: background 0.3s, border-color 0.3s, backdrop-filter 0.3s;
          border-bottom: 1px solid transparent;
        }
        .nav--solid {
          background: rgba(7, 11, 16, 0.72);
          backdrop-filter: blur(14px) saturate(140%);
          border-bottom-color: var(--line);
        }
        .nav__inner {
          height: 62px;
          display: flex; align-items: center; gap: 24px;
        }
        .nav__brand {
          display: inline-flex; align-items: center; gap: 11px;
          color: var(--ink); text-decoration: none;
        }
        .nav__word {
          font-family: var(--font-mono); font-weight: 700;
          letter-spacing: 0.34em; font-size: 14px;
        }
        .nav__links {
          display: flex; gap: 22px; margin-left: auto;
        }
        .nav__links a {
          font-family: var(--font-mono);
          font-size: 12px; letter-spacing: 0.06em;
          color: var(--mute); text-decoration: none;
          transition: color 0.2s;
        }
        .nav__links a:hover { color: var(--helm); }
        .nav__badge {
          font-size: 10px; letter-spacing: 0.16em;
          color: var(--faint);
          padding: 5px 11px; border: 1px solid var(--line);
          border-radius: 999px;
        }
        @media (max-width: 860px) {
          .nav__links { display: none; }
          .nav__badge { margin-left: auto; }
        }
        @media (max-width: 520px) {
          .nav__badge { display: none; }
        }
      `}</style>
    </header>
  );
}

// Compact ship's-wheel mark rendered as SVG.
function WheelMark() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="24" cy="24" r="9" stroke="var(--helm)" strokeWidth="2" />
      <circle cx="24" cy="24" r="3" fill="var(--helm)" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const r1 = 9;
        const r2 = 21;
        const rad = (a * Math.PI) / 180;
        const x1 = 24 + r1 * Math.cos(rad);
        const y1 = 24 + r1 * Math.sin(rad);
        const x2 = 24 + r2 * Math.cos(rad);
        const y2 = 24 + r2 * Math.sin(rad);
        return (
          <line
            key={a}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="var(--helm)"
            strokeWidth="2"
            strokeLinecap="round"
            opacity={a % 90 === 0 ? 1 : 0.5}
          />
        );
      })}
      <circle
        cx="24"
        cy="24"
        r="21"
        stroke="var(--helm)"
        strokeWidth="1"
        opacity="0.4"
        strokeDasharray="2 4"
      />
    </svg>
  );
}
