"""Tests for vectra_flow.fetch_inputs module."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vectra_flow.fetch_inputs import fetch_sheet, remap_columns


def _make_urlopen_mock(content: bytes) -> MagicMock:
    """Return a mock suitable for patching ``urllib.request.urlopen``."""
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = content
    return mock_resp


_SAMPLE_CSV = b"date,text,rating,product\n2026-01-01,Great!,5,Widget A\n"

# Simulates what Google Forms actually exports (Italian question titles + Timestamp)
_GOOGLE_FORMS_CSV = (
    b"Timestamp,Il tuo feedback,Valutazione (1-5),Prodotto\n"
    b"2026-01-01 09:00:00,Ottimo prodotto!,5,Widget A\n"
)

_GOOGLE_FORMS_COLUMN_MAP = {
    "Timestamp": "date",
    "Il tuo feedback": "text",
    "Valutazione (1-5)": "rating",
    "Prodotto": "product",
}


# ── URL validation ────────────────────────────────────────────────────────────

def test_fetch_sheet_empty_url_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        fetch_sheet("", Path("/tmp/unused.csv"))


def test_fetch_sheet_unsupported_scheme_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        fetch_sheet("ftp://example.com/data.csv", tmp_path / "out.csv")


def test_fetch_sheet_file_scheme_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        fetch_sheet("file:///etc/passwd", tmp_path / "out.csv")


def test_fetch_sheet_localhost_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        fetch_sheet("http://localhost/data.csv", tmp_path / "out.csv")


def test_fetch_sheet_loopback_ip_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        fetch_sheet("http://127.0.0.1/data.csv", tmp_path / "out.csv")


def test_fetch_sheet_link_local_ip_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        fetch_sheet("http://169.254.169.254/latest/meta-data/", tmp_path / "out.csv")


def test_fetch_sheet_private_ip_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        fetch_sheet("http://192.168.1.1/data.csv", tmp_path / "out.csv")


# ── Basic download ────────────────────────────────────────────────────────────

def test_fetch_sheet_writes_csv(tmp_path: Path) -> None:
    dest = tmp_path / "sheet.csv"
    mock_resp = _make_urlopen_mock(_SAMPLE_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_sheet("https://docs.google.com/spreadsheets/d/ABC/export?format=csv", dest)

    assert dest.exists()
    assert dest.read_bytes() == _SAMPLE_CSV


def test_fetch_sheet_creates_parent_dirs(tmp_path: Path) -> None:
    dest = tmp_path / "nested" / "subdir" / "sheet.csv"
    mock_resp = _make_urlopen_mock(_SAMPLE_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_sheet("https://example.com/data.csv", dest)

    assert dest.exists()


def test_fetch_sheet_http_scheme_allowed(tmp_path: Path) -> None:
    dest = tmp_path / "sheet.csv"
    mock_resp = _make_urlopen_mock(_SAMPLE_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_sheet("http://example.com/data.csv", dest)

    assert dest.exists()


def test_fetch_sheet_passes_timeout(tmp_path: Path) -> None:
    dest = tmp_path / "sheet.csv"
    mock_resp = _make_urlopen_mock(_SAMPLE_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        fetch_sheet("https://example.com/data.csv", dest, timeout=15)

    _, kwargs = mock_open.call_args
    assert kwargs.get("timeout") == 15 or mock_open.call_args[0][1] == 15


# ── Column mapping ────────────────────────────────────────────────────────────

def test_remap_columns_renames_present_columns() -> None:
    df = pd.DataFrame({"Timestamp": ["2026-01-01"], "Feedback": ["Good!"]})
    result = remap_columns(df, {"Timestamp": "date", "Feedback": "text"})
    assert list(result.columns) == ["date", "text"]


def test_remap_columns_ignores_missing_keys() -> None:
    df = pd.DataFrame({"Timestamp": ["2026-01-01"]})
    result = remap_columns(df, {"Timestamp": "date", "NonExistent": "product"})
    assert list(result.columns) == ["date"]


def test_remap_columns_leaves_unmapped_columns() -> None:
    df = pd.DataFrame({"Timestamp": ["2026-01-01"], "extra": [42]})
    result = remap_columns(df, {"Timestamp": "date"})
    assert "date" in result.columns
    assert "extra" in result.columns


def test_remap_columns_does_not_mutate_input() -> None:
    df = pd.DataFrame({"Timestamp": ["2026-01-01"]})
    remap_columns(df, {"Timestamp": "date"})
    assert "Timestamp" in df.columns


def test_fetch_sheet_applies_column_map(tmp_path: Path) -> None:
    dest = tmp_path / "sheet.csv"
    mock_resp = _make_urlopen_mock(_GOOGLE_FORMS_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_sheet(
            "https://docs.google.com/spreadsheets/d/ABC/export?format=csv",
            dest,
            column_map=_GOOGLE_FORMS_COLUMN_MAP,
        )

    assert dest.exists()
    result_df = pd.read_csv(dest)
    for col in ("date", "text", "rating", "product"):
        assert col in result_df.columns, f"Expected column '{col}' after mapping"


def test_fetch_sheet_without_column_map_keeps_raw_bytes(tmp_path: Path) -> None:
    dest = tmp_path / "sheet.csv"
    mock_resp = _make_urlopen_mock(_SAMPLE_CSV)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        fetch_sheet("https://example.com/data.csv", dest)

    assert dest.read_bytes() == _SAMPLE_CSV
