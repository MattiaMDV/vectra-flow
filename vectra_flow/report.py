"""
Report generation module for vectra_flow.

Produces an HTML report from the analysed opportunity list.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from vectra_flow.config import Config

logger = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Vectra-Flow Report – {date}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f9f9f9; }}
    h1   {{ color: #2c3e50; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td {{ border: 1px solid #ddd; padding: 0.6rem 1rem; text-align: left; }}
    th   {{ background: #2c3e50; color: #fff; }}
    tr:nth-child(even) {{ background: #f2f2f2; }}
    .score {{ font-weight: bold; color: #27ae60; }}
    .footer {{ margin-top: 2rem; font-size: 0.85rem; color: #999; }}
  </style>
</head>
<body>
  <h1>Vectra-Flow – Opportunity Report</h1>
  <p>Generated on <strong>{date}</strong> | {count} opportunities found</p>
  <table>
    <thead>
      <tr>
        <th>#</th>
        {headers}
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <div class="footer">Powered by vectra-flow v{version}</div>
</body>
</html>
"""


def _build_rows(records: List[Dict[str, Any]]) -> tuple[str, str]:
    """Return (header_html, body_html) for the records table."""
    if not records:
        return "", "<tr><td colspan='99'>No opportunities found.</td></tr>"

    all_keys = list(records[0].keys())
    headers = "".join(f"<th>{k}</th>" for k in all_keys)

    rows_html = []
    for idx, rec in enumerate(records, start=1):
        cells = []
        for k, v in rec.items():
            cls = ' class="score"' if k == "score" else ""
            cells.append(f"<td{cls}>{v}</td>")
        rows_html.append(f"<tr><td>{idx}</td>{''.join(cells)}</tr>")

    return headers, "\n      ".join(rows_html)


def generate_report(
    records: List[Dict[str, Any]],
    output: Path | str | None = None,
) -> Path:
    """Write an HTML report and return the output path.

    Args:
        records: Scored records from :func:`vectra_flow.analyze.analyze`.
        output: Destination file. Defaults to ``<REPORTS_DIR>/<timestamp>_report.html``.

    Returns:
        Path to the generated report file.
    """
    from vectra_flow import __version__

    cfg = Config()
    cfg.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if output is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = cfg.REPORTS_DIR / f"{timestamp}_report.html"
    else:
        out_path = Path(output)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    headers, rows = _build_rows(records)

    html = _HTML_TEMPLATE.format(
        date=date_str,
        count=len(records),
        headers=headers,
        rows=rows,
        version=__version__,
    )

    out_path.write_text(html, encoding="utf-8")
    logger.info("Report written to %s", out_path)
    return out_path
