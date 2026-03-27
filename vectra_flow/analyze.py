"""
Analysis module for vectra_flow.

Scores and filters opportunity records loaded from ingestion.
"""

import logging
from typing import List, Dict, Any

from vectra_flow.config import Config

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"name", "market_size", "competition", "feasibility"}


def _validate(record: Dict[str, Any]) -> None:
    """Raise ValueError if required scoring fields are missing."""
    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValueError(f"Record is missing required fields: {missing}")


def _score(record: Dict[str, Any]) -> float:
    """Compute a composite opportunity score in [0, 1].

    Score = (market_size * feasibility) / (1 + competition)
    where each field is expected to be a float in [0, 1].
    """
    try:
        market_size = float(record.get("market_size", 0))
        competition = float(record.get("competition", 1))
        feasibility = float(record.get("feasibility", 0))
    except (TypeError, ValueError):
        logger.warning("Invalid numeric fields in record: %s", record)
        return 0.0

    raw = (market_size * feasibility) / (1 + competition)
    return round(min(max(raw, 0.0), 1.0), 4)


def analyze(
    records: List[Dict[str, Any]],
    min_score: float | None = None,
    top_n: int | None = None,
) -> List[Dict[str, Any]]:
    """Score, filter, and rank opportunity records.

    Args:
        records: Raw records from :func:`vectra_flow.ingest.ingest`.
        min_score: Minimum score threshold (0–1). Defaults to Config.MIN_SCORE.
        top_n: Maximum number of results to return. Defaults to Config.TOP_N.

    Returns:
        Ranked list of records with an added ``score`` field.
    """
    cfg = Config()
    threshold = min_score if min_score is not None else cfg.MIN_SCORE
    limit = top_n if top_n is not None else cfg.TOP_N

    scored = []
    for rec in records:
        rec = dict(rec)
        try:
            _validate(rec)
        except ValueError as exc:
            logger.warning("Skipping invalid record: %s", exc)
            continue
        rec["score"] = _score(rec)
        if rec["score"] >= threshold:
            scored.append(rec)

    scored.sort(key=lambda r: r["score"], reverse=True)
    result = scored[:limit]

    logger.info(
        "Analyzed %d records → %d passed threshold (%.2f), top %d returned",
        len(records),
        len(scored),
        threshold,
        len(result),
    )
    return result
