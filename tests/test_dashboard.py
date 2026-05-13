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
