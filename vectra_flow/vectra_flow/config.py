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
