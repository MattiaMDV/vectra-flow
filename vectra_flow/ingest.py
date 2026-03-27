"""
Data ingestion module for vectra_flow.

Reads a CSV file and returns a list of opportunity records.
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

from vectra_flow.config import Config

logger = logging.getLogger(__name__)


def ingest(path: Path | None = None) -> List[Dict[str, Any]]:
    """Load opportunity data from a CSV file.

    Args:
        path: Path to the CSV file. Defaults to Config.DEFAULT_INPUT.

    Returns:
        A list of dicts, one per row in the CSV.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If the CSV file is empty or malformed.
    """
    cfg = Config()
    source = Path(path) if path else cfg.DEFAULT_INPUT

    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    records: List[Dict[str, Any]] = []
    with source.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file is empty or has no header: {source}")
        for row in reader:
            records.append(dict(row))

    if not records:
        raise ValueError(f"No data rows found in: {source}")

    logger.info("Ingested %d records from %s", len(records), source)
    return records
