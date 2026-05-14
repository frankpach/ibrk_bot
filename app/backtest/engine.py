# app/backtest/engine.py
"""
Motor de backtesting para el IBKR AI Trader.
Descarga datos historicos de IB, aplica señales multi-timeframe,
simula trades con las reglas de riesgo actuales y genera metricas.
"""
import logging
from dataclasses import dataclass, field

import pandas as pd

from app.analysis.indicators import classify_signal, compute_from_df as _calc_indicators

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    symbol: str
    period_days: int
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_usd: float
    total_pnl_pct: float
    profit_factor: float
    max_drawdown_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    trades: list = field(default_factory=list)


def apply_signals_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el clasificador de senales al DataFrame y agrega columna 'signal'.
    Usa solo el timeframe daily disponible en el backtest.
    """
    df = df.copy()
    signals = []

    for i in range(len(df)):
        if i < 14:
            signals.append("WEAK")
            continue
        slice_df = df.iloc[:i + 1]
        ind = _calc_indicators(slice_df)
        if not ind:
            signals.append("WEAK")
            continue
        sig = classify_signal(ind["rsi"], ind["macd_crossover"], ind["volume_ratio"])
        signals.append(sig)

    df["signal"] = signals
    return df


def simulate_trades(
    df: pd.DataFrame,
    stop_loss_pct: float,
    take_profit_pct: float,
    capital: float,
    max_positions: int = 1,
    commission_per_trade: float = 1.0,
    slippage_pct: float = 0.001,
) -> list:
    """
    Simula trades sobre el DataFrame con señales.
    Entra en BUY cuando signal == STRONG o MEDIUM.
    Sale al tocar stop-loss, take-profit, o fin de datos.

    commission_per_trade: IBKR cobra mínimo $1 por lado ($2 roundtrip).
    slippage_pct: 0.1% de slippage por lado es conservador para acciones líquidas.
    """
    from app.config.settings import MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD

    trades = []
    in_trade = False
    entry_price = 0.0
    entry_units = 0.0
    entry_idx = 0
    stop_price = 0.0
    take_price = 0.0

    for i, row in df.iterrows():
        price = float(row["close"])
        signal = row.get("signal", "WEAK")

        if not in_trade and signal in ("STRONG", "MEDIUM"):
            max_risk = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
            max_pos_usd = min(max_risk / stop_loss_pct, MAX_POSITION_USD)
            # Support fractional shares (realistic for small capital)
            units = max_pos_usd / price
            if units * price < 1.0:
                continue
            # Apply entry slippage (pay slightly more to enter)
            effective_entry = price * (1 + slippage_pct)
            in_trade = True
            entry_price = effective_entry
            entry_units = units
            entry_idx = i
            stop_price = round(price * (1 - stop_loss_pct), 4)
            take_price = round(price * (1 + take_profit_pct), 4)
            continue

        if in_trade:
            exit_reason = None
            exit_price = price

            if price <= stop_price:
                exit_reason = "STOP_LOSS"
                # Slippage is worse on stop-loss (gap through stop)
                exit_price = price * (1 - slippage_pct * 1.5)
            elif price >= take_price:
                exit_reason = "TAKE_PROFIT"
                exit_price = price * (1 - slippage_pct)
            elif i == df.index[-1]:
                exit_reason = "END_OF_DATA"
                exit_price = price * (1 - slippage_pct)

            if exit_reason:
                gross_pnl_usd = (exit_price - entry_price) * entry_units
                # Deduct roundtrip commission (entry + exit)
                total_commission = 2 * max(commission_per_trade,
                                           0.005 * entry_units)  # $0.005/share IBKR min
                net_pnl_usd = gross_pnl_usd - total_commission
                position_value = entry_price * entry_units
                net_pnl_pct = net_pnl_usd / position_value if position_value > 0 else 0.0
                trades.append({
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "pnl_pct": round(net_pnl_pct, 4),
                    "pnl_usd": round(net_pnl_usd, 2),
                    "gross_pnl_usd": round(gross_pnl_usd, 2),
                    "commission_usd": round(total_commission, 2),
                    "exit_reason": exit_reason,
                    "units": round(entry_units, 4),
                })
                in_trade = False

    return trades


def calculate_metrics(trades: list, capital: float) -> BacktestResult:
    """Calcula metricas de performance sobre la lista de trades simulados."""
    if not trades:
        return BacktestResult(
            symbol="", period_days=0, total_trades=0, wins=0, losses=0,
            win_rate=0.0, total_pnl_usd=0.0, total_pnl_pct=0.0,
            profit_factor=0.0, max_drawdown_pct=0.0,
            avg_win_pct=0.0, avg_loss_pct=0.0, trades=[],
        )

    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    total_pnl = sum(t["pnl_usd"] for t in trades)
    gross_wins = sum(t["pnl_usd"] for t in wins)
    gross_losses = abs(sum(t["pnl_usd"] for t in losses))

    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf")
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) * 100 if wins else 0.0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) * 100 if losses else 0.0

    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        running += t["pnl_usd"]
        if running > peak:
            peak = running
        dd = (peak - running) / capital * 100 if capital > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_commissions = sum(t.get("commission_usd", 0) for t in trades)
    result = BacktestResult(
        symbol="", period_days=len(trades),
        total_trades=len(trades),
        wins=len(wins), losses=len(losses),
        win_rate=round(win_rate, 2),
        total_pnl_usd=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl / capital * 100, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown_pct=round(max_dd, 2),
        avg_win_pct=round(avg_win, 2),
        avg_loss_pct=round(avg_loss, 2),
        trades=trades,
    )
    # Attach commission summary as extra attribute (backwards compatible)
    result.__dict__["total_commissions_usd"] = round(total_commissions, 2)
    return result


def run_backtest(
    symbol: str,
    ib_client,
    period_days: int = 180,
    stop_loss_pct: float = 0.025,
    take_profit_pct: float = 0.06,
    capital: float = 500.0,
) -> BacktestResult:
    """
    Descarga datos historicos de IB y corre el backtest completo.
    period_days: cuantos dias hacia atras analizar
    """
    try:
        from app.analysis.data import IBDataLayer

        data_layer = IBDataLayer(ib_client)
        df = data_layer.get_ohlcv(symbol, f"{period_days} D", "1 day", "backtest")

        if df is None or len(df) < 30:
            logger.warning(f"Not enough data for {symbol}: {len(df) if df is not None else 0} bars")
            result = calculate_metrics([], capital)
            result.symbol = symbol
            result.period_days = period_days
            return result

        bars_df = pd.DataFrame(df[["close", "volume"]].copy())
        bars_df = apply_signals_to_df(bars_df)
        trades = simulate_trades(bars_df, stop_loss_pct, take_profit_pct, capital)
        result = calculate_metrics(trades, capital)
        result.symbol = symbol
        result.period_days = period_days
        return result

    except Exception as e:
        logger.error(f"Backtest failed for {symbol}: {e}")
        result = calculate_metrics([], capital)
        result.symbol = symbol
        result.period_days = period_days
        return result
