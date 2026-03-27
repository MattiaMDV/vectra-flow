"""Digital Real Estate & Flip — Asset Report Module.

Generates HTML, Markdown, and JSON portfolio reports from a list of scored
:class:`~vectra_flow.asset_score.AssetOpportunity` objects.
"""

from __future__ import annotations

import dataclasses
import html
import json
from pathlib import Path

import pandas as pd

from vectra_flow.asset_score import AssetOpportunity

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_STRATEGY_ICON: dict[str, str] = {
    "flip": "🚀",
    "hold": "💼",
    "skip": "⏭️",
}
_STRATEGY_LABEL: dict[str, str] = {
    "flip": "Flip (36× MRR target)",
    "hold": "Hold (cash-flow)",
    "skip": "Skip",
}


def render_asset_html(assets: list[AssetOpportunity]) -> str:
    """Return a self-contained HTML portfolio report for *assets*."""

    def esc(value: object) -> str:
        return html.escape(str(value))

    generated_at = pd.Timestamp.now("UTC").isoformat()

    rows_html = ""
    for a in assets:
        icon = _STRATEGY_ICON.get(a.exit_strategy, "⏭️")
        label = _STRATEGY_LABEL.get(a.exit_strategy, "Skip")
        recs_html = "".join(f"<li>{esc(r)}</li>" for r in a.recommendations)
        rows_html += f"""
  <div class='asset-card strategy-{esc(a.exit_strategy)}'>
    <h3>{esc(a.title)}</h3>
    <p class='url'><a href='{esc(a.url)}' target='_blank' rel='noopener'>{esc(a.url)}</a></p>
    <div class='asset-meta'>
      <span class='badge score-badge'>Score {esc(a.score)}</span>
      <span class='badge strategy-badge'>{icon} {esc(label)}</span>
      <span class='badge'>Category: {esc(a.category)}</span>
    </div>
    <table class='metrics'>
      <tr><td>Asking price</td><td><strong>${esc(f'{a.asking_price:,.0f}')}</strong></td></tr>
      <tr><td>Monthly revenue (MRR)</td><td><strong>${esc(f'{a.monthly_revenue:,.0f}')}</strong></td></tr>
      <tr><td>Revenue multiple</td><td>{esc(f'{a.revenue_multiple:.1f}')}×</td></tr>
      <tr><td>Monthly traffic</td><td>{esc(f'{a.monthly_traffic:,}')}</td></tr>
      <tr><td>Est. post-optimisation value</td>
          <td><strong>${esc(f'{a.estimated_post_optimization_value:,.0f}')}</strong></td></tr>
      <tr><td>Monetisation gaps</td>
          <td>{esc(', '.join(a.monetization_gaps) or '—')}</td></tr>
      <tr><td>Email list</td>
          <td>{'✅ Yes' if a.has_email_list else '❌ No'}</td></tr>
    </table>
    <div class='recs'><strong>Recommendations:</strong><ul>{recs_html}</ul></div>
  </div>"""

    total = len(assets)
    flippable = sum(1 for a in assets if a.exit_strategy == "flip")
    holdable = sum(1 for a in assets if a.exit_strategy == "hold")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vectra Flow — Digital Asset Portfolio</title>
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
    .asset-card {{background:#fff;border-radius:8px;padding:1.25rem 1.5rem;
                  box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:1.25rem;
                  border-left:5px solid #ccc;}}
    .strategy-flip {{border-left-color:#43a047;}}
    .strategy-hold {{border-left-color:#1976d2;}}
    .strategy-skip {{border-left-color:#9e9e9e;}}
    .url {{margin:.25rem 0 .75rem;font-size:.9em;}}
    .url a {{color:#0f3460;}}
    .asset-meta {{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem;}}
    .badge {{background:#e0e0e0;color:#333;border-radius:12px;
             padding:.15rem .7rem;font-size:.8rem;font-weight:600;}}
    .score-badge {{background:#fce4ec;color:#c62828;}}
    .strategy-flip .strategy-badge {{background:#e8f5e9;color:#1b5e20;}}
    .strategy-hold .strategy-badge {{background:#e3f2fd;color:#0d47a1;}}
    .metrics {{border-collapse:collapse;width:100%;margin-bottom:.75rem;}}
    .metrics td {{padding:.3rem .5rem;border-bottom:1px solid #f0f0f0;font-size:.9em;}}
    .metrics tr:last-child td {{border-bottom:none;}}
    .recs ul {{margin:.4rem 0 0;padding-left:1.2rem;}}
    .recs li {{margin:.3rem 0;line-height:1.5;font-size:.9em;}}
    footer {{margin-top:2rem;font-size:.8rem;color:#888;border-top:1px solid #ddd;
             padding-top:1rem;}}
  </style>
</head>
<body>
  <h1>Vectra Flow — Digital Asset Portfolio</h1>

  <div class="summary">
    <ul>
      <li><strong>Generated at (UTC):</strong> {esc(generated_at)}</li>
      <li><strong>Assets analysed:</strong> {esc(total)}</li>
      <li><strong>Recommended to flip:</strong> {esc(flippable)}</li>
      <li><strong>Recommended to hold:</strong> {esc(holdable)}</li>
    </ul>
  </div>

  <h2>Asset Opportunities (ranked by score)</h2>
  {rows_html}

  <footer>
    Vectra Flow — Digital Real Estate &amp; Flip engine.
    Scores and recommendations are generated automatically and do not
    constitute financial advice.
    &nbsp;|&nbsp; <a href="./asset_latest.md">Download Markdown version</a>
  </footer>
</body>
</html>
"""


def render_asset_markdown(assets: list[AssetOpportunity]) -> str:
    """Return a Markdown portfolio report for *assets*."""
    lines: list[str] = []
    generated_at = pd.Timestamp.now("UTC").isoformat()

    lines.append("# Vectra Flow — Digital Asset Portfolio")
    lines.append("")
    lines.append(f"Generated at (UTC): **{generated_at}**")
    lines.append(f"Assets analysed: **{len(assets)}**")
    lines.append("")

    for a in assets:
        icon = _STRATEGY_ICON.get(a.exit_strategy, "⏭️")
        label = _STRATEGY_LABEL.get(a.exit_strategy, "Skip")
        lines.append(f"## {a.title}")
        lines.append(f"- URL: {a.url}")
        lines.append(f"- Category: {a.category}")
        lines.append(f"- **Score:** {a.score}")
        lines.append(f"- **Exit strategy:** {icon} {label}")
        lines.append(f"- Asking price: ${a.asking_price:,.0f}")
        lines.append(f"- Monthly revenue (MRR): ${a.monthly_revenue:,.0f}")
        lines.append(f"- Revenue multiple: {a.revenue_multiple:.1f}×")
        lines.append(f"- Monthly traffic: {a.monthly_traffic:,}")
        lines.append(
            f"- Est. post-optimisation value: "
            f"${a.estimated_post_optimization_value:,.0f}"
        )
        lines.append(
            f"- Monetisation gaps: "
            f"{', '.join(a.monetization_gaps) if a.monetization_gaps else '—'}"
        )
        lines.append(f"- Email list: {'Yes' if a.has_email_list else 'No'}")
        if a.recommendations:
            lines.append("")
            lines.append("**Recommendations:**")
            for rec in a.recommendations:
                lines.append(f"- {rec}")
        lines.append("")

    lines.append("---")
    lines.append(
        "Vectra Flow — Digital Real Estate & Flip engine. "
        "Scores and recommendations are generated automatically and do not "
        "constitute financial advice."
    )
    return "\n".join(lines)


def write_asset_reports(
    assets: list[AssetOpportunity], out_dir: Path
) -> list[Path]:
    """Write JSON, Markdown, and HTML reports to *out_dir*.

    Returns a list of the paths that were written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "asset_latest.json"
    json_path.write_text(
        json.dumps([dataclasses.asdict(a) for a in assets], indent=2),
        encoding="utf-8",
    )

    md = render_asset_markdown(assets)
    md_path = out_dir / "asset_latest.md"
    md_path.write_text(md, encoding="utf-8")

    html_path = out_dir / "asset_latest.html"
    html_path.write_text(render_asset_html(assets), encoding="utf-8")

    return [json_path, md_path, html_path]
