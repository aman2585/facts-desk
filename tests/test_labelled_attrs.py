"""Category labelled-pair completion (g026–g028 under-specify fix)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate.labelled_attrs import (
    complete_labelled_attributes,
    extract_category_pairs,
    format_category_answer,
    is_category_query,
)


MID_CAP_CHUNK = {
    "chunk_id": "src_001::c_001",
    "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "tables": [
        {"label": "Category", "value": "Equity"},
        {"label": "Sub-category", "value": "Mid Cap"},
    ],
    "text": "Category: Equity | Sub-category: Mid Cap",
}

EQUITY_CHUNK = {
    "chunk_id": "src_002::c_001",
    "source_url": "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "tables": [
        {"label": "Category", "value": "Equity"},
        {"label": "Sub-category", "value": "Flexi Cap"},
    ],
    "text": "Category: Equity | Sub-category: Flexi Cap",
}

SMALL_CAP_CHUNK = {
    "chunk_id": "src_003::c_001",
    "source_url": "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "tables": [
        {"label": "Category", "value": "Equity"},
        {"label": "Sub-category", "value": "Small Cap"},
    ],
    "text": "Category: Equity | Sub-category: Small Cap",
}


class TestLabelledCategoryAttrs(unittest.TestCase):
    def test_detects_category_queries(self) -> None:
        self.assertTrue(is_category_query("Is HDFC Mid Cap Fund a mid-cap scheme?"))
        self.assertTrue(
            is_category_query("Is HDFC Small Cap Fund Direct Growth a small-cap fund?")
        )
        self.assertTrue(is_category_query("What category is HDFC Equity Fund Direct Growth?"))
        self.assertFalse(is_category_query("What is the expense ratio of HDFC Mid Cap?"))

    def test_extract_and_format(self) -> None:
        pairs = extract_category_pairs(MID_CAP_CHUNK)
        self.assertEqual(
            pairs,
            [("Category", "Equity"), ("Sub-category", "Mid Cap")],
        )
        self.assertEqual(
            format_category_answer(pairs),
            "Category: Equity; Sub-category: Mid Cap",
        )

    def test_completes_underspecified_answers(self) -> None:
        cases = [
            (
                "Is HDFC Mid Cap Fund a mid-cap scheme?",
                "The HDFC Mid Cap Fund is a Mid Cap scheme.\n\n"
                "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
                MID_CAP_CHUNK,
                "Category: Equity; Sub-category: Mid Cap",
            ),
            (
                "Is HDFC Small Cap Fund Direct Growth a small-cap fund?",
                "The fund's sub-category is Small Cap.\n\n"
                "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
                SMALL_CAP_CHUNK,
                "Category: Equity; Sub-category: Small Cap",
            ),
            (
                "What category is HDFC Equity Fund Direct Growth?",
                "The category of HDFC Equity Fund Direct Growth is Equity.\n\n"
                "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
                EQUITY_CHUNK,
                "Category: Equity; Sub-category: Flexi Cap",
            ),
        ]
        for query, raw, chunk, want_body in cases:
            with self.subTest(query=query):
                out = complete_labelled_attributes(query, raw, [chunk])
                self.assertIn(want_body, out)
                self.assertIn(chunk["source_url"], out)

    def test_leaves_non_category_unchanged(self) -> None:
        raw = (
            "Expense ratio: 0.75%\n\n"
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )
        out = complete_labelled_attributes(
            "What is the expense ratio of HDFC Mid Cap Fund?",
            raw,
            [MID_CAP_CHUNK],
        )
        self.assertEqual(out, raw)


if __name__ == "__main__":
    unittest.main()
