"""
IBKR AI Trader — React dashboard.
Served as HTML from /dashboard. All data fetched client-side from /dashboard/data.
No build step — React + Tailwind via CDN.
"""


def render_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IBKR AI Trader</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Fira+Code:wght@300;400;500&family=Barlow+Condensed:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            bebas: ['"Bebas Neue"', 'cursive'],
            fira:  ['"Fira Code"', 'monospace'],
            ui:    ['"Barlow Condensed"', 'sans-serif'],
          },
        }
      }
    }
  </script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#06090F;color:#CBD5E1;font-family:"Barlow Condensed",sans-serif;-webkit-font-smoothing:antialiased}
    ::-webkit-scrollbar{width:4px;height:4px}
    ::-webkit-scrollbar-track{background:#06090F}
    ::-webkit-scrollbar-thumb{background:#1E2D42;border-radius:2px}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    @keyframes glow-green{0%,100%{box-shadow:0 0 6px rgba(16,185,129,.4)}50%{box-shadow:0 0 14px rgba(16,185,129,.7)}}
    .pulse{animation:pulse 2s ease-in-out infinite}
    .fade-up{animation:fadeUp .35s ease both}
    .badge-strong{background:rgba(16,185,129,.12);color:#10B981;border:1px solid rgba(16,185,129,.35);animation:glow-green 2.5s ease-in-out infinite}
    .badge-medium{background:rgba(245,158,11,.12);color:#F59E0B;border:1px solid rgba(245,158,11,.3)}
    .badge-weak{background:rgba(100,116,139,.1);color:#64748B;border:1px solid rgba(100,116,139,.2)}
    .badge-none{background:rgba(51,65,85,.1);color:#334155;border:1px solid rgba(51,65,85,.15)}
    .card{background:#0C1421;border:1px solid #1E2D42;border-radius:.5rem;overflow:hidden}
    .card-head{background:#111D2E;border-bottom:1px solid #1E2D42;padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between}
    .card-label{font-family:"Barlow Condensed",sans-serif;font-size:.7rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#475569}
    .trend-bull{color:#38BDF8;background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.2);font-size:.65rem;padding:.1rem .4rem;border-radius:.25rem;font-family:"Fira Code",monospace}
    .trend-bear{color:#F43F5E;background:rgba(244,63,94,.1);border:1px solid rgba(244,63,94,.2);font-size:.65rem;padding:.1rem .4rem;border-radius:.25rem;font-family:"Fira Code",monospace}
    table{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.75rem}
    th{color:#374151;font-weight:400;padding:.4rem .5rem;text-align:left;border-bottom:1px solid #1E2D42;white-space:nowrap}
    td{padding:.45rem .5rem;border-bottom:1px solid rgba(30,45,66,.5);white-space:nowrap}
    tr:hover td{background:rgba(17,29,46,.7)}
    .meter-track{background:#111D2E;height:4px;border-radius:2px;overflow:hidden;flex:1}
    .meter-fill{height:100%;border-radius:2px;transition:width .6s ease}
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    const { useState, useEffect, useCallback } = React;

    /* ── Formatting helpers ── */
    const f = {
      usd:   v => v == null ? '—' : `$${parseFloat(v).toFixed(2)}`,
      pct:   v => v == null ? '—' : `${parseFloat(v) >= 0 ? '+' : ''}${parseFloat(v).toFixed(2)}%`,
      n:     (v, d=1) => v == null ? '—' : parseFloat(v).toFixed(d),
      time:  v => v ? String(v).slice(11,16) : '—',
      date:  v => v ? String(v).slice(2,16).replace('T',' ') : '—',
    };

    /* ── Components ── */

    function Badge({ s }) {
      const map = {STRONG:'badge-strong',MEDIUM:'badge-medium',WEAK:'badge-weak'};
      const cls = map[s] || 'badge-none';
      return (
        <span className={`inline-block px-2 py-0.5 rounded text-xs font-fira tracking-widest ${cls}`}>
          {s || '—'}
        </span>
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

    function Card({ title, right, children }) {
      return (
        <div className="card fade-up">
          <div className="card-head">
            <span className="card-label">{title}</span>
            {right && <div>{right}</div>}
          </div>
          <div style={{padding:'1rem'}}>{children}</div>
        </div>
      );
    }

    function Empty({ msg }) {
      return (
        <p style={{color:'#374151',fontFamily:'"Fira Code",monospace',fontSize:'.75rem',
          padding:'1.5rem 0',textAlign:'center',letterSpacing:'.05em'}}>
          {msg}
        </p>
      );
    }

    function StatCard({ label, value, sub, accent }) {
      return (
        <div className="card fade-up" style={{padding:'1rem'}}>
          <div style={{color:'#475569',fontSize:'.7rem',fontWeight:600,letterSpacing:'.12em',
            textTransform:'uppercase',marginBottom:'.25rem'}}>{label}</div>
          <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'2.8rem',lineHeight:1,
            color: accent || '#E2E8F0'}}>{value}</div>
          {sub && <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
            color:'#475569',marginTop:'.2rem'}}>{sub}</div>}
        </div>
      );
    }

    function Dot({ active, color='#0EA5E9' }) {
      return (
        <span style={{display:'inline-block',width:8,height:8,borderRadius:'50%',
          background: active ? color : '#1E2D42',
          boxShadow: active ? `0 0 6px ${color}` : 'none'}}
          className={active ? 'pulse' : ''} />
      );
    }

    function WinBar({ symbol, rate }) {
      const pct = Math.round((rate || 0) * 100);
      const fill = pct >= 55 ? '#10B981' : pct >= 40 ? '#F59E0B' : '#F43F5E';
      return (
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
            color:'#475569',width:44,flexShrink:0}}>{symbol}</span>
          <div className="meter-track">
            <div className="meter-fill" style={{width:`${pct}%`,background:fill}} />
          </div>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
            color:'#475569',width:32,textAlign:'right',flexShrink:0}}>{pct}%</span>
        </div>
      );
    }

    /* ── Panels ── */

    function OpenPositions({ trades }) {
      if (!trades?.length) return <Empty msg="// sin posiciones abiertas" />;
      return (
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {trades.map((t,i) => (
            <div key={i} className="fade-up" style={{background:'#111D2E',border:'1px solid #1E2D42',
              borderRadius:6,padding:'10px 12px'}}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:6}}>
                <div style={{display:'flex',alignItems:'center',gap:8}}>
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.35rem',
                    letterSpacing:'.06em',color:'#E2E8F0'}}>{t.symbol}</span>
                  <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
                    padding:'1px 6px',borderRadius:4,
                    background: t.action==='BUY' ? 'rgba(16,185,129,.15)' : 'rgba(244,63,94,.15)',
                    color: t.action==='BUY' ? '#10B981' : '#F43F5E'}}>
                    {t.action}
                  </span>
                  <Badge s={t.signal_strength} />
                </div>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'#374151'}}>
                  {t.quantity} u
                </span>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:4,
                fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                <div><span style={{color:'#374151'}}>ENTRY </span>
                  <span style={{color:'#94A3B8'}}>{f.usd(t.entry_price)}</span></div>
                <div><span style={{color:'#374151'}}>SL </span>
                  <span style={{color:'#F43F5E'}}>{f.usd(t.stop_loss_price)}</span></div>
                <div><span style={{color:'#374151'}}>TP </span>
                  <span style={{color:'#10B981'}}>{f.usd(t.take_profit_price)}</span></div>
              </div>
            </div>
          ))}
        </div>
      );
    }

    function Signals({ signals }) {
      if (!signals?.length) return <Empty msg="// sin señales recientes" />;
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
                    <td style={{color:'#CBD5E1',fontWeight:500}}>{s.symbol}</td>
                    <td><Badge s={s.strength} /></td>
                    <td style={{textAlign:'right',color:'#94A3B8'}}>{s.rsi ? f.n(s.rsi) : '—'}</td>
                    <td style={{textAlign:'right',color:'#94A3B8'}}>
                      {s.volume_ratio ? f.n(s.volume_ratio,1)+'x' : '—'}
                    </td>
                    <td><TrendChip trend={extra.weekly_trend} /></td>
                    <td style={{textAlign:'right',color:'#374151'}}>{f.time(s.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    function History({ closed }) {
      if (!closed?.length) return <Empty msg="// sin historial" />;
      return (
        <div style={{overflowX:'auto'}}>
          <table>
            <thead>
              <tr>
                <th>SYM</th><th>ACT</th><th style={{textAlign:'right'}}>P&L $</th>
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
                    <td style={{color:'#CBD5E1',fontWeight:500}}>{t.symbol}</td>
                    <td style={{color: t.action==='BUY' ? '#10B981' : '#F43F5E'}}>{t.action}</td>
                    <td style={{textAlign:'right',fontWeight:500,
                      color: win ? '#10B981' : '#F43F5E'}}>{f.usd(pnl)}</td>
                    <td style={{textAlign:'right',
                      color: win ? '#10B981' : '#F43F5E'}}>{f.pct(pct * 100)}</td>
                    <td style={{color:'#475569',maxWidth:100,overflow:'hidden',
                      textOverflow:'ellipsis'}}>
                      {(t.exit_reason||'—').replace(/_/g,' ')}
                    </td>
                    <td style={{textAlign:'right',color:'#374151'}}>{f.date(t.closed_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    function Learning({ data }) {
      const { model_trained, win_rates, total_trades, pkl_age_hours } = data || {};
      const hasRates = win_rates && Object.keys(win_rates).length > 0;
      return (
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          {/* Model status */}
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <Dot active={model_trained} color="#0EA5E9" />
            <div>
              <div style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.6rem',
                color: model_trained ? '#0EA5E9' : '#374151',lineHeight:1}}>
                {model_trained ? 'MODELO ACTIVO' : 'SIN MODELO'}
              </div>
              <div style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',color:'#374151'}}>
                {model_trained && pkl_age_hours != null
                  ? `actualizado hace ${pkl_age_hours < 1 ? '<1h' : Math.round(pkl_age_hours)+'h'}`
                  : total_trades >= 10 ? 'pendiente: siguiente ciclo 17:05 ET' : `${total_trades||0} trades (mín 10)`}
              </div>
            </div>
          </div>
          {/* Win rates */}
          {hasRates && (
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              <div className="card-label" style={{marginBottom:2}}>Win Rate / Símbolo</div>
              {Object.entries(win_rates)
                .sort(([,a],[,b]) => b - a)
                .slice(0, 7)
                .map(([sym, rate]) => <WinBar key={sym} symbol={sym} rate={rate} />)}
            </div>
          )}
          {!hasRates && (
            <Empty msg="// win rates disponibles con 3+ trades por símbolo" />
          )}
        </div>
      );
    }

    function Patterns({ patterns }) {
      if (!patterns?.length) return null;
      return (
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))',gap:8}}>
          {patterns.slice(0,6).map((p,i) => {
            const w = p.wins || 0, l = p.losses || 0, tot = w + l;
            const wr = tot > 0 ? Math.round(w/tot*100) : 0;
            return (
              <div key={i} className="fade-up"
                style={{background:'#111D2E',border:'1px solid #1E2D42',borderRadius:6,padding:'10px 12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',
                  alignItems:'center',marginBottom:4}}>
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',
                    color:'#94A3B8',letterSpacing:'.06em'}}>{p.symbol}</span>
                  <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',
                    color: wr>=50 ? '#10B981' : '#F43F5E'}}>
                    {wr}% ({w}W/{l}L)
                  </span>
                </div>
                <p style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',
                  color:'#374151',lineHeight:1.5,
                  overflow:'hidden',display:'-webkit-box',WebkitLineClamp:2,
                  WebkitBoxOrient:'vertical'}}>
                  {p.pattern_text || p.pattern}
                </p>
              </div>
            );
          })}
        </div>
      );
    }

    /* ── Countdown ── */
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
      }, [total]);
      const pct = (rem / total) * 100;
      return (
        <div style={{display:'flex',alignItems:'center',gap:6}}>
          <div style={{width:24,height:24,position:'relative',flexShrink:0}}>
            <svg viewBox="0 0 24 24" style={{width:24,height:24,transform:'rotate(-90deg)'}}>
              <circle cx="12" cy="12" r="9" fill="none" stroke="#1E2D42" strokeWidth="2"/>
              <circle cx="12" cy="12" r="9" fill="none" stroke="#0EA5E9" strokeWidth="2"
                strokeDasharray={`${2*Math.PI*9}`}
                strokeDashoffset={`${2*Math.PI*9*(1-pct/100)}`}
                style={{transition:'stroke-dashoffset 1s linear'}}/>
            </svg>
          </div>
          <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.68rem',color:'#374151'}}>
            {rem}s
          </span>
        </div>
      );
    }

    /* ── Main App ── */
    function App() {
      const [data,    setData]    = useState(null);
      const [err,     setErr]     = useState(null);
      const [updated, setUpdated] = useState('');
      const [tick,    setTick]    = useState(0);

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

      useEffect(() => { load(); }, [tick]);

      const st = data?.status || {};
      const pnl = parseFloat(st.daily_pnl_usd || 0);
      const pct = parseFloat(st.daily_pnl_pct || 0);
      const isLive = (st.mode||'paper').toUpperCase() === 'LIVE';
      const cap = st.operating_capital || st.simulated_capital || 500;

      return (
        <div style={{minHeight:'100vh',background:'#06090F'}}>

          {/* ── Header ── */}
          <header style={{background:'#0C1421',borderBottom:'1px solid #1E2D42',
            position:'sticky',top:0,zIndex:10}}>
            <div style={{maxWidth:1280,margin:'0 auto',padding:'.75rem 1rem',
              display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:8}}>

              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <div style={{display:'flex',alignItems:'center',gap:6}}>
                  <Dot active={!err} color={isLive ? '#F59E0B' : '#10B981'} />
                  <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.4rem',
                    letterSpacing:'.12em',color:'#E2E8F0'}}>IBKR AI TRADER</span>
                </div>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
                  padding:'2px 8px',borderRadius:4,
                  background: isLive ? 'rgba(245,158,11,.12)' : 'rgba(16,185,129,.12)',
                  color: isLive ? '#F59E0B' : '#10B981',
                  border: `1px solid ${isLive ? 'rgba(245,158,11,.3)' : 'rgba(16,185,129,.3)'}` }}>
                  {isLive ? 'LIVE' : 'PAPER'}
                </span>
                {st.paused && (
                  <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',
                    padding:'2px 8px',borderRadius:4,
                    background:'rgba(100,116,139,.1)',color:'#64748B',
                    border:'1px solid rgba(100,116,139,.25)'}}>PAUSADO</span>
                )}
              </div>

              <div style={{display:'flex',alignItems:'center',gap:12}}>
                {err && <span style={{fontFamily:'"Fira Code",monospace',
                  fontSize:'.68rem',color:'#F43F5E'}}>⚠ {err}</span>}
                {updated && <span style={{fontFamily:'"Fira Code",monospace',
                  fontSize:'.68rem',color:'#374151'}}>{updated}</span>}
                <Refresh total={30} onTick={() => setTick(k => k+1)} />
              </div>
            </div>
          </header>

          {/* ── Content ── */}
          <main style={{maxWidth:1280,margin:'0 auto',padding:'1rem',
            display:'flex',flexDirection:'column',gap:'1rem'}}>

            {/* Stats strip */}
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:8}}>
              <StatCard label="P&L Hoy"
                value={f.usd(pnl)}
                sub={f.pct(pct)}
                accent={pnl >= 0 ? '#10B981' : '#F43F5E'}
              />
              <StatCard label="Capital"
                value={`$${Math.round(cap)}`}
                accent="#0EA5E9"
              />
              <StatCard label="Posiciones"
                value={`${data?.open_trades?.length || 0}/3`}
                sub={data?.open_trades?.length ? 'activas' : 'libre'}
                accent="#E2E8F0"
              />
              <StatCard label="Señales"
                value={data?.signals?.length || 0}
                sub="pendientes"
                accent="#F59E0B"
              />
            </div>

            {/* Main grid */}
            <div style={{display:'grid',
              gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,480px),1fr))',
              gap:'1rem'}}>

              <Card title="Posiciones Abiertas">
                <OpenPositions trades={data?.open_trades} />
              </Card>

              <Card title="Señales Detectadas">
                <Signals signals={data?.signals} />
              </Card>

              <Card title="Historial Reciente">
                <History closed={data?.closed_trades} />
              </Card>

              <Card title="Motor de Aprendizaje"
                right={<Dot active={data?.learning?.model_trained} color="#0EA5E9" />}>
                <Learning data={data?.learning} />
              </Card>

            </div>

            {/* Patterns */}
            {data?.patterns?.length > 0 && (
              <Card title="Patrones Aprendidos">
                <Patterns patterns={data.patterns} />
              </Card>
            )}

          </main>

          <footer style={{maxWidth:1280,margin:'0 auto',padding:'.75rem 1rem',
            display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'#1E2D42'}}>
              {data ? `${(data.open_trades?.length||0)+(data.closed_trades?.length||0)} trades · ${data.patterns?.length||0} patrones` : ''}
            </span>
            <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'#1E2D42'}}>
              :8088/dashboard
            </span>
          </footer>

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
