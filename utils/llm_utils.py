import json
import os

from groq import Groq
from pydantic import ValidationError

from models.page_extraction import PageExtraction
from utils.prompts_utils import EXTRACTION_PROMPT
from config import MODEL


def get_groq_client():
    """
    Returns a configured Groq client.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables.")

    return Groq(api_key=api_key)


def extract_entities(
    markdown: str,
    country: str,
    source_url: str,
    page_title: str,
    model: str = MODEL,
):
    """
    Extract structured immigration knowledge from webpage markdown.
    """

    client = get_groq_client()

    prompt = EXTRACTION_PROMPT.replace(
    "{{CONTENT}}",
    markdown
)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a highly accurate information extraction system.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    content = response.choices[0].message.content
    print("\n========== RAW LLM RESPONSE ==========\n")
    print(content)
    print("\n======================================\n")

    try:

        parsed = json.loads(content)

        extraction = PageExtraction.model_validate(parsed)

        #
        # Fill deterministic metadata ourselves.
        #
        for entity in extraction.entities:

            entity.country = country
            entity.source_url = source_url
            entity.page_title = page_title

        return extraction

    except json.JSONDecodeError as e:

        print("Failed to parse JSON.")
        print(content)
        raise e

    except ValidationError as e:

        print("Pydantic validation failed.")
        print(e)
        raise e