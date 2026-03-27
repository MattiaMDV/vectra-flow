"""Partnership Notification Module.

When the scout identifies promising digital assets, this module composes a
structured partnership-outreach proposal and saves it to disk for review and
dispatch.

Business model
--------------
* **2-week free promotional period** — Vectra-Flow provides free visibility
  and publicity for the asset (forum posts, social shares, community
  introductions) with no up-front cost.
* **Revenue-share clause** — After the 14-day free window the standard
  revenue-share rate of **≥ 15 %** of the asset's proceeds (sale,
  funding round, or token distribution) applies for the duration of the
  promotional campaign.

Outreach message
----------------
Each proposal contains:
- A personalised introduction explaining Vectra-Flow's value proposition.
- A description of what promotional activities Vectra-Flow will deliver.
- The partnership terms (free period + revenue share).
- Contact / reply instructions.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from vectra_flow.asset_scout import ScoutedAsset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FREE_PERIOD_DAYS: int = 14
"""Duration of the complimentary promotional period in calendar days."""

MIN_FEE_RATE: float = 0.15
"""Minimum revenue-share percentage (15 %) applied after the free period."""

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PartnershipProposal:
    """A partnership outreach proposal generated for a :class:`ScoutedAsset`.

    Attributes
    ----------
    asset_name:
        Name / ticker of the discovered asset.
    source_url:
        Forum URL where the asset was discovered.
    source_platform:
        Platform label (e.g. ``"reddit"``, ``"bitcointalk"``).
    snippet:
        Short excerpt from the discovery page.
    discovery_score:
        Scout relevance score (0.0–1.0).
    tickers:
        Ticker symbols found in the discovery snippet.
    project_urls:
        External links found near the asset mention.
    created_at:
        UTC timestamp when the proposal was created.
    free_period_ends_at:
        UTC timestamp when the free promotional period expires.
    fee_rate:
        Revenue-share rate as a decimal (e.g. ``0.15`` = 15 %).
    outreach_message:
        The full text of the partnership proposal to be sent.
    """

    asset_name: str
    source_url: str
    source_platform: str
    snippet: str
    discovery_score: float
    tickers: list[str]
    project_urls: list[str]
    created_at: str
    free_period_ends_at: str
    fee_rate: float
    outreach_message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_fee_rate(
    partnership_start: datetime,
    *,
    now: datetime | None = None,
    base_rate: float = MIN_FEE_RATE,
) -> float:
    """Return the applicable revenue-share rate for a partnership.

    During the first :data:`FREE_PERIOD_DAYS` the rate is ``0.0`` (free).
    After that the rate is *base_rate* (default 15 %).

    Parameters
    ----------
    partnership_start:
        The UTC datetime when the partnership / free period started.
    now:
        Current UTC datetime (defaults to ``datetime.now(timezone.utc)``).
    base_rate:
        The post-free-period revenue-share fraction (default 0.15).

    Returns
    -------
    float
        ``0.0`` during the free period, ``base_rate`` thereafter.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elapsed = (now - partnership_start).days
    return 0.0 if elapsed < FREE_PERIOD_DAYS else base_rate


def create_proposal(asset: ScoutedAsset) -> PartnershipProposal:
    """Build a :class:`PartnershipProposal` for a discovered *asset*.

    Parameters
    ----------
    asset:
        A :class:`~vectra_flow.asset_scout.ScoutedAsset` returned by
        :func:`~vectra_flow.asset_scout.scan_forums`.

    Returns
    -------
    PartnershipProposal
        A fully populated proposal including the outreach message text.
    """
    now = datetime.now(timezone.utc)
    # Compute the free-period end date (14 days from now)
    free_period_ends_at = now + timedelta(days=FREE_PERIOD_DAYS)

    tickers_str = (
        ", ".join(f"${t}" for t in asset.tickers) if asset.tickers else asset.name
    )
    project_link = asset.project_urls[0] if asset.project_urls else asset.source_url

    message = _render_outreach_message(
        asset_name=asset.name,
        tickers_str=tickers_str,
        source_platform=asset.source_platform,
        source_url=asset.source_url,
        project_link=project_link,
        free_period_days=FREE_PERIOD_DAYS,
        fee_rate_pct=int(MIN_FEE_RATE * 100),
        free_period_ends=free_period_ends_at.strftime("%Y-%m-%d"),
    )

    return PartnershipProposal(
        asset_name=asset.name,
        source_url=asset.source_url,
        source_platform=asset.source_platform,
        snippet=asset.snippet,
        discovery_score=asset.score,
        tickers=asset.tickers,
        project_urls=asset.project_urls,
        created_at=now.isoformat(),
        free_period_ends_at=free_period_ends_at.isoformat(),
        fee_rate=MIN_FEE_RATE,
        outreach_message=message,
    )


def create_proposals(assets: Sequence[ScoutedAsset]) -> list[PartnershipProposal]:
    """Create a :class:`PartnershipProposal` for each asset in *assets*.

    Parameters
    ----------
    assets:
        Sequence of :class:`~vectra_flow.asset_scout.ScoutedAsset` objects.

    Returns
    -------
    list[PartnershipProposal]
        One proposal per asset, ordered the same as the input.
    """
    return [create_proposal(a) for a in assets]


