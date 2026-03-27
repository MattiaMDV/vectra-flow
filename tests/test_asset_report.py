"""Tests for vectra_flow.asset_report module."""
import json
from pathlib import Path

import pytest

from vectra_flow.asset_report import (
    render_asset_html,
    render_asset_markdown,
    write_asset_reports,
)
from vectra_flow.asset_score import AssetOpportunity, score_asset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scored_asset(**kwargs) -> AssetOpportunity:
    defaults = dict(
        url="https://example.com/app",
        title="Demo App",
        asking_price=200.0,
        monthly_revenue=20.0,
        monthly_traffic=3_000,
        current_monetization="",
        has_email_list=False,
    )
    defaults.update(kwargs)
    a = AssetOpportunity(**defaults)
    return score_asset(a)


# ---------------------------------------------------------------------------
# render_asset_html
# ---------------------------------------------------------------------------

def test_render_html_returns_string() -> None:
    assets = [_make_scored_asset()]
    result = render_asset_html(assets)
    assert isinstance(result, str)


def test_render_html_contains_title() -> None:
    assets = [_make_scored_asset(title="My Awesome SaaS")]
    result = render_asset_html(assets)
    assert "My Awesome SaaS" in result


def test_render_html_contains_doctype() -> None:
    result = render_asset_html([_make_scored_asset()])
    assert "<!DOCTYPE html>" in result


def test_render_html_shows_asset_count() -> None:
    assets = [_make_scored_asset(title=f"App {i}") for i in range(3)]
    result = render_asset_html(assets)
    assert "3" in result


def test_render_html_escapes_special_chars() -> None:
    assets = [_make_scored_asset(title="<script>alert('xss')</script>")]
    result = render_asset_html(assets)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_render_html_shows_strategy_flip() -> None:
    asset = _make_scored_asset(
        asking_price=200.0,
        monthly_revenue=40.0,
        monthly_traffic=12_000,
        has_email_list=True,
    )
    result = render_asset_html([asset])
    assert "flip" in result.lower() or "Flip" in result


def test_render_html_empty_list() -> None:
    result = render_asset_html([])
    assert "<!DOCTYPE html>" in result


# ---------------------------------------------------------------------------
# render_asset_markdown
# ---------------------------------------------------------------------------

def test_render_markdown_returns_string() -> None:
    assets = [_make_scored_asset()]
    result = render_asset_markdown(assets)
    assert isinstance(result, str)


def test_render_markdown_contains_h1() -> None:
    result = render_asset_markdown([_make_scored_asset()])
    assert result.startswith("# Vectra Flow")


def test_render_markdown_contains_asset_title() -> None:
    assets = [_make_scored_asset(title="QuickNote App")]
    result = render_asset_markdown(assets)
    assert "QuickNote App" in result


def test_render_markdown_contains_score() -> None:
    asset = _make_scored_asset()
    result = render_asset_markdown([asset])
    assert "Score" in result
    assert str(asset.score) in result


def test_render_markdown_contains_strategy() -> None:
    result = render_asset_markdown([_make_scored_asset()])
    assert "Exit strategy" in result


def test_render_markdown_empty_list() -> None:
    result = render_asset_markdown([])
    assert "# Vectra Flow" in result


# ---------------------------------------------------------------------------
# write_asset_reports
# ---------------------------------------------------------------------------

def test_write_asset_reports_creates_files(tmp_path: Path) -> None:
    assets = [_make_scored_asset()]
    paths = write_asset_reports(assets, out_dir=tmp_path)
    assert len(paths) == 3
    for p in paths:
        assert p.exists()


def test_write_asset_reports_json_valid(tmp_path: Path) -> None:
    assets = [_make_scored_asset(title="JSON Test")]
    write_asset_reports(assets, out_dir=tmp_path)
    data = json.loads((tmp_path / "asset_latest.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["title"] == "JSON Test"


def test_write_asset_reports_markdown_file(tmp_path: Path) -> None:
    assets = [_make_scored_asset()]
    write_asset_reports(assets, out_dir=tmp_path)
    md = (tmp_path / "asset_latest.md").read_text(encoding="utf-8")
    assert "# Vectra Flow" in md


def test_write_asset_reports_html_file(tmp_path: Path) -> None:
    assets = [_make_scored_asset()]
    write_asset_reports(assets, out_dir=tmp_path)
    html_content = (tmp_path / "asset_latest.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content


def test_write_asset_reports_creates_out_dir(tmp_path: Path) -> None:
    new_dir = tmp_path / "nested" / "reports"
    write_asset_reports([_make_scored_asset()], out_dir=new_dir)
    assert new_dir.exists()
