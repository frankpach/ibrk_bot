# Interface Design: dev-plan — Feature-Centric Analysis Pipeline

**Module**: dev-plan
**Phase**: Phase 2 — Design
**Status**: ✓ Complete
**Date**: 2026-05-07
**Chosen Alternative**: B — Pipeline como clase AnalysisPipeline con contexto
**Previous artifact**: docs/dev/artifacts/dev-plan/05-why-decisions.md
**Next artifact**: docs/dev/artifacts/dev-plan/07-requirements.md

---

## Chosen Alternative: B

**Razón**: El objeto `AnalysisPipeline` con `pipeline.current_step` habilita el watchdog de 10 minutos que el usuario requiere — sabe exactamente en qué paso se trabó y puede notificarlo via Telegram. El `IBDataLayer` como singleton gestiona el TTL automáticamente según el `context` del pipeline, eliminando duplicación. Sin el overhead de implementar PipelineRunner abstracto (C), sin el problema de TTL manual disperso (A).

---

## Primary Interface

### IBDataLayer (app/analysis/data.py)

Singleton creado en `run.py`, inyectado donde se necesite. Gestiona cache en memoria con TTL diferenciado. Envuelve IBKRClient sin modificarlo. Soporta MockIBClient via `IB_MOCK=true`.

```python
class IBDataLayer:
    def __init__(self, ib_client):
        # ib_client: IBKRClient real o MockIBClient según IB_MOCK setting
        self._client = ib_client
        self._cache: dict[str, tuple[any, float]] = {}  # key → (data, expires_at)

    def get_ohlcv(self, symbol: str, duration: str, bar_size: str, context: str) -> pd.DataFrame | None:
        # context determina TTL: "trade_entry"=0, "on_demand"=120, "scanner"=900, "backtest"=3600
        ...

    def get_historical_volatility(self, symbol: str, context: str) -> pd.DataFrame | None:
        # whatToShow="HISTORICAL_VOLATILITY" via reqHistoricalData
        ...

    def get_implied_volatility(self, symbol: str, context: str) -> pd.DataFrame | None:
        # whatToShow="OPTION_IMPLIED_VOLATILITY"
        ...

    def get_news(self, symbol: str) -> list[dict]:
        # reqHistoricalNews de IB primero, Yahoo RSS como fallback
        ...

    def get_earnings_date(self, symbol: str) -> datetime | None:
        # reqFundamentalData("CalendarReport"), fallback Yahoo, fallback None
        # TTL 24h — los earnings no cambian durante el día
        ...

    def run_scanner(self, scan_code: str, max_results: int = 20) -> list[str]:
        # reqScannerData: HOT_BY_VOLUME, TOP_PERC_GAIN, MOST_ACTIVE
        # Retorna lista de símbolos (tickers)
        ...

    def get_spy_price_on(self, date: datetime) -> float | None:
        # Para cálculo de alpha vs SPY en ReturnEvaluator
        ...
```

---

### IndicatorEngine (app/analysis/indicators.py)

Funciones puras sobre DataFrames. Plugin registry para indicadores. Persiste FeatureSnapshot en DB. Soporta solicitud on-demand de indicador individual.

```python
# Plugin registry — fácil agregar nuevos sin tocar el core
INDICATORS: dict[str, Callable] = {
    "rsi_14": _compute_rsi,
    "macd": _compute_macd,
    "atr_pct": _compute_atr,
    "sma20": _compute_sma20,
    "sma50": _compute_sma50,
    "sma200": _compute_sma200,
    "bollinger": _compute_bollinger,
    "vwap": _compute_vwap,
    "volume_ratio_20d": _compute_volume_ratio,
    "rs_vs_spy": _compute_relative_strength_spy,
    "rs_vs_qqq": _compute_relative_strength_qqq,
}

@dataclass
class FeatureSet:
    symbol: str
    timestamp: datetime
    # Indicadores técnicos
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_crossover: bool
    atr_pct: float
    sma20: float; sma50: float; sma200: float
    bollinger_upper: float; bollinger_lower: float; bollinger_position: float  # 0-1
    vwap: float
    volume_ratio_20d: float
    # Datos IB adicionales
    hist_volatility_30d: float | None
    impl_volatility: float | None
    # Relative strength
    rs_vs_spy_30d: float | None
    rs_vs_qqq_30d: float | None
    # Feature relevance aprendida (multiplicadores 0.5-1.5)
    feature_relevance: dict[str, float]

def compute_features(
    symbol: str,
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None,
    df_5min: pd.DataFrame | None,
    hv_series: pd.DataFrame | None,
    iv_series: pd.DataFrame | None,
    spy_df: pd.DataFrame | None,
    qqq_df: pd.DataFrame | None,
) -> FeatureSet:
    # Calcula todos los indicadores disponibles según los datos provistos
    # Si df_hourly es None → indicadores hourly se omiten (no fallan)
    ...

def compute_single_indicator(
    indicator_name: str,
    df: pd.DataFrame,
) -> float | bool | None:
    # Permite solicitar un indicador on-demand usando datos ya disponibles
    # El LLM puede llamar esto via tool call MCP si necesita un indicador adicional
    ...
```

