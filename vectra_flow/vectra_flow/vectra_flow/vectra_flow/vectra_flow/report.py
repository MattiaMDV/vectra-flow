from dataclasses import asdict
from pathlib import Path
import json
from vectra_flow.analyze import AnalysisResults

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

    return [out_dir / "latest.md", dated, out_dir / "latest.json"]
