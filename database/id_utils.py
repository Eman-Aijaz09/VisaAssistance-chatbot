"""
id_utils.py

Single source of truth for how a visa_knowledge record's stable
identity is derived. Used at:
  - backfill/migration time (this script)
  - ingestion time (future scraper writes stable_id directly)
  - embed/sync time (Chroma document ID)

Never compute this logic ad-hoc in more than one place — if the key
fields ever change, this is the only file that should need editing.
"""

import hashlib


def compute_stable_id(row) -> str:
    """
    Deterministic ID derived from a record's real-world identity —
    stable across DB rebuilds and re-scrapes, unlike AUTOINCREMENT id.

    Key = source_url + title + entry_type:
      - source_url handles the common case (distinct page per visa)
      - title handles multiple visa types listed on one page
      - entry_type handles the same visa appearing as both an
        "overview" and "detailed" record
    """
    key_parts = [
        (row["source_url"] or "").strip().lower(),
        (row["title"] or "").strip().lower(),
        (row["entry_type"] or "").strip().lower(),
    ]
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()[:16]