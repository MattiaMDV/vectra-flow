"""Tests for vectra_flow.asset_score module."""
import pytest

from vectra_flow.asset_score import (
    AssetOpportunity,
    _detect_monetization_gaps,
    _generate_recommendations,
    score_asset,
    score_assets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_asset(**kwargs) -> AssetOpportunity:
    defaults = dict(
        url="https://example.com",
        title="Test Asset",
        asking_price=200.0,
        monthly_revenue=20.0,
        monthly_traffic=1000,
    )
    defaults.update(kwargs)
    return AssetOpportunity(**defaults)


# ---------------------------------------------------------------------------
# score_asset — basic contract
# ---------------------------------------------------------------------------

def test_score_asset_returns_same_instance() -> None:
    asset = _make_asset()
    result = score_asset(asset)
    assert result is asset


def test_score_asset_score_in_range() -> None:
    asset = _make_asset()
    score_asset(asset)
    assert 0.0 <= asset.score <= 100.0


def test_score_asset_zero_revenue_sets_zero_multiple() -> None:
    asset = _make_asset(monthly_revenue=0.0)
    score_asset(asset)
    assert asset.revenue_multiple == 0.0


def test_score_asset_revenue_multiple_computed() -> None:
    asset = _make_asset(asking_price=120.0, monthly_revenue=10.0)
    score_asset(asset)
    assert asset.revenue_multiple == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Exit strategy thresholds
# ---------------------------------------------------------------------------

def test_exit_strategy_flip_for_high_score() -> None:
    # Low price + revenue + traffic + monetisation gaps → high score
    asset = _make_asset(
        asking_price=200.0,
        monthly_revenue=40.0,
        monthly_traffic=12_000,
        current_monetization="",
        has_email_list=True,
    )
    score_asset(asset)
    assert asset.exit_strategy == "flip"


def test_exit_strategy_skip_for_zero_revenue_low_traffic() -> None:
    asset = _make_asset(
        asking_price=5_000.0,
        monthly_revenue=0.0,
        monthly_traffic=10,
        current_monetization="subscription, affiliate, ads",
        has_email_list=False,
    )
    score_asset(asset)
    assert asset.exit_strategy == "skip"


def test_exit_strategy_hold_for_medium_score() -> None:
    # revenue multiple = 600/25 = 24 → 10 pts
    # traffic = 600 (≥500) → 6 pts
    # asking_price = 600 (≤1000) → 8 pts
    # 2 monetisation gaps (subscription + affiliate) → 16 pts
    # total = 40 → hold
    asset = _make_asset(
        asking_price=600.0,
        monthly_revenue=25.0,
        monthly_traffic=600,
        current_monetization="",
    )
    score_asset(asset)
    assert asset.score == pytest.approx(40.0)
    assert asset.exit_strategy == "hold"


def test_estimated_value_zero_for_skip() -> None:
    asset = _make_asset(
        asking_price=10_000.0,
        monthly_revenue=0.0,
        monthly_traffic=0,
        current_monetization="subscription, affiliate, ads",
    )
    score_asset(asset)
    assert asset.exit_strategy == "skip"
    assert asset.estimated_post_optimization_value == 0.0


def test_estimated_value_positive_for_flip() -> None:
    asset = _make_asset(
        asking_price=200.0,
        monthly_revenue=40.0,
        monthly_traffic=12_000,
        current_monetization="",
        has_email_list=True,
    )
    score_asset(asset)
    assert asset.exit_strategy == "flip"
    assert asset.estimated_post_optimization_value == pytest.approx(40.0 * 36)


# ---------------------------------------------------------------------------
# Monetisation gap detection
# ---------------------------------------------------------------------------

def test_gaps_all_present_when_no_monetization() -> None:
    asset = _make_asset(
        monthly_traffic=5_000,
        current_monetization="",
    )
    gaps = _detect_monetization_gaps(asset)
    assert "subscription" in gaps
    assert "affiliate" in gaps
    assert "display_ads" in gaps


def test_no_display_ads_gap_for_low_traffic() -> None:
    asset = _make_asset(monthly_traffic=100, current_monetization="")
    gaps = _detect_monetization_gaps(asset)
    assert "display_ads" not in gaps


def test_no_subscription_gap_when_subscription_exists() -> None:
    asset = _make_asset(current_monetization="subscription")
    gaps = _detect_monetization_gaps(asset)
    assert "subscription" not in gaps


def test_no_affiliate_gap_when_affiliate_exists() -> None:
    asset = _make_asset(current_monetization="affiliate marketing")
    gaps = _detect_monetization_gaps(asset)
    assert "affiliate" not in gaps


# ---------------------------------------------------------------------------
# Recommendation generation
# ---------------------------------------------------------------------------

def test_recommendations_include_subscription_when_gap() -> None:
    asset = _make_asset(current_monetization="", monthly_traffic=100)
    score_asset(asset)
    combined = " ".join(asset.recommendations).lower()
    assert "subscription" in combined or "freemium" in combined


def test_recommendations_include_seo_for_low_traffic() -> None:
    asset = _make_asset(monthly_traffic=50, current_monetization="subscription, affiliate")
    score_asset(asset)
    combined = " ".join(asset.recommendations).lower()
    assert "seo" in combined


def test_recommendations_include_email_when_no_list() -> None:
    asset = _make_asset(has_email_list=False)
    score_asset(asset)
    combined = " ".join(asset.recommendations).lower()
    assert "email" in combined


def test_no_email_recommendation_when_list_exists() -> None:
    asset = _make_asset(
        has_email_list=True,
        current_monetization="subscription, affiliate",
        monthly_traffic=5_000,
    )
    score_asset(asset)
    combined = " ".join(asset.recommendations).lower()
    assert "email list" not in combined


# ---------------------------------------------------------------------------
# score_assets (batch)
# ---------------------------------------------------------------------------

def test_score_assets_returns_sorted() -> None:
    assets = [
        _make_asset(asking_price=5_000.0, monthly_revenue=0.0, monthly_traffic=0),
        _make_asset(asking_price=200.0, monthly_revenue=40.0, monthly_traffic=12_000, has_email_list=True),
    ]
    scored = score_assets(assets)
    assert scored[0].score >= scored[1].score


def test_score_assets_all_scored() -> None:
    assets = [_make_asset() for _ in range(5)]
    scored = score_assets(assets)
    assert all(a.score > 0 or a.score == 0 for a in scored)
    assert len(scored) == 5
