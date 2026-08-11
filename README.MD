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
- [Evaluation](#evaluation)
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

The project spans the full lifecycle of a production RAG application:

```
Official Websites → Crawling → Processing → Categorization (LLM extraction)
    → Grouping & Merging → Structured Database (Postgres + pgvector)
    → Query Classification → Retrieval → Generation → API → Frontend
```

---

## Repository Structure

```
ImmigrationAssistant/
├── DATA_INGESTION/            # Offline pipeline: raw web content → structured knowledge
│   └── new_approach/
│       ├── crawler/           # Discovers and downloads pages from official sites
│       ├── processor/         # Filters and cleans downloaded pages into plain text
│       ├── categorization/    # LLM-based structured extraction (in progress)
│       ├── debug_html/        # Raw HTML output from the crawler
│       ├── cleaned_text/      # Cleaned .txt output from the processor
│       ├── queue_state/       # Resumable per-country/website crawl state
│       └── reports/           # Audit trail of keep/skip decisions
│
├── RAG/                       # Online application: query → retrieval → generation
│   ├── data/                  # Sample/seed data for local development
│   ├── database/              # Supabase loading, content assembly, currency, stable IDs
│   ├── embeddings/            # Vector embedding computation
│   ├── retrieval/             # Query classification + four retrieval strategies
│   ├── generation/            # Prompts, citation handling, LLM generation
│   ├── eval/                  # Golden-query evaluation harness
│   ├── session_store.py       # In-memory per-session conversation state
│   └── fast_api.py            # FastAPI layer exposing the full pipeline
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
- [Evaluation](#evaluation)
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

The project spans the full lifecycle of a production RAG application:

```
Official Websites → Crawling → Processing → Categorization (LLM extraction)
    → Grouping & Merging → Structured Database (Postgres + pgvector)
    → Query Classification → Retrieval → Generation → API → Frontend
```

---

## Repository Structure

```
ImmigrationAssistant/
├── DATA_INGESTION/            # Offline pipeline: raw web content → structured knowledge
│   └── new_approach/
│       ├── crawler/           # Discovers and downloads pages from official sites
│       ├── processor/         # Filters and cleans downloaded pages into plain text
│       ├── categorization/    # LLM-based structured extraction (in progress)
│       ├── debug_html/        # Raw HTML output from the crawler
│       ├── cleaned_text/      # Cleaned .txt output from the processor
│       ├── queue_state/       # Resumable per-country/website crawl state
│       └── reports/           # Audit trail of keep/skip decisions
│
├── RAG/                       # Online application: query → retrieval → generation
│   ├── data/                  # Sample/seed data for local development
│   ├── database/              # Supabase loading, content assembly, currency, stable IDs
│   ├── embeddings/            # Vector embedding computation
│   ├── retrieval/             # Query classification + four retrieval strategies
│   ├── generation/            # Prompts, citation handling, LLM generation
│   ├── eval/                  # Golden-query evaluation harness
│   ├── session_store.py       # In-memory per-session conversation state
│   └── fast_api.py            # FastAPI layer exposing the full pipeline
│
├── frontend/                  # User-facing web app (built with Lovable)
│
├── fast_api.py                # Root-level API entry point
├── requirements.txt           # Python dependencies
├── test_llm.py                # LLM extraction test/debug script
├── .gitignore
└── README.md
```

> **Note:** `DATA_INGESTION/` and `RAG/` are intentionally decoupled. Crawling produces raw HTML independent of how it will later be cleaned; processing produces clean text independent of how it will later be structured; retrieval is independent of which category a query falls into. This separation makes the system easier to debug and extend one stage at a time.

---

## Architecture

### High-level flow

```
config.py → crawler/ → debug_html/ → processor/ → cleaned_text/
cleaned_text/ → categorization/ (LLM extraction) → extracted_json/
extracted_json/ → grouping.py → merge_save_to_csv.py → final CSV
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

### 1. Data Ingestion (`DATA_INGESTION/`)

- **Crawling** — Discovers pages via sitemap parsing (fast path) and BFS link traversal (fallback), using SeleniumBase (stealth) + Playwright over CDP to render JavaScript-heavy government sites. A priority queue ranks and resumes crawls per website.
- **Processing** — A two-pass filter (URL-level, then content-level) discards junk pages (privacy policies, contact pages, near-empty content), and Trafilatura (with a BeautifulSoup fallback) converts the remaining HTML into clean plain text.
- **Categorization** *(in progress)* — Cleaned text is sent to an LLM with a strict extraction schema and anti-hallucination rules, returning structured JSON visa entities. `country` and `source_url` are injected programmatically after extraction, never trusted to the LLM.
- **Grouping & Merging** *(planned)* — Records describing the same real-world visa, scattered across multiple pages, will be grouped and merged into one canonical entity, with conflicts flagged rather than silently resolved.

### 2. Database Layer (`RAG/database/`, `RAG/embeddings/`)

- Validated CSV loading into a Postgres (Supabase) table with stable, hash-derived record IDs that survive re-scrapes.
- `content` (the full text shown to users and cited from) is **assembled deterministically from structured fields — never generated by an LLM.** This is the single biggest guardrail against citation hallucination in the whole system.
- A separate, narrower `embedding_text` (title + purpose + topic + visa_type + summary) is used only for the vector itself, to keep embeddings focused rather than diluted by every procedural field.
- Embeddings are computed with `BAAI/bge-base-en-v1.5` and stored directly in Postgres via `pgvector`, with content-hash-based incremental re-embedding.

### 3. Retrieval (`RAG/retrieval/`)

- `query_classifier.py` — LLM-based classification into one of four categories, plus entity extraction, with conversation-history awareness that is explicitly guarded against leaking stale context into unrelated new questions.
- `factual_retrieval.py` / `general_retrieval.py` — pgvector similarity search, with the general path diversifying results round-robin across countries so one dense embedding neighborhood can't dominate a cross-country answer.
- `recommendation_retrieval.py` — Structured SQL filtering on hard constraints (country, purpose, education level, budget, language test), with soft-scoring, relaxation fallback, and round-robin diversification when no country is specified.
- `comparison_retrieval.py` — One deterministic query per country, guaranteeing every side of a comparison is represented — something similarity search alone cannot promise.
- `router.py` — The single entry point tying classification to retrieval, with correctness safeguards such as scoped context injection and a minimum relevance-score floor to stop off-topic queries from being answered off irrelevant sources.

### 4. Generation (`RAG/generation/`)

- `citation_utils.py` normalizes three structurally different result shapes into one numbered source list, and resolves `[Source N]` markers into clean `[N]` citation badges.
- `prompts.py` encodes hard-won correctness rules: unsourced claims must be explicitly labeled "From general knowledge," numeric comparisons across units must show their conversion inline, and — critically — **the LLM must never estimate or convert a currency exchange rate itself.**
- `generator.py` calls the LLM with a hardened system prompt that resists being reframed by instructions embedded in the user's message or in scraped source content (prompt-injection hardening), then resolves citations and appends a disclaimer.

### 5. API & Frontend

- `fast_api.py` exposes the full pipeline over HTTP (see [API Reference](#api-reference)).
- `frontend/` is the user-facing web application, built with **Lovable**, consuming the API for the chat interface, eligibility form, and visa detail views.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Browser automation | SeleniumBase (stealth) + Playwright (via Chrome DevTools Protocol) |
| Content extraction | Trafilatura (primary), BeautifulSoup (fallback) |
| Structured extraction (LLM) | Groq API (`llama-3.3-70b-versatile`); Ollama + `qwen2.5:3b-instruct` (local, experimental) |
| Database | Supabase — PostgreSQL with the `pgvector` extension |
| Embeddings | `BAAI/bge-base-en-v1.5` (SentenceTransformers) |
| Query classification & generation | Groq API — `llama-3.1-8b-instant` (classification), `llama-3.3-70b-versatile` (generation) |
| Application layer | FastAPI (Python) |
| Frontend | Lovable |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A Supabase (Postgres + pgvector) project
- A Groq API key
- Chrome/Chromium (for the crawler and extraction scripts)

### Installation

```bash
git clone <repo-url>
cd ImmigrationAssistant
pip install -r requirements.txt
```
```bash
git clone <repo-url>
cd ImmigrationAssistant
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the relevant directories (`RAG/`, `DATA_INGESTION/`) with:

```
SUPABASE_DB_URL=<your Postgres connection string — use the Session Pooler, not the direct connection>
GROQ_API_KEY=<your Groq API key>
```

### Running the ingestion pipeline

```bash
# 1. Crawl configured sources
python DATA_INGESTION/new_approach/crawler/crawler.py

# 2. Process and clean downloaded pages
python DATA_INGESTION/new_approach/processor/run-parser.py

# 3. Extract structured entities (see categorization/ — strategy still in progress)
python DATA_INGESTION/new_approach/categorization/test.py --input_dir cleaned_text --output_dir extracted_json

# 4. Load into Supabase
python RAG/database/load_csv_to_supabase.py path/to/final.csv

# 5. Build content and compute embeddings
python RAG/database/build_content_postgres.py
python RAG/embeddings/embedder_postgres.py
```

### Running the API

```bash
uvicorn RAG.fast_api:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Running the frontend

The `frontend/` app is built with [Lovable](https://lovable.dev). Refer to the project's Lovable dashboard for local preview and deployment, and ensure its API base URL points at your running `fast_api.py` instance.

---

## API Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/ask` | `POST` | Full pipeline — classify, route, retrieve, generate a cited answer, and persist the conversation turn. |
| `/route` | `POST` | Debug endpoint — classification and retrieval only, no LLM generation call. |
| `/recommend` | `POST` | Direct structured recommendation from a filter form, bypassing the classifier. |
| `/visa-detail/{visa_id}` | `GET` | Fetches one full structured record for a detail-card view. |
| `/health` | `GET` | Basic liveness check. |

Example request to `/ask`:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-session",
    "query": "What documents do I need for a German student visa?"
  }'
```

---

## Evaluation

`RAG/eval/` contains a golden-query evaluation harness:

- **25 hand-written queries**, verified against real rows in the dataset (9 factual, 6 general, 6 recommendation, 4 comparison), each documenting a specific edge case (disambiguation between similarly named visas, currency-clarification handling, deterministic tie-breaking, missing-country flagging).
- `run_eval.py` runs every query through the **real** `route_query()` function — the same one the live API calls — and scores classification accuracy and retrieval quality separately.

```bash
python -m RAG.eval.run_eval
```

**Current results:** 100% retrieval pass rate, 92% classification accuracy.

---

## Current Status

| Component | Status |
|---|---|
| Crawling pipeline | ✅ Completed |
| Processing pipeline | ✅ Completed |
| Categorization / LLM extraction | 🟡 In Progress — strategy not yet finalized |
| Grouping & merging | 🔴 Not Started — designed, not yet built |
| Database layer (Supabase/pgvector) | ✅ Completed |
| Retrieval layer (4-path) | ✅ Completed |
| Query classification | ✅ Completed (92% accuracy) |
| Generation & citations | ✅ Completed |
| Session management | ✅ Completed (in-memory only) |
| API layer | ✅ Completed |
| Frontend (Lovable) | 🟡 In Progress |
| Evaluation harness | ✅ Completed |
| RAG validated on real production data | 🔴 Not Started |
| Multi-country expansion | 🟡 In Progress (Germany, USA only so far) |
| Production deployment | 🔴 Not Started |

---

## Known Limitations

- Neither sitemap discovery nor link-based crawling guarantees full page coverage of a target site.
- The categorization/extraction stage's final strategy is not yet confirmed — Groq API rate limits, local model quality on constrained hardware, and an experimental browser-automation approach are all still being weighed.
- Grouping and merging of records describing the same visa across multiple pages is not yet implemented, and carries an acknowledged, unvalidated risk of incorrect merges.
- A single entity-level embedding underserves very specific factual questions where the relevant detail lives in a field (e.g. required documents) not included in the embedded text.
- The session store is in-memory only and does not persist across server restarts.
- The system has not yet been deployed to a hosted environment.

---

## Roadmap

- **RAG on real production data** — run the full pipeline end-to-end against real crawled and extracted data once categorization and grouping are finalized.
- **More countries and sources** — expand beyond Germany and the USA to France, Qatar, Australia, and Japan.
- **Further RAG improvements** — hybrid keyword + vector search, result reranking, and field-level embeddings.
- **Deployment** — move from local development to a hosted production environment with proper environment/secrets management and monitoring.
- **Full user-flow validation** — end-to-end testing of the eligibility form → recommendation results → detail view → chat interaction path with real users.

---

## Contributors

- **Ayesha Bhatti** 
- **Eman Aijaz** 
