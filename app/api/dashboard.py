"""
IBKR AI Trader — React dashboard.
Served as HTML from /dashboard. All data fetched client-side from /dashboard/data.
No build step — React + Tailwind via CDN.
"""


def render_dashboard_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IBKR AI Trader</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Fira+Code:wght@300;400;500&family=Barlow+Condensed:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    /* ─── Reset & Tokens ─────────────────────────────── */
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
    ::-webkit-scrollbar{width:4px;height:4px}
    ::-webkit-scrollbar-track{background:var(--bg)}
    ::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    @keyframes glow-green{0%,100%{box-shadow:0 0 6px rgba(16,185,129,.4)}50%{box-shadow:0 0 14px rgba(16,185,129,.7)}}
    .pulse{animation:pulse 2s ease-in-out infinite}
    .fade-up{animation:fadeUp .35s ease both}

    /* ─── IB Status Bar ─────────────────────────────── */
    .ib-bar{
      padding:5px 16px;display:flex;align-items:center;gap:8px;
      font-family:"Fira Code",monospace;font-size:.68rem;
    }
    .ib-bar.online{background:rgba(16,185,129,.08);border-bottom:1px solid rgba(16,185,129,.15)}
    .ib-bar.offline{background:rgba(244,63,94,.07);border-bottom:1px solid rgba(244,63,94,.15)}
    .ib-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
    .ib-bar.online .ib-dot{background:var(--green);box-shadow:0 0 5px var(--green)}
    .ib-bar.offline .ib-dot{background:var(--red)}
    .ib-bar.online .ib-status{color:var(--green)}
    .ib-bar.offline .ib-status{color:var(--red)}
    .ib-warn{color:var(--amber);margin-left:4px}

    /* ─── Header ─────────────────────────────────────── */
    .header{
      background:var(--surface);border-bottom:1px solid var(--border);
      padding:9px 16px;display:flex;align-items:center;justify-content:space-between;
      flex-wrap:wrap;gap:8px;position:sticky;top:0;z-index:20;
    }
    .logo{font-family:"Bebas Neue",cursive;font-size:1.3rem;letter-spacing:.1em;color:var(--text)}
    .badge{padding:2px 8px;border-radius:4px;font-family:"Fira Code",monospace;font-size:.68rem}
    .badge-paper{background:var(--green-bg);color:var(--green);border:1px solid rgba(16,185,129,.3)}
    .badge-live{background:var(--amber-bg);color:var(--amber);border:1px solid rgba(251,191,36,.3)}
    .hbtn{
      padding:4px 10px;border-radius:5px;font-family:"Barlow Condensed",sans-serif;
      font-size:.8rem;font-weight:600;letter-spacing:.04em;cursor:pointer;
      background:var(--surface2);border:1px solid var(--border);color:var(--muted);
    }
    .hbtn-pause{color:var(--amber);border-color:rgba(251,191,36,.25);background:var(--amber-bg)}
    .hbtn:disabled{opacity:.4;cursor:not-allowed}
    .theme-btn{
      background:var(--surface2);border:1px solid var(--border);color:var(--dim);
      padding:4px 10px;border-radius:20px;font-size:.75rem;cursor:pointer;
      display:flex;align-items:center;gap:5px;font-family:"Barlow Condensed",sans-serif;font-weight:600;
    }
    .countdown{font-family:"Fira Code",monospace;font-size:.65rem;color:var(--dimmer)}

    /* ─── Layout ─────────────────────────────────────── */
    .page{max-width:1200px;margin:0 auto;padding:12px;display:flex;flex-direction:column;gap:12px}
    .row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
    .row-2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    @media(max-width:900px){.row-4{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:600px){.row-2,.row-4{grid-template-columns:1fr}}

    /* ─── Cards ──────────────────────────────────────── */
    .card{background:var(--surface);border:1px solid var(--border);border-radius:7px;overflow:hidden}
    .ch{
      background:var(--surface2);border-bottom:1px solid var(--border);
      padding:8px 12px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;
    }
    .ct{font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--dim)}
    .cb{padding:12px}

    /* ─── Stat cards ─────────────────────────────────── */
    .sc{background:var(--surface);border:1px solid var(--border);border-radius:7px;padding:12px}
    .sl{font-size:.62rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--dim);margin-bottom:3px}
    .sv{font-family:"Bebas Neue",cursive;font-size:2.1rem;line-height:1.05}
    .ss{font-family:"Fira Code",monospace;font-size:.67rem;color:var(--muted);margin-top:2px}
    .green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.amber{color:var(--amber)}

    /* ─── Drawdown gauge ─────────────────────────────── */
    .dg-track{height:5px;border-radius:3px;overflow:hidden;margin-top:6px;
      background:linear-gradient(to right,var(--green) 0% 33%,var(--amber) 33% 66%,var(--red) 66%)}
    .dg-wrap{position:relative;height:5px;margin-top:6px}
    .dg-bg{position:absolute;inset:0;height:5px;border-radius:3px;
      background:linear-gradient(to right,rgba(16,185,129,.2) 0% 33%,rgba(251,191,36,.2) 33% 66%,rgba(244,63,94,.2) 66%)}
    .dg-fill{position:absolute;left:0;top:0;height:5px;border-radius:3px;transition:width .6s ease}
    .dg-pin{position:absolute;top:-2px;width:3px;height:9px;border-radius:1px;background:var(--text);transform:translateX(-50%);transition:left .6s ease}

    /* ─── Tabs ───────────────────────────────────────── */
    .tabs{display:flex;gap:2px;background:var(--bg);border-radius:5px;padding:2px}
    .tab{
      padding:3px 9px;border-radius:4px;font-family:"Fira Code",monospace;
      font-size:.66rem;color:var(--dim);cursor:pointer;border:none;background:transparent;
      white-space:nowrap;
    }
    .tab.on{background:var(--surface2);color:var(--text);border:1px solid var(--border)}

    /* ─── Positions ──────────────────────────────────── */
    .pos{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:8px}
    .pos:last-child{margin-bottom:0}
    .pos-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
    .psym{font-family:"Bebas Neue",cursive;font-size:1.25rem;letter-spacing:.06em;color:var(--text)}
    .ptag{padding:1px 6px;border-radius:3px;font-size:.67rem;font-family:"Fira Code",monospace}
    .tag-buy{background:var(--green-bg);color:var(--green);border:1px solid rgba(16,185,129,.3)}
    .tag-sell{background:var(--red-bg);color:var(--red);border:1px solid rgba(244,63,94,.3)}
    .str-s{color:var(--green);background:var(--green-bg);border:1px solid rgba(16,185,129,.3);padding:1px 6px;border-radius:3px;font-size:.67rem;font-family:"Fira Code",monospace}
    .str-m{color:var(--amber);background:var(--amber-bg);border:1px solid rgba(251,191,36,.25);padding:1px 6px;border-radius:3px;font-size:.67rem;font-family:"Fira Code",monospace}
    .str-w{color:var(--dim);background:rgba(100,116,139,.1);border:1px solid var(--border);padding:1px 6px;border-radius:3px;font-size:.67rem;font-family:"Fira Code",monospace}
    .ppnl{font-family:"Fira Code",monospace;font-size:.85rem;font-weight:500}
    .bcl{background:var(--red-bg);color:var(--red);border:1px solid rgba(244,63,94,.3);padding:3px 9px;border-radius:4px;font-size:.7rem;font-family:"Fira Code",monospace;cursor:pointer}
    .bcl:disabled{opacity:.4;cursor:not-allowed}
    .pos-g{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;font-family:"Fira Code",monospace;font-size:.71rem;margin-bottom:8px}
    .pk{color:var(--muted)}

    /* ─── R/R Bar ────────────────────────────────────── */
    .rr-track{height:6px;border-radius:3px;overflow:visible;position:relative;
      background:linear-gradient(to right,rgba(244,63,94,.35) 0%,rgba(251,191,36,.25) 50%,rgba(16,185,129,.35) 100%);
      margin:6px 0}
    .rr-pin{position:absolute;top:-4px;width:4px;height:14px;background:var(--text);border-radius:2px;transform:translateX(-50%);transition:left .4s ease}

    /* ─── Chart helpers ──────────────────────────────── */
    .ch-area{overflow:hidden;border-radius:4px}
    .meter{height:8px;border-radius:4px;overflow:hidden;flex:1;background:rgba(255,255,255,.05)}
    .meter-fill{height:100%;border-radius:4px;transition:width .5s ease}

    /* ─── Earnings badge ─────────────────────────────── */
    .earn-badge{
      background:rgba(251,191,36,.1);color:var(--amber);
      border:1px solid rgba(251,191,36,.3);padding:1px 7px;border-radius:3px;
      font-size:.64rem;font-family:"Fira Code",monospace;
    }

    /* ─── Trend chip ─────────────────────────────────── */
    .trend-bull{color:var(--blue);font-size:.65rem;font-family:"Fira Code",monospace}
    .trend-bear{color:var(--red);font-size:.65rem;font-family:"Fira Code",monospace}

    /* ─── Table ──────────────────────────────────────── */
    table{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.71rem}
    th{color:var(--dim);font-weight:500;padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)}
    td{padding:5px 8px;border-bottom:1px solid var(--border);color:var(--muted)}
    td.sym{color:var(--text);font-weight:500}
    tr:last-child td{border-bottom:none}

    /* ─── Empty state ────────────────────────────────── */
    .empty{color:var(--dimmer);font-family:"Fira Code",monospace;font-size:.75rem;
      padding:1.5rem 0;text-align:center;letter-spacing:.05em}

    /* ─── Footer ─────────────────────────────────────── */
    .footer{text-align:center;color:var(--dimmer);font-family:"Fira Code",monospace;font-size:.63rem;padding:12px}
  </style>
