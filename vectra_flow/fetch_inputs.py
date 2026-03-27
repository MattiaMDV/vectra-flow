"""Download CSV input data from a remote URL (e.g. Google Sheets CSV export).

Typical usage from the command line (reads the ``SHEET_URL`` environment
variable and writes the result to ``data/sheet.csv``):

    python -m vectra_flow.fetch_inputs

Or programmatically:

    from vectra_flow.fetch_inputs import fetch_sheet, remap_columns
    fetch_sheet("https://...", Path("data/sheet.csv"))

Google Forms / Google Sheets setup
------------------------------------
Google Forms automatically names columns after the question text and adds a
leading "Timestamp" column.  Vectra Flow expects exactly four column names:
``date``, ``text``, ``rating``, ``product``.

Recommended Google Form question titles (use these exact names so that no
column mapping is needed):

    * **date**    — "date"   (or map "Timestamp" → "date" with COLUMN_MAP)
    * **text**    — "text"   (the free-text feedback field)
    * **rating**  — "rating" (numeric 1-5 rating)
    * **product** — "product"(product / service name)

If you prefer friendlier question titles, pass a JSON mapping via the
``COLUMN_MAP`` environment variable or the ``--column-map`` CLI flag:

    COLUMN_MAP='{"Timestamp":"date","Feedback":"text","Score":"rating","Product":"product"}'

Setup steps
-----------
1. Create a Google Form with the four questions above.
2. Link the form to a Google Sheets spreadsheet (Responses → Sheets icon).
3. In Google Sheets choose *File → Share → Publish to web*, select the
   response sheet and *Comma-separated values (.csv)*, then click *Publish*.
   Copy the published CSV URL.
4. Add the URL as a GitHub repository secret named ``SHEET_URL``
   (*Settings → Secrets and variables → Actions → New repository secret*).
5. Optionally add a ``COLUMN_MAP`` secret (JSON) if your question titles differ
   from the required column names.
6. The ``vectra_flow.yml`` workflow will automatically fetch the sheet on
   every scheduled or manual run.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that must never be fetched (SSRF guard).
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "0.0.0.0",
})


def _check_url(url: str) -> None:
    """Validate *url* before opening it.

    Raises ValueError for empty strings, disallowed URL schemes, and
    hostnames that point at localhost or link-local addresses (SSRF guard).
    """
    if not url:
        raise ValueError("Sheet URL must not be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Unsupported URL scheme {parsed.scheme!r}. Only HTTP(S) URLs are allowed."
        )

    hostname = parsed.hostname or ""
    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Requests to {hostname!r} are not allowed.")

    # Reject numeric IP addresses that resolve to loopback, link-local, or
    # private ranges (e.g. 127.0.0.1, 169.254.x.x, 10.x.x.x, ::1).
    try:
        import ipaddress
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback or addr.is_link_local or addr.is_private:
            raise ValueError(
                f"Requests to private/internal IP address {hostname!r} are not allowed."
            )
    except ValueError as exc:
        # Re-raise our own explicit errors; plain hostnames raise ValueError
        # inside ipaddress.ip_address() — that just means it is a domain name.
        if "not allowed" in str(exc):
            raise


def fetch_sheet(url: str, dest: Path, timeout: int = 30, column_map: dict[str, str] | None = None) -> None:
    """Download a CSV from *url* and write it to *dest*.

    If *column_map* is provided the downloaded CSV is read into a DataFrame,
    the columns are renamed, and the result is written back to *dest*.  This
    is useful when the Google Form question titles differ from the required
    column names (``date``, ``text``, ``rating``, ``product``).

    Args:
        url:        HTTP(S) URL that returns CSV data
                    (e.g. a Google Sheets "Publish to web" CSV export URL).
        dest:       Filesystem path where the downloaded CSV will be saved.
                    Parent directories are created automatically.
        timeout:    Network timeout in seconds (default: 30).
        column_map: Optional dict mapping source column names (from the
                    downloaded CSV) to target column names expected by the
                    analysis pipeline.  Example::

                        {"Timestamp": "date",
                         "Il tuo feedback": "text",
                         "Valutazione (1-5)": "rating",
                         "Prodotto": "product"}

    Raises:
        ValueError:              if *url* is empty, uses an unsupported scheme,
                                 or targets a private/internal address.
        urllib.error.URLError:   if the network request fails.
    """
    _check_url(url)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read()

    if column_map:
        df = pd.read_csv(io.BytesIO(raw))
        df = remap_columns(df, column_map)
        dest.write_text(df.to_csv(index=False), encoding="utf-8")
    else:
        dest.write_bytes(raw)


def remap_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename DataFrame columns using *mapping*.

    Only the columns present in *mapping* are renamed; all other columns are
    left untouched.  This lets you adapt any Google Forms CSV export to the
    column names expected by the analysis pipeline.

    Args:
        df:      Source DataFrame (e.g. freshly read from a Google Sheets CSV).
        mapping: Dict mapping source column names → target column names.
                 Keys that do not appear in *df* are silently ignored.

    Returns:
        A new DataFrame with the renamed columns.

    Example::

        df = remap_columns(df, {
            "Timestamp":           "date",
            "Il tuo feedback":     "text",
            "Valutazione (1-5)":   "rating",
            "Prodotto":            "product",
        })
    """
    return df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})


if __name__ == "__main__":
    url = os.environ.get("SHEET_URL", "").strip()
    if not url:
        print("SHEET_URL is not set — skipping Google Sheets fetch.", file=sys.stderr)
        raise SystemExit(0)

    dest = Path(os.environ.get("SHEET_DEST", "data/sheet.csv"))

    column_map: dict[str, str] | None = None
    column_map_json = os.environ.get("COLUMN_MAP", "").strip()
    if column_map_json:
        try:
            column_map = json.loads(column_map_json)
            if not isinstance(column_map, dict):
                raise TypeError("COLUMN_MAP must be a JSON object (dict)")
        except (json.JSONDecodeError, TypeError) as exc:
            print(f"ERROR: invalid COLUMN_MAP: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    try:
        fetch_sheet(url, dest, column_map=column_map)
        print(f"Fetched sheet data → {dest}")
        if column_map:
            print(f"Applied column mapping: {column_map}")
    except Exception as exc:
        print(f"ERROR: failed to fetch sheet data: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