---

### QuantScorer (app/analysis/scorer.py)

Produce un score 0-100 ponderado. Pesos globales como hipótesis inicial. Multiplicadores por símbolo almacenados en DB. Ventana mínima de 5 trades antes de ajustar.

```python
GLOBAL_WEIGHTS = {
    "momentum": 0.25,   # RSI + MACD
    "trend": 0.20,      # SMA posición + RS vs SPY
    "volume": 0.15,     # volume_ratio + VWAP
    "volatility": 0.10, # ATR + HV vs IV
    "portfolio_fit": 0.15,  # correlación + capital disponible
    "sentiment": 0.15,  # news sentiment score
}

THRESHOLDS = {
    "rejected": 49,
    "watchlist": 69,
    "propose": 84,
    "priority": 100,
}

@dataclass
class QuantScore:
    symbol: str
    total: float           # 0-100
    momentum: float        # 0-1
    trend: float           # 0-1
    volume: float          # 0-1
    volatility: float      # 0-1
    portfolio_fit: float   # 0-1
    sentiment: float       # 0-1
    recommendation: str    # REJECTED | WATCHLIST | PROPOSE | PRIORITY
    weights_used: dict     # para auditoría

def compute_score(features: FeatureSet, symbol: str, portfolio: list) -> QuantScore:
    # Carga multiplicadores por símbolo desde DB (default 1.0 si no existen)
    # effective_weight = global_weight * symbol_multiplier
    # Clampea multiplicadores a [0.5, 1.5]
    ...

def update_weights_attenuated(
    symbol: str,
    dimension: str,           # "momentum", "trend", etc.
    suggested_multiplier: float,
    confidence: float,
    learning_rate: float = 0.15,
    min_trade_count: int = 5,
) -> bool:
    # Retorna False si trade_count < min_trade_count (no ajusta)
    # new_mult = old_mult + (suggested - old_mult) * confidence * learning_rate
    # Clampea resultado a [0.5, 1.5]
    ...
```

---

### HardRules (app/analysis/hard_rules.py)

Reglas determinísticas. Sin LLM. Si cualquiera falla, el pipeline retorna REJECTED sin llamar al LLM.

```python
@dataclass
class HardRulesResult:
    passed: bool
    failures: list[str]   # razones si no pasó
    warnings: list[str]   # condiciones que no bloquean pero el LLM debe saber
    earnings_in_days: int | None

def check_all(
    symbol: str,
    features: FeatureSet,
    portfolio: list,
    earnings_date: datetime | None,
    capital: float,
) -> HardRulesResult:
    # Verifica en orden:
    # 1. Liquidez: volume_ratio_20d implica volumen base > 500k acciones/día
    # 2. Earnings gate: earnings en < 3 días → FAIL (en 3-7 días → WARNING)
    # 3. Correlación: si ya hay posición en mismo sector → WARNING si > 0.7, FAIL si > 0.85
    # 4. Capital: unidades calculadas >= 1 con $500 capital → FAIL si 0
    ...
```

---

### AnalysisPipeline (app/analysis/pipeline.py)

El orchestrador central. Se crea por análisis, no es singleton. Lleva el contexto a través de todas las etapas. Provee watchdog y progress streaming integrados.

