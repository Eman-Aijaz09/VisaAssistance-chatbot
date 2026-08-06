# session_store.py

"""
In-memory conversation state, keyed by a session_id the frontend
generates once per user session and includes on every request.
Not persistent across server restarts — acceptable for a demo;
swap the dict for Redis/DB later without changing the interface.
"""

_sessions: dict[str, dict] = {}

# def get_session(session_id: str) -> dict:
#     if session_id not in _sessions:
#         _sessions[session_id] = {
#             "recommendation_context": None,   # last /recommend results
#             "user_profile": {                  # merged form + refinement state
#                 "countries": None, "purpose": None, "education_level": None,
#                 "language_test": None, "language_score": None, "budget": None,
#             },
#             "selected_visa": None,             # {country, visa_type} — last card opened
#         }
#     return _sessions[session_id]

MAX_HISTORY_TURNS = 8   # last N user+assistant exchanges kept for context resolution

def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "recommendation_context": None,
            "user_profile": {
                "countries": None, "purpose": None, "education_level": None,
                "language_test": None, "language_score": None, "budget": None,
                "budget_currency": None,
            },
            "selected_visa": None,
            "history": [],   # NEW — [{"role": "user"/"assistant", "text": ...}, ...]
        }
    return _sessions[session_id]

def append_turn(session_id: str, role: str, text: str):
    """Appends one turn to conversation history, trimming to the last
    MAX_HISTORY_TURNS*2 messages (user+assistant pairs)."""
    session = get_session(session_id)
    session["history"].append({"role": role, "text": text})
    session["history"] = session["history"][-(MAX_HISTORY_TURNS * 2):]

def update_session(session_id: str, **fields):
    session = get_session(session_id)
    session.update(fields)
    return session