// Central palette + label maps. Colors mirror the CSS custom properties in
// globals.css so chart series (recharts needs literal color strings) stay in
// sync with the rest of the instrument-deck theme.

import type { RegimeLabel, StrategyKey } from './types';

export const COLORS = {
  bg: '#070b10',
  panel: '#0c131b',
  ink: '#e8eef2',
  mute: '#7d8d99',
  // Phosphor teal — Helm's signature line / sonar glow
  helm: '#2ee6c8',
  // Warm amber — risk-off gate / caution
  amber: '#f5a524',
  // Coral red — danger, drawdown, DQ line
  danger: '#ff5d5d',
  // Slate blues for the also-ran baselines
  steel: '#5b7fb0',
  violet: '#9b8cff',
  sand: '#c7a36a',
} as const;

// Per-strategy color + display label for the equity overlay.
export const STRATEGY_META: Record<
  StrategyKey,
  { label: string; color: string; emphasis?: boolean }
> = {
  helm: { label: 'Helm (gated)', color: COLORS.helm, emphasis: true },
  helm_ungated: { label: 'Helm — gate off', color: COLORS.violet },
  momentum: { label: 'Momentum', color: COLORS.sand },
  mean_reversion: { label: 'Mean reversion', color: COLORS.danger },
  equal_weight: { label: 'Equal-weight market', color: COLORS.steel },
};

// Regime band colors used for the chart background overlay + legends.
export const REGIME_META: Record<
  RegimeLabel,
  { label: string; color: string; band: string }
> = {
  trending: { label: 'Trending', color: COLORS.helm, band: 'rgba(46,230,200,0.10)' },
  ranging: { label: 'Ranging', color: COLORS.steel, band: 'rgba(91,127,176,0.10)' },
  high_volatility: {
    label: 'High volatility',
    color: COLORS.amber,
    band: 'rgba(245,165,36,0.12)',
  },
  unclassified: {
    label: 'Warm-up',
    color: COLORS.mute,
    band: 'rgba(125,141,153,0.06)',
  },
};

// Per-config labels for the walk-forward OOS tables/bars.
export const CONFIG_LABELS: Record<string, string> = {
  helm_gated: 'Helm · gated',
  helm_gated_tvl: 'Helm · gated + TVL',
  helm_gated_tvl_confirmed: 'Helm · gated + TVL + confirm',
  helm_gate_confirm2: 'Helm · gate confirm-2',
  helm_gate_confirm3: 'Helm · gate confirm-3',
  helm_ungated: 'Helm · gate off',
  momentum: 'Momentum',
  equal_weight: 'Equal-weight market',
};
