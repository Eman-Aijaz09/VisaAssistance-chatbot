"""
clean_knowledge.py

Applies final cleanup to existing visa_knowledge JSON files:
  1. Removes citation artifacts (strong pattern).
  2. Enforces total_estimated_cost / cost_currency pairing.

Usage:
    python clean_knowledge.py --knowledge_dir "data/visa_knowledge"
"""

import argparse
import json
import re
from pathlib import Path

CITATION_SUFFIX_PATTERN = re.compile(
    r"\s+[A-Za-z0-9][\w\.\-]*(?:\+[0-9]+)(?:\s*[A-Za-z0-9][\w\.\-]*(?:\+[0-9]+))*\s*$"
)

def strip_citation_artifacts(value):
    if isinstance(value, str):
        prev = value
        while True:
            new = CITATION_SUFFIX_PATTERN.sub("", prev).strip()
            if new == prev:
                return new
            prev = new
    if isinstance(value, list):
        return [strip_citation_artifacts(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_citation_artifacts(v) for k, v in value.items()}
    return value


def clean_entity(entity: dict) -> dict:
    # Remove citation artifacts from all fields except metadata
    for key in list(entity.keys()):
        if key in ("country", "source_url", "visa_key", "last_verified_date"):
            continue
        entity[key] = strip_citation_artifacts(entity[key])

    # Normalise falsy cost/currency to None
    cost = entity.get("total_estimated_cost")
    currency = entity.get("cost_currency")

    # Treat None, "", 0, 0.0 as missing
    if not cost:
        entity["total_estimated_cost"] = None
        entity["cost_currency"] = None
    else:
        # cost is present (truthy), ensure currency present
        if not currency:
            entity["cost_currency"] = None

    return entity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge_dir", required=True)
    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists():
        print(f"Directory not found: {knowledge_dir}")
        return

    for file in sorted(knowledge_dir.glob("*_knowledge.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ Skipping {file.name}: {e}")
            continue

        entities = data.get("entities", [])
        if not isinstance(entities, list):
            continue

        cleaned = [clean_entity(e) for e in entities if isinstance(e, dict)]

        data["entities"] = cleaned
        file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  ✅ Cleaned {file.name} ({len(cleaned)} entities)")

    print("\nDone.")

if __name__ == "__main__":
    main()