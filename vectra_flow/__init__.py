"""
vectra_flow - AI-powered pipeline to ingest, analyze, and report on niche software opportunities.
"""

__version__ = "0.1.0"
__author__ = "MattiaMDV"

from vectra_flow.config import Config
from vectra_flow.ingest import ingest
from vectra_flow.analyze import analyze
from vectra_flow.report import generate_report

__all__ = ["Config", "ingest", "analyze", "generate_report"]
