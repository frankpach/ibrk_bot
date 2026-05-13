# tests/test_dashboard.py
# Dashboard is now a React CDN app — all data fetched client-side.
# Tests verify: HTML skeleton is valid, React scaffold present, legacy shim works.
from app.api.dashboard import render_dashboard, render_dashboard_html


def test_dashboard_html_is_valid():
    html = render_dashboard_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_dashboard_html_has_react_root():
    html = render_dashboard_html()
    assert 'id="root"' in html


def test_dashboard_html_has_cdn_react():
    html = render_dashboard_html()
    assert "react" in html.lower()


def test_dashboard_html_has_fetch_endpoint():
    """React app fetches /dashboard/data — verify the URL is in the source."""
    html = render_dashboard_html()
    assert "/dashboard/data" in html


def test_dashboard_html_has_dark_mode_css():
    html = render_dashboard_html()
    assert "--bg" in html or "data-theme" in html or "background" in html


def test_dashboard_legacy_shim_works():
    """render_dashboard() shim must still return valid HTML (backwards compat)."""
    html = render_dashboard({}, [], [], [], [])
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_dashboard_html_has_ibkr_title():
    html = render_dashboard_html()
    assert "IBKR" in html.upper() or "Trader" in html


# ── LD-005: Part B sections ────────────────────────────────────────────────

def test_dashboard_html_has_news_section():
    html = render_dashboard_html()
    assert "Noticias" in html or "news" in html.lower()


def test_dashboard_html_has_universo_section():
    html = render_dashboard_html()
    assert "Universo" in html or "universo" in html.lower() or "backtest" in html.lower()


def test_dashboard_html_has_market_trends():
    html = render_dashboard_html()
    assert "Trends" in html or "scanner" in html.lower()


def test_dashboard_html_has_symbol_chart():
    html = render_dashboard_html()
    assert "SymbolChart" in html or "symbol_chart" in html.lower() or "dashboard/symbol" in html


def test_dashboard_html_has_control_bar():
    html = render_dashboard_html()
    assert "ControlBar" in html or "Control del Sistema" in html or "sistema/pause" in html.lower() or "system/pause" in html


def test_dashboard_html_has_symbol_endpoint_call():
    """Dashboard JS must call /dashboard/symbol/ for lazy chart loading."""
    html = render_dashboard_html()
    assert "/dashboard/symbol/" in html


def test_dashboard_html_news_defaults_universe_tab():
    """NewsCard defaults to 'universe' tab."""
    html = render_dashboard_html()
    assert "Mi universo" in html or "universe" in html


def test_dashboard_html_market_trends_six_tabs():
    """MarketTrendsCard must declare all 6 tab keys."""
    html = render_dashboard_html()
    for key in ("most_active", "top_movers", "gainers", "losers", "sector", "implied_move"):
        assert key in html


def test_dashboard_html_recalibrate_calls_approve():
    """Recalibrar button calls /symbols/approve/{symbol}."""
    html = render_dashboard_html()
    assert "/symbols/approve/" in html


def test_dashboard_html_add_button_calls_propose():
    """+ añadir button calls /symbols/propose."""
    html = render_dashboard_html()
    assert "/symbols/propose" in html


def test_dashboard_html_notifications_level_endpoint():
    """Control bar calls /notifications/level/."""
    html = render_dashboard_html()
    assert "/notifications/level/" in html
