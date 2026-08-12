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
    country = (row["country"] or "").strip().lower()
    visa_key = (row["visa_key"] or "").strip().lower()

    if visa_key:
        key_string = f"{country}|{visa_key}"
    else:
        # fallback for older rows without visa_key
        key_string = "|".join([
            country,
            (row["source_url"] or "").strip().lower(),
            (row["title"] or "").strip().lower(),
            (row["entry_type"] or "").strip().lower(),
        ])
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()[:16]