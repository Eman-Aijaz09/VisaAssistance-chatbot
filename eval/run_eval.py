"""
eval/run_eval.py

Runs the golden query set (golden_queries.py) through the REAL
route_query() entry point — the same function fast_api.py calls —
and reports:

  1. Classification accuracy: did query_classifier.py pick the
     expected category? (free signal toward issue #3, tracked
     separately from retrieval quality so the two aren't conflated)

  2. Retrieval quality, split by how each category is scored:
       - factual / general : recall@k + rank of first expected hit
                              (MRR-ready — useful baseline before
                              reranking / hybrid search land)
       - recommendation    : presence check against structured filter
                              results (not rank-based — this path is
                              a SQL filter, not a similarity search)
       - comparison         : presence check per-country + whether
                              missing_countries was flagged correctly

This intentionally does NOT call the LLM generation step — it tests
retrieval only, which is what #2 is scoped to. Wire in generator.py
separately later if you want an end-to-end eval too.

USAGE:
    python -m eval.run_eval                  # run everything
    python -m eval.run_eval --category factual
    python -m eval.run_eval --id factual_03
    python -m eval.run_eval --verbose         # show every query's detail, not just failures
"""

import argparse
import sys

from eval.golden_queries import GOLDEN_QUERIES
from retrieval.router import route_query


# ----------------------------------------------------------------
# Helpers to pull a flat list of source_urls out of each category's
# native result shape, so scoring logic doesn't need to special-case
# the shape everywhere.
# ----------------------------------------------------------------

def _extract_urls_factual_general(results) -> list[str]:
    # results: list of {"content", "metadata": {"source_url": ...}, "score"}
    return [r["metadata"].get("source_url") for r in results if isinstance(r, dict) and "metadata" in r]


def _extract_urls_recommendation(results) -> list[str]:
    # results: list of raw dict rows with a source_url column
    return [r.get("source_url") for r in results if isinstance(r, dict)]


def _extract_urls_comparison(results) -> dict[str, list[str]]:
    # results: dict[country] -> list of raw dict rows
    return {
        country: [r.get("source_url") for r in rows]
        for country, rows in results.items()
    }


# ----------------------------------------------------------------
# Per-category scorers. Each returns (passed: bool, detail: dict)
# ----------------------------------------------------------------

def score_factual_general(golden: dict, routed: dict) -> tuple[bool, dict]:
    results = routed["results"]
    if not isinstance(results, list):
        return False, {"error": f"expected list results, got {type(results)}"}

    urls = _extract_urls_factual_general(results)
    expected = golden["expected_sources"]

    hits = [u for u in expected if u in urls]
    recall = len(hits) / len(expected) if expected else 1.0

    # rank (1-indexed) of the first expected source, if any
    first_rank = None
    for expected_url in expected:
        if expected_url in urls:
            r = urls.index(expected_url) + 1
            if first_rank is None or r < first_rank:
                first_rank = r

    passed = recall == 1.0
    return passed, {
        "recall": recall,
        "hits": len(hits),
        "expected_count": len(expected),
        "first_hit_rank": first_rank,
        "returned_count": len(urls),
    }


def score_recommendation(golden: dict, routed: dict) -> tuple[bool, dict]:
    # Special case: currency-clarification queries pass if the flag fired,
    # not by source match (there ARE no sources — that's the point).
    if not golden["expected_sources"] and routed.get("needs_currency_clarification"):
        return True, {"needs_currency_clarification": True, "note": "clarification correctly triggered"}

    results = routed["results"]
    if not isinstance(results, list):
        return False, {"error": f"expected list results, got {type(results)}"}

    urls = _extract_urls_recommendation(results)
    expected = golden["expected_sources"]

    hits = [u for u in expected if u in urls]
    missing = [u for u in expected if u not in urls]
    unexpected_extra = [u for u in urls if u and u not in expected]

    passed = len(missing) == 0
    return passed, {
        "hits": len(hits),
        "expected_count": len(expected),
        "missing": missing,
        "returned_count": len(urls),
        "unexpected_extra_count": len(unexpected_extra),
    }


