"""What happens after a decision: the two-way loop with workshops and clients.

The audit log records decisions. This log records everything after them: an offer
goes out, a workshop accepts, says it has closed or asks for more time, a client
answers a delay notice, the dispatcher approves a recovery plan. Each is one
appended line. The current picture (jobs, workshop status, threads, incidents) is
always rebuilt from those lines, on top of the untouched CSV snapshot and audit
log, so nothing is ever edited and every change can be traced to who made it.

Workshop changes are overlays: build() returns copies of the Workshop records with
the approved changes applied, and the existing engine takes them as they are.
No allocation rule lives here.

Append-only JSONL with a file lock, like the audit log. records/*.jsonl is git-ignored.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

import portalocker

import batches
import desk
import languages
from ui import explain

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "records" / "ops.jsonl"
REHEARSAL_LOG = ROOT / "records" / "rehearsal_ops.jsonl"

STAGES = {
    "booked": "Booked, not sent yet",
    "offered": "Waiting for the workshop",
    "accepted": "Accepted",
    "in_production": "In production",
    "ready": "Completed",
    "shipped": "On its way back",
    "received": "Received",
    "declined": "Declined by the workshop",
}
# The batch no longer ties up the workshop: it is finished, or it was never taken. It does not have to be back first.
FREE_STAGES = ("ready", "shipped", "received", "declined")
OPEN_STAGES = ("booked", "offered", "accepted", "in_production", "ready", "declined")   # still needs something from someone
# The same order and meaning as the status colours on the phone, so a chat and the app read alike.
MARKS = {"booked": "⚪", "offered": "🟣", "accepted": "🔵", "in_production": "✂️", "ready": "📦", "shipped": "🚚", "received": "✅", "declined": "🔴"}
STEPS = {"booked": 0, "offered": 1, "accepted": 2, "in_production": 3, "ready": 4, "shipped": 4, "received": 5, "declined": 0}
OFFER_SLA_MINUTES = 120   # an offer unanswered this long is worth a reminder
CLIENT = "client:"
ISLAND_STEPS = {"booked": 0, "offered": 0, "declined": 0, "accepted": 1, "in_production": 2, "ready": 3, "shipped": 3, "received": 4}
TEAM = "team"             # the dispatcher's own chat: gets the brief, is not a party to any job


def log_path(decisions_path) -> Path:
    """The operations log that belongs to an audit log (live or rehearsal)."""
    return REHEARSAL_LOG if decisions_path is not None and Path(decisions_path).name.startswith("rehearsal") else LOG


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(path: Path, kind: str, **fields) -> dict:
    row = {"id": uuid4().hex[:10], "kind": kind, "at": now(), **fields}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        portalocker.lock(stream, portalocker.LOCK_EX)
        try:
            stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            stream.flush()
        finally:
            portalocker.unlock(stream)
    return row


def rows(path: Path) -> list[dict]:
    try:
        stream = Path(path).open(encoding="utf-8")
    except FileNotFoundError:
        return []
    out = []
    with stream:
        portalocker.lock(stream, portalocker.LOCK_SH)
        try:
            for line in stream:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue   # A torn line never hides the rest of the history.
        finally:
            portalocker.unlock(stream)
    return out


def _day(value) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


def party_name(party: str, workshops) -> str:
    if party.startswith(CLIENT):
        return party[len(CLIENT):]
    return workshops[party].name if party in workshops else party


@dataclass
class World:
    today: date
    base: dict
    workshops: dict            # base records with approved changes applied
    notices: dict              # workshop id -> approved changes in force, newest last
    queues: dict
    allocator: object
    jobs: dict
    threads: dict              # party -> messages, oldest first, each with its reading
    incidents: dict
    letters: dict              # client notices, draft or sent
    bindings: dict             # party -> {"chat_id", "thread_id"}
    events: list = field(default_factory=list)
    automations: dict = field(default_factory=dict)   # name -> switched on
    languages: dict = field(default_factory=dict)     # party -> job card language, English if missing


def _network(base, events, today):
    workshops, notices = deepcopy(base), {wid: [] for wid in base}
    for event in events:
        if event["kind"] != "network" or event["workshop_id"] not in workshops:
            continue
        until = _day(event.get("until"))
        if until and today >= until:
            continue   # The change has run its course; the record of it stays in the log.
        workshop = workshops[event["workshop_id"]]
        for name, value in event["changes"].items():
            setattr(workshop, name, value)
        notices[event["workshop_id"]].append({k: event.get(k) for k in ("label", "until", "reason", "by", "at")})
    return workshops, notices


def _note(job, event, label, detail=""):
    job["log"].append({"at": event["at"], "on": event.get("on"), "label": label, "detail": detail, "by": event.get("by")})


def build(base, decisions_path=None, path=None, received=None) -> World:
    events = rows(path or log_path(decisions_path))
    today = _day(next((e["today"] for e in reversed(events) if e["kind"] == "clock"), None)) or desk.TODAY
    workshops, notices = _network(base, events, today)
    queues, allocator, _ = desk.queues_from_log(base, decisions_path)

    jobs = {}
    for batch in batches.out_batches(decisions_path, received):
        jobs[batch["key"]] = {**batch, "stage": "received" if batch["received"] else "booked", "back_was": None, "moved_from": None,
                              "rate": base[batch["workshop_id"]].cost if batch["workshop_id"] in base else None,
                              "offered_at": None, "offered_on": None, "reminded_at": None, "held": False, "log": []}
        job = jobs[batch["key"]]
        job["log"].append({"at": batch["confirmed_at"], "on": str(batch["sent"]) if batch["sent"] else None, "label": "Decision confirmed",
                           "detail": f"{batch['workshop']}, back {explain.short_date(batch['back'])}", "by": batch["by"]})
        if batch["received"]:
            job["log"].append({"at": batch["received"]["at"], "on": batch["received"]["scenario_date"], "label": "Received",
                               "detail": "", "by": batch["received"]["by"]})

    threads, incidents, letters, bindings, readings, automations = {}, {}, {}, {}, {}, {}
    chosen_languages = {}
    for event in events:
        kind, job = event["kind"], jobs.get(event.get("job"))
        if kind == "automation":
            automations[event["name"]] = event["on"]
        elif kind == "language":
            chosen_languages[event["party"]] = event["language"]
        elif kind == "bind":
            here = {"chat_id": event["chat_id"], "thread_id": event.get("thread_id")}
            bindings = {party: chat for party, chat in bindings.items() if chat != here}   # A chat speaks for one party at a time.
            bindings[event["party"]] = here
        elif kind == "message":
            threads.setdefault(event["party"], []).append({**event, "reading": None})
        elif kind == "reading":
            readings[event["message"]] = event["reading"]
        elif kind == "incident":
            incidents[event["id"]] = {**event, "status": "open", "resolution": None}
        elif kind == "resolved" and event["incident"] in incidents:
            incidents[event["incident"]].update(status=event["decision"], resolution=event)
        elif kind == "letter":
            letters[event["id"]] = {**event, "status": "draft"}
        elif kind == "letter_sent" and event["letter"] in letters:
            letters[event["letter"]].update(status="sent", text=event["text"], sent_at=event["at"], sent_by=event.get("by"), delivered=event.get("delivered"))
        elif kind == "letter_dropped" and event["letter"] in letters:
            letters[event["letter"]].update(status="dropped")
        elif job is None:
            continue
        elif kind == "offer":
            if job["stage"] != "received":
                job.update(stage="offered", offered_at=event["at"], offered_on=event.get("on"), reminded_at=None)
            _note(job, event, "Offered", job["workshop"])
        elif kind == "reminder":
            job["reminded_at"] = event["at"]
            _note(job, event, "Reminder sent", job["workshop"])
        elif kind == "stage":
            if job["stage"] != "received":
                job["stage"] = event["stage"]
            _note(job, event, STAGES.get(event["stage"], event["stage"]), event.get("detail", ""))
        elif kind == "eta":
            job.update(back_was=job["back"], back=_day(event["back"]))
            _note(job, event, "New return date", f"{explain.short_date(event['back'])}. {event.get('detail', '')}".strip())
        elif kind == "move":
            was, to = job["workshop_id"], event["to"]
            if was in base:
                queues[was] = max(0.0, queues.get(was, 0.0) - job["pieces"] / base[was].capacity)
                allocator.pieces_by_workshop[was] = max(0, allocator.pieces_by_workshop.get(was, 0) - job["pieces"])
            queues[to] = queues.get(to, 0.0) + job["pieces"] / base[to].capacity
            allocator.pieces_by_workshop[to] = allocator.pieces_by_workshop.get(to, 0) + job["pieces"]
            job.update(moved_from=job["workshop"], workshop_id=to, workshop=base[to].name, back=_day(event["back"]),
                       rate=base[to].cost, stage="booked", offered_at=None, offered_on=None)
            _note(job, event, "Moved", f"to {base[to].name}, back {explain.short_date(event['back'])}. {event.get('detail', '')}".strip())
    for messages in threads.values():
        for message in messages:
            message["reading"] = readings.get(message["id"])
    for job in jobs.values():
        wid = job["workshop_id"]
        if job["stage"] in FREE_STAGES and wid in base:
            queues[wid] = max(0.0, queues.get(wid, 0.0) - job["pieces"] / base[wid].capacity)
            allocator.pieces_by_workshop[wid] = max(0, allocator.pieces_by_workshop.get(wid, 0) - job["pieces"])
    queues = desk.projected_queues(queues, desk.TODAY, today)
    return World(today, base, workshops, notices, queues, allocator, jobs, threads, incidents, letters, bindings, events, automations, chosen_languages)


# Views ---------------------------------------------------------------------------

def health(job, today) -> str:
    """batches.STATUSES key, with a job still at a closed workshop or declined never shown as on track."""
    return batches.status(job, today)


def island(job) -> dict:
    """What a batch's Dynamic Island says. The app and Apple's push both use this, so they cannot disagree."""
    declined = job["stage"] == "declined"
    status = f"{job['workshop']} cannot take it" if declined else f"Waiting for {job['workshop']}" if job["stage"] == "offered" else STAGES[job["stage"]]
    return {"status": status, "detail": f"{goods(job)}, back {explain.short_date(job['back'])}", "step": ISLAND_STEPS[job["stage"]], "alert": declined}


def job_view(job, today) -> dict:
    spare = (job["due"] - job["back"]).days if job["due"] and job["back"] else None
    status = health(job, today)
    return {"key": job["key"], "order_id": job["order_id"], "customer": job["customer"], "product": job["product"], "category": job["category"],
            "pieces": job["pieces"], "workshop_id": job["workshop_id"], "workshop": job["workshop"], "sent": job["sent"], "back": job["back"],
            "back_was": job["back_was"], "due": job["due"], "days_to_spare": spare, "stage": job["stage"], "stage_label": STAGES[job["stage"]],
            "health": status, "health_label": batches.STATUSES[status], "split": job["split"], "override": bool(job["override"]),
            "moved_from": job["moved_from"], "channel": job["channel"], "confirmed_by": job["by"], "rate": job["rate"],
            "total_cost": round(job["pieces"] * job["rate"], 2) if job["rate"] else None, "log": job["log"], "silent": is_silent(job, today), "island": island(job)}


def age_seconds(stamp: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()


def goods(job) -> str:
    """'150 vests', same plural rule as the desk: scarf to scarves."""
    word = str(job["product"] or "pieces").lower()
    word = word[:-1] + "ves" if word.endswith("f") else word if word.endswith("s") else word + "s"
    return f"{job['pieces']:,} {word}"


def stage_line(job, lang="en") -> str:
    """'✂️ In production ▰▰▰▱▱': where a batch is, in the words and order the app uses."""
    step = STEPS[job["stage"]]
    return f"{MARKS[job['stage']]} {languages.say(lang, STAGES[job['stage']])} {'▰' * step}{'▱' * (5 - step)}"


def telegram_link(binding) -> str | None:
    """A link to a bound chat or topic, which Telegram can only make for a supergroup."""
    chat = str((binding or {}).get("chat_id", ""))
    if not chat.startswith("-100"):
        return None
    topic = binding.get("thread_id")
    return f"https://t.me/c/{chat[4:]}" + (f"/{topic}" if topic else "")


def is_silent(job, today, moment=None) -> bool:
    """An offer nobody has answered. A reminder restarts the wait, so its card clears once one is sent."""
    if job["stage"] != "offered":
        return False
    sent = datetime.fromisoformat(job["reminded_at"] or job["offered_at"])
    waited = ((moment or datetime.now(timezone.utc)) - sent).total_seconds() / 60
    return waited > OFFER_SLA_MINUTES or (not job["reminded_at"] and (_day(job["offered_on"]) or today) < today)


def open_jobs(world, workshop_id=None) -> list[dict]:
    jobs = [j for j in world.jobs.values() if j["stage"] in OPEN_STAGES and (workshop_id is None or j["workshop_id"] == workshop_id)]
    return sorted(jobs, key=lambda j: (j["back"] or world.today, j["order_id"] or ""))


def workshop_view(world, workshop_id) -> dict:
    w = world.workshops[workshop_id]
    jobs = [j for j in world.jobs.values() if j["workshop_id"] == workshop_id]
    reported = next((i for i in world.incidents.values() if i["status"] == "open" and i["workshop_id"] == workshop_id), None)
    offers = sum(1 for e in world.events if e["kind"] == "offer" and world.jobs.get(e.get("job"), {}).get("workshop_id") == workshop_id)
    said = [e for e in world.events if e["kind"] == "stage" and world.jobs.get(e.get("job"), {}).get("workshop_id") == workshop_id]
    binding = world.bindings.get(workshop_id)
    return {"id": workshop_id, "name": w.name, "status": w.status, "capacity": w.capacity, "lead_days": w.lead_days, "cost": w.cost,
            "defect_rate": w.defect_rate, "makes": sorted(w.makes), "max_batch": w.max_batch, "notes": w.notes,
            "queue_days": round(world.queues.get(workshop_id, 0.0), 1), "open_jobs": sum(1 for j in jobs if j["stage"] not in FREE_STAGES),
            "completed": sum(1 for j in jobs if j["stage"] in ("ready", "shipped")),
            "pieces_out": sum(j["pieces"] for j in jobs if j["stage"] in OPEN_STAGES + ("shipped",)),
            "notices": world.notices.get(workshop_id, []), "reported": reported["summary"] if reported else None,
            "offers": offers, "accepted": sum(1 for e in said if e["stage"] == "accepted"), "declined": sum(1 for e in said if e["stage"] == "declined"),
            "connected": binding is not None, "last_message": (world.threads.get(workshop_id) or [{}])[-1].get("text")}


def _letters_for(world, job_key) -> list[dict]:
    return [l for l in world.letters.values() if l.get("job") == job_key]


def attention(world) -> list[dict]:
    """Everything that needs a person now, most urgent first. Each card has one obvious next step."""
    cards = []

    def add(rank, kind, tone, title, detail, action, target, when=None):
        cards.append({"id": f"{kind}:{target['id']}", "rank": rank, "kind": kind, "tone": tone, "title": title, "detail": detail,
                      "action": action, "target": target, "when": when})

    for incident in world.incidents.values():
        if incident["status"] == "open":
            count = len(incident.get("jobs", []))
            detail = incident.get("detail") or (f"{count} batch{'es' if count != 1 else ''} affected." if count else "Review before it changes the network.")
            add(0, "incident", "risk", incident["summary"], detail, "Review", {"type": "incident", "id": incident["id"]}, incident["at"])
    for letter in world.letters.values():
        if letter["status"] == "draft":
            add(1, "letter", "warn", f"Tell {letter['customer']} about {letter['order_id']}", letter.get("reason", "A delay notice is ready to send."),
                "Review notice", {"type": "letter", "id": letter["id"]}, letter["at"])
    for party, messages in world.threads.items():
        last = messages[-1]
        reading = last.get("reading") or {}
        if last["direction"] == "in" and reading.get("needs_person"):
            add(2, "question", "info", f"{party_name(party, world.workshops)} needs an answer", last["text"][:120], "Reply",
                {"type": "thread", "id": party}, last["at"])
    today = world.today
    planned = {key for i in world.incidents.values() if i["status"] == "open" for key in i.get("jobs", [])}
    for job in open_jobs(world):
        label = goods(job)
        target = {"type": "job", "id": job["key"]}
        if job["stage"] == "declined":
            if job["key"] not in planned:   # An open incident already carries the plan for this batch.
                add(1, "declined", "risk", f"{job['workshop']} cannot take {job['order_id']}", label, "Find another workshop", target)
        elif job["stage"] == "booked":
            add(5, "unsent", "info", f"{job['order_id']} has not gone to {job['workshop']}", label, "Send offer", target)
        elif job["back"] and job["back"] < today:
            add(2, "overdue", "risk", f"{job['order_id']} is {explain.days((today - job['back']).days)} overdue", f"{job['workshop']}, {label}", "Chase", target)
        elif job["back"] == today:
            add(3, "due", "warn", f"{job['order_id']} is due back today", f"{job['workshop']}, {label}", "Mark received", target)
        elif is_silent(job, today):
            add(4, "silent", "warn", f"No answer from {job['workshop']}", f"{job['order_id']} was offered. No reply yet.", "Send a reminder", target)
        if job["back"] and job["due"] and job["back"] > job["due"] and not _letters_for(world, job["key"]):
            late = (job["back"] - job["due"]).days
            add(2, "late", "warn", f"{job['order_id']} will miss the {job['customer'] or 'customer'} date",
                f"Back {explain.short_date(job['back'])}, {explain.days(late)} after {explain.short_date(job['due'])}.", "Tell the client", target)
    return sorted(cards, key=lambda c: c["rank"])


def thread_summaries(world) -> list[dict]:
    clients = [CLIENT + str(j["customer"]) for j in world.jobs.values() if j["customer"] and j["stage"] != "received"]
    parties = dict.fromkeys(list(world.base) + list(world.threads) + clients)
    out = []
    for party in parties:
        messages = world.threads.get(party, [])
        last = messages[-1] if messages else None
        is_client = party.startswith(CLIENT)
        out.append({"party": party, "name": party_name(party, world.workshops), "type": "client" if is_client else "workshop",
                    "connected": party in world.bindings, "status": None if is_client else world.workshops[party].status,
                    "last_text": last["text"] if last else None, "last_at": last["at"] if last else None,
                    "last_direction": last["direction"] if last else None, "count": len(messages)})
    return sorted(out, key=lambda t: (t["last_at"] is None, t["last_at"] and -datetime.fromisoformat(t["last_at"]).timestamp(), t["name"]))


def brief(world) -> str:
    """The spoken and written morning summary, composed from the same cards the Today screen shows."""
    cards = attention(world)
    out = [j for j in world.jobs.values() if j["stage"] not in ("received",)]
    closed = [w.name for wid, w in world.workshops.items() if w.status != "ACTIVE" and world.base[wid].status == "ACTIVE"]
    lead = f"{len(cards)} thing{'s need' if len(cards) != 1 else ' needs'} you." if cards else "Nothing needs you right now."
    lines = [lead, f"{len(out)} batch{'es are' if len(out) != 1 else ' is'} out at workshops."]
    if closed:
        lines.append(f"{' and '.join(closed)} {'are' if len(closed) != 1 else 'is'} closed.")
    lines += [card["title"] + "." for card in cards[:3]]
    return " ".join(lines)


_COUNTS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def _count(number: int) -> str:
    return _COUNTS[number] if number < len(_COUNTS) else str(number)


def _aloud(line: str) -> str:
    """A written line as someone would say it: order 41 rather than ORD-041, and names a voice can pronounce."""
    line = re.sub(r"ORD-0*(\d+)", r"order \1", line)
    line = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", line)
    return line.replace("cannot", "can't").replace("has not", "hasn't")


def _said(card) -> str:
    if card["kind"] == "silent":
        return f"{card['title'].removeprefix('No answer from ')} still hasn't answered on {card['detail'].split(' was')[0]}"
    if card["kind"] == "overdue":
        return f"{card['title']} at {card['detail'].split(',')[0]}"
    if card["kind"] == "letter":
        return f"you still need to {card['title'][0].lower()}{card['title'][1:]}"
    return card["title"]


def spoken_brief(world) -> str:
    """The same facts as brief(), in the words a colleague would use when reading them out to you."""
    cards = attention(world)
    out = len([j for j in world.jobs.values() if j["stage"] != "received"])
    closed = [w.name for wid, w in world.workshops.items() if w.status != "ACTIVE" and world.base[wid].status == "ACTIVE"]
    hour = datetime.now().hour
    lines = ["Morning." if hour < 12 else "Afternoon." if hour < 18 else "Evening."]
    lines.append(f"{_count(len(cards)).capitalize()} thing{'s need' if len(cards) != 1 else ' needs'} you." if cards else "Nothing needs you right now.")
    if closed:
        lines.append(f"{' and '.join(closed)} {'are' if len(closed) != 1 else 'is'} closed.")
    for lead, card in zip(("", "Then, ", "And "), cards):
        said = _aloud(_said(card))
        lines.append(f"{lead}{said}." if lead else f"{said[0].upper()}{said[1:]}.")
    if len(cards) > 3:
        lines.append(f"There {'are' if len(cards) > 4 else 'is'} {_count(len(cards) - 3)} more on your list.")
    if out:
        lines.append(f"{_count(out).capitalize()} batch{'es are' if out != 1 else ' is'} out with workshops.")
    return _aloud(" ".join(lines))


def advance(job_stage_from: str) -> str | None:
    order = ["offered", "accepted", "in_production", "ready", "shipped"]
    return order[order.index(job_stage_from) + 1] if job_stage_from in order[:-1] else None


def shift(day: date, days: int) -> date:
    return day + timedelta(days=int(days))
