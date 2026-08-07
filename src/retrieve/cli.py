"""CLI for Phase 3 retrieval smoke checks."""

from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Facts Desk hybrid retrieval (Phase 3)")
    parser.add_argument("query", nargs="?", help="Factual query to retrieve against published index")
    parser.add_argument("--tau", type=float, default=None, help="Override confidence gate τ")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.query:
        parser.print_help()
        return 2

    from .pipeline import retrieve

    result = retrieve(args.query, tau=args.tau)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"status={result.status} corpus={result.corpus_version} collection={result.chroma_collection}")
        print(f"scheme_resolution={result.query.resolution} scheme_code={result.query.scheme_code}")
        print(f"top_score={result.gate.top_score} tau={result.gate.tau} — {result.gate.reason}")
        for i, c in enumerate(result.chunks, 1):
            score = f"{c.rerank_score:.4f}" if c.rerank_score is not None else "n/a"
            print(f"  {i}. {c.chunk_id} source={c.source_id} rerank={score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
