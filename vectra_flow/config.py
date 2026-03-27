"""
Configuration module for vectra_flow.

Loads settings from environment variables and provides defaults.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Central configuration for the vectra_flow pipeline."""

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    REPORTS_DIR: Path = BASE_DIR / "reports"

    # Input / output defaults
    DEFAULT_INPUT: Path = DATA_DIR / "sample.csv"
    DEFAULT_OUTPUT: str = "report.html"

    # Analysis thresholds
    MIN_SCORE: float = float(os.getenv("VECTRA_MIN_SCORE", "0.3"))
    TOP_N: int = int(os.getenv("VECTRA_TOP_N", "10"))

    # Logging
    LOG_LEVEL: str = os.getenv("VECTRA_LOG_LEVEL", "INFO")

    def __repr__(self) -> str:
        return (
            f"Config("
            f"DATA_DIR={self.DATA_DIR}, "
            f"REPORTS_DIR={self.REPORTS_DIR}, "
            f"MIN_SCORE={self.MIN_SCORE}, "
            f"TOP_N={self.TOP_N})"
        )
