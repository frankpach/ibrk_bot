# Dashboard & Control UX Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar legibilidad, responsiveness mobile (iPhone 13 Pro 390×844), gráfica colapsable con más periodos, QuickScan prominente, control plane funcional con seed de settings LLM y selección de modelo por tarea.

**Architecture:** Todos los cambios son en `app/api/dashboard.py` (React inline) y `app/api/control_plane.py` (React inline) + un script de seed DB (`scripts/seed_control_settings.py`) + ajuste en `app/llm/agent.py` para leer modelo de DB. No hay build step — React via CDN, cambios se sirven en caliente desde FastAPI.

**Tech Stack:** Python/FastAPI (backend), React 18 inline (frontend), LightweightCharts 4.1.3 (gráfica), SQLite/PostgreSQL vía `app/infrastructure/db/compat.py`, `app/application/use_cases/update_control_setting.py`

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/api/dashboard.py` | CSS responsive + fuentes + SymbolChart colapsable + periodos + QuickScan header |
| `app/api/control_plane.py` | CSS mobile sidebar + LLM panel + formularios pre-poblados |
| `app/api/main.py` | Endpoint `/dashboard/symbol/{symbol}` — añadir periodos 1h, 4h, 1w, 3m |
| `app/llm/agent.py` | Leer `OPENCODE_MODEL` de DB según tarea (analysis/signal/postmortem) |
| `app/infrastructure/db/compat.py` | Función `get_control_setting_value(key, default)` |
| `scripts/seed_control_settings.py` | Script one-shot para poblar settings LLM en DB |
| `tests/api/test_dashboard_symbol.py` | Tests para nuevos periodos de la gráfica |
| `tests/test_control_seed.py` | Tests para seed de settings |

---

## Task 1: Seed de control_settings con defaults LLM

**Problema:** Los formularios de InfraPanel aparecen vacíos porque `control_settings` no tiene valores para `opencode_model`, `opencode_bin`, etc. `RiskPanel` también vacío por la misma razón.

**Files:**
- Create: `scripts/seed_control_settings.py`
- Modify: `app/infrastructure/db/compat.py` (añadir `get_control_setting_value`)

- [ ] **Step 1: Añadir `get_control_setting_value` a compat.py**

En `app/infrastructure/db/compat.py`, añadir al final (antes del último bloque):

```python
def get_control_setting_value(key: str, default: str = "") -> str:
    """Return the value of a control setting, or default if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM control_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def seed_control_setting(key: str, value: str, is_secret: bool = False) -> None:
    """Insert a control setting only if it doesn't exist yet."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT key FROM control_settings WHERE key = ?", (key,)
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO control_settings (key, value, is_secret, updated_at, updated_by)
                   VALUES (?, ?, ?, datetime('now'), 'seed')""",
                (key, value, 1 if is_secret else 0),
            )
            conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Crear `scripts/seed_control_settings.py`**

```python
#!/usr/bin/env python3
"""
Seed control_settings table with defaults from .env / settings.py.
Run once after deployment: python scripts/seed_control_settings.py
Safe to re-run — skips existing keys.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config.settings import (
    OPENCODE_BIN, OPENCODE_MODEL, IB_HOST,
    MAX_POSITIONS, MAX_RISK_PCT, MIN_RISK_USD,
    MAX_POSITION_USD, CAPITAL_CAP, DATABASE_URL if hasattr(__import__('app.config.settings', fromlist=['DATABASE_URL']), 'DATABASE_URL') else None,
)
from app.infrastructure.db.compat import seed_control_setting, init_db

init_db()

DEFAULTS = [
    # Risk
    ("max_positions",         str(MAX_POSITIONS),    False),
    ("max_risk_pct",          str(MAX_RISK_PCT),     False),
    ("min_risk_usd",          str(MIN_RISK_USD),     False),
    ("max_position_usd",      str(MAX_POSITION_USD), False),
    ("capital_cap",           str(CAPITAL_CAP),      False),
    # Infra
    ("ib_host",               IB_HOST,               False),
    ("opencode_bin",          OPENCODE_BIN,           False),
    ("opencode_model",        OPENCODE_MODEL,         False),
    # LLM per-task models
    ("llm_model_analysis",    OPENCODE_MODEL,         False),
    ("llm_model_signal",      OPENCODE_MODEL,         False),
    ("llm_model_postmortem",  OPENCODE_MODEL,         False),
]

for key, value, is_secret in DEFAULTS:
    if value:
        seed_control_setting(key, value, is_secret)
        print(f"  seeded: {key} = {value[:40]}")

print("Done.")
```

- [ ] **Step 3: Ejecutar el seed en el Pi**

```bash
ssh aiutox-pi "cd /home/frankpach/ibkr-bot && .venv/bin/python scripts/seed_control_settings.py"
```

Resultado esperado:
```
  seeded: max_positions = 3
  seeded: max_risk_pct = 0.02
  ...
  seeded: llm_model_analysis = opencode-go/qwen3.5-plus
  seeded: llm_model_signal = opencode-go/qwen3.5-plus
  seeded: llm_model_postmortem = opencode-go/qwen3.5-plus
