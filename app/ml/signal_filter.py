# app/ml/signal_filter.py
"""SignalFilter — lightweight ML pre-filter for signals before LLM."""
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FilterFeatures:
    rsi: float
    macd: float
    atr_pct: float
    volume_ratio: float
    bollinger_position: float
    rs_vs_spy: float
    day_of_week: int  # 0=Mon, 6=Sun
    hour: int


class SignalFilter:
    """
    Lightweight logistic regression filter for trading signals.
    Predicts P(win) and rejects weak signals before LLM analysis.
    
    Features: RSI, MACD, ATR, volume, Bollinger, RS vs SPY, day, hour
    """

    THRESHOLD = 0.45
    MODEL_PATH = "models/signal_filter.pkl"

    def __init__(self, model_path: str = None):
        self.model_path = model_path or self.MODEL_PATH
        self._model = None
        self._scaler = None
        self._load_model()

    def _load_model(self) -> None:
        """Load pre-trained model if available."""
        path = Path(self.model_path)
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self._model = data.get("model")
                    self._scaler = data.get("scaler")
                logger.info("Signal filter model loaded")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")
        else:
            logger.info("No signal filter model found — using heuristic fallback")

    def _extract_features(self, features) -> list:
        """Extract numeric features from FeatureSet, dict, or similar object."""
        def _get(key, default):
            if isinstance(features, dict):
                return features.get(key, default) or default
            return getattr(features, key, default) or default

        return [
            _get('rsi_14', 50),
            _get('macd_line', 0),
            _get('atr_pct', 2.0),
            _get('volume_ratio_20d', 1.0),
            _get('bollinger_position', 0.5),
            _get('rs_vs_spy_30d', 0),
            _get('day_of_week', 0),
            _get('hour', 10),
            _get('rsi_1h', 50),            # NEW: hourly RSI
            _get('volume_ratio_1h', 1.0),  # NEW: hourly volume ratio
        ]

    def predict(self, features) -> float:
        """
        Predict P(win) for a signal.
        Returns probability between 0 and 1.
        """
        if self._model is None:
            # Heuristic fallback when no model is trained
            return self._heuristic_predict(features)
        
        try:
            X = [self._extract_features(features)]
            if self._scaler:
                X = self._scaler.transform(X)
            proba = self._model.predict_proba(X)[0][1]  # P(class=1)
            return float(proba)
        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            return self._heuristic_predict(features)

    def _heuristic_predict(self, features) -> float:
        """Simple heuristic when model is not available."""
        score = 0.5
        
        # RSI extremes are good
        rsi = getattr(features, 'rsi_14', 50) or 50
        if rsi < 30 or rsi > 70:
            score += 0.1
        
        # High volume confirmation
        vol = getattr(features, 'volume_ratio_20d', 1.0) or 1.0
        if vol > 1.5:
            score += 0.1
        
        # ATR not too high
        atr = getattr(features, 'atr_pct', 2.0) or 2.0
        if atr > 4.0:
            score -= 0.1
        
        # Positive RS vs SPY
        rs = getattr(features, 'rs_vs_spy_30d', 0) or 0
        if rs > 0.02:
            score += 0.05
        
        return max(0.0, min(1.0, score))

    def should_ignore(self, features) -> bool:
        """Returns True if signal should be ignored (P(win) < threshold)."""
        p_win = self.predict(features)
        return p_win < self.THRESHOLD

    def retrain(self, trades: list) -> "float | bool":
        """
        Retrain model with trade data. trades can be:
        - list of dicts (from get_closed_trades_with_snapshots)
        - list of Trade objects with feature_snapshot_id
        Returns AUC float on success, False on failure/insufficient data.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import TimeSeriesSplit, cross_val_score

            X = []
            y = []

            for trade in trades:
                # Support both dict (from JOIN query) and Trade objects
                if isinstance(trade, dict):
                    snap = trade  # dict has all snapshot fields
                    pnl = trade.get("pnl_pct", 0) or 0
                else:
                    snap_id = getattr(trade, "feature_snapshot_id", None)
                    if not snap_id:
                        continue
                    from app.db.database import get_feature_snapshot_by_id
                    snap_or_none = get_feature_snapshot_by_id(snap_id)
                    if snap_or_none is None:
                        continue
                    snap = snap_or_none
                    pnl = getattr(trade, "pnl_pct", 0) or 0

                X.append(self._extract_features(snap))
                y.append(1 if pnl > 0 else 0)

            if len(X) < 10:
                logger.warning(f"Not enough data to retrain: {len(X)} samples")
                return False

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Evaluate with TimeSeriesSplit (no future leakage)
            n_splits = min(5, max(2, len(X) // 5))
            tscv = TimeSeriesSplit(n_splits=n_splits)
            try:
                model_eval = LogisticRegression(max_iter=1000)
                auc_scores = cross_val_score(
                    model_eval, X_scaled, y, cv=tscv, scoring="roc_auc"
                )
                auc = float(auc_scores.mean())
            except Exception as cv_err:
                logger.warning(f"CV failed ({cv_err}), using 0.5 as AUC")
                auc = 0.5

            # Train final model on all data
            try:
                model = LogisticRegression(max_iter=1000)
                model.fit(X_scaled, y)
            except Exception as fit_err:
                logger.warning(f"Final model fit failed ({fit_err}), returning AUC only")
                return auc

            # Save
            Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": model, "scaler": scaler}, f)

            self._model = model
            self._scaler = scaler
            logger.info(f"Model retrained with {len(X)} samples. CV AUC: {auc:.3f}")
            return auc

        except ImportError:
            logger.warning("scikit-learn not available, cannot retrain")
            return False
        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            return False


# Singleton
_filter_instance = None


def get_signal_filter() -> SignalFilter:
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = SignalFilter()
    return _filter_instance
