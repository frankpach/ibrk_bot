"""
IBKR AI Trader — Control Plane Frontend.
Served as HTML from /control. All data fetched client-side from /control/* endpoints.
No build step — React + Tailwind via CDN.
"""


def render_control_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Control Plane — IBKR AI Trader</title>
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
    body{background:radial-gradient(ellipse at 30% 20%,#0A1628 0%,#06090F 60%);background-attachment:fixed;color:var(--text);font-family:"Barlow Condensed",sans-serif;font-size:14px;min-height:100vh;-webkit-font-smoothing:antialiased}
    ::-webkit-scrollbar{width:4px;height:4px}
    ::-webkit-scrollbar-track{background:var(--bg)}
    ::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
    .pulse{animation:pulse 2s ease-in-out infinite}
    .fade-up{animation:fadeUp .35s ease both}

    /* ─── System Status Bar ──────────────────────────── */
    .status-bar{
      padding:6px 16px;display:flex;align-items:center;gap:12px;
      font-family:"Fira Code",monospace;font-size:.7rem;
      background:rgba(12,20,33,.88);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
      border-bottom:1px solid var(--border);border-top:2px solid var(--blue);
      flex-wrap:wrap;
      position:sticky;top:0;z-index:30;
    }
    .status-bar .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
    .status-bar a{color:var(--blue);text-decoration:none;margin-left:auto}
    .status-bar a:hover{text-decoration:underline}

    /* ─── Layout ─────────────────────────────────────── */
    .ctrl-page{display:flex;min-height:100vh}
    .sidebar{
      width:200px;background:var(--surface);border-right:1px solid var(--border);
      padding:12px 0;display:flex;flex-direction:column;gap:2px;flex-shrink:0;
    }
    .sidebar-item{
      padding:8px 16px;font-family:"Barlow Condensed",sans-serif;font-size:.85rem;
      color:var(--muted);cursor:pointer;border:none;background:transparent;text-align:left;
      letter-spacing:.02em;font-weight:600;border-left:3px solid transparent;
    }
    .sidebar-item:hover{color:var(--text);background:var(--surface2)}
    .sidebar-item.active{color:var(--blue);background:rgba(56,189,248,.08);border-left:3px solid var(--blue);box-shadow:inset 3px 0 8px rgba(56,189,248,.1)}
    .sidebar-item.active::before{content:'▸ '}
    .main{flex:1;padding:16px;overflow-y:auto;max-width:900px}

    /* ─── Cards ──────────────────────────────────────── */
    .card{background:var(--surface);border:1px solid var(--border);border-radius:7px;overflow:hidden;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.03)}
    .ch{
      background:var(--surface2);border-bottom:1px solid var(--border);border-left:2px solid var(--border);
      padding:8px 12px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;
      transition:border-left-color .2s;
    }
    .card:hover .ch{border-left-color:rgba(56,189,248,.35)}
    .ct{font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}

    /* ─── Skeleton shimmer ───────────────────────────── */
    .skel{height:.9em;border-radius:3px;background:linear-gradient(90deg,var(--border) 25%,var(--surface2) 50%,var(--border) 75%);background-size:200% 100%;animation:shimmer 1.4s ease infinite;margin:4px 0}
    .cb{padding:12px}

    /* ─── Forms ──────────────────────────────────────── */
    .field{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
    .field label{font-family:"Fira Code",monospace;font-size:.68rem;color:var(--dim)}
    .field input, .field select{
      padding:6px 10px;border-radius:5px;background:var(--surface2);border:1px solid var(--border);
      color:var(--text);font-family:"Barlow Condensed",sans-serif;font-size:.85rem;
    }
    .field .err{font-family:"Fira Code",monospace;font-size:.65rem;color:var(--red);margin-top:2px}
    .field .hint{font-family:"Fira Code",monospace;font-size:.62rem;color:var(--dimmer)}
    .btn{
      padding:5px 12px;border-radius:5px;font-family:"Barlow Condensed",sans-serif;
      font-size:.82rem;font-weight:600;letter-spacing:.04em;cursor:pointer;
      background:var(--blue);border:none;color:#fff;
    }
    .btn:disabled{opacity:.4;cursor:not-allowed}
    .btn-secondary{
      background:var(--surface2);border:1px solid var(--border);color:var(--muted);
    }
    .btn-danger{background:var(--red);border:none;color:#fff}
    .btn-warn{background:var(--amber);border:none;color:#000}

    /* ─── Tables ─────────────────────────────────────── */
    table{width:100%;border-collapse:collapse;font-family:"Fira Code",monospace;font-size:.71rem}
    th{color:var(--dim);font-weight:500;padding:5px 8px;text-align:left;border-bottom:1px solid var(--border)}
    td{padding:5px 8px;border-bottom:1px solid var(--border);color:var(--muted)}
    td.sym{color:var(--text);font-weight:500}
    tr:last-child td{border-bottom:none}

    /* ─── Toast ──────────────────────────────────────── */
    .toast{
      position:fixed;top:12px;right:12px;padding:8px 14px;border-radius:5px;
      font-family:"Fira Code",monospace;font-size:.75rem;z-index:100;
      background:var(--green-bg);color:var(--green);border:1px solid rgba(16,185,129,.3);
      animation:fadeUp .3s ease both;
    }
    .toast.err{background:var(--red-bg);color:var(--red);border:1px solid rgba(244,63,94,.3)}

    /* ─── Banner ─────────────────────────────────────── */
    .banner{
      padding:8px 12px;border-radius:5px;font-family:"Fira Code",monospace;font-size:.72rem;
      background:var(--amber-bg);color:var(--amber);border:1px solid rgba(251,191,36,.25);
      margin-bottom:12px;
    }

    /* ─── Modal ──────────────────────────────────────── */
    .modal-overlay{
      position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;z-index:50;
    }
    .modal{
      background:var(--surface);border:1px solid var(--border);border-radius:8px;
      padding:16px;width:90%;max-width:420px;
    }
    .modal h3{font-size:1.1rem;margin-bottom:10px}
    .modal p{font-size:.82rem;color:var(--muted);margin-bottom:12px}

    /* ─── Mobile sidebar ─────────────────────────── */
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
      .sidebar-item.active{border-bottom:2px solid var(--blue)!important;border-right:none;border-left:3px solid transparent!important;box-shadow:none!important}
      .sidebar-item.active::before{content:''}
      .main{padding:8px}
    }
    @media(min-width:769px){
      .main{padding:16px;flex:1;overflow-y:auto}
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
    const { useState, useEffect, useRef, useCallback } = React;

    const f = {
      usd: v => v == null ? '—' : '$' + parseFloat(v).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}),
      pct: v => v == null ? '—' : (parseFloat(v) >= 0 ? '+' : '') + parseFloat(v).toFixed(2) + '%',
    };

    /* ── SystemStatusBar (shared) ── */
    function SystemStatusBar() {
      const [status, setStatus] = useState(null);
      const [err, setErr] = useState(false);

      useEffect(() => {
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

      const navLinks = [
        {href:'/dashboard', label:'Dashboard'},
        {href:'/control',   label:'Control'},
        {href:'/reports',   label:'Reportes'},
        {href:'/docs',      label:'API Docs'},
      ];
      const path = window.location.pathname;

      return (
        <div className="status-bar">
          <span className="dot" style={{background:dotColor,boxShadow:dotColor==='var(--red)'?'none':'0 0 5px '+dotColor}} className={err?'':'pulse'}></span>
          <span style={{color:isLive?'var(--amber)':'var(--green)',fontWeight:700}}>{mode}</span>
          <span style={{color:'var(--dim)'}}>| Puerto: {port}</span>
          <span style={{color:isPaused?'var(--amber)':'var(--green)'}}>{isPaused ? '● Pausado' : '● Activo'}</span>
          <span style={{color:pnl>=0?'var(--green)':'var(--red)'}}>| P&L: {f.usd(pnl)}</span>
          <span style={{color:ibConn?'var(--green)':'var(--red)'}}>| IB: {ibConn ? '✓' : '✗'}</span>
          {err && <span style={{color:'var(--red)'}}>⚠ offline</span>}
          <span style={{flex:1}}></span>
          <nav style={{display:'flex',gap:2}}>
            {navLinks.map(({href,label})=>{
              const active = path===href || (href!=='/dashboard' && path.startsWith(href));
              return <a key={href} href={href} style={{
                fontFamily:'"Barlow Condensed",sans-serif',
                fontWeight: active?600:500, fontSize:'.8rem', letterSpacing:'.04em',
                color: active?'var(--text)':'var(--dim)', textDecoration:'none',
                padding:'2px 10px', borderRadius:4,
                background: active?'var(--surface)':'transparent',
                border: active?'1px solid var(--border)':'1px solid transparent',
              }}>{label}</a>;
            })}
          </nav>
        </div>
      );
    }

    /* ── Toast ── */
    function Toast({ msg, onClose, isError }) {
      useEffect(() => {
        const t = setTimeout(onClose, 3000);
        return () => clearTimeout(t);
      }, [onClose]);
      return <div className={"toast " + (isError ? 'err' : '')}>{msg}</div>;
    }

    /* ── ConfirmModeModal ── */
    function ConfirmModeModal({ open, onClose, onConfirm, hasPositions }) {
      const [key, setKey] = useState('');
      const [loading, setLoading] = useState(false);
      if (!open) return null;
      return (
        <div className="modal-overlay" onClick={onClose}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 style={{color:'var(--amber)'}}>⚠ Cambiar a LIVE</h3>
            {hasPositions && (
              <p style={{color:'var(--red)'}}>Hay posiciones abiertas. Cambiar a LIVE afectará ejecución real.</p>
            )}
            <p>Requiere Admin Key para confirmar.</p>
            <div className="field">
              <label>X-Admin-Key</label>
              <input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder="••••••••" />
            </div>
            <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
              <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
              <button className="btn btn-danger" disabled={!key||loading} onClick={()=>{setLoading(true);onConfirm(key).finally(()=>setLoading(false));}}>
                {loading?'...':'Confirmar LIVE'}
              </button>
            </div>
          </div>
        </div>
      );
    }

    /* ── Panels ── */

    function OperationalPanel({ status, refresh }) {
      const [modalOpen, setModalOpen] = useState(false);
      const [loadingPause, setLoadingPause] = useState(false);
      const [loadingReset, setLoadingReset] = useState(false);
      const [toast, setToast] = useState(null);

      async function togglePause() {
        setLoadingPause(true);
        try {
          const ep = status?.paused || status?.is_paused ? '/control/resume' : '/control/pause';
          const res = await fetch(ep, {method:'POST', headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||''}});
          if (!res.ok) throw new Error('HTTP ' + res.status);
          setToast({msg: '✓ Estado actualizado', err: false});
          refresh();
        } catch(e) { setToast({msg: 'Error: ' + e.message, err: true}); }
        setLoadingPause(false);
      }

      async function resetCircuit() {
        setLoadingReset(true);
        try {
          const res = await fetch('/control/circuit-breaker/reset', {method:'POST', headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||''}});
          if (!res.ok) throw new Error('HTTP ' + res.status);
          setToast({msg: '✓ Circuit breaker reset', err: false});
          refresh();
        } catch(e) { setToast({msg: 'Error: ' + e.message, err: true}); }
        setLoadingReset(false);
      }

      async function confirmMode(adminKey) {
        try {
          const res = await fetch('/control/mode/live', {
            method:'POST',
            headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||'','X-Admin-Key':adminKey}
          });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          setToast({msg: '✓ Modo cambiado a LIVE', err: false});
          setModalOpen(false);
          refresh();
        } catch(e) { setToast({msg: 'Error: ' + e.message, err: true}); throw e; }
      }

      const mode = (status?.mode||'paper').toUpperCase();
      const paused = status?.paused || status?.is_paused;

      return (
        <div>
          {toast && <Toast msg={toast.msg} isError={toast.err} onClose={()=>setToast(null)} />}
          <ConfirmModeModal open={modalOpen} onClose={()=>setModalOpen(false)} onConfirm={confirmMode} hasPositions={(status?.open_positions||0)>0} />
          <div className="card">
            <div className="ch"><span className="ct">Modo de Trading</span></div>
            <div className="cb">
              <div style={{display:'flex',gap:12,alignItems:'center',flexWrap:'wrap'}}>
                <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer'}}>
                  <input type="radio" checked={mode==='PAPER'} readOnly />
                  <span>PAPER</span>
                </label>
                <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer'}}>
                  <input type="radio" checked={mode==='LIVE'} readOnly />
                  <span>LIVE</span>
                </label>
                {mode==='PAPER' && (
                  <button className="btn btn-danger" onClick={()=>setModalOpen(true)}>Cambiar a LIVE</button>
                )}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="ch"><span className="ct">Pausa / Reanudar</span></div>
            <div className="cb">
              <button className={"btn " + (paused?"":"btn-warn")} disabled={loadingPause} onClick={togglePause}>
                {loadingPause?'...':(paused?'▶ Reanudar':'⏸ Pausar')}
              </button>
            </div>
          </div>
          <div className="card">
            <div className="ch"><span className="ct">Circuit Breaker</span></div>
            <div className="cb">
              <div style={{display:'flex',gap:10,alignItems:'center'}}>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>
                  Estado: {status?.circuit_breaker_active ? 'ACTIVADO' : 'Activo'}
                </span>
                <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.7rem',color:'var(--dim)'}}>
                  Threshold: {status?.circuit_breaker_threshold || '5%'}
                </span>
                <button className="btn btn-secondary" disabled={loadingReset} onClick={resetCircuit}>
                  {loadingReset?'...':'Reset'}
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    function RiskPanel() {
      const [settings, setSettings] = useState({});
      const [errors, setErrors] = useState({});
      const [loading, setLoading] = useState({});
      const [toast, setToast] = useState(null);
      const keys = ['max_positions','max_risk_pct','min_risk_usd','max_position_usd','capital_cap'];

      useEffect(() => {
        fetch('/control/settings').then(r=>r.json()).then(d=>{
          const map = {};
          (d.settings||[]).forEach(s=>map[s.key]=s.value);
          setSettings(map);
        }).catch(()=>{});
      }, []);

      async function save(key) {
        setLoading(prev=>({...prev,[key]:true}));
        setErrors(prev=>({...prev,[key]:null}));
        try {
          const res = await fetch(`/control/settings/${key}`, {
            method:'PUT',
            headers:{'Content-Type':'application/json','X-Control-Key':localStorage.getItem('ctrlKey')||''},
            body: JSON.stringify({value: String(settings[key])})
          });
          const data = await res.json();
          if (!res.ok) {
            const errMsg = data.detail?.error || data.detail || 'Error';
            setErrors(prev=>({...prev,[key]:errMsg}));
            setToast({msg: `✗ ${key}: ${errMsg}`, err: true});
          } else {
            setToast({msg: `✓ ${key} actualizado a ${settings[key]}`, err: false});
          }
        } catch(e) {
          setErrors(prev=>({...prev,[key]:e.message}));
        }
        setLoading(prev=>({...prev,[key]:false}));
      }

      return (
        <div>
          {toast && <Toast msg={toast.msg} isError={toast.err} onClose={()=>setToast(null)} />}
          <div className="card">
            <div className="ch"><span className="ct">Parámetros de Riesgo</span></div>
            <div className="cb">
              {keys.map(k=>{
                const labelMap = {max_positions:'Max Posiciones',max_risk_pct:'Max Riesgo %',min_risk_usd:'Min Riesgo $',max_position_usd:'Max Posición $',capital_cap:'Capital Cap'};
                return (
                  <div className="field" key={k}>
                    <label>{labelMap[k]||k}</label>
                    <div style={{display:'flex',gap:8}}>
                      <input value={settings[k]||''} onChange={e=>setSettings(prev=>({...prev,[k]:e.target.value}))} />
                      <button className="btn" disabled={loading[k]} onClick={()=>save(k)}>{loading[k]?'...':'Guardar'}</button>
                    </div>
                    {errors[k] && <div className="err">{errors[k]}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    }

    function InfraPanel() {
      const [settings, setSettings] = useState({});
      const [restartBanner, setRestartBanner] = useState(false);
      const [toast, setToast] = useState(null);
      const keys = ['ib_host','opencode_bin','opencode_model','database_url'];
      const restartKeys = ['database_url','opencode_bin'];

      useEffect(() => {
        fetch('/control/settings').then(r=>r.json()).then(d=>{
          const map={};
          (d.settings||[]).forEach(s=>{ if(keys.includes(s.key)) map[s.key]=s.value; });
          setSettings(map);
        }).catch(()=>{});
      }, []);

      async function save(key) {
        try {
          const res = await fetch(`/control/settings/${key}`, {
            method:'PUT',
            headers:{'Content-Type':'application/json','X-Control-Key':localStorage.getItem('ctrlKey')||'','X-Admin-Key':localStorage.getItem('adminKey')||''},
            body: JSON.stringify({value: String(settings[key]||'')})
          });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          if (restartKeys.includes(key)) setRestartBanner(true);
          setToast({msg: `✓ ${key} actualizado`, err: false});
        } catch(e) { setToast({msg: 'Error: ' + e.message, err: true}); }
      }

      return (
        <div>
          {toast && <Toast msg={toast.msg} isError={toast.err} onClose={()=>setToast(null)} />}
          {restartBanner && <div className="banner">⚠ Requiere restart para aplicar cambios de infraestructura</div>}
          <div className="card">
            <div className="ch"><span className="ct">Infraestructura</span></div>
            <div className="cb">
              {keys.map(k=>{
                const labelMap={ib_host:'IB Host',opencode_bin:'OpenCode Bin',opencode_model:'OpenCode Model',database_url:'Database URL'};
                return (
                  <div className="field" key={k}>
                    <label>{labelMap[k]||k}</label>
                    <div style={{display:'flex',gap:8}}>
                      <input value={settings[k]||''} onChange={e=>setSettings(prev=>({...prev,[k]:e.target.value}))} />
                      <button className="btn" onClick={()=>save(k)}>Guardar</button>
                    </div>
                    {restartKeys.includes(k) && <div className="hint">⚠ Requiere restart</div>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    }

    function ApiKeysPanel() {
      const [settings, setSettings] = useState([]);
      const [editing, setEditing] = useState({});
      const [toast, setToast] = useState(null);
      const [failedCount, setFailedCount] = useState(0);

      useEffect(() => {
        fetch('/control/settings').then(r=>r.json()).then(d=>{
          const secs = (d.settings||[]).filter(s=>s.is_secret);
          setSettings(secs);
          setFailedCount(secs.filter(s=>s.decryption_failed).length);
        }).catch(()=>{});
      }, []);

      async function save(key) {
        try {
          const res = await fetch(`/control/settings/${key}`, {
            method:'PUT',
            headers:{'Content-Type':'application/json','X-Control-Key':localStorage.getItem('ctrlKey')||'','X-Admin-Key':localStorage.getItem('adminKey')||''},
            body: JSON.stringify({value: String(editing[key]||'')})
          });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          setToast({msg: `✓ ${key} actualizado`, err: false});
          setEditing(prev=>({...prev,[key]:''}));
          // Refresh
          fetch('/control/settings').then(r=>r.json()).then(d=>{
            const secs = (d.settings||[]).filter(s=>s.is_secret);
            setSettings(secs);
            setFailedCount(secs.filter(s=>s.decryption_failed).length);
          }).catch(()=>{});
        } catch(e) { setToast({msg: 'Error: ' + e.message, err: true}); }
      }

      return (
        <div>
          {toast && <Toast msg={toast.msg} isError={toast.err} onClose={()=>setToast(null)} />}
          {failedCount>0 && <div className="banner">⚠ {failedCount} secret(s) no pueden descifrarse — re-ingrésalos</div>}
          <div className="card">
            <div className="ch"><span className="ct">API Keys</span></div>
            <div className="cb">
              {settings.map(s=>{
                const hasFailed = s.decryption_failed;
                return (
                  <div className="field" key={s.key}>
                    <label>{s.key} {hasFailed && <span style={{color:'var(--red)'}}>⚠ No se puede leer</span>}</label>
                    <div style={{display:'flex',gap:8,alignItems:'center'}}>
                      <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>••••••••</span>
                      <input type="password" style={{flex:1}} placeholder="Nuevo valor" value={editing[s.key]||''} onChange={e=>setEditing(prev=>({...prev,[s.key]:e.target.value}))} />
                      <button className="btn" onClick={()=>save(s.key)}>Actualizar</button>
                    </div>
                  </div>
                );
              })}
              {!settings.length && <div style={{color:'var(--dimmer)',fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>// sin secrets configurados</div>}
            </div>
          </div>
        </div>
      );
    }

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

    function JobsPanel() {
      const [jobs, setJobs] = useState([]);
      const [loading, setLoading] = useState({});

      function load() {
        fetch('/control/jobs').then(r=>r.json()).then(d=>setJobs(d.jobs||[])).catch(()=>{});
      }

      useEffect(() => { load(); }, []);

      async function trigger(jobId) {
        setLoading(prev=>({...prev,[jobId]:true}));
        try {
          await fetch(`/control/jobs/${jobId}/trigger`, {
            method:'POST',
            headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||''}
          });
          load();
        } catch(e) {}
        setLoading(prev=>({...prev,[jobId]:false}));
      }

      return (
        <div className="card">
          <div className="ch"><span className="ct">Jobs</span></div>
          <div className="cb">
            <table>
              <thead><tr><th>Job</th><th>Last</th><th>Next</th><th>Estado</th><th></th></tr></thead>
              <tbody>
                {jobs.map(j=>{
                  const ok = !j.last_error;
                  return (
                    <tr key={j.id}>
                      <td className="sym">{j.id}</td>
                      <td>{j.last_run||'—'}</td>
                      <td>{j.next_run||'—'}</td>
                      <td style={{color:ok?'var(--green)':'var(--red)'}}>{ok?'● OK':'● ERR'}</td>
                      <td>
                        <button className="btn btn-secondary" disabled={loading[j.id]} onClick={()=>trigger(j.id)}>
                          {loading[j.id]?'...':'▶'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {!jobs.length && <tr><td colSpan={5} style={{textAlign:'center',color:'var(--dimmer)'}}>// sin jobs</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    function AuditLogPanel() {
      const [entries, setEntries] = useState([]);
      const [total, setTotal] = useState(0);
      const [offset, setOffset] = useState(0);
      const limit = 50;

      function load(o) {
        fetch(`/control/audit?limit=${limit}&offset=${o}`, {headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||''}})
          .then(r=>r.json()).then(d=>{setEntries(d.entries||[]);setTotal(d.total||0);}).catch(()=>{});
      }

      useEffect(() => { load(0); }, []);

      return (
        <div className="card">
          <div className="ch"><span className="ct">Audit Log</span></div>
          <div className="cb">
            <table>
              <thead><tr><th>Fecha</th><th>Evento</th><th>Usuario</th><th>Old</th><th>New</th></tr></thead>
              <tbody>
                {entries.map((e,i)=>{
                  const oldVal = e.old_value != null ? String(e.old_value).slice(0,40) : '—';
                  const newVal = e.new_value != null ? String(e.new_value).slice(0,40) : '—';
                  return (
                    <tr key={i}>
                      <td>{(e.occurred_at||'').slice(0,19).replace('T',' ')}</td>
                      <td className="sym">{e.event_type}</td>
                      <td>{e.changed_by||'—'}</td>
                      <td title={e.old_value}>{oldVal}</td>
                      <td title={e.new_value}>{newVal}</td>
                    </tr>
                  );
                })}
                {!entries.length && <tr><td colSpan={5} style={{textAlign:'center',color:'var(--dimmer)'}}>// sin entradas</td></tr>}
              </tbody>
            </table>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:10}}>
              <span style={{fontFamily:'"Fira Code",monospace',fontSize:'.65rem',color:'var(--dim)'}}>
                {offset+1}-{Math.min(offset+limit,total)} de {total}
              </span>
              <div style={{display:'flex',gap:8}}>
                <button className="btn btn-secondary" disabled={offset===0} onClick={()=>{const o=Math.max(0,offset-limit);setOffset(o);load(o);}}>Anterior</button>
                <button className="btn btn-secondary" disabled={offset+limit>=total} onClick={()=>{const o=offset+limit;setOffset(o);load(o);}}>Siguiente</button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    function SymbolsPanel() {
      const [symbols, setSymbols] = useState([]);
      const [proposals, setProposals] = useState([]);

      useEffect(() => {
        fetch('/allowed-symbols').then(r=>r.json()).then(d=>setSymbols(d.symbols||[])).catch(()=>{});
        fetch('/symbols/proposals').then(r=>r.json()).then(d=>setProposals(d||[])).catch(()=>{});
      }, []);

      async function approve(sym) {
        try {
          await fetch(`/symbols/approve/${sym}`, {method:'POST', headers:{'X-Control-Key':localStorage.getItem('ctrlKey')||''}});
          fetch('/symbols/proposals').then(r=>r.json()).then(d=>setProposals(d||[])).catch(()=>{});
        } catch(e) {}
      }

      async function reject(sym) {
        // No direct reject endpoint; just remove from proposals list locally for UI
        setProposals(prev=>prev.filter(p=>p.symbol!==sym));
      }

      return (
        <div>
          <div className="card">
            <div className="ch"><span className="ct">Símbolos Aprobados</span></div>
            <div className="cb">
              <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                {symbols.map(s=><span key={s} style={{padding:'3px 10px',borderRadius:4,background:'var(--surface2)',border:'1px solid var(--border)',fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>{s}</span>)}
                {!symbols.length && <span style={{color:'var(--dimmer)',fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>// sin símbolos</span>}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="ch"><span className="ct">Proposals Pendientes</span></div>
            <div className="cb">
              {proposals.map(p=>{
                const sym = p.symbol || p;
                const reason = p.reason || '';
                return (
                  <div key={sym} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 0',borderBottom:'1px solid var(--border)'}}>
                    <span style={{fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',minWidth:60}}>{sym}</span>
                    <span style={{flex:1,fontSize:'.75rem',color:'var(--muted)'}}>{reason}</span>
                    <button className="btn" style={{padding:'3px 10px',fontSize:'.75rem'}} onClick={()=>approve(sym)}>Aprobar</button>
                    <button className="btn btn-secondary" style={{padding:'3px 10px',fontSize:'.75rem'}} onClick={()=>reject(sym)}>Rechazar</button>
                  </div>
                );
              })}
              {!proposals.length && <span style={{color:'var(--dimmer)',fontFamily:'"Fira Code",monospace',fontSize:'.72rem'}}>// sin proposals pendientes</span>}
            </div>
          </div>
        </div>
      );
    }

    /* ── Main ControlPlaneApp ── */
    function ControlPlaneApp() {
      const [section, setSection] = useState('operational');
      const [status, setStatus] = useState(null);

      function loadStatus() {
        fetch('/control/status').then(r=>r.json()).then(d=>setStatus(d)).catch(()=>{});
      }

      useEffect(() => {
        loadStatus();
        const id = setInterval(loadStatus, 30000);
        return () => clearInterval(id);
      }, []);

      // Parse URL param
      useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const sec = params.get('section');
        if (sec) setSection(sec);
      }, []);

      function navigate(sec) {
        setSection(sec);
        const url = new URL(window.location);
        url.searchParams.set('section', sec);
        window.history.pushState({}, '', url);
      }

      const items = [
        {id:'operational',label:'Operativo'},
        {id:'risk',label:'Riesgo'},
        {id:'symbols',label:'Símbolos'},
        {id:'infra',label:'Infraestructura'},
        {id:'jobs',label:'Jobs'},
        {id:'llm',label:'🤖 Modelos LLM'},
        {id:'apikeys',label:'API Keys'},
        {id:'audit',label:'Audit Log'},
      ];

      return (
        <div>
          <SystemStatusBar />
          <div className="ctrl-page">
            <div className="sidebar">
              <div style={{padding:'8px 16px 12px',fontFamily:'"Bebas Neue",cursive',fontSize:'1.1rem',letterSpacing:'.06em',color:'var(--text)'}}>
                Control
              </div>
              {items.map(it=>{
                const active = section === it.id;
                return (
                  <button key={it.id} className={"sidebar-item " + (active?"active":"")} onClick={()=>navigate(it.id)}>
                    <span>{it.label}</span>
                  </button>
                );
              })}
            </div>
            <div className="main">
              {section==='operational' && <OperationalPanel status={status} refresh={loadStatus} />}
              {section==='risk' && <RiskPanel />}
              {section==='symbols' && <SymbolsPanel />}
              {section==='infra' && <InfraPanel />}
              {section==='jobs' && <JobsPanel />}
              {section==='llm' && <LLMPanel />}
              {section==='apikeys' && <ApiKeysPanel />}
              {section==='audit' && <AuditLogPanel />}
            </div>
          </div>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById('root')).render(<ControlPlaneApp />);
  </script>
</body>
</html>"""
