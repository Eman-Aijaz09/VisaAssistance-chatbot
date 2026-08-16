# ImmigrationAssistant

**A Retrieval-Augmented Generation (RAG) system for grounded, cited answers to visa and immigration questions.**

ImmigrationAssistant answers natural-language visa and immigration questions by retrieving information from a structured knowledge base built exclusively from **official government and embassy sources** — never third-party blogs or forums — and generating cited, natural-language answers via an LLM. Every claim in a generated answer is traceable back to a real source URL.

Built over a 6-week internship by **Ayesha Bhatti** and **Eman Aijaz**.

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Architecture](#architecture)
- [How It Works — End to End](#how-it-works--end-to-end)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Current Status](#current-status)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Overview

A single visa question can be one of several fundamentally different problems:

- A narrow factual lookup — *"What is the processing time for the France Airport Transit Visa?"*
- A broad conceptual question — *"How does Germany's Opportunity Card work?"*
- A personalized eligibility filter — *"I have a Bachelor's degree and IELTS 7, which countries can I apply to?"*
- A side-by-side comparison — *"Compare Germany and Canada for studying."*

Rather than forcing every query through one generic retrieval mechanism, ImmigrationAssistant classifies each query and dispatches it to a purpose-built retrieval strategy suited to that specific problem type — then generates an answer that never states a fact without citing where it came from.

Covers **six countries**: Germany, USA, Australia, Japan, France, and Finland.

The project spans the full lifecycle of a production RAG application:

```
Official Websites → Browser-Automated Catalog Discovery → Per-Visa Extraction
    → Cleaning & Validation → Merge → Structured Database (Postgres + pgvector)
    → Query Classification → Retrieval → Generation → API → Frontend
```

---

## Repository Structure

```
ImmigrationAssistant/
├── BACKEND/
│   ├── data_collection/       # Browser-automated visa catalog discovery & extraction
│   │   ├── browser_for_data.py       # SeleniumBase (stealth) + Playwright/CDP session manager
│   │   ├── login_claude.py           # One-time manual login, persists Claude.ai session
│   │   ├── login_chatgpt.py          # One-time manual login, persists ChatGPT session
│   │   ├── visa_catalog.py           # Phase 1 — discovers every visa type per country
│   │   ├── extract_visa_knowledge.py # Phase 2 — extracts full detail for each cataloged visa
│   │   ├── clean_knowledge.py        # Strips citation artifacts, normalizes cost/currency pairing
│   │   ├── validate_extraction.py    # Cross-checks extracted data against the catalog; schema checks
│   │   ├── filter_knowledge.py       # Removes visa types not applicable to Pakistani nationals
│   │   ├── merge_and_export.py       # Merges all countries' extracted entities into one CSV
│   │   └── csv_to_json.py            # Utility conversion helper
│   │
│   ├── database/               # Supabase loading, content assembly, currency, stable IDs
│   ├── embeddings/             # Vector embedding computation
│   ├── retrieval/              # Query classification + four retrieval strategies
│   ├── generation/             # Prompts, citation handling, LLM generation
│   ├── fast_api.py             # FastAPI layer exposing the full pipeline
│   └── session_store.py        # In-memory per-session conversation state
│
├── FRONTEND/                   # User-facing web app (built with Lovable)
│
├── requirements.txt            # Python dependencies
├── .gitignore
└── README.md
```

> **Note:** Data collection and the database/retrieval/generation layers are intentionally decoupled. The collection pipeline's only contract with the rest of the system is the final CSV it produces — everything downstream (Supabase loading, embeddings, retrieval, generation) works from that CSV regardless of how it was collected.

---

## Architecture

### High-level flow

```
visa_catalog.py (Phase 1: per-country catalog discovery, browser-automated)
    → visa_catalog/<Country>.json  (reviewed by hand before Phase 2)

extract_visa_knowledge.py (Phase 2: per-visa detail extraction, browser-automated)
    → visa_knowledge/<Country>_knowledge.json

clean_knowledge.py → validate_extraction.py → filter_knowledge.py → merge_and_export.py
    → final CSV

final CSV → load_csv_to_supabase.py → visa_knowledge (Postgres/pgvector)
visa_knowledge → build_content_postgres.py → embedder_postgres.py

User Query → fast_api.py → router.py → [retrieval path] → generator.py → Answer
```

### The four retrieval paths

| Category | Deciding question | Retrieval strategy |
|---|---|---|
| **Factual** | Could the answer be one short fact/number/list from one source? | pgvector cosine-similarity search |
| **General** | Does it require explaining a concept, or synthesis across sources? | pgvector search, diversified round-robin per country |
| **Recommendation** | Did the user state something personal about themselves to filter against? | Direct structured SQL filtering + soft scoring — **not** vector search |
| **Comparison** | Explicit or implicit request to compare 2+ countries/visas? | Deterministic per-country fetch — **not** vector search |

Query classification is handled by an LLM call (not keyword rules) that also extracts structured entities (country, purpose, education level, budget, etc.) in the same pass.

---

## How It Works — End to End

### 1. Data Collection (`BACKEND/data_collection/`)

The collection pipeline is fully browser-automated, driving an authenticated Claude.ai or ChatGPT session via SeleniumBase (stealth mode) + Playwright over Chrome DevTools Protocol, rather than crawling and scraping official sites directly.

- **Phase 1 — Catalog discovery (`visa_catalog.py`)** — For each of the six target countries, a web-search-grounded prompt asks the model to enumerate every distinct visa subclass offered, sourced strictly from official government/embassy domains (`.gov`, `.diplo.de`, `.mofa.go.jp`, `travel.state.gov`, etc.) — explicitly excluding Wikipedia, blogs, forums, and visa agencies. Each entry gets a machine-readable `visa_key`, a canonical `purpose`, and a `source_url`. Output is one JSON file per country, meant to be **reviewed by hand** before Phase 2 runs against it.
- **Phase 2 — Per-visa extraction (`extract_visa_knowledge.py`)** — For every catalog entry, a separate, narrowly-scoped prompt asks the model to research and return exactly one fully structured visa entity (eligibility, required documents, application process, fees, processing times, income/points thresholds, etc.) — explicitly forbidden from returning information about any other visa encountered during research, even closely related ones on the same source page. `country` and `source_url` are force-injected into the output afterward rather than trusted to the model. Includes resume logic (skips already-extracted visas) and automatic fresh-chat resets every few visas to avoid context growth.
- **Cleaning & validation (`clean_knowledge.py`, `validate_extraction.py`)** — Strips recurring citation-marker artifacts from text fields, enforces that cost and currency fields are always populated together, and cross-checks every extracted file against its source catalog (missing/extra/duplicate `visa_key` detection, required-field presence, enum validity, URL formatting, date formatting) with a full pass/fail summary per country.
- **Filtering (`filter_knowledge.py`)** — Removes visa types not applicable to Pakistani nationals from the extracted knowledge (e.g. nationality-restricted categories, EU-citizen-only pathways) via a per-country blacklist.
- **Merge & export (`merge_and_export.py`)** — Flattens every country's cleaned, filtered entities into one merged JSON and a single CSV, matching exactly the column format `load_csv_to_supabase.py` expects.

> This approach replaced an earlier crawl-then-scrape-then-extract pipeline (sitemap/BFS discovery → Trafilatura cleaning → single-page LLM extraction) that stalled at the extraction stage due to Groq API rate limits and weak local-model output on dense pages. The current two-phase, catalog-then-extract browser-automation strategy is what successfully unblocked data collection.

### 2. Database Layer (`BACKEND/database/`, `BACKEND/embeddings/`)

- Validated CSV loading into a Postgres (Supabase) table with stable, hash-derived record IDs that survive re-scrapes.
- `content` (the full text shown to users and cited from) is **assembled deterministically from structured fields — never generated by an LLM.** This is the single biggest guardrail against citation hallucination in the whole system.
- A separate, narrower `embedding_text` (title + purpose + topic + visa_type + summary) is used only for the vector itself, to keep embeddings focused rather than diluted by every procedural field.
- Embeddings are computed with `BAAI/bge-base-en-v1.5` and stored directly in Postgres via `pgvector`, with content-hash-based incremental re-embedding.

### 3. Retrieval (`BACKEND/retrieval/`)

- `query_classifier.py` — LLM-based classification into one of four categories, plus entity extraction, with conversation-history awareness that is explicitly guarded against leaking stale context into unrelated new questions.
- `factual_retrieval.py` / `general_retrieval.py` — pgvector similarity search, with the general path diversifying results round-robin across countries so one dense embedding neighborhood can't dominate a cross-country answer.
- `recommendation_retrieval.py` — Structured SQL filtering on hard constraints (country, purpose, education level, budget, language test), with soft-scoring, relaxation fallback, and round-robin diversification when no country is specified.
- `comparison_retrieval.py` — One deterministic query per country, guaranteeing every side of a comparison is represented — something similarity search alone cannot promise.
- `router.py` — The single entry point tying classification to retrieval. Accepts optional per-visa card context (`context_country`, `context_visa_type`, `context_visa_id`) so a question like *"what is this?"* asked with a specific visa card open resolves to that exact record rather than searching broadly.

### 4. Generation (`BACKEND/generation/`)

- `citation_utils.py` normalizes three structurally different result shapes into one numbered source list, and resolves `[Source N]` markers into clean `[N]` citation badges.
- `prompts.py` encodes hard-won correctness rules: unsourced claims must be explicitly labeled "From general knowledge," numeric comparisons across units must show their conversion inline, and — critically — **the LLM must never estimate or convert a currency exchange rate itself.**
- `generator.py` calls the LLM with a hardened system prompt that resists being reframed by instructions embedded in the user's message or in scraped source content (prompt-injection hardening), then resolves citations and appends a disclaimer.

### 6. Session Management (`BACKEND/session_store.py`)

A per-`session_id` in-memory store (not persisted across server restarts) tracking:

- `recommendation_context` — the most recent set of recommendation results, so follow-up questions like *"which one is cheapest"* can resolve against it without the frontend resending the whole list.
- `user_profile` — the countries, purpose, education level, language test/score, and budget/currency last submitted via `/recommend`.
- `selected_visa` — the `{country, visa_type, id}` of the currently open visa card, set directly from whatever `context_country` / `context_visa_type` / `context_visa_id` the frontend sends with each `/ask` request (the frontend is the source of truth for what's currently "open"; the backend doesn't merge this with a prior value).
- `history` — the last 8 user/assistant turn pairs, used by the query classifier to resolve conversational references (e.g. *"compare it to Japan"*).

Note: the frontend maintains its own **multiple, independent sessions** (see Section 7 below), each with its own `session_id` — the backend's in-memory store is keyed per `session_id`, so each frontend session gets its own isolated `recommendation_context`, `user_profile`, `selected_visa`, and `history` on the backend automatically, with no extra backend logic required.

### 7. Frontend Flow — Form → Results → Follow-up Chat (`FRONTEND/`)

Built with **Lovable** (React + TypeScript + Tailwind), consuming the API described above. The user-facing flow has two views toggled by local state, no routing library:

**View 1 — Recommendation form.** A single form collects `purpose`, a multi-select of target countries (checkbox dropdown over the six supported countries — leaving it empty matches any country), `education_level`, and `budget` + `budget_currency`. A client-side plausibility check rejects an implausibly low budget (under ~Rs 20,000, mirroring the backend's own `MIN_PLAUSIBLE_BUDGET_USD` guard in `router.py`) before the request is even sent, with the submit button disabled and an inline error shown rather than a wasted round trip. On submit, this calls `POST /recommend`; on success the app switches to the results view with an assistant welcome message summarizing how many pathways were found.

**View 2 — Split-screen results.** Left panel is a scrollable list of recommendation cards (`RecommendationList` / `RecommendationCard`), one per matched visa, each an accordion: collapsed shows country/visa-type tags, title, a 2-line summary, and an official-source link; expanding lazily fetches `GET /visa-detail/{id}` (cached client-side per visa id so re-expanding never refetches) and renders eligibility, required documents, application process, fees/costs, important notes, and a last-verified date. Each expanded card ends with an **"Ask the assistant about this visa"** button that sends a pre-filled question using that card's title/country as context.

Right panel is the chat (`ChatPanel` / `ChatMessage`), calling `POST /ask` on every message. Opening a card sets the chat's active context (`country`, `visa_type`, and critically `visa_id`) so a question like *"what is this?"* resolves against that exact database record on the backend rather than being answered generically — this closes the loop with `router.py`'s `context_visa_id` priority handling described in Section 3. The header line shows *"Focused on {country} · {visa_type}"* when a card is open, or a general-context message otherwise. If a chat response includes `updated_recommendations` (a stated refinement, e.g. *"I also have a Master's"*), the left panel's results are replaced in place, the open card collapses, and the detail cache clears.

**Multi-session support.** Unlike a single running conversation, the frontend maintains a list of independent sessions (`Session[]`), each with its own `id` (a fresh backend `session_id`), form data, recommendation results, card cache, chat context, and message history — switchable from the sidebar, with a "New chat" action starting a fresh assessment from scratch. Sessions (and which one is active) are persisted to `sessionStorage` so a page refresh doesn't lose in-progress work; this clears when the tab closes and is explicitly scoped to non-sensitive UI state only — no personal form data or chat content is intended to persist beyond the tab's lifetime per the original security requirements, though the current implementation does persist full session content (including chat text and submitted form values) to `sessionStorage` for refresh-resilience — see Known Limitations.

**Security posture**, carried over from the original build spec and consistently applied in the shipped code: `ChatMessage.tsx` never uses `dangerouslySetInnerHTML` on raw model text directly — citation-marker formatting is run through a sanitizer first (see `lib/sanitize.ts`), source URLs are validated with `safeUrl()` before being used in any `href`, and every externally-sourced link uses `target="_blank" rel="noopener noreferrer"`. Errors are surfaced as inline UI state, never `alert()`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Browser automation (data collection) | SeleniumBase (stealth) + Playwright (via Chrome DevTools Protocol) |
| Catalog & extraction LLMs | Claude.ai / ChatGPT, driven via authenticated browser session (web-search-grounded) |
| Database | Supabase — PostgreSQL with the `pgvector` extension |
| Embeddings | `BAAI/bge-base-en-v1.5` (SentenceTransformers) |
| Query classification & generation | Groq API — `llama-3.1-8b-instant` (classification), `llama-3.3-70b-versatile` (generation) |
| Application layer | FastAPI (Python) |
| Frontend | React + TypeScript + Tailwind CSS (built with Lovable) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A Supabase (Postgres + pgvector) project
- A Groq API key
- Chrome/Chromium (for browser-automated data collection)
- A logged-in Claude.ai or ChatGPT account (session persisted via `login_claude.py` / `login_chatgpt.py`)

### Installation

```bash
git clone <repo-url>
cd ImmigrationAssistant
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file with:

```
SUPABASE_DB_URL=<your Postgres connection string — use the Session Pooler, not the direct connection>
GROQ_API_KEY=<your Groq API key>
```

### Running the data collection pipeline

```bash
# 0. One-time manual login (persists session to browser_profiles/)
python BACKEND/data_collection/login_claude.py --profile claude

# 1. Phase 1 — discover each country's visa catalog (review output by hand before Phase 2)
python BACKEND/data_collection/visa_catalog.py \
    --output_dir "visa_catalog" \
    --countries Germany USA Australia Japan France Finland \
    --profile claude

# 2. Phase 2 — extract full detail for each cataloged visa
python BACKEND/data_collection/extract_visa_knowledge.py \
    --catalog_dir "visa_catalog" \
    --output_dir "visa_knowledge" \
    --profile claude

# 3. Clean, validate, and filter extracted data
python BACKEND/data_collection/clean_knowledge.py --knowledge_dir "visa_knowledge"
python BACKEND/data_collection/validate_extraction.py --catalog_dir "visa_catalog" --knowledge_dir "visa_knowledge"
python BACKEND/data_collection/filter_knowledge.py --knowledge_dir "visa_knowledge"

# 4. Merge into a single CSV
python BACKEND/data_collection/merge_and_export.py \
    --knowledge_dir "visa_knowledge" \
    --output_json "merged_knowledge.json" \
    --output_csv "merged_knowledge.csv"

# 5. Load into Supabase
python BACKEND/database/load_csv_to_supabase.py merged_knowledge.csv

# 6. Build content and compute embeddings
python BACKEND/database/build_content_postgres.py
python BACKEND/embeddings/embedder_postgres.py
```

### Running the API

```bash
cd BACKEND
uvicorn fast_api:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

> By default, CORS is restricted to `http://localhost:8081` (see `fast_api.py`) — update `allow_origins` if your frontend runs on a different port/origin.

### Running the frontend

The `FRONTEND/` app is a React + TypeScript + Tailwind app built with [Lovable](https://lovable.dev), running end-to-end against the API above (recommendation form → results with follow-up chat).

```bash
cd FRONTEND
npm install
npm run dev
```

Set the API base URL via an environment variable (e.g. `VITE_API_BASE_URL`) pointing at your running `fast_api.py` instance — never hardcode it. Continued development can also happen directly in the [Lovable editor](https://lovable.dev), which syncs changes straight back to this repository.

---

## API Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/ask` | `POST` | Full pipeline — classify, route, retrieve, generate a cited answer, and persist the conversation turn. |
| `/route` | `POST` | Debug endpoint — classification and retrieval only, no LLM generation call. |
| `/recommend` | `POST` | Direct structured recommendation from a filter form, bypassing the classifier. |
| `/visa-detail/{visa_id}` | `GET` | Fetches one full structured record for a detail-card view. |
| `/health` | `GET` | Basic liveness check. |

### `POST /ask`

Request body:

```json
{
  "session_id": "demo-session",
  "query": "What documents do I need for a German student visa?",
  "context_country": null,
  "context_visa_type": null,
  "context_visa_id": null
}
```

`context_country` / `context_visa_type` / `context_visa_id` are optional and let the frontend tell the backend which visa card (if any) is currently open, so a question like *"what is this?"* resolves to that exact record. Every `/ask` call updates the session's `selected_visa` to exactly what was sent in the request.

Response:

```json
{
  "query": "What documents do I need for a German student visa?",
  "category": "factual",
  "answer": "...",
  "sources": [...],
  "missing_countries": [],
  "updated_recommendations": null
}
```

### `POST /recommend`

Request body:

```json
{
  "session_id": "demo-session",
  "countries": ["Germany", "Finland"],
  "purpose": "study",
  "education_level": "bachelor",
  "language_test": "IELTS",
  "language_score": "7.0",
  "budget": 15000,
  "budget_currency": "PKR"
}
```

`budget_currency` is required whenever `budget` is set — the endpoint rejects the request with a 400 if it's missing or unsupported. Results and the submitted profile are persisted to the session for later `/ask` follow-ups.

### `GET /visa-detail/{visa_id}`

Returns the full structured record for one visa (eligibility, required documents, application process, fees, processing time, validity, PR pathway info, etc.) for a detail-card view.

Example:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session",
    "query": "What documents do I need for a German student visa?"
  }'
```

---

## Current Status

| Component | Status |
|---|---|
| Data collection — catalog discovery (Phase 1) | ✅ Completed |
| Data collection — per-visa extraction (Phase 2) | ✅ Completed |
| Cleaning, validation & filtering | ✅ Completed |
| Merge & CSV export | ✅ Completed |
| Database layer (Supabase/pgvector) | ✅ Completed |
| Retrieval layer (4-path) | ✅ Completed |
| Query classification | ✅ Completed |
| Generation & citations | ✅ Completed |
| Session management | ✅ Completed (in-memory only) |
| API layer | ✅ Completed |
| Frontend (Lovable) — form → results → follow-up chat | ✅ Completed, running end to end |
| Six-country coverage (Germany, USA, Australia, Japan, France, Finland) | ✅ Completed |
| Production deployment | 🔴 Not Started |

---

## Known Limitations

- Data collection depends on browser automation of consumer chat interfaces (Claude.ai / ChatGPT), which is fragile to interface/DOM changes and carries Terms-of-Service considerations.
- Catalog discovery (Phase 1) and per-visa extraction (Phase 2) both depend on the underlying LLM's web search actually finding and using official sources — output is designed to be reviewed by hand rather than trusted blindly.
- A single entity-level embedding underserves very specific factual questions where the relevant detail lives in a field (e.g. required documents) not included in the embedded text.
- The session store is in-memory only and does not persist across server restarts.
- CORS is currently restricted to a single hardcoded local origin.
- The frontend persists full session state — including chat message text and submitted form values (education, budget) — to `sessionStorage` for refresh-resilience, which is broader than the original "only the session ID may persist" security intent; acceptable for a no-auth demo, but should be tightened before handling genuinely sensitive user data.
- The system has not yet been deployed to a hosted environment.

---

## Roadmap

- **More visa types & deeper country coverage** — broaden beyond the current six-country catalog as new sources are reviewed.
- **Further RAG improvements** — hybrid keyword + vector search, result reranking, field-level embeddings.
- **Deployment** — move from local development to a hosted production environment with proper environment/secrets management and CORS configuration.
- **Full user-flow validation with real users** — the eligibility form → recommendation results → detail view → follow-up chat path is implemented and running end to end; next is broader testing with real users rather than internal walkthroughs.

---

## Contributors

- **Ayesha Bhatti**
- **Eman Aijaz**