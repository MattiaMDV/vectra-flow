"""Tests for vectra_flow.asset_scout module."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from vectra_flow.asset_scout import (
    DEFAULT_SCOUT_URLS,
    ScoutedAsset,
    _DISCOURSE_HOSTS,
    _extract_project_urls,
    _fetch_discourse_paragraphs,
    _infer_name,
    _is_discourse_url,
    _platform_label,
    _score_paragraph,
    _split_paragraphs,
    scan_forums,
)


# ---------------------------------------------------------------------------
# _platform_label
# ---------------------------------------------------------------------------


def test_platform_label_reddit() -> None:
    assert _platform_label("https://old.reddit.com/r/CryptoMoonShots/") == "reddit"


def test_platform_label_bitcointalk() -> None:
    assert _platform_label("https://bitcointalk.org/index.php?board=159.0") == "bitcointalk"


def test_platform_label_ethereum_magicians() -> None:
    assert _platform_label("https://ethereum-magicians.org/latest") == "ethereum_governance"


def test_platform_label_uniswap() -> None:
    assert _platform_label("https://gov.uniswap.org/latest") == "uniswap_governance"


def test_platform_label_aave() -> None:
    assert _platform_label("https://governance.aave.com/latest") == "aave_governance"


def test_platform_label_binance() -> None:
    assert _platform_label("https://square.binance.com/en") == "binance_square"


def test_platform_label_unknown() -> None:
    label = _platform_label("https://example.com/forum")
    assert label == "example.com"


# ---------------------------------------------------------------------------
# _score_paragraph
# ---------------------------------------------------------------------------


def test_score_zero_for_empty_text() -> None:
    assert _score_paragraph("") == 0.0


def test_score_positive_for_undervalued_signals() -> None:
    text = "This is an undervalued token with low cap and no vc backing."
    score = _score_paragraph(text)
    assert score > 0.0


def test_score_asset_identifier_alone() -> None:
    text = "A new blockchain protocol with interesting tokenomics."
    score = _score_paragraph(text)
    assert score > 0.0


def test_score_decremented_by_spam_signals() -> None:
    clean = "This is an undervalued token looking for partnership."
    spammy = clean + " 100x guaranteed get rich fast pump moon guaranteed"
    assert _score_paragraph(spammy) <= _score_paragraph(clean)


def test_score_capped_at_one() -> None:
    text = (
        "undervalued hidden gem early stage seed round pre-sale presale low cap "
        "micro cap small cap looking for partners partnership seeking investors "
        "$TOKEN $COIN blockchain defi dao nft dapp smart contract tokenomics "
    )
    assert _score_paragraph(text) <= 1.0


def test_score_clamped_to_zero_when_heavily_spammy() -> None:
    text = "rug honeypot scam get rich pump moon guaranteed 100x guaranteed"
    assert _score_paragraph(text) >= 0.0


def test_score_ticker_contributes() -> None:
    with_ticker = "Interesting project $XYZ with defi protocol."
    without_ticker = "Interesting project with defi protocol."
    assert _score_paragraph(with_ticker) >= _score_paragraph(without_ticker)


# ---------------------------------------------------------------------------
# _split_paragraphs
# ---------------------------------------------------------------------------


def test_split_paragraphs_basic() -> None:
    text = "Short.\n\nThis is a longer paragraph that exceeds the minimum length threshold.\n\nAnother good paragraph here that also has enough characters."
    result = _split_paragraphs(text, min_len=40, max_count=100)
    assert len(result) == 2
    assert all(len(p) >= 40 for p in result)


def test_split_paragraphs_max_count_respected() -> None:
    text = "\n".join([f"Paragraph number {i} that is long enough to pass the filter." for i in range(20)])
    result = _split_paragraphs(text, min_len=10, max_count=5)
    assert len(result) == 5


def test_split_paragraphs_empty_input() -> None:
    result = _split_paragraphs("", min_len=10, max_count=100)
    assert result == []


# ---------------------------------------------------------------------------
# _extract_project_urls
# ---------------------------------------------------------------------------


def test_extract_project_urls_finds_external_link() -> None:
    para = "Check out the project at https://someproject.io/token for details."
    urls = _extract_project_urls(para, source_url="https://reddit.com/r/crypto")
    assert "https://someproject.io/token" in urls


def test_extract_project_urls_excludes_source_domain() -> None:
    from urllib.parse import urlparse
    para = "See https://reddit.com/r/other for more info."
    urls = _extract_project_urls(para, source_url="https://reddit.com/r/crypto")
    assert all(urlparse(u).hostname != "reddit.com" for u in urls)


def test_extract_project_urls_empty_para() -> None:
    assert _extract_project_urls("", source_url="https://example.com") == []


# ---------------------------------------------------------------------------
# _infer_name
# ---------------------------------------------------------------------------


def test_infer_name_prefers_ticker() -> None:
    name = _infer_name("The $DOGE coin is undervalued.", tickers=["DOGE"])
    assert name == "DOGE"


def test_infer_name_falls_back_to_capitalised_word() -> None:
    name = _infer_name("Ethereum Protocol is very interesting here.", tickers=[])
    assert name  # non-empty
    assert name[0].isupper()


def test_infer_name_returns_unknown_when_no_match() -> None:
    name = _infer_name("all lower case text with no tickers", tickers=[])
    assert name == "Unknown"


# ---------------------------------------------------------------------------
# DEFAULT_SCOUT_URLS
# ---------------------------------------------------------------------------


def test_default_scout_urls_non_empty() -> None:
    assert len(DEFAULT_SCOUT_URLS) > 0


def test_default_scout_urls_all_https() -> None:
    for url in DEFAULT_SCOUT_URLS:
        assert url.startswith("http"), f"Expected http(s) URL, got: {url}"


# ---------------------------------------------------------------------------
# scan_forums — uses mocked HTTP
# ---------------------------------------------------------------------------

_FAKE_HTML = """
<html><body>
<p>This is an undervalued token called $XYZ. It has low cap and is looking for
partners to help with community growth and promotion. No VC, fair launch, the
project is just launched and seeking investors. Tokenomics look solid.
Visit https://xyztoken.io for more details.</p>
<p>Another hidden gem early stage defi protocol $ABC with great potential.
Seeking promotional partnership. The team is focused on organic growth.</p>
</body></html>
"""


def _make_mock_fetch(html: str = _FAKE_HTML):
    def _mock_fetch_html(url: str, timeout: int = 30) -> str:  # noqa: ARG001
        return html
    return _mock_fetch_html


def test_scan_forums_returns_list() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert isinstance(result, list)


def test_scan_forums_discovers_asset() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert len(result) > 0


def test_scan_forums_result_is_scouted_asset() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert all(isinstance(a, ScoutedAsset) for a in result)


def test_scan_forums_score_within_range() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert all(0.0 <= a.score <= 1.0 for a in result)


def test_scan_forums_sorted_by_score_desc() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    scores = [a.score for a in result]
    assert scores == sorted(scores, reverse=True)


def test_scan_forums_respects_min_score() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.99)
    # With such a high threshold, very few (possibly zero) results expected
    assert all(a.score >= 0.99 for a in result)


def test_scan_forums_network_error_is_skipped() -> None:
    """A fetch failure on one URL should not abort the whole scan."""
    import warnings

    def _flaky_fetch(url: str, timeout: int = 30) -> str:
        raise OSError("connection refused")

    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_flaky_fetch):
        with warnings.catch_warnings(record=True):
            result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert result == []


def test_scan_forums_invalid_url_raises() -> None:
    with pytest.raises(ValueError):
        scan_forums(["ftp://not-allowed.com/"])


def test_scan_forums_empty_page_returns_empty() -> None:
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch("<html><body></body></html>")):
        result = scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    assert result == []


def test_scan_forums_deduplicates_results() -> None:
    """Identical paragraphs from the same URL should appear only once."""
    with patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()):
        result = scan_forums(
            ["https://old.reddit.com/r/CryptoMoonShots/", "https://old.reddit.com/r/CryptoMoonShots/"],
            min_score=0.1,
        )
    # Even though URL is repeated, snippet keys are the same → deduplicated
    snippets = [a.snippet[:80] for a in result]
    assert len(snippets) == len(set(snippets))


# ---------------------------------------------------------------------------
# _is_discourse_url
# ---------------------------------------------------------------------------


def test_is_discourse_url_known_hosts() -> None:
    assert _is_discourse_url("https://ethereum-magicians.org/latest") is True
    assert _is_discourse_url("https://gov.uniswap.org/latest") is True
    assert _is_discourse_url("https://governance.aave.com/latest") is True
    assert _is_discourse_url("https://www.comp.xyz/latest") is True


def test_is_discourse_url_non_discourse() -> None:
    assert _is_discourse_url("https://old.reddit.com/r/crypto") is False
    assert _is_discourse_url("https://bitcointalk.org/board=1") is False
    assert _is_discourse_url("https://square.binance.com/en") is False


def test_discourse_hosts_non_empty() -> None:
    assert len(_DISCOURSE_HOSTS) > 0


# ---------------------------------------------------------------------------
# _fetch_discourse_paragraphs
# ---------------------------------------------------------------------------

_FAKE_DISCOURSE_JSON = b"""{
  "topic_list": {
    "topics": [
      {
        "id": 1,
        "title": "Undervalued DeFi token looking for partnership",
        "excerpt": "This is a hidden gem early stage blockchain project seeking investors and community growth."
      },
      {
        "id": 2,
        "title": "Another defi protocol with solid tokenomics",
        "excerpt": "Low cap undiscovered token with organic growth and fair launch."
      },
      {
        "id": 3,
        "title": "short",
        "excerpt": "tiny"
      }
    ]
  }
}"""


def _make_discourse_urlopen_mock(content: bytes):
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = content
    return mock_resp


def test_fetch_discourse_paragraphs_returns_list() -> None:
    mock_resp = _make_discourse_urlopen_mock(_FAKE_DISCOURSE_JSON)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _fetch_discourse_paragraphs("https://ethereum-magicians.org/latest")
    assert isinstance(result, list)


def test_fetch_discourse_paragraphs_combines_title_and_excerpt() -> None:
    mock_resp = _make_discourse_urlopen_mock(_FAKE_DISCOURSE_JSON)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _fetch_discourse_paragraphs("https://ethereum-magicians.org/latest", min_len=10)
    assert any("Undervalued DeFi token" in p for p in result)
    assert any("hidden gem" in p for p in result)


def test_fetch_discourse_paragraphs_respects_min_len() -> None:
    mock_resp = _make_discourse_urlopen_mock(_FAKE_DISCOURSE_JSON)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _fetch_discourse_paragraphs("https://ethereum-magicians.org/latest", min_len=40)
    # The "short — tiny" combo is only 12 chars and should be filtered out
    assert all(len(p) >= 40 for p in result)


def test_fetch_discourse_paragraphs_respects_max_count() -> None:
    mock_resp = _make_discourse_urlopen_mock(_FAKE_DISCOURSE_JSON)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _fetch_discourse_paragraphs(
            "https://ethereum-magicians.org/latest", min_len=10, max_count=1
        )
    assert len(result) <= 1


# ---------------------------------------------------------------------------
# scan_forums — Discourse dispatch
# ---------------------------------------------------------------------------


_DISCOURSE_PARAS = [
    "Undervalued DeFi token seeking partnership early stage blockchain hidden gem investors.",
    "Low cap defi protocol tokenomics undiscovered organic growth community grassroots.",
]


def test_scan_forums_discourse_url_discovers_assets() -> None:
    """Discourse URLs trigger the JSON API path and discover assets."""
    with patch(
        "vectra_flow.asset_scout._fetch_discourse_paragraphs",
        return_value=_DISCOURSE_PARAS,
    ):
        result = scan_forums(["https://ethereum-magicians.org/latest"], min_score=0.1)
    assert len(result) > 0
    assert all(isinstance(a, ScoutedAsset) for a in result)


def test_scan_forums_discourse_url_does_not_call_fetch_html() -> None:
    """For Discourse URLs, _fetch_html must NOT be called."""
    with (
        patch(
            "vectra_flow.asset_scout._fetch_discourse_paragraphs",
            return_value=_DISCOURSE_PARAS,
        ) as mock_discourse,
        patch("vectra_flow.asset_scout._fetch_html") as mock_html,
    ):
        scan_forums(["https://ethereum-magicians.org/latest"], min_score=0.1)
    mock_discourse.assert_called_once()
    mock_html.assert_not_called()


def test_scan_forums_non_discourse_url_does_not_call_discourse_fetcher() -> None:
    """For non-Discourse URLs, _fetch_discourse_paragraphs must NOT be called."""
    with (
        patch("vectra_flow.asset_scout._fetch_html", side_effect=_make_mock_fetch()),
        patch(
            "vectra_flow.asset_scout._fetch_discourse_paragraphs"
        ) as mock_discourse,
    ):
        scan_forums(["https://old.reddit.com/r/CryptoMoonShots/"], min_score=0.1)
    mock_discourse.assert_not_called()

