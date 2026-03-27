"""Asset Scout — Discover undervalued digital assets by scanning crypto forums.

Scans a curated set of public crypto/blockchain forums and social channels
for emerging or undervalued projects.  Each promising mention is turned into a
:class:`ScoutedAsset` that can be passed straight to the partnership-
notification pipeline.

Default sources
---------------
* Reddit — r/CryptoMoonShots, r/CryptoCurrency, r/defi, r/ethereum,
            r/altcoin
* Bitcointalk — Altcoin Announcements board
* Ethereum governance / EthCC-adjacent — Ethereum Magicians forum,
  Ethereum Research
* Protocol governance — Uniswap forum, Aave forum, Compound forum
* Binance Square — Binance social feed (square.binance.com)

Discovery heuristics
---------------------
Text from each page is scanned for keyword signals that suggest a project is
under-valued or seeking attention.  Each hit increments a relevance *score*
(0.0–1.0).  Only assets whose score reaches ``min_score`` are surfaced.
"""

from __future__ import annotations

import re
import urllib.parse
import warnings
from dataclasses import dataclass, field
from typing import Sequence

# Reuse the existing SSRF-safe fetch primitives
from vectra_flow.fetch_web import _check_url, _fetch_html, _TextExtractor

# ---------------------------------------------------------------------------
# Default forum targets
# ---------------------------------------------------------------------------

#: Public URLs that the scout visits by default.
DEFAULT_SCOUT_URLS: list[str] = [
    # Reddit – crypto discussion
    "https://old.reddit.com/r/CryptoMoonShots/new/",
    "https://old.reddit.com/r/CryptoCurrency/new/",
    "https://old.reddit.com/r/defi/new/",
    "https://old.reddit.com/r/ethereum/new/",
    "https://old.reddit.com/r/altcoin/new/",
    # Bitcointalk – altcoin announcements
    "https://bitcointalk.org/index.php?board=159.0",
    # Ethereum Magicians governance
    "https://ethereum-magicians.org/latest",
    # Protocol governance forums
    "https://gov.uniswap.org/latest",
    "https://governance.aave.com/latest",
    "https://www.comp.xyz/latest",
    # Binance Square social feed
    "https://square.binance.com/en",
]

# ---------------------------------------------------------------------------
# Keyword scoring tables
# ---------------------------------------------------------------------------

# Positive signals: suggests project is undervalued / seeking growth
_UNDERVALUED_SIGNALS: list[str] = [
    "undervalued",
    "hidden gem",
    "early stage",
    "seed round",
    "pre-sale",
    "presale",
    "low cap",
    "micro cap",
    "small cap",
    "looking for partners",
    "partnership",
    "seeking investors",
    "seeking promotion",
    "community growth",
    "marketing needed",
    "exposure needed",
    "low volume",
    "overlooked",
    "undiscovered",
    "new project",
    "launch soon",
    "just launched",
    "fair launch",
    "no vc",
    "no venture",
    "grassroots",
    "organic growth",
]

# Asset-type identifiers — confirms the snippet is about a digital asset
_ASSET_IDENTIFIERS: list[str] = [
    "token",
    "coin",
    "protocol",
    "defi",
    "dao",
    "nft",
    "dapp",
    "smart contract",
    "blockchain",
    "crypto",
    "project",
    "network",
    "chain",
    "layer",
    "whitepaper",
    "tokenomics",
    "airdrop",
    "staking",
    "yield",
    "liquidity",
]

# Negative / spam signals — reduce score when present
_SPAM_SIGNALS: list[str] = [
    "100x guaranteed",
    "get rich",
    "pump",
    "moon guaranteed",
    "not financial advice",
    "rug",
    "honeypot",
    "scam",
]

