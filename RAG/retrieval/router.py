# retrieval/router.py

from RAG.retrieval.query_classifier import classify_query_llm
from RAG.retrieval.factual_retrieval import retrieve_factual
from RAG.retrieval.recommendation_retrieval import recommend, fetch_by_ids
from RAG.retrieval.comparison_retrieval import compare
from RAG.retrieval.general_retrieval import retrieve_general, retrieve_general_diverse
from RAG.database.exchange_rates import convert_to_usd
import time


def _wrap_as_source_rows(rows: list[dict]) -> list[dict]:
    """
    Adapts raw SQLite rows (from fetch_by_ids) into the standardized
    {"content", "metadata", "score"} shape that citation_utils expects
    for factual/general-style results.
    """
    return [
        {
            "content": row["content"],
            "metadata": {
                "title": row["title"],
                "country": row["country"],
                "visa_type": row["visa_type"],
                "source_url": row["source_url"],
                "last_verified_date": row.get("last_verified_date"),
            },
            "score": 1.0,
        }
        for row in rows
    ]


# def route_query(
#     query: str,
#     context_country: str | None = None,
#     context_visa_type: str | None = None,
#     recommendation_context: list | None = None,   # NEW
#     user_profile: dict | None = None,               # NEW
# ) -> dict:

#     t0 = time.monotonic()
#     classifier_output = classify_query_llm(query)
#     t1 = time.monotonic()
def route_query(
    query: str,
    context_country: str | None = None,
    context_visa_type: str | None = None,
    context_visa_id: int | None = None,   # NEW
    recommendation_context: list | None = None,
    user_profile: dict | None = None,
    history: list | None = None,
) -> dict:

    t0 = time.monotonic()
    classifier_output = classify_query_llm(query, history=history)
    t1 = time.monotonic()
    print(f"  Classification only: {t1 - t0:.2f}s")

    category = classifier_output["category"]
    countries = classifier_output["countries"]
    purpose = classifier_output["purpose"]

    is_refinement = classifier_output.get("is_refinement", False)
    if is_refinement:
        category = "recommendation"

    if category == "irrelevant":
        return {
            "category": "irrelevant",
            "classifier_output": classifier_output,
            "results": [],
            "missing_countries": [],
            "relaxed": False,
            "relaxed_message": None,
            "is_refinement": False,
            "updated_recommendations": None,
            "needs_currency_clarification": False,
        }

    if category in ("factual", "general"):
        if not countries and context_country:
            countries = [context_country]
            classifier_output["countries"] = countries
        if not classifier_output.get("visa_type") and context_visa_type:
            classifier_output["visa_type"] = context_visa_type

    visa_type = classifier_output.get("visa_type")

    missing_countries = []
    relaxed = False
    relaxed_message = None
    needs_currency_clarification = False

    if category == "factual":
        # NEW — a specific card is open: answer from exactly that
        # record, no search, no ambiguity across other recommendations
        if context_visa_id:
            results = _wrap_as_source_rows(fetch_by_ids([context_visa_id]))
        elif not countries and not context_country and recommendation_context:
            ids = [item["id"] for item in recommendation_context]
            results = _wrap_as_source_rows(fetch_by_ids(ids))
        else:
            results = retrieve_factual(query, countries=countries or None, purpose=purpose)

    elif category == "recommendation":
        merged_profile = dict(user_profile) if user_profile else {}
        for field in ["countries", "purpose", "education_level", "language_test", "language_score", "budget", "budget_currency"]:
            classifier_value = classifier_output.get(field)
            if classifier_value:
                merged_profile[field] = classifier_value

        needs_currency_clarification = False
        budget_usd = None

        stated_budget = merged_profile.get("budget")
        stated_currency = merged_profile.get("budget_currency")

        if stated_budget is not None:
            if not stated_currency:
                needs_currency_clarification = True
            else:
                budget_usd = convert_to_usd(stated_budget, stated_currency)
                if budget_usd is None:
                    needs_currency_clarification = True

        recommendation_output = recommend(
            countries=merged_profile.get("countries") or countries or None,
            purpose=merged_profile.get("purpose") or purpose,
            visa_type=visa_type,
            education_level=merged_profile.get("education_level"),
            language_test=merged_profile.get("language_test"),
            language_score=merged_profile.get("language_score"),
            max_budget=budget_usd,
        )
        results = recommendation_output["results"]
        relaxed = recommendation_output["relaxed"]
        relaxed_message = recommendation_output["message"]

    elif category == "comparison":
        if countries and len(countries) >= 2:
            comparison_output = compare(countries=countries, purpose=purpose)
            results = comparison_output["results"]
            missing_countries = comparison_output["missing_countries"]
            if missing_countries:
                print(f"WARNING: no data available for: {missing_countries}")
        elif recommendation_context:
            ids = [item["id"] for item in recommendation_context]
            rows = fetch_by_ids(ids)
            results = {}
            for row in rows:
                results.setdefault(row["country"], []).append(row)
        else:
            print("Comparison classified but insufficient context — falling back to factual retrieval.")
            results = retrieve_factual(query, countries=countries or None, purpose=purpose)
            category = "factual"

    else:  # general, or any unexpected category value
        # NEW — same specific-card-first priority as factual
        if context_visa_id:
            results = _wrap_as_source_rows(fetch_by_ids([context_visa_id]))
        elif recommendation_context and not countries:
            ids = [item["id"] for item in recommendation_context]
            results = _wrap_as_source_rows(fetch_by_ids(ids))
        elif not countries:
            results = retrieve_general_diverse(query)
        else:
            results = retrieve_general(query, countries=countries, visa_type=visa_type)

        MIN_RELEVANCE_SCORE = 0.3
        if category in ("factual", "general") and isinstance(results, list):
            results = [r for r in results if r.get("score", 1.0) >= MIN_RELEVANCE_SCORE]

    return {
        "category": category,
        "classifier_output": classifier_output,
        "results": results,
        "missing_countries": missing_countries,
        "relaxed": relaxed,
        "relaxed_message": relaxed_message,
        "is_refinement": is_refinement,
        "updated_recommendations": results if is_refinement else None,
        "needs_currency_clarification": needs_currency_clarification,
    }
if __name__ == "__main__":
    test_queries = [
        "I want to work in tech in the US",
        "how do I bring my spouse to Germany",
        "which countries can I apply to with a Bachelor's degree and IELTS 7",
        "compare Germany and Canada for studying",
        "what is the Opportunity Card",
        "what documents do I need for a German student visa",
    ]

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")

        routed = route_query(query)

        print(f"Routed to: {routed['category']}")
        print(f"Classifier output: {routed['classifier_output']}")

        if routed["missing_countries"]:
            print(f"Missing data for: {routed['missing_countries']}")

        results = routed["results"]

        if routed["category"] == "comparison":
            for country, rows in results.items():
                print(f"\n  {country}:")
                for r in rows:
                    print(f"    - {r['title']}")
        elif routed["category"] == "recommendation":
            for r in results:
                print(f"    - {r['country']} | {r['title']}")
        else:
            for r in results:
                print(f"    - [{r['score']:.4f}] {r['metadata']['title']}")