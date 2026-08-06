# query_classifier.py
import os
from dotenv import load_dotenv

load_dotenv()

import json
from groq import Groq

MODEL = "llama-3.1-8b-instant"

QUERY_CLASSIFICATION_PROMPT = """
You are a query router for a visa/immigration assistant. Classify the
user's question into exactly one category, and extract any relevant
entities mentioned.

CATEGORIES:
- "factual": asks for ONE SPECIFIC, EXTRACTABLE DATA POINT about a
  SINGLE named visa — a number, a yes/no, a specific list (fee,
  processing time, points required, one eligibility criterion, one
  document list). The answer is a short, concrete fact drawn from one
  source.
- "recommendation": the user states THEIR OWN qualifications,
  constraints, or situation (education, budget, language, experience,
  or an explicit personal intent like "I have X, I want Y") and wants
  to know WHICH visa/country fits. The defining signal is a personal
  detail to filter against — not just the topic of immigration options.
- "comparison": explicitly or implicitly asks to compare two or more
  countries/visas against each other
- "general": asks to EXPLAIN, UNDERSTAND, or SYNTHESIZE how something
  works, what a program/system/category consists of, or an overview
  that likely spans MULTIPLE related visas/sources — even if it names
  one visa or one country. Signal words: "how does X work", "what is
  X" (for a program/system, not a single fact), "what options exist".
  The answer requires explaining a concept or covering more than one
  discrete fact, not just returning a single number or short list.
  Mentioning specific countries does NOT make this "recommendation" —
  unless the user also states something personal to filter against.

FACTUAL vs GENERAL — the deciding question: could the answer be ONE
short fact/number/list from ONE source? -> factual. Does answering
well require explaining a system/concept, or drawing from MULTIPLE
sources to give a fuller picture? -> general. "How does Australia's
points-based system work" -> general (explaining a system, likely
spans 189 + 190). "How many points does Australia's Subclass 189
require" -> factual (one number, one source).

CRITICAL DISTINCTION (recommendation vs general): "What research visa
options exist in Germany and France?" -> general (no personal
qualifications stated, just asking what exists). "I have a PhD, what
research visa options exist in Germany and France?" -> recommendation
(personal qualification stated: PhD). The presence of named countries
or a topic keyword ("options", "visas for X") is NOT sufficient for
recommendation on its own — look specifically for a stated personal
attribute.

- "is_refinement": true/false — true if the user is stating a NEW or CHANGED
constraint about themselves (education, budget, language, country
preference) rather than asking a question. Examples: "I also have a
Master's", "my budget is only $15,000", "only show European countries",
"remove Canada", "can you narrow it down". False for genuine questions
like "which one is cheapest" or "what documents do I need".

Return ONLY valid JSON, no markdown, no explanation, matching this schema:

{
  "category": "factual" | "recommendation" | "comparison" | "general",
  "countries": [],              // country names mentioned, e.g. ["Germany"], [] if none
  "purpose": null,               // one of: study, work, tourist, family_reunion, business, permanent_residency, or null
  "visa_type": null,             // specific visa name if mentioned, else null
  "education_level": null,       // one of: none, bachelor, master, phd, or null if not mentioned
  "language_test": null,         // test name only, e.g. "IELTS", "TOEFL", "IELTS", or null
  "language_score": null,        // score AS STATED by the user, as a string, e.g. "7", "6.5", "B2", or null
  "budget": null                 // a single number if the user states a cost limit, else null
  "budget_currency": null,       // currency code if EXPLICITLY stated or unambiguous from symbol/word (e.g. "PKR", "USD", "EUR"), else null
  "is_refinement": false
  
}

Rules for the new fields:
- Only populate these if the user EXPLICITLY states them. Never infer
  or guess a value that wasn't stated.
- "education_level" must map to exactly one of: none, bachelor, master,
  phd. If the user says "Bachelor's degree", use "bachelor". If they
  say "Master's", use "master". Do not invent other values.
- "language_test" and "language_score" are usually mentioned together
  (e.g. "IELTS 7" -> language_test: "IELTS", language_score: "7").
- "visa_type" must be a SPECIFIC named visa (e.g. "EU Blue Card",
  "H-1B", "Subclass 189") — never a generic category phrase like
  "family reunion visas", "work visas", or "student visas". If the
  user only names a category/purpose rather than a specific visa,
  leave "visa_type" null and let "purpose" carry that information
  instead.
- "budget_currency": only populate if the currency is explicit (symbol
  like "$", "€", "Rs", or a word/code like "dollars", "euros", "PKR",
  "rupees"). If the user states a bare number with NO currency
  indication whatsoever (e.g. "my budget is 50000"), set "budget" to
  that number but "budget_currency" to null — do NOT guess or default
  to any currency. A bare "$15,000" implies "USD". "Rs 50000" or
  "50000 rupees" implies "PKR".
- "purpose" should be inferred from clearly work-related activities
  even without the literal word "work" — e.g. "research work",
  "doing research", "a research position", "a job in my field" all
  imply purpose="work". Similarly "studying", "a degree program",
  "attending university" imply purpose="study". Map the described
  ACTIVITY to the closest purpose category, don't require an exact
  keyword match.
- USE THE RECENT CONVERSATION only to resolve genuine references in
  the CURRENT query (e.g. "how much does it cost" after discussing a
  specific visa → that visa; "compare it to Japan" → the country/visa
  just discussed). Do NOT carry countries, visa_type, or other fields
  forward into a NEW, unrelated question just because they appeared
  earlier in the conversation. If the current query is self-contained
  and doesn't reference prior context, extract ONLY from the current
  query, ignoring the conversation history entirely.
- CRITICAL: "budget" and "budget_currency" must ONLY be extracted from
  the CURRENT user message. NEVER infer, reuse, or extract a budget
  figure from the conversation history — not from fee amounts, source
  numbers, citation markers like [1] or [2], or any number mentioned
  in a prior assistant answer. If the current message does not itself
  state a budget, both fields must be null, even if numbers appear
  anywhere in the recent conversation text.
Examples:
Query: "I want to work in tech in the US"
{"category": "recommendation", "countries": ["USA"], "purpose": "work", "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": null}

Query: "what documents do I need for a German student visa"
{"category": "factual", "countries": ["Germany"], "purpose": "study", "visa_type": "Student Visa", "education_level": null, "language_test": null, "language_score": null, "budget": null}

Query: "compare Germany and Canada for studying"
{"category": "comparison", "countries": ["Germany", "Canada"], "purpose": "study", "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": null}

Query: "what is the Opportunity Card"
{"category": "general", "countries": [], "purpose": null, "visa_type": "Opportunity Card", "education_level": null, "language_test": null, "language_score": null, "budget": null}

Query: "how does Australia's points-based skilled migration system work"
{"category": "general", "countries": ["Australia"], "purpose": null, "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": null, "budget_currency": null}

Query: "which countries can I apply to with a Bachelor's degree and IELTS 7"
{"category": "recommendation", "countries": [], "purpose": null, "visa_type": null, "education_level": "bachelor", "language_test": "IELTS", "language_score": "7", "budget": null, "budget_currency": null}

Query: "I have a PhD and want to do research work, which countries should I consider?"
{"category": "recommendation", "countries": [], "purpose": "work", "visa_type": null, "education_level": "phd", "language_test": null, "language_score": null, "budget": null, "budget_currency": null}

Query: "my budget is only 50000"
{"category": "recommendation", "countries": [], "purpose": null, "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": 50000, "budget_currency": null}

Query: "my budget is Rs 50000"
{"category": "recommendation", "countries": [], "purpose": null, "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": 50000, "budget_currency": null}

Query: "what immigration options exist for researchers in Germany and France"
{"category": "general", "countries": ["Germany", "France"], "purpose": "work", "visa_type": null, "education_level": null, "language_test": null, "language_score": null, "budget": null, "budget_currency": null}

Query: "show me family reunion visas, my spouse has a bachelor's degree"
{"category": "recommendation", "countries": [], "purpose": "family_reunion", "visa_type": null, "education_level": "bachelor", "language_test": null, "language_score": null, "budget": null, "budget_currency": null}

Now classify this query:
"{{QUERY}}"
"""


