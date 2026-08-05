# fast_api.py

"""
FastAPI layer exposing the full pipeline (classification -> routing ->
retrieval -> generation) as a single endpoint, plus a couple of
narrower endpoints for debugging individual stages without paying
for a full LLM generation call each time.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from retrieval.router import route_query
from generation.generator import generate_answer
from retrieval.recommendation_retrieval import recommend
import time, json
from session_store import update_session, get_session
from database.exchange_rates import convert_to_usd
app = FastAPI(title="Visa Assistant API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# import sqlite3

# from session_store import update_session, get_session, append_turn

# DATABASE_NAME = "visa_assistant.db"
from retrieval.shared_resource import get_connection
from session_store import update_session, get_session, append_turn
# -----------------------------
# Request/response models
# -----------------------------

class QueryRequest(BaseModel):
    session_id: str
    query: str

    # Optional context from the recommendation page
    context_country: str | None = None
    context_visa_type: str | None = None


class AskResponse(BaseModel):
    query: str
    category: str
    answer: str
    sources: list
    missing_countries: list
    updated_recommendations: list | None = None   # NEW



class RouteOnlyResponse(BaseModel):
    query: str
    category: str
    classifier_output: dict
    missing_countries: list
    raw_results: dict | list

class RecommendationRequest(BaseModel):
    session_id: str
    countries: list[str] | None = None
    purpose: str | None = None
    education_level: str | None = None
    language_test: str | None = None
    language_score: str | None = None
    budget: float | None = None
    budget_currency: str | None = None   # e.g. "PKR" — required if budget is set

class RecommendationItem(BaseModel):
    id: int
    country: str
    visa_type: str
    title: str
    summary: str
    source_url: str


class RecommendationResponse(BaseModel):
    relaxed: bool
    message: str | None = None
    results: list[RecommendationItem]

# -----------------------------
# Main endpoint — full pipeline
# -----------------------------

@app.post("/ask", response_model=AskResponse)
def ask(request: QueryRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    session = get_session(request.session_id)

    t0 = time.monotonic()

    # try:
    #     routed = route_query(
    #         query=query,
    #         context_country=request.context_country or (session.get("selected_visa") or {}).get("country"),
    #         context_visa_type=request.context_visa_type or (session.get("selected_visa") or {}).get("visa_type"),
    #         recommendation_context=session.get("recommendation_context"),
    #         user_profile=session.get("user_profile"),
    #     )
    #     t1 = time.monotonic()
    #     result = generate_answer(query, routed, user_profile=session.get("user_profile"))
    #     t2 = time.monotonic()
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    try:
        routed = route_query(
            query=query,
            context_country=request.context_country or (session.get("selected_visa") or {}).get("country"),
            context_visa_type=request.context_visa_type or (session.get("selected_visa") or {}).get("visa_type"),
            recommendation_context=session.get("recommendation_context"),
            user_profile=session.get("user_profile"),
            history=session.get("history"),   # NEW
        )
        t1 = time.monotonic()
        result = generate_answer(query, routed, user_profile=session.get("user_profile"))
        t2 = time.monotonic()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    # NEW — record this exchange so future turns can reference it naturally
    append_turn(request.session_id, "user", query)
    append_turn(request.session_id, "assistant", result["answer"])

    print(f"Routing (classify + retrieve): {t1 - t0:.2f}s")
    print(f"Generation (LLM call):         {t2 - t1:.2f}s")
    print(f"Total:                          {t2 - t0:.2f}s")

    # NEW — if this follow-up was a refinement, persist the fresh
    # results as the session's new recommendation_context, so
    # SUBSEQUENT follow-ups ("which one is cheapest") also see the
    # updated set, not the stale original one
    if routed.get("is_refinement"):
        update_session(request.session_id, recommendation_context=routed["results"])

    # NEW — if this turn selected/updated a specific visa (e.g. context
    # passed in this request), remember it for the NEXT follow-up too
    if request.context_country or request.context_visa_type:
        update_session(
            request.session_id,
            selected_visa={
                "country": request.context_country or session.get("selected_visa", {}).get("country"),
                "visa_type": request.context_visa_type or session.get("selected_visa", {}).get("visa_type"),
            },
        )

    return AskResponse(
        query=query,
        category=result["category"],
        answer=result["answer"],
        sources=result["sources"],
        missing_countries=routed.get("missing_countries", []),
        updated_recommendations=routed.get("updated_recommendations"),
    )




# -----------------------------
# Debug endpoint — routing/retrieval only, no LLM generation call
# -----------------------------

@app.post("/route", response_model=RouteOnlyResponse)
def route_only(request: QueryRequest):
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    session = get_session(request.session_id)   # NEW

    # try:
    #     routed = route_query(
    #         query=query,
    #         context_country=request.context_country or (session.get("selected_visa") or {}).get("country"),
    #         context_visa_type=request.context_visa_type or (session.get("selected_visa") or {}).get("visa_type"),
    #         recommendation_context=session.get("recommendation_context"),   # NEW
    #         user_profile=session.get("user_profile"),                       # NEW
    #     )
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Routing error: {e}")
    try:
        routed = route_query(
            query=query,
            context_country=request.context_country or (session.get("selected_visa") or {}).get("country"),
            context_visa_type=request.context_visa_type or (session.get("selected_visa") or {}).get("visa_type"),
            recommendation_context=session.get("recommendation_context"),
            user_profile=session.get("user_profile"),
            history=session.get("history"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {e}")

    return RouteOnlyResponse(
        query=query,
        category=routed["category"],
        classifier_output=routed["classifier_output"],
        missing_countries=routed.get("missing_countries", []),
        raw_results=routed["results"],
    )

# -----------------------------
# Health check
# -----------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendationResponse)
def recommend_endpoint(request: RecommendationRequest):
    

    print(request.model_dump())

    budget_usd = None
    if request.budget is not None:
        if not request.budget_currency:
            raise HTTPException(status_code=400, detail="budget_currency is required when budget is set.")
        budget_usd = convert_to_usd(request.budget, request.budget_currency)
        if budget_usd is None:
            raise HTTPException(status_code=400, detail=f"Unsupported currency: {request.budget_currency}")

    recommendation = recommend(
        countries=request.countries,
        purpose=request.purpose,
        education_level=request.education_level,
        language_test=request.language_test,
        language_score=request.language_score,
        max_budget=budget_usd,
    )

    # NEW — persist this result set and the profile that produced it,
    # keyed by session_id, so /ask can later resolve "which one is
    # cheapest" without the frontend needing to resend the list.
    update_session(
        request.session_id,
        recommendation_context=recommendation["results"],
        user_profile={
            "countries": request.countries,
            "purpose": request.purpose,
            "education_level": request.education_level,
            "language_test": request.language_test,
            "language_score": request.language_score,
            #"budget": budget_usd,   # store the converted value — everything downstream expects USD
            "budget": request.budget, 
            "budget_currency": request.budget_currency,     # original currency, so later /ask follow-ups don't need to re-state it
        },
    )

    return RecommendationResponse(
        relaxed=recommendation["relaxed"],
        message=recommendation["message"],
        results=[
            RecommendationItem(
                id=row["id"],
                country=row["country"],
                visa_type=row["visa_type"],
                title=row["title"],
                summary=row["summary"],
                source_url=row["source_url"],
            )
            for row in recommendation["results"]
        ]
    )


# @app.get("/visa-detail/{visa_id}")
# def visa_detail(visa_id: int):
#     conn = sqlite3.connect(DATABASE_NAME)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM visa_knowledge WHERE id = ?", (visa_id,))
#     row = cursor.fetchone()
#     conn.close()

#     if not row:
#         raise HTTPException(status_code=404, detail="Visa not found.")

#     row = dict(row)

#     def parse_list(value):
#         """Turns a JSON array string into a Python list for the frontend
#         to render as real bullet points, instead of a raw '["a", "b"]' string."""
#         if not value:
#             return []
#         try:
#             parsed = json.loads(value)
#             return parsed if isinstance(parsed, list) else [str(parsed)]
#         except (json.JSONDecodeError, TypeError):
#             return [value]  # fall back to showing it as one line, not crashing

