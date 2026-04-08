"""Fetch and extract plain text from public web pages (forums, discussion boards).

Typical programmatic usage::

    from vectra_flow.fetch_web import fetch_web_sources
    df = fetch_web_sources(["https://www.reddit.com/r/…", "https://forum.example.com/…"])

The returned DataFrame has the same columns expected by the analysis pipeline:
``date``, ``text``, ``rating``, ``product``.  The ``rating`` column is left as
``NaN`` (no explicit score is available for raw HTML pages) and ``product`` is
set to the URL hostname so that the "by product" breakdown groups entries by
source site.

Security
--------
The same SSRF guard used in :mod:`vectra_flow.fetch_inputs` is applied here:
empty strings, non-HTTP(S) schemes, ``localhost``, loopback / link-local /
private IP addresses are all rejected with a ``ValueError``.
"""
from __future__ import annotations

import ipaddress
import re
import urllib.error
import urllib.request
import warnings
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_BLOCKED_HOSTNAMES = frozenset({"localhost", "0.0.0.0"})

# Tags whose content we always discard (scripts, styles, navigation…).
_SKIP_TAGS = frozenset({
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "select", "option",
})

# Tags that signal the start of a new paragraph / post.
_BLOCK_TAGS = frozenset({
    "p", "div", "li", "blockquote", "article", "section",
    "td", "th", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6",
})

_USER_AGENT = (
    "VectraFlow/1.0 (sentiment analysis bot; "
    "+https://github.com/MattiaMDV/vectra-flow)"
)


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain-text extractor using the standard library."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth: int = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            # Normalise inline whitespace (including embedded newlines that are
            # just HTML source formatting) to a single space.  Block-level
            # paragraph boundaries are already marked by the explicit "\n"
            # appended in handle_starttag, so we must NOT let text-node
            # newlines pollute the paragraph structure.
            self._chunks.append(re.sub(r"\s+", " ", data))

    @property
    def text(self) -> str:
        raw = "".join(self._chunks)
        # Strip spaces around the block-level newlines and drop empty lines,
        # but preserve newline boundaries so _split_into_paragraphs / _split_paragraphs
        # can correctly separate content from different HTML block elements.
        lines = [line.strip() for line in raw.split("\n")]
        return "\n".join(line for line in lines if line)


def _check_url(url: str) -> None:
    """Validate *url* before opening it (SSRF guard)."""
    if not url:
        raise ValueError("URL must not be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Unsupported URL scheme {parsed.scheme!r}. Only HTTP(S) URLs are allowed."
        )

    hostname = parsed.hostname or ""
    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Requests to {hostname!r} are not allowed.")

    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback or addr.is_link_local or addr.is_private:
            raise ValueError(
                f"Requests to private/internal IP address {hostname!r} are not allowed."
            )
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise


def _fetch_html(url: str, timeout: int = 30) -> str:
    """Return the raw HTML body of *url* as a UTF-8 string."""
    _check_url(url)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read()
    # Try to detect charset from Content-Type header; fall back to utf-8.
    content_type = resp.headers.get("Content-Type", "")
    charset = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[1].strip()
            break
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _split_into_paragraphs(text: str, min_len: int = 40) -> list[str]:
    """Split plain *text* into non-trivial paragraphs."""
    paragraphs = [p.strip() for p in re.split(r"\n{1,}", text)]
    return [p for p in paragraphs if len(p) >= min_len]


def fetch_web_sources(
    urls: list[str],
    timeout: int = 30,
    min_paragraph_len: int = 40,
    max_paragraphs_per_url: int = 200,
) -> pd.DataFrame:
    """Fetch plain-text content from *urls* and return a DataFrame.

    Each paragraph / user post from each page becomes one row in the returned
    DataFrame.  Columns:

    - **date**    — fetch timestamp (UTC), same for all rows from the same URL.
    - **text**    — extracted paragraph / sentence.
    - **rating**  — ``NaN`` (no explicit score available for raw HTML pages).
    - **product** — hostname of the source URL (used as the "product" label in
                    the by-product sentiment breakdown).

    Args:
        urls:                  List of HTTP(S) URLs to fetch.
        timeout:               Network timeout per request in seconds.
        min_paragraph_len:     Minimum character length for a paragraph to be
                               included (filters out short nav labels etc.).
        max_paragraphs_per_url: Maximum number of paragraphs extracted per URL.

    Returns:
        DataFrame with columns ``date``, ``text``, ``rating``, ``product``.
        Empty DataFrame (with correct columns) if no text could be extracted.

    Raises:
        ValueError: if any URL is empty, uses an unsupported scheme, or targets
                    a private/internal address.
    """
    # Validate all URLs upfront so the caller gets a clear error early.
    for url in urls:
        _check_url(url)

    rows: list[dict] = []
    now = pd.Timestamp.now("UTC")

    for url in urls:
        hostname = urlparse(url).hostname or url
        try:
            html_body = _fetch_html(url, timeout=timeout)
        except (urllib.error.URLError, OSError) as exc:
            # Non-fatal: log and continue with other URLs.
            warnings.warn(f"Could not fetch {url!r}: {exc}", stacklevel=2)
            continue

        parser = _TextExtractor()
        parser.feed(html_body)
        paragraphs = _split_into_paragraphs(parser.text, min_len=min_paragraph_len)

        for para in paragraphs[:max_paragraphs_per_url]:
            rows.append({
                "date": now,
                "text": para,
                "rating": float("nan"),
                "product": hostname,
            })

    if not rows:
        return pd.DataFrame(columns=["date", "text", "rating", "product"])

    return pd.DataFrame(rows)
