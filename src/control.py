"""Everything the phone and the group chat can do, in one place.

The iPhone app (through api.py) and the Telegram bot both call this class, so a
batch confirmed on one shows up on the other and every action lands in the same
logs. The roles do not change: the model reads, Python decides, a person approves.
Nothing here allocates on its own, and every outbound message is a fixed template
filled from the record, so no message can state a number the record does not hold.

Telegram is how the outside world reaches the desk: workshops and clients stay in
the app they already use and never install anything. The phone is the dispatcher's
side of the same conversations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import re
import threading
import time

import pandas as pd

import batches
import desk
import faithfulness
import guardrails
import hearing
import inbox_store
import intake
import languages
from objectives import PRESETS
import ops
import partners
import recovery
import rehearsal
import tools
from ui import explain

BRIEF = re.compile(r"\b(brief me|what needs me|what do i need|what'?s (?:going on|happening|up)|today'?s (?:brief|summary)|how are we doing|morning brief)\b", re.I)
SEND_WORDS = r"(?:tell|message|text|ask|remind|chase|ping|let|send)"
TELL = re.compile(rf"^\s*(?:please\s+|can you\s+|hey\s+)?{SEND_WORDS}\b", re.I)
ARRIVED = re.compile(r"\b(received|came back|come back|arrived|is back|are back|got back|mark .* (?:received|back))\b", re.I)
WHERE = re.compile(r"\b(where(?:'s| is)?|status|how(?:'s| is)|what about|any news|update on)\b", re.I)
DUE = re.compile(r"\b(what(?:'s| is)?|which|anything).{0,20}\b(due|coming back|back today|back tomorrow|overdue)\b", re.I)
SPOKEN_ORDER = re.compile(r"\b(?:o\.?\s?r\.?\s?d\.?|order)(?:\s+(?:number|no\.?))?[\s#-]*(\d{1,4})\b", re.I)
SPOKEN_REQUEST = re.compile(r"\b(pieces?|pcs|hoodies|vests|scarves|beanies|cardigans|sweaters?|shirts?|due|back by|needs? a home|send|farm out|allocate|dispatch)\b", re.I)

SPOKEN_PIECES = re.compile(r"\b(\d[\d,]*)\s+(hoodies|hoodie|vests?|scar(?:f|ves)|beanies?|cardigans?|crewnecks?|sweaters?|polos?|polo shirts?)\b", re.I)
PRODUCTS = {"hood": "Hoodie", "vest": "Vest", "scar": "Scarf", "bean": "Beanie", "card": "Cardigan", "crew": "Crewneck sweater", "swea": "Crewneck sweater", "polo": "Polo shirt"}
PRIORITIES = {"Fastest": "fastest please", "Cheapest": "cheapest please", "Best quality": "lowest defects please"}
PREFERENCES = {"Fastest": "fastest", "Cheapest": "cheapest", "Best quality": "lowest_defect"}
SPOKEN_PRIORITY = (("Fastest", ("fastest", "urgent", "asap", "rush")), ("Cheapest", ("cheapest", "lowest cost")), ("Best quality", ("quality", "defect")))

SEED = ("R04", "R06", "R07", "R17", "R22", "R25", "R26", "R27")

# Rules a dispatcher can switch on. They only ask questions from fixed templates: none moves a batch or writes to a client.
AUTOMATIONS = {
    "chase_silent": ("Chase a silent workshop", "If an offer has no answer after 2 hours, send one reminder."),
    "check_due": ("Check the day before", "Ask for a status the day before a batch is booked back."),
    "morning_brief": ("Morning brief to the team", "Post the day's brief in the team's Telegram chat at 08:30."),
}
BRIEF_AT = (8, 30)
REPEAT_SECONDS = 120      # The same words again this soon are a double send, not news.


def spoken(text: str) -> str:
    """Dictation writes 'order 45' or 'ORD 045'; the desk writes ORD-045."""
    return SPOKEN_ORDER.sub(lambda m: f"ORD-{int(m[1]):03d}", text)


goods = ops.goods


def long_date(day) -> str:
    """With the year, so the number check can match it to the record exactly."""
    return explain.long_date(str(day)) if day else "n/a"


DECLINE_REASONS = ("No capacity right now", "Machine or power problem", "Cannot make this product", "Rate is too low", "Date is too tight")
PROBLEM_REASONS = ("Machine down", "Material short", "Quality problem")
ESCALATE_REASONS = ("Customer needs a decision", "No workshop meets the date", "Cost or margin", "Quality risk", "Other")


OFFER = "New job from SweaterCo: {order}, {goods}.\nNeeded back by {back}. Rate {rate} per piece, {total} in total.\nCan you take it?"


def offer_text(job, lang="en") -> str:
    return languages.say(lang, OFFER, order=job["order_id"], goods=languages.goods(lang, job, goods(job)), back=long_date(job["back"]),
                         rate=f"{job['rate']:g}", total=f"{job['pieces'] * job['rate']:,.0f}")


def offer_buttons(key: str, lang="en") -> list:
    return [[{"text": languages.say(lang, "Accept"), "data": f"j:accepts:{key}", "style": "success"},
             {"text": languages.say(lang, "Cannot take it"), "data": f"j:why:{key}", "style": "danger"}]]


def progress_buttons(key: str, stage: str, lang="en") -> list:
    steps = {"accepted": ("Started", "started"), "in_production": ("Completed", "ready"), "ready": ("Shipped", "shipped")}
    if stage not in steps:
        return []
    rows = [[{"text": languages.say(lang, steps[stage][0]), "data": f"j:{steps[stage][1]}:{key}"}]]
    return rows + [[{"text": languages.say(lang, "Report a problem"), "data": f"j:problem:{key}"}]] if stage != "ready" else rows


def job_buttons(job, lang="en") -> list:
    return offer_buttons(job["key"], lang) if job["stage"] == "offered" else progress_buttons(job["key"], job["stage"], lang)


def job_menu(action: str, job, lang="en") -> tuple[str, list] | None:
    """A question asked on the card itself, before anything is recorded. Back returns to the card's own buttons."""
    key = job["key"]
    word = lambda text, **fields: languages.say(lang, text, **fields)
    back = [[{"text": word("Back"), "data": f"j:card:{key}"}]]
    if action == "why":
        return word("Why can you not take it?"), [[{"text": word(r), "data": f"j:no{i}:{key}"}] for i, r in enumerate(DECLINE_REASONS)] + back
    if action == "problem":
        return word("What is the problem?"), [[{"text": word("Will be late"), "data": f"j:late:{key}"}]] + [[{"text": word(r), "data": f"j:fix{i}:{key}"}] for i, r in enumerate(PROBLEM_REASONS)] + back
    if action == "late":
        return word("How many days late?"), [[{"text": word("+{days} day" if n == 1 else "+{days} days", days=n), "data": f"j:late{n}:{key}"} for n in (1, 2, 3, 5)]] + back
    if action == "card":
        return "", job_buttons(job, lang)
    return None


def letter_text(job, *, was=None) -> str:
    what = f"{job['order_id']} ({goods(job)})"
    return (f"Hello {job['customer']}, an update on {what}. Because of a problem at the workshop, we now expect it back on "
            f"{long_date(job['back'])} instead of {long_date(job['due'] if was is None else was)}. "
            "We are on it and will confirm as soon as it ships. Sorry for the change.")


def facts(job) -> dict:
    return {"candidates": [{k: str(v) if isinstance(v, date) else v for k, v in {"order": job["order_id"], "pieces": job["pieces"], "back": job["back"],
                                                                                 "was": job["back_was"], "due": job["due"], "cost": job["rate"]}.items()}]}


