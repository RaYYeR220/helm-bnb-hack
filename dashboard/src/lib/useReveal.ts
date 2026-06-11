'use client';

import { useEffect } from 'react';

// Adds `.in` to every `.reveal` element as it scrolls into view, driving the
// staggered entrance animation defined in globals.css. Re-runs whenever `dep`
// changes so elements rendered after an async data load also get observed.
export function useReveal(dep?: unknown): void {
  useEffect(() => {
    const els = Array.from(
      document.querySelectorAll<HTMLElement>('.reveal:not(.in)')
    );
    if (els.length === 0) return;

    if (!('IntersectionObserver' in window)) {
      els.forEach((el) => el.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -6% 0px' }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [dep]);
}