#     return {
#         "id": row["id"],
#         "title": row["title"],
#         "country": row["country"],
#         "visa_type": row["visa_type"],
#         "purpose": row["purpose"],
#         "summary": row["summary"],
#         "eligibility": parse_list(row["eligibility"]),
#         "required_documents": parse_list(row["required_documents"]),
#         "application_process": parse_list(row["application_process"]),
#         "important_notes": parse_list(row["important_notes"]),
#         "official_links": parse_list(row["official_links"]),
#         "processing_time": row["processing_time"],
#         "application_fee": row["application_fee"],
#         "total_estimated_cost": row["total_estimated_cost"],
#         "cost_currency": row["cost_currency"],
#         "validity": row["validity"],
#         "pr_pathway_available": bool(row["pr_pathway_available"]) if row["pr_pathway_available"] is not None else None,
#         "pr_pathway_years": row["pr_pathway_years"],
#         "last_verified_date": row["last_verified_date"],
#         "source_url": row["source_url"],
#         # NOTE: `content` and `embedding_text` intentionally excluded —
#         # those are LLM-facing fields, not meant for direct display.
#     }

@app.get("/visa-detail/{visa_id}")
def visa_detail(visa_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM visa_knowledge WHERE id = %s", (visa_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Visa not found.")

    def as_list(value):
        """JSONB columns already come back as real Python lists via
        RealDictCursor — this just guards against a null or an
        unexpected non-list shape, no JSON parsing needed anymore."""
        if not value:
            return []
        return value if isinstance(value, list) else [str(value)]

    return {
        "id": row["id"],
        "title": row["title"],
        "country": row["country"],
        "visa_type": row["visa_type"],
        "purpose": row["purpose"],
        "summary": row["summary"],
        "eligibility": as_list(row["eligibility"]),
        "required_documents": as_list(row["required_documents"]),
        "application_process": as_list(row["application_process"]),
        "important_notes": as_list(row["important_notes"]),
        "official_links": as_list(row["official_links"]),
        "processing_time": row["processing_time"],
        "application_fee": row["application_fee"],
        "total_estimated_cost": row["total_estimated_cost"],
        "cost_currency": row["cost_currency"],
        "validity": row["validity"],
        "pr_pathway_available": row["pr_pathway_available"],
        "pr_pathway_years": row["pr_pathway_years"],
        "last_verified_date": row["last_verified_date"],
        "source_url": row["source_url"],
    }