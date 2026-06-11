"""Regime classifier (single read) and causal walk-forward regime path.

`RegimeClassifier.read` produces a `RegimeRead` for the last date of a price
window. `compute_regime_path` walks forward causally, periodically refitting,
and returns a per-date label Series the router consumes.
"""

import pandas as pd

from helm.regime.attribution import attribute
from helm.regime.features import FEATURE_COLS, compute_feature_panel
from helm.regime.hmm_model import RegimeHMM
from helm.types import RegimeRead


class RegimeClassifier:
    def __init__(
        self,
        hmm: RegimeHMM,
        vol_window: int = 20,
        trend_window: int = 20,
        breadth_window: int = 20,
        extra_features: pd.DataFrame | None = None,
    ):
        self.hmm = hmm
        self.vol_window = vol_window
        self.trend_window = trend_window
        self.breadth_window = breadth_window
        # date-indexed extra columns (e.g. on-chain TVL features). Joined onto
        # the market features by date BEFORE the HMM sees them; see _features.
        self.extra_features = (
            extra_features.sort_index() if extra_features is not None else None
        )
        self._feature_panel: pd.DataFrame | None = None

    def _features(self, prices: pd.DataFrame) -> pd.DataFrame:
        feats = compute_feature_panel(
            prices,
            vol_window=self.vol_window,
            trend_window=self.trend_window,
            breadth_window=self.breadth_window,
        )
        if self.extra_features is None or self.extra_features.empty:
            return feats
        # CAUSAL JOIN: a daily left-join + ffill-to-last-known. Each market-feature
        # date d takes the most recent extra-feature row with date <= d (ffill);
        # extra rows dated AFTER d are never used (a left reindex onto feats.index
        # followed by ffill cannot pull a future row backward). Residual leading
        # gaps (extra starts after feats) are zero-filled so the matrix is finite.
        extra = self.extra_features.reindex(feats.index, method="ffill")
        extra = extra.reindex(feats.index)  # ensure exact alignment
        joined = feats.join(extra, how="left").ffill().fillna(0.0)
        return joined

    def fit(self, prices: pd.DataFrame) -> "RegimeClassifier":
        feats = self._features(prices)
        # If extras are present, the HMM must train on the union of columns.
        if self.extra_features is not None and not self.extra_features.empty:
            cols = list(FEATURE_COLS) + list(self.extra_features.columns)
            self.hmm._feature_cols = cols
        self.hmm.fit(feats)
        self._feature_panel = feats
        return self

    def read(self, prices_hist: pd.DataFrame) -> RegimeRead:
        feats = self._features(prices_hist)
        last = feats.iloc[[-1]]                      # 1-row frame
        date = last.index[-1]
        proba = self.hmm.predict_proba(last).iloc[0]  # Series: label -> prob
        posterior = {k: float(v) for k, v in proba.items()}
        regime = max(posterior, key=posterior.get)
        confidence = float(posterior[regime])

        raw_row = last.iloc[0]
        features = {k: float(v) for k, v in raw_row.items()}

        z = self.hmm.standardize_row(raw_row)
        signature = self.hmm.signatures()[regime]
        attribution = attribute(z, signature)

        return RegimeRead(
            date=date,
            regime=regime,
            posterior=posterior,
            confidence=confidence,
            features=features,
            attribution=attribution,
        )


def compute_regime_path(
    prices: pd.DataFrame,
    min_train: int = 60,
    refit_every: int = 5,
    vol_window: int = 20,
    trend_window: int = 20,
    breadth_window: int = 20,
    seed: int = 0,
    extra_features: pd.DataFrame | None = None,
) -> pd.Series:
    """Causal walk-forward regime labels.

    For each integer position t >= min_train, (re)fit a fresh classifier on
    prices.iloc[:t+1] every `refit_every` positions (reusing the last fit in
    between), then read the regime at t. Uses no data after t.

    Optional ``extra_features``: a date-indexed DataFrame of additional columns
    (e.g. on-chain TVL features) that is causally ffill-joined onto the market
    feature panel BEFORE the HMM sees it. The join is causal: only rows with
    date <= the current window's last date are used (reindex+ffill). With
    ``extra_features=None`` (default) the path is bit-identical to the pre-change
    behaviour.

    Returns a Series indexed by date (positions >= min_train) of label strings.
    The per-date full `RegimeRead` objects are also returned via the Series'
    `.attrs["reads"]` dict (date -> RegimeRead) for downstream explainability.
    """
    prices = prices.sort_index()
    dates = prices.index
    n = len(dates)

    labels: dict[pd.Timestamp, str] = {}
    reads: dict[pd.Timestamp, RegimeRead] = {}

    clf: RegimeClassifier | None = None
    since_fit = 0
    for t in range(min_train, n):
        window = prices.iloc[: t + 1]
        need_fit = clf is None or since_fit >= refit_every
        if need_fit:
            cols = (
                None
                if extra_features is None or extra_features.empty
                else list(FEATURE_COLS) + list(extra_features.columns)
            )
            clf = RegimeClassifier(
                hmm=RegimeHMM(seed=seed, feature_cols=cols),
                vol_window=vol_window,
                trend_window=trend_window,
                breadth_window=breadth_window,
                extra_features=extra_features,
            )
            clf.fit(window)
            since_fit = 0
        else:
            since_fit += 1

        read = clf.read(window)
        date = dates[t]
        labels[date] = read.regime
        reads[date] = read

    path = pd.Series(labels, name="regime")
    path.index = pd.DatetimeIndex(path.index)
    path = path.sort_index()
    path.attrs["reads"] = reads
    return path
