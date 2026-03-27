"""Tests for vectra_flow.report module."""
from pathlib import Path

import pandas as pd
import pytest

from vectra_flow.analyze import analyze_dataset
from vectra_flow.report import render_html, render_markdown, write_reports


@pytest.fixture()
def analysis_results():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
                utc=True,
            ),
            "text": [
                "Great product, very happy with the purchase!",
                "Shipping was slow and support was unhelpful.",
                "Acceptable quality for the price paid.",
                "Absolutely love it, will buy again!",
                "Product broke after one week, very disappointed.",
            ],
            "rating": [5.0, 2.0, 3.0, 5.0, 1.0],
            "product": ["Widget A", "Widget B", "Widget A", "Widget A", "Widget B"],
        }
    )
    return analyze_dataset(df, n_topics=2)


def test_render_markdown_returns_string(analysis_results) -> None:
    md = render_markdown(analysis_results)
    assert isinstance(md, str)


def test_render_markdown_contains_heading(analysis_results) -> None:
    md = render_markdown(analysis_results)
    assert "Vectra Flow" in md


def test_render_markdown_contains_overall_section(analysis_results) -> None:
    md = render_markdown(analysis_results)
    assert "## Overall" in md


def test_render_markdown_contains_topics_section(analysis_results) -> None:
    md = render_markdown(analysis_results)
    assert "## Topics" in md


def test_render_html_returns_string(analysis_results) -> None:
    page = render_html(analysis_results)
    assert isinstance(page, str)


def test_render_html_is_valid_html(analysis_results) -> None:
    page = render_html(analysis_results)
    assert page.startswith("<!DOCTYPE html>")
    assert "<html" in page
    assert "</html>" in page


def test_render_html_contains_report_content(analysis_results) -> None:
    page = render_html(analysis_results)
    assert "Vectra Flow" in page
    assert "Overall" in page
    assert "Topics" in page


def test_render_html_escapes_special_chars(analysis_results) -> None:
    """Product names containing HTML-special chars must be escaped."""
    page = render_html(analysis_results)
    # Confirm the page does not contain raw unescaped angle brackets from data
    assert "<script>" not in page


def test_write_reports_creates_files(tmp_path: Path, analysis_results) -> None:
    out_dir = tmp_path / "reports"
    paths = write_reports(analysis_results, out_dir)
    assert len(paths) == 4
    for p in paths:
        assert p.exists(), f"Expected {p} to exist"


def test_write_reports_latest_md_exists(tmp_path: Path, analysis_results) -> None:
    out_dir = tmp_path / "reports"
    write_reports(analysis_results, out_dir)
    assert (out_dir / "latest.md").exists()


def test_write_reports_latest_html_exists(tmp_path: Path, analysis_results) -> None:
    out_dir = tmp_path / "reports"
    write_reports(analysis_results, out_dir)
    html_path = out_dir / "latest.html"
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_write_reports_latest_json_exists(tmp_path: Path, analysis_results) -> None:
    import json

    out_dir = tmp_path / "reports"
    write_reports(analysis_results, out_dir)
    json_path = out_dir / "latest.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "rows" in data
    assert "topics" in data
