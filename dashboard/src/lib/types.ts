// Type definitions mirroring the exact field names in the three Helm artifacts.
// Field names are load-bearing — they match data_cache/*.json verbatim.

export type RegimeLabel =
  | 'trending'
  | 'ranging'
  | 'high_volatility'
  | 'unclassified';

export interface RegimePoint {
  date: string; // ISO yyyy-mm-dd
  regime: RegimeLabel;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface StrategyMetrics {
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  win_rate: number;
  turnover: number;
  total_return: number;
}

export interface Strategy {
  metrics: StrategyMetrics;
  equity: EquityPoint[];
}

export interface RegimeAttributionEntry {
  days: number;
  total_return: number;
  mean_return: number;
  share_of_pnl: number;
}

export type StrategyKey =
  | 'helm'
  | 'helm_ungated'
  | 'momentum'
  | 'mean_reversion'
  | 'equal_weight';

export interface RegimeArtifact {
  regime_path: RegimePoint[];
  regime_attribution: Record<string, RegimeAttributionEntry>;
  strategies: Record<StrategyKey, Strategy>;
}

// ---- onchain_validation_artifact.json ----

export interface PerConfigOos {
  mean_sharpe: number;
  mean_total_return: number;
  mean_max_drawdown: number;
}

export interface RegimeValueCounts {
  ranging: number;
  trending: number;
  high_volatility: number;
}

export interface OnchainArtifact {
  panel: { days: number; symbols: string[] };
  onchain_feature_cols: string[];
  dex_volume_coverage_days: number;
  regime_value_counts: { baseline: RegimeValueCounts; tvl: RegimeValueCounts };
  selection: {
    oos: Record<string, number>;
    n_trials: number;
    selected_variant: string;
  };
  per_config_oos: Record<string, PerConfigOos>;
  deflated_sharpe: { value: number; n_trials: number; sr_variance: number };
  bootstrap: {
    sharpe: { lo: number; hi: number; point: number };
    total_return: { lo: number; hi: number; point: number };
  };
}

// ---- validation_artifact.json (earlier 3y harness) ----

export interface PerWindowRow {
  window_id: number;
  chosen: string;
  n_days: number;
  total_return: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
}

export interface ValidationArtifact {
  panel: { days: number; symbols: string[] };
  regime_value_counts: RegimeValueCounts;
  selection: {
    per_window: PerWindowRow[];
    oos: Record<string, number>;
    n_trials: number;
    selected_variant: string;
  };
  per_config_oos: Record<string, PerConfigOos>;
  deflated_sharpe: { value: number; n_trials: number; sr_variance: number };
  bootstrap: {
    sharpe: { lo: number; hi: number; point: number };
    total_return: { lo: number; hi: number; point: number };
  };
}

export interface HelmData {
  regime: RegimeArtifact;
  onchain: OnchainArtifact;
  validation: ValidationArtifact;
}
