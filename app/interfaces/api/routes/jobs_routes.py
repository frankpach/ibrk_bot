# app/interfaces/api/routes/jobs_routes.py
"""Background jobs API — POST /jobs/* and GET /jobs/{id}."""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.application.services.job_runner import get_global_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

class LlmAnalysisRequest(BaseModel):
    symbol: str


class BacktestRequest(BaseModel):
    symbol: str
    days: int = 180


class JobResponse(BaseModel):
    job_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_runner():
    return get_global_runner()


def _run_llm_analysis(symbol: str) -> dict:
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
    from app.llm.agent import get_data_layer
    from app.container import get_container
    data_layer = get_data_layer()
    context = AnalysisContext(mode="on_demand")
    _c = get_container()
    pipeline = AnalysisPipeline(symbol.upper(), data_layer, context, notify_fn=None,
                                broker=_c.broker, event_bus=_c.event_bus)
    result = pipeline.run()
    return result.to_dict()


def _run_backtest(symbol: str, days: int) -> dict:
    from app.backtest.engine import run_backtest
    from app.backtest.reporter import format_api
    from app.ibkr.client import get_client
    from app.api.capital import get_operating_capital
    client = get_client()
    try:
        account = client.get_account()
        capital = get_operating_capital(account.get("net_liquidation", 0.0))
    except Exception:
        from app.config.settings import CAPITAL_CAP
        capital = CAPITAL_CAP
    result = run_backtest(symbol=symbol.upper(), ib_client=client, period_days=days, capital=capital)
    return format_api(result)


def _run_opportunity_scan() -> dict:
    from app.analysis.admission import run_daily_discovery
    from app.analysis.mock_client import MockIBClient
    from app.analysis.data import IBDataLayer
    data_layer = IBDataLayer(MockIBClient())
    run_daily_discovery(data_layer)
    return {"status": "scan_completed"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/llm-analysis")
def post_llm_analysis(req: LlmAnalysisRequest):
    """Queue an LLM analysis job. Returns immediately with job_id."""
    runner = _get_runner()
    job_id = runner.submit(
        job_type="llm-analysis",
        fn=_run_llm_analysis,
        timeout_seconds=60,
        symbol=req.symbol.upper(),
    )
    return {"job_id": job_id}


@router.post("/backtest")
def post_backtest(req: BacktestRequest):
    """Queue a backtest job. Returns immediately with job_id."""
    runner = _get_runner()
    job_id = runner.submit(
        job_type="backtest",
        fn=_run_backtest,
        timeout_seconds=60,
        symbol=req.symbol.upper(),
        days=req.days,
    )
    return {"job_id": job_id}


@router.post("/opportunity-scan")
def post_opportunity_scan():
    """Queue an opportunity scan job. Returns immediately with job_id."""
    runner = _get_runner()
    job_id = runner.submit(
        job_type="opportunity-scan",
        fn=_run_opportunity_scan,
        timeout_seconds=300,
    )
    return {"job_id": job_id}


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get job status, result, and error."""
    runner = _get_runner()
    job = runner.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("")
def list_jobs(
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List jobs with optional filtering."""
    runner = _get_runner()
    return {"jobs": runner.list_jobs(job_type=type, status=status, limit=limit, offset=offset)}
