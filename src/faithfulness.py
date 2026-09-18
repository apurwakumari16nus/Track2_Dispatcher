"""Numerical evidence membership, separate from decision correctness.

Trust only candidates, ineligible (eligibility tool results), and tool_outputs.
Never whitelist numbers from the explanation, reason_chosen, timestamps, raw
LLM extraction or constraints. Dates and digit-bearing IDs are atomic: W2 does
not authorize a claim of 2 days, and a date does not authorize its year as money.
Decimal spelling/group separators/currency symbols are normalized; percentages
map to fractions. No rounding tolerance is applied. This checks numerical
support, not units, relationships, names without digits, omissions, or truth:
using the wrong candidate's real number can still pass. Use fixed templates.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_TOKEN = re.compile(
    r"(?<!\w)(?:\d{4}-\d{2}-\d{2}(?!\d)"
    + r"|\d{4}/\d{1,2}/\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    + rf"|{_MONTH}\s+\d{{1,2}}(?:,?\s+\d{{4}})?"
    + rf"|\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?"
    + r"|[A-Za-z][A-Za-z_]*-?\d+(?:[-_][A-Za-z0-9]+)*"
    + r"|[+\-−]?(?:[$£€]\s*)?[+\-−]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?%?)",
    re.IGNORECASE,
)


def _tokens(text):
    return [match.group(0) for match in _TOKEN.finditer(text)]


def _canonical(token):
    # Ambiguous numeric dates are indivisible and fail closed. Do not let their
    # individual day/month/year numbers accidentally pass as other tool values.
    if re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", token):
        return ("unresolved_date", token)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        try:
            return ("date", date.fromisoformat(token).isoformat())
        except ValueError:
            return ("invalid_date", token)
    if re.search(_MONTH + r"\s|\s" + _MONTH, token, re.IGNORECASE):
        for fmt in ("%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
            try:
                return ("date", datetime.strptime(token.replace(",", ""), fmt).date().isoformat())
            except ValueError:
                pass
        return ("unresolved_date", token)
    if re.match(r"[A-Za-z]", token):
        return ("id", token.casefold())
    number = re.sub(r"[$£€,\s]", "", token).replace("−", "-")
    try:
        return ("number", Decimal(number[:-1]) / 100 if number.endswith("%") else Decimal(number))
    except InvalidOperation:
        return ("invalid_number", token)


def _evidence(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _evidence(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _evidence(item)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        if number.is_finite():
            yield ("number", number)
    elif isinstance(value, date):
        yield ("date", value.isoformat())
    elif isinstance(value, str):
        for token in _tokens(value):
            canonical = _canonical(token)
            if canonical[0] not in {"invalid_date", "unresolved_date", "invalid_number"}:
                yield canonical


def check(explanation_text, decision_record) -> dict:
    """Return JSON-ready {passed, numbers_in_text, unmatched}, in text order.

    decision_record accepts a DecisionRecord, dictionary, or its JSON string.
    Digit-bearing IDs/dates remain whole tokens in numbers_in_text. Repeated
    claims remain repeated, making unmatched entries easy to locate in prose.
    """
    import json
    if isinstance(decision_record, str):
        decision_record = json.loads(decision_record)
    elif hasattr(decision_record, "to_dict"):
        decision_record = decision_record.to_dict()
    if not isinstance(decision_record, dict):
        raise TypeError("decision_record must be a record, dict, or JSON object")
    allowed = set()
    for key in ("candidates", "ineligible", "tool_outputs"):
        allowed.update(_evidence(decision_record.get(key)))
    numbers = _tokens(explanation_text)
    unmatched = [token for token in numbers if _canonical(token) not in allowed]
    return {"passed": not unmatched, "numbers_in_text": numbers, "unmatched": unmatched}
