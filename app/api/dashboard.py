"""
IBKR AI Trader — React dashboard v2.
Served as HTML from /dashboard. All data fetched client-side from /dashboard/data.
No build step — React + Tailwind via CDN.
"""


def render_dashboard_html() -> str:
    return r'''<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>IBKR AI Trader</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Fira+Code:wght@300;400;500&family=Barlow+Condensed:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{
      --bg:#06090F;--surface:#0C1421;--surface2:#111D2E;--border:#1E2D42;
      --text:#E2E8F0;--muted:#94A3B8;--dim:#64748B;--dimmer:#334155;
      --green:#10B981;--red:#F43F5E;--blue:#38BDF8;--amber:#FBBF24;--purple:#A78BFA;
      --green-bg:rgba(16,185,129,.12);--red-bg:rgba(244,63,94,.1);
      --blue-bg:rgba(56,189,248,.1);--amber-bg:rgba(251,191,36,.08);
    }
    [data-theme="light"]{
      --bg:#F1F5F9;--surface:#FFFFFF;--surface2:#F8FAFC;--border:#E2E8F0;
      --text:#1E293B;--muted:#475569;--dim:#94A3B8;--dimmer:#CBD5E1;
      --green:#059669;--red:#DC2626;--blue:#0284C7;--amber:#D97706;
      --green-bg:rgba(5,150,105,.1);--red-bg:rgba(220,38,38,.08);
      --blue-bg:rgba(2,132,199,.1);--amber-bg:rgba(217,119,6,.08);
    }
    body{background:var(--bg);color:var(--text);font-family:"Barlow Condensed",sans-serif;font-size:14px;min-height:100vh;-webkit-font-smoothing:antialiased}
    ::-webkit-scrollbar{width:3px;height:3px}
    ::-webkit-scrollbar-track{background:var(--bg)}
    ::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    .pulse{animation:pulse 2s ease-in-out infinite}
    .fade-up{animation:fadeUp .35s ease both}

    /* Layout */
    .page{max-width:1280px;margin:0 auto;padding:10px;display:flex;flex-direction:column;gap:10px}
    .row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
    .row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
    .row-2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    @media(max-width:960px){.row-4{grid-template-columns:repeat(2,1fr)}.row-3{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:640px){.row-2,.row-3,.row-4{grid-template-columns:1fr}}

    /* Cards */
    .card{background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden}
    .ch{background:var(--surface2);border-bottom:1px solid var(--border);padding:8px 12px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
    .ct{font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
    .cb{padding:12px}

    /* Stat card */
    .sc{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;position:relative;overflow:hidden}
    .sl{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-bottom:4px}
    .sv{font-family:"Bebas Neue",cursive;font-size:2rem;line-height:1.05}
    .ss{font-family:"Fira Code",monospace;font-size:.78rem;color:var(--muted);margin-top:3px}
    .green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.amber{color:var(--amber)}.purple{color:var(--purple)}

    /* Tags */
    .tag{display:inline-block;padding:2px 7px;border-radius:3px;font-size:.72rem;font-family:"Fira Code",monospace;font-weight:500;border:1px solid}
    .tag-buy{background:var(--green-bg);color:var(--green);border-color:rgba(16,185,129,.3)}
    .tag-sell{background:var(--red-bg);color:var(--red);border-color:rgba(244,63,94,.3)}
    .tag-overnight{background:var(--amber-bg);color:var(--amber);border-color:rgba(251,191,36,.25)}
    .tag-neutral{background:rgba(100,116,139,.1);color:var(--dim);border-color:var(--border)}

    /* Position card */
    .pos-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:8px}
    .pos-card:last-child{margin-bottom:0}
    .pos-row{display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;margin-bottom:6px}
    .pos-sym{font-family:"Bebas Neue",cursive;font-size:1.2rem;letter-spacing:.06em;color:var(--text)}
    .pos-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:4px 8px;font-family:"Fira Code",monospace;font-size:.8rem;margin:8px 0}
    @media(min-width:640px){.pos-grid{grid-template-columns:repeat(4,1fr)}}
    .pos-k{color:var(--muted)}.pos-v{color:var(--text);font-weight:500}
    .pos-pnl{font-family:"Fira Code",monospace;font-size:.9rem;font-weight:500}

    /* Meters */
    .meter{height:6px;border-radius:3px;overflow:hidden;background:rgba(255,255,255,.05)}
    .meter-fill{height:100%;border-radius:3px;transition:width .5s ease}
    .rr-track{height:6px;border-radius:3px;overflow:visible;position:relative;background:linear-gradient(to right,rgba(244,63,94,.35) 0%,rgba(251,191,36,.25) 50%,rgba(16,185,129,.35) 100%);margin:6px 0}
    .rr-pin{position:absolute;top:-4px;width:4px;height:14px;background:var(--text);border-radius:2px;transform:translateX(-50%);transition:left .4s ease}

    /* Tabs */
    .tabs{display:flex;gap:2px;background:var(--bg);border-radius:5px;padding:2px}
    .tab{padding:4px 10px;border-radius:4px;font-family:"Fira Code",monospace;font-size:.75rem;color:var(--dim);cursor:pointer;border:none;background:transparent;white-space:nowrap}
    .tab.on{background:var(--surface2);color:var(--text);border:1px solid var(--border)}

    /* Buttons */
    .btn{padding:4px 10px;border-radius:5px;font-family:"Barlow Condensed",sans-serif;font-size:.78rem;font-weight:600;letter-spacing:.04em;cursor:pointer;background:var(--surface2);border:1px solid var(--border);color:var(--muted)}
    .btn-primary{background:var(--blue-bg);color:var(--blue);border-color:rgba(56,189,248,.3)}
    .btn-danger{background:var(--red-bg);color:var(--red);border-color:rgba(244,63,94,.3)}
    .btn-amber{background:var(--amber-bg);color:var(--amber);border-color:rgba(251,191,36,.25)}
    .btn:disabled{opacity:.4;cursor:not-allowed}

    /* Header */
    .header{background:var(--surface);border-bottom:1px solid var(--border);padding:8px 12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;position:sticky;top:0;z-index:20}
    .logo{font-family:"Bebas Neue",cursive;font-size:1.25rem;letter-spacing:.1em;color:var(--text)}
    .badge{padding:2px 8px;border-radius:4px;font-family:"Fira Code",monospace;font-size:.65rem}
    .badge-paper{background:var(--green-bg);color:var(--green);border:1px solid rgba(16,185,129,.3)}
    .badge-live{background:var(--amber-bg);color:var(--amber);border:1px solid rgba(251,191,36,.3)}
    .theme-btn{background:var(--surface2);border:1px solid var(--border);color:var(--dim);padding:4px 10px;border-radius:20px;font-size:.72rem;cursor:pointer;display:flex;align-items:center;gap:5px;font-family:"Barlow Condensed",sans-serif;font-weight:600}

    /* Market context bar */
    .mkt-bar{padding:6px 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:var(--surface2);border-bottom:1px solid var(--border);font-family:"Fira Code",monospace;font-size:.75rem}
    .mkt-chip{display:flex;align-items:center;gap:4px;padding:2px 7px;border-radius:4px;background:var(--bg);border:1px solid var(--border)}

    /* System bar */
    .sys-bar{padding:6px 12px;display:flex;align-items:center;gap:12px;font-family:"Fira Code",monospace;font-size:.78rem;background:var(--surface2);border-bottom:1px solid var(--border);flex-wrap:wrap}

    /* Quick scan */
    .qs-box{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
    .qs-input{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:5px;padding:6px 10px;font-size:.82rem;font-family:"Fira Code",monospace;width:150px}

    /* Empty */
    .empty{color:var(--dimmer);font-family:"Fira Code",monospace;font-size:.82rem;padding:1.4rem 0;text-align:center;letter-spacing:.04em}

    /* Timeline */
    .tl{display:flex;flex-direction:column;gap:0}
    .tl-item{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid var(--border);font-family:"Fira Code",monospace;font-size:.8rem}
    .tl-item:last-child{border-bottom:none}
    .tl-dot{width:6px;height:6px;border-radius:50%;margin-top:5px;flex-shrink:0}
    .tl-time{min-width:44px;color:var(--dim);font-size:.72rem}

    /* Table */
    table{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.8rem}
    th{color:var(--dim);font-weight:500;padding:6px 8px;text-align:left;border-bottom:1px solid var(--border)}
    td{padding:6px 8px;border-bottom:1px solid var(--border);color:var(--muted)}
    td.sym{color:var(--text);font-weight:500}
    tr:last-child td{border-bottom:none}

    /* Footer */
    .footer{text-align:center;color:var(--dimmer);font-family:"Fira Code",monospace;font-size:.62rem;padding:12px}

    /* Scroll container */
    .scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch}
    .table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}

    /* ─── Mobile 480px (iPhone 13 Pro 390px) ─────── */
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
      .pos-grid{font-size:.78rem}
      table{min-width:480px}
      .table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -6px;padding:0 6px}
      .hide-mobile{display:none!important}
      .mkt-bar{font-size:.78rem;gap:6px}
      .sys-bar{font-size:.8rem}
    }
  </style>
</head>
<body>
  <div id="root"></div>
  <script>
    (function(){
      var t = localStorage.getItem('theme') || 'dark';
      document.documentElement.setAttribute('data-theme', t);
    })();
  </script>
  <script type="text/babel">
    const { useState, useEffect, useRef, useCallback, useMemo } = React;

    /* Formatting */
    const fmt = {
      usd: v => v == null ? '—' : '$' + parseFloat(v).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}),
      pct: v => v == null ? '—' : (parseFloat(v) >= 0 ? '+' : '') + parseFloat(v).toFixed(2) + '%',
      n: (v, d=1) => v == null ? '—' : parseFloat(v).toFixed(d),
      time: v => v ? String(v).slice(11,16) : '—',
      date: v => v ? String(v).slice(2,16).replace('T',' ') : '—',
    };

    // Global chart symbol bus — lets any component trigger the chart
    window._chartBus = window._chartBus || { listeners: [], emit(sym) { this.listeners.forEach(fn => fn(sym)); } };
    function useChartBus(cb) {
      React.useEffect(() => {
        window._chartBus.listeners.push(cb);
        return () => { window._chartBus.listeners = window._chartBus.listeners.filter(f => f !== cb); };
      }, [cb]);
    }

    function toggleTheme() {
      const h = document.documentElement;
      const dark = h.getAttribute('data-theme') === 'dark';
      h.setAttribute('data-theme', dark ? 'light' : 'dark');
      localStorage.setItem('theme', dark ? 'light' : 'dark');
    }

    async function closePosition(tradeId) {
      if (!confirm('Cerrar posicion?')) return;
      try {
        const res = await fetch('/orders/close/id/' + tradeId, {method:'POST'});
        const d = await res.json();
        if (d.message) alert(d.message); else if (d.detail) alert('Error: ' + d.detail);
      } catch(e) { alert('Error de red: ' + e.message); }
    }

    /* ───────── COMPONENTS ───────── */

    function MarketContextBar({ data }) {
      const ctx = data?.status?.market_context || {};
      const chips = ['SPY','QQQ','IWM','VIX'];
      return (
        <div className="mkt-bar">
          <span style={{color:'var(--dim)',fontSize:'.6rem',textTransform:'uppercase',letterSpacing:'.1em'}}>Mercado</span>
          {chips.map(sym => {
            const c = ctx[sym];
            if (!c) return null;
            const col = sym === 'VIX' ? (c.change_pct >= 0 ? 'var(--red)' : 'var(--green)') : (c.change_pct >= 0 ? 'var(--green)' : 'var(--red)');
            return (
              <div key={sym} className="mkt-chip">
                <span style={{color:'var(--text)',fontWeight:600}}>{sym}</span>
                <span style={{color:col}}>{c.change_pct >= 0 ? '+' : ''}{fmt.n(c.change_pct)}%</span>
                {sym !== 'VIX' && c.volume_ratio > 0 && <span style={{color:'var(--blue)',fontSize:'.55rem'}}>RVOL {fmt.n(c.volume_ratio,1)}x</span>}
              </div>
            );
          })}
        </div>
      );
    }

    function SystemStatusBar({ data }) {
      const st = data?.status || {};
      const ib = data?.ib_connected;
      const mode = (st.mode || 'paper').toUpperCase();
      const paused = st.paused;
      const pnl = st.intraday_pnl_usd != null ? st.intraday_pnl_usd : st.daily_pnl_usd;
      const port = st.ib_port || '—';
      const dd = st.drawdown_pct || 0;
      return (
        <div className="sys-bar">
          <span style={{width:7,height:7,borderRadius:'50%',background: ib ? 'var(--green)' : 'var(--red)',boxShadow: ib ? '0 0 5px var(--green)' : 'none'}} className={ib?'pulse':''}></span>
          <span style={{color:mode==='LIVE'?'var(--amber)':'var(--green)',fontWeight:700}}>{mode}</span>
          <span style={{color:'var(--dim)'}}>| Puerto {port}</span>
          <span style={{color:paused?'var(--amber)':'var(--green)'}}>{paused ? 'Pausado' : 'Activo'}</span>
          <span style={{color:pnl>=0?'var(--green)':'var(--red)'}}>| P&L {fmt.usd(pnl)}</span>
          <span style={{color:dd>5?'var(--red)':dd>2?'var(--amber)':'var(--green)'}}>| DD {fmt.n(dd)}%</span>
          <span style={{color:ib?'var(--green)':'var(--red)',marginLeft:'auto'}}>IB {ib ? 'ON' : 'OFF'}</span>
        </div>
      );
    }

    function Header({ data, onTogglePause, onRefresh, interval, onTick }) {
      const st = data?.status || {};
      const isLive = (st.mode || 'paper').toUpperCase() === 'LIVE';
      const ib = data?.ib_connected;
      const [isDark, setIsDark] = useState(() => (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark');
      const path = window.location.pathname;
      const nav = [
        {href:'/dashboard', label:'Dashboard'},
        {href:'/control', label:'Control'},
        {href:'/reports', label:'Reportes'},
        {href:'/docs', label:'API Docs'},
      ];
      return (
        <div className="header">
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span style={{display:'inline-block',width:8,height:8,borderRadius:'50%',background:ib?'var(--green)':'var(--red)',boxShadow:ib?'0 0 6px var(--green)':'none'}} className={ib?'pulse':''}></span>
            <span className="logo">IBKR AI Trader</span>
            <span className={'badge ' + (isLive ? 'badge-live' : 'badge-paper')}>{isLive ? 'LIVE' : 'PAPER'}</span>
            {st.paused && <span className="tag tag-neutral">PAUSADO</span>}
          </div>
          <nav style={{display:'flex',alignItems:'center',gap:2}}>
            {nav.map(({href,label})=>{
              const active = path === href || (href !== '/dashboard' && path.startsWith(href));
              return (
                <a key={href} href={href} style={{fontFamily:'"Barlow Condensed",sans-serif',fontWeight:active?600:500,fontSize:'.8rem',letterSpacing:'.04em',color:active?'var(--text)':'var(--dim)',textDecoration:'none',padding:'4px 10px',borderRadius:5,background:active?'var(--surface2)':'transparent',border:active?'1px solid var(--border)':'1px solid transparent',transition:'color .15s,background .15s'}}>{label}</a>
              );
            })}
          </nav>
          <div style={{display:'flex',alignItems:'center',gap:6}}>
            <button className="btn btn-amber" disabled={!ib} onClick={onTogglePause}>Pausar</button>
            <button className="btn" onClick={onRefresh}>↻</button>
            <button className="theme-btn" onClick={()=>{toggleTheme();setIsDark(d=>!d);}}>
              <span>{isDark ? '☀' : '☾'}</span><span>{isDark ? 'Claro' : 'Oscuro'}</span>
            </button>
            <Countdown total={interval} onTick={onTick} />
          </div>
        </div>
      );
    }

    function Countdown({ total, onTick }) {
      const [rem, setRem] = useState(total);
      useEffect(() => {
        setRem(total);
        const t = setInterval(() => {
          setRem(r => { if (r <= 1) { onTick(); return total; } return r - 1; });
        }, 1000);
        return () => clearInterval(t);
      }, [total, onTick]);
      const pct = (rem / total) * 100;
      const circ = 2 * Math.PI * 7;
      return (
        <div style={{display:'flex',alignItems:'center',gap:4}}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <circle cx="9" cy="9" r="7" fill="none" stroke="var(--border)" strokeWidth="1.5"/>
            <circle cx="9" cy="9" r="7" fill="none" stroke="var(--blue)" strokeWidth="1.5" strokeDasharray={circ} strokeDashoffset={circ * (1 - pct/100)} style={{transform:'rotate(-90deg)',transformOrigin:'center',transition:'stroke-dashoffset 1s linear'}}/></svg>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)'}}>{rem}s</span>
        </div>
      );
    }

    function QuickScan() {
      const [sym, setSym] = useState('');
      const [loading, setLoading] = useState(false);
      async function analyze() {
        if (!sym.trim()) return;
        setLoading(true);
        try {
          const s = sym.trim().toUpperCase();
          await fetch('/candidate-analysis/' + s, {method:'GET'});
          alert('Analisis solicitado para ' + s + '. Revisa Telegram o /reports para el resultado.');
        } catch(e) { alert('Error solicitando analisis'); }
        setLoading(false);
      }
      return (
        <div className="qs-box">
          <span className="ct">Quick Scan</span>
          <input className="qs-input" placeholder="SYMBOL" value={sym} onChange={e=>setSym(e.target.value.toUpperCase())} onKeyDown={e=>e.key==='Enter'&&analyze()}/>
          <button className="btn btn-primary" disabled={loading||!sym.trim()} onClick={analyze}>{loading?'...':'Analizar'}</button>
        </div>
      );
    }

    function StatCards({ data }) {
      const st = data?.status || {};
      const acct = data?.latest_account || {};
      const netLiq = acct.net_liquidation || st.operating_capital || st.simulated_capital || 0;
      const buyPow = acct.buying_power || st.operating_capital || 0;
      const openCount = data?.open_trades?.length || 0;
      const intraday = st.intraday_pnl_usd != null ? st.intraday_pnl_usd : (st.daily_pnl_usd || 0);
      const realized = st.realized_pnl_usd || 0;
      const unrealized = st.unrealized_pnl_usd || 0;
      const dd = st.drawdown_pct || 0;
      const maxDd = st.max_drawdown_pct || 0;
      const comm = st.daily_commissions_usd || 0;
      const overnight = st.overnight_count || 0;
      return (
        <div className="row-4">
          <div className="sc fade-up">
            <div className="sl">Net Liquidation</div>
            <div className="sv blue">{fmt.usd(netLiq)}</div>
            <div className="ss">{st.ib_data_live ? 'IBKR snapshot · hoy' : 'ultimo snapshot'}</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">P&L Intradia</div>
            <div className={'sv ' + (intraday >= 0 ? 'green' : 'red')}>{fmt.usd(intraday)}</div>
            <div className="ss" style={{display:'flex',gap:8}}>
              <span style={{color:'var(--green)'}}>R {fmt.usd(realized)}</span>
              <span style={{color:unrealized>=0?'var(--green)':'var(--red)'}}>UR {fmt.usd(unrealized)}</span>
            </div>
          </div>
          <div className="sc fade-up">
            <div className="sl">Buying Power</div>
            <div className="sv" style={{color:'var(--text)'}}>{fmt.usd(buyPow)}</div>
            <div className="ss">disponible</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">Drawdown / Peak</div>
            <div className="sv" style={{color: dd > 5 ? 'var(--red)' : dd > 2 ? 'var(--amber)' : 'var(--green)'}}>{fmt.n(dd)}%</div>
            <div className="ss">max {fmt.n(maxDd)}% · peak {fmt.usd(st.peak_net_liq)}</div>
            <DrawdownBar pct={dd} />
          </div>
          <div className="sc fade-up">
            <div className="sl">Posiciones</div>
            <div className="sv" style={{color:'var(--text)'}}>{openCount}<span style={{fontSize:'1rem',color:'var(--dim)'}}>/3</span></div>
            <div className="ss">{overnight > 0 && <span className="tag tag-overnight" style={{marginRight:6}}>ON {overnight}</span>}{openCount < 3 ? (3-openCount)+' libre' : 'max'}</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">Comisiones Hoy</div>
            <div className="sv" style={{color:'var(--text)'}}>{fmt.usd(comm)}</div>
            <div className="ss">semanal {fmt.usd(st.weekly_commissions_usd)}</div>
          </div>
        </div>
      );
    }

    function DrawdownBar({ pct }) {
      const p = Math.min(Math.abs(pct || 0), 20);
      const width = (p / 20) * 100;
      const color = p < 5 ? 'var(--green)' : p < 10 ? 'var(--amber)' : 'var(--red)';
      return (
        <div style={{height:4,borderRadius:2,overflow:'hidden',background:'rgba(255,255,255,.06)',marginTop:6}}>
          <div style={{height:'100%',width:width+'%',background:color,borderRadius:2,transition:'width .6s ease'}}/></div>
      );
    }

    function RiskThermometer({ data }) {
      const trades = data?.open_trades || [];
      const snaps = data?.position_snapshots || [];
      const capital = data?.status?.operating_capital || 1;
      let totalRisk = 0;
      trades.forEach(t => {
        const entry = parseFloat(t.entry_price || t.entry_fill_price || 0);
        const sl = parseFloat(t.stop_loss_price || 0);
        const qty = parseFloat(t.quantity || 0);
        if (entry && sl && qty) totalRisk += Math.abs(entry - sl) * qty;
      });
      const riskPct = Math.min((totalRisk / capital) * 100, 100);
      const color = riskPct > 3 ? 'var(--red)' : riskPct > 1.5 ? 'var(--amber)' : 'var(--green)';
      return (
        <div className="card fade-up">
          <div className="ch"><span className="ct">Riesgo Acumulado</span><span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'var(--dim)'}}>{fmt.usd(totalRisk)} / {fmt.n(riskPct)}% capital</span></div>
          <div className="cb">
            <div style={{height:10,borderRadius:5,overflow:'hidden',background:'rgba(255,255,255,.06)'}}>
              <div style={{height:'100%',width:riskPct+'%',background:color,borderRadius:5,transition:'width .5s ease'}}/></div>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:4,fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)'}}>
              <span>0%</span><span>1.5%</span><span>3%</span><span>5%+</span>
            </div>
          </div>
        </div>
      );
    }

    function RRBar({ trade, snapshots }) {
      const snap = (snapshots||[]).find(s=>s.trade_id===(trade.trade_id||trade.id))||{};
      const cur = parseFloat(snap.current_price||trade.current_price||trade.entry_price||0);
      const sl = parseFloat(trade.stop_loss_price||0);
      const tp = parseFloat(trade.take_profit_price||0);
      let pin = 50;
      if (tp > sl) {
        const raw = trade.action==='BUY' ? (cur-sl)/(tp-sl) : (sl-cur)/(sl-tp);
        pin = Math.max(0,Math.min(100,raw*100));
      }
      return (
        <div style={{margin:'6px 0'}}>
          <div className="rr-track"><div className="rr-pin" style={{left:pin+'%'}}/></div>
          <div style={{display:'flex',justifyContent:'space-between',fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)',marginTop:2}}>
            <span style={{color:'var(--red)'}}>SL {fmt.usd(sl)}</span>
            <span style={{color:'var(--blue)'}}>ACT {fmt.usd(cur)}</span>
            <span style={{color:'var(--green)'}}>TP {fmt.usd(tp)}</span>
          </div>
        </div>
      );
    }

    function OpenPositions({ data }) {
      const trades = data?.open_trades || [];
      const snaps = data?.position_snapshots || [];
      const ib = data?.ib_connected;
      const overnightSet = new Set(data?.status?.overnight_symbols || []);
      const cards = trades.map((t,i)=>{
        const snap = snaps.find(s=>s.trade_id===(t.trade_id||t.id))||{};
        const pnlUsd = parseFloat(snap.pnl_usd!=null?snap.pnl_usd:(t.pnl_usd||0));
        const pnlPct = parseFloat(snap.pnl_pct!=null?snap.pnl_pct:(t.pnl_pct||0));
        const cur = snap.current_price||t.current_price||t.entry_price;
        const entry = parseFloat(t.entry_price||t.entry_fill_price||0);
        const sl = parseFloat(t.stop_loss_price||0);
        const qty = parseFloat(t.quantity||0);
        const distSl = entry && sl ? Math.abs((cur-sl)/sl*100) : 0;
        const risk = entry && sl ? Math.abs(entry-sl)*qty : 0;
        const r = entry && sl && Math.abs(entry-sl)>0.0001 ? (cur-entry)/(entry-sl) : 0;
        return (
          <div key={t.trade_id||t.id||i} className="pos-card fade-up">
            <div className="pos-row">
              <div style={{display:'flex',alignItems:'center',gap:7,flexWrap:'wrap'}}>
                <span className="pos-sym" style={{cursor:'pointer'}} onClick={()=>window._chartBus.emit(t.symbol)}>{t.symbol}</span>
                <span className={'tag ' + (t.action==='BUY'?'tag-buy':'tag-sell')}>{t.action}</span>
                <span className="tag tag-neutral">{t.signal_strength||'—'}</span>
                {overnightSet.has(t.symbol) && <span className="tag tag-overnight">OVERNIGHT</span>}
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span className={'pos-pnl '+(pnlUsd>=0?'green':'red')}>{fmt.usd(pnlUsd)} <span style={{fontSize:'.72rem'}}>{fmt.pct(pnlPct*100)}</span></span>
                <button className="btn btn-danger" style={{fontSize:'.65rem',padding:'3px 8px'}} disabled={!ib} onClick={()=>closePosition(t.trade_id||t.id)}>Cerrar</button>
              </div>
            </div>
            <div className="pos-grid">
              <div><span className="pos-k">SIZE </span><span className="pos-v">{qty} u</span></div>
              <div><span className="pos-k">COSTO </span><span className="pos-v">{fmt.usd(entry)}</span></div>
              <div><span className="pos-k">ACTUAL </span><span className="pos-v">{fmt.usd(cur)}</span></div>
              <div><span className="pos-k">DIST SL </span><span className="pos-v">{fmt.n(distSl)}%</span></div>
              <div><span className="pos-k">RIESGO $ </span><span className="pos-v">{fmt.usd(risk)}</span></div>
              <div><span className="pos-k">R actual </span><span className="pos-v" style={{color:r>=0?'var(--green)':'var(--red)'}}>{fmt.n(r,2)}R</span></div>
            </div>
            <RRBar trade={t} snapshots={snaps} />
          </div>
        );
      });
      while (cards.length < 3) {
        cards.push(
          <div key={'slot-'+cards.length} style={{background:'var(--surface2)',border:'1px dashed var(--border)',borderRadius:8,padding:14,textAlign:'center',fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--dimmer)',marginBottom:cards.length<2?8:0}}>
            Slot disponible — esperando senal STRONG
          </div>
        );
      }
      return <div>{cards}</div>;
    }

    function EquityDrawdownChart({ history }) {
      if (!history || history.length < 2) return <div className="empty">// sin historial de cuenta</div>;
      const W=420, H=160, padT=16, padB=20;
      const vals = history.map(h=>parseFloat(h.net_liquidation||0));
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const range = max-min||1;
      const step = W/(vals.length-1||1);
      // Peak and drawdown series
      let peak = vals[0];
      const ddPts = [];
      const eqPts = [];
      vals.forEach((v,i)=>{
        if (v>peak) peak=v;
        const x = i*step;
        const y = padT+((max-v)/range)*(H-padT-padB);
        eqPts.push(x+','+y);
        const ddY = padT+((max-(peak-v))/range)*(H-padT-padB);
        ddPts.push(x+','+ddY);
      });
      const total = vals[vals.length-1]-vals[0];
      return (
        <div>
          <div style={{overflow:'hidden',borderRadius:4,height:H}}>
            <svg width="100%" height={H} viewBox={'0 0 '+W+' '+H} preserveAspectRatio="none">
              <defs>
                <linearGradient id="eqG" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38BDF8" stopOpacity=".22"/>
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity="0"/>
                </linearGradient>
                <linearGradient id="ddG" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F43F5E" stopOpacity=".15"/>
                  <stop offset="100%" stopColor="#F43F5E" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <polyline points={eqPts.join(' ')} fill="none" stroke="#38BDF8" strokeWidth="2"/>
              <polygon points={eqPts.join(' ')+' '+W+','+H+' 0,'+H} fill="url(#eqG)"/>
              {/* Drawdown area under peak */}
              <polygon points={eqPts.map((p,i)=>{const [x]=p.split(',');const py=padT+((max-vals[i])/range)*(H-padT-padB);return x+','+py;}).join(' ')+' '+W+','+H+' 0,'+H} fill="url(#ddG)"/>
              <text x="3" y="13" fill="var(--dimmer)" fontSize="9" fontFamily="monospace">{fmt.usd(vals[vals.length-1])} · {history.length}d</text>
            </svg>
          </div>
          <div style={{display:'flex',gap:10,marginTop:6,fontFamily:'"Fira Code",monospace',fontSize:'.65rem'}}>
            <span style={{color:'var(--blue)'}}>━ equity</span>
            <span style={{color:'var(--red)'}}>━ drawdown</span>
            <span style={{marginLeft:'auto',color:total>=0?'var(--green)':'var(--red)'}}>{total>=0?'+':''}{fmt.usd(total)}</span>
          </div>
        </div>
      );
    }

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

      const chips = useMemo(() => {
        const openSyms = (data?.open_trades||[]).map(t => t.symbol);
        const uniSyms = (data?.symbols_universe||[]).map(s => s.symbol);
        const all = [...new Set([...openSyms, ...uniSyms])].slice(0, 12);
        return { all, open: new Set(openSyms) };
      }, [data]);

      const handleBus = useCallback((sym) => { setOpen(true); selectSym(sym); }, [tab]);
      useChartBus(handleBus);

      const PERIODS = [
        ['intraday','Hoy 5m'],['1h','1h'],['4h','4h'],
        ['daily','30D'],['weekly','1W'],['monthly','3M'],
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
        const bg = isDark ? '#0C1421' : '#FFFFFF'; const text = isDark ? '#94A3B8' : '#475569'; const grid = isDark ? '#1E2D42' : '#E2E8F0';
        const chart = LightweightCharts.createChart(chartRef.current, {
          layout:{background:{color:bg},textColor:text},
          grid:{vertLines:{color:grid},horzLines:{color:grid}},
          crosshair:{mode:LightweightCharts.CrosshairMode.Normal},
          rightPriceScale:{borderColor:grid},
          timeScale:{borderColor:grid,timeVisible:false},
          width:chartRef.current.clientWidth, height:260,
        });
        tvRef.current = chart;
        const bars = cdata.bars;
        const candle = chart.addCandlestickSeries({upColor:'#10B981',downColor:'#F43F5E',borderUpColor:'#10B981',borderDownColor:'#F43F5E',wickUpColor:'#10B981',wickDownColor:'#F43F5E'});
        candle.setData(bars.map(b=>({time:b.time,open:b.open,high:b.high,low:b.low,close:b.close})));
        const trade = (data?.open_trades||[]).find(t=>t.symbol===selected);
        if (trade && bars.length > 0) {
          [[trade.entry_price,'#FBBF24'],[trade.stop_loss_price,'#F43F5E'],[trade.take_profit_price,'#10B981']].forEach(([price,color])=>{
            if (price == null) return;
            const s = chart.addLineSeries({color,lineWidth:1,lineStyle:LightweightCharts.LineStyle.LargeDashed});
            s.setData(bars.map(b=>({time:b.time,value:parseFloat(price)})));
          });
        }
        if (inds.volume) {
          const vol = chart.addHistogramSeries({priceFormat:{type:'volume'},priceScaleId:'vol',color:'#38BDF840'});
          chart.priceScale('vol').applyOptions({scaleMargins:{top:.82,bottom:0}});
          vol.setData(bars.map(b=>({time:b.time,value:b.volume,color:b.close>=b.open?'#10B98140':'#F43F5E40'})));
        }
        if (inds.vwap && cdata.vwap_series?.length){const s=chart.addLineSeries({color:'#A78BFA',lineWidth:1});s.setData(cdata.vwap_series);}
        if (inds.ema9 && cdata.ema9_series?.length){const s=chart.addLineSeries({color:'#FBBF24',lineWidth:1});s.setData(cdata.ema9_series);}
        if (inds.ema20 && cdata.ema20_series?.length){const s=chart.addLineSeries({color:'#38BDF8',lineWidth:1});s.setData(cdata.ema20_series);}
        if (inds.boll && cdata.boll_series?.length){
          const u=chart.addLineSeries({color:'#A78BFA50',lineWidth:1});u.setData(cdata.boll_series.map(b=>({time:b.time,value:b.upper})));
          const m=chart.addLineSeries({color:'#A78BFA80',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed});m.setData(cdata.boll_series.map(b=>({time:b.time,value:b.middle})));
          const l=chart.addLineSeries({color:'#A78BFA50',lineWidth:1});l.setData(cdata.boll_series.map(b=>({time:b.time,value:b.lower})));
        }
        chart.timeScale().fitContent();
        const ro = new ResizeObserver(()=>{if(chartRef.current) chart.applyOptions({width:chartRef.current.clientWidth});});
        ro.observe(chartRef.current);
        return ()=>ro.disconnect();
      }, [cdata, inds]);

      const toggle = k => setInds(p=>({...p,[k]:!p[k]}));

      return (
        <div className="card fade-up">
          <div className="ch" style={{cursor:'pointer'}} onClick={()=>setOpen(o=>!o)}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:'1rem',lineHeight:1}}>{open?'▾':'▸'}</span>
              <span className="ct">📈 Gráfica</span>
              {selected && <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',color:'var(--blue)',marginLeft:4}}>{selected}</span>}
            </div>
            {!open && <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.75rem',color:'var(--dim)'}}>
              {chips.all.length} símbolos — click para expandir
            </span>}
          </div>
          {open && (
            <>
              <div style={{display:'flex',gap:6,flexWrap:'wrap',padding:'8px 12px',borderBottom:'1px solid var(--border)',alignItems:'center',background:'var(--surface2)'}}>
                {chips.all.map(sym=>(
                  <button key={sym} onClick={e=>{e.stopPropagation();selectSym(sym);}}
                    style={{padding:'3px 10px',borderRadius:12,fontFamily:'"Fira Code",monospace',fontSize:'.78rem',cursor:'pointer',
                      border:'1px solid '+(selected===sym?'rgba(56,189,248,.35)':'var(--border)'),
                      background:selected===sym?'var(--blue-bg)':'transparent',
                      color:selected===sym?'var(--blue)':'var(--muted)',position:'relative'}}>
                    {sym}
                    {chips.open.has(sym) && <span style={{position:'absolute',top:-3,right:-3,width:6,height:6,borderRadius:'50%',background:'var(--amber)'}}/>}
                  </button>
                ))}
              </div>
              <div className="ch">
                <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}>
                  <span className="ct">{selected||'Símbolo'}</span>
                  {cdata?.atr!=null && <span className="tag tag-neutral">ATR {fmt.n(cdata.atr,2)}</span>}
                  {cdata?.volume_relative!=null && <span className="tag tag-neutral">RVOL {fmt.n(cdata.volume_relative,1)}x</span>}
                  {['volume','vwap','ema9','ema20','boll','rsi','macd'].map(ind=>(
                    <button key={ind} onClick={()=>toggle(ind)}
                      style={{padding:'2px 7px',borderRadius:3,fontFamily:'"Fira Code",monospace',fontSize:'.72rem',cursor:'pointer',
                        background:inds[ind]?'var(--blue-bg)':'transparent',color:inds[ind]?'var(--blue)':'var(--dim)',
                        border:`1px solid ${inds[ind]?'rgba(56,189,248,.3)':'var(--border)'}`}}>
                      {ind.toUpperCase()}
                    </button>
                  ))}
                </div>
                <div className="tabs">
                  {PERIODS.map(([t,l])=>(
                    <button key={t} className={'tab'+(tab===t?' on':'')} onClick={e=>{e.stopPropagation();switchTab(t);}}>{l}</button>
                  ))}
                </div>
              </div>
              <div className="cb" style={{padding:'8px 12px',minHeight:280}}>
                {loading && <span className="empty">cargando {selected}...</span>}
                {!loading && !cdata && selected && <span className="empty">// sin datos para {selected}</span>}
                {!loading && !selected && <span className="empty">// selecciona un símbolo arriba</span>}
                <div ref={chartRef} style={{width:'100%',display:cdata?.bars?.length&&!loading?'block':'none'}}/>
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

    function ExecutionTimeline({ data }) {
      const items = data?.status?.trade_timeline || [];
      if (!items.length) return <div className="empty">// sin ejecuciones hoy</div>;
      return (
        <div className="tl">
          {items.slice(0,10).map((t,i)=>{
            const win = (t.pnl_usd||0) >= 0;
            return (
              <div key={i} className="tl-item">
                <span className="tl-dot" style={{background:t.status==='OPEN'?'var(--blue)':win?'var(--green)':'var(--red)'}}></span>
                <span className="tl-time">{fmt.time(t.opened_at)}</span>
                <div style={{flex:1}}>
                  <span style={{color:'var(--text)',fontWeight:500}}>{t.symbol}</span>
                  <span style={{marginLeft:6,fontSize:'.6rem',color:t.action==='BUY'?'var(--green)':'var(--red)'}}>{t.action}</span>
                  {t.status==='CLOSED' && (
                    <span style={{marginLeft:6,color:win?'var(--green)':'var(--red)'}}>{fmt.usd(t.pnl_usd)} {fmt.pct((t.pnl_pct||0)*100)}</span>
                  )}
                  {t.exit_reason && <span style={{marginLeft:6,color:'var(--dim)',fontSize:'.6rem'}}>{t.exit_reason.replace(/_/g,' ')}</span>}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    function WatchlistShort({ data }) {
      const items = (data?.daily_watchlist || []).slice(0,10);
      if (!items.length) return null;
      return (
        <div className="card fade-up">
          <div className="ch"><span className="ct">Watchlist Top 10</span><span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'var(--dim)'}}>score / liquidez / contexto</span></div>
          <div className="cb" style={{padding:'0 12px'}}>
            {items.map((item,i)=>{
              const up = (item.change_pct||0) >= 0;
              const vr = item.volume_ratio || 0;
              return (
                <div key={i} style={{display:'grid',gridTemplateColumns:'44px 1fr 44px 44px 44px 70px',alignItems:'center',padding:'7px 0',borderBottom:'1px solid var(--border)',gap:6,fontFamily:'"Fira Code",monospace',fontSize:'.68rem'}}>
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1rem',color:'var(--text)'}}>{item.symbol}</span>
                  <span style={{color:'var(--dim)',fontSize:'.6rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{(item.reason||'').split(':')[0]}</span>
                  <span style={{color:up?'var(--green)':'var(--red)'}}>{up?'+':''}{fmt.n(item.change_pct,1)}%</span>
                  <span style={{color:vr>2?'var(--green)':'var(--amber)',fontSize:'.6rem'}}>RVOL {fmt.n(vr,1)}x</span>
                  <span className="tag tag-neutral" style={{fontSize:'.55rem'}}>{item.signal_strength||'—'}</span>
                  <button onClick={()=>window.open('/analyze-page/'+item.symbol,'_blank')} className="btn btn-primary" style={{fontSize:'.6rem',padding:'2px 6px'}}>Analizar</button>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    function SignalsCompact({ signals }) {
      if (!signals?.length) return <div className="empty">// sin senales recientes</div>;
      return (
        <div style={{display:'flex',flexDirection:'column',gap:0}}>
          {signals.slice(0,8).map((s,i)=>{
            let extra={}; try{extra=JSON.parse(s.extra_indicators||'{}');}catch(e){}
            const trend=extra.weekly_trend;
            return (
              <div key={i} style={{display:'flex',alignItems:'center',gap:8,padding:'7px 0',borderBottom:'1px solid var(--border)',fontFamily:'"Fira Code",monospace',fontSize:'.68rem'}}>
                <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1rem',minWidth:40,color:'var(--text)'}}>{s.symbol}</span>
                <span className={'tag '+(s.strength==='STRONG'?'tag-buy':s.strength==='MEDIUM'?'tag-amber':'tag-neutral')} style={{fontSize:'.55rem'}}>{s.strength||'—'}</span>
                <span style={{color:'var(--dim)',fontSize:'.6rem'}}>RSI {fmt.n(s.rsi)}</span>
                <span style={{color:'var(--blue)',fontSize:'.6rem'}}>RVOL {fmt.n(s.volume_ratio,1)}x</span>
                {trend && trend!=='NEUTRAL' && <span style={{color:trend==='BULLISH'?'var(--green)':'var(--red)',fontSize:'.6rem'}}>{trend==='BULLISH'?'▲ BULL':'▼ BEAR'}</span>}
                <span style={{marginLeft:'auto',color:'var(--dimmer)',fontSize:'.6rem'}}>{fmt.time(s.created_at)}</span>
              </div>
            );
          })}
        </div>
      );
    }

    function NewsCard({ data }) {
      const [tab, setTab] = useState('universe');
      const all = data?.news || [];
      const openSyms = new Set((data?.open_trades||[]).map(t=>t.symbol));
      const univSyms = new Set((data?.symbols_universe||[]).map(s=>s.symbol));
      const filtered = {
        universe: all.filter(n=>univSyms.has(n.symbol)),
        all: all,
        positions: all.filter(n=>openSyms.has(n.symbol)),
      };
      const items = filtered[tab] || [];
      const sentColor = s => s==='positive'?'var(--green)':s==='negative'?'var(--red)':'var(--dim)';
      return (
        <div className="card fade-up">
          <div className="ch">
            <span className="ct">Noticias IBKR</span>
            <div className="tabs">
              {[['universe','Mi universo'],['all','Todas'],['positions','Posiciones']].map(([k,l])=>(
                <button key={k} className={'tab'+(tab===k?' on':'')} onClick={()=>setTab(k)}>{l}</button>
              ))}
            </div>
          </div>
          <div style={{padding:'0 12px'}}>
            {!items.length && <div style={{padding:'14px 0',textAlign:'center',fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--dimmer)'}}>// sin noticias</div>}
            {items.slice(0,4).map((n,i)=> (
              <div key={i} style={{padding:'8px 0',borderBottom:'1px solid var(--border)',display:'flex',gap:8}}>
                <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'.95rem',minWidth:38,color:'var(--text)'}}>{n.symbol||'MKT'}</span>
                <div>
                  {n.url?(
                    <a href={n.url} target="_blank" rel="noopener noreferrer" style={{fontSize:'.75rem',lineHeight:1.3,color:'var(--text)',display:'block',textDecoration:'underline',textUnderlineOffset:2}}>{n.headline}</a>
                  ):<p style={{fontSize:'.75rem',lineHeight:1.3,color:'var(--text)',marginBottom:2}}>{n.headline}</p>}
                  <div style={{display:'flex',gap:6,fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dim)'}}>
                    <span>{n.provider}</span><span>{n.fetched_at?.slice(11,16)||''}</span>
                    <span style={{padding:'1px 4px',borderRadius:3,border:'1px solid',fontSize:'.58rem',color:sentColor(n.sentiment),borderColor:sentColor(n.sentiment)+'44',background:sentColor(n.sentiment)+'11'}}>{n.sentiment||'neutral'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    function AnalyzeModal({ symbol, onClose }) {
      const [phase, setPhase] = useState('idle'); // idle | analyzing | done | error | approving | approved
      const [result, setResult] = useState(null);
      const [err, setErr] = useState(null);

      async function runAnalysis() {
        setPhase('analyzing'); setErr(null);
        try {
          const r = await fetch('/candidate-analysis/'+symbol);
          const j = await r.json();
          const jobId = j.job_id;
          // poll until done
          for (let i=0; i<60; i++) {
            await new Promise(res=>setTimeout(res,2000));
            const p = await fetch('/jobs/'+jobId);
            const pj = await p.json();
            if (pj.status==='success') { setResult(pj.result); setPhase('done'); return; }
            if (pj.status==='failed') { setErr(pj.error||'Análisis falló'); setPhase('error'); return; }
          }
          setErr('Timeout'); setPhase('error');
        } catch(e) { setErr(String(e)); setPhase('error'); }
      }

      async function approve() {
        setPhase('approving');
        try {
          await fetch('/symbols/approve/'+symbol, {method:'POST', headers:{'X-Control-Key': window._controlKey||''}});
          setPhase('approved');
        } catch(e) { setErr(String(e)); setPhase('error'); }
      }

      const score = result?.score ?? result?.total ?? null;
      const rec = result?.recommendation || null;
      const recColor = rec==='PRIORITY'?'var(--green)':rec==='WATCHLIST'?'var(--amber)':'var(--red)';

      return (
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.75)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center'}} onClick={onClose}>
          <div style={{background:'var(--surface)',border:'1px solid var(--border)',borderRadius:8,padding:24,width:340,maxWidth:'90vw'}} onClick={e=>e.stopPropagation()}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
              <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.4rem',color:'var(--text)'}}>{symbol}</span>
              <button onClick={onClose} style={{background:'none',border:'none',color:'var(--dim)',cursor:'pointer',fontSize:'1.2rem'}}>✕</button>
            </div>

            {phase==='idle' && (
              <button onClick={runAnalysis} className="btn btn-primary" style={{width:'100%',fontSize:'.85rem',padding:'8px'}}>
                🔍 Analizar con IA
              </button>
            )}

            {phase==='analyzing' && (
              <div style={{textAlign:'center',padding:'16px 0',fontFamily:'"Fira Code",monospace',fontSize:'.8rem',color:'var(--dim)'}}>
                <div className="pulse" style={{marginBottom:8}}>⚡ Analizando {symbol}...</div>
                <div style={{fontSize:'.7rem',color:'var(--dimmer)'}}>puede tardar 30-60s</div>
              </div>
            )}

            {phase==='done' && result && (
              <div>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:12}}>
                  <div>
                    <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dim)'}}>Score</div>
                    <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'2rem',color:'var(--blue)',lineHeight:1}}>{score!=null?Math.round(score):'—'}</div>
                  </div>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dim)'}}>Recomendación</div>
                    <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.2rem',color:recColor}}>{rec||'—'}</div>
                  </div>
                </div>
                {result.justification && (
                  <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--muted)',marginBottom:12,lineHeight:1.5,maxHeight:80,overflow:'auto'}}>
                    {result.justification}
                  </div>
                )}
                <div style={{display:'flex',gap:8}}>
                  <button onClick={approve} className="btn btn-primary" style={{flex:1,fontSize:'.82rem',padding:'7px'}}>
                    ✅ Agregar al universo
                  </button>
                  <button onClick={onClose} className="btn" style={{fontSize:'.82rem',padding:'7px 12px'}}>
                    Cerrar
                  </button>
                </div>
              </div>
            )}

            {phase==='approving' && (
              <div style={{textAlign:'center',padding:'16px 0',fontFamily:'"Fira Code",monospace',fontSize:'.8rem',color:'var(--dim)'}}>
                Aprobando {symbol}...
              </div>
            )}

            {phase==='approved' && (
              <div style={{textAlign:'center',padding:'16px 0'}}>
                <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.4rem',color:'var(--green)',marginBottom:8}}>✓ {symbol} AGREGADO</div>
                <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.75rem',color:'var(--dim)',marginBottom:12}}>Ya está en tu universo de trading</div>
                <button onClick={onClose} className="btn" style={{fontSize:'.82rem',padding:'7px 16px'}}>Cerrar</button>
              </div>
            )}

            {phase==='error' && (
              <div style={{textAlign:'center',padding:'12px 0'}}>
                <div style={{color:'var(--red)',fontFamily:'"Fira Code",monospace',fontSize:'.75rem',marginBottom:12}}>{err}</div>
                <button onClick={()=>setPhase('idle')} className="btn" style={{fontSize:'.82rem'}}>Reintentar</button>
              </div>
            )}
          </div>
        </div>
      );
    }

    function MarketTrendsCard({ data }) {
      const [tab,setTab]=useState('most_active');
      const [modal,setModal]=useState(null);
      const scanner=data?.scanner||{};
      const tabs=[['most_active','Activos'],['top_movers','Movers'],['gainers','Gainers'],['losers','Losers'],['sector','Sectores']];
      const rows=scanner[tab]||[];
      return (
        <div className="card fade-up">
          {modal && <AnalyzeModal symbol={modal} onClose={()=>setModal(null)} />}
          <div className="ch">
            <span className="ct">Market Trends</span>
            <div className="tabs">
              {tabs.map(([k,l])=>(<button key={k} className={'tab'+(tab===k?' on':'')} onClick={()=>setTab(k)}>{l}</button>))}
            </div>
          </div>
          <div style={{padding:'0 12px'}}>
            {!rows.length && <div style={{padding:'12px 0',textAlign:'center',fontFamily:'"Fira Code",monospace',fontSize:'.8rem',color:'var(--dimmer)'}}>// actualizando...</div>}
            {tab==='sector'?(
              <div style={{display:'flex',flexDirection:'column',gap:6,padding:'8px 0'}}>
                {rows.slice(0,6).map((r,i)=>{
                  const pct=r.change_pct==null?null:parseFloat(r.change_pct);
                  const color=(pct??0)>=0?'var(--green)':'var(--red)';
                  return (
                    <div key={i} style={{display:'flex',alignItems:'center',gap:8,fontFamily:'"Fira Code",monospace',fontSize:'.78rem'}}>
                      <span style={{width:36,color:'var(--text)',fontWeight:600,cursor:'pointer'}} onClick={()=>window._chartBus.emit(r.symbol)}>{r.symbol}</span>
                      <span style={{width:72,color:'var(--muted)',fontSize:'.72rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name}</span>
                      <div style={{flex:1,height:6,borderRadius:3,background:'rgba(255,255,255,.04)',overflow:'hidden'}}>
                        <div style={{height:'100%',width:`${Math.min(Math.abs(pct??0)*10,100)}%`,background:color,borderRadius:3}}/></div>
                      <span style={{color,width:44,textAlign:'right',fontWeight:600}}>{pct==null?'—':`${pct>=0?'+':''}${fmt.n(pct,1)}%`}</span>
                      <button onClick={()=>setModal(r.symbol)} className="btn btn-primary" style={{fontSize:'.7rem',padding:'2px 7px'}}>+</button>
                    </div>
                  );
                })}
              </div>
            ):rows.slice(0,5).map((r,i)=>{
              const pct=r.change_pct==null?null:parseFloat(r.change_pct);
              const vr=r.volume_ratio==null?null:parseFloat(r.volume_ratio);
              return (
                <div key={i} style={{display:'grid',gridTemplateColumns:'52px 1fr 56px 50px 60px',alignItems:'center',padding:'7px 0',borderBottom:'1px solid var(--border)',gap:6,fontFamily:'"Fira Code",monospace',fontSize:'.78rem'}}>
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',color:'var(--text)',cursor:'pointer'}}
                        onClick={()=>window._chartBus.emit(r.symbol)}>
                    {r.symbol}
                  </span>
                  <span style={{color:'var(--muted)',fontSize:'.72rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name||''}</span>
                  <span style={{color:(pct??0)>=0?'var(--green)':'var(--red)',fontWeight:600}}>{pct==null?'—':`${pct>=0?'+':''}${fmt.n(pct,1)}%`}</span>
                  <span className="tag" style={{fontSize:'.65rem',background:(vr??0)>2?'var(--green-bg)':'var(--amber-bg)',color:(vr??0)>2?'var(--green)':'var(--amber)',borderColor:(vr??0)>2?'rgba(16,185,129,.25)':'rgba(251,191,36,.2)'}}>{vr==null?'—':`${fmt.n(vr,1)}x`}</span>
                  <button onClick={()=>setModal(r.symbol)} className="btn btn-primary" style={{fontSize:'.7rem',padding:'3px 6px'}}>+ Analizar</button>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    function LearningCompact({ data }) {
      const l=data?.learning||{};
      return (
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <span style={{display:'inline-block',width:7,height:7,borderRadius:'50%',background:l.model_trained?'var(--blue)':'var(--border)',boxShadow:l.model_trained?'0 0 5px var(--blue)':'none'}} className={l.model_trained?'pulse':''}></span>
          <div>
            <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.2rem',color:l.model_trained?'var(--blue)':'var(--dimmer)',lineHeight:1}}>{l.model_trained?'MODELO ACTIVO':'SIN MODELO'}</div>
            <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)'}}>{l.model_trained?`actualizado hace ${l.pkl_age_hours<1?'<1h':Math.round(l.pkl_age_hours)+'h'}`:`${l.total_trades||0} trades (min 10)`}</div>
          </div>
        </div>
      );
    }

    function UniversoTable({ data }) {
      const all = data?.symbols_universe||[];
      const [search,setSearch]=useState('');
      const [page,setPage]=useState(0);
      const PAGE=15;
      const filtered=all.filter(s=>!search||s.symbol.toUpperCase().includes(search.toUpperCase()));
      const totalPages=Math.ceil(filtered.length/PAGE);
      const pageSyms=filtered.slice(page*PAGE,(page+1)*PAGE);
      useEffect(()=>{setPage(0);},[search]);
      if(!all.length) return null;
      return (
        <div className="card fade-up">
          <div className="ch" style={{gap:8,flexWrap:'wrap'}}>
            <span className="ct">Mi Universo</span>
            <span style={{fontSize:'.65rem',color:'var(--dim)',marginLeft:'auto'}}>{filtered.length} de {all.length}</span>
          </div>
          <div style={{display:'flex',gap:6,padding:'6px 12px',borderBottom:'1px solid var(--border)',flexWrap:'wrap',alignItems:'center'}}>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar..." style={{background:'var(--surface)',color:'var(--text)',border:'1px solid var(--border)',borderRadius:4,padding:'3px 8px',fontSize:'.68rem',fontFamily:'"Fira Code",monospace',width:120}}/>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr>{['SYM','CAL','SL%','TP%','PF','WR','TRADES',''].map(h=>(<th key={h}>{h}</th>))}</tr></thead>
              <tbody>
                {pageSyms.map(s=>(
                  <tr key={s.symbol}>
                    <td className="sym" style={{cursor:'pointer'}} onClick={()=>window._chartBus.emit(s.symbol)}>{s.symbol}{s.is_open&&<span className="tag tag-buy" style={{marginLeft:4,fontSize:'.55rem'}}>OPEN</span>}</td>
                    <td>{s.backtest_calibrated?<span className="tag tag-buy" style={{fontSize:'.55rem'}}>backtest</span>:<span className="tag tag-neutral" style={{fontSize:'.55rem'}}>default</span>}</td>
                    <td>{fmt.n((s.stop_loss_pct||0)*100,1)}%</td>
                    <td>{fmt.n((s.take_profit_pct||0)*100,1)}%</td>
                    <td>{fmt.n(s.backtest_profit_factor,2)}</td>
                    <td style={{color:s.win_rate>=.5?'var(--green)':s.win_rate!=null?'var(--red)':'var(--dim)'}}>{s.win_rate!=null?`${(s.win_rate*100).toFixed(0)}%`:'—'}</td>
                    <td>{s.trade_count}</td>
                    <td><button className="btn btn-primary" style={{fontSize:'.6rem',padding:'2px 6px'}} onClick={()=>fetch('/symbols/approve/'+s.symbol,{method:'POST'}).catch(()=>{})}>Recal.</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages>1 && (
            <div style={{display:'flex',gap:4,padding:'6px 12px',borderTop:'1px solid var(--border)',alignItems:'center',justifyContent:'flex-end'}}>
              <span style={{fontSize:'.65rem',color:'var(--dim)',marginRight:'auto'}}>Pag {page+1}/{totalPages}</span>
              <button className="btn" style={{fontSize:'.6rem',padding:'2px 6px'}} onClick={()=>setPage(0)} disabled={page===0}>|&lt;</button>
              <button className="btn" style={{fontSize:'.6rem',padding:'2px 6px'}} onClick={()=>setPage(p=>Math.max(0,p-1))} disabled={page===0}>&lt;</button>
              <button className="btn" style={{fontSize:'.6rem',padding:'2px 6px'}} onClick={()=>setPage(p=>Math.min(totalPages-1,p+1))} disabled={page===totalPages-1}>&gt;</button>
              <button className="btn" style={{fontSize:'.6rem',padding:'2px 6px'}} onClick={()=>setPage(totalPages-1)} disabled={page===totalPages-1}>&gt;|</button>
            </div>
          )}
        </div>
      );
    }

    function ControlBar({ data }) {
      const mode=(data?.status?.mode||'paper').toUpperCase();
      const paused=data?.status?.paused;
      const ib=data?.ib_connected;
      async function toggle(){ if(!ib) return; const ep=paused?'/system/resume':'/system/pause'; await fetch(ep,{method:'POST'}).catch(()=>{}); }
      return (
        <div className="card fade-up">
          <div className="ch"><span className="ct">Control del Sistema</span></div>
          <div style={{padding:'10px 12px',display:'flex',flexWrap:'wrap',alignItems:'center',gap:10}}>
            <button onClick={toggle} disabled={!ib} className="btn" style={{background:paused?'var(--red-bg)':'var(--green-bg)',color:paused?'var(--red)':'var(--green)',borderColor:paused?'rgba(244,63,94,.3)':'rgba(16,185,129,.3)',fontWeight:700}}>{paused?'REANUDAR':'PAUSAR'} SCANNER</button>
            <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)',marginLeft:'auto'}}>Modo {mode} · IB {ib?'ON':'OFF'}</span>
          </div>
        </div>
      );
    }

    function LogViewer() {
      const [logs,setLogs]=useState('');
      const [open,setOpen]=useState(false);
      const [lines,setLines]=useState(100);
      async function load(){ const res=await fetch('/logs?lines='+lines); const d=await res.json(); setLogs(d.log||''); setOpen(true); }
      return (
        <div>
          <div style={{display:'flex',gap:6,alignItems:'center',marginBottom:open?6:0}}>
            <button className="btn" style={{fontSize:'.65rem'}} onClick={load}>Logs</button>
            {[50,100,500].map(n=>(<button key={n} className="btn" style={{fontSize:'.6rem',padding:'2px 6px',background:lines===n?'var(--blue-bg)':'var(--surface2)',color:lines===n?'var(--blue)':'var(--dim)'}} onClick={()=>setLines(n)}>{n}</button>))}
            {open&&<button className="btn" style={{fontSize:'.65rem',padding:'2px 6px'}} onClick={()=>setOpen(false)}>x</button>}
          </div>
          {open&&(
            <div style={{background:'var(--surface2)',border:'1px solid var(--border)',borderRadius:6,padding:10,maxHeight:320,overflowY:'auto',fontFamily:'"Fira Code",monospace',fontSize:'.62rem',lineHeight:1.5}}>
              <pre style={{color:'var(--muted)',whiteSpace:'pre-wrap',wordBreak:'break-all',margin:0}}>{logs||'// sin logs'}</pre>
            </div>
          )}
        </div>
      );
    }

    /* ── Main App ── */
    function App() {
      const [data,setData]=useState(null);
      const [err,setErr]=useState(null);
      const [tick,setTick]=useState(0);
      const load = useCallback(async ()=>{
        try {
          const res=await fetch('/dashboard/data');
          if(!res.ok) throw new Error('HTTP '+res.status);
          setData(await res.json()); setErr(null);
        } catch(e){ setErr(e.message); }
      },[]);
      useEffect(()=>{ load(); },[tick,load]);
      const interval = data?.open_trades?.length>0?15:60;
      const ib = data?.ib_connected;
      async function togglePause(){ if(!ib) return; const ep=data?.status?.paused?'/system/resume':'/system/pause'; await fetch(ep,{method:'POST'}).catch(()=>{}); load(); }
      async function refresh(){ try{await fetch('/refresh',{method:'POST'});}catch(e){} setTick(k=>k+1); }

      return (
        <div style={{minHeight:'100vh',background:'var(--bg)'}}>
          <MarketContextBar data={data} />
          <SystemStatusBar data={data} />
          <Header data={data} interval={interval} onTick={()=>setTick(k=>k+1)} onTogglePause={togglePause} onRefresh={refresh}/>
          <div className="page">
            <StatCards data={data} />
            <div className="row-2">
              <div className="card fade-up">
                <div className="ch"><span className="ct">Posiciones Abiertas</span><span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'var(--muted)'}}>Riesgo / Size / Costo</span></div>
                <div className="cb"><OpenPositions data={data} /></div>
              </div>
              <div className="card fade-up">
                <div className="ch"><span className="ct">Mi Cuenta</span><span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'var(--muted)'}}>Equity + Drawdown</span></div>
                <div className="cb" style={{padding:'8px 12px'}}><EquityDrawdownChart history={data?.account_history} /></div>
              </div>
            </div>
            <RiskThermometer data={data} />
            <SymbolChart data={data} />
            <WatchlistShort data={data} />
            <div className="row-2">
              <div className="card fade-up">
                <div className="ch"><span className="ct">Ejecuciones Hoy</span></div>
                <div className="cb"><ExecutionTimeline data={data} /></div>
              </div>
              <div className="card fade-up">
                <div className="ch"><span className="ct">Senales</span></div>
                <div className="cb"><SignalsCompact signals={data?.signals} /></div>
              </div>
            </div>
            <div className="row-2">
              <NewsCard data={data} />
              <MarketTrendsCard data={data} />
            </div>
            <div className="card fade-up">
              <div className="ch"><span className="ct">Motor de Aprendizaje</span></div>
              <div className="cb"><LearningCompact data={data} /></div>
            </div>
            <UniversoTable data={data} />
            <ControlBar data={data} />
            {err&&<div style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--red)',padding:'8px 12px',background:'var(--red-bg)',border:'1px solid rgba(244,63,94,.3)',borderRadius:6}}>⚠ {err}</div>}
            <LogViewer />
          </div>
          <div className="footer">{data?(data.open_trades?.length||0)+' pos · '+(data.closed_trades?.length||0)+' cerrados · '+(data.patterns?.length||0)+' patrones':'cargando...'}</div>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById('root')).render(<App />);
  </script>
</body>
</html>'''


# Legacy shim
def render_dashboard(status, trades, closed_trades, signals, patterns) -> str:
    return render_dashboard_html()