```python
@dataclass
class AnalysisContext:
    # Contexto de uso — determina TTL y si notificar Telegram
    mode: str  # "on_demand" | "auto_signal" | "daily_discovery" | "backtest"

@dataclass
class AnalysisResult:
    symbol: str
    in_universe: bool
    features: FeatureSet | None
    score: QuantScore | None
    hard_rules: HardRulesResult | None
    llm_narrative: str
    llm_confidence: float        # 0.0-1.0
    recommendation: str          # REJECTED | WATCHLIST | PROPOSE | PRIORITY | BUY | SELL | IGNORE
    parameter_suggestions: list[ParameterSuggestion]  # para post-mortem
    feature_snapshot_id: int | None  # FK guardado en DB
    elapsed_seconds: float
    failed_at_step: str | None   # si watchdog cortó

@dataclass
class ParameterSuggestion:
    dimension: str        # "stop_loss_pct" | "momentum_weight" | etc.
    current_value: float
    suggested_value: float
    confidence: float
    reason: str

class AnalysisPipeline:
    STEP_TIMEOUTS = {
        "fetch_data": 30,
        "compute_indicators": 10,
        "score": 2,
        "hard_rules": 5,
        "llm_interpret": 60,
    }
    TOTAL_TIMEOUT = 600  # 10 minutos

    def __init__(
        self,
        symbol: str,
        data_layer: IBDataLayer,
        context: AnalysisContext,
        notify_fn: Callable[[str], None] | None = None,
        # notify_fn = notify de telegram.py — None si no es on_demand
    ):
        self.symbol = symbol
        self.current_step: str = "init"
        self._result = AnalysisResult(...)
        ...

    def run(self) -> AnalysisResult:
        # Ejecuta pipeline con watchdog threading.Timer(TOTAL_TIMEOUT)
        # Si timer dispara → self._result.failed_at_step = self.current_step → notifica
        try:
            self._fetch_data()
            self._compute_indicators()
            self._score()
            self._check_hard_rules()
            if self._result.hard_rules.passed:
                self._llm_interpret()
            self._persist()
        except PipelineTimeout:
            self._notify_timeout()
        return self._result

    def _notify_progress(self, message: str):
        if self.notify_fn:
            self.notify_fn(message)

    def _fetch_data(self):
        self.current_step = "fetch_data"
        self._notify_progress(f"Descargando datos {self.symbol}...")
        # Llama IBDataLayer con TTL según context.mode
        ...

    def _compute_indicators(self):
        self.current_step = "compute_indicators"
        self._notify_progress(f"Calculando indicadores {self.symbol}...")
        # Llama IndicatorEngine.compute_features()
        ...

    def _score(self):
        self.current_step = "score"
        # Sin notificación — < 2s, silencioso
        ...

    def _check_hard_rules(self):
        self.current_step = "hard_rules"
        # Si falla → notify y retorna sin llamar LLM
        ...

    def _llm_interpret(self):
        self.current_step = "llm_interpret"
        self._notify_progress(f"Consultando LLM para {self.symbol} (score: {self._result.score.total:.0f})...")
        # Construye prompt estructurado con FeatureSet + QuantScore + HardRulesResult
        # Un solo call a _call_opencode()
        # Parsea respuesta: narrative, confidence, parameter_suggestions
        ...

    def _persist(self):
        # Guarda FeatureSnapshot, CandidateDecision en DB
        # Actualiza WatchlistScore si corresponde
        ...
```

---

### PostMortem v2 (app/llm/postmortem.py — refactor)

Migra de openai SDK a `_call_opencode()`. Agrega sugerencias de ajuste estructuradas. Llama `update_weights_attenuated()` si trade_count >= 5.

```python
def run_postmortem(trade: Trade, feature_snapshot: FeatureSet | None = None):
    # Usa _call_opencode() — no openai SDK
    # Prompt incluye el FeatureSet al momento de entrada (si disponible)
    # LLM retorna JSON estructurado:
    # {
    #   "pattern_text": "AAPL + RSI<30 + MACD alcista → BUY confiable",
    #   "suggestions": [
    #     {"dimension": "stop_loss_pct", "suggested": 0.028, "confidence": 0.7, "reason": "ATR sugiere SL más amplio"},
    #     {"dimension": "momentum_weight", "suggested_multiplier": 1.2, "confidence": 0.6, "reason": "RSI fue el indicador más predictivo"}
    #   ]
    # }
    # Aplica sugerencias atenuadas via QuantScorer.update_weights_attenuated()
    ...
```

