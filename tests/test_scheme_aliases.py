"""Assert all five corpus schemes resolve from common user phrasings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.retrieve.normaliser import _load_alias_maps, normalise_query
from src.safety.intent import classify_intent

# Common phrasings that must resolve to the corpus scheme_code.
# Includes the Phase 4 false-positive set: Nifty 50 / BAF short forms.
SCHEME_PHRASINGS: dict[str, tuple[str, ...]] = {
    "hdfc_mid_cap_direct_growth": (
        "HDFC Mid Cap Fund Direct Growth",
        "HDFC Mid Cap",
        "hdfc midcap",
        "mid cap fund",
    ),
    "hdfc_equity_direct_growth": (
        "HDFC Equity Fund Direct Growth",
        "HDFC Equity Fund",
        "HDFC Flexi Cap",
        "hdfc flexicap",
    ),
    "hdfc_small_cap_direct_growth": (
        "HDFC Small Cap Fund Direct Growth",
        "HDFC Small Cap",
        "hdfc smallcap",
        "small cap fund",
    ),
    "hdfc_nifty_50_index_direct_growth": (
        "HDFC Nifty 50 Index Fund Direct Growth",
        "HDFC Nifty 50 Index Fund Direct",
        "Nifty 50",
        "NIFTY 50 Index Fund",
        "nifty 50 index",
        "hdfc nifty 50",
    ),
    "hdfc_balanced_advantage_direct_growth": (
        "HDFC Balanced Advantage Fund Direct Growth",
        "Balanced Advantage",
        "balanced advantage fund",
        "BAF",
        "hdfc baf",
    ),
}

# Golden IDs that previously short-circuited as uncovered_scheme.
GOLDEN_IN_CORPUS_QUERIES: tuple[tuple[str, str], ...] = (
    ("g004", "What is the expense ratio of HDFC Nifty 50 Index Fund Direct?"),
    ("g005", "HDFC Balanced Advantage Fund Direct Growth expense ratio?"),
    ("g009", "Does HDFC Nifty 50 Index Fund Direct Growth have an exit load?"),
    ("g014", "Minimum investment or SIP for HDFC Nifty 50 Index Fund Direct Growth?"),
    ("g019", "Riskometer classification for HDFC Nifty 50 Index Fund Direct Growth?"),
    ("g024", "What index does HDFC Nifty 50 Index Fund track?"),
    ("g031", "Does HDFC Nifty 50 Index Fund Direct Growth have a lock-in period?"),
)

FOREIGN_MUST_STAY_UNCOVERED: tuple[str, ...] = (
    "Axis Midcap exit load",
    "Kotak Flexicap TER",
    "SBI Bluechip exit load",
    "ICICI Prudential Midcap expense ratio",
)


class TestSchemeAliasResolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _load_alias_maps.cache_clear()

    def test_all_five_schemes_resolve_from_common_phrasings(self) -> None:
        for scheme_code, phrases in SCHEME_PHRASINGS.items():
            for phrase in phrases:
                with self.subTest(scheme=scheme_code, phrase=phrase):
                    nq = normalise_query(phrase)
                    self.assertEqual(
                        nq.resolution,
                        "resolved",
                        f"{phrase!r} → resolution={nq.resolution!r} "
                        f"matched={nq.matched_alias!r}",
                    )
                    self.assertEqual(
                        nq.scheme_code,
                        scheme_code,
                        f"{phrase!r} → scheme_code={nq.scheme_code!r}, "
                        f"want {scheme_code}",
                    )

    def test_golden_nifty_baf_queries_not_uncovered(self) -> None:
        expected = {
            "g004": "hdfc_nifty_50_index_direct_growth",
            "g005": "hdfc_balanced_advantage_direct_growth",
            "g009": "hdfc_nifty_50_index_direct_growth",
            "g014": "hdfc_nifty_50_index_direct_growth",
            "g019": "hdfc_nifty_50_index_direct_growth",
            "g024": "hdfc_nifty_50_index_direct_growth",
            "g031": "hdfc_nifty_50_index_direct_growth",
        }
        for gid, query in GOLDEN_IN_CORPUS_QUERIES:
            with self.subTest(id=gid):
                nq = normalise_query(query)
                ir = classify_intent(query)
                self.assertEqual(nq.resolution, "resolved", query)
                self.assertEqual(nq.scheme_code, expected[gid], query)
                self.assertNotEqual(ir.intent, "uncovered_scheme", query)
                self.assertEqual(ir.scheme_code, expected[gid], query)

    def test_foreign_amcs_still_uncovered(self) -> None:
        for query in FOREIGN_MUST_STAY_UNCOVERED:
            with self.subTest(query=query):
                nq = normalise_query(query)
                ir = classify_intent(query)
                self.assertEqual(nq.resolution, "uncovered", query)
                self.assertIsNone(nq.scheme_code, query)
                self.assertEqual(ir.intent, "uncovered_scheme", query)


if __name__ == "__main__":
    unittest.main()
