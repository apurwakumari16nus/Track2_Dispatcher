"""Deterministic guards around the LLM extraction (Sprint 3).

Pure functions on the raw chat line and the extracted values. They never call
the model and never decide a workshop; intake.py applies them as post-checks
and logs each outcome. Built against the red-team set (data/redteam_requests.txt).

- Grounding: a name, ID or quantity the LLM returns must be traceable to the
  message. An untraceable value is dropped, so the request is asked about
  rather than resolved from something the sender never said.
- Order references: 'ORD45', 'ord 041' and '041' are read as ORD-045 / ORD-041;
  two or more distinct references mean several orders in one message.
- Close matches: an unknown order ID or workshop name gets suggestions for the
  dispatcher to confirm. A suggestion is never applied on its own.
- Units: dozens are converted here ('50 dz' is 600 pieces), not by the LLM.
"""

from __future__ import annotations

from difflib import SequenceMatcher, get_close_matches
import re

MAX_MESSAGE_CHARS = 1000

_ORDER_REF = re.compile(r"\bord[\s#-]*(\d{1,4})\b", re.IGNORECASE)
_ORDER_VALUE = re.compile(r"^\s*(?:ord)?[\s#-]*(\d{1,4})\s*$", re.IGNORECASE)
_DOZEN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:dz|doz|dozens?)\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(k)?(?![\w.])", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")


def _canonical(digits: str) -> str:
    return f"ORD-{int(digits):03d}"


def normalize_order_id(value: str | None) -> str | None:
    """'ORD45', 'ord 041', '041' and 'ORD-045' all read as ORD-045; anything else is None."""
    if not value:
        return None
    match = _ORDER_VALUE.match(value)
    return _canonical(match[1]) if match else None


def order_refs(message: str) -> list[str]:
    """Distinct order references written in the message, canonical form, in order of appearance."""
    return list(dict.fromkeys(_canonical(m[1]) for m in _ORDER_REF.finditer(message)))


def _one_slip(a: str, b: str) -> bool:
    """True if b is a with one character added, dropped, or two neighbours swapped.

    A changed digit is not a slip: ORD-999 and ORD-099 are both valid-looking IDs,
    so suggesting one for the other would be a guess.
    """
    if len(a) == len(b) + 1:
        a, b = b, a
    if len(b) == len(a) + 1:
        return any(b[:i] + b[i + 1:] == a for i in range(len(b)))
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    return False


def close_order_ids(value: str, known_ids, limit: int = 3) -> list[str]:
    """Existing order IDs one typing slip away from an unknown one (ORD-0455 -> ORD-045, ORD-055)."""
    written = value.strip().upper()
    return sorted(k for k in known_ids if _one_slip(written, k.upper()))[:limit]


def close_workshop(reference: str, workshops) -> str | None:
    """The one workshop whose name or ID a misspelt reference most likely means, or None."""
    names = {w.name.casefold(): w.workshop_id for w in workshops.values()}
    match = get_close_matches(reference.strip().casefold(), list(names), n=2, cutoff=0.8)
    return names[match[0]] if len(match) == 1 else None


def dozen_pieces(message: str) -> int | None:
    """Pieces from a single dozen quantity ('50 dz', '12.5 dozen'); None if absent, repeated or fractional."""
    found = {float(m[1]) * 12 for m in _DOZEN.finditer(message)}
    if len(found) != 1:
        return None
    pieces = found.pop()
    return int(pieces) if pieces.is_integer() and pieces > 0 else None


def numbers_in(message: str) -> set[int]:
    """Whole numbers written in the message, including '1,500' and '1.5k'."""
    out = set()
    for digits, thousand in _NUMBER.findall(message):
        value = float(digits.replace(",", "")) * (1000 if thousand else 1)
        if value.is_integer():
            out.add(int(value))
    return out


def _words(text: str) -> list[str]:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)   # UrbanThread -> Urban Thread
    return _WORD.findall(spaced.casefold())


def grounded_name(value: str, message: str) -> bool:
    """True if a customer, product or workshop name can be traced to words in the message.

    Accepts the name itself, plurals and small typos ('polos' for Polo shirt,
    'Urbn Thread' for UrbanThread) and initials ('HK' for Harbor Knits).
    """
    tokens = _words(message)
    words = [w for w in _words(value) if len(w) >= 2 and w not in {"and", "co"}]
    if not words:
        return True
    if len(words) >= 2 and "".join(w[0] for w in words) in tokens:
        return True
    for word in words:
        for token in tokens:
            if len(token) < 3:
                continue
            if token.startswith(word[:4]) or word.startswith(token) or SequenceMatcher(None, word, token).ratio() >= 0.75:
                return True
    return False


def grounded_order_id(value: str, message: str) -> bool:
    """True if the order ID is written in the message, in any of the forms normalize_order_id reads."""
    return normalize_order_id(value) in order_refs(message) or value.strip().casefold() in message.casefold()


def grounded_pieces(pieces: int, message: str) -> bool:
    """True if the quantity is written in the message, directly or as dozens."""
    return pieces in numbers_in(message) or pieces == dozen_pieces(message)