</head>
<body>
  <div id="root"></div>
  <script>
    // Theme initialization — runs before React mounts to avoid flicker
    (function(){
      var t = localStorage.getItem('theme') || 'dark';
      document.documentElement.setAttribute('data-theme', t);
    })();
  </script>
  <script type="text/babel">
    const { useState, useEffect, useRef, useCallback } = React;

    /* ── Formatting helpers ── */
    const f = {
      usd:   v => v == null ? '—' : '$' + parseFloat(v).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}),
      pct:   v => v == null ? '—' : (parseFloat(v) >= 0 ? '+' : '') + parseFloat(v).toFixed(2) + '%',
      n:     (v, d=1) => v == null ? '—' : parseFloat(v).toFixed(d),
      time:  v => v ? String(v).slice(11,16) : '—',
      date:  v => v ? String(v).slice(2,16).replace('T',' ') : '—',
    };

    /* ── Theme toggle ── */
    function toggleTheme() {
      const h = document.documentElement;
      const dark = h.getAttribute('data-theme') === 'dark';
      h.setAttribute('data-theme', dark ? 'light' : 'dark');
      localStorage.setItem('theme', dark ? 'light' : 'dark');
    }

    /* ── Close position ── */
    async function closePosition(tradeId) {
      if (!confirm('Cerrar posición? Se enviará confirmación por Telegram.')) return;
      try {
        const res = await fetch('/orders/close/id/' + tradeId, {method:'POST'});
        const d = await res.json();
        if (d.message) alert(d.message);
        else if (d.detail) alert('Error: ' + d.detail);
      } catch(e) {
        alert('Error de red: ' + e.message);
      }
    }

    /* ──────────────────── COMPONENTS ──────────────────── */

    /* IB Status Bar */
    function IbStatusBar({ ibConnected }) {
      const cls = ibConnected ? 'ib-bar online pulse' : 'ib-bar offline';
      return (
        <div className={cls}>
          <span className="ib-dot"></span>
          <span className="ib-status">
            IB Gateway · {ibConnected ? 'conectado' : 'offline'}
          </span>
          {!ibConnected && (
            <span className="ib-warn">⚡ critical actions blocked</span>
          )}
        </div>
      );
    }

    /* SystemStatusBar — polls /control/status every 30s (Issue 006) */
    function SystemStatusBar() {
      const [status, setStatus] = React.useState(null);
      const [err, setErr] = React.useState(false);

      React.useEffect(() => {
        let mounted = true;
        async function fetchStatus() {
          try {
            const res = await fetch('/control/status');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();
            if (mounted) { setStatus(data); setErr(false); }
          } catch(e) { if (mounted) setErr(true); }
        }
        fetchStatus();
        const id = setInterval(fetchStatus, 30000);
        return () => { mounted = false; clearInterval(id); };
      }, []);

      const mode = (status?.mode || 'paper').toUpperCase();
      const isLive = mode === 'LIVE';
      const isPaused = status?.is_paused || status?.paused;
      const ibConn = status?.ib_connected;
      const port = status?.ib_port || '—';
      const pnl = status?.daily_pnl_usd;

      let dotColor = isLive ? 'var(--amber)' : 'var(--green)';
      if (isPaused) dotColor = 'var(--amber)';
      if (!ibConn) dotColor = 'var(--red)';

      return (
        <div style={{padding:'6px 16px',display:'flex',alignItems:'center',gap:'12px',fontFamily:'"Fira Code",monospace',fontSize:'.7rem',background:'var(--surface2)',borderBottom:'1px solid var(--border)',flexWrap:'wrap'}}>
          <span style={{width:7,height:7,borderRadius:'50%',background:dotColor,boxShadow:dotColor==='var(--red)'?'none':'0 0 5px '+dotColor}} className={err?'':'pulse'}></span>
          <span style={{color:isLive?'var(--amber)':'var(--green)',fontWeight:700}}>{mode}</span>
          <span style={{color:'var(--dim)'}}>| Puerto: {port}</span>
          <span style={{color:isPaused?'var(--amber)':'var(--green)'}}>{isPaused ? '● Pausado' : '● Activo'}</span>
          <span style={{color:pnl>=0?'var(--green)':'var(--red)'}}>| P&L: {pnl == null ? '—' : '$' + parseFloat(pnl).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}</span>
          <span style={{color:ibConn?'var(--green)':'var(--red)'}}>| IB: {ibConn ? '✓' : '✗'}</span>
          <a href="/control" style={{color:'var(--blue)',textDecoration:'none',marginLeft:'auto'}}>[→ /control]</a>
          {err && <span style={{color:'var(--red)',marginLeft:8}}>⚠ offline</span>}
        </div>
      );
    }

    /* Countdown ring */
    function Refresh({ total, onTick }) {
      const [rem, setRem] = useState(total);
      useEffect(() => {
        setRem(total);
        const t = setInterval(() => {
          setRem(r => {
            if (r <= 1) { onTick(); return total; }
            return r - 1;
          });
        }, 1000);
        return () => clearInterval(t);
      }, [total, onTick]);
      const pct = (rem / total) * 100;
      const r = 7;
      const circ = 2 * Math.PI * r;
      return (
        <div style={{display:'flex',alignItems:'center',gap:4}}>
          <svg width="20" height="20" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r={r} fill="none" stroke="var(--border)" strokeWidth="1.5"/>
            <circle cx="10" cy="10" r={r} fill="none" stroke="var(--blue)" strokeWidth="1.5"
              strokeDasharray={circ}
              strokeDashoffset={circ * (1 - pct/100)}
              style={{transform:'rotate(-90deg)',transformOrigin:'center',transition:'stroke-dashoffset 1s linear'}}/>
          </svg>
          <span className="countdown">{rem}s</span>
        </div>
      );
    }

    /* Header */
    function Header({ data, interval, onTick, onTogglePause, onRefresh }) {
      const st = data?.status || {};
      const isLive = (st.mode || 'paper').toUpperCase() === 'LIVE';
      const ibConnected = data?.ib_connected;
      const [isDark, setIsDark] = useState(
        () => (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark'
      );

      function handleToggle() {
        toggleTheme();
        setIsDark(d => !d);
      }

      return (
        <div className="header">
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span style={{
              display:'inline-block',width:8,height:8,borderRadius:'50%',
              background: ibConnected ? 'var(--green)' : 'var(--red)',
              boxShadow: ibConnected ? '0 0 6px var(--green)' : 'none'
            }} className={ibConnected ? 'pulse' : ''}></span>
            <span className="logo">IBKR AI Trader</span>
            <span className={'badge ' + (isLive ? 'badge-live' : 'badge-paper')}>
              {isLive ? 'LIVE' : 'PAPER'}
            </span>
            {st.paused && (
              <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
                padding:'2px 8px',borderRadius:4,
                background:'rgba(100,116,139,.1)',color:'var(--dim)',
                border:'1px solid var(--border)'}}>PAUSADO</span>
            )}
          </div>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <button
              className="hbtn hbtn-pause"
              disabled={!ibConnected}
              title={!ibConnected ? 'IB Gateway offline' : ''}
              onClick={onTogglePause}
            >⏸ Pausar</button>
            <a href="/reports" style={{
              fontFamily:'"Fira Code",monospace', fontSize:'.75rem',
              color:'var(--blue)', textDecoration:'none',
              padding:'4px 10px', borderRadius:5,
              background:'var(--blue-bg)', border:'1px solid rgba(56,189,248,.25)'
            }}>📊 Reportes</a>
            <button onClick={onRefresh} style={{
              background:'var(--surface2)', border:'1px solid var(--border)',
              color:'var(--dim)', padding:'4px 8px', borderRadius:5,
              fontFamily:'"Fira Code",monospace', fontSize:'.72rem', cursor:'pointer'
            }}>↻</button>
            <button className="theme-btn" onClick={handleToggle}>
              <span>{isDark ? '☀️' : '🌙'}</span>
              <span>{isDark ? 'Claro' : 'Oscuro'}</span>
            </button>
            <Refresh total={interval} onTick={onTick} />
          </div>
        </div>
      );
    }

    /* Drawdown gauge */
    function DrawdownGauge({ drawdownPct }) {
      const dd = Math.min(Math.abs(parseFloat(drawdownPct) || 0), 15);
      const pct = (dd / 15) * 100;
      const color = dd < 5 ? 'var(--green)' : dd < 10 ? 'var(--amber)' : 'var(--red)';
      return (
        <div style={{marginTop:6}}>
          <div className="dg-wrap" style={{height:5,borderRadius:3}}>
            <div className="dg-bg"></div>
            <div className="dg-fill" style={{
              width: pct + '%', background: color, height:5, borderRadius:3, position:'absolute', left:0, top:0
            }}></div>
            <div className="dg-pin" style={{left: pct + '%'}}></div>
          </div>
          <div style={{display:'flex',justifyContent:'space-between',
            fontFamily:'"Fira Code",monospace',fontSize:'.6rem',color:'var(--dimmer)',marginTop:3}}>
            <span>0%</span><span>5%</span><span>10%</span><span>15%</span>
          </div>
        </div>
      );
    }

    /* Stat Cards */
    function StatCards({ data }) {
      const st = data?.status || {};
      const acct = data?.latest_account || {};
      const pnl = parseFloat(st.daily_pnl_usd || 0);
      const pct = parseFloat(st.daily_pnl_pct || 0);
      const netLiq = acct.net_liquidation || st.operating_capital || st.simulated_capital || 0;
      const buyPow = acct.buying_power || st.operating_capital || 0;
      const openCount = data?.open_trades?.length || 0;
      const accountSubtitle = st.ib_data_live ? 'IBKR snapshot · hoy' : 'último snapshot guardado';

      return (
        <div className="row-4">
          <div className="sc fade-up">
            <div className="sl">Net Liquidation</div>
            <div className="sv blue">{f.usd(netLiq)}</div>
            <div className="ss">{accountSubtitle}</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">P&amp;L Hoy</div>
            <div className={'sv ' + (pnl >= 0 ? 'green' : 'red')}>{f.usd(pnl)}</div>
            <div className="ss">{f.pct(pct)} · drawdown</div>
            <DrawdownGauge drawdownPct={st.drawdown_pct} />
          </div>
          <div className="sc fade-up">
            <div className="sl">Buying Power</div>
            <div className="sv" style={{color:'var(--text)'}}>{f.usd(buyPow)}</div>
            <div className="ss">disponible</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">Posiciones</div>
            <div className="sv" style={{color:'var(--text)'}}>
              {openCount}<span style={{fontSize:'1rem',color:'var(--dim)'}}>/3</span>
            </div>
            <div className="ss">{openCount < 3 ? (3 - openCount) + ' slot(s) libre(s)' : 'máx alcanzado'}</div>
          </div>
        </div>
      );
    }

    /* R/R bar */
    function RRBar({ trade, snapshots }) {
      const snap = (snapshots || []).find(s => s.trade_id === (trade.trade_id || trade.id)) || {};
      const current = parseFloat(snap.current_price || trade.current_price || trade.entry_price || 0);
      const sl = parseFloat(trade.stop_loss_price || 0);
      const tp = parseFloat(trade.take_profit_price || 0);

      let pinPct = 50;
      if (tp > sl) {
        const raw = trade.action === 'BUY'
          ? (current - sl) / (tp - sl)
          : (sl - current) / (sl - tp);
        pinPct = Math.max(0, Math.min(100, raw * 100));
      }

      return (
        <div style={{margin:'6px 0'}}>
          <div className="rr-track">
            <div className="rr-pin" style={{left: pinPct + '%'}}></div>
          </div>
          <div style={{display:'flex',justifyContent:'space-between',
            fontFamily:'"Fira Code",monospace',fontSize:'.62rem',color:'var(--dimmer)',marginTop:2}}>
            <span style={{color:'var(--red)'}}>SL {f.usd(sl)}</span>
            <span style={{color:'var(--blue)'}}>ACT {f.usd(current)}</span>
            <span style={{color:'var(--green)'}}>TP {f.usd(tp)}</span>
          </div>
        </div>
      );
    }

    /* Open Positions */
    function OpenPositions({ data }) {
      const trades = data?.open_trades || [];
      const snapshots = data?.position_snapshots || [];
      const earningsWarnings = data?.earnings_warnings || {};
      const ibConnected = data?.ib_connected;

      const strCls = s => s === 'STRONG' ? 'str-s' : s === 'MEDIUM' ? 'str-m' : 'str-w';

      const items = trades.map((t, i) => {
        const snap = snapshots.find(s => s.trade_id === (t.trade_id || t.id)) || {};
        const pnlUsd = parseFloat(snap.pnl_usd != null ? snap.pnl_usd : (t.pnl_usd || 0));
        const pnlPct = parseFloat(snap.pnl_pct != null ? snap.pnl_pct : (t.pnl_pct || 0));
        const currentPrice = snap.current_price || t.current_price || t.entry_price;
        const earningsDays = earningsWarnings[t.symbol];
        let extra = {};
        try { extra = JSON.parse(t.extra_indicators || '{}'); } catch(e) {}
        const trend = extra.weekly_trend;

        return (
          <div key={t.trade_id || t.id || i} className="pos fade-up">
            <div className="pos-top">
              <div style={{display:'flex',alignItems:'center',gap:7,flexWrap:'wrap'}}>
                <span className="psym">{t.symbol}</span>
                <span className={'ptag ' + (t.action === 'BUY' ? 'tag-buy' : 'tag-sell')}>{t.action}</span>
                <span className={strCls(t.signal_strength)}>{t.signal_strength || '—'}</span>
                {trend && trend !== 'NEUTRAL' && (
                  <span className={trend === 'BULLISH' ? 'trend-bull' : 'trend-bear'}>
                    {trend === 'BULLISH' ? '▲' : '▼'} {trend === 'BULLISH' ? 'BULL' : 'BEAR'}
                  </span>
                )}
                {earningsDays !== undefined && (
                  <span className="earn-badge">⚠ Earnings en {earningsDays}d</span>
                )}
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span className={'ppnl ' + (pnlUsd >= 0 ? 'green' : 'red')}>
                  {f.usd(pnlUsd)} <span style={{fontSize:'.75rem'}}>{f.pct(pnlPct * 100)}</span>
                </span>
                <button
                  className="bcl"
                  disabled={!ibConnected}
                  title={!ibConnected ? 'IB Gateway offline' : ''}
                  onClick={() => closePosition(t.trade_id || t.id)}
                >Cerrar</button>
              </div>
            </div>
            <div className="pos-g">
              <div><span className="pk">ENTRY </span><span style={{color:'var(--text)'}}>{f.usd(t.entry_price)}</span></div>
              <div><span className="pk">ACTUAL </span><span style={{color:'var(--text)'}}>{f.usd(currentPrice)}</span></div>
              <div><span className="pk">RET% </span><span style={{color: pnlPct >= 0 ? 'var(--green)' : 'var(--red)'}}>{f.pct(pnlPct * 100)}</span></div>
              <div><span className="pk">SL </span><span style={{color:'var(--red)'}}>{f.usd(t.stop_loss_price)}</span></div>
              <div><span className="pk">TP </span><span style={{color:'var(--green)'}}>{f.usd(t.take_profit_price)}</span></div>
              <div><span className="pk">QTY </span><span style={{color:'var(--text)'}}>{t.quantity} u</span></div>
            </div>
            <RRBar trade={t} snapshots={snapshots} />
          </div>
        );
      });

      // Fill empty slots up to 3
      const slots = [...items];
      while (slots.length < 3) {
        slots.push(
          <div key={'slot-' + slots.length} style={{
            background:'var(--surface2)',border:'1px dashed var(--border)',
            borderRadius:6,padding:14,textAlign:'center',
            fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--dimmer)',
            marginBottom: slots.length < 2 ? 8 : 0
          }}>
            slot disponible — esperando señal STRONG
          </div>
        );
      }

      return <div>{slots}</div>;
    }

    /* ─── Mi Cuenta charts ─────────────────────────── */

    function EquityChart({ history }) {
      if (!history || history.length === 0) {
        return <div className="empty">// sin historial de cuenta aún</div>;
      }
      const W = 420, H = 148, padT = 16, padB = 20;
      const vals = history.map(h => parseFloat(h.net_liquidation || 0));
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const range = max - min || 1;
      const step = W / (vals.length - 1 || 1);

      const pts = vals.map((v, i) => {
        const x = i * step;
        const y = padT + ((max - v) / range) * (H - padT - padB);
        return x + ',' + y;
      }).join(' ');

      const firstVal = vals[0];
      const lastVal = vals[vals.length - 1];
      const totalPnl = lastVal - firstVal;

      return (
        <div>
          <div className="ch-area" style={{height:H}}>
            <svg width="100%" height={H} viewBox={'0 0 ' + W + ' ' + H} preserveAspectRatio="none">
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38BDF8" stopOpacity=".22"/>
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <polyline points={pts} fill="none" stroke="#38BDF8" strokeWidth="2.2"/>
              <polygon points={pts + ' ' + W + ',' + H + ' 0,' + H}
                fill="url(#eqGrad)"/>
              {history.map((h, i) => {
                const pnl = parseFloat(h.daily_pnl_usd || 0);
                if (pnl === 0) return null;
                const x = i * step;
                const barH = Math.min(Math.abs(pnl) / (range || 1) * (H - padT - padB) * 2, 18);
                const color = pnl >= 0 ? '#10B981' : '#F43F5E';
                return <rect key={i} x={x - step * 0.35} y={H - padB - barH}
                  width={step * 0.7} height={barH}
                  fill={color} opacity=".75"/>;
              })}
              <text x="3" y="13" fill="var(--dimmer)" fontSize="9" fontFamily="monospace">
                {f.usd(lastVal)} · {history.length}d
              </text>
            </svg>
          </div>
          <div style={{display:'flex',gap:10,marginTop:6,
            fontFamily:'"Fira Code",monospace',fontSize:'.68rem'}}>
            <span style={{color:'var(--blue)'}}>━ balance</span>
            <span style={{color:'var(--green)'}}>▮ día +</span>
            <span style={{color:'var(--red)'}}>▮ día −</span>
            <span style={{marginLeft:'auto',color: totalPnl >= 0 ? 'var(--green)' : 'var(--red)'}}>
              {totalPnl >= 0 ? '+' : ''}{f.usd(totalPnl)}
            </span>
          </div>
        </div>
      );
    }

    function WeeklyChart({ closed }) {
      if (!closed || closed.length === 0) {
        return <div className="empty">// sin trades cerrados aún</div>;
      }
      // Group by ISO week
      const weekMap = {};
      closed.forEach(t => {
        const d = new Date(t.closed_at || t.opened_at);
        const jan4 = new Date(d.getFullYear(), 0, 4);
        const week = Math.ceil(((d - jan4) / 86400000 + jan4.getDay() + 1) / 7);
        const key = d.getFullYear() + '-W' + String(week).padStart(2,'0');
        weekMap[key] = (weekMap[key] || 0) + parseFloat(t.pnl_usd || 0);
      });
      const weeks = Object.entries(weekMap).sort((a,b) => a[0] < b[0] ? -1 : 1).slice(-8);
      if (weeks.length === 0) return <div className="empty">// sin historial semanal</div>;

      const vals = weeks.map(([,v]) => v);
      const maxAbs = Math.max(...vals.map(Math.abs), 0.01);
      const W = 420, H = 148, baseline = H * 0.6, maxBarH = H * 0.55;
      const bw = Math.floor(W / weeks.length * 0.6);
      const gap = W / weeks.length;

      return (
        <div className="ch-area" style={{height:H}}>
          <svg width="100%" height={H} viewBox={'0 0 ' + W + ' ' + H} preserveAspectRatio="none">
            <line x1="0" y1={baseline} x2={W} y2={baseline} stroke="var(--border)" strokeWidth="1"/>
            {weeks.map(([label, val], i) => {
              const x = i * gap + gap * 0.2;
              const h = (Math.abs(val) / maxAbs) * maxBarH;
              const y = val >= 0 ? baseline - h : baseline;
              const color = val >= 0 ? '#10B981' : '#F43F5E';
              const shortLabel = label.split('-W')[1] ? 'W' + label.split('-W')[1] : label;
              return (
                <g key={label}>
                  <rect x={x} y={y} width={bw} height={h || 1} fill={color} opacity=".8" rx="2"/>
                  <text x={x + bw/2} y={H - 3} fill="var(--dimmer)" fontSize="8"
                    fontFamily="monospace" textAnchor="middle">{shortLabel}</text>
                </g>
              );
            })}
            <text x="3" y="13" fill="var(--dimmer)" fontSize="9" fontFamily="monospace">P&amp;L por semana</text>
          </svg>
        </div>
      );
    }

    function ExitsChart({ closed }) {
      if (!closed || closed.length === 0) {
        return <div className="empty">// sin historial de cierres aún</div>;
      }
      const counts = {};
      closed.forEach(t => {
        const r = (t.exit_reason || 'UNKNOWN').replace(/_/g,' ');
        counts[r] = (counts[r] || 0) + 1;
      });
      const total = closed.length;
      const entries = Object.entries(counts).sort((a,b) => b[1]-a[1]);
      const colorMap = {
        'TAKE PROFIT': 'var(--green)', 'STOP LOSS': 'var(--red)',
        'TRAILING STOP': 'var(--amber)', 'MANUAL CLOSE': 'var(--dim)',
        'MANUAL': 'var(--dim)',
      };

      return (
        <div style={{display:'flex',flexDirection:'column',gap:9}}>
          <p style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',
            color:'var(--dim)',marginBottom:6}}>
            Distribución de cierres · {total} trades
          </p>
          {entries.map(([reason, cnt]) => {
            const pct = Math.round(cnt / total * 100);
            const color = colorMap[reason] || 'var(--muted)';
            return (
              <div key={reason} style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{width:8,height:8,borderRadius:'50%',background:color,
                  flexShrink:0,display:'inline-block'}}></span>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.73rem',
                  color:'var(--muted)',width:110,overflow:'hidden',
                  textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{reason}</span>
                <div className="meter">
                  <div className="meter-fill" style={{width:pct+'%',background:color}}></div>
                </div>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.73rem',
                  color:color,width:32,textAlign:'right'}}>{pct}%</span>
              </div>
            );
          })}
        </div>
      );
    }

    function HoursChart({ closed }) {
      if (!closed || closed.length === 0) {
        return <div className="empty">// sin historial por horas aún</div>;
      }
      const hourMap = {};
      closed.forEach(t => {
        const d = new Date(t.opened_at);
        const h = d.getHours();
        if (!hourMap[h]) hourMap[h] = {sum:0, count:0};
        hourMap[h].sum += parseFloat(t.pnl_usd || 0);
        hourMap[h].count++;
      });
      const hours = Object.entries(hourMap)
        .map(([h, {sum, count}]) => [parseInt(h), count > 0 ? sum / count : null])
        .filter(([, avg]) => avg !== null && !isNaN(avg))
        .sort((a,b) => a[0]-b[0]);

      if (hours.length === 0) return <div className="empty">// sin datos por hora</div>;

      const vals = hours.map(([,v]) => v);
      const maxAbs = Math.max(...vals.map(Math.abs), 0.01);
      const W = 420, H = 148, baseline = H * 0.6, maxBarH = H * 0.5;
      const bw = Math.max(Math.floor(W / hours.length * 0.6), 4);
      const gap = W / hours.length;

      return (
        <div className="ch-area" style={{height:H}}>
          <svg width="100%" height={H} viewBox={'0 0 ' + W + ' ' + H} preserveAspectRatio="none">
            <line x1="0" y1={baseline} x2={W} y2={baseline}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="4,4"/>
            {hours.map(([hr, avg], i) => {
              const x = i * gap + gap * 0.2;
              const h = (Math.abs(avg) / maxAbs) * maxBarH;
              const y = avg >= 0 ? baseline - h : baseline;
              const color = avg >= 0 ? '#10B981' : '#F43F5E';
              return (
                <g key={hr}>
                  <rect x={x} y={y} width={bw} height={h || 1} fill={color}
                    opacity={0.4 + 0.5 * Math.abs(avg) / maxAbs} rx="1"/>
                  <text x={x + bw/2} y={H - 3} fill="var(--dimmer)" fontSize="8"
                    fontFamily="monospace" textAnchor="middle">{hr}:00</text>
                </g>
              );
            })}
            <text x="3" y="13" fill="var(--dimmer)" fontSize="9" fontFamily="monospace">
              P&amp;L promedio por hora de entrada
            </text>
          </svg>
        </div>
      );
    }

    function MiCuenta({ data }) {
      const [tab, setTab] = useState('eq');
      const history = data?.account_history || [];
      const closed = data?.closed_trades || [];

      return (
        <div className="card fade-up">
          <div className="ch">
            <span className="ct">Mi Cuenta</span>
            <div className="tabs">
              {[['eq','Equity'],['wk','Semanal'],['ex','Exits'],['hr','Horas']].map(([id,label]) => (
                <button key={id}
                  className={'tab' + (tab === id ? ' on' : '')}
                  onClick={() => setTab(id)}>{label}</button>
              ))}
            </div>
          </div>
          <div className="cb" style={{padding:'8px 12px'}}>
            {tab === 'eq' && <EquityChart history={history} />}
            {tab === 'wk' && <WeeklyChart closed={closed} />}
            {tab === 'ex' && <ExitsChart closed={closed} />}
            {tab === 'hr' && <HoursChart closed={closed} />}
          </div>
        </div>
      );
    }

    /* ──────────────────── PART B COMPONENTS ──────────────────── */

    /* Symbol Chart — TradingView Lightweight Charts (candlesticks) */
    function SymbolChart({ data }) {
      const [selected, setSelected] = React.useState(null);
      const [chartData, setChartData] = React.useState(null);
      const [tab, setTab] = React.useState('intraday');
      const [loading, setLoading] = React.useState(false);
      const [indicators, setIndicators] = React.useState({rsi: false, macd: false, boll: false, volume: true});
      const chartRef = React.useRef(null);
      const tvChartRef = React.useRef(null);
      const seriesRef = React.useRef({});

      const chips = React.useMemo(() => {
        const syms = [
          ...(data?.open_trades || []).map(t => t.symbol),
          ...(data?.signals || []).slice(0,4).map(s => s.symbol),
        ];
        return [...new Set(syms)].slice(0,8);
      }, [data]);

      async function loadChart(sym, period) {
        setLoading(true);
        try {
          const res = await fetch(`/dashboard/symbol/${sym}?period=${period}`);
          const d = await res.json();
          setChartData(d);
        } catch(e) { setChartData(null); }
        setLoading(false);
      }

      function selectSym(sym) {
        setSelected(sym);
        loadChart(sym, tab);
      }

      function switchTab(t) {
        setTab(t);
        if (selected) loadChart(selected, t);
      }

      // Build/rebuild TradingView chart when data or indicator toggles change
      React.useEffect(() => {
        if (!chartRef.current || !chartData?.bars?.length || typeof LightweightCharts === 'undefined') return;

        // Destroy previous chart
        if (tvChartRef.current) {
          try { tvChartRef.current.remove(); } catch(e) {}
          tvChartRef.current = null;
          seriesRef.current = {};
        }

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
          width: chartRef.current.clientWidth,
          height: 200,
        });
        tvChartRef.current = chart;

        // Main candlestick series
        const bars = chartData.bars;
        const candleSeries = chart.addCandlestickSeries({
          upColor: '#10B981', downColor: '#F43F5E',
          borderUpColor: '#10B981', borderDownColor: '#F43F5E',
          wickUpColor: '#10B981', wickDownColor: '#F43F5E',
        });
        candleSeries.setData(bars.map(b => ({
          time: b.time, open: b.open, high: b.high, low: b.low, close: b.close
        })));
        seriesRef.current.candle = candleSeries;

        // Entry/SL/TP lines for open positions
        const trade = data?.open_trades?.find(t => t.symbol === selected);
        if (trade && bars.length > 0) {
          const entryLine = chart.addLineSeries({ color: '#FBBF24', lineWidth: 1, lineStyle: 2 });
          entryLine.setData(bars.map(b => ({ time: b.time, value: trade.entry_price })));
          const slLine = chart.addLineSeries({ color: '#F43F5E', lineWidth: 1, lineStyle: 2 });
          slLine.setData(bars.map(b => ({ time: b.time, value: trade.stop_loss_price })));
          const tpLine = chart.addLineSeries({ color: '#10B981', lineWidth: 1, lineStyle: 2 });
          tpLine.setData(bars.map(b => ({ time: b.time, value: trade.take_profit_price })));
        }

        // Volume histogram
        if (indicators.volume) {
          const volSeries = chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'vol',
            color: '#38BDF840',
          });
          chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
          volSeries.setData(bars.map(b => ({
            time: b.time, value: b.volume,
            color: b.close >= b.open ? '#10B98140' : '#F43F5E40'
          })));
          seriesRef.current.volume = volSeries;
        }

        // Bollinger Bands
        if (indicators.boll && chartData.boll_series?.length) {
          const bollU = chart.addLineSeries({ color: '#A78BFA50', lineWidth: 1 });
          const bollM = chart.addLineSeries({ color: '#A78BFA80', lineWidth: 1, lineStyle: 2 });
          const bollL = chart.addLineSeries({ color: '#A78BFA50', lineWidth: 1 });
          bollU.setData(chartData.boll_series.map(b => ({ time: b.time, value: b.upper })));
          bollM.setData(chartData.boll_series.map(b => ({ time: b.time, value: b.middle })));
          bollL.setData(chartData.boll_series.map(b => ({ time: b.time, value: b.lower })));
        }

        chart.timeScale().fitContent();

        // Resize observer
        const ro = new ResizeObserver(() => {
          if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
        });
        ro.observe(chartRef.current);
        return () => ro.disconnect();
      }, [chartData, indicators]);

      if (!chips.length) return null;

      const toggleIndicator = (key) => setIndicators(prev => ({ ...prev, [key]: !prev[key] }));

      return (
        <div className="card fade-up">
          <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap',padding:'8px 12px',background:'var(--surface2)',borderBottom:'1px solid var(--border)'}}>
            <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.67rem',color:'var(--dim)'}}>SYM:</span>
            {chips.map(sym => (
              <button key={sym} onClick={() => selectSym(sym)}
                style={{padding:'3px 10px',borderRadius:12,fontFamily:'"Fira Code",monospace',fontSize:'.68rem',cursor:'pointer',
                  border:'1px solid '+(selected===sym?'rgba(56,189,248,.35)':'var(--border)'),
                  background:selected===sym?'var(--blue-bg)':'transparent',
                  color:selected===sym?'var(--blue)':'var(--muted)'}}>
                {sym}
              </button>
            ))}
          </div>

          <div className="ch">
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span className="ct">{selected||'Símbolo'}</span>
              {selected && ['volume','boll','rsi','macd'].map(ind => (
                <button key={ind} onClick={() => toggleIndicator(ind)}
                  style={{padding:'2px 7px',borderRadius:3,fontFamily:'"Fira Code",monospace',fontSize:'.63rem',cursor:'pointer',
                    background:indicators[ind]?'var(--blue-bg)':'transparent',
                    color:indicators[ind]?'var(--blue)':'var(--dim)',
                    border:`1px solid ${indicators[ind]?'rgba(56,189,248,.3)':'var(--border)'}`}}>
                  {ind.toUpperCase()}
                </button>
              ))}
            </div>
            <div className="tabs">
              {[['intraday','Hoy 5min'],['daily','30D'],['indicators','Indicadores']].map(([t,l])=>(
                <button key={t} className={`tab${tab===t?' on':''}`} onClick={()=>switchTab(t)}>{l}</button>
              ))}
            </div>
          </div>

          <div className="cb" style={{padding:'8px 12px',minHeight:220}}>
            {loading && <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dim)'}}>cargando...</span>}
            {!loading && !chartData && selected && (
              <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dim)'}}>// sin datos para {selected}</span>
            )}
            {!loading && !selected && (
              <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dim)'}}>// selecciona un símbolo</span>
            )}
            <div ref={chartRef} style={{width:'100%',display: chartData?.bars?.length && !loading ? 'block':'none'}} />

            {/* RSI panel */}
            {indicators.rsi && chartData?.rsi_series?.length && !loading && (
              <div style={{marginTop:8,fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                <span style={{color:'var(--dim)'}}>RSI(14): </span>
                <span style={{color: chartData.rsi_series.at(-1).value > 70 ? 'var(--red)' : chartData.rsi_series.at(-1).value < 30 ? 'var(--green)' : 'var(--text)'}}>
                  {chartData.rsi_series.at(-1).value.toFixed(1)}
                </span>
              </div>
            )}

            {/* MACD panel */}
            {indicators.macd && chartData?.macd_series?.length && !loading && (
              <div style={{marginTop:4,fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                <span style={{color:'var(--dim)'}}>MACD: </span>
                <span style={{color: chartData.macd_series.at(-1).histogram > 0 ? 'var(--green)' : 'var(--red)'}}>
                  {chartData.macd_series.at(-1).macd.toFixed(3)} / Signal: {chartData.macd_series.at(-1).signal.toFixed(3)}
                </span>
              </div>
            )}
          </div>
        </div>
      );
    }

    /* Legacy lower panels */
    function Badge({ s }) {
      const clsMap = {STRONG:'str-s',MEDIUM:'str-m',WEAK:'str-w'};
      return (
        <span className={clsMap[s] || 'str-w'}>{s || '—'}</span>
      );
    }

    function TrendChip({ trend }) {
      if (!trend || trend === 'NEUTRAL') return null;
      return (
        <span className={trend === 'BULLISH' ? 'trend-bull' : 'trend-bear'}>
          {trend === 'BULLISH' ? '▲' : '▼'} {trend}
        </span>
      );
    }

    function Signals({ signals }) {
      if (!signals?.length) return <div className="empty">// sin señales recientes</div>;
      return (
        <div style={{overflowX:'auto'}}>
          <table>
            <thead>
              <tr>
                <th>SYM</th><th>FUERZA</th><th style={{textAlign:'right'}}>RSI</th>
                <th style={{textAlign:'right'}}>VOL</th><th>TREND</th>
                <th style={{textAlign:'right'}}>HORA</th>
              </tr>
            </thead>
            <tbody>
              {signals.slice(0,8).map((s,i) => {
                let extra = {};
                try { extra = JSON.parse(s.extra_indicators || '{}'); } catch(e) {}
                return (
                  <tr key={i} className="fade-up">
                    <td className="sym">{s.symbol}</td>
                    <td><Badge s={s.strength} /></td>
                    <td style={{textAlign:'right'}}>{s.rsi ? f.n(s.rsi) : '—'}</td>
                    <td style={{textAlign:'right'}}>{s.volume_ratio ? f.n(s.volume_ratio,1)+'x' : '—'}</td>
                    <td><TrendChip trend={extra.weekly_trend} /></td>
                    <td style={{textAlign:'right'}}>{f.time(s.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    function History({ closed }) {
      if (!closed?.length) return <div className="empty">// sin historial</div>;
      return (
        <div style={{overflowX:'auto'}}>
          <table>
            <thead>
              <tr>
                <th>SYM</th><th>ACT</th><th style={{textAlign:'right'}}>P&amp;L $</th>
                <th style={{textAlign:'right'}}>%</th><th>RAZÓN</th>
                <th style={{textAlign:'right'}}>FECHA</th>
              </tr>
            </thead>
            <tbody>
              {closed.slice(0,8).map((t,i) => {
                const pnl = parseFloat(t.pnl_usd || 0);
                const pct = parseFloat(t.pnl_pct || 0);
                const win = pnl >= 0;
                return (
                  <tr key={i} className="fade-up">
                    <td className="sym">{t.symbol}</td>
                    <td style={{color: t.action==='BUY' ? 'var(--green)' : 'var(--red)'}}>{t.action}</td>
                    <td style={{textAlign:'right',color: win ? 'var(--green)' : 'var(--red)'}}>{f.usd(pnl)}</td>
                    <td style={{textAlign:'right',color: win ? 'var(--green)' : 'var(--red)'}}>{f.pct(pct * 100)}</td>
                    <td style={{maxWidth:100,overflow:'hidden',textOverflow:'ellipsis'}}>
                      {(t.exit_reason||'—').replace(/_/g,' ')}
                    </td>
                    <td style={{textAlign:'right'}}>{f.date(t.closed_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    function WinBar({ symbol, rate }) {
      const pct = Math.round((rate || 0) * 100);
      const fill = pct >= 55 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : 'var(--red)';
      return (
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
            color:'var(--muted)',width:44,flexShrink:0}}>{symbol}</span>
          <div className="meter">
            <div className="meter-fill" style={{width:pct+'%',background:fill}}></div>
          </div>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
            color:'var(--muted)',width:32,textAlign:'right',flexShrink:0}}>{pct}%</span>
        </div>
      );
    }

    function Learning({ data }) {
      const { model_trained, win_rates, total_trades, pkl_age_hours } = data || {};
      const hasRates = win_rates && Object.keys(win_rates).length > 0;
      return (
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <span style={{
              display:'inline-block',width:8,height:8,borderRadius:'50%',
              background: model_trained ? 'var(--blue)' : 'var(--border)',
              boxShadow: model_trained ? '0 0 6px var(--blue)' : 'none',
            }} className={model_trained ? 'pulse' : ''}></span>
            <div>
              <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.6rem',
                color: model_trained ? 'var(--blue)' : 'var(--dimmer)',lineHeight:1}}>
                {model_trained ? 'MODELO ACTIVO' : 'SIN MODELO'}
              </div>
              <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',color:'var(--dimmer)'}}>
                {model_trained && pkl_age_hours != null
                  ? 'actualizado hace ' + (pkl_age_hours < 1 ? '<1h' : Math.round(pkl_age_hours)+'h')
                  : total_trades >= 10 ? 'pendiente: siguiente ciclo 17:05 ET' : (total_trades||0)+' trades (mín 10)'}
              </div>
            </div>
          </div>
          {hasRates && (
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              <div style={{fontSize:'.62rem',fontWeight:700,letterSpacing:'.13em',
                textTransform:'uppercase',color:'var(--dim)',marginBottom:2}}>Win Rate / Símbolo</div>
              {Object.entries(win_rates)
                .sort(([,a],[,b]) => b-a).slice(0,7)
                .map(([sym, rate]) => <WinBar key={sym} symbol={sym} rate={rate} />)}
            </div>
          )}
          {!hasRates && <div className="empty">// win rates disponibles con 3+ trades por símbolo</div>}
        </div>
      );
    }

    /* Noticias (3 tabs, default "universe") */
    function NewsCard({ data }) {
      const [tab, setTab] = React.useState('universe');
      const allNews = data?.news || [];
      const openSyms = new Set((data?.open_trades||[]).map(t=>t.symbol));
      const univSyms = new Set((data?.symbols_universe||[]).map(s=>s.symbol));

      const filtered = {
        universe: allNews.filter(n => univSyms.has(n.symbol)),
        all: allNews,
        positions: allNews.filter(n => openSyms.has(n.symbol)),
      };
      const items = filtered[tab] || [];
      const sentColor = s => s==='positive'?'var(--green)':s==='negative'?'var(--red)':'var(--dim)';

      return (
        <div className="card fade-up">
          <div className="ch">
            <span className="ct">Noticias IBKR</span>
            <div className="tabs">
              {[['universe','Mi universo'],['all','Todas'],['positions','Posiciones']].map(([k,l])=>(
                <button key={k} className={`tab${tab===k?' on':''}`} onClick={()=>setTab(k)}>{l}</button>
              ))}
            </div>
          </div>
          <div style={{padding:'0 12px'}}>
            {!items.length && <div style={{padding:'16px 0',textAlign:'center',fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dimmer)'}}>// sin noticias en caché aún</div>}
            {items.slice(0,5).map((n,i)=>(
              <div key={i} style={{padding:'9px 0',borderBottom:'1px solid var(--border)',display:'flex',gap:10}}>
                <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1rem',minWidth:44,color:'var(--text)'}}>{n.symbol||'MKT'}</span>
                <div>
                  {n.url ? (
                    <a href={n.url} target="_blank" rel="noopener noreferrer" style={{fontSize:'.8rem',lineHeight:1.35,color:'var(--text)',marginBottom:3,display:'block',textDecoration:'underline',textUnderlineOffset:2}}>{n.headline}</a>
                  ) : (
                    <p style={{fontSize:'.8rem',lineHeight:1.35,color:'var(--text)',marginBottom:3}}>{n.headline}</p>
                  )}
                  <div style={{display:'flex',gap:8,fontFamily:'"Fira Code",monospace',fontSize:'.63rem',color:'var(--dim)'}}>
                    <span>{n.provider}</span>
                    <span>{n.fetched_at?.slice(11,16)||''}</span>
                    <span style={{padding:'1px 5px',borderRadius:3,border:'1px solid',fontSize:'.62rem',
                      color:sentColor(n.sentiment),borderColor:sentColor(n.sentiment)+'44',
                      background:sentColor(n.sentiment)+'11'}}>{n.sentiment||'neutral'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    /* Market Trends (6 tabs) */
    function MarketTrendsCard({ data }) {
      const [tab, setTab] = React.useState('most_active');
      const scanner = data?.scanner || {};

      const tabs = [
        ['most_active','Más activos'],['top_movers','Top Movers'],
        ['gainers','Gainers'],['losers','Losers'],
        ['sector','Sectores'],['implied_move','Implied Move'],
      ];

      async function proposeSymbol(symbol) {
        try {
          await fetch('/symbols/propose', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({symbol, reason:'Added from Market Trends dashboard'})});
        } catch(e) {}
      }

      async function analyzeFromTrends(symbol) {
        try {
          await fetch('/analyze/' + symbol, {method:'POST'});
        } catch(e) {}
      }

      const rows = scanner[tab] || [];

      return (
        <div className="card fade-up">
          <div className="ch">
            <span className="ct">Market Trends</span>
            <div className="tabs">
              {tabs.map(([k,l])=>(
                <button key={k} className={`tab${tab===k?' on':''}`} onClick={()=>setTab(k)}>{l}</button>
              ))}
            </div>
          </div>
          <div style={{padding:'0 12px'}}>
            {!rows.length && <div style={{padding:'14px 0',textAlign:'center',fontFamily:'"Fira Code",monospace',fontSize:'.72rem',color:'var(--dimmer)'}}>// actualizando cada 5min...</div>}
            {tab === 'sector' ? (
              <div style={{display:'flex',flexDirection:'column',gap:6,padding:'10px 0'}}>
                {rows.map((r,i)=>{
                  const pct = r.change_pct == null ? null : parseFloat(r.change_pct);
                  const color = (pct ?? 0)>=0?'var(--green)':'var(--red)';
                  return (
                    <div key={i} style={{display:'flex',alignItems:'center',gap:8,fontFamily:'"Fira Code",monospace',fontSize:'.73rem'}}>
                      <span style={{width:36,color:'var(--text)',fontWeight:500}}>{r.symbol}</span>
                      <span style={{width:80,color:'var(--muted)',fontSize:'.68rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name}</span>
                      <div style={{flex:1,height:7,borderRadius:4,background:'rgba(255,255,255,.04)',overflow:'hidden'}}>
                        <div style={{height:'100%',width:`${Math.min(Math.abs(pct ?? 0)*10,100)}%`,background:color,borderRadius:4}}/>
                      </div>
                      <span style={{color,width:44,textAlign:'right'}}>{pct == null ? '—' : `${pct>=0?'+':''}${pct.toFixed(1)}%`}</span>
                    </div>
                  );
                })}
              </div>
            ) : tab === 'implied_move' ? (
              <div style={{display:'flex',flexDirection:'column',gap:4,padding:'8px 0'}}>
                {rows.map((r,i)=>{
                  const move = r.change_pct == null ? null : parseFloat(r.change_pct);
                  const color = (move ?? 0)>3?'var(--amber)':'var(--green)';
                  return (
                    <div key={i} style={{display:'flex',alignItems:'center',gap:8,fontFamily:'"Fira Code",monospace',fontSize:'.73rem'}}>
                      <span style={{width:48,color:'var(--text)',fontWeight:500,fontFamily:'"Bebas Neue",cursive',fontSize:'1rem'}}>{r.symbol}</span>
                      <div style={{flex:1,height:7,borderRadius:4,background:'rgba(255,255,255,.04)',overflow:'hidden'}}>
                        <div style={{height:'100%',width:`${Math.min((move ?? 0)*12,100)}%`,background:color,borderRadius:4}}/>
                      </div>
                      <span style={{color,width:44,textAlign:'right'}}>{move == null ? '—' : `±${move.toFixed(1)}%`}</span>
                      <span style={{color:'var(--dimmer)',fontSize:'.63rem'}}>7d</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div>
                <div style={{padding:'5px 0 3px',fontFamily:'"Fira Code",monospace',fontSize:'.63rem',color:'var(--dimmer)'}}>
                  {tab==='most_active'?'Most active by volume':tab==='top_movers'?'Largest % moves':tab==='gainers'?'Top gainers':'Top losers'} · 5min
                </div>
                {rows.slice(0,6).map((r,i)=>{
                  const pct = r.change_pct == null ? null : parseFloat(r.change_pct);
                  const vr = r.volume_ratio == null ? null : parseFloat(r.volume_ratio);
                  return (
                    <div key={i} style={{display:'grid',gridTemplateColumns:'48px 1fr 60px 55px 66px',alignItems:'center',padding:'6px 0',borderBottom:'1px solid var(--border)',gap:4,fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                      <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.05rem',color:'var(--text)'}}>{r.symbol}</span>
                      <span style={{color:'var(--muted)',fontSize:'.68rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name||''}</span>
                      <span style={{color:(pct ?? 0)>=0?'var(--green)':'var(--red)'}}>{pct == null ? '—' : `${pct>=0?'+':''}${pct.toFixed(1)}%`}</span>
                      <span style={{padding:'1px 5px',borderRadius:3,fontSize:'.63rem',
                        background:(vr ?? 0)>2?'var(--green-bg)':'var(--amber-bg)',
                        color:(vr ?? 0)>2?'var(--green)':'var(--amber)',
                        border:`1px solid ${(vr ?? 0)>2?'rgba(16,185,129,.25)':'rgba(251,191,36,.2)'}`}}>{vr == null ? '—' : `${vr.toFixed(1)}×`}</span>
                      <div style={{display:'flex',gap:4}}>
                        <button onClick={()=>analyzeFromTrends(r.symbol)}
                          style={{background:'rgba(56,189,248,.08)',color:'var(--blue)',border:'1px solid rgba(56,189,248,.25)',padding:'2px 6px',borderRadius:3,fontSize:'.67rem',cursor:'pointer',fontFamily:'"Fira Code",monospace'}}>
                          📊 Ver
                        </button>
                        <button onClick={()=>proposeSymbol(r.symbol)}
                          style={{background:'var(--blue-bg)',color:'var(--blue)',border:'1px solid rgba(56,189,248,.25)',padding:'2px 6px',borderRadius:3,fontSize:'.67rem',cursor:'pointer',fontFamily:'"Fira Code",monospace'}}>
                          +
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      );
    }

    /* Daily Watchlist — hourly opportunity candidates */
    function DailyWatchlist({ data }) {
      const items = data?.daily_watchlist || [];
      if (!items.length) return null;

      return (
        <div className="card fade-up">
          <div className="ch">
            <span className="ct">🎯 Oportunidades del Día</span>
            <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.67rem',color:'var(--dim)'}}>
              {items.length} candidatos · actualiza cada hora
            </span>
          </div>
          <div style={{padding:'0 12px'}}>
            {items.slice(0,8).map((item, i) => {
              const signalColor = item.signal_strength === 'STRONG' ? 'var(--green)' : 'var(--amber)';
              const changePos = (item.change_pct || 0) >= 0;
              return (
                <div key={i} style={{display:'grid',gridTemplateColumns:'52px 1fr 55px 55px 55px 70px',
                  alignItems:'center',padding:'6px 0',borderBottom:'1px solid var(--border)',
                  gap:6,fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.05rem',color:'var(--text)'}}>{item.symbol}</span>
                  <span style={{color:'var(--dim)',fontSize:'.65rem',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{item.reason?.split(':')[0] || ''}</span>
                  <span style={{color: changePos ? 'var(--green)' : 'var(--red)'}}>
                    {(item.change_pct||0) >= 0 ? '+' : ''}{(item.change_pct||0).toFixed(1)}%
                  </span>
                  <span style={{color: signalColor, fontSize:'.65rem'}}>{item.signal_strength}</span>
                  <span style={{color:'var(--blue)'}}>{(item.score||0).toFixed(0)}/100</span>
                  <button onClick={() => window.open('/analyze-page/'+item.symbol,'_blank')}
                    style={{background:'var(--blue-bg)',color:'var(--blue)',border:'1px solid rgba(56,189,248,.25)',
                      padding:'2px 8px',borderRadius:3,fontSize:'.67rem',cursor:'pointer',fontFamily:'"Fira Code",monospace'}}>
                    📊 Analizar
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    /* Mi Universo table */
    function UniversoTable({ data }) {
      const syms = data?.symbols_universe || [];
      if (!syms.length) return null;

      async function recalibrate(symbol) {
        try {
          await fetch(`/symbols/approve/${symbol}`, {method:'POST'});
          alert(`Recalibración solicitada para ${symbol}. Revisa Telegram o logs para confirmar la ejecución real.`);
        } catch(e) {}
      }

      return (
        <div className="card fade-up">
          <div className="ch"><span className="ct">Mi Universo — Entrenamiento y Backtesting</span></div>
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%',borderCollapse:'collapse',fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
              <thead>
                <tr>
                  {['SYM','CALIBRADO','SL%','TP%','P.FACTOR','WIN RATE','TRADES','APRENDIZAJE','ÚLTIMA CAL.',''].map(h=>(
                    <th key={h} style={{color:'var(--dim)',fontWeight:500,padding:'5px 8px',textAlign:'left',borderBottom:'1px solid var(--border)',whiteSpace:'nowrap'}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {syms.map(s=>(
                  <tr key={s.symbol} style={{borderBottom:'1px solid var(--border)'}}>
                    <td style={{padding:'5px 8px',color:'var(--text)',fontWeight:500}}>
                      {s.symbol}
                      {s.is_open && (
                        <span style={{
                          marginLeft: 6,
                          background:'var(--green-bg)',
                          color:'var(--green)',
                          border:'1px solid rgba(16,185,129,.3)',
                          padding:'1px 6px',
                          borderRadius:3,
                          fontSize:'.63rem'
                        }}>OPEN</span>
                      )}
                    </td>
                    <td style={{padding:'5px 8px'}}>
                      {s.backtest_calibrated
                        ? <span style={{background:'var(--green-bg)',color:'var(--green)',border:'1px solid rgba(16,185,129,.3)',padding:'1px 6px',borderRadius:3,fontSize:'.63rem'}}>✓ backtest</span>
                        : <span style={{background:'rgba(100,116,139,.1)',color:'var(--dim)',border:'1px solid var(--border)',padding:'1px 6px',borderRadius:3,fontSize:'.63rem'}}>defaults</span>}
                    </td>
                    <td style={{padding:'5px 8px',color:'var(--muted)'}}>{((s.stop_loss_pct||0)*100).toFixed(1)}%</td>
                    <td style={{padding:'5px 8px',color:'var(--muted)'}}>{((s.take_profit_pct||0)*100).toFixed(1)}%</td>
                    <td style={{padding:'5px 8px',color:'var(--muted)'}}>{s.backtest_profit_factor?.toFixed(2)||'—'}</td>
                    <td style={{padding:'5px 8px',color:s.win_rate>=.5?'var(--green)':s.win_rate!=null?'var(--red)':'var(--dim)'}}>
                      {s.win_rate!=null?`${(s.win_rate*100).toFixed(0)}%`:'—'}
                    </td>
                    <td style={{padding:'5px 8px',color:'var(--muted)'}}>{s.trade_count}</td>
                    <td style={{padding:'5px 8px',maxWidth:120}}>
                      {Object.entries(s.multipliers_drifted||{}).map(([k,v])=>(
                        <span key={k} style={{marginRight:4,fontSize:'.63rem',color:v>1?'var(--green)':'var(--amber)'}}>
                          {k.slice(0,3)} {v>1?'▲':'▼'}{v.toFixed(2)}
                        </span>
                      ))}
                    </td>
                    <td style={{padding:'5px 8px',color:'var(--dimmer)'}}>{s.backtest_calibrated_at?.slice(0,10)||'—'}</td>
                    <td style={{padding:'5px 8px'}}>
                      <button onClick={()=>recalibrate(s.symbol)}
                        style={{background:'var(--blue-bg)',color:'var(--blue)',border:'1px solid rgba(56,189,248,.25)',
                          padding:'2px 8px',borderRadius:3,fontSize:'.67rem',cursor:'pointer',fontFamily:'"Fira Code",monospace'}}>
                        ↻ Recal.
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    /* Control Bar */
    function ControlBar({ data }) {
      const mode = (data?.status?.mode||'paper').toUpperCase();
      const paused = data?.status?.paused;
      const ibConn = data?.ib_connected;

      async function toggleScanner() {
        if (!ibConn) return;
        const ep = paused ? '/system/resume' : '/system/pause';
        await fetch(ep, {method:'POST'}).catch(()=>{});
      }

      async function setNotifLevel(level) {
        await fetch(`/notifications/level/${level}`, {method:'POST'}).catch(()=>{});
      }

      return (
        <div className="card fade-up">
          <div className="ch"><span className="ct">Control del Sistema</span></div>
          <div style={{padding:'10px 12px',display:'flex',flexWrap:'wrap',alignItems:'center',gap:14}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:'.68rem',color:'var(--dim)',fontFamily:'"Fira Code",monospace'}}>SCANNER</span>
              <button onClick={toggleScanner} disabled={!ibConn}
                style={{padding:'3px 10px',borderRadius:4,fontSize:'.78rem',fontFamily:'"Barlow Condensed",sans-serif',
                  fontWeight:700,letterSpacing:'.04em',cursor:ibConn?'pointer':'not-allowed',border:'1px solid',
                  background: paused?'var(--red-bg)':'var(--green-bg)',
                  color: paused?'var(--red)':'var(--green)',
                  borderColor: paused?'rgba(244,63,94,.3)':'rgba(16,185,129,.3)'}}>
                {paused ? '⏸ PAUSADO' : '▶ ACTIVO'}
              </button>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:'.68rem',color:'var(--dim)',fontFamily:'"Fira Code",monospace'}}>NOTIF</span>
              {['critico','normal','verbose'].map(l=>(
                <button key={l} onClick={()=>setNotifLevel(l)}
                  style={{padding:'3px 8px',borderRadius:3,fontSize:'.68rem',fontFamily:'"Fira Code",monospace',
                    cursor:'pointer',border:'1px solid var(--border)',background:'transparent',color:'var(--muted)'}}>
                  {l}
                </button>
              ))}
            </div>
            <span style={{marginLeft:'auto',fontFamily:'"Fira Code",monospace',fontSize:'.64rem',color:'var(--dimmer)'}}>
              ⚡ cerrar posición / pausar → confirmación Telegram
            </span>
          </div>
        </div>
      );
    }

    /* ── Main App ── */
    function App() {
      const [data, setData] = useState(null);
      const [err, setErr] = useState(null);
      const [updated, setUpdated] = useState('');
      const [tick, setTick] = useState(0);

      const load = useCallback(async () => {
        try {
          const res = await fetch('/dashboard/data');
          if (!res.ok) throw new Error('HTTP ' + res.status);
          setData(await res.json());
          setErr(null);
          setUpdated(new Date().toLocaleTimeString('es-MX',
            {hour:'2-digit',minute:'2-digit',second:'2-digit'}));
        } catch(e) { setErr(e.message); }
      }, []);

      useEffect(() => { load(); }, [tick, load]);

      // Smart refresh: 15s with open positions, 60s without
      const interval = data?.open_trades?.length > 0 ? 15 : 60;

      const ibConnected = data?.ib_connected;

      async function toggleScanner() {
        if (!ibConnected) return;
        const paused = data?.status?.paused;
        const ep = paused ? '/system/resume' : '/system/pause';
        await fetch(ep, {method:'POST'}).catch(()=>{});
        load();
      }

      return (
        <div style={{minHeight:'100vh',background:'var(--bg)'}}>

          <IbStatusBar ibConnected={ibConnected} />

          <SystemStatusBar />

          <Header data={data} interval={interval} onTick={() => setTick(k => k+1)} onTogglePause={toggleScanner} onRefresh={async () => {
            try { await fetch('/refresh', {method:'POST'}); } catch(e) {}
            setTick(k => k+1);
          }} />

          <div className="page">

            <StatCards data={data} />

            <div className="row-2">
              <div className="card fade-up">
                <div className="ch">
                  <span className="ct">Posiciones Abiertas</span>
                  <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',color:'var(--muted)'}}>
                    P&amp;L live · {updated || '—'}
                  </span>
                </div>
                <div className="cb">
                  <OpenPositions data={data} />
                </div>
              </div>

              <MiCuenta data={data} />
            </div>

            <SymbolChart data={data} />

            <div className="row-2">
              <NewsCard data={data} />
              <MarketTrendsCard data={data} />
            </div>

            <DailyWatchlist data={data} />

            <div className="row-2">
              <div className="card fade-up">
                <div className="ch"><span className="ct">Señales Detectadas</span></div>
                <div className="cb"><Signals signals={data?.signals} /></div>
              </div>

              <div className="card fade-up">
                <div className="ch"><span className="ct">Historial Reciente</span></div>
                <div className="cb"><History closed={data?.closed_trades} /></div>
              </div>
            </div>

            <div className="card fade-up">
              <div className="ch">
                <span className="ct">Motor de Aprendizaje</span>
                <span style={{
                  display:'inline-block',width:8,height:8,borderRadius:'50%',
                  background: data?.learning?.model_trained ? 'var(--blue)' : 'var(--border)',
                  boxShadow: data?.learning?.model_trained ? '0 0 6px var(--blue)' : 'none',
                }} className={data?.learning?.model_trained ? 'pulse' : ''}></span>
              </div>
              <div className="cb"><Learning data={data?.learning} /></div>
            </div>

            <UniversoTable data={data} />
            <ControlBar data={data} />

            {err && (
              <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.75rem',
                color:'var(--red)',padding:'8px 12px',
                background:'var(--red-bg)',border:'1px solid rgba(244,63,94,.3)',borderRadius:6}}>
                ⚠ {err}
              </div>
            )}

            <LogViewer />

          </div>

          <div className="footer">
            {data
              ? (data.open_trades?.length||0) + ' posiciones · ' +
                (data.closed_trades?.length||0) + ' trades cerrados · ' +
                (data.patterns?.length||0) + ' patrones'
              : 'cargando...'}
            &nbsp;·&nbsp;:8088/dashboard
          </div>

        </div>
      );
    }

    function LogViewer() {
      const [logs, setLogs] = React.useState('');
      const [open, setOpen] = React.useState(false);
      const [lines, setLines] = React.useState(100);

      async function loadLogs() {
        const res = await fetch(`/logs?lines=${lines}`);
        const d = await res.json();
        setLogs(d.log || '');
        setOpen(true);
      }

      return (
        <div>
          <div style={{display:'flex', gap:8, alignItems:'center', marginBottom: open ? 8 : 0}}>
            <button onClick={loadLogs} style={{
              background:'var(--surface2)', border:'1px solid var(--border)',
              color:'var(--muted)', padding:'4px 10px', borderRadius:4,
              fontFamily:'"Fira Code",monospace', fontSize:'.72rem', cursor:'pointer'
            }}>📋 Logs recientes</button>
            {[50,100,500].map(n => (
              <button key={n} onClick={() => { setLines(n); }} style={{
                background: lines===n ? 'var(--blue-bg)' : 'var(--surface2)',
                border:`1px solid ${lines===n ? 'rgba(56,189,248,.3)' : 'var(--border)'}`,
                color: lines===n ? 'var(--blue)' : 'var(--dim)',
                padding:'3px 8px', borderRadius:3,
                fontFamily:'"Fira Code",monospace', fontSize:'.68rem', cursor:'pointer'
              }}>{n} líneas</button>
            ))}
            {open && <button onClick={() => setOpen(false)} style={{
              background:'transparent', border:'none', color:'var(--dim)', cursor:'pointer', fontSize:'.8rem'
            }}>✕</button>}
          </div>
          {open && (
            <div style={{
              background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:6,
              padding:12, maxHeight:400, overflowY:'auto',
              fontFamily:'"Fira Code",monospace', fontSize:'.68rem', lineHeight:1.5
            }}>
              <pre style={{color:'var(--muted)', whiteSpace:'pre-wrap', wordBreak:'break-all', margin:0}}>
                {logs || '// sin logs'}
              </pre>
            </div>
          )}
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById('root')).render(<App />);
  </script>
</body>
</html>"""


# Legacy shim — kept so old import still works if referenced anywhere
def render_dashboard(status, trades, closed_trades, signals, patterns) -> str:
    return render_dashboard_html()
