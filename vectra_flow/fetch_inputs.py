"""Download CSV input data from a remote URL (e.g. Google Sheets CSV export).

Typical usage from the command line (reads the ``SHEET_URL`` environment
variable and writes the result to ``data/sheet.csv``):

    python -m vectra_flow.fetch_inputs

Or programmatically:

    from vectra_flow.fetch_inputs import fetch_sheet
    fetch_sheet("https://...", Path("data/sheet.csv"))

Google Forms / Google Sheets setup
------------------------------------
1. Create a Google Form with the fields: date, text, rating, product.
2. Link the form to a Google Sheets spreadsheet (Form → Responses → Sheets icon).
3. In Google Sheets choose *File → Share → Publish to web*,
   select the response sheet and *Comma-separated values (.csv)*, then click
   *Publish*.  Copy the published CSV URL.
4. Add the URL as a GitHub repository secret named ``SHEET_URL``
   (*Settings → Secrets and variables → Actions → New repository secret*).
5. The ``vectra_flow.yml`` workflow will automatically fetch the sheet on
   every scheduled or manual run.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

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


def fetch_sheet(url: str, dest: Path, timeout: int = 30) -> None:
    """Download a CSV from *url* and write it to *dest*.

    Args:
        url:     HTTP(S) URL that returns CSV data
                 (e.g. a Google Sheets "Publish to web" CSV export URL).
        dest:    Filesystem path where the downloaded CSV will be saved.
                 Parent directories are created automatically.
        timeout: Network timeout in seconds (default: 30).

    Raises:
        ValueError:              if *url* is empty, uses an unsupported scheme,
                                 or targets a private/internal address.
        urllib.error.URLError:   if the network request fails.
    """
    _check_url(url)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        dest.write_bytes(resp.read())


if __name__ == "__main__":
    url = os.environ.get("SHEET_URL", "").strip()
    if not url:
        print("SHEET_URL is not set — skipping Google Sheets fetch.", file=sys.stderr)
        raise SystemExit(0)

    dest = Path(os.environ.get("SHEET_DEST", "data/sheet.csv"))
    try:
        fetch_sheet(url, dest)
        print(f"Fetched sheet data → {dest}")
    except Exception as exc:
        print(f"ERROR: failed to fetch sheet data: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
