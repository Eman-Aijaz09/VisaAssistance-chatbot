EXTRACTION_PROMPT = """
You are an expert information extraction system specializing in immigration and visa information.

Your task is to extract ALL immigration-related knowledge entities from the provided webpage.

IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Do NOT include explanations.
3. Do NOT wrap the JSON in markdown.
4. If multiple visa types or immigration topics exist, return multiple entities.
5. If information is missing, use null or [].
6. Never invent information.
7. Preserve wording whenever possible.
8. Summaries should be concise (2-3 sentences maximum).

The JSON MUST follow this schema:

{
    "entities": [
        {
            "country": "",
            "source_url": "",
            "page_title": "",

            "purpose": "",
            "topic": "",
            "visa_type": null,

            "title": "",
            "summary": "",

            "eligibility": [],
            "required_documents": [],

            "application_process": [],

            "processing_time": null,
            "application_fee": null,
            "validity": null,

            "official_links": [],
            "important_notes": [],

            "extra_information": {}
        }
    ]
}

The webpage content begins below.

====================================================
{{CONTENT}}
====================================================
"""