"""CLI: python -m src.ingest.cli run | schedule | smoke."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow `python -m src.ingest.cli` from repo root
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def cmd_run(args: argparse.Namespace) -> int:
    from src.ingest.pipeline import run_ingestion

    result = run_ingestion(force=args.force, skip_embed=args.skip_embed)
    print(json.dumps({
        "corpus_version": result.corpus_version,
        "published": result.published,
        "embedding_model": result.embedding_model,
        "chroma_collection": result.chroma_collection,
        "chunk_total": result.chunk_total,
        "message": result.message,
        "sources": [
            {
                "source_id": s.source_id,
                "status": s.status,
                "chunk_count": s.chunk_count,
                "content_hash": s.content_hash,
                "error": s.error,
                "numeric_diffs": s.numeric_diffs,
            }
            for s in result.sources
        ],
    }, indent=2))
    return 0 if result.published else 1


def cmd_schedule(args: argparse.Namespace) -> int:
    from src.ingest.scheduler import start_scheduler

    start_scheduler()
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    from src.ingest.indexes import smoke_bm25_query, smoke_chroma_query
    from src.ingest.paths import PUBLISHED_POINTER, STAGING_DIR

    if not PUBLISHED_POINTER.exists():
        print("No published corpus. Run: python -m src.ingest.cli run")
        return 1
    pointer = json.loads(PUBLISHED_POINTER.read_text(encoding="utf-8"))
    version = pointer["corpus_version"]
    version_dir = Path(pointer.get("version_dir") or (STAGING_DIR / version))
    collection = pointer.get("chroma_collection")

    print("Published:", json.dumps(pointer, indent=2))

    bm25_hits = smoke_bm25_query(version_dir, "expense ratio mid cap", top_k=3)
    print("\nBM25 smoke (expense ratio mid cap):")
    print(json.dumps(bm25_hits, indent=2))

    if collection and not args.skip_embed:
        chroma_hits = smoke_chroma_query(
            collection,
            scheme_code="hdfc_mid_cap_direct_growth",
            query="What is the expense ratio?",
        )
        print("\nChroma smoke (scheme_code=hdfc_mid_cap_direct_growth):")
        print(json.dumps(chroma_hits, indent=2))
    else:
        print("\nChroma smoke skipped (no collection or --skip-embed).")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facts-desk-ingest",
        description="Facts Desk Phase 2 ingestion (HTML-only, 5 Groww URLs)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run ingestion once (manual trigger)")
    run_p.add_argument("--force", action="store_true", help="Re-parse even if content_hash unchanged")
    run_p.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip BGE/Chroma (chunk+BM25 only) — for offline debugging",
    )
    run_p.set_defaults(func=cmd_run)

    sched_p = sub.add_parser("schedule", help="Block and run daily at 09:15 Asia/Kolkata")
    sched_p.set_defaults(func=cmd_schedule)

    smoke_p = sub.add_parser("smoke", help="Smoke-test BM25 + Chroma against published index")
    smoke_p.add_argument("--skip-embed", action="store_true")
    smoke_p.set_defaults(func=cmd_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