Done.
```

- [ ] **Step 4: Verificar que /control/settings devuelve los valores**

```bash
curl http://aiutox-pi:8088/control/settings | python3 -m json.tool | grep -E '"key"|"value"' | head -30
```

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_control_settings.py app/infrastructure/db/compat.py
git commit -m "feat(control): seed control_settings with LLM and risk defaults"
```

---

## Task 2: Control plane — LLM Panel + mobile sidebar

**Problema:** No hay panel de modelos LLM en /control. En móvil, la sidebar está cortada y las secciones no son accesibles.

**Files:**
- Modify: `app/api/control_plane.py`

- [ ] **Step 1: Añadir CSS responsive para sidebar en control_plane.py**

Localizar el bloque `.sidebar{` (línea ~52) y añadir después del CSS existente:

```css
/* ─── Mobile Responsive ─────────────────────────────── */
@media(max-width:768px){
  .ctrl-page{flex-direction:column}
  .sidebar{
    width:100%;border-right:none;border-bottom:1px solid var(--border);
    flex-direction:row;padding:4px 8px;gap:0;overflow-x:auto;
    flex-wrap:nowrap;white-space:nowrap;
  }
  .sidebar-item{
    padding:8px 12px;font-size:.8rem;border-bottom:none;
    border-right:1px solid var(--border);flex-shrink:0;
  }
  .sidebar-item.active{border-bottom:2px solid var(--blue);border-right:none}
  .ctrl-content{padding:8px}
}
@media(min-width:769px){
  .ctrl-content{padding:16px;flex:1;overflow-y:auto}
}
```

- [ ] **Step 2: Añadir `LLMPanel` component en control_plane.py**

Añadir antes de `function JobsPanel()`:

