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
    function Header({ data, interval, onTick }) {
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
            >⏸ Pausar</button>
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
      const buyPow = acct.buying_power || 0;
      const openCount = data?.open_trades?.length || 0;

      return (
        <div className="row-4">
          <div className="sc fade-up">
            <div className="sl">Net Liquidation</div>
            <div className="sv blue">{f.usd(netLiq)}</div>
            <div className="ss">IBKR real · cuenta</div>
          </div>
          <div className="sc fade-up">
            <div className="sl">P&amp;L Hoy</div>
            <div className={'sv ' + (pnl >= 0 ? 'green' : 'red')}>{f.usd(pnl)}</div>
            <div className="ss">{f.pct(pct * 100)} · drawdown</div>
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
      const snap = (snapshots || []).find(s => s.trade_id === trade.id) || {};
      const current = parseFloat(snap.current_price || trade.entry_price || 0);
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
        const snap = snapshots.find(s => s.trade_id === t.id) || {};
        const pnlUsd = parseFloat(snap.pnl_usd != null ? snap.pnl_usd : (t.pnl_usd || 0));
        const pnlPct = parseFloat(snap.pnl_pct != null ? snap.pnl_pct : (t.pnl_pct || 0));
        const currentPrice = snap.current_price || t.entry_price;
        const earningsDays = earningsWarnings[t.symbol];
        let extra = {};
        try { extra = JSON.parse(t.extra_indicators || '{}'); } catch(e) {}
        const trend = extra.weekly_trend;

        return (
          <div key={t.id || i} className="pos fade-up">
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
                  onClick={() => closePosition(t.id)}
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
        .map(([h, {sum, count}]) => [parseInt(h), sum / count])
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

      return (
        <div style={{minHeight:'100vh',background:'var(--bg)'}}>

          <IbStatusBar ibConnected={ibConnected} />

          <Header data={data} interval={interval} onTick={() => setTick(k => k+1)} />

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

            {err && (
              <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.75rem',
                color:'var(--red)',padding:'8px 12px',
                background:'var(--red-bg)',border:'1px solid rgba(244,63,94,.3)',borderRadius:6}}>
                ⚠ {err}
              </div>
            )}

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

    ReactDOM.createRoot(document.getElementById('root')).render(<App />);
  </script>
</body>
</html>"""


# Legacy shim — kept so old import still works if referenced anywhere
def render_dashboard(status, trades, closed_trades, signals, patterns) -> str:
    return render_dashboard_html()