def get_groq_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


# def classify_query_llm(query: str, model: str = MODEL) -> dict:
#     """
#     Returns a dict with category, entities, and (for recommendation
#     queries) the user's stated constraints. Falls back to "general"
#     with all fields empty/null if the LLM call or parsing fails.
#     """
#     client = get_groq_client()
#     prompt = QUERY_CLASSIFICATION_PROMPT.replace("{{QUERY}}", query)
def classify_query_llm(query: str, model: str = MODEL, history: list = None) -> dict:
    """
    Returns a dict with category, entities, and (for recommendation
    queries) the user's stated constraints. Falls back to "general"
    with all fields empty/null if the LLM call or parsing fails.

    `history` (optional): recent conversation turns, used so the model
    can resolve references like "it", "that one", "the first option"
    against what was ACTUALLY discussed — instead of a fixed context
    slot being blindly reapplied to every future query regardless of
    relevance.
    """
    client = get_groq_client()

    history_block = ""
    if history:
        lines = []
        for turn in history[-6:]:   # last 3 exchanges is plenty for reference resolution
            role_label = "User" if turn["role"] == "user" else "Assistant"
            # Truncate long assistant answers — we only need enough to resolve references
            text = turn["text"][:400]
            lines.append(f"{role_label}: {text}")
        history_block = "\n\nRECENT CONVERSATION (for resolving references like 'it', 'that one', 'the previous visa' — use ONLY if the current query actually refers back to something specific; do NOT let old context leak into unrelated new questions):\n" + "\n".join(lines)

    prompt = QUERY_CLASSIFICATION_PROMPT.replace("{{QUERY}}", query) + history_block

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a precise query classification system."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)

        return {
            "category": parsed.get("category", "general"),
            "countries": parsed.get("countries", []) or [],
            "purpose": parsed.get("purpose"),
            "visa_type": parsed.get("visa_type"),
            "education_level": parsed.get("education_level"),
            "language_test": parsed.get("language_test"),
            "language_score": parsed.get("language_score"),
            "budget": parsed.get("budget"),
            "budget_currency": parsed.get("budget_currency"),
            "is_refinement": parsed.get("is_refinement", False),   # NEW
        }

    except Exception as e:
        print(f"Query classification failed, defaulting to 'general': {e}")
        return {
            "category": "general",
            "countries": [],
            "purpose": None,
            "visa_type": None,
            "education_level": None,
            "language_test": None,
            "language_score": None,
            "budget": None,
            "budget_currency": None,
            "is_refinement": False,   # NEW
        }


if __name__ == "__main__":
    test_queries = [
        "I want to work in tech in the US",
        "how do I bring my spouse to Germany",
        "which countries can I apply to with a Bachelor's degree and IELTS 7",
        "compare Germany and Canada for studying",
        "what is the Opportunity Card",
        "what documents do I need for a German student visa",
    ]
    for q in test_queries:
        result = classify_query_llm(q)
        print(f"{result['category']:15} | {result} | {q}")