# session_store.py

"""
In-memory conversation state, keyed by a session_id the frontend
generates once per user session and includes on every request.
Not persistent across server restarts — acceptable for a demo;
swap the dict for Redis/DB later without changing the interface.
"""
"""
In-memory conversation state, keyed by a session_id the frontend
generates once per user session and includes on every request.
"""

_sessions: dict[str, dict] = {}

MAX_HISTORY_TURNS = 8

def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "recommendation_context": None,
            "user_profile": {
                "countries": None, "purpose": None, "education_level": None,
                "language_test": None, "language_score": None, "budget": None,
                "budget_currency": None,
            },
            "selected_visa": None,   # now holds {"country", "visa_type", "id"}
            "history": [],
        }
    return _sessions[session_id]

def append_turn(session_id: str, role: str, text: str):
    session = get_session(session_id)
    session["history"].append({"role": role, "text": text})
    session["history"] = session["history"][-(MAX_HISTORY_TURNS * 2):]

def update_session(session_id: str, **fields):
    session = get_session(session_id)
    session.update(fields)
    return session