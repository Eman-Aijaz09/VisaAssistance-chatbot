"""
exchange_rates.py

Static USD conversion table — single source of truth for currency
conversion, used at both ingestion time (converting scraped costs to
USD) and request time (converting a user's stated budget to USD
before it reaches recommend()).

Swap USD_RATES for a live/cached API later without touching any
caller — they only ever call convert_to_usd().
"""

USD_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "PKR": 0.0036,
    "QAR": 0.27,
    "AUD": 0.66,
    "JPY": 0.0067,
}


def convert_to_usd(amount: float, currency: str) -> float | None:
    """
    Returns None (not 0) when conversion isn't possible — callers
    must treat None as "unknown", never as "free"/"zero cost".
    """
    if amount is None or not currency:
        return None

    rate = USD_RATES.get(currency.strip().upper())
    if rate is None:
        print(f"WARNING: no USD rate for currency '{currency}' — cannot convert.")
        return None

    return round(amount * rate, 2)