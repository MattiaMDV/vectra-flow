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
import html
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
    """Persist *proposals* to disk as JSON, Markdown, plain-text, and HTML files.

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
        ``[notifications.json, notifications.md, notifications.txt, notifications.html]``.
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

    # ---- HTML (published to GitHub Pages) ------------------------------
    html_path = out_dir / "notifications.html"
    html_path.write_text(_render_html(proposals), encoding="utf-8")

    return [json_path, md_path, txt_path, html_path]


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


def _render_html(proposals: Sequence[PartnershipProposal]) -> str:
    """Return a self-contained HTML page listing all partnership proposals."""

    def esc(value: object) -> str:
        return html.escape(str(value))

    generated_at = datetime.now(timezone.utc).isoformat()

    cards_html = ""
    for i, p in enumerate(proposals, 1):
        tickers_html = (
            f"<li><strong>Tickers:</strong> {esc(', '.join(p.tickers))}</li>"
            if p.tickers else ""
        )
        project_urls_html = ""
        if p.project_urls:
            links = " ".join(
                f"<a href='{esc(u)}' target='_blank' rel='noopener'>{esc(u)}</a>"
                for u in p.project_urls
            )
            project_urls_html = f"<li><strong>Project URLs:</strong> {links}</li>"
        cards_html += f"""
  <div class='proposal-card'>
    <h3>{esc(i)}. {esc(p.asset_name)}</h3>
    <div class='proposal-meta'>
      <span class='badge score-badge'>Score {esc(f'{p.discovery_score:.3f}')}</span>
      <span class='badge platform-badge'>{esc(p.source_platform)}</span>
    </div>
    <ul class='meta-list'>
      <li><strong>Source:</strong>
          <a href='{esc(p.source_url)}' target='_blank' rel='noopener'>{esc(p.source_url)}</a></li>
      <li><strong>Created at (UTC):</strong> {esc(p.created_at)}</li>
      <li><strong>Free period ends:</strong> {esc(p.free_period_ends_at)}</li>
      <li><strong>Fee rate (post-free):</strong> {esc(int(p.fee_rate * 100))}%</li>
      {tickers_html}
      {project_urls_html}
    </ul>
    <div class='snippet'>
      <strong>Snippet:</strong>
      <blockquote>{esc(p.snippet[:300])}</blockquote>
    </div>
    <div class='outreach'>
      <strong>Outreach message:</strong>
      <pre>{esc(p.outreach_message)}</pre>
    </div>
  </div>"""

    empty_html = ""
    if not proposals:
        empty_html = (
            "<p class='empty-notice'>No qualifying assets discovered in this scan. "
            "The scout will retry on the next scheduled run.</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vectra-Flow — Partnership Proposals</title>
  <style>
    body {{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
           max-width:960px;margin:0 auto;padding:2rem 1rem;color:#1a1a2e;background:#f8f9fa;}}
    h1 {{color:#0f3460;border-bottom:3px solid #e94560;padding-bottom:.5rem;}}
    h2 {{color:#16213e;margin-top:2rem;}}
    h3 {{color:#0f3460;margin-bottom:.25rem;}}
    .summary {{background:#fff;border-radius:8px;padding:1rem 1.5rem;
               box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:1.5rem;}}
    .summary ul {{list-style:none;padding:0;margin:0;}}
    .summary li {{padding:.25rem 0;}}
    .proposal-card {{background:#fff;border-radius:8px;padding:1.25rem 1.5rem;
                     box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:1.25rem;
                     border-left:5px solid #e94560;}}
    .proposal-meta {{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem;}}
    .badge {{background:#e0e0e0;color:#333;border-radius:12px;
             padding:.15rem .7rem;font-size:.8rem;font-weight:600;}}
    .score-badge {{background:#fce4ec;color:#c62828;}}
    .platform-badge {{background:#e3f2fd;color:#0d47a1;}}
    .meta-list {{list-style:none;padding:0;margin:.5rem 0;}}
    .meta-list li {{padding:.2rem 0;font-size:.9em;}}
    .meta-list a {{color:#0f3460;}}
    .snippet blockquote {{background:#f0f4ff;border-left:4px solid #1976d2;
                          margin:.5rem 0;padding:.5rem 1rem;border-radius:0 4px 4px 0;
                          font-size:.9em;}}
    .outreach pre {{background:#f9f9f9;border:1px solid #ddd;border-radius:4px;
                    padding:1rem;font-size:.85em;white-space:pre-wrap;
                    word-break:break-word;overflow-x:auto;}}
    .empty-notice {{background:#fff8e1;border-left:4px solid #ffc107;
                    padding:1rem 1.5rem;border-radius:0 8px 8px 0;
                    font-size:1rem;color:#5d4037;}}
    footer {{margin-top:2rem;font-size:.8rem;color:#888;border-top:1px solid #ddd;
             padding-top:1rem;}}
    a {{color:#0f3460;}}
  </style>
</head>
<body>
  <h1>Vectra-Flow — Partnership Proposals</h1>

  <div class="summary">
    <ul>
      <li><strong>Generated at (UTC):</strong> {esc(generated_at)}</li>
      <li><strong>Total proposals:</strong> {esc(len(proposals))}</li>
      <li><strong>Free period:</strong> {esc(FREE_PERIOD_DAYS)} days — zero cost</li>
      <li><strong>Revenue share (post-free):</strong> ≥{esc(int(MIN_FEE_RATE * 100))}%</li>
    </ul>
  </div>

  {empty_html}
  {cards_html}

  <footer>
    Vectra-Flow — automated partnership outreach.
    Free for the first {esc(FREE_PERIOD_DAYS)} days, then
    ≥{esc(int(MIN_FEE_RATE * 100))}% revenue share.
    &nbsp;|&nbsp; <a href="./notifications.md">Download Markdown version</a>
    &nbsp;|&nbsp; <a href="../assets.html">Asset evaluation report</a>
    &nbsp;|&nbsp; <a href="../index.html">Feedback report</a>
  </footer>
</body>
</html>
"""
