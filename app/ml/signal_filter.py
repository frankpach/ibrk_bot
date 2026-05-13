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
        """Extract numeric features from FeatureSet or similar object."""
        return [
            getattr(features, 'rsi_14', 50) or 50,
            getattr(features, 'macd_line', 0) or 0,
            getattr(features, 'atr_pct', 2.0) or 2.0,
            getattr(features, 'volume_ratio_20d', 1.0) or 1.0,
            getattr(features, 'bollinger_position', 0.5) or 0.5,
            getattr(features, 'rs_vs_spy_30d', 0) or 0,
            getattr(features, 'day_of_week', 0) or 0,
            getattr(features, 'hour', 10) or 10,
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

    def retrain(self, trades: list) -> bool:
        """
        Retrain model with new trade data.
        Requires scikit-learn.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            
            X = []
            y = []
            
            for trade in trades:
                if not hasattr(trade, 'feature_snapshot_id'):
                    continue
                # Load feature snapshot
                # This requires DB access — simplified here
                feat = getattr(trade, 'features', None)
                if feat is None:
                    continue
                
                X.append(self._extract_features(feat))
                y.append(1 if (trade.pnl_pct or 0) > 0 else 0)
            
            if len(X) < 10:
                logger.warning(f"Not enough data to retrain: {len(X)} samples")
                return False
            
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            model = LogisticRegression(max_iter=1000)
            model.fit(X_scaled, y)
            
            # Save
            Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": model, "scaler": scaler}, f)
            
            self._model = model
            self._scaler = scaler
            
            logger.info(f"Model retrained with {len(X)} samples")
            return True
            
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
