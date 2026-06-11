import type { Metadata, Viewport } from 'next';
import { Fraunces, Archivo, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const fraunces = Fraunces({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  variable: '--font-fraunces',
  display: 'swap',
  axes: ['SOFT', 'WONK', 'opsz'],
});

const archivo = Archivo({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-archivo',
  display: 'swap',
});

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Helm — regime-switching BSC strategy engine',
  description:
    'Helm reads the market regime, switches strategy, and a trend-filter gate holds cash through bears — same Sharpe class as the market with a 3.6x smaller max drawdown. Validated, walk-forward, out-of-sample. Built for BNB Hack Track 2.',
  authors: [{ name: 'Helm' }],
  openGraph: {
    title: 'Helm — read the regime, hold the course',
    description:
      'Regime-switching BSC trading engine. Same Sharpe class as the market, 3.6x smaller max drawdown. BNB Hack Track 2.',
    type: 'website',
  },
};

export const viewport: Viewport = {
  themeColor: '#070b10',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <style>{`
          :root {
            --font-display: ${fraunces.style.fontFamily}, Georgia, serif;
            --font-sans: ${archivo.style.fontFamily}, Helvetica, Arial, sans-serif;
            --font-mono: ${jetbrains.style.fontFamily}, ui-monospace, monospace;
          }
        `}</style>
      </head>
      <body
        className={`${fraunces.variable} ${archivo.variable} ${jetbrains.variable}`}
      >
        <div className="grain" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