def score_comparison(golden: dict, routed: dict) -> tuple[bool, dict]:
    results = routed["results"]
    if not isinstance(results, dict):
        return False, {"error": f"expected dict results, got {type(results)}"}

    actual_urls_by_country = _extract_urls_comparison(results)
    expected_by_country = golden.get("expected_sources", {})

    per_country_missing = {}
    for country, expected_urls in expected_by_country.items():
        actual = actual_urls_by_country.get(country, [])
        missing = [u for u in expected_urls if u not in actual]
        if missing:
            per_country_missing[country] = missing

    expected_missing_countries = set(golden.get("expected_missing_countries", []))
    actual_missing_countries = set(routed.get("missing_countries", []))
    missing_countries_correct = expected_missing_countries == actual_missing_countries

    passed = (not per_country_missing) and missing_countries_correct
    return passed, {
        "per_country_missing": per_country_missing,
        "expected_missing_countries": sorted(expected_missing_countries),
        "actual_missing_countries": sorted(actual_missing_countries),
        "missing_countries_correct": missing_countries_correct,
    }


SCORERS = {
    "factual": score_factual_general,
    "general": score_factual_general,
    "recommendation": score_recommendation,
    "comparison": score_comparison,
}


# ----------------------------------------------------------------
# Runner
# ----------------------------------------------------------------

def run(queries: list[dict], verbose: bool = False) -> dict:
    results_by_category = {}
    classification_correct = 0
    retrieval_passed = 0
    all_details = []

    for golden in queries:
        query_text = golden["query"]
        expected_category = golden["expected_category"]
        kwargs = {"query": query_text}

        # For recommendation queries, pass through the profile as if it
        # were already-established session context — mirrors how a real
        # multi-turn session would have it by the time retrieval runs.
        # (Classification of the RAW query text is still exercised and
        # reported separately below.)
        if expected_category == "recommendation" and "profile" in golden:
            kwargs["user_profile"] = golden["profile"]
        try:
            routed = route_query(**kwargs)
        except Exception as e:
            all_details.append({
                "id": golden["id"], "query": query_text,
                "error": f"route_query raised: {e}",
                "classification_correct": False, "retrieval_passed": False,
            })
            continue

        actual_category = routed["category"]
        cat_correct = (actual_category == expected_category)
        classification_correct += int(cat_correct)

        scorer = SCORERS.get(expected_category)
        if scorer is None:
            passed, detail = False, {"error": f"no scorer for category {expected_category}"}
        else:
            passed, detail = scorer(golden, routed)

        retrieval_passed += int(passed)

        bucket = results_by_category.setdefault(expected_category, {"total": 0, "cat_correct": 0, "retrieval_passed": 0})
        bucket["total"] += 1
        bucket["cat_correct"] += int(cat_correct)
        bucket["retrieval_passed"] += int(passed)

        row = {
            "id": golden["id"],
            "query": query_text,
            "expected_category": expected_category,
            "actual_category": actual_category,
            "classification_correct": cat_correct,
            "retrieval_passed": passed,
            "detail": detail,
        }
        all_details.append(row)

        if verbose or not passed or not cat_correct:
            status = "PASS" if passed else "FAIL"
            cat_flag = "" if cat_correct else f"  [MISCLASSIFIED as {actual_category}]"
            print(f"[{status}] {golden['id']:20} {status}{cat_flag}")
            print(f"         query: {query_text}")
            print(f"         detail: {detail}")
            print()

    total = len(queries)
    print("=" * 70)
    print(f"TOTAL: {total} queries")
    print(f"Classification accuracy: {classification_correct}/{total} ({100*classification_correct/total:.1f}%)")
    print(f"Retrieval pass rate:     {retrieval_passed}/{total} ({100*retrieval_passed/total:.1f}%)")
    print()
    print("By category:")
    for cat, b in results_by_category.items():
        print(f"  {cat:15} classification {b['cat_correct']}/{b['total']}   retrieval {b['retrieval_passed']}/{b['total']}")
    print("=" * 70)

    return {
        "total": total,
        "classification_correct": classification_correct,
        "retrieval_passed": retrieval_passed,
        "by_category": results_by_category,
        "details": all_details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=["factual", "general", "recommendation", "comparison"])
    parser.add_argument("--id", dest="query_id")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    queries = GOLDEN_QUERIES
    if args.query_id:
        queries = [q for q in queries if q["id"] == args.query_id]
        if not queries:
            print(f"No query with id '{args.query_id}'")
            sys.exit(1)
    elif args.category:
        queries = [q for q in queries if q["expected_category"] == args.category]

    run(queries, verbose=args.verbose)