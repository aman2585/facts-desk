"""Ingestion pipeline (Phase 2): fetch → parse → chunk → embed → publish."""

from .pipeline import run_ingestion

__all__ = ["run_ingestion"]