def write_proposals(
    proposals: Sequence[PartnershipProposal],
    out_dir: Path,
) -> list[Path]:
    """Persist *proposals* to disk as JSON, Markdown, and plain-text files.

    Parameters
    ----------
    proposals:
        Sequence of :class:`PartnershipProposal` objects to save.
    out_dir:
        Directory where output files are written (created if absent).

    Returns
    -------
    list[Path]
        Paths of the files that were written:
        ``[notifications.json, notifications.md, notifications.txt]``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- JSON ----------------------------------------------------------
    json_path = out_dir / "notifications.json"
    json_path.write_text(
        json.dumps([dataclasses.asdict(p) for p in proposals], indent=2),
        encoding="utf-8",
    )

    # ---- Markdown ------------------------------------------------------
    md_path = out_dir / "notifications.md"
    md_path.write_text(_render_markdown(proposals), encoding="utf-8")

    # ---- Plain-text (one message per asset, ready to copy-paste) ------
    txt_path = out_dir / "notifications.txt"
    txt_path.write_text(_render_plaintext(proposals), encoding="utf-8")

    return [json_path, md_path, txt_path]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _render_outreach_message(
    *,
    asset_name: str,
    tickers_str: str,
    source_platform: str,
    source_url: str,
    project_link: str,
    free_period_days: int,
    fee_rate_pct: int,
    free_period_ends: str,
) -> str:
    """Compose the full partnership outreach message."""
    return (
        f"Subject: Partnership Proposal — Free Promotional Campaign for {asset_name}\n"
        "\n"
        f"Hello {asset_name} team,\n"
        "\n"
        f"I'm reaching out on behalf of **Vectra-Flow**, an autonomous digital-asset "
        f"discovery and promotion agent.  We found {tickers_str} while monitoring "
        f"{source_platform} ({source_url}) and believe your project has strong "
        f"potential that deserves wider attention.\n"
        "\n"
        "**What we offer:**\n"
        "• Active promotion across Reddit (crypto subreddits), Bitcointalk, "
        "Ethereum governance forums, Binance Square, and other crypto communities.\n"
        "• Regular community updates and engagement posts highlighting your project's "
        "value proposition.\n"
        "• Inclusion in our curated 'Undervalued Assets' report distributed to our "
        "subscriber network.\n"
        "\n"
        "**Partnership terms:**\n"
        f"• **Free for the first {free_period_days} days** (until {free_period_ends}) "
        "— zero cost, full promotional service.\n"
        f"• After the free period: a **{fee_rate_pct}% revenue-share** on proceeds "
        "attributable to the campaign (token sale, funding round, or equivalent). "
        "This is the minimum rate; higher tiers unlock additional promotional channels.\n"
        "\n"
        "**Next steps:**\n"
        "If you're interested, simply reply to this message or reach out at the "
        "contact details below.  We'll kick off the promotional campaign immediately "
        "at no cost to you.\n"
        "\n"
        f"Project we found: {project_link}\n"
        "\n"
        "Best regards,\n"
        "Vectra-Flow Partnership Team\n"
        "https://github.com/MattiaMDV/vectra-flow\n"
    )


def _render_markdown(proposals: Sequence[PartnershipProposal]) -> str:
    lines: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()
    lines.append("# Vectra-Flow — Partnership Notifications")
    lines.append("")
    lines.append(f"Generated at (UTC): **{generated_at}**")
    lines.append(f"Total proposals: **{len(proposals)}**")
    lines.append("")

    for i, p in enumerate(proposals, 1):
        lines.append(f"## {i}. {p.asset_name}")
        lines.append(f"- **Platform:** {p.source_platform}")
        lines.append(f"- **Source URL:** {p.source_url}")
        lines.append(f"- **Discovery score:** {p.discovery_score:.3f}")
        lines.append(f"- **Created at:** {p.created_at}")
        lines.append(f"- **Free period ends:** {p.free_period_ends_at}")
        lines.append(f"- **Fee rate (post-free):** {int(p.fee_rate * 100)}%")
        if p.tickers:
            lines.append(f"- **Tickers:** {', '.join(p.tickers)}")
        if p.project_urls:
            lines.append(f"- **Project URLs:** {', '.join(p.project_urls)}")
        lines.append("")
        lines.append("**Snippet:**")
        lines.append(f"> {p.snippet[:300]}")
        lines.append("")
        lines.append("**Outreach message:**")
        lines.append("")
        lines.append("```")
        lines.append(p.outreach_message)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append(
        "_Vectra-Flow — automated partnership outreach. "
        f"Free for the first {FREE_PERIOD_DAYS} days, "
        f"then ≥{int(MIN_FEE_RATE * 100)}% revenue share._"
    )
    return "\n".join(lines)


def _render_plaintext(proposals: Sequence[PartnershipProposal]) -> str:
    separator = "=" * 72
    parts: list[str] = [
        "VECTRA-FLOW PARTNERSHIP NOTIFICATIONS",
        separator,
        "",
    ]
    for p in proposals:
        parts.append(p.outreach_message)
        parts.append(separator)
        parts.append("")
    return "\n".join(parts)
