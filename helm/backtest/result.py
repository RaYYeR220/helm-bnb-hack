"""Backtest configuration and result container (JSON-artifact emitter)."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class BacktestConfig:
    fee_bps: float = 10.0          # per-side trading fee (basis points)
    slippage_bps: float = 5.0      # per-side slippage (basis points)
    initial_capital: float = 10_000.0


def _series_records(s: pd.Series) -> list[dict]:
    return [
        {"date": d.strftime("%Y-%m-%d"), "value": (None if pd.isna(v) else float(v))}
        for d, v in s.items()
    ]


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict
    strategy_name: str
    meta: dict = field(default_factory=dict)

    def to_json(self, path: str | Path) -> None:
        """Write a dashboard-friendly JSON artifact."""
        payload = {
            "strategy_name": self.strategy_name,
            "metrics": self.metrics,
            "equity": _series_records(self.equity),
            "returns": _series_records(self.returns),
            "weights": [
                {"date": d.strftime("%Y-%m-%d"), **{k: float(v) for k, v in row.dropna().items()}}
                for d, row in self.weights.iterrows()
            ],
            "meta": self.meta,
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
