# app/analysis/pipeline.py
"""
AnalysisPipeline — orchestrates the full analysis: data -> indicators -> score -> hard_rules -> LLM.
Includes watchdog (10 min total) and per-step timeouts with Telegram progress streaming.
"""
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

STEP_TIMEOUTS = {
    "fetch_data": 30, "compute_indicators": 10,
    "score": 2, "hard_rules": 5, "llm_interpret": 60,
}
TOTAL_TIMEOUT = 600


@dataclass
class AnalysisContext:
    mode: str  # "on_demand" | "auto_signal" | "daily_discovery" | "backtest"


@dataclass
class ParameterSuggestion:
    dimension: str
    current_value: float
    suggested_value: float
    confidence: float
    reason: str


@dataclass
class AnalysisResult:
    symbol: str
    in_universe: bool = False
    features = None
    score = None
    hard_rules = None
    llm_narrative: str = ""
    llm_confidence: float = 0.0
    recommendation: str = "UNKNOWN"
    parameter_suggestions: list = field(default_factory=list)
    feature_snapshot_id: Optional[int] = None
    elapsed_seconds: float = 0.0
    failed_at_step: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "in_universe": self.in_universe,
            "recommendation": self.recommendation,
            "llm_narrative": self.llm_narrative,
            "llm_confidence": self.llm_confidence,
            "quant_score": self.score.total if self.score else None,
            "quant_recommendation": self.score.recommendation if self.score else None,
            "hard_rules_passed": self.hard_rules.passed if self.hard_rules else None,
            "hard_rules_failures": self.hard_rules.failures if self.hard_rules else [],
            "hard_rules_warnings": self.hard_rules.warnings if self.hard_rules else [],
            "feature_snapshot_id": self.feature_snapshot_id,
            "elapsed_seconds": self.elapsed_seconds,
            "failed_at_step": self.failed_at_step,
        }


