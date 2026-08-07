"""Extractive generation prompts — provider-agnostic."""

from __future__ import annotations

from typing import Any, Sequence

SYSTEM_PROMPT = """You are Facts Desk, a facts-only mutual fund assistant.
Answer ONLY using the provided source chunks. Do not use outside knowledge.

Extractive contract (mandatory):
- State only the fact the user asked for. Prefer exactly ONE sentence.
- Use wording from the cited chunk (labels/values as written). Do not paraphrase into a definition.
- When the chunk holds labelled pairs for the attribute asked (e.g. Category and
  Sub-category), include EVERY such labelled pair in the answer — never only one.
  Example form: Category: Equity; Sub-category: Mid Cap
- No definitions, no glossary, no "what X means", no background, no elaboration beyond the chunk.
- Do not copy unrelated fields or explanatory prose from other sections of the chunk.
- At most 3 sentences total if one is impossible; never pad with explanation.
- Declarative. No hedging (typically, generally, might, probably).
- No advice, recommendations, comparisons, or predictions.
- Every number must appear verbatim in a provided chunk (no arithmetic, rounding, or conversion).
- Cite exactly ONE allow-listed source URL — copy it exactly from a chunk's source_url field.
- Put the citation URL alone on the last line of your reply.
- If the chunks do not contain the answer, reply with exactly:
I could not find that in my sources.
followed by one allow-listed source_url from the chunks on the next line.
"""


def _format_chunk(i: int, chunk: dict[str, Any]) -> str:
    tables = chunk.get("tables") or []
    table_lines = []
    for row in tables:
        label = row.get("label", "")
        value = row.get("value", "")
        table_lines.append(f"  - {label}: {value}")
    tables_block = "\n".join(table_lines) if table_lines else "  (none)"
    heading = chunk.get("heading_path_str") or " > ".join(chunk.get("heading_path") or [])
    return (
        f"[chunk {i}] chunk_id={chunk.get('chunk_id')}\n"
        f"source_url={chunk.get('source_url')}\n"
        f"fetched_at={chunk.get('fetched_at')}\n"
        f"heading={heading}\n"
        f"text:\n{chunk.get('text') or ''}\n"
        f"tables:\n{tables_block}"
    )


def build_user_prompt(
    query: str,
    chunks: Sequence[dict[str, Any]],
    *,
    scheme_code: str | None = None,
    prior_failures: Sequence[str] | None = None,
) -> str:
    parts = [
        f"query: {query}",
        f"scheme: {scheme_code or 'null'}",
        "chunks:",
    ]
    for i, ch in enumerate(chunks, 1):
        parts.append(_format_chunk(i, ch))
    if prior_failures:
        parts.append(
            "Your previous reply failed validation for these reasons: "
            + "; ".join(prior_failures)
            + ". Fix them. Still obey all rules."
        )
    parts.append(
        "Reply with one extractive factual sentence (chunk wording only; "
        "no definitions), then exactly one source_url on its own line."
    )
    return "\n\n".join(parts)


def build_messages(
    query: str,
    chunks: Sequence[dict[str, Any]],
    *,
    scheme_code: str | None = None,
    prior_failures: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_user_prompt(
                query,
                chunks,
                scheme_code=scheme_code,
                prior_failures=prior_failures,
            ),
        },
    ]
