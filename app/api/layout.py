"""
Shared HTML layout for all non-dashboard pages.
Provides a consistent header with nav, IB status pulse, and page wrapper.
"""

_SHARED_CSS = """
  :root {
    --bg: #06090F; --surface: #0C1421; --surface2: #111D2E;
    --border: #1E2D42; --text: #E2E8F0; --muted: #94A3B8;
    --dim: #64748B; --dimmer: #334155;
    --blue: #38BDF8; --blue-bg: rgba(56,189,248,.1);
    --green: #10B981; --green-bg: rgba(16,185,129,.1);
    --amber: #FBBF24; --amber-bg: rgba(251,191,36,.1);
    --red: #F43F5E; --red-bg: rgba(244,63,94,.1);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: "Barlow Condensed", sans-serif;
    min-height: 100vh; display: flex; flex-direction: column;
  }

  /* ── Top nav bar ─────────────────────────────── */
  .layout-header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 20px;
    height: 46px;
    display: flex; align-items: center; gap: 16px;
    position: sticky; top: 0; z-index: 50;
    flex-shrink: 0;
  }
  .layout-logo {
    font-family: "Bebas Neue", cursive;
    font-size: 1.25rem; letter-spacing: .1em;
    color: var(--text); white-space: nowrap;
  }
  .ib-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    transition: background .4s;
  }
  .ib-dot.online  { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .ib-dot.offline { background: var(--red); }
  @keyframes pulse-dot {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: .55; transform: scale(.75); }
  }
  .ib-dot.online { animation: pulse-dot 2s ease-in-out infinite; }

  .layout-nav { display: flex; align-items: center; gap: 2px; margin-left: 8px; }
  .layout-nav a {
    font-family: "Barlow Condensed", sans-serif;
    font-weight: 500; font-size: .85rem; letter-spacing: .04em;
    color: var(--dim); text-decoration: none;
    padding: 5px 12px; border-radius: 5px;
    border: 1px solid transparent;
    transition: color .15s, background .15s;
  }
  .layout-nav a:hover { color: var(--muted); }
  .layout-nav a.active {
    color: var(--text); font-weight: 600;
    background: var(--surface2); border-color: var(--border);
  }

  .layout-spacer { flex: 1; }
  .layout-mode-badge {
    font-family: "Fira Code", monospace; font-size: .68rem;
    padding: 2px 8px; border-radius: 4px;
  }
  .badge-paper { background: var(--green-bg); color: var(--green); border: 1px solid rgba(16,185,129,.3); }
  .badge-live  { background: var(--amber-bg); color: var(--amber); border: 1px solid rgba(251,191,36,.3); }
  .badge-paused { background: rgba(100,116,139,.1); color: var(--dim); border: 1px solid var(--border); }

  /* ── Page content ──────────────────────────── */
  .layout-content {
    flex: 1; max-width: 1100px; width: 100%;
    margin: 0 auto; padding: 24px 20px;
  }
  .layout-footer {
    border-top: 1px solid var(--border);
    padding: 8px 20px;
    font-family: "Fira Code", monospace; font-size: .68rem;
    color: var(--dimmer); text-align: center;
  }

  /* ── Typography ────────────────────────────── */
  h1 { font-size: 1.6rem; color: var(--blue); border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 20px; }
  h2 { font-size: 1.25rem; color: var(--muted); margin: 24px 0 10px; }
  h3 { font-size: 1.05rem; color: var(--text); margin: 16px 0 6px; }
  a  { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }
  code { font-family: "Fira Code", monospace; background: var(--surface2); padding: 2px 6px; border-radius: 3px; color: var(--blue); font-size: .85em; }
  strong { color: var(--amber); }
  em { color: var(--muted); }
  hr { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
  blockquote { border-left: 3px solid var(--blue); margin: 0; padding: 8px 16px; background: var(--surface); color: var(--muted); font-style: italic; border-radius: 0 4px 4px 0; }
  table { width: 100%; border-collapse: collapse; font-family: "Fira Code", monospace; font-size: .82rem; margin: 12px 0; }
  th { color: var(--dim); text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-size: .7rem; letter-spacing: .1em; text-transform: uppercase; }
  td { padding: 8px 10px; border-bottom: 1px solid rgba(30,45,66,.5); }
  tr:nth-child(even) td { background: var(--surface); }
  ul { padding-left: 20px; } li { margin: 4px 0; }

  /* ── Cards ─────────────────────────────────── */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;
  }
  .card-header { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 12px; }
  .empty { color: var(--dimmer); font-family: "Fira Code", monospace; padding: 40px; text-align: center; }

  /* ── Buttons ───────────────────────────────── */
  .btn {
    font-family: "Barlow Condensed", sans-serif; font-weight: 600;
    font-size: .82rem; letter-spacing: .04em; cursor: pointer;
    padding: 5px 14px; border-radius: 5px; border: 1px solid var(--border);
    background: var(--surface2); color: var(--muted);
    transition: color .15s, border-color .15s;
  }
  .btn:hover { color: var(--text); border-color: var(--muted); }
  .btn-danger { background: var(--red-bg); color: var(--red); border-color: rgba(244,63,94,.3); }
  .btn-danger:hover { border-color: var(--red); }
"""

_FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Fira+Code:wght@400;500&family=Barlow+Condensed:wght@400;500;600&display=swap" rel="stylesheet">'


def shared_layout(
    *,
    title: str,
    active_nav: str,          # 'dashboard' | 'control' | 'reports' | 'docs'
    content: str,
    extra_css: str = "",
    extra_scripts: str = "",
    footer_text: str = "IBKR AI Trader",
) -> str:
    """
    Render a full HTML page with the shared header nav bar.
    IB status and mode badge are fetched client-side from /health and /system/status.
    """
    nav_items = [
        ("dashboard", "/dashboard", "Dashboard"),
        ("control",   "/control",   "Control"),
        ("reports",   "/reports",   "Reportes"),
        ("docs",      "/docs",      "API Docs"),
    ]
    nav_html = "\n".join(
        f'<a href="{href}" class="{"active" if key == active_nav else ""}">{label}</a>'
        for key, href, label in nav_items
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — IBKR AI Trader</title>
  {_FONTS}
  <style>
{_SHARED_CSS}
{extra_css}
  </style>
</head>
<body>
  <header class="layout-header">
    <span class="ib-dot offline" id="ib-dot"></span>
    <span class="layout-logo">IBKR AI Trader</span>
    <span class="layout-mode-badge badge-paper" id="mode-badge" style="display:none"></span>
    <nav class="layout-nav">
      {nav_html}
    </nav>
    <span class="layout-spacer"></span>
  </header>

  <main class="layout-content">
    {content}
  </main>

  <footer class="layout-footer">{footer_text}</footer>

  <script>
    // Fetch IB status + mode and update header badges
    (async function pollStatus() {{
      try {{
        const [health, status] = await Promise.all([
          fetch('/health').then(r => r.json()).catch(() => ({{}})),
          fetch('/system/status').then(r => r.json()).catch(() => ({{}})),
        ]);
        const dot = document.getElementById('ib-dot');
        const badge = document.getElementById('mode-badge');
        if (dot) {{
          dot.className = 'ib-dot ' + (health.connected ? 'online' : 'offline');
        }}
        if (badge && status.mode) {{
          const mode = (status.mode || 'paper').toUpperCase();
          const paused = status.paused;
          badge.style.display = '';
          if (paused) {{
            badge.className = 'layout-mode-badge badge-paused';
            badge.textContent = 'PAUSADO';
          }} else {{
            badge.className = 'layout-mode-badge ' + (mode === 'LIVE' ? 'badge-live' : 'badge-paper');
            badge.textContent = mode;
          }}
        }}
      }} catch(e) {{}}
      setTimeout(pollStatus, 15000);
    }})();
  </script>
  {extra_scripts}
</body>
</html>"""
