"""Blind keyword/regex baseline: reads one chat message into a structured dict."""
import re
from datetime import date, timedelta

TODAY = date(2026, 4, 1)
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
WEEKDAYS = {d: i for i, d in enumerate("mon tue wed thu fri sat sun".split())}

PLACE = r"\b(send|sending|place|put|dispatch|outsource|subcon\w*|allocate|assign|farm|push|ship|move|route|book|give|hand|get .{0,12} (done|made)|can you take|pls take|take)\b"
AVOID = r"\b(not|avoid|except|exclude|excluding|without|no|never|skip|anyone but|anywhere but|dont|don't|do not|nt)\b"
USE = r"\b(use|using|go with|goes? to|send to|send it to|to|via|at|with|only|must|has to|put (it )?(in|at|with))\b"
INFO = r"\b(who is|what is|what's|whats|how (much|many|long)|why|when did|status|where is|which (customer|colou?r)|colou?r|fabric|yarn|price quote|invoice|payment|supplier|stock|inventory|salary|weather|address|phone)\b"
CHEAP = r"\b(cheap\w*|lowest cost|least expensive|budget|save money|cost)\b"
QUAL = r"\b(quality|defect\w*|best work|careful|clean|no mistakes|least defects?|accurate|fussy|premium)\b"
FAST = r"\b(fast\w*|quick\w*|asap|urgent\w*|rush\w*|speed\w*|soonest|earliest|hurry)\b"


def _alias(workshops):
    out = {}
    for wid, w in workshops.items():
        n = w.name.lower()
        for a in {n, n.replace(" ", ""), wid.lower(), n.split()[0] if " " in n else n}:
            out[a] = wid
    out.update({"quick stitch": "W1", "steady hands": "W2", "budget works": "W3",
                "giant weave": "W5", "nimble": "W6", "old mill": "W7", "fresh start": "W8",
                "little loom": "W4", "loom": "W4", "steady": "W2", "giant": "W5"})
    return {k: v for k, v in out.items() if v in workshops}


def _date(t):
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    mon = "|".join(MONTHS)
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({mon})[a-z]*\b", t) or None
    if m:
        return date(2026, MONTHS[m[2]], int(m[1]))
    m = re.search(rf"\b({mon})[a-z]*\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", t)
    if m:
        return date(2026, MONTHS[m[1]], int(m[2]))
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
    if m:  # assume day/month
        return date(2026, int(m[2]), int(m[1]))
    m = re.search(r"\bin (\d+) days?\b", t)
    if m:
        return TODAY + timedelta(days=int(m[1]))
    if "tomorrow" in t or "tmr" in t:
        return TODAY + timedelta(days=1)
    m = re.search(r"\b(?:by|before|on|due)\s+(?:next\s+)?(mon|tue|wed|thu|fri|sat|sun)", t)
    if m:
        d = (WEEKDAYS[m[1]] - TODAY.weekday()) % 7 or 7
        return TODAY + timedelta(days=d)
    return None


def read(text, orders, workshops):
    t = text.lower()
    res = {"behaviour": "clarify", "order_id": None, "due_date": None,
           "exclude": [], "named": [], "preference": None}
    ids = set(orders["order_id"])
    m = re.search(r"\bord[-_ #]*0*(\d{1,3})\b", t)
    if m:
        oid = f"ORD-{int(m[1]):03d}"
        res["order_id"] = oid
        if oid not in ids:
            res["behaviour"] = "decline"
            return res
    res["due_date"] = _date(t)
    for alias, wid in sorted(_alias(workshops).items(), key=lambda x: -len(x[0])):
        for hit in re.finditer(rf"\b{re.escape(alias)}\b", t):
            before = t[max(0, hit.start() - 30):hit.start()]
            bucket = "exclude" if re.search(AVOID, before) else "named"
            if wid not in res["exclude"] and wid not in res["named"]:
                res[bucket].append(wid)
    for key, pat in (("cheapest", CHEAP), ("lowest_defect", QUAL), ("fastest", FAST)):
        if re.search(pat, t):
            res["preference"] = key
            break
    if re.search(r"\b(ask|confirm|check with|not sure|unsure|tbc|tbd|maybe|\?)", t) and res["due_date"]:
        res["due_date"] = res["due_date"]  # stated date kept; hedging handled below
        hedged = True
    else:
        hedged = False
    placing = bool(re.search(PLACE, t)) or bool(res["named"]) or bool(res["preference"])
    if re.search(INFO, t) and not re.search(PLACE, t):
        res["behaviour"] = "decline"
    elif res["order_id"] and (placing or res["exclude"]) and not hedged:
        res["behaviour"] = "allocate"
    elif res["order_id"] and not placing and not hedged and len(t.split()) <= 4:
        res["behaviour"] = "allocate"
    elif not res["order_id"] and not placing:
        res["behaviour"] = "decline" if "?" in t else "clarify"
    return res
