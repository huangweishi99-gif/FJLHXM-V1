"""W15 strategy animation static markers."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_strategy_animations_js_exists() -> None:
    path = ROOT / "web" / "js" / "strategy_animations.js"
    text = path.read_text(encoding="utf-8")
    assert "FengJiStrategyAnim" in text
    assert "DURATION_SEC" in text
    assert "ENGINE_VERSION" in text
    assert "buildSvg" in text
    assert "mountLottieStage" in text
    assert "lottieAssetPath" in text


def test_lottie_assets_manifest() -> None:
    manifest = ROOT / "web" / "assets" / "lottie" / "manifest.json"
    assert manifest.exists()
    data = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    assert len(data.get("strategies", [])) >= 9
    assert data.get("version", 0) >= 5
    assert data.get("refinement") == "o1_n_breakthrough_v4"
    assert (ROOT / "web" / "assets" / "lottie" / "DS01.json").exists()


def test_config_lottie_sources() -> None:
    cfg = (ROOT / "web" / "js" / "config.js").read_text(encoding="utf-8")
    assert "LOTTIE" in cfg
    assert "DS01.json" in cfg
    assert 'MODE: "auto"' in cfg


def test_strategies_page_wires_animations() -> None:
    html = (ROOT / "web" / "strategies.html").read_text(encoding="utf-8")
    assert "strategy_animations.js" in html
    assert "strategy-anim-modal" in html
    assert "strategyAnimPauseBtn" in html
    assert "FengJiStrategyAnim" in html
    assert "10s 循环" in html


def test_config_strategy_anim_engine_version() -> None:
    cfg = (ROOT / "web" / "js" / "config.js").read_text(encoding="utf-8")
    assert "STRATEGY_ANIM" in cfg
    assert "ENGINE_VERSION" in cfg
    assert "DURATION_SEC: 10" in cfg


def test_w15_browser_smoke_script_exists() -> None:
    path = ROOT / "scripts" / "smoke_w15_strategies_browser.py"
    text = path.read_text(encoding="utf-8")
    assert "browser_strategies_smoke" in text
    assert "w15_strategies_browser_smoke.png" in text


def test_w15_page_linkage_markers() -> None:
    index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    backtest_html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    strategies_html = (ROOT / "web" / "strategies.html").read_text(encoding="utf-8")
    app_js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

    assert "strategyHelpLinkHtml" in app_js or "strategyAnimLinkHtml" in app_js
    assert "strategyAnimPageUrl" in app_js
    assert "strategyHelpLinkHtml" in index_html or "strategyAnimLinkHtml" in index_html
    assert "strategyAnimLink" in backtest_html
    assert "applyDeepLink" in strategies_html
    assert "strategy=" in strategies_html or "open" in strategies_html
