#llm.py
import json
import os
from datetime import date

from groq import Groq
from pydantic import ValidationError

from DATA_INGESTION.models.page_extraction import PageExtraction
from DATA_INGESTION.utils.prompts_utils import EXTRACTION_PROMPT
from config import MODEL


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables.")
    return Groq(api_key=api_key)


def _normalize_empty_strings(obj):
    """
    Recursively convert empty strings to None throughout the parsed
    JSON before Pydantic validation. Groq's JSON mode doesn't reliably
    emit `null` for every unpopulated field despite the prompt asking
    for it — it often returns "" instead, which fails validation
    against typed Optional[int]/Optional[bool]/Optional[EligibilityGate]
    fields.
    """
    if isinstance(obj, dict):
        return {k: _normalize_empty_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_normalize_empty_strings(v) for v in obj]
    elif obj == "":
        return None
    else:
        return obj


def extract_entities(
    markdown: str,
    country: str,
    source_url: str,
    page_title: str,
    model: str = MODEL,
):
    client = get_groq_client()

    prompt = EXTRACTION_PROMPT.replace("{{CONTENT}}", markdown)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a highly accurate information extraction system."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    print("\n========== RAW LLM RESPONSE ==========\n")
    print(content)
    print("\n======================================\n")

    try:
        parsed = json.loads(content)
        parsed = _normalize_empty_strings(parsed)

        extraction = PageExtraction.model_validate(parsed)

        today = date.today().isoformat()

        for entity in extraction.entities:
            entity.country = country
            entity.source_url = source_url
            entity.page_title = page_title
            entity.last_verified_date = today

        return extraction

    except json.JSONDecodeError as e:
        print("Failed to parse JSON.")
        print(content)
        raise e

    except ValidationError as e:
        print("Pydantic validation failed.")
        print(e)
        raise e