_TICKER_RE = re.compile(r"\$([A-Z]{2,8})\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ScoutedAsset:
    """A digital asset discovered by the forum scout.

    Attributes
    ----------
    name:
        Project name or ticker extracted from the source text.
    source_url:
        The forum / page where the asset was mentioned.
    source_platform:
        Human-readable platform label (e.g. ``"reddit"``, ``"bitcointalk"``).
    snippet:
        Representative text excerpt from the source page.
    score:
        Relevance / undervaluation signal score in the range [0.0, 1.0].
    tickers:
        List of ``$TICKER`` symbols found in the snippet.
    project_urls:
        External URLs found in the snippet (may point to the project site).
    """

    name: str
    source_url: str
    source_platform: str
    snippet: str
    score: float
    tickers: list[str] = field(default_factory=list)
    project_urls: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_forums(
    urls: Sequence[str] | None = None,
    *,
    timeout: int = 30,
    min_score: float = 0.3,
    max_paragraphs_per_url: int = 300,
    min_paragraph_len: int = 40,
) -> list[ScoutedAsset]:
    """Scan forum pages for undervalued digital asset mentions.

    Parameters
    ----------
    urls:
        List of HTTP(S) URLs to scan.  Defaults to :data:`DEFAULT_SCOUT_URLS`.
    timeout:
        Network timeout per request in seconds.
    min_score:
        Minimum relevance score (0.0–1.0) for an asset to be surfaced.
    max_paragraphs_per_url:
        Maximum paragraphs to extract per page (limits memory usage).
    min_paragraph_len:
        Minimum character length for a paragraph to be considered.

    Returns
    -------
    list[ScoutedAsset]
        Discovered assets sorted by score descending.
    """
    if urls is None:
        urls = DEFAULT_SCOUT_URLS

    # Validate all URLs upfront
    for url in urls:
        _check_url(url)

    discovered: list[ScoutedAsset] = []

    for url in urls:
        platform = _platform_label(url)
        try:
            html_body = _fetch_html(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"Scout: could not fetch {url!r}: {exc}", stacklevel=2)
            continue

        parser = _TextExtractor()
        parser.feed(html_body)
        full_text = parser.text

        paragraphs = _split_paragraphs(
            full_text,
            min_len=min_paragraph_len,
            max_count=max_paragraphs_per_url,
        )

        for para in paragraphs:
            score = _score_paragraph(para)
            if score >= min_score:
                tickers = _TICKER_RE.findall(para)
                project_urls = _extract_project_urls(para, source_url=url)
                name = _infer_name(para, tickers)
                discovered.append(
                    ScoutedAsset(
                        name=name,
                        source_url=url,
                        source_platform=platform,
                        snippet=para[:500],
                        score=round(score, 3),
                        tickers=tickers[:10],
                        project_urls=project_urls[:5],
                    )
                )

    # Deduplicate by (source_url, snippet prefix) and sort
    seen: set[str] = set()
    unique: list[ScoutedAsset] = []
    for asset in sorted(discovered, key=lambda a: a.score, reverse=True):
        key = f"{asset.source_url}::{asset.snippet[:80]}"
        if key not in seen:
            seen.add(key)
            unique.append(asset)

    return unique


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _platform_label(url: str) -> str:
    """Return a short human-readable platform name for *url*."""
    hostname = urllib.parse.urlparse(url).hostname or url
    if "reddit" in hostname:
        return "reddit"
    if "bitcointalk" in hostname:
        return "bitcointalk"
    if "ethereum-magicians" in hostname or "ethresear" in hostname:
        return "ethereum_governance"
    if "uniswap" in hostname:
        return "uniswap_governance"
    if "aave" in hostname:
        return "aave_governance"
    if "comp.xyz" in hostname or "compound" in hostname:
        return "compound_governance"
    if "binance" in hostname:
        return "binance_square"
    return hostname.replace("www.", "")


def _score_paragraph(text: str) -> float:
    """Compute a relevance score in [0.0, 1.0] for *text*.

    Scoring rules
    -------------
    * +0.15 per unique undervaluation signal keyword found (capped at 0.45).
    * +0.10 per unique asset-type identifier found (capped at 0.30).
    * -0.20 per unique spam / manipulation signal found (capped at -0.40).
    * Tickers (``$SYMBOL``) give +0.05 each (capped at 0.20).
    * The resulting value is clamped to [0.0, 1.0].
    """
    lower = text.lower()

    undervalued_hits = sum(1 for kw in _UNDERVALUED_SIGNALS if kw in lower)
    asset_hits = sum(1 for kw in _ASSET_IDENTIFIERS if kw in lower)
    spam_hits = sum(1 for kw in _SPAM_SIGNALS if kw in lower)
    ticker_hits = len(_TICKER_RE.findall(text))

    score = (
        min(undervalued_hits * 0.15, 0.45)
        + min(asset_hits * 0.10, 0.30)
        + min(ticker_hits * 0.05, 0.20)
        - min(spam_hits * 0.20, 0.40)
    )
    return max(0.0, min(1.0, score))


def _split_paragraphs(
    text: str, *, min_len: int, max_count: int
) -> list[str]:
    """Split *text* into non-trivial paragraphs."""
    raw = re.split(r"\n+", text)
    result: list[str] = []
    for para in raw:
        para = para.strip()
        if len(para) >= min_len:
            result.append(para)
            if len(result) >= max_count:
                break
    return result


def _extract_project_urls(para: str, source_url: str) -> list[str]:
    """Return external URLs found in *para* (excluding the source domain)."""
    source_host = urllib.parse.urlparse(source_url).hostname or ""
    found: list[str] = []
    for match in _URL_RE.finditer(para):
        url = match.group(0).rstrip(".,;)")
        host = urllib.parse.urlparse(url).hostname or ""
        if host and host != source_host:
            found.append(url)
    return found


def _infer_name(para: str, tickers: list[str]) -> str:
    """Infer a project name from the paragraph text or ticker list."""
    if tickers:
        return tickers[0]
    # Look for a capitalised multi-word phrase up to 4 tokens
    match = re.search(r"\b([A-Z][A-Za-z0-9]{1,20}(?:\s[A-Z][A-Za-z0-9]{1,20}){0,3})\b", para)
    if match:
        return match.group(1)
    return "Unknown"
