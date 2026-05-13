# app/analysis/indicators.py
"""
IndicatorEngine — single source of truth for all technical indicators.
Pure functions over pandas DataFrames. Plugin registry for easy extension.
Migrates classify_signal and classify_multitimeframe from preprocessor.py.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureSet:
    symbol: str
    timestamp: datetime
    # RSI
    rsi_14: Optional[float] = None
    # MACD
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_crossover: Optional[bool] = None
    # ATR
    atr_pct: Optional[float] = None
    # SMAs
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    # Bollinger
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_position: Optional[float] = None
    # VWAP
    vwap: Optional[float] = None
    # Volume
    volume_ratio_20d: Optional[float] = None
    # IB series
    hist_volatility_30d: Optional[float] = None
    impl_volatility: Optional[float] = None
    # Relative strength
    rs_vs_spy_30d: Optional[float] = None
    rs_vs_qqq_30d: Optional[float] = None
    # Price change today (gap + intraday)
    price_change_pct: Optional[float] = None
    # Hourly timeframe features
    rsi_1h: Optional[float] = None
    volume_ratio_1h: Optional[float] = None
    # Weekly trend
    weekly_trend: Optional[str] = None  # "BULLISH" | "BEARISH" | "NEUTRAL"
    # Learned relevance per indicator (multipliers 0.5-1.5)
    feature_relevance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        import dataclasses
        d = dataclasses.asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


def _compute_rsi(df: pd.DataFrame) -> Optional[float]:
    if len(df) < 15:
        return None
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None


def _compute_macd(df: pd.DataFrame) -> dict:
    if len(df) < 26:
        return {"line": None, "signal": None, "crossover": None}
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    crossover = bool(
        (macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]) or
        (macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1])
    )
    return {
        "line": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal_line.iloc[-1]), 4),
        "crossover": crossover,
    }


def _compute_atr(df: pd.DataFrame) -> Optional[float]:
    if len(df) < 15 or "high" not in df.columns or "low" not in df.columns:
        return None
    high_low = df["high"] - df["low"]
    high_cp = (df["high"] - df["close"].shift()).abs()
    low_cp = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    price = df["close"].iloc[-1]
    if price > 0 and not pd.isna(atr):
        return round(float(atr / price * 100), 2)
    return None


def _compute_sma(df: pd.DataFrame, period: int) -> Optional[float]:
    if len(df) < period:
        return None
    val = df["close"].rolling(period).mean().iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None


def _compute_bollinger(df: pd.DataFrame) -> dict:
    if len(df) < 20:
        return {"upper": None, "lower": None, "position": None}
    sma = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = (sma + 2 * std).iloc[-1]
    lower = (sma - 2 * std).iloc[-1]
    close = df["close"].iloc[-1]
    if pd.isna(upper) or pd.isna(lower) or (upper - lower) == 0:
        return {"upper": None, "lower": None, "position": None}
    position = (close - lower) / (upper - lower)
    return {
        "upper": round(float(upper), 2),
        "lower": round(float(lower), 2),
        "position": round(float(max(0, min(1, position))), 4),
    }


def _compute_vwap(df: pd.DataFrame) -> Optional[float]:
    if len(df) < 2 or "volume" not in df.columns:
        return None
    if "high" not in df.columns or "low" not in df.columns:
        typical = df["close"]
    else:
        typical = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"]
    if vol.sum() == 0:
        return None
    vwap = (typical * vol).sum() / vol.sum()
    return round(float(vwap), 2) if not pd.isna(vwap) else None


def _compute_volume_ratio(df: pd.DataFrame) -> Optional[float]:
    if len(df) < 21 or "volume" not in df.columns:
        return None
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    current_vol = df["volume"].iloc[-1]
    if avg_vol > 0:
        return round(float(current_vol / avg_vol), 2)
    return None


def _compute_rs(symbol_df: pd.DataFrame, benchmark_df: pd.DataFrame, days: int = 30) -> Optional[float]:
    if symbol_df is None or benchmark_df is None:
        return None
    if len(symbol_df) < days or len(benchmark_df) < days:
        return None
    sym_return = (symbol_df["close"].iloc[-1] - symbol_df["close"].iloc[-days]) / symbol_df["close"].iloc[-days]
    bench_return = (benchmark_df["close"].iloc[-1] - benchmark_df["close"].iloc[-days]) / benchmark_df["close"].iloc[-days]
    return round(float(sym_return - bench_return), 4)


# Plugin registry
INDICATORS: dict[str, Callable] = {
    "rsi_14": _compute_rsi,
    "macd": _compute_macd,
    "atr_pct": _compute_atr,
    "sma20": lambda df: _compute_sma(df, 20),
    "sma50": lambda df: _compute_sma(df, 50),
    "sma200": lambda df: _compute_sma(df, 200),
    "bollinger": _compute_bollinger,
    "vwap": _compute_vwap,
    "volume_ratio_20d": _compute_volume_ratio,
}


def compute_features(
    symbol: str,
    df_daily: pd.DataFrame,
    df_hourly: Optional[pd.DataFrame] = None,
    df_5min: Optional[pd.DataFrame] = None,
    hv_series: Optional[pd.DataFrame] = None,
    iv_series: Optional[pd.DataFrame] = None,
    spy_df: Optional[pd.DataFrame] = None,
    qqq_df: Optional[pd.DataFrame] = None,
) -> FeatureSet:
    """Compute all available indicators. Returns FeatureSet with None for unavailable data."""
    fs = FeatureSet(symbol=symbol, timestamp=datetime.utcnow())

    if df_daily is None or len(df_daily) < 15:
        return fs  # all None

    fs.rsi_14 = _compute_rsi(df_daily)

    macd = _compute_macd(df_daily)
    fs.macd_line = macd["line"]
    fs.macd_signal = macd["signal"]
    fs.macd_crossover = macd["crossover"]

    fs.atr_pct = _compute_atr(df_daily)
    fs.sma20 = _compute_sma(df_daily, 20)
    fs.sma50 = _compute_sma(df_daily, 50)
    fs.sma200 = _compute_sma(df_daily, 200)

    boll = _compute_bollinger(df_daily)
    fs.bollinger_upper = boll["upper"]
    fs.bollinger_lower = boll["lower"]
    fs.bollinger_position = boll["position"]

    fs.vwap = _compute_vwap(df_daily)
    fs.volume_ratio_20d = _compute_volume_ratio(df_daily)

    # Price change today (gap + intraday)
    if len(df_daily) >= 2:
        today = df_daily.iloc[-1]
        yesterday_close = df_daily["close"].iloc[-2]
        if yesterday_close > 0:
            fs.price_change_pct = round(float((today["close"] - yesterday_close) / yesterday_close * 100), 2)

    # Hourly features (when available)
    if df_hourly is not None and len(df_hourly) >= 15:
        fs.rsi_1h = _compute_rsi(df_hourly)
        fs.volume_ratio_1h = _compute_volume_ratio(df_hourly)

    if hv_series is not None and len(hv_series) > 0:
        fs.hist_volatility_30d = round(float(hv_series["close"].iloc[-1]), 4)

    if iv_series is not None and len(iv_series) > 0:
        fs.impl_volatility = round(float(iv_series["close"].iloc[-1]), 4)

    if spy_df is not None:
        fs.rs_vs_spy_30d = _compute_rs(df_daily, spy_df)

    if qqq_df is not None:
        fs.rs_vs_qqq_30d = _compute_rs(df_daily, qqq_df)

    # Load feature relevance from DB
    try:
        from app.db.database import get_or_create_symbol_parameters
        params = get_or_create_symbol_parameters(symbol)
        if params:
            fs.feature_relevance = {
                "momentum": getattr(params, "momentum_mult", 1.0),
                "trend": getattr(params, "trend_mult", 1.0),
                "volume": getattr(params, "volume_mult", 1.0),
                "volatility": getattr(params, "volatility_mult", 1.0),
            }
    except Exception:
        pass

    return fs


def compute_from_df(df: pd.DataFrame) -> dict:
    """Backward-compatible function for backtest engine. Returns dict like old _calc_indicators."""
    if len(df) < 15:
        return {}
    # Compute RSI directly to preserve NaN behavior matching original _calc_indicators
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = float((100 - 100 / (1 + rs)).iloc[-1])

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    macd_crossover = bool(
        (macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]) or
        (macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1])
    )

    avg_vol = df["volume"].rolling(20).mean().iloc[-1] if "volume" in df.columns else float("nan")
    volume_ratio = float(df["volume"].iloc[-1] / avg_vol) if (
        "volume" in df.columns and avg_vol > 0
    ) else 1.0

    return {
        "rsi": round(rsi, 2),
        "macd": round(float(macd_line.iloc[-1]), 4),
        "macd_crossover": macd_crossover,
        "volume_ratio": round(volume_ratio, 2),
    }


def compute_single_indicator(indicator_name: str, df: pd.DataFrame):
    """Compute a single indicator by name using cached bars."""
    fn = INDICATORS.get(indicator_name)
    if fn is None:
        logger.warning(f"Unknown indicator: {indicator_name}")
        return None
    try:
        return fn(df)
    except Exception as e:
        logger.error(f"compute_single_indicator({indicator_name}): {e}")
        return None


# --- Migrated from preprocessor.py (reexported for backwards compatibility) ---

def classify_signal(rsi: float, macd_crossover: bool, volume_ratio: float) -> str:
    """Classify signal from a single timeframe.
    Criterio relajado para capturar mas oportunidades en dias movidos.
    """
    conditions = []
    # RSI extremo o al menos direccional
    if rsi is not None:
        if rsi < 35 or rsi > 65:
            conditions.append("rsi_extreme")
        elif rsi < 40 or rsi > 60:
            conditions.append("rsi_directional")
    # MACD crossover
    if bool(macd_crossover):
        conditions.append("macd")
    # Volumen elevado o al menos activo
    if volume_ratio is not None:
        if volume_ratio > 1.5:
            conditions.append("volume_high")
        elif volume_ratio > 1.0:
            conditions.append("volume_active")

    count = len(conditions)
    if count >= 3:
        return "STRONG"
    if count >= 2:
        return "MEDIUM"
    if count >= 1:
        return "WEAK"
    return "NONE"


def classify_multitimeframe(daily: str, hourly: str, minute: str) -> str:
    """
    Classify combined signal from 3 timeframes.
    STRONG: daily STRONG + al menos uno sub >= MEDIUM.
    MEDIUM: daily MEDIUM + al menos uno sub >= WEAK, o dos sub >= MEDIUM.
    WEAK: daily WEAK + al menos uno sub >= WEAK.
    """
    strength_val = {"STRONG": 2, "MEDIUM": 1, "WEAK": 0, "NONE": -1}
    d = strength_val.get(daily, 0)
    h = strength_val.get(hourly, 0)
    m = strength_val.get(minute, 0)
    subs = [h, m]
    sub_max = max(subs)
    sub_count_medium = sum(1 for s in subs if s >= 1)

    if d >= 2 and sub_max >= 1:
        return "STRONG"
    if (d >= 1 and sub_max >= 0) or sub_count_medium >= 2:
        return "MEDIUM"
    if d >= 0 or sub_max >= 0:
        return "WEAK"
    return "NONE"



def classify_signal_v2(features: FeatureSet) -> str:
    """
    Criterio de entrada relajado para capturar movimientos del dia.
    STRONG: 3-4 condiciones. MEDIUM: 2. WEAK: 1.
    """
    conditions = 0

    # Condicion 1: RSI direccional o extremo
    rsi = features.rsi_14
    if rsi is not None:
        if rsi < 30 or rsi > 70:
            conditions += 1
        elif rsi < 40 or rsi > 60:
            conditions += 0.5

    # Condicion 2: MACD crossover
    if features.macd_crossover is True:
        conditions += 1

    # Condicion 3: Volumen activo o elevado
    vol = features.volume_ratio_20d
    if vol is not None:
        if vol > 1.5:
            conditions += 1
        elif vol > 1.0:
            conditions += 0.5

    # Condicion 4: Movimiento de precio significativo
    pc = features.price_change_pct
    if pc is not None and abs(pc) > 1.0:
        conditions += 1

    # Condicion 5: Zona Bollinger extrema
    boll = features.bollinger_position
    if boll is not None and (boll < 0.15 or boll > 0.85):
        conditions += 0.5

    if conditions >= 3:
        return 'STRONG'
    elif conditions >= 2:
        return 'MEDIUM'
    elif conditions >= 1:
        return 'WEAK'
    return 'NONE'
