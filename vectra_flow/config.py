from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    repo_root: Path = Path(".")
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    max_rows: int = 20000
    n_topics: int = 8

    required_columns = ("date", "text", "rating", "product")

SETTINGS = Settings()


@dataclass(frozen=True)
class AssetSettings:
    """Configuration for the Digital Real Estate & Flip mode."""

    data_dir: Path = Path("data/assets")
    reports_dir: Path = Path("reports")
    max_rows: int = 5_000

    # Minimum acquisition score (0–100) to include an asset in reports.
    min_score: float = 0.0

    required_columns = ("url", "title", "asking_price", "monthly_revenue", "monthly_traffic")

ASSET_SETTINGS = AssetSettings()


@dataclass(frozen=True)
class ScoutSettings:
    """Configuration for the Asset Scout mode."""

    reports_dir: Path = Path("reports/notifications")

    # Minimum scout relevance score (0.0–1.0) to surface an asset.
    min_score: float = 0.3

    # Network timeout per forum request (seconds).
    timeout: int = 30

    # Maximum paragraphs extracted per forum page.
    max_paragraphs_per_url: int = 300

SCOUT_SETTINGS = ScoutSettings()
