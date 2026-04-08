"""Tests for vectra_flow.fetch_web module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vectra_flow.fetch_web import fetch_web_sources, _check_url, _TextExtractor


# ── URL validation ─────────────────────────────────────────────────────────────

def test_check_url_empty_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _check_url("")


def test_check_url_unsupported_scheme_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _check_url("ftp://example.com/page")


def test_check_url_file_scheme_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _check_url("file:///etc/passwd")


def test_check_url_localhost_blocked() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_url("http://localhost/forum")


def test_check_url_loopback_ip_blocked() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_url("http://127.0.0.1/forum")


def test_check_url_link_local_ip_blocked() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_url("http://169.254.169.254/latest/")


def test_check_url_private_ip_blocked() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _check_url("http://192.168.1.1/forum")


def test_check_url_valid_https_passes() -> None:
    # Should not raise.
    _check_url("https://www.reddit.com/r/example")


def test_check_url_valid_http_passes() -> None:
    _check_url("http://forum.example.com/thread/123")


# ── TextExtractor ──────────────────────────────────────────────────────────────

def test_text_extractor_basic() -> None:
    html = "<html><body><p>Hello world!</p></body></html>"
    parser = _TextExtractor()
    parser.feed(html)
    assert "Hello world" in parser.text


def test_text_extractor_strips_scripts() -> None:
    html = "<html><body><script>alert('x')</script><p>Content here.</p></body></html>"
    parser = _TextExtractor()
    parser.feed(html)
    assert "alert" not in parser.text
    assert "Content here" in parser.text


def test_text_extractor_strips_style() -> None:
    html = "<html><head><style>.cls{color:red}</style></head><body><p>Visible.</p></body></html>"
    parser = _TextExtractor()
    parser.feed(html)
    assert "color" not in parser.text
    assert "Visible" in parser.text


def test_text_extractor_preserves_paragraph_boundaries() -> None:
    """Block elements must produce separate lines so paragraph splitting works."""
    html = "<body><p>First paragraph here.</p><p>Second paragraph here.</p></body>"
    parser = _TextExtractor()
    parser.feed(html)
    lines = [l for l in parser.text.split("\n") if l.strip()]
    assert len(lines) == 2, f"Expected 2 paragraphs, got: {lines}"


def test_text_extractor_normalises_inline_newlines() -> None:
    """Newlines inside a <p> are HTML source formatting — they must become spaces."""
    html = "<p>Line one\nline two\nline three.</p>"
    parser = _TextExtractor()
    parser.feed(html)
    # Should be a single paragraph (no newlines in the middle of text content)
    assert "\n" not in parser.text.strip()
    assert "Line one line two line three" in parser.text


# ── fetch_web_sources ──────────────────────────────────────────────────────────

_SAMPLE_HTML = b"""<!DOCTYPE html>
<html><body>
<p>This is the first paragraph about a product review with enough content.</p>
<p>Users are very happy with the quality and fast delivery of the items ordered.</p>
<p>The support team was responsive and solved the issue quickly.</p>
</body></html>"""


def _make_urlopen_mock(content: bytes, content_type: str = "text/html; charset=utf-8") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = content
    mock_resp.headers = MagicMock()
    mock_resp.headers.get = MagicMock(return_value=content_type)
    return mock_resp


def test_fetch_web_sources_returns_dataframe() -> None:
    mock_resp = _make_urlopen_mock(_SAMPLE_HTML)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        df = fetch_web_sources(["https://forum.example.com/thread/1"])
    assert isinstance(df, pd.DataFrame)


def test_fetch_web_sources_has_required_columns() -> None:
    mock_resp = _make_urlopen_mock(_SAMPLE_HTML)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        df = fetch_web_sources(["https://forum.example.com/thread/1"])
    for col in ("date", "text", "rating", "product"):
        assert col in df.columns


def test_fetch_web_sources_product_is_hostname() -> None:
    mock_resp = _make_urlopen_mock(_SAMPLE_HTML)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        df = fetch_web_sources(["https://forum.example.com/thread/1"])
    assert all(df["product"] == "forum.example.com")


def test_fetch_web_sources_rating_is_nan() -> None:
    mock_resp = _make_urlopen_mock(_SAMPLE_HTML)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        df = fetch_web_sources(["https://forum.example.com/thread/1"])
    assert df["rating"].isna().all()


def test_fetch_web_sources_empty_on_blocked_url() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        fetch_web_sources(["http://localhost/forum"])


def test_fetch_web_sources_empty_dataframe_on_network_error() -> None:
    import urllib.error
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        df = fetch_web_sources(["https://forum.example.com/thread/1"])
    assert df.empty
    assert list(df.columns) == ["date", "text", "rating", "product"]


def test_fetch_web_sources_multiple_urls() -> None:
    mock_resp = _make_urlopen_mock(_SAMPLE_HTML)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        df = fetch_web_sources([
            "https://forum.example.com/thread/1",
            "https://other.example.com/thread/2",
        ])
    assert len(df["product"].unique()) == 2
