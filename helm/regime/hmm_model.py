"""3-state Gaussian HMM with deterministic state->regime labeling.

States are unidentifiable up to permutation, so we attach a deterministic label
map from each state's standardized feature signature:
  - the state with the highest mean standardized `realized_vol` -> high_volatility;
  - of the remaining two, the one with higher mean |standardized trend_strength|
    -> trending; the last -> ranging.

EM is non-convex: with `random_state` fixed to a single value the fit can land
in a degenerate local optimum that collapses two true regimes into one state
(empirically verified — the default seed merged trending+ranging). We therefore
fit `n_restarts` HMMs over the deterministic seed range `[seed, seed+n_restarts)`
and keep the highest-log-likelihood model. This stays fully deterministic for a
fixed `seed` while reliably recovering the three-regime structure.
"""

import logging
import warnings

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from helm.regime.features import FEATURE_COLS
from helm.types import REGIMES


class RegimeHMM:
    def __init__(
        self,
        n_components: int = 3,
        seed: int = 0,
        n_restarts: int = 8,
        feature_cols: list[str] | None = None,
    ):
        self.n_components = n_components
        self.seed = seed
        self.n_restarts = n_restarts
        self._model: GaussianHMM | None = None
        self._scaler: StandardScaler | None = None
        self._state_to_label: dict[int, str] = {}
        self._signatures: dict[str, dict] = {}
        # Default -> the four market features (bit-identical to the old behavior);
        # callers may pass FEATURE_COLS + extra on-chain columns. Labeling still
        # keys off realized_vol / trend_strength, so extra columns are safe.
        self._feature_cols = (
            list(FEATURE_COLS) if feature_cols is None else list(feature_cols)
        )

    def _fit_best(self, Xz: np.ndarray) -> GaussianHMM:
        """Fit n_restarts HMMs over a deterministic seed range; keep the best
        by log-likelihood. Falls back to a single fit if every restart errors."""
        best_score = -np.inf
        best_model: GaussianHMM | None = None
        for r in range(max(1, self.n_restarts)):
            model = GaussianHMM(
                n_components=self.n_components,
                covariance_type="diag",
                n_iter=200,
                tol=1e-4,
                random_state=self.seed + r,
            )
            try:
                # hmmlearn reports non-convergence at n_iter via the `logging`
                # module (not `warnings`); that is benign here since we keep the
                # best of many restarts. Silence both channels for clean output.
                hmm_logger = logging.getLogger("hmmlearn")
                prev_level = hmm_logger.level
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    hmm_logger.setLevel(logging.ERROR)
                    try:
                        model.fit(Xz)
                        score = float(model.score(Xz))
                    finally:
                        hmm_logger.setLevel(prev_level)
            except Exception:
                continue
            if score > best_score:
                best_score = score
                best_model = model
        if best_model is None:
            best_model = GaussianHMM(
                n_components=self.n_components,
                covariance_type="diag",
                n_iter=200,
                random_state=self.seed,
            )
            best_model.fit(Xz)
        return best_model

    def fit(self, features: pd.DataFrame) -> "RegimeHMM":
        X = features[self._feature_cols].to_numpy(dtype=float)

        self._scaler = StandardScaler().fit(X)
        Xz = self._scaler.transform(X)

        self._model = self._fit_best(Xz)
        model = self._model

        # Per-state standardized feature means (signatures), in FEATURE_COLS order.
        means = model.means_  # shape (n_components, n_features)
        vol_i = self._feature_cols.index("realized_vol")
        trend_i = self._feature_cols.index("trend_strength")

        states = list(range(self.n_components))
        # 1) highest mean standardized realized_vol -> high_volatility
        hv = max(states, key=lambda s: means[s, vol_i])
        remaining = [s for s in states if s != hv]
        # 2) of the rest, higher mean |standardized trend_strength| -> trending
        tr = max(remaining, key=lambda s: abs(means[s, trend_i]))
        rg = [s for s in remaining if s != tr][0]

        self._state_to_label = {hv: "high_volatility", tr: "trending", rg: "ranging"}

        self._signatures = {
            self._state_to_label[s]: {
                col: float(means[s, j]) for j, col in enumerate(self._feature_cols)
            }
            for s in states
        }
        return self

    def _label_columns(self) -> list[str]:
        """State-index-ordered list of labels: column j corresponds to state j."""
        return [self._state_to_label[s] for s in range(self.n_components)]

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        if self._model is None or self._scaler is None:
            raise RuntimeError("RegimeHMM must be fit before predict_proba.")
        X = features[self._feature_cols].to_numpy(dtype=float)
        Xz = self._scaler.transform(X)
        proba = self._model.predict_proba(Xz)  # (n, n_components), by state index

        df = pd.DataFrame(proba, index=features.index, columns=self._label_columns())
        # Reorder to the canonical REGIMES order for a stable column layout.
        return df[list(REGIMES)]

    def signatures(self) -> dict:
        """regime label -> {feature: standardized mean}."""
        if not self._signatures:
            raise RuntimeError("RegimeHMM must be fit before signatures.")
        return self._signatures

    def standardize_row(self, row: pd.Series) -> dict:
        """Standardize a single raw feature row with the fitted scaler,
        returning {feature: z-score}. Used by the classifier for attribution."""
        if self._scaler is None:
            raise RuntimeError("RegimeHMM must be fit before standardize_row.")
        vec = row[self._feature_cols].to_numpy(dtype=float).reshape(1, -1)
        z = self._scaler.transform(vec).ravel()
        return {col: float(z[j]) for j, col in enumerate(self._feature_cols)}
