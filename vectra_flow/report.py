from dataclasses import asdict
from pathlib import Path
import html
import json
from vectra_flow.analyze import AnalysisResults

def render_html(r: AnalysisResults) -> str:
    """Render a self-contained HTML page for the report."""

    def esc(value: object) -> str:
        return html.escape(str(value))

    rows_html = ""
    for row in r.sentiment_by_product[:10]:
        sentiment_str = f"{row['sentiment_compound_mean']:.3f}"
        rating_str = f"{row['rating_mean']:.2f}"
        rows_html += (
            f"<tr><td>{esc(row['product'])}</td>"
            f"<td>{esc(row['rows'])}</td>"
            f"<td>{esc(sentiment_str)}</td>"
            f"<td>{esc(rating_str)}</td></tr>\n"
        )

    topics_html = ""
    for t in r.topics:
        terms = esc(", ".join(t.top_terms))
        examples_html = ""
        for ex in t.examples:
            date_str = esc(ex["date"] or "—")
            product_str = esc(ex["product"])
            rating_str = esc(ex["rating"] if ex["rating"] is not None else "—")
            sentiment_str = esc(f'{ex["sentiment_compound"]:.3f}')
            text_str = esc(ex["text"])
            examples_html += (
                f"<li><span class='meta'>({date_str}) [{product_str}] "
                f"rating={rating_str} sentiment={sentiment_str}</span> — {text_str}</li>\n"
            )
        topics_html += (
            f"<div class='topic'>"
            f"<h3>Topic {esc(t.topic_id)} <span class='badge'>n={esc(t.size)}</span></h3>"
            f"<p class='terms'><strong>Top terms:</strong> <code>{terms}</code></p>"
            f"<ul>{examples_html}</ul>"
            f"</div>\n"
        )

    date_range_html = ""
    if r.date_min and r.date_max:
        date_range_html = (
            f"<li><strong>Date range:</strong> {esc(r.date_min)} → {esc(r.date_max)}</li>"
        )

    rating_html = ""
    if r.sentiment_overall.get("rows_with_rating", 0) > 0:
        rating_mean_str = f"{r.sentiment_overall['rating_mean']:.2f}"
        rating_html = (
            f"<li><strong>Mean rating:</strong> "
            f"{esc(rating_mean_str)} "
            f"(n={esc(r.sentiment_overall['rows_with_rating'])})</li>"
        )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vectra Flow — Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           max-width: 900px; margin: 0 auto; padding: 2rem 1rem; color: #1a1a2e; background: #f8f9fa; }}
    h1 {{ color: #0f3460; border-bottom: 3px solid #e94560; padding-bottom: .5rem; }}
    h2 {{ color: #16213e; margin-top: 2rem; }}
    h3 {{ color: #0f3460; }}
    .meta-block {{ background: #fff; border-radius: 8px; padding: 1rem 1.5rem;
                   box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 1.5rem; }}
    .meta-block ul {{ list-style: none; padding: 0; margin: 0; }}
    .meta-block li {{ padding: .25rem 0; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff;
             border-radius: 8px; overflow: hidden;
             box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    th {{ background: #0f3460; color: #fff; padding: .6rem 1rem; text-align: left; }}
    td {{ padding: .5rem 1rem; border-bottom: 1px solid #eee; }}
    tr:last-child td {{ border-bottom: none; }}
    .topic {{ background: #fff; border-radius: 8px; padding: 1rem 1.5rem;
              box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 1rem; }}
    .badge {{ background: #e94560; color: #fff; border-radius: 12px;
              padding: .1rem .6rem; font-size: .8rem; font-weight: 600; }}
    .terms {{ margin: .25rem 0; }}
    code {{ background: #f0f4ff; padding: .1rem .4rem; border-radius: 4px; font-size: .9em; }}
    ul {{ padding-left: 1.2rem; }}
    li {{ margin: .3rem 0; line-height: 1.5; }}
    .meta {{ color: #666; font-size: .85em; }}
    .feedback {{ background: #fff8e1; border-left: 4px solid #ffc107;
                 padding: 1rem 1.5rem; border-radius: 0 8px 8px 0; margin-top: 1.5rem; }}
    footer {{ margin-top: 2rem; font-size: .8rem; color: #888; border-top: 1px solid #ddd;
              padding-top: 1rem; }}
    a {{ color: #0f3460; }}
  </style>
</head>
<body>
  <h1>Vectra Flow — Sentiment &amp; Trends Report</h1>

  <div class="meta-block">
    <ul>
      <li><strong>Generated at (UTC):</strong> {esc(r.generated_at_utc)}</li>
      <li><strong>Rows analyzed:</strong> {esc(r.rows)}</li>
      {date_range_html}
    </ul>
  </div>

  <h2>Overall</h2>
  <div class="meta-block">
    <ul>
      <li><strong>Mean text sentiment (VADER compound):</strong>
          {esc(f"{r.sentiment_overall['sentiment_compound_mean']:.3f}")}</li>
      {rating_html}
    </ul>
  </div>

  <h2>By product (top)</h2>
  <table>
    <thead><tr><th>Product</th><th>Rows</th><th>Sentiment</th><th>Rating</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>

  <h2>Topics (clusters)</h2>
  {topics_html}

  <div class="feedback">
    <h2 style="margin-top:0">Customer Feedback <small>(to be filled by the client)</small></h2>
    <ul>
      <li>Utility rating (1–5):</li>
      <li>Most useful insight this week:</li>
      <li>What's missing / unclear:</li>
      <li>Would you recommend it? (NPS 0–10):</li>
    </ul>
  </div>

  <footer>
    Beta note: this report is produced during the initial 2-week free Beta.
    Vectra Flow will expand with paid tools/integrations and broader services after validation.
    &nbsp;|&nbsp; <a href="./latest.md">Download Markdown version</a>
  </footer>
</body>
</html>
"""

def render_markdown(r: AnalysisResults) -> str:
    lines = []
    lines.append("# Vectra Flow — Sentiment & Trends Report")
    lines.append("")
    lines.append(f"Generated at (UTC): **{r.generated_at_utc}**")
    lines.append(f"Rows analyzed: **{r.rows}**")
    if r.date_min and r.date_max:
        lines.append(f"Date range: **{r.date_min} → {r.date_max}**")
    lines.append("")
    lines.append("## Overall")
    lines.append(f"- Mean text sentiment (VADER compound): **{r.sentiment_overall['sentiment_compound_mean']:.3f}**")
    if r.sentiment_overall["rows_with_rating"] > 0:
        lines.append(f"- Mean rating: **{r.sentiment_overall['rating_mean']:.2f}** (n={r.sentiment_overall['rows_with_rating']})")
    lines.append("")
    lines.append("## By product (top)")
    for row in r.sentiment_by_product[:10]:
        lines.append(f"- **{row['product']}** — rows={row['rows']}, sentiment={row['sentiment_compound_mean']:.3f}, rating={row['rating_mean']:.2f}")
    lines.append("")
    lines.append("## Topics (clusters)")
    for t in r.topics:
        lines.append(f"### Topic {t.topic_id} (n={t.size})")
        lines.append(f"Top terms: `{', '.join(t.top_terms)}`")
        lines.append("")
        lines.append("Examples:")
        for ex in t.examples:
            lines.append(f"- ({ex['date']}) [{ex['product']}] rating={ex['rating']} sentiment={ex['sentiment_compound']:.3f} — {ex['text']}")
        lines.append("")

    lines.append("## Customer Feedback (to be filled by the client)")
    lines.append("- Utility rating (1–5):")
    lines.append("- Most useful insight this week:")
    lines.append("- What’s missing / unclear:")
    lines.append("- Would you recommend it? (NPS 0–10):")
    lines.append("")
    lines.append("---")
    lines.append("Beta note: this report is produced during the initial 2-week free Beta. Vectra Flow will expand with paid tools/integrations and broader services after validation.")
    return "\n".join(lines)

def write_reports(r: AnalysisResults, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "latest.json").write_text(json.dumps(asdict(r), indent=2), encoding="utf-8")
    md = render_markdown(r)
    (out_dir / "latest.md").write_text(md, encoding="utf-8")
    dated = out_dir / f"{r.generated_at_utc[:10]}_report.md"
    dated.write_text(md, encoding="utf-8")
    (out_dir / "latest.html").write_text(render_html(r), encoding="utf-8")

    return [out_dir / "latest.md", dated, out_dir / "latest.json", out_dir / "latest.html"]