---

## Key Workflows

### Workflow 1: Análisis on-demand `/analizar NFLX`

```
Frank: /analizar NFLX

telegram_bot.cmd_analizar("NFLX")
    ↓
pipeline = AnalysisPipeline(
    symbol="NFLX",
    data_layer=data_layer,  # singleton de run.py
    context=AnalysisContext(mode="on_demand"),
    notify_fn=notify,       # Telegram streaming
)
    ↓
pipeline.run()
    ↓ progress: "Descargando datos NFLX..."
    fetch_data() → IBDataLayer.get_ohlcv(ttl=120s) + get_news() + get_earnings_date()
    ↓ progress: "Calculando indicadores NFLX..."
    compute_indicators() → IndicatorEngine.compute_features()
    ↓
    score() → QuantScorer.compute_score() → QuantScore(total=72, recommendation="PROPOSE")
    ↓
    check_hard_rules() → HardRulesResult(passed=True, warnings=["earnings in 8 days"])
    ↓ progress: "Consultando LLM (score: 72)..."
    llm_interpret() → narrative + confidence=0.74 + parameter_suggestions
    ↓
    persist() → CandidateDecision guardado, WatchlistScore actualizado

Frank recibe:
"NFLX — Score: 72/100 [PROPONER INCLUSIÓN]
RSI 61, MACD alcista, vol 1.4x, RS vs SPY: +12%
Volatilidad: media-alta (ATR 3.1%)
Earnings en 8 días — considerar reducir TP

LLM: 'Condiciones técnicas favorables para swing corto. El momentum post-earnings previo fue positivo (ver patrones). Riesgo: earnings próximos pueden invalidar el setup.'
Confianza: 74%

¿Agregar NFLX al universo? /proponer NFLX momentum_tecnico_favorable"
```

### Workflow 2: Señal automática → ejecución

```
scanner (cada 15 min)
    ↓ señal STRONG: AAPL RSI=28, MACD cross, vol=1.8x
    insert_signal(Signal(symbol="AAPL", strength="STRONG", ...))

signal_processor (cada 15 min)
    ↓ lee pending signals
    pipeline = AnalysisPipeline(
        symbol="AAPL",
        data_layer=data_layer,
        context=AnalysisContext(mode="auto_signal"),
        notify_fn=notify,  # notifica a Frank
    )
    ↓
    pipeline.run() → AnalysisResult(recommendation="BUY", score=81)
    ↓ si BUY/SELL:
    POST /orders/place → RiskValidator → IBKRClient.place_order()
    ↓
    insert_trade(Trade(..., feature_snapshot_id=snapshot.id))
```

### Workflow 3: Discovery diario y rotación de universo

```
daily_discovery (8am ET, días de mercado)
    ↓
    IBDataLayer.run_scanner("HOT_BY_VOLUME") → ["NFLX", "SHOP", "PLTR", ...]
    IBDataLayer.run_scanner("TOP_PERC_GAIN") → [...]
    candidatos = union(scanners) - ALLOWED_SYMBOLS, top 20 por volumen
    ↓
    for symbol in candidatos:
        pipeline = AnalysisPipeline(
            symbol=symbol,
            data_layer=data_layer,
            context=AnalysisContext(mode="daily_discovery"),
            notify_fn=None,  # sin streaming — batch silencioso
        )
        result = pipeline.run()
        # Si score >= 70: candidato para watchlist
    ↓
    universe_rotation(candidates, current_universe)
    → si mejor_candidato.score > 75 y peor_universo.watchlist_score < 40:
        notifica Frank: "NFLX (78) entra, META (38) sale"
        actualiza ALLOWED_SYMBOLS en DB
```

### Workflow 4: Post-mortem y aprendizaje

