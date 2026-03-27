"""Digital Real Estate & Flip — Asset Scoring Module.

Implements the three active roles of Vectra-Flow's autonomous portfolio manager:

* **Hunter** — evaluates acquisition potential by scoring each asset on price,
  revenue multiple, traffic, and untapped monetisation channels.
* **Mechanic** — generates concrete optimisation recommendations (SEO, copy
  rewrites, UI/UX hints, speed improvements).
* **Seller** — decides the exit strategy (hold as cash-flow or flip at a
  target 10× multiple) and estimates the post-optimisation asset value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

ExitStrategy = Literal["flip", "hold", "skip"]

# Technologies considered outdated that signal a modernisation opportunity.
_OUTDATED_TECH: frozenset[str] = frozenset({"php4", "php5", "jquery", "flash"})


@dataclass
class AssetOpportunity:
    """Represents a single digital asset acquisition candidate.

    Required fields (provided by the caller / CSV):
        url, title, asking_price, monthly_revenue, monthly_traffic

    Computed fields (populated by :func:`score_asset`):
        score, revenue_multiple, monetization_gaps, recommendations,
        exit_strategy, estimated_post_optimization_value
    """

    url: str
    title: str
    asking_price: float          # USD – listed price
    monthly_revenue: float       # USD – current MRR
    monthly_traffic: int         # estimated monthly unique visitors

    tech_stack: list[str] = field(default_factory=list)
    category: str = "micro-saas"
    has_email_list: bool = False
    current_monetization: str = ""

    # Computed by score_asset()
    score: float = 0.0
    revenue_multiple: float = 0.0
    monetization_gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    exit_strategy: ExitStrategy = "skip"
    estimated_post_optimization_value: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_asset(asset: AssetOpportunity) -> AssetOpportunity:
    """Compute acquisition score and populate all derived fields in-place.

    Returns the same *asset* instance (mutated) for convenience.
    """
    score = 0.0

    # 1. Revenue-multiple score (lower multiple = better deal)
    if asset.monthly_revenue > 0:
        multiple = asset.asking_price / asset.monthly_revenue
        asset.revenue_multiple = round(multiple, 2)
        if multiple <= 6:
            score += 30
        elif multiple <= 12:
            score += 20
        elif multiple <= 24:
            score += 10
    else:
        asset.revenue_multiple = 0.0

    # 2. Traffic score
    if asset.monthly_traffic >= 10_000:
        score += 20
    elif asset.monthly_traffic >= 2_000:
        score += 12
    elif asset.monthly_traffic >= 500:
        score += 6

    # 3. Low asking-price score (micro-asset sweet-spot ≤ $1 000)
    if asset.asking_price <= 200:
        score += 20
    elif asset.asking_price <= 500:
        score += 14
    elif asset.asking_price <= 1_000:
        score += 8

    # 4. Monetisation-gap bonus (each untapped channel = +8, capped at 24)
    gaps = _detect_monetization_gaps(asset)
    asset.monetization_gaps = gaps
    score += min(len(gaps) * 8, 24)

    # 5. Email list bonus
    if asset.has_email_list:
        score += 6

    asset.score = round(min(score, 100.0), 1)

    # Recommendations
    asset.recommendations = _generate_recommendations(asset)

    # Exit strategy and estimated value
    if asset.score >= 60 and asset.monthly_revenue > 0:
        asset.exit_strategy = "flip"
        # Target: sell at 36× MRR after optimisation
        asset.estimated_post_optimization_value = round(
            asset.monthly_revenue * 36, 2
        )
    elif asset.score >= 35:
        asset.exit_strategy = "hold"
        # Conservative: 24× MRR + cost basis
        asset.estimated_post_optimization_value = round(
            asset.monthly_revenue * 24 + asset.asking_price, 2
        )
    else:
        asset.exit_strategy = "skip"
        asset.estimated_post_optimization_value = 0.0

    return asset


def score_assets(assets: list[AssetOpportunity]) -> list[AssetOpportunity]:
    """Score all *assets* and return them sorted by score descending."""
    scored = [score_asset(a) for a in assets]
    return sorted(scored, key=lambda a: a.score, reverse=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_monetization_gaps(asset: AssetOpportunity) -> list[str]:
    """Return a list of untapped monetisation channels for *asset*."""
    gaps: list[str] = []
    current = asset.current_monetization.lower()

    if "subscription" not in current and "premium" not in current:
        gaps.append("subscription")
    if "affiliate" not in current:
        gaps.append("affiliate")
    if (
        asset.monthly_traffic >= 2_000
        and "ads" not in current
        and "advertising" not in current
    ):
        gaps.append("display_ads")

    return gaps


def _generate_recommendations(asset: AssetOpportunity) -> list[str]:
    """Generate actionable optimisation recommendations for *asset*."""
    recs: list[str] = []

    for gap in asset.monetization_gaps:
        if gap == "subscription":
            recs.append(
                f"Introduce a freemium/subscription tier for '{asset.title}' "
                "(e.g. $2–5/month premium plan) to convert free users into "
                "recurring revenue."
            )
        elif gap == "affiliate":
            recs.append(
                "Add affiliate links for complementary tools/services in "
                f"the {asset.category} niche to generate passive commission."
            )
        elif gap == "display_ads":
            recs.append(
                f"With {asset.monthly_traffic:,} monthly visitors, "
                "display ads (e.g. Carbon Ads, EthicalAds) could generate "
                "meaningful passive revenue with zero additional effort."
            )

    if asset.monthly_traffic < 500:
        recs.append(
            "SEO overhaul needed: rewrite meta titles/descriptions with "
            "long-tail keywords, create a sitemap, and submit to Google Search "
            "Console to unlock organic traffic growth."
        )

    if not asset.has_email_list:
        recs.append(
            "Build an email list immediately — add a lead-magnet or newsletter "
            "signup to capture returning visitors and enable direct marketing."
        )

    if not asset.tech_stack or any(
        t.lower() in _OUTDATED_TECH for t in asset.tech_stack
    ):
        recs.append(
            "Modernise the tech stack: migrating to a contemporary framework "
            "improves page speed (Core Web Vitals), SEO ranking, and perceived "
            "value when reselling."
        )

    return recs