def _short(value) -> str:
    return explain.short_date(str(value)) if value else "n/a"


class Transport:
    """No chat connected. Messages stay in the app and are marked as not delivered."""
    connected = False

    def send(self, binding, text, buttons=None) -> bool:
        return False


class Control:
    def __init__(self, *, demo=True, transport=None, source="live", partner_call=None, notifier=None, translator=None, decisions_path=None, ops_path=None, received=None):
        self.supplied, self.base, self.messages = desk.load_inputs()
        self.decisions_path = decisions_path if decisions_path is not None else (desk.REHEARSAL_LOG if demo else None)
        self.ops_path = ops_path or ops.log_path(self.decisions_path)
        self.orders = self._book()
        self.received = received
        self.transport, self.source, self.demo = transport or Transport(), source, demo
        self.config = PRESETS["lateness"]
        self.previews: dict[str, dict] = {}
        self.saved: dict = {}
        self.partner_call = partner_call
        self.notifier = notifier
        self.translator = translator
        self.arrivals = threading.Lock()

    # Shared state ----------------------------------------------------------------

    def _book(self):
        """The supplied order book, plus any order added since. The supplied file stays as it was given."""
        added = [e["order"] for e in ops.rows(self.ops_path) if e["kind"] == "order"]
        return pd.concat([self.supplied, pd.DataFrame(added)], ignore_index=True) if added else self.supplied

    def world(self) -> ops.World:
        return ops.build(self.base, self.decisions_path, self.ops_path, self.received)

    def log(self, kind, **fields) -> dict:
        return ops.append(self.ops_path, kind, **fields)

    def path_received(self):
        return self.received or batches.received_path(self.decisions_path)

    def _append(self, response):
        return desk.records.append(response, self.decisions_path)

    def language(self, party, world=None) -> str:
        return (world or self.world()).languages.get(party, "en")

    def set_language(self, party, language) -> dict:
        return self.log("language", party=party, language=language)

    def say(self, party, text, *, by, job=None, buttons=None, automatic=False, world=None, local=None) -> dict:
        """One message out: sent if that party has a chat, always kept in the thread in English. local is what the party reads."""
        binding = (world or self.world()).bindings.get(party)
        delivered = bool(binding) and self.transport.send(binding, local or text, buttons)
        return self.log("message", party=party, direction="out", author=by, text=text, channel="telegram" if delivered else "app", job=job,
                        delivered=delivered, automatic=automatic)

    def job(self, key, world=None) -> dict:
        world = world or self.world()
        if key not in world.jobs:
            raise KeyError("That batch is not on record.")
        return world.jobs[key]

    # Today ---------------------------------------------------------------------

    def waiting_requests(self, world=None) -> list[dict]:
        world = world or self.world()
        done = {e["line"] for e in world.events if e["kind"] == "request_done"}
        out = []
        for line in self.messages:
            rid, stamp, sender, body = re.match(r"(R\d+) \[(\d\d:\d\d)\] ([^:]+): (.*)", line).groups()
            if rid not in done:
                out.append({"id": rid, "time": stamp, "sender": sender, "text": body, "channel": "group chat", "line": line})
        mine = [{"id": e["id"], "time": e["at"][11:16], "sender": e["by"], "text": e["text"], "channel": "your request", "line": f"{e['by']}: {e['text']}"}
                for e in world.events if e["kind"] == "request" and e["id"] not in done]
        out[:0] = reversed(mine)
        for thread in inbox_store.threads():
            if thread["status"] in ("Received", "Needs reply", "Recommended"):
                out.append({"id": thread["id"], "time": thread["at"][11:16], "sender": thread["sender"], "text": thread["text"],
                            "channel": thread["channel"], "line": inbox_store.engine_text(thread)})
        return out

    def today(self) -> dict:
        world = self.world()
        cards = ops.attention(world)
        requests = self.waiting_requests(world)
        if requests:
            cards.append({"id": "requests:all", "rank": 6, "kind": "requests", "tone": "info",
                          "title": f"{len(requests)} request{'s' if len(requests) != 1 else ''} in review",
                          "detail": "Waiting for a decision.", "action": "Open", "target": {"type": "requests", "id": "all"}, "when": None})
        jobs = [j for j in world.jobs.values() if j["stage"] != "received"]
        counts = {k: sum(ops.health(j, world.today) == k for j in world.jobs.values()) for k in batches.STATUSES}
        coming = sorted((j for j in jobs if j["back"]), key=lambda j: j["back"])[:6]
        urgent = [c for c in cards if c["kind"] != "requests"]
        return {"today": world.today, "headline": (f"{len(urgent)} thing{'s need' if len(urgent) != 1 else ' needs'} you." if urgent else "All clear."),
                "brief": ops.brief(world), "spoken": ops.spoken_brief(world), "attention": cards, "counts": counts, "out": len(jobs), "demo": self.demo,
                "pieces_out": sum(j["pieces"] for j in jobs), "coming_back": [ops.job_view(j, world.today) for j in coming],
                "network": [ops.workshop_view(world, wid) for wid in world.base], "requests": len(requests)}

    # Speaking ------------------------------------------------------------------

    def _party_in(self, text: str, world) -> str | None:
        squeezed = re.sub(r"[^a-z0-9]", "", text.casefold())
        for wid, w in world.base.items():
            if re.sub(r"[^a-z0-9]", "", w.name.casefold()) in squeezed:
                return wid
        for customer in sorted(self.orders["customer"].dropna().unique(), key=len, reverse=True):
            if re.sub(r"[^a-z0-9]", "", customer.casefold()) in squeezed:
                return ops.CLIENT + customer
        return None

    def _job_for(self, order_id, world):
        return next((j for j in sorted(world.jobs.values(), key=lambda j: j["stage"] == "received") if j["order_id"] == order_id), None)

    def speak(self, text: str, by: str = "Dispatcher") -> dict:
        """Hindi or Chinese goes through the same path in English, and the person sees that reading on the card."""
        names = [w.name for w in self.base.values()] + sorted(self.orders["customer"].dropna().unique())
        english = partners.english(text, names, self.translator)
        card = self._speak(english or text, by)
        return {**card, "read_as": english} if english else card

    def _speak(self, text: str, by: str = "Dispatcher") -> dict:
        """One input for everything: a question, a message to someone, an arrival or a new request.

        Fixed rules route it, so routing is instant, free and testable. Only a new
        request goes to the model. Writes still wait for a person on the card.
        """
        text = spoken(text.strip())
        if not text:
            return {"card": "error", "title": "Nothing was heard", "text": "Try again, or type it instead."}
        world = self.world()
        order = (guardrails.order_refs(text) or [None])[0]
        party = self._party_in(text, world)
        job = self._job_for(order, world) if order else None
        looks_new = SPOKEN_REQUEST.search(text) and order and not job
        if BRIEF.search(text):
            return self.answer_brief(world)
        if order and job and ARRIVED.search(text):
            return {"card": "action", "action": "received", "key": job["key"], "title": f"Mark {order} received?",
                    "text": f"{goods(job)} from {job['workshop']}.", "button": "Mark received"}
        if party and TELL.search(text):
            return self.draft_for(party, text, world)
        if DUE.search(text):
            return self.answer_due(world, "tomorrow" in text.casefold())
        if order and job and WHERE.search(text):
            return self.answer_job(job, world)
        if order and WHERE.search(text) and not looks_new:
            return {"card": "answer", "title": f"{order} is not out", "text": f"{order} has not been sent to a workshop.", "items": []}
        if party and not party.startswith(ops.CLIENT) and WHERE.search(text) and not order:
            return self.answer_workshop(party, world)
        draft = None if order else self._spoken_order(text, world)
        return draft or self.evaluate(f"{by}: {text}", by=by)

    def _spoken_order(self, text, world) -> dict | None:
        """A request with everything but an order number is a new order, which the dispatcher adds with one tap. Nothing is added here."""
        found = SPOKEN_PIECES.search(text)
        due = partners.read_date(text, world.today)
        squeezed = re.sub(r"[^a-z0-9]", "", text.casefold())
        customer = next((c for c in self.orders["customer"].dropna().unique() if re.sub(r"[^a-z0-9]", "", c.casefold()) in squeezed), None)
        if not (found and due and customer):
            return None
        pieces, product = int(found[1].replace(",", "")), PRODUCTS[found[2].casefold()[:4]]
        same = self.orders[(self.orders["customer"] == customer) & (self.orders["product"] == product) & (self.orders["pieces"] == pieces) & (self.orders["status"] == "IN_PROGRESS")]
        if len(same):
            return None     # It is already in the book, so the usual reading finds it.
        lower = text.casefold()
        priority = next((name for name, words in SPOKEN_PRIORITY if any(w in lower for w in words)), None)
        return {"card": "action", "action": "new_order", "title": "Add this order?", "button": "Add and recommend",
                "text": f"{goods({'product': product, 'pieces': pieces})} for {customer}, back by {long_date(due)}. It is not in the order book yet.",
                "fields": {"customer": customer, "product": product, "pieces": pieces, "due": due, "priority": priority}}

    # Your own requests ----------------------------------------------------------

    def order_book(self) -> dict:
        """What the New request screen offers: orders with no workshop yet, and what a new order can be."""
        out = {j["order_id"] for j in self.world().jobs.values() if j["stage"] not in ("received", "declined")}
        waiting = self.orders[(self.orders["status"] == "IN_PROGRESS") & ~self.orders["order_id"].isin(out)].sort_values("due_date")
        return {"open": [{"order_id": o.order_id, "customer": o.customer, "product": o.product, "pieces": int(o.pieces), "due": str(o.due_date)[:10]} for o in waiting.itertuples()],
                "customers": sorted(self.orders["customer"].dropna().unique()), "products": sorted(self.supplied["product"].dropna().unique()),
                "priorities": ["Balanced", *PRIORITIES]}

    def add_order(self, customer, product, pieces, due, by="Dispatcher") -> dict:
        """A new order for the book. Later requests treat it exactly like a supplied one."""
        customer = (customer or "").strip()
        known = self.supplied.drop_duplicates("product").set_index("product")["category"]
        today = self.world().today
        if not customer:
            raise ValueError("Say who the order is for.")
        if product not in known.index:
            raise ValueError("Choose a product from the list.")
        if not pieces or pieces < 1:
            raise ValueError("Enter how many pieces.")
        if due is None or due <= today:
            raise ValueError("The date needs to be after today.")
        number = 1 + max(int(o.split("-")[1]) for o in self.orders["order_id"])
        order = {"order_id": f"ORD-{number:03d}", "customer": customer, "product": product, "category": known[product], "pieces": int(pieces),
                 "order_date": today.isoformat(), "due_date": due.isoformat(), "status": "IN_PROGRESS", "current_stage": "KNITTING"}
        self.log("order", order=order, by=by)
        self.orders = self._book()
        return order

    def new_request(self, *, order_id=None, customer=None, product=None, pieces=None, due=None, priority=None, note="", by="Dispatcher") -> dict:
        """Your own request. Written out as a sentence and read like any other, and it stays in review until a decision goes out."""
        if order_id:
            rows = self.orders[self.orders["order_id"] == order_id]
            if rows.empty:
                raise KeyError("That order is not in the book.")
            order = rows.iloc[0].to_dict()
        else:
            order = self.add_order(customer, product, pieces, due, by)
        when = due or date.fromisoformat(str(order["due_date"])[:10])
        wish = [PRIORITIES[priority]] if priority in PRIORITIES else []
        text = ", ".join([f"{order['order_id']}, {goods({'product': order['product'], 'pieces': int(order['pieces'])})} for {order['customer']}", f"due {long_date(when)}", *wish])
        if (note or "").strip():
            text += f". {note.strip()}"
        request = f"A{1 + sum(e['kind'] == 'request' for e in self.world().events)}"
        self.log("request", id=request, order_id=order["order_id"], text=text, by=by)
        reading = None if (note or "").strip() else self._form_reading(order, when, priority)   # A note is free text, so the model reads it.
        return self.evaluate(f"{by}: {text}", by=by, request=request, reading=reading)

    @staticmethod
    def _form_reading(order, when, priority) -> intake.LLMReply:
        """A form already holds every field, so there is nothing for the model to read. Instant and free, and every Python check still runs."""
        fields = {"request_id": None, "sender": None, "order_id": order["order_id"], "customer": order["customer"], "product": order["product"],
                  "category": order["category"], "pieces": int(order["pieces"]), "due_date_text": long_date(when), "dispatch_date_text": None,
                  "date_not_confirmed": False, "suggested_workshop": None, "excluded_workshops": [], "preference": PREFERENCES.get(priority),
                  "split_allowed": False, "is_question_only": False, "question_topic": "other", "must_make_date": False, "constraints": [],
                  "missing_fields": [], "behaviour": "allocate", "reason": "From the New request form."}
        return intake.LLMReply(json.dumps(fields), {"provider": "form", "extraction_source": "form"})

    def answer_brief(self, world) -> dict:
        cards = ops.attention(world)
        return {"card": "answer", "title": "Today", "text": ops.brief(world), "items": [{"title": c["title"], "detail": c["detail"], "target": c["target"]} for c in cards[:5]]}

    def answer_due(self, world, tomorrow=False) -> dict:
        day = ops.shift(world.today, 1) if tomorrow else world.today
        jobs = [j for j in ops.open_jobs(world) if j["back"] and j["back"] <= day]
        word = "tomorrow" if tomorrow else "today"
        text = (f"{len(jobs)} batch{'es are' if len(jobs) != 1 else ' is'} due back by {word}." if jobs else f"Nothing is due back by {word}.")
        return {"card": "answer", "title": f"Due back by {word}", "text": text,
                "items": [{"title": f"{j['order_id']} at {j['workshop']}", "detail": f"Back {_short(j['back'])}, {j['pieces']:,} pieces",
                           "target": {"type": "job", "id": j["key"]}} for j in jobs]}

    def answer_job(self, job, world) -> dict:
        view = ops.job_view(job, world.today)
        spare = view["days_to_spare"]
        lead = f"{job['order_id']} is at {job['workshop']}: {view['stage_label'].lower()}."
        back = f" Back {_short(job['back'])}" + (f", {explain.days(spare)} to spare." if spare is not None and spare >= 0 else
                                                 f", {explain.days(-spare)} late." if spare is not None else ".")
        return {"card": "answer", "title": job["order_id"], "text": lead + back,
                "items": [{"title": "Open batch", "detail": view["health_label"], "target": {"type": "job", "id": job["key"]}}]}

    def answer_workshop(self, wid, world) -> dict:
        view = ops.workshop_view(world, wid)
        state = "is working" if view["status"] == "ACTIVE" else "is closed"
        text = f"{view['name']} {state}. {view['open_jobs']} open batch{'es' if view['open_jobs'] != 1 else ''}, {view['queue_days']:.1f} days of queue."
        return {"card": "answer", "title": view["name"], "text": text, "items": [{"title": "Open workshop", "detail": "", "target": {"type": "workshop", "id": wid}}]}

    def draft_for(self, party, text, world) -> dict:
        """'Tell QuickStitch we need it by Friday' becomes a message for review: the words after the name, unchanged."""
        name = ops.party_name(party, world.workshops)
        body = re.sub(rf"^\s*(?:please\s+|can you\s+|hey\s+)?{SEND_WORDS}\s+(?:to\s+)?", "", text, flags=re.I)
        body = re.sub(r"\s*".join(re.escape(c) for c in name.replace(" ", "")), "", body, count=1, flags=re.I).strip(" ,.:") or text
        body = re.sub(r"^(?:that|to)\s+", "", body, flags=re.I)
        return {"card": "draft", "party": party, "name": name, "text": body[:1].upper() + body[1:], "connected": party in world.bindings}

    # Deciding ------------------------------------------------------------------

    def evaluate(self, message: str, *, by="Dispatcher", answers=None, request=None, reading=None) -> dict:
        world = self.world()
        source = "fixture" if message in self.messages else self.source
        started = time.perf_counter()
        call = (lambda prompt, text: reading) if reading else rehearsal.make_source(source, record_live=False)
        try:
            with intake.extraction_source(call):
                preview = desk.make_preview(message, world.today, self.config, self.orders, world.workshops, world.queues, world.allocator,
                                            0, source, answers)
        except Exception as error:
            title, action, retry = intake.ERROR_CATEGORIES.get(getattr(error, "category", None), ("The request was not processed", "Try again.", True))
            return {"card": "error", "title": title, "text": f"{action} Nothing was allocated.", "retry": retry}
        self.previews[preview.token] = {"preview": preview, "message": message, "answers": dict(answers or {}), "request": request, "by": by}
        return {**self.decision_card(preview, world), "seconds": round(time.perf_counter() - started, 1)}

    def decision_card(self, preview, world) -> dict:
        response = preview.response
        parsed, record = response.parsed_request, response.decision_record
        base = {"token": preview.token, "order_id": parsed.order_id, "customer": parsed.customer, "product": parsed.product, "pieces": parsed.pieces,
                "due": parsed.due_date, "reading": (parsed.llm_metadata or {}).get("extraction_source", preview.source),
                "model": intake.model_label((parsed.llm_metadata or {}).get("model")) if (parsed.llm_metadata or {}).get("model") else None,
                "checks_passed": sum(1 for c in parsed.post_checks if c.get("result") != "failed"), "checks": len(parsed.post_checks)}
        if parsed.behaviour == "clarify":
            prompt = explain.clarify_prompt(parsed.to_dict(), record.get("tool_outputs", {}).get("order_options", []))
            options = [{"label": f"{o['order_id']}, {o['product']}, {o['pieces']:,}", "field": "order_id", "value": o["order_id"]} for o in prompt["options"][:6]]
            suggested = record.get("tool_outputs", {}).get("order_suggestions") or []
            row = self.orders[self.orders["order_id"] == parsed.order_id]
            if parsed.order_id and (parsed.date_not_confirmed or parsed.due_date is None) and len(row):
                on_file = str(row.iloc[0]["due_date"])[:10]
                options.append({"label": f"Keep {_short(on_file)}, the date on file", "field": "due_date", "value": on_file})
            return {**base, "card": "clarify", "question": prompt["question"], "missing": prompt["missing"], "options": options, "suggested": suggested}
        chosen = explain.chosen_row(record)
        if parsed.behaviour == "decline" or chosen is None:
            reason = ("That order is not in the order book." if parsed.reason == "order not found"
                      else "That information is not in the supplied data." if parsed.behaviour == "decline"
                      else "No active workshop can take this batch as one job.")
            return {**base, "card": "cannot", "title": "Cannot act on this", "text": f"{reason} Nothing was allocated."}
        won = explain.why_won(record)
        other = explain.runner_up(record)
        named = world.workshops[parsed.suggested_workshop].name if parsed.suggested_workshop in world.workshops else "The named workshop"
        awkward = record.get("awkward_case") == "none_makes_date"
        headline = (f"No workshop makes {_short(parsed.due_date)}" if awkward else f"{named} cannot take it" if parsed.behaviour == "refuse" else "Recommended")

        def option(row):
            return {"workshop_id": row["workshop_id"], "name": row["name"], "back": row["eta_date"], "days_to_spare": row["days_to_spare"], "total_days": round(row["total_days"], 1),
                    "total_cost": row["total_cost"], "cost_per_piece": row["cost_per_piece"], "defect": row["expected_defect_rate"]}

        warnings = [line for line in response.explanation_text.splitlines() if line.startswith(("DATE CHECK", "ALREADY LATE"))]
        held = self.holder(parsed.order_id, world, preview.token)
        block = f"{parsed.order_id} is already with {held['workshop']}." if held else preview.block_reason
        if held:
            headline, awkward = "Already sent", True
        return {**base, "card": "recommendation", "headline": headline, "awkward": awkward, "chosen": option(chosen), "runner_up": option(other) if other else None,
                "why": won["sentence"] if won else record["reason_chosen"], "metrics": explain.deciding_metrics(record, chosen, other) if other else [],
                "options": [option(c) for c in explain.selection_order(record)], "warnings": warnings, "can_confirm": block is None,
                "block_reason": block, "override_reasons": list(desk.OVERRIDE_REASONS), "escalate_reasons": list(ESCALATE_REASONS), "numbers_verified": bool((response.faithfulness or {}).get("passed"))}

    def _stored(self, token):
        if token not in self.previews:
            raise KeyError("This recommendation has expired. Run it again.")
        return self.previews[token]

    def _current(self, stored, world):
        return desk.signature(stored["message"], world.today, self.config, self.orders, world.workshops, world.queues, 0, stored["preview"].source, stored["answers"])

    def answer(self, token, field_name, value, by="Dispatcher") -> dict:
        stored = self._stored(token)
        answers = {**stored["answers"], field_name: {"value": value, "at": ops.now()}}
        return self.evaluate(stored["message"], by=by, answers=answers, request=stored["request"])

    def _after_confirm(self, stored, record, by):
        """The request is dealt with, and so is any waiting chat line for the same order, so it cannot be booked twice."""
        order = stored["preview"].response.parsed_request.order_id
        same = [r["id"] for r in self.waiting_requests() if order and r["channel"] in ("group chat", "your request") and order in r["text"]]
        for line in dict.fromkeys(filter(None, [stored["request"], *same])):
            self.log("request_done", line=line, by=by)

    def holder(self, order, world, token=None) -> dict | None:
        """The live batch for this order, if a different decision already sent it. Pressing confirm twice on one card is harmless."""
        return next((j for key, j in world.jobs.items() if order and j["order_id"] == order and j["stage"] not in ("received", "declined")
                     and not key.startswith(f"{token}:")), None)

    def _not_already_out(self, stored, world) -> None:
        preview = stored["preview"]
        order = preview.response.parsed_request.order_id
        held = self.holder(order, world, preview.token)
        if held:
            raise ValueError(f"{order} is already with {held['workshop']}.")

    def confirm(self, token, by="Dispatcher") -> dict:
        """The person's approval. Writes the decision once, then the job goes to the workshop."""
        stored = self._stored(token)
        preview, world = stored["preview"], self.world()
        self._not_already_out(stored, world)
        row = desk.confirm_preview(preview, self._current(stored, world), self.saved, append=self._append, guided_demo=self.demo, channel="app", by=by)
        self._after_confirm(stored, row, by)
        key = f"{preview.token}:{row['decision_record']['chosen_workshop']}"
        self.offer(key, by)
        return {"card": "confirmed", "key": key, "job": ops.job_view(self.job(key), self.world().today)}

    def override(self, token, workshop_id, reason, note="", by="Dispatcher") -> dict:
        stored = self._stored(token)
        preview, world = stored["preview"], self.world()
        self._not_already_out(stored, world)
        row, _, _ = desk.confirm_override(preview, self._current(stored, world), self.saved, workshop_id, reason, note, world.workshops, world.queues,
                                          world.allocator, append=self._append, guided_demo=self.demo, channel="app", by=by)
        self._after_confirm(stored, row, by)
        key = f"{preview.token}:{workshop_id}"
        self.offer(key, by)
        return {"card": "confirmed", "key": key, "job": ops.job_view(self.job(key), self.world().today)}

    def split_option(self, token) -> dict:
        """One workshop against the fastest two. Python's estimate only: nothing is allocated until confirm_split."""
        stored = self._stored(token)
        response, world = stored["preview"].response, self.world()
        parsed, record = response.parsed_request, response.decision_record
        chosen = explain.chosen_row(record)
        batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category, "due_date": parsed.due_date, "sent_date": world.today}
        try:
            split = tools.estimate_split(batch, world.workshops, world.queues, world.today, record["constraints_applied"]["exclude"], record["chosen_workshop"])
        except ValueError as error:
            split = {"available": False, "reason": str(error)}
        stored["split"] = split
        single = {"name": chosen["name"], "back": chosen["eta_date"], "cost": chosen["total_cost"], "defect": chosen["expected_defect_rate"]}
        if not split.get("available"):
            return {"available": False, "reason": split.get("reason") or "No two workshops can share this batch.", "single": single}
        return {"available": True, "single": single, "parts": [{"name": p["name"], "pieces": p["pieces"], "back": p["eta_date"]} for p in split["parts"]],
                "back": split["eta_date"], "cost": split["total_cost"], "defect": desk.split_defect_rate(split, world.workshops),
                "saves_days": round(max(0.0, chosen["total_days"] - split["total_days"]), 1)}

    def confirm_split(self, token, by="Dispatcher") -> dict:
        stored = self._stored(token)
        preview, world = stored["preview"], self.world()
        self._not_already_out(stored, world)
        if not (stored.get("split") or {}).get("available"):
            raise ValueError("No two-workshop split is ready for this request.")
        row, _, _ = desk.confirm_split(preview, self._current(stored, world), self.saved, stored["split"], world.workshops, world.queues, world.allocator,
                                       append=self._append, guided_demo=self.demo, channel="app", by=by)
        self._after_confirm(stored, row, by)
        keys = [f"{preview.token}:{part['workshop_id']}" for part in stored["split"]["parts"]]
        for key in keys:
            self.offer(key, by)
        return {"card": "confirmed", "key": keys[0], "job": ops.job_view(self.job(keys[0]), self.world().today)}

    def escalate(self, token, reason, note="", by="Dispatcher") -> dict:
        if reason not in ESCALATE_REASONS:
            raise ValueError("Pick a reason for the escalation.")
        if reason == "Other" and not note.strip():
            raise ValueError("Add a short note when the reason is Other.")
        stored = self._stored(token)
        said = ". ".join(filter(None, [reason, note.strip()]))
        desk.escalate(stored["preview"], "Planner", said, append=self._append, guided_demo=self.demo, channel="app", by=by)
        if stored["request"]:
            self.log("request_done", line=stored["request"], by=by)
        self.alert(f"{by} escalated {stored['preview'].response.parsed_request.order_id or 'a request'} to the planner: {said}. Nothing was allocated.")
        return {"card": "escalated"}

    # The loop with workshops ------------------------------------------------------

    def offer(self, key, by="Dispatcher") -> dict:
        world = self.world()
        job = self.job(key, world)
        lang = self.language(job["workshop_id"], world)
        message = self.say(job["workshop_id"], offer_text(job), by=by, job=key, buttons=offer_buttons(key, lang), world=world, local=offer_text(job, lang))
        self.log("offer", job=key, on=world.today, by=by)
        return message

    def chase(self, key, by="Dispatcher", automatic=False, reason=None) -> dict:
        world = self.world()
        job = self.job(key, world)
        lang = self.language(job["workshop_id"], world)
        if job["stage"] == "offered":
            wording, fields = "A reminder about {order}, {goods}. Can you take it? We need to plan today.", {"order": job["order_id"], "goods": goods(job)}
            local = languages.say(lang, wording, order=job["order_id"], goods=languages.goods(lang, job, goods(job)))
            buttons = offer_buttons(key, lang)
        else:
            wording, fields = "How is {order} looking? It is booked back on {back}.", {"order": job["order_id"], "back": long_date(job["back"])}
            local = languages.say(lang, wording, **fields)
            buttons = None
        message = self.say(job["workshop_id"], wording.format(**fields), by=by, job=key, buttons=buttons, automatic=automatic, world=world, local=local)
        self.log("reminder", job=key, on=world.today, by=by, reason=reason)
        return message

    def set_stage(self, key, stage, *, by, detail="", world=None, quiet=False) -> None:
        world = world or self.world()
        self.log("stage", job=key, stage=stage, on=world.today, by=by, detail=detail)
        if not quiet:
            self._tell_team(self.job(key, world), stage)

    def _tell_team(self, job, stage) -> None:
        """The team chat follows the work without opening the app. Problems arrive separately, as plans to approve."""
        name, order = job["workshop"], job["order_id"]
        if stage == "accepted":
            self.alert(f"{name} accepted {order}, {goods(job)}. Back by {long_date(job['back'])}.")
        elif stage == "ready":
            self.alert(f"{name} completed {order}, {goods(job)}. {self._room(job['workshop_id'])}")
        elif stage == "shipped":
            self.alert(f"{name} shipped {order}, {goods(job)}.")

    def _room(self, workshop_id) -> str:
        days = self.world().queues.get(workshop_id, 0.0)
        return "It is free for new work now." if days < 0.05 else f"It has room again: {days:.1f} days of work left."

    def mark_received(self, key, by="Dispatcher") -> dict:
        world = self.world()
        job = self.job(key, world)
        if job["received"]:
            return ops.job_view(job, world.today)
        batches.record_arrival(key, by=by, scenario_date=world.today, path=self.path_received())
        return ops.job_view(self.job(key), world.today)

    def job_tap(self, action, key, by, channel="telegram", reason=None) -> str:
        """A workshop tapped a button on a job card. A tap is unambiguous, so it needs no reading."""
        world = self.world()
        job = self.job(key, world)
        name = world.base[job["workshop_id"]].name
        roleplay = channel == "roleplay"
        lang = self.language(job["workshop_id"], world)
        if action.startswith("fix"):
            return self._problem(world, job, PROBLEM_REASONS[int(action[3:])], by, channel)
        if action.startswith("late"):
            days = int(action[4:])
            self.log("message", party=job["workshop_id"], direction="in", author=by, text=f"Will be {explain.days(days)} late ({job['order_id']})", channel=channel, job=key, tapped=True)
            self.open_incident(world, job["workshop_id"], "delay", f"{name} says {job['order_id']} comes back {explain.days(days)} later", {},
                               jobs=[job], delay_days=days)
            return languages.say(self.language(job["workshop_id"], world), "{order}: thank you, the team has been told it is {days} days late.", order=job["order_id"], days=days)
        if action.startswith("no"):
            action, reason = "declines", DECLINE_REASONS[int(action[2:])]
        stage = "declined" if action == "declines" else partners.PROGRESS[action]
        self.set_stage(key, stage, by=by, detail=reason or ("Role-play tap" if roleplay else "Tapped in Telegram"), world=world, quiet=roleplay)
        said = f"{ops.STAGES[stage]} ({job['order_id']})" + (f": {reason}" if reason else "")
        self.log("message", party=job["workshop_id"], direction="in", author=by, text=said, channel=channel, job=key, tapped=True)
        if stage == "declined":
            self.open_incident(world, job["workshop_id"], "declined", f"{name} cannot take {job['order_id']}", {"reason": reason}, jobs=[job])
            return languages.say(lang, "{order}: declined, reason noted. Thank you, {name}.", order=job["order_id"], name=name)
        if stage == "ready":
            days = self.world().queues.get(job["workshop_id"], 0.0)
            if days < 0.05:
                return languages.say(lang, "{order}: completed. Thank you, {name}. You are free for new work now.", order=job["order_id"], name=name)
            return languages.say(lang, "{order}: completed. Thank you, {name}. You have room again: {days} days of work left.", order=job["order_id"], name=name, days=f"{days:.1f}")
        label = ops.STAGES[stage] if lang != "en" else ops.STAGES[stage].lower()
        return languages.say(lang, "{order}: {stage}. Thank you, {name}.", order=job["order_id"], stage=label, name=name)

    def _problem(self, world, job, reason, by, channel) -> str:
        """A workshop raising something the job card has no step for. The batch stays where it is until the dispatcher decides."""
        party, order = job["workshop_id"], job["order_id"]
        self.log("message", party=party, direction="in", author=by, text=f"Problem with {order}: {reason}", channel=channel, job=job["key"], tapped=True)
        self.open_incident(world, party, "problem", f"{world.base[party].name} reports a problem with {order}", {"reason": reason}, jobs=[job])
        return languages.say(self.language(party, world), "{order}: thank you, the team has been told: {reason}.", order=order, reason=reason)

    def inbound(self, party, text, *, by=None, channel="telegram") -> dict:
        """A workshop or client wrote something. Read it, check it, and do only what its kind allows."""
        with self.arrivals:
            world = self.world()
            last = (world.threads.get(party) or [None])[-1]
            if last and last["direction"] == "in" and last["text"] == text and ops.age_seconds(last["at"]) < REPEAT_SECONDS:
                return last["reading"] or {"kind": "repeat"}     # No second reading to pay for, and no second incident.
            message = self.log("message", party=party, direction="in", author=by or ops.party_name(party, world.workshops), text=text, channel=channel)
        client = party.startswith(ops.CLIENT)
        held = ([j for j in world.jobs.values() if j["customer"] == party[len(ops.CLIENT):] and j["stage"] != "received"] if client
                else ops.open_jobs(world, party))
        reading = partners.read(text, role="client" if client else "partner workshop", today=world.today,
                                order_ids=sorted({j["order_id"] for j in held if j["order_id"]}), call=self.partner_call)
        self.log("reading", message=message["id"], reading=reading)
        if reading.get("needs_person"):
            self.alert(f"{ops.party_name(party, world.workshops)} needs an answer: {text[:200]}", world=world)
        return self._act(world, party, reading, held, client)

    def alert(self, text, buttons=None, world=None) -> bool:
        """The team's Telegram chat, and a phone alert, are how the desk reaches the dispatcher when the app is closed."""
        if self.notifier:
            self.notifier(text)
        binding = (world or self.world()).bindings.get(ops.TEAM)
        return bool(binding) and self.transport.send(binding, text, buttons)

    def own_work(self, party) -> str:
        """/jobs or /status in a workshop's or a client's chat. Only their own work, and a client never sees who is sewing it."""
        world = self.world()
        client = party.startswith(ops.CLIENT)
        jobs = [j for j in world.jobs.values() if j["stage"] != "received" and (j["customer"] == party[len(ops.CLIENT):] if client else j["workshop_id"] == party)]
        if not jobs:
            return "Nothing open right now."
        lines = [f"{j['order_id']}, {goods(j)}\n{ops.stage_line(j)}\nBack {long_date(j['back'])}" for j in sorted(jobs, key=lambda j: j["back"] or world.today)]
        return "\n\n".join(lines)

    def own_cards(self, party) -> list:
        """/jobs in a workshop's chat: each open batch on its own card, with the next step to tap."""
        world = self.world()
        jobs = sorted((j for j in world.jobs.values() if j["stage"] not in ("received", "declined") and j["workshop_id"] == party), key=lambda j: j["back"] or world.today)
        lang = self.language(party, world)
        return [(f"{j['order_id']}, {languages.goods(lang, j, goods(j))}. {long_date(j['back'])}\n\n{ops.stage_line(j, lang)}" if lang != "en"
                 else f"{j['order_id']}, {goods(j)}. Back {long_date(j['back'])}.\n\n{ops.stage_line(j)}", job_buttons(j, lang)) for j in jobs]

    def own_summary(self, party) -> str:
        view = ops.workshop_view(self.world(), party)
        return f"{view['name']}: {view['open_jobs']} batch{'es' if view['open_jobs'] != 1 else ''} in hand, {view['queue_days']:.1f} days of work booked."

    def _ask(self, party, text, world) -> None:
        self.say(party, text, by="Threadline", automatic=True, world=world)

    def _act(self, world, party, reading, held, client) -> dict:
        kind = reading["kind"]
        job = next((j for j in held if j["order_id"] == reading["order_id"]), None) or (held[0] if len(held) == 1 else None)
        if client:
            if kind == "agrees" and job:
                self.log("stage", job=job["key"], stage=job["stage"], on=world.today, by=ops.party_name(party, world.workshops), detail="Client agreed to the new date")
            return reading
        name = world.base[party].name
        if kind in partners.PROGRESS or kind == "declines":
            if job is None:
                if held:
                    self._ask(party, "Which order is that? " + ", ".join(j["order_id"] for j in held), world)
                return reading
            stage = "declined" if kind == "declines" else partners.PROGRESS[kind]
            self.set_stage(job["key"], stage, by=name, detail=reading.get("reason") or "", world=world)
            if kind == "accepts":
                self._ask(party, f"Thank you. {job['order_id']} is confirmed with you, back by {long_date(job['back'])}.", world)
            if kind == "declines":
                self.open_incident(world, party, "declined", f"{name} cannot take {job['order_id']}", reading, jobs=[job])
            return reading
        if kind == "closed":
            until = reading["date"]
            self.open_incident(world, party, "closed", f"{name} reports closed" + (f" until {_short(until)}" if until else ""), reading, jobs=held,
                               changes={"status": "SUSPENDED"}, until=until, label=f"Closed until {_short(until)}" if until else "Closed")
            if not until:
                self._ask(party, "Sorry to hear that. When do you expect to reopen?", world)
        elif kind == "reopened":
            self.open_incident(world, party, "reopened", f"{name} says it is working again", reading, changes={"status": "ACTIVE"}, label="Working again")
        elif kind == "delay":
            if job is None:
                self._ask(party, "Which order is delayed? " + ", ".join(j["order_id"] for j in held), world)
                return {**reading, "needs_person": False}
            back = reading["date"]
            days = reading["delay_days"]
            if not back and not days:
                self._ask(party, f"What date can you return {job['order_id']}?", world)
                return reading
            when = _short(back) if back else f"{explain.days(days)} later"
            self.open_incident(world, party, "delay", f"{name} says {job['order_id']} comes back {when if back is None else 'on ' + when}", reading, jobs=[job], back=back, delay_days=days)
        elif kind == "capacity_change":
            if reading["capacity_per_day"]:
                value = reading["capacity_per_day"]
                self.open_incident(world, party, "capacity", f"{name} says it can now do {value:,} a day", reading, jobs=held, changes={"capacity": value}, label=f"{value:,} a day")
            else:
                self._ask(party, "Thanks for telling us. How many pieces a day can you do for now?", world)
        elif kind == "price_change":
            if reading["price_per_piece"]:
                value = reading["price_per_piece"]
                self.open_incident(world, party, "price", f"{name} says its rate is now {value:g} per piece", reading, changes={"cost": value}, label=f"Rate {value:g}")
            else:
                self._ask(party, "What is the new rate per piece, and from when?", world)
        return reading

    def open_incident(self, world, party, kind, summary, reading, *, jobs=(), changes=None, until=None, back=None, delay_days=None, label=None) -> dict:
        """Nothing changes yet. The dispatcher sees the plan and approves it."""
        already = next((i for i in self.world().incidents.values() if i["status"] == "open" and i["workshop_id"] == party and i["summary"] == summary), None)
        if already:
            return already
        incident = {"workshop_id": party, "type": kind, "changes": changes or {}, "until": until, "back": back, "delay_days": delay_days,
                    "jobs": [j["key"] for j in jobs], "label": label, "reason": reading.get("reason")}
        rows = recovery.plan(world, {**incident, "id": ""})["rows"]
        late = sum(1 for r in rows if r["stay"]["back"] is None or (r["stay"]["days_to_spare"] or 0) < 0)
        detail = ""
        if rows:
            detail = f"{len(rows)} batch{'es' if len(rows) != 1 else ''} affected" + (f", {late} would miss the customer date." if late else ". All still make their dates.")
        if kind == "declined":
            detail = "It needs a new workshop."
        event = self.log("incident", **incident, summary=summary, detail=detail)
        moves = [f"{r['order_id']}: move to {r['move']['name']}, back {_short(r['move']['back'])}" if r["action"] == "move" and r["move"]
                 else f"{r['order_id']}: stays, back {_short(r['stay']['back'])}" for r in rows if r["stay"]["back"] or r["move"]]
        given = f"Reason given: {reading['reason']}" if reading.get("reason") else None
        self.alert("\n".join(filter(None, [summary, given, detail, *moves, "Approve here, or open Threadline to change the plan first."])),
                   [[{"text": "Approve plan", "data": f"i:approve:{event['id']}", "style": "success"}]], world)
        return event

    def incident(self, incident_id) -> dict:
        world = self.world()
        found = world.incidents.get(incident_id)
        if found is None:
            raise KeyError("That incident is not on record.")
        return {**found, "workshop": world.base[found["workshop_id"]].name, "plan": recovery.plan(world, found)}

    def approve(self, incident_id, by="Dispatcher", choices=None) -> dict:
        """The dispatcher's approval: apply the change, move what should move, set new dates, draft client notices."""
        world = self.world()
        incident = world.incidents.get(incident_id)
        if incident is None or incident["status"] != "open":
            raise ValueError("This incident has already been handled.")
        result = recovery.plan(world, incident)
        if incident.get("changes"):
            self.log("network", workshop_id=incident["workshop_id"], changes=incident["changes"], until=incident.get("until"), label=incident.get("label"),
                     reason=incident.get("reason"), by=by, incident=incident_id, on=world.today)
        moved, letters = 0, 0
        for row in result["rows"]:
            key = row["job"]
            job = world.jobs[key]
            action = (choices or {}).get(key, row["action"]) if row["can_keep"] else row["action"]    # A refused batch cannot stay where it was refused.
            if action == "move" and row["move"]:
                old = job["workshop_id"]
                self.log("move", job=key, to=row["move"]["workshop_id"], back=row["move"]["back"], detail=incident["summary"], by=by, on=world.today)
                if job["stage"] in ("offered", "accepted"):
                    self.say(old, f"{job['order_id']} has been moved to another workshop, so please do not start it. Thank you.", by=by, job=key, world=world)
                self.offer(key, by)
                moved += 1
            elif row["stay"]["back"] and row["stay"]["back"] != job["back"]:
                self.log("eta", job=key, back=row["stay"]["back"], detail=incident["summary"], by=by, on=world.today)
            final = row["move"]["back"] if action == "move" and row["move"] else row["stay"]["back"]
            if row["customer"] and job["due"] and final and date.fromisoformat(str(final)) > job["due"]:
                letters += bool(self.draft_letter(key, by=by, reason=incident["summary"]))
        self.say(incident["workshop_id"], "Thank you for letting us know. We have updated our plan.", by="Threadline", automatic=True, world=world)
        self.log("resolved", incident=incident_id, decision="approved", by=by, moved=moved, letters=letters)
        return {"moved": moved, "letters": letters}

    def dismiss(self, incident_id, by="Dispatcher") -> dict:
        world = self.world()
        incident = world.incidents.get(incident_id)
        if incident is None or incident["status"] != "open":
            raise ValueError("This incident has already been handled.")
        self.log("resolved", incident=incident_id, decision="dismissed", by=by)
        return {"moved": 0, "letters": 0}

    # Telling clients ---------------------------------------------------------------

    def draft_letter(self, key, *, by="Dispatcher", reason="") -> dict | None:
        world = self.world()
        job = self.job(key, world)
        if any(l.get("job") == key and l["status"] != "dropped" for l in world.letters.values()):
            return None
        return self.log("letter", job=key, party=ops.CLIENT + job["customer"], customer=job["customer"], order_id=job["order_id"], text=letter_text(job),
                        reason=reason or f"Back {_short(job['back'])}, after the customer date of {_short(job['due'])}.", by=by)

    def letter(self, letter_id) -> dict:
        world = self.world()
        found = world.letters.get(letter_id)
        if found is None:
            raise KeyError("That notice is not on record.")
        return {**found, "connected": found["party"] in world.bindings, "check": faithfulness.check(found["text"], facts(world.jobs[found["job"]]))}

    def send_letter(self, letter_id, text=None, by="Dispatcher", acknowledged=False) -> dict:
        """Numbers are checked against the record, so an edit cannot quietly promise a date nobody holds."""
        world = self.world()
        found = world.letters.get(letter_id)
        if found is None or found["status"] != "draft":
            raise ValueError("This notice has already been handled.")
        text = (text or found["text"]).strip()
        audit = faithfulness.check(text, facts(world.jobs[found["job"]]))
        if not audit["passed"] and not acknowledged:
            return {"sent": False, "unmatched": audit["unmatched"]}
        message = self.say(found["party"], text, by=by, job=found["job"], world=world)
        self.log("letter_sent", letter=letter_id, text=text, by=by, unmatched=audit["unmatched"], delivered=message["delivered"])
        return {"sent": True, "unmatched": audit["unmatched"]}

    def suggestions(self, party, world) -> list[dict]:
        """Ready-made replies from the record, never from the model."""
        if party.startswith(ops.CLIENT):
            name = party[len(ops.CLIENT):]
            jobs = [j for j in world.jobs.values() if j["customer"] == name and j["stage"] != "received"]
            return [{"label": f"Status of {j['order_id']}", "text": f"{j['order_id']} is {ops.STAGES[j['stage']].lower()}. We expect it back on {long_date(j['back'])}."} for j in jobs[:3]]
        out = [{"label": f"Chase {j['order_id']}", "text": f"How is {j['order_id']} looking? It is booked back on {long_date(j['back'])}."} for j in ops.open_jobs(world, party)[:2]]
        if world.workshops[party].status != "ACTIVE":
            out.insert(0, {"label": "When do you reopen?", "text": "When do you expect to reopen?"})
        return out + [{"label": "Thank you", "text": "Thank you."}]

    def thread(self, party) -> dict:
        world = self.world()
        name = ops.party_name(party, world.workshops)
        return {"party": party, "name": name, "type": "client" if party.startswith(ops.CLIENT) else "workshop", "connected": party in world.bindings,
                "messages": world.threads.get(party, []), "suggestions": self.suggestions(party, world), "telegram_url": ops.telegram_link(world.bindings.get(party)),
                "jobs": [ops.job_view(j, world.today) for j in world.jobs.values() if (j["workshop_id"] == party or ops.CLIENT + str(j["customer"]) == party) and j["stage"] != "received"]}

    def where(self, text) -> str:
        """The answer to /where in the team chat. Never reaches the model."""
        order = (guardrails.order_refs(spoken(text)) or [None])[0]
        if order is None:
            return "Say which order, for example /where ORD-041."
        world = self.world()
        job = self._job_for(order, world)
        return self.answer_job(job, world)["text"] if job else f"{order} has not been sent to a workshop."

    def bind(self, party, chat_id, thread_id=None) -> dict:
        return self.log("bind", party=party, chat_id=chat_id, thread_id=thread_id)

    def catch_up(self, party) -> int:
        """A chat that has just taken on a workshop gets the offers waiting for it, which had nowhere to go before."""
        world = self.world()
        waiting = [j for j in world.jobs.values() if j["workshop_id"] == party and j["stage"] == "offered"]
        for job in waiting:
            lang = self.language(party, world)
            self.transport.send(world.bindings[party], offer_text(job, lang), offer_buttons(job["key"], lang))
        return len(waiting)

    def hearing_hints(self, language="en") -> str:
        return hearing.hints([w.name for w in self.world().base.values()], sorted(self.orders["customer"].dropna().unique()), language)

    def party_for(self, chat_id, thread_id=None) -> str | None:
        world = self.world()
        return next((p for p, b in world.bindings.items() if b["chat_id"] == chat_id and b.get("thread_id") == thread_id), None)

    def resolve_party(self, text: str) -> str | None:
        return self._party_in(text, self.world())

    def set_clock(self, day: date) -> dict:
        if day < desk.TODAY:
            raise ValueError("Pick a date on or after the 1 April snapshot.")
        return self.log("clock", today=day)

    # Automations ------------------------------------------------------------------

    def automations(self) -> list[dict]:
        switched = self.world().automations
        return [{"name": name, "title": title, "detail": detail, "on": bool(switched.get(name))} for name, (title, detail) in AUTOMATIONS.items()]

    def set_automation(self, name, on, by="Dispatcher") -> list[dict]:
        if name not in AUTOMATIONS:
            raise KeyError("That automation does not exist.")
        self.log("automation", name=name, on=bool(on), by=by)
        return self.automations()

    def _silent(self, world) -> list[dict]:
        return [j for j in ops.open_jobs(world) if not j["reminded_at"] and ops.is_silent(j, world.today)]

    def _chase_silent(self, world) -> list[str]:
        """A reminder with no chat to go to reaches nobody, so it stays due until the workshop connects."""
        waiting = [j for j in self._silent(world) if j["workshop_id"] in world.bindings]
        for job in waiting:
            self.chase(job["key"], by="Threadline", automatic=True)
        return [f"{j['workshop']} reminded about {j['order_id']}" for j in waiting]

    def _check_due(self, world) -> list[str]:
        asked = {e.get("job") for e in world.events if e["kind"] == "reminder" and e.get("reason") == "check_due"}
        tomorrow = world.today + timedelta(days=1)
        due = [j for j in ops.open_jobs(world) if j["back"] == tomorrow and j["stage"] in ("accepted", "in_production") and j["key"] not in asked
               and j["workshop_id"] in world.bindings]
        for job in due:
            self.chase(job["key"], by="Threadline", automatic=True, reason="check_due")
        return [f"{j['workshop']} asked about {j['order_id']}" for j in due]

    def _send_brief(self, world) -> list[str]:
        binding = world.bindings.get(ops.TEAM)
        if not (binding and self.transport.send(binding, ops.brief(world), None)):
            return []                   # Not posted, so it stays due until a team chat can receive it.
        self.log("brief", on=world.today)
        return ["Brief posted in the team chat"]

    def run_automation(self, name) -> dict:
        """Run one rule now, whether or not it is switched on."""
        if name not in AUTOMATIONS:
            raise KeyError("That automation does not exist.")
        done = getattr(self, {"morning_brief": "_send_brief"}.get(name, f"_{name}"))(self.world())
        world = self.world()
        unreachable = sorted({j["workshop"] for j in self._silent(world) if j["workshop_id"] not in world.bindings}) if name == "chase_silent" else []
        empty = ("The team chat is not connected. Send /iam Team there." if name == "morning_brief"
                 else f"{' and '.join(unreachable)} has no chat connected, so no reminder went." if unreachable else "Nothing needed doing.")
        return {"done": done, "text": ". ".join(done) + "." if done else empty}

    def automate(self, moment=None) -> list[str]:
        """One pass of the switched-on rules. Called every half minute while the desk runs."""
        world = self.world()
        moment = moment or datetime.now()
        done = []
        if world.automations.get("chase_silent"):
            done += self._chase_silent(world)
        if world.automations.get("check_due"):
            done += self._check_due(world)
        briefed = any(e["kind"] == "brief" and ops._day(e.get("on")) == world.today for e in world.events)
        if world.automations.get("morning_brief") and not briefed and (moment.hour, moment.minute) >= BRIEF_AT:
            done += self._send_brief(world)
        return done

    # Demo -------------------------------------------------------------------------

    def reset_demo(self) -> dict:
        """A known starting point: real decisions from the supplied requests, at different stages, read from the fixtures.

        Only rehearsal logs are touched, and chat bindings survive so Telegram stays connected."""
        if not self.demo:
            raise ValueError("Reset only applies to the demo.")
        keep = [e for e in ops.rows(self.ops_path) if e["kind"] in ("bind", "language")]
        for path in (self.decisions_path, self.ops_path, self.path_received()):
            path.unlink(missing_ok=True)
        self.orders = self.supplied
        for event in keep:
            if event["kind"] == "language":
                self.set_language(event["party"], event["language"])
            else:
                self.log("bind", party=event["party"], chat_id=event["chat_id"], thread_id=event.get("thread_id"))
        self.previews, self.saved = {}, {}
        stages = ("in_production", "accepted", "in_production", "accepted", "offered", "accepted", "in_production", "offered")
        keys = []
        for rid, stage in zip(SEED, stages):
            line = next(m for m in self.messages if m.startswith(rid + " "))
            card = self.evaluate(line, by="Mei", request=rid)
            if card.get("card") != "recommendation" or not card.get("can_confirm"):
                continue
            stored = self._stored(card["token"])
            world = self.world()
            row = desk.confirm_preview(stored["preview"], self._current(stored, world), self.saved, append=self._append, guided_demo=True, channel="telegram", by="Mei")
            self.log("request_done", line=rid, by="Mei")
            key = f"{card['token']}:{row['decision_record']['chosen_workshop']}"
            keys.append(key)
            self.log("offer", job=key, on=date(2026, 3, 31) if stage == "offered" and rid == "R27" else world.today, by="Mei")
            job = self.job(key)
            name = job["workshop"]
            self.log("message", party=job["workshop_id"], direction="out", author="Mei", text=offer_text(job), channel="roleplay", job=key, delivered=True, automatic=False)
            for reached in {"accepted": ("accepted",), "in_production": ("accepted", "in_production")}.get(stage, ()):
                self.set_stage(key, reached, by=name, detail="Role-play tap")
                self.log("message", party=job["workshop_id"], direction="in", author=name, text=f"{ops.STAGES[reached]} ({job['order_id']})", channel="roleplay", job=key, tapped=True)
        return {"jobs": len(keys)}

    def health(self) -> dict:
        world = self.world()
        status = rehearsal.live_status()
        return {"ok": True, "demo": self.demo, "today": world.today, "source": self.source, "reader": "model" if self.partner_call else "rules",
                "model": intake.model_label(status.get("model")) if status.get("model") else None, "telegram": self.transport.connected,
                "connected": sorted(world.bindings)}
