'use client';

import { useEffect, useState } from 'react';
import { loadHelmData } from '@/lib/data';
import type { HelmData } from '@/lib/types';
import { useReveal } from '@/lib/useReveal';
import { Hero } from '@/components/Hero';
import { EquitySection } from '@/components/EquitySection';
import { GateSection } from '@/components/GateSection';
import { WalkForwardSection } from '@/components/WalkForwardSection';
import { DqSection } from '@/components/DqSection';
import { ArchitectureSection } from '@/components/ArchitectureSection';
import { LimitationsSection } from '@/components/LimitationsSection';
import { SiteFooter } from '@/components/SiteFooter';
import { Nav } from '@/components/Nav';

export default function Page() {
  const [data, setData] = useState<HelmData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHelmData()
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)));
  }, []);

  // Re-run reveal observers once data has rendered (dep on data presence).
  useReveal(data);

  if (error) {
    return (
      <main className="wrap" style={{ padding: '120px 28px' }}>
        <p className="eyebrow">Data error</p>
        <h1 style={{ fontSize: 32, marginTop: 16 }}>Could not load artifacts</h1>
        <p className="mono" style={{ color: 'var(--danger)', marginTop: 12 }}>
          {error}
        </p>
        <p style={{ color: 'var(--mute)', marginTop: 8 }}>
          Run <code>npm run sync-data</code> to snapshot the JSON artifacts into
          <code> public/data/</code>.
        </p>
      </main>
    );
  }

  if (!data) {
    return <LoadingScreen />;
  }

  return (
    <>
      <Nav />
      <main>
        <Hero data={data} />
        <EquitySection data={data} />
        <GateSection data={data} />
        <WalkForwardSection data={data} />
        <DqSection data={data} />
        <ArchitectureSection />
        <LimitationsSection />
      </main>
      <SiteFooter />
    </>
  );
}

function LoadingScreen() {
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <div className="helm-spinner" aria-hidden="true" />
        <p
          className="eyebrow"
          style={{ marginTop: 22, justifyContent: 'center' }}
        >
          Reading the regime…
        </p>
      </div>
      <style>{`
        .helm-spinner {
          width: 54px; height: 54px; margin: 0 auto;
          border: 2px solid rgba(46,230,200,0.18);
          border-top-color: var(--helm);
          border-radius: 50%;
          animation: spin 0.9s linear infinite;
          box-shadow: var(--glow-helm);
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </main>
  );
}
