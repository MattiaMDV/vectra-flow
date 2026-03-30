"""Digital Real Estate & Flip — Asset Ingest Module.

Loads digital-asset opportunity data from CSV files and converts each row
into an :class:`~vectra_flow.asset_score.AssetOpportunity` instance.

Expected CSV columns
--------------------
Required:
    url, title, asking_price, monthly_revenue, monthly_traffic

Optional (defaults applied when absent):
    tech_stack          comma-separated list, e.g. "Python, Django, PostgreSQL"
    category            default "micro-saas"
    has_email_list      true/yes/1 → True, anything else → False
    current_monetization  free-text describing existing revenue model
"""

from __future__ import annotations

import glob as _glob

import pandas as pd

from vectra_flow.asset_score import AssetOpportunity

_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"url", "title", "asking_price", "monthly_revenue", "monthly_traffic"}
)


def load_assets(
    input_glob: str,
    max_rows: int = 5_000,
    column_map: dict[str, str] | None = None,
) -> list[AssetOpportunity]:
    """Load asset opportunity CSV files matching *input_glob*.

    Parameters
    ----------
    input_glob:
        Glob pattern (e.g. ``"data/assets/*.csv"``).
    max_rows:
        Maximum number of rows to process across all matched files.
    column_map:
        Optional dict mapping source column names (e.g. from a Google Form
        export) to the required column names.  Example::

            {
                "URL asset":             "url",
                "Nome asset / Titolo":   "title",
                "Prezzo richiesto":      "asking_price",
                "MRR attuale (o 0)":     "monthly_revenue",
                "Traffico mensile":      "monthly_traffic",
            }

        Keys not present in the CSV are silently ignored.

    Returns
    -------
    list[AssetOpportunity]
        Unsorted list of asset candidates (scoring not yet applied).

    Raises
    ------
    FileNotFoundError
        If no files match *input_glob*.
    ValueError
        If a file is missing one or more required columns.
    """
    files = sorted(_glob.glob(input_glob))
    if not files:
        raise FileNotFoundError(f"No asset files matched: {input_glob!r}")

    frames: list[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path)
        if column_map:
            df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        _validate_columns(df, path)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Numeric coercion
    combined["asking_price"] = (
        pd.to_numeric(combined["asking_price"], errors="coerce").fillna(0.0)
    )
    combined["monthly_revenue"] = (
        pd.to_numeric(combined["monthly_revenue"], errors="coerce").fillna(0.0)
    )
    combined["monthly_traffic"] = (
        pd.to_numeric(combined["monthly_traffic"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    if len(combined) > max_rows:
        combined = combined.head(max_rows)

    assets: list[AssetOpportunity] = []
    for _, row in combined.iterrows():
        tech_raw = str(row.get("tech_stack", "") or "")
        tech_stack = [t.strip() for t in tech_raw.split(",") if t.strip()]

        has_email_raw = str(row.get("has_email_list", "false") or "false").lower()
        has_email = has_email_raw in {"true", "yes", "1"}

        assets.append(
            AssetOpportunity(
                url=str(row.get("url", "") or ""),
                title=str(row.get("title", "") or ""),
                asking_price=float(row["asking_price"]),
                monthly_revenue=float(row["monthly_revenue"]),
                monthly_traffic=int(row["monthly_traffic"]),
                tech_stack=tech_stack,
                category=str(row.get("category", "micro-saas") or "micro-saas"),
                has_email_list=has_email,
                current_monetization=str(
                    row.get("current_monetization", "") or ""
                ),
            )
        )

    return assets


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_columns(df: pd.DataFrame, path: str = "") -> None:
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        label = f" in {path}" if path else ""
        raise ValueError(
            f"Missing required columns{label}: {sorted(missing)}. "
            f"Found: {list(df.columns)}"
        )