```
position_manager.check_positions()
    ↓ AAPL toca take-profit
    close_trade(trade_id, exit_price, "TAKE_PROFIT", pnl_usd, pnl_pct)
    ↓
    feature_snapshot = load_snapshot(trade.feature_snapshot_id)  # snapshot al momento de entrada
    run_postmortem(trade, feature_snapshot)
    ↓
    LLM recibe: trade completo + FeatureSet original + resultado
    LLM retorna: pattern_text + parameter_suggestions
    ↓
    insert_pattern(pattern_text)
    for suggestion in parameter_suggestions:
        QuantScorer.update_weights_attenuated(
            symbol="AAPL",
            dimension=suggestion.dimension,
            suggested_multiplier=suggestion.suggested_value,
            confidence=suggestion.confidence,
        )
    ↓ notifica Frank: "Post-mortem AAPL: patrón guardado. Ajuste: momentum +8% (atenuado)"
```

### Workflow 5: ReturnEvaluator — validación retrospectiva

```
return_evaluator (daily 6am ET)
    ↓
    decisions_7d = get_candidate_decisions_from_7_days_ago()
    for decision in decisions_7d:
        current_price = IBDataLayer.get_ohlcv(decision.symbol, "1 D", "1 day", "backtest")
        spy_price_then = IBDataLayer.get_spy_price_on(decision.date)
        spy_price_now = IBDataLayer.get_ohlcv("SPY", "1 D", "1 day", "backtest")

        return_7d = (current_price - decision.price_at_decision) / decision.price_at_decision
        spy_return = (spy_now - spy_then) / spy_then
        alpha_7d = return_7d - spy_return

        update_candidate_decision(decision.id, future_return_7d=return_7d, alpha_vs_spy_7d=alpha_7d)

    # Si el sistema tiene >= 20 decisiones evaluadas:
    # ReturnEvaluator ajusta thresholds del scorer si accuracy < 50%
    # (determinístico, sin LLM)
```

---

## Components to Build

| Component | Path | Priority |
|---|---|---|
| IBDataLayer | app/analysis/data.py | P0 — todo depende de esto |
| MockIBClient | app/analysis/mock_client.py | P0 — bloquea tests locales |
| IndicatorEngine | app/analysis/indicators.py | P0 — bloquea pipeline |
| QuantScorer | app/analysis/scorer.py | P1 |
| HardRules | app/analysis/hard_rules.py | P1 |
| AnalysisPipeline | app/analysis/pipeline.py | P1 |
| PostMortem v2 (bug fix) | app/llm/postmortem.py | P0 — bug activo |
| settings.py env vars | app/config/settings.py | P0 — bloquea dev local |
| DB: 4 nuevas tablas | app/db/models.py + database.py | P1 |
| DailyDiscovery job | run.py | P2 |
| ReturnEvaluator job | run.py | P2 |
| UniverseRotation | app/analysis/admission.py | P2 |

## Components to Migrate

| Component | Change | Risk |
|---|---|---|
| preprocessor.py | Importar de IndicatorEngine en vez de definir _calc_indicators | Low |
| backtest/engine.py | Importar de IndicatorEngine en vez de preprocessor | Low |
| agent.py | Recibir FeatureSet JSON, mover OPENCODE_BIN a settings | Medium |
| telegram_bot.cmd_analizar | Usar AnalysisPipeline en vez de prompt libre | Medium |
| loop.py | Usar AnalysisPipeline en vez de analyze_signal() directo | Medium |
| mcp/server.py | Agregar tools: candidate_analysis, compute_indicator | Low |

---

## Trade-offs Made

**Optimizando para:**
- Visibilidad del progreso — Frank siempre sabe en qué paso está el análisis
- Auditabilidad — cada decisión tiene su FeatureSnapshot guardado
- Cohesión — el estado del análisis está contenido en el pipeline object
- Testabilidad local — MockIBClient + AnalysisContext permiten tests sin IB Gateway

**Sacrificando:**
- Flexibilidad de composición — no puedes reordenar los steps (vs Alternativa C)
- Pureza funcional — el pipeline tiene estado mutable (vs Alternativa A)

**Por qué este trade-off es correcto:**
El sistema corre en un solo proceso en la Pi. El usuario (Frank) interactúa principalmente via Telegram. La prioridad es confiabilidad operacional y feedback visible, no extensibilidad arquitectural abstracta. Si en el futuro hay múltiples pipelines (opciones, futuros, crypto), se refactoriza a Alternativa C — el AnalysisPipeline es el candidato natural a extraer como nodo.

---

**Document Version**: 1.0
**Created by**: Phase 2 Design
**Approved**: ✓ Frank — Alternativa B elegida