```javascript
function LLMPanel() {
  const [settings, setSettings] = useState({});
  const [toast, setToast] = useState(null);
  const taskKeys = [
    ['llm_model_analysis',   'Análisis Técnico', 'Pipeline de análisis on-demand'],
    ['llm_model_signal',     'Procesamiento Señales', 'Loop de señales en tiempo real'],
    ['llm_model_postmortem', 'Postmortem/Aprendizaje', 'Ciclo de aprendizaje semanal'],
    ['opencode_model',       'Modelo Global (fallback)', 'Usado si no hay valor por tarea'],
    ['opencode_bin',         'OpenCode Binary Path', 'Ruta al binario opencode'],
  ];
  const SUGGESTIONS = [
    'opencode-go/qwen3.5-plus',
    'opencode-go/claude-sonnet-4',
    'opencode-go/gpt-4o',
    'opencode-go/gemini-2.5-pro',
    'anthropic/claude-opus-4-5',
  ];

  useEffect(() => {
    fetch('/control/settings').then(r=>r.json()).then(d=>{
      const map = {};
      (d.settings||[]).forEach(s => { map[s.key] = s.value; });
      setSettings(map);
    }).catch(()=>{});
  }, []);

  async function save(key) {
    try {
      const res = await fetch(`/control/settings/${key}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Control-Key': localStorage.getItem('ctrlKey') || '',
        },
        body: JSON.stringify({ value: String(settings[key] || '') }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      setToast({ msg: `✓ ${key} guardado`, err: false });
    } catch(e) {
      setToast({ msg: 'Error: ' + e.message, err: true });
    }
  }

  return (
    <div>
      {toast && <Toast msg={toast.msg} isError={toast.err} onClose={()=>setToast(null)} />}
      <div className="card">
        <div className="ch">
          <span className="ct">Modelos LLM por Tarea</span>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--dim)'}}>
            cambios aplican en el próximo análisis
          </span>
        </div>
        <div className="cb">
          {taskKeys.map(([key, label, hint]) => (
            <div className="field" key={key}>
              <label>{label}</label>
              <div style={{fontSize:'.7rem',color:'var(--dim)',marginBottom:4,fontFamily:'"Fira Code",monospace'}}>{hint}</div>
              <div style={{display:'flex',gap:8,alignItems:'center',flexWrap:'wrap'}}>
                <input
                  list={`suggest-${key}`}
                  value={settings[key] || ''}
                  onChange={e => setSettings(prev => ({...prev, [key]: e.target.value}))}
                  style={{flex:1,minWidth:200}}
                  placeholder="modelo/nombre"
                />
                <datalist id={`suggest-${key}`}>
                  {SUGGESTIONS.map(s => <option key={s} value={s} />)}
                </datalist>
                <button className="btn btn-primary" onClick={() => save(key)}>Guardar</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Añadir LLM al sidebar y routing en control_plane.py**

Localizar donde se define el array de secciones del sidebar (buscar `'operativo'` o `section==='risk'`):

En el array de items del sidebar, añadir `['llm', '🤖 Modelos LLM']` y en el router:
```javascript
{section==='llm' && <LLMPanel />}
```

- [ ] **Step 4: Copiar al Pi y verificar visualmente**

```bash
scp app/api/control_plane.py aiutox-pi:/home/frankpach/ibkr-bot/app/api/control_plane.py
ssh aiutox-pi "sudo systemctl restart ibkr-api.service && sleep 20 && systemctl is-active ibkr-api.service"
```

Abrir en browser: `http://aiutox-pi:8088/control` — verificar que aparece "🤖 Modelos LLM" en el sidebar y los campos muestran valores del seed.

- [ ] **Step 5: Commit**

```bash
git add app/api/control_plane.py
git commit -m "feat(control): add LLM panel + mobile responsive sidebar"
```

---

## Task 3: Selección de modelo LLM por tarea en agent.py

**Problema:** `app/llm/agent.py` tiene `OPENCODE_MODEL` hardcodeado. No usa la DB.

**Files:**
- Modify: `app/llm/agent.py:23`
- Modify: `app/infrastructure/llm/opencode_adapter.py`

- [ ] **Step 1: Añadir función `get_llm_model_for_task` en agent.py**

Reemplazar línea 23 (`OPENCODE_MODEL = "opencode-go/qwen3.5-plus"`) con:

```python
from app.config.settings import OPENCODE_MODEL as _DEFAULT_OPENCODE_MODEL

def get_llm_model_for_task(task: str = "analysis") -> str:
    """Read per-task LLM model from control_settings DB, fallback to env default."""
    key_map = {
        "analysis":   "llm_model_analysis",
        "signal":     "llm_model_signal",
        "postmortem": "llm_model_postmortem",
    }
    key = key_map.get(task, "opencode_model")
    try:
        from app.infrastructure.db.compat import get_control_setting_value
        val = get_control_setting_value(key, _DEFAULT_OPENCODE_MODEL)
        return val if val else _DEFAULT_OPENCODE_MODEL
    except Exception:
        return _DEFAULT_OPENCODE_MODEL
```

- [ ] **Step 2: Usar `get_llm_model_for_task` en las llamadas LLM**

En `app/llm/agent.py`, buscar donde se llama al modelo (buscar `OPENCODE_MODEL` o `run_opencode`) y reemplazar con:

```python
model = get_llm_model_for_task("analysis")
```

En `app/llm/loop.py` (si tiene llamadas LLM directas):
```python
from app.llm.agent import get_llm_model_for_task
model = get_llm_model_for_task("signal")
```

En `app/ml/cycle.py` (postmortem):
```python
from app.llm.agent import get_llm_model_for_task
model = get_llm_model_for_task("postmortem")
```

- [ ] **Step 3: Test**

```python
# tests/test_llm_model_selection.py
from unittest.mock import patch
from app.llm.agent import get_llm_model_for_task

def test_fallback_when_db_fails():
    with patch("app.infrastructure.db.compat.get_control_setting_value",
               side_effect=Exception("db down")):
        model = get_llm_model_for_task("analysis")
    assert "qwen" in model or "opencode" in model

def test_returns_db_value():
    with patch("app.infrastructure.db.compat.get_control_setting_value",
               return_value="opencode-go/claude-sonnet-4"):
        model = get_llm_model_for_task("analysis")
    assert model == "opencode-go/claude-sonnet-4"

def test_per_task_key_mapping():
    calls = []
    def fake_get(key, default):
        calls.append(key)
        return default
    with patch("app.infrastructure.db.compat.get_control_setting_value", side_effect=fake_get):
        get_llm_model_for_task("signal")
        get_llm_model_for_task("postmortem")
    assert "llm_model_signal" in calls
    assert "llm_model_postmortem" in calls
```

- [ ] **Step 4: Ejecutar tests**

```bash
uv run pytest tests/test_llm_model_selection.py -v
```

Esperado: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/llm/agent.py tests/test_llm_model_selection.py
git commit -m "feat(llm): per-task model selection from control_settings DB"
```

---

## Task 4: CSS global — fuentes legibles + responsive dashboard

**Problema medido:** 169 elementos con 10.88px, tags en 8.8px, tabs en 10.24px. En iPhone 390px las tablas desbordan.

**Files:**
- Modify: `app/api/dashboard.py` (bloque `<style>`)

- [ ] **Step 1: Actualizar escala de fuentes en dashboard.py**

En el bloque `<style>`, reemplazar las definiciones de clases problemáticas:

```css
/* ANTES: .ct{font-size:.65rem} → DESPUÉS: */
.ct{font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.sl{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-bottom:4px}
.ss{font-family:"Fira Code",monospace;font-size:.78rem;color:var(--muted);margin-top:3px}

/* ANTES: .tag{font-size:.62rem} → DESPUÉS: */
.tag{display:inline-block;padding:2px 7px;border-radius:3px;font-size:.72rem;font-family:"Fira Code",monospace;font-weight:500;border:1px solid}

/* ANTES: .tab{font-size:.64rem} → DESPUÉS: */
.tab{padding:4px 10px;border-radius:4px;font-family:"Fira Code",monospace;font-size:.75rem;color:var(--dim);cursor:pointer;border:none;background:transparent;white-space:nowrap}

/* ANTES: table{font-size:.68rem} → DESPUÉS: */
table{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.8rem}
th{color:var(--dim);font-weight:500;padding:6px 8px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:6px 8px;border-bottom:1px solid var(--border);color:var(--muted)}

/* ANTES: .tl-item{font-size:.68rem} → DESPUÉS: */
.tl-item{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid var(--border);font-family:"Fira Code",monospace;font-size:.8rem}
.tl-time{min-width:44px;color:var(--dim);font-size:.72rem}

/* ANTES: .mkt-bar{font-size:.62rem} → DESPUÉS: */
.mkt-bar{padding:6px 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:var(--surface2);border-bottom:1px solid var(--border);font-family:"Fira Code",monospace;font-size:.75rem}

/* ANTES: .sys-bar{font-size:.65rem} → DESPUÉS: */
.sys-bar{padding:6px 12px;display:flex;align-items:center;gap:12px;font-family:"Fira Code",monospace;font-size:.78rem;background:var(--surface2);border-bottom:1px solid var(--border);flex-wrap:wrap}

/* ANTES: .qs-input{font-size:.75rem} → DESPUÉS: */
.qs-input{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:5px;padding:6px 10px;font-size:.82rem;font-family:"Fira Code",monospace;width:150px}

/* ANTES: .empty{font-size:.72rem} → DESPUÉS: */
.empty{color:var(--dimmer);font-family:"Fira Code",monospace;font-size:.82rem;padding:1.4rem 0;text-align:center;letter-spacing:.04em}

/* .pos-grid font */
.pos-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:4px 8px;font-family:"Fira Code",monospace;font-size:.8rem;margin:8px 0}
```

- [ ] **Step 2: Añadir media queries mobile para el dashboard**

Añadir al final del bloque `<style>` (antes de `</style>`):

```css
/* ─── Mobile (iPhone 13 Pro: 390px) ─────────────────── */
@media(max-width:480px){
  html{font-size:15px}
  .page{padding:6px;gap:6px}
  .header{padding:6px 10px}
  .logo{font-size:1.1rem}
  .badge{font-size:.72rem}
  .sv{font-size:1.6rem}
  .sc{padding:10px}
  .ch{padding:6px 10px;gap:6px}
  .ct{font-size:.82rem}
  .tag{font-size:.74rem;padding:2px 6px}
  .tab{font-size:.74rem;padding:3px 8px}
  .btn{font-size:.82rem;padding:5px 10px}
  .pos-grid{grid-template-columns:repeat(2,1fr);font-size:.78rem}
  .scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch}
  /* Forzar scroll horizontal en tablas */
  table{min-width:500px}
  .table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -10px;padding:0 10px}
  /* Ocultar columnas secundarias en mobile */
  .hide-mobile{display:none!important}
  .mkt-bar{font-size:.78rem;gap:6px}
  .sys-bar{font-size:.8rem}
}
@media(max-width:640px){
  .row-2{grid-template-columns:1fr}
  .row-3{grid-template-columns:1fr}
  .row-4{grid-template-columns:repeat(2,1fr)}
}
```

- [ ] **Step 3: Envolver tablas en .table-wrap**

En el componente `UniversoTable` (línea ~862 aprox.), envolver el `<table>` en:
```jsx
<div className="table-wrap scroll-x">
  <table>...</table>
</div>
```

Hacer lo mismo en cualquier otra tabla en el dashboard.

- [ ] **Step 4: Verificar con Playwright en 390px**

```javascript
// Ejecutar en Playwright:
await page.setViewportSize({ width: 390, height: 844 });
await page.goto('http://aiutox-pi:8088/dashboard');
await page.screenshot({ path: 'e2e-iphone-after.png', fullPage: true });
```

Verificar: sin overflow horizontal, texto legible, cards apilados verticalmente.

- [ ] **Step 5: Commit**

```bash
git add app/api/dashboard.py
git commit -m "fix(ui): increase font sizes to 0.75-0.82rem, add mobile responsive CSS"
```

---

## Task 5: SymbolChart colapsable + click desde cualquier componente

**Problema:** `if(!chips.length) return null` elimina la gráfica. Chips solo de open_trades+signals. No hay forma de navegar a la gráfica desde otras tablas.

**Files:**
- Modify: `app/api/dashboard.py` — componente `SymbolChart` (líneas 524-670)

- [ ] **Step 1: Añadir estado global de símbolo seleccionado vía window**

En el bloque `<script type="text/babel">`, añadir después de la definición de `fmt`:

```javascript
// Global chart symbol bus — any component can set this
window._chartBus = { listeners: [], emit(sym) { this.listeners.forEach(fn => fn(sym)); } };
function useChartBus(cb) {
  React.useEffect(() => {
    window._chartBus.listeners.push(cb);
    return () => { window._chartBus.listeners = window._chartBus.listeners.filter(f => f !== cb); };
  }, [cb]);
}
```

- [ ] **Step 2: Reemplazar SymbolChart con versión colapsable**

Reemplazar el componente completo `function SymbolChart({ data })` con:

```javascript
function SymbolChart({ data }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [cdata, setCdata] = useState(null);
  const [tab, setTab] = useState('intraday');
  const [loading, setLoading] = useState(false);
  const [inds, setInds] = useState({volume:true,vwap:true,ema9:true,ema20:false,boll:false,rsi:false,macd:false});
  const chartRef = useRef(null);
  const tvRef = useRef(null);
  const seriesRef = useRef({});

  // Chips: open trades + universe symbols (max 12)
  const chips = useMemo(() => {
    const openSyms = (data?.open_trades||[]).map(t => t.symbol);
    const uniSyms = (data?.symbols_universe||[]).map(s => s.symbol);
    const all = [...new Set([...openSyms, ...uniSyms])].slice(0, 12);
    return { all, open: new Set(openSyms) };
  }, [data]);

  // Listen to global chart bus
  const handleBus = useCallback((sym) => {
    setOpen(true);
    selectSym(sym);
  }, []);
  useChartBus(handleBus);

  const PERIODS = [
    ['intraday', 'Hoy 5m'],
    ['1h',       '1h'],
    ['4h',       '4h'],
    ['daily',    '30D'],
    ['weekly',   '1W'],
    ['monthly',  '3M'],
  ];

  async function load(sym, period) {
    setLoading(true);
    try {
      const res = await fetch(`/dashboard/symbol/${sym}?period=${period}`);
      const d = await res.json();
      setCdata(d);
    } catch(e) { setCdata(null); }
    setLoading(false);
  }

  function selectSym(sym) { setSelected(sym); load(sym, tab); }
  function switchTab(t) { setTab(t); if (selected) load(selected, t); }

  useEffect(() => {
    if (!chartRef.current || !cdata?.bars?.length || typeof LightweightCharts === 'undefined') return;
    if (tvRef.current) { try { tvRef.current.remove(); } catch(e) {} tvRef.current = null; seriesRef.current = {}; }
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const bg = isDark ? '#0C1421' : '#FFFFFF';
    const text = isDark ? '#94A3B8' : '#475569';
    const grid = isDark ? '#1E2D42' : '#E2E8F0';
    const chart = LightweightCharts.createChart(chartRef.current, {
      layout: { background: { color: bg }, textColor: text },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, timeVisible: false },
      width: chartRef.current.clientWidth, height: 260,
    });
    tvRef.current = chart;
    const bars = cdata.bars;
    const candle = chart.addCandlestickSeries({ upColor:'#10B981',downColor:'#F43F5E',borderUpColor:'#10B981',borderDownColor:'#F43F5E',wickUpColor:'#10B981',wickDownColor:'#F43F5E' });
    candle.setData(bars.map(b => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));
    const trade = (data?.open_trades||[]).find(t => t.symbol === selected);
    if (trade && bars.length > 0) {
      [[trade.entry_price,'#FBBF24'],[trade.stop_loss_price,'#F43F5E'],[trade.take_profit_price,'#10B981']].forEach(([price, color]) => {
        if (price == null) return;
        const s = chart.addLineSeries({ color, lineWidth: 1, lineStyle: LightweightCharts.LineStyle.LargeDashed });
        s.setData(bars.map(b => ({ time: b.time, value: parseFloat(price) })));
      });
    }
    if (inds.volume) {
      const vol = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol', color: '#38BDF840' });
      chart.priceScale('vol').applyOptions({ scaleMargins: { top: .82, bottom: 0 } });
      vol.setData(bars.map(b => ({ time: b.time, value: b.volume, color: b.close >= b.open ? '#10B98140' : '#F43F5E40' })));
    }
    if (inds.vwap && cdata.vwap_series?.length) { const s=chart.addLineSeries({color:'#A78BFA',lineWidth:1}); s.setData(cdata.vwap_series); }
    if (inds.ema9 && cdata.ema9_series?.length) { const s=chart.addLineSeries({color:'#FBBF24',lineWidth:1}); s.setData(cdata.ema9_series); }
    if (inds.ema20 && cdata.ema20_series?.length) { const s=chart.addLineSeries({color:'#38BDF8',lineWidth:1}); s.setData(cdata.ema20_series); }
    if (inds.boll && cdata.boll_series?.length) {
      const u=chart.addLineSeries({color:'#A78BFA50',lineWidth:1}); u.setData(cdata.boll_series.map(b=>({time:b.time,value:b.upper})));
      const m=chart.addLineSeries({color:'#A78BFA80',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed}); m.setData(cdata.boll_series.map(b=>({time:b.time,value:b.middle})));
      const l=chart.addLineSeries({color:'#A78BFA50',lineWidth:1}); l.setData(cdata.boll_series.map(b=>({time:b.time,value:b.lower})));
    }
    chart.timeScale().fitContent();
    const ro = new ResizeObserver(() => { if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth }); });
    ro.observe(chartRef.current);
    return () => ro.disconnect();
  }, [cdata, inds]);

  const toggle = k => setInds(p => ({...p, [k]: !p[k]}));

  return (
    <div className="card fade-up">
      {/* Header siempre visible con toggle */}
      <div className="ch" style={{cursor:'pointer'}} onClick={() => setOpen(o => !o)}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontSize:'1rem',lineHeight:1}}>{open ? '▾' : '▸'}</span>
          <span className="ct">📈 Gráfica</span>
          {selected && <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',color:'var(--blue)',marginLeft:4}}>{selected}</span>}
        </div>
        {!open && <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.75rem',color:'var(--dim)'}}>
          {chips.all.length} símbolos disponibles — click para expandir
        </span>}
      </div>

      {open && (
        <>
          {/* Selector de símbolos */}
          <div style={{display:'flex',gap:6,flexWrap:'wrap',padding:'8px 12px',borderBottom:'1px solid var(--border)',alignItems:'center',background:'var(--surface2)'}}>
            {chips.all.map(sym => (
              <button key={sym} onClick={e => { e.stopPropagation(); selectSym(sym); }}
                style={{padding:'3px 10px',borderRadius:12,fontFamily:'"Fira Code",monospace',fontSize:'.78rem',cursor:'pointer',
                  border:'1px solid '+(selected===sym?'rgba(56,189,248,.35)':'var(--border)'),
                  background:selected===sym?'var(--blue-bg)':'transparent',
                  color:selected===sym?'var(--blue)':'var(--muted)',position:'relative'}}>
                {sym}
                {chips.open.has(sym) && <span style={{position:'absolute',top:-3,right:-3,width:6,height:6,borderRadius:'50%',background:'var(--amber)'}} />}
              </button>
            ))}
            <QuickScan onSelect={sym => { setOpen(true); selectSym(sym); }} compact />
          </div>

          {/* Indicadores y periodos */}
          <div className="ch">
            <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}>
              <span className="ct">{selected || 'Símbolo'}</span>
              {cdata?.atr != null && <span className="tag tag-neutral">ATR {fmt.n(cdata.atr,2)}</span>}
              {cdata?.volume_relative != null && <span className="tag tag-neutral">RVOL {fmt.n(cdata.volume_relative,1)}x</span>}
              {['volume','vwap','ema9','ema20','boll','rsi','macd'].map(ind => (
                <button key={ind} onClick={() => toggle(ind)}
                  style={{padding:'2px 7px',borderRadius:3,fontFamily:'"Fira Code",monospace',fontSize:'.72rem',cursor:'pointer',
                    background:inds[ind]?'var(--blue-bg)':'transparent',color:inds[ind]?'var(--blue)':'var(--dim)',
                    border:`1px solid ${inds[ind]?'rgba(56,189,248,.3)':'var(--border)'}`}}>
                  {ind.toUpperCase()}
                </button>
              ))}
            </div>
            <div className="tabs">
              {PERIODS.map(([t,l]) => (
                <button key={t} className={'tab'+(tab===t?' on':'')} onClick={e => { e.stopPropagation(); switchTab(t); }}>{l}</button>
              ))}
            </div>
          </div>

          {/* Chart */}
          <div className="cb" style={{padding:'8px 12px',minHeight:280}}>
            {loading && <span className="empty">cargando {selected}...</span>}
            {!loading && !cdata && selected && <span className="empty">// sin datos para {selected}</span>}
            {!loading && !selected && <span className="empty">// selecciona un símbolo arriba</span>}
            <div ref={chartRef} style={{width:'100%',display:cdata?.bars?.length && !loading ? 'block' : 'none'}} />
            {inds.rsi && cdata?.rsi_series?.length && !loading && (
              <div style={{marginTop:6,fontFamily:'"Fira Code",monospace',fontSize:'.78rem'}}>
                <span style={{color:'var(--dim)'}}>RSI(14): </span>
                <span style={{color:cdata.rsi_series.at(-1).value>70?'var(--red)':cdata.rsi_series.at(-1).value<30?'var(--green)':'var(--text)'}}>
                  {fmt.n(cdata.rsi_series.at(-1).value,1)}
                </span>
              </div>
            )}
            {inds.macd && cdata?.macd_series?.length && !loading && (
              <div style={{marginTop:4,fontFamily:'"Fira Code",monospace',fontSize:'.78rem'}}>
                <span style={{color:'var(--dim)'}}>MACD: </span>
                <span style={{color:cdata.macd_series.at(-1).histogram>0?'var(--green)':'var(--red)'}}>
                  {fmt.n(cdata.macd_series.at(-1).macd,3)} / Signal {fmt.n(cdata.macd_series.at(-1).signal,3)}
                </span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Añadir click-to-chart en UniversoTable y MarketTrends**

En `UniversoTable`, donde se renderiza el símbolo (buscar `s.symbol` en la fila de la tabla), añadir `onClick`:

```jsx
<td className="sym" style={{cursor:'pointer'}} onClick={() => window._chartBus.emit(s.symbol)}>
  {s.symbol}
</td>
```

En `MarketTrends` (ya tiene botón `+ Analizar`), añadir también click en el símbolo:
```jsx
<span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',color:'var(--text)',cursor:'pointer'}}
      onClick={() => window._chartBus.emit(r.symbol)}>
  {r.symbol}
</span>
```

En `open_trades` / positions, donde aparece el símbolo de una posición abierta:
```jsx
<span className="pos-sym" style={{cursor:'pointer'}} onClick={() => window._chartBus.emit(t.symbol)}>
  {t.symbol}
</span>
```

- [ ] **Step 4: Actualizar QuickScan para aceptar prop `onSelect`**

Localizar `function QuickScan()` y modificar firma:
```javascript
function QuickScan({ onSelect, compact = false }) {
  // ...
  // En lugar de navigate, llamar onSelect si existe:
  function run() {
    if (!sym) return;
    if (onSelect) { onSelect(sym.toUpperCase()); setSym(''); return; }
    // comportamiento original
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add app/api/dashboard.py
git commit -m "feat(chart): collapsible SymbolChart + click-to-chart from any component + 6 periods"
```

---

## Task 6: Nuevos periodos en endpoint backend `/dashboard/symbol`

**Problema:** El endpoint solo acepta `intraday` y `daily`. Necesita `1h`, `4h`, `weekly`, `monthly`.

**Files:**
- Modify: `app/api/main.py` — función `dashboard_symbol_data` (línea ~741)

- [ ] **Step 1: Ampliar el endpoint para nuevos periodos**

Reemplazar el bloque de obtención de datos (actualmente líneas ~750-753):

```python
PERIOD_CONFIG = {
    "intraday": ("1 D",   "5 mins",  False),
    "1h":       ("5 D",   "1 hour",  False),
    "4h":       ("20 D",  "4 hours", False),
    "daily":    ("30 D",  "1 day",   False),
    "weekly":   ("180 D", "1 week",  False),
    "monthly":  ("730 D", "1 month", False),
}
duration, bar_size, _ = PERIOD_CONFIG.get(period, PERIOD_CONFIG["daily"])
df = data_layer.get_ohlcv(symbol, duration, bar_size, "dashboard_chart")
```

Y el bloque intraday extras (condición `if period == "intraday"`) mantenerlo igual.

- [ ] **Step 2: Test del endpoint**

```python
# tests/api/test_dashboard_symbol.py
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

def _make_df(n=30):
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "open": np.full(n, 100.0), "high": np.full(n, 105.0),
        "low": np.full(n, 95.0), "close": np.linspace(100, 110, n),
        "volume": np.full(n, 1_000_000),
    }, index=dates)

def test_period_1h_calls_correct_bar_size():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df()
        from app.api.main import app
        client = TestClient(app, headers={"X-Control-Key": "ci-test-key"})
        resp = client.get("/dashboard/symbol/AAPL?period=1h")
    assert resp.status_code == 200
    calls = mock_dl.return_value.get_ohlcv.call_args_list
    assert any("1 hour" in str(c) for c in calls)

def test_period_weekly_returns_bars():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df(52)
        from app.api.main import app
        client = TestClient(app, headers={"X-Control-Key": "ci-test-key"})
        resp = client.get("/dashboard/symbol/AAPL?period=weekly")
    assert resp.status_code == 200
    assert len(resp.json()["bars"]) == 52

def test_unknown_period_falls_back_to_daily():
    with patch("app.llm.agent.get_data_layer") as mock_dl:
        mock_dl.return_value.get_ohlcv.return_value = _make_df()
        from app.api.main import app
        client = TestClient(app, headers={"X-Control-Key": "ci-test-key"})
        resp = client.get("/dashboard/symbol/AAPL?period=bogus")
    assert resp.status_code == 200
    assert "bars" in resp.json()
```

- [ ] **Step 3: Ejecutar tests**

```bash
uv run pytest tests/api/test_dashboard_symbol.py -v
```

Esperado: 3 PASSED

- [ ] **Step 4: Commit**

```bash
git add app/api/main.py tests/api/test_dashboard_symbol.py
git commit -m "feat(api): add 1h/4h/weekly/monthly periods to dashboard/symbol endpoint"
```

---

## Task 7: QuickScan prominente + verificación de acceso IB

**Problema:** QuickScan está escondido en la barra de chips. No verifica si IB tiene acceso al símbolo antes de analizar.

**Files:**
- Modify: `app/api/dashboard.py` — header + QuickScan

- [ ] **Step 1: Mover QuickScan al header del dashboard**

Localizar el componente `Header` (busca `.header` o `function Header`) y añadir el QuickScan inline:

```jsx
// En el Header, añadir después del logo/badge:
<div className="qs-box" style={{flex:1,maxWidth:320}}>
  <input
    className="qs-input"
    placeholder="Buscar símbolo... (AAPL, TSLA)"
    value={qsSym}
    onChange={e => setQsSym(e.target.value.toUpperCase())}
    onKeyDown={e => e.key==='Enter' && runQS()}
    style={{width:'100%'}}
  />
  <button className="btn btn-primary" onClick={runQS} disabled={qsLoading}>
    {qsLoading ? '...' : '🔍'}
  </button>
</div>
```

El estado `qsSym`, `qsLoading` se maneja en el componente `App` y se pasa via props o Context.

- [ ] **Step 2: Añadir verificación de acceso IB antes de analizar**

Modificar `QuickScan` / `AnalyzeModal` para verificar acceso primero:

```javascript
async function verifyAccess(sym) {
  try {
    const res = await fetch(`/price/free/${sym}`);
    if (!res.ok) return { ok: false, reason: 'Sin acceso de mercado para ' + sym };
    const d = await res.json();
    if (d.error) return { ok: false, reason: d.error };
    return { ok: true, price: d.market_price };
  } catch(e) {
    return { ok: false, reason: 'No se pudo verificar: ' + e.message };
  }
}

// En runAnalysis (dentro de AnalyzeModal):
async function runAnalysis() {
  setPhase('checking');
  const access = await verifyAccess(symbol);
  if (!access.ok) {
    setErr(`🚫 ${access.reason}`);
    setPhase('error');
    return;
  }
  setPhase('analyzing');
  // ... resto del flujo existente
}
```

Añadir fase `'checking'` con mensaje "Verificando acceso a {symbol}...".

- [ ] **Step 3: Añadir input de símbolo libre al AnalyzeModal para símbolos arbitrarios**

En el dashboard, añadir botón "🔍 Analizar símbolo" en el header que abre `AnalyzeModal` con input libre:

```jsx
// En el header, botón que abre modal con input:
<button className="btn btn-primary" onClick={() => setAnalyzeTarget('__custom__')}>
  + Analizar símbolo
</button>

// AnalyzeModal acepta symbol='' como "modo custom":
function AnalyzeModal({ symbol: initSymbol, onClose }) {
  const [symbol, setSymbol] = useState(initSymbol || '');
  // Si symbol está vacío, mostrar input primero
  if (!symbol) return (
    <div ...modal wrapper...>
      <input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}
             placeholder="AAPL, TSLA..." onKeyDown={e=>e.key==='Enter'&&runAnalysis()} />
      <button onClick={runAnalysis}>Analizar</button>
    </div>
  );
  // ... resto del modal existente
}
```

- [ ] **Step 4: Commit**

```bash
git add app/api/dashboard.py
git commit -m "feat(ui): prominent QuickScan in header + IB access verification before analysis"
```

---

## Task 8: Deploy completo y verificación E2E

- [ ] **Step 1: Push a main y esperar CI**

```bash
git push origin main
```

Esperar que GitHub Actions complete los 3 jobs: `test`, `live`, `deploy`.

- [ ] **Step 2: Verificar deploy en Pi**

```bash
ssh aiutox-pi "sudo systemctl status ibkr-api.service --no-pager | tail -5"
```

- [ ] **Step 3: Ejecutar seed en Pi**

```bash
ssh aiutox-pi "cd /home/frankpach/ibkr-bot && .venv/bin/python scripts/seed_control_settings.py"
```

- [ ] **Step 4: E2E Playwright — Desktop**

```javascript
await page.setViewportSize({ width: 1440, height: 900 });
await page.goto('http://aiutox-pi:8088/dashboard');
// Verificar:
// 1. QuickScan visible en header
// 2. Sección gráfica con botón toggle
// 3. Fuentes legibles (>= 12px computed)
await page.screenshot({ path: 'e2e-desktop-v2.png', fullPage: true });

await page.goto('http://aiutox-pi:8088/control');
// Verificar:
// 1. Sidebar con "🤖 Modelos LLM"
// 2. Formularios RiskPanel pre-poblados
// 3. LLMPanel con dropdowns
await page.screenshot({ path: 'e2e-desktop-control-v2.png', fullPage: true });
```

- [ ] **Step 5: E2E Playwright — iPhone 13 Pro**

```javascript
await page.setViewportSize({ width: 390, height: 844 });
await page.goto('http://aiutox-pi:8088/dashboard');
// Verificar:
// 1. Sin overflow horizontal
// 2. Sidebar de /control colapsa a barra horizontal
// 3. Cards apilados verticalmente
await page.screenshot({ path: 'e2e-iphone-v2.png', fullPage: true });
```

- [ ] **Step 6: Verificar font sizes mínimos**

```javascript
const minFont = await page.evaluate(() => {
  const sizes = Array.from(document.querySelectorAll('*'))
    .map(el => parseFloat(window.getComputedStyle(el).fontSize))
    .filter(s => s > 0 && s < 100);
  return Math.min(...sizes);
});
console.assert(minFont >= 11, `Font too small: ${minFont}px`);
```

---

## Notas de implementación

### Orden recomendado de ejecución
1. Task 1 (seed DB) — prerequisito para Tasks 2 y 3
2. Task 6 (endpoint periodos) — prerequisito para Task 5
3. Task 4 (CSS) — independiente, bajo riesgo
4. Task 2 (LLM panel control) — requiere Task 1
5. Task 3 (agent.py) — requiere Task 1
6. Task 5 (SymbolChart) — requiere Task 6
7. Task 7 (QuickScan) — puede ir en paralelo con 5
8. Task 8 (deploy E2E) — siempre al final

### Riesgos
- `get_ohlcv` con `"4 hours"` / `"1 week"` puede no estar soportado por IB en todos los instrumentos — el endpoint debe manejar `None` silenciosamente y retornar `{"bars": []}`.
- El seed script es idempotente (no sobreescribe existentes) — seguro correrlo varias veces.
- `window._chartBus` es un patrón simple de event bus sin React Context — funciona pero no sobrevive HMR. Para producción sin build step es suficiente.