class AnalysisPipeline:
    def __init__(
        self,
        symbol: str,
        data_layer,
        context: AnalysisContext,
        notify_fn: Optional[Callable] = None,
    ):
        self.symbol = symbol.upper()
        self._data_layer = data_layer
        self._context = context
        self._notify_fn = notify_fn
        self.current_step = "init"
        self._result = AnalysisResult(symbol=self.symbol)
        self._start_time = 0.0
        self._aborted = threading.Event()

    def _notify(self, msg: str):
        if self._notify_fn:
            try:
                self._notify_fn(msg)
            except Exception:
                pass

    def _check_abort(self):
        if self._aborted.is_set():
            raise TimeoutError(f"Pipeline aborted at step: {self.current_step}")

    def run(self) -> AnalysisResult:
        import time
        self._start_time = time.time()

        # Global watchdog
        def _timeout_handler():
            if not self._aborted.is_set():
                self._aborted.set()
                self._result.failed_at_step = self.current_step
                self._notify(
                    f"⏱ Analysis <b>{self.symbol}</b> timed out at step '{self.current_step}' (10 min limit).\n"
                    f"Check IB Gateway and OpenCode connectivity."
                )
        watchdog = threading.Timer(TOTAL_TIMEOUT, _timeout_handler)
        watchdog.daemon = True
        watchdog.start()

        try:
            self._fetch_data()
            self._check_abort()

            # Validate data quality before continuing
            if self._df_daily is None or len(self._df_daily) < 15:
                self._result.recommendation = "ERROR"
                self._result.failed_at_step = "fetch_data"
                self._notify(
                    f"❌ <b>{self.symbol}</b>: No se pudieron obtener datos históricos.\n"
                    f"Verifica que IB Gateway esté conectado y que el símbolo sea operable.\n"
                    f"Reintenta con /analizar {self.symbol}"
                )
                self._persist()
                return self._result

            self._compute_indicators()
            self._check_abort()
            self._score()
            self._check_abort()
            self._check_hard_rules()
            self._check_abort()
            if self._result.hard_rules and self._result.hard_rules.passed:
                # Skip LLM for daily_discovery with low scores to save tokens
                if not (self._context.mode == "daily_discovery" and
                        self._result.score and self._result.score.total < 60):
                    # ML signal filter gate (< 100ms)
                    from app.ml.signal_filter import get_signal_filter
                    ml_filter = get_signal_filter()
                    if ml_filter.should_ignore(self._result.features):
                        self._result.recommendation = "REJECTED"
                        self._result.llm_narrative = "ML filter: weak signal, skipping LLM"
                        self._notify(
                            f"🤖 <b>{self.symbol}</b> rechazado por filtro ML (señal débil). "
                            f"Saltando análisis LLM."
                        )
                    else:
                        self._llm_interpret()
                        self._check_abort()
            elif self._result.hard_rules:
                self._result.recommendation = "REJECTED"
                self._notify(
                    f"❌ <b>{self.symbol}</b> failed hard rules:\n" +
                    "\n".join(f"• {f}" for f in self._result.hard_rules.failures)
                )
            self._persist()
        except TimeoutError:
            self._result.recommendation = "ERROR"
        except Exception as e:
            logger.error(f"AnalysisPipeline {self.symbol} error at {self.current_step}: {e}")
            self._result.failed_at_step = self.current_step
            self._result.recommendation = "ERROR"
        finally:
            watchdog.cancel()
            import time
            self._result.elapsed_seconds = round(time.time() - self._start_time, 1)

        return self._result

    def _fetch_data(self):
        self.current_step = "fetch_data"
        ctx = self._context.mode
        self._notify(f"📥 Fetching data for <b>{self.symbol}</b>...")

        self._df_daily = self._data_layer.get_ohlcv(self.symbol, "180 D", "1 day", ctx)
        self._df_hourly = self._data_layer.get_ohlcv(self.symbol, "5 D", "1 hour", ctx)
        self._hv = self._data_layer.get_historical_volatility(self.symbol, ctx)
        self._news = self._data_layer.get_news(self.symbol)
        self._earnings_date = self._data_layer.get_earnings_date(self.symbol)

        # SPY and QQQ for relative strength
        self._spy_df = self._data_layer.get_ohlcv("SPY", "180 D", "1 day", ctx)
        self._qqq_df = self._data_layer.get_ohlcv("QQQ", "180 D", "1 day", ctx)



    def _compute_indicators(self):
        self.current_step = "compute_indicators"
        self._notify(f"📊 Computing indicators for <b>{self.symbol}</b>...")
        from app.analysis.indicators import compute_features
        self._result.features = compute_features(
            self.symbol, self._df_daily, self._df_hourly,
            hv_series=self._hv, spy_df=self._spy_df, qqq_df=self._qqq_df,
        )

    def _score(self):
        self.current_step = "score"
        from app.analysis.scorer import compute_score
        portfolio = []
        try:
            import httpx
            from app.config.settings import API_BASE
            r = httpx.get(f"{API_BASE}/portfolio", timeout=5)
            portfolio = r.json() if r.status_code == 200 else []
        except Exception:
            pass
        self._result.score = compute_score(
            self._result.features, self.symbol, portfolio, self._news
        )
        self._result.in_universe = self.symbol in __import__(
            "app.config.settings", fromlist=["ALLOWED_SYMBOLS"]
        ).ALLOWED_SYMBOLS

    def _check_hard_rules(self):
        self.current_step = "hard_rules"
        from app.analysis.hard_rules import check_all
        portfolio = []
        self._result.hard_rules = check_all(
            self.symbol, self._result.features, portfolio,
            self._earnings_date, capital=500.0,
        )

    def _llm_interpret(self):
        self.current_step = "llm_interpret"
        score = self._result.score
        self._notify(
            f"🤖 Consulting LLM for <b>{self.symbol}</b> (score: {score.total:.0f}/100)..."
        )
        try:
            from app.config.settings import OPENCODE_BIN, OPENCODE_MODEL
            from app.llm.agent import get_symbol_category, get_strategy_context
            from app.db.database import get_patterns_for_symbol

            category = get_symbol_category(self.symbol)
            strategy = get_strategy_context(category)
            patterns = get_patterns_for_symbol(self.symbol)
            patterns_text = "\n".join(
                f"- {p.pattern_text} (W:{p.win_count} L:{p.loss_count})"
                for p in patterns[:3]
            ) or "No patterns yet."

            news_text = "\n".join(
                f"[{n.get('sentiment','?').upper()}] {n.get('title','')}"
                for n in self._news[:3]
            ) or "No recent news."

            features_dict = self._result.features.to_dict() if self._result.features else {}
            hard_dict = {
                "passed": self._result.hard_rules.passed,
                "warnings": self._result.hard_rules.warnings,
                "earnings_in_days": self._result.hard_rules.earnings_in_days,
            }

            prompt = (
                f"You are a swing trading analyst. Analyze this symbol and provide interpretation.\n\n"
                f"SYMBOL: {self.symbol}\n"
                f"CATEGORY: {category}\n"
                f"STRATEGY: {strategy}\n\n"
                f"QUANT_SCORE: {score.total:.1f}/100 [{score.recommendation}]\n"
                f"Dimensions: momentum={score.momentum:.2f} trend={score.trend:.2f} "
                f"volume={score.volume:.2f} volatility={score.volatility:.2f} "
                f"price_change={score.price_change:.2f}\n\n"
                f"KEY_FEATURES:\n"
                f"  RSI: {features_dict.get('rsi_14', 'N/A')}\n"
                f"  MACD crossover: {features_dict.get('macd_crossover', 'N/A')}\n"
                f"  Volume ratio: {features_dict.get('volume_ratio_20d', 'N/A')}\n"
                f"  ATR%: {features_dict.get('atr_pct', 'N/A')}\n"
                f"  Price change today: {features_dict.get('price_change_pct', 'N/A')}%\n"
                f"  RS vs SPY 30d: {features_dict.get('rs_vs_spy_30d', 'N/A')}\n\n"
                f"HARD_RULES: {hard_dict}\n\n"
                f"NEWS:\n{news_text}\n\n"
                f"HISTORICAL_PATTERNS:\n{patterns_text}\n\n"
                f"Respond ONLY with this JSON:\n"
                '{{"narrative": "2-3 sentence analysis", "confidence": 0.75, '
                '"key_risks": ["risk1"], "recommendation": "BUY|SELL|IGNORE|WATCHLIST|PROPOSE"}}'
            )

            import subprocess
            result = subprocess.run(
                [OPENCODE_BIN, "run", "--model", OPENCODE_MODEL, "--format", "json", prompt],
                capture_output=True, text=True, timeout=60,
                cwd="/home/frankpach/ibkr-bot",
            )
            text_parts = []
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "text":
                        text_parts.append(event["part"]["text"])
                except json.JSONDecodeError:
                    continue
            response = "".join(text_parts).strip()

            if response:
                try:
                    content = response.strip()
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    data = json.loads(content)
                    self._result.llm_narrative = data.get("narrative", "")
                    self._result.llm_confidence = float(data.get("confidence", 0.5))
                    llm_rec = data.get("recommendation", score.recommendation)
                    self._result.recommendation = llm_rec
                except (json.JSONDecodeError, ValueError):
                    self._result.llm_narrative = response[:500]
                    self._result.recommendation = score.recommendation
            else:
                self._result.recommendation = score.recommendation

        except Exception as e:
            logger.error(f"LLM interpret failed for {self.symbol}: {e}")
            self._result.recommendation = self._result.score.recommendation if self._result.score else "ERROR"

    def _persist(self):
        self.current_step = "persist"
        try:
            from app.db.database import insert_feature_snapshot, insert_candidate_decision
            if self._result.features:
                fs_dict = self._result.features.to_dict()
                fs_dict["context"] = self._context.mode
                self._result.feature_snapshot_id = insert_feature_snapshot(fs_dict)

            price = None
            if self._df_daily is not None and len(self._df_daily) > 0:
                price = float(self._df_daily["close"].iloc[-1])

            insert_candidate_decision(
                symbol=self.symbol,
                decision=self._result.recommendation,
                price=price or 0.0,
                score=self._result.score.total if self._result.score else 0.0,
                feature_snapshot_id=self._result.feature_snapshot_id,
                llm_summary=self._result.llm_narrative[:500] if self._result.llm_narrative else None,
            )
        except Exception as e:
            logger.error(f"Pipeline persist failed for {self.symbol}: {e}")
