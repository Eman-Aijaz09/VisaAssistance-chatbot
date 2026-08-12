"""
filter_knowledge.py

Removes non‑applicable visa entities from already‑extracted knowledge files.
After running, re‑merge and re‑export before loading into Supabase.

Usage:
    python filter_knowledge.py --knowledge_dir "data/visa_knowledge"
"""

import argparse
import json
from pathlib import Path

# --------------------------------------------------------------------
# BLACKLIST — visa_keys that are NOT applicable to Pakistani citizens
# --------------------------------------------------------------------
REMOVE_KEYS = {
    "USA": [
        "e1_visa",
        "e2_visa",
        "e2c_visa",
        "e3_visa",
        "f3_visa",
        "h1b1_visa",
        "tn_visa",
        "visa_waiver_esta",
        "s_visa",
        "t_visa",
        "u_visa",
        "v_visa",
    ],
    "Finland": [
        "working_holiday",
        "eu_citizen_registration_right_of_residence",
        "eu_citizen_family_residence_card",
        "eu_citizen_permanent_residence_card_family",
        "asylum_international_protection",
        "quota_refugee_resettlement",
        "finnish_citizenship_application_adults",
        "finnish_citizenship_declaration",
        "finnish_citizenship_for_child",
        "remigration_ingrian_evacuee",
        "returnees_extended_permit_former_soviet_union",
        "remigration_finnish_army_service",
        "remigration_descendant_finnish_citizen",
        "remigration_former_finnish_citizen",
        "victim_human_trafficking_first_permit",
        "extended_permit_victim_human_trafficking",
        "extended_permit_domestic_violence",
        "extended_permit_victim_employer_exploitation",
    ],
    "Japan": [],
    "Germany": [],
    "Australia": [
        # nationality restricted
        "eta_601", "evisitor_651", "visitor_600_frequent_traveller",
        "visitor_600_approved_destination", "working_holiday_417",
        "work_and_holiday_462", "special_category_444",
        # humanitarian / protection
        "refugee_200", "in_country_special_humanitarian_201",
        "global_special_humanitarian_202", "emergency_rescue_203",
        "woman_at_risk_204", "protection_866", "temporary_protection_785",
        "safe_haven_enterprise_790", "resolution_of_status_851",
        # onshore-only
        "visitor_600_tourist_onshore", "partner_820", "partner_801",
        "child_802", "aged_parent_804", "aged_dependent_relative_838",
        "carer_836", "remaining_relative_835", "orphan_relative_837",
        # closed / returning resident
        "former_resident_151", "resident_return_155_157",
        "business_innovation_investment_188", "business_innovation_investment_888",
    ],
    "France": [
        "working_holiday_visa",
        "afghan_resident_special_situation_visa",
        "diplomatic_service_passport_visa",
    ],
}

def clean_country_file(file_path: Path, blacklist: list) -> int:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ Could not read {file_path.name}: {e}")
        return 0

    entities = data.get("entities", [])
    if not isinstance(entities, list):
        return 0

    original_count = len(entities)
    kept = [e for e in entities if e.get("visa_key") not in blacklist]
    removed = original_count - len(kept)

    if removed > 0:
        data["entities"] = kept
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  ✅ {file_path.name}: removed {removed} non‑applicable entities")
    else:
        print(f"  ℹ️ {file_path.name}: no removals needed")

    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge_dir", required=True)
    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists():
        print(f"Directory not found: {knowledge_dir}")
        return

    total_removed = 0
    for file in sorted(knowledge_dir.glob("*_knowledge.json")):
        country = file.stem.replace("_knowledge", "")
        blacklist = REMOVE_KEYS.get(country)
        if blacklist is None:
            print(f"  ⏭️  {file.name}: no blacklist defined for {country} — skipping")
            continue
        total_removed += clean_country_file(file, blacklist)

    print(f"\nDone. Total removed: {total_removed}")

if __name__ == "__main__":
    main()