"""CLI: Facts Desk ask path (Phase 4)."""

from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Facts Desk ask — redact → classify → retrieve/generate or refuse"
    )
    parser.add_argument("query", nargs="?", help="User question")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument("--tau", type=float, default=None, help="Override retrieval τ")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    if not args.query:
        parser.print_help()
        return 2

    from src.generate.pipeline import ask

    result = ask(args.query, tau=args.tau)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"intent={result.intent.intent} type={result.response.response_type}")
        if result.model_version:
            print(f"model_version={result.model_version}")
        if result.corpus_version:
            print(f"corpus_version={result.corpus_version}")
        print()
        print(result.response.display)
    return 0


if __name__ == "__main__":
    sys.exit(main())
