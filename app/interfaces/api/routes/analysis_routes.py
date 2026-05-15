# app/interfaces/api/routes/analysis_routes.py
from fastapi import APIRouter, HTTPException
from app.container import get_container

router = APIRouter()


@router.get("/backtest/{symbol}")
def backtest(symbol: str, days: int = 180):
    from app.backtest.engine import run_backtest
    from app.ibkr.client import get_client
    try:
        result = run_backtest(symbol.upper(), days, get_client())
        return {
            "symbol": result.symbol, "period_days": result.period_days,
            "total_trades": result.total_trades, "wins": result.wins,
            "losses": result.losses, "win_rate_pct": result.win_rate,
            "total_pnl_usd": result.total_pnl_usd, "total_pnl_pct": result.total_pnl_pct,
            "profit_factor": result.profit_factor, "max_drawdown_pct": result.max_drawdown_pct,
            "avg_win_pct": result.avg_win_pct, "avg_loss_pct": result.avg_loss_pct,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/candidate-analysis/{symbol}")
def candidate_analysis(symbol: str):
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
    from app.llm.agent import get_data_layer
    try:
        dl = get_data_layer()
        _c = get_container()
        pipeline = AnalysisPipeline(symbol.upper(), dl, AnalysisContext(mode="on_demand"),
                                    broker=_c.broker, event_bus=_c.event_bus)
        result = pipeline.run()
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/analysis/indicator/{symbol}/{indicator_name}")
def analysis_indicator(symbol: str, indicator_name: str):
    from app.analysis.indicators import compute_single_indicator
    from app.ibkr.client import get_client
    try:
        value = compute_single_indicator(symbol.upper(), indicator_name, get_client())
        return {"symbol": symbol.upper(), "indicator": indicator_name, "value": value}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/universe/watchlist")
def universe_watchlist():
    from app.infrastructure.db.compat import get_approved_symbols_with_meta
    return get_approved_symbols_with_meta()


@router.get("/candidate-decisions")
def candidate_decisions():
    from app.infrastructure.db.compat import get_candidate_decisions_for_evaluation
    decisions = get_candidate_decisions_for_evaluation(days_ago=7)
    return [{"id": d.id, "symbol": d.symbol, "decision": d.decision,
             "price_at_decision": d.price_at_decision, "quant_score": d.quant_score} for d in decisions]


@router.get("/symbol-parameters/{symbol}")
def symbol_parameters(symbol: str):
    from app.infrastructure.db.compat import get_or_create_symbol_parameters
    params = get_or_create_symbol_parameters(symbol.upper())
    return {
        "symbol": params.symbol, "stop_loss_pct": params.stop_loss_pct,
        "take_profit_pct": params.take_profit_pct, "trade_count": params.trade_count,
    }


@router.get("/market-permissions")
def market_permissions():
    from app.ibkr.market_permissions import get_permissions_report
    return get_permissions_report()


@router.post("/analyze/{symbol}")
def analyze(symbol: str):
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
    from app.llm.agent import get_data_layer
    try:
        dl = get_data_layer()
        _c = get_container()
        pipeline = AnalysisPipeline(symbol.upper(), dl, AnalysisContext(mode="on_demand"),
                                    broker=_c.broker, event_bus=_c.event_bus)
        result = pipeline.run()
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/refresh")
def refresh():
    return {"status": "ok"}
