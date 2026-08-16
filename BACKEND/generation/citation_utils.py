"""
citation_utils.py

Converts retrieved documents (from any retrieval path) into a
numbered source list, and provides the mapping needed to convert
inline [Source N] markers from LLM output into real citations.
"""
import re

def build_source_list(results, category: str) -> list:
    """
    Normalizes retrieved results from ANY retrieval path into a flat,
    numbered list of sources: [{"number": 1, "title": ..., "source_url": ..., "country": ...}, ...]

    Handles the three different result shapes:
      - factual/general: list of {"content", "metadata", "score"}
      - recommendation:   list of raw dicts (SQLite rows)
      - comparison:       dict keyed by country -> list of raw dicts
    """
    sources = []

    if category == "comparison":
        for country, rows in results.items():
            for row in rows:
                sources.append({
                    "title": row.get("title"),
                    "source_url": row.get("source_url"),
                    "country": row.get("country"),
                    "content": row.get("content") or _fallback_content(row),
                    "last_verified_date": row.get("last_verified_date"),
                })

    elif category == "recommendation":
        for row in results:
            sources.append({
                "title": row.get("title"),
                "source_url": row.get("source_url"),
                "country": row.get("country"),
                "content": row.get("content") or _fallback_content(row),
                "last_verified_date": row.get("last_verified_date"),
            })

    else:  # factual, general
        for r in results:
            meta = r["metadata"]
            sources.append({
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "country": meta.get("country"),
                "content": r["content"],
                "last_verified_date": meta.get("last_verified_date"),
            })

    # Number them — this numbering is what [Source N] in the LLM prompt refers to
    for i, s in enumerate(sources, start=1):
        s["number"] = i

    return sources


def _fallback_content(row: dict) -> str:
    """
    Recommendation/comparison rows come straight from SQLite and may
    not have a pre-built 'content' blob depending on your schema —
    build a minimal readable summary from the raw fields if needed.
    """
    parts = [
        f"Title: {row.get('title')}",
        f"Country: {row.get('country')}",
        f"Visa Type: {row.get('visa_type')}",
        f"Summary: {row.get('summary')}",
    ]
    return "\n".join(p for p in parts if p)


def format_sources_for_prompt(sources: list) -> str:
    """
    Builds the source-block text injected into the generation prompt,
    labeled [Source N] so the LLM can reference them inline.
    """
    blocks = []
    for s in sources:
        verified_line = f"Last verified: {s['last_verified_date']}\n" if s.get("last_verified_date") else ""
        blocks.append(
            f"[Source {s['number']}] {s['title']} ({s['country']})\n"
            f"URL: {s['source_url']}\n"
            f"{verified_line}"
            f"{s['content']}\n"
        )
    return "\n---\n".join(blocks)


def resolve_citations(answer_text: str, sources: list) -> str:
    """
    Replaces [Source N] markers with compact numeric references [N].

    Handles BOTH patterns the LLM produces:
      - separate brackets: [Source 1][Source 2]
      - combined brackets: [Source 1, Source 2, Source 3]

    A simple string-replace on "[Source N]" only catches the first
    pattern — combined brackets never match that exact substring and
    leak through to the user as raw unresolved text. This regex-based
    approach extracts ALL numbers from EVERY bracket, regardless of
    how the LLM grouped them, and emits one clean [N] badge per number.
    """
    valid_numbers = {s["number"] for s in sources}

    def replace_bracket(match):
        # match.group(1) is everything between "[Source " and "]"
        # e.g. "1" or "1, 2, 3" or "5,6"
        raw_numbers = re.findall(r"\d+", match.group(1))
        badges = []
        for n in raw_numbers:
            num = int(n)
            if num in valid_numbers:
                badges.append(f"[{num}]")
            # silently drop numbers that don't correspond to a real
            # source, rather than showing a broken/misleading badge
        return "".join(badges) if badges else ""

    # Matches "[Source 1]", "[Source 1, Source 2]", "[Source 1, 2, 3]", etc.
    pattern = re.compile(r"\[Source\s+(\d+(?:\s*,\s*(?:Source\s+)?\d+)*)\]")
    return pattern.sub(replace_bracket, answer_text)