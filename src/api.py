"""The HTTP API the iPhone app talks to. No logic here: every route is one call into control.py.

Run it from the repository root:

    uv run python src/api.py                 # this Mac only, for the iOS Simulator
    uv run python src/api.py --lan           # also reachable from an iPhone on the same network

--lan needs THREADLINE_API_TOKEN in the environment, and the app sends it as a
bearer token. If TELEGRAM_BOT_TOKEN is set the bot runs inside this process, so
the app and Telegram share one desk. Without it, messages stay in the app and are
marked as not delivered, and role-play covers the other side.

THREADLINE_MODE=demo (default) writes to the rehearsal logs and can be reset.
THREADLINE_MODE=live writes to the live logs. THREADLINE_READING picks live
(default), cached or fixture for reading new requests.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
from datetime import date
import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PERF_LOG = ROOT / "records" / "perf.jsonl"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import control  # noqa: E402
import hearing  # noqa: E402
import intake  # noqa: E402
import island  # noqa: E402
import ops  # noqa: E402
import partners  # noqa: E402
import rehearsal  # noqa: E402
import telegram_bot  # noqa: E402

app = FastAPI(title="Threadline")
desk_control: control.Control | None = None
push = island.Island()


class Words(BaseModel):
    text: str
    by: str = "Dispatcher"


class By(BaseModel):
    by: str = "Dispatcher"


class Device(BaseModel):
    token: str = Field(pattern=r"^[0-9a-f]{32,400}$")     # It becomes part of the address on Apple's server.


class Watch(Device):
    key: str


class Answer(By):
    field: str
    value: str


class Override(By):
    workshop_id: str
    reason: str
    note: str = ""


class Note(By):
    note: str = ""


class Escalation(Note):
    reason: str


class Approval(By):
    choices: dict[str, str] | None = None


class Letter(By):
    text: str | None = None
    acknowledged: bool = False


class Inbound(BaseModel):
    party: str
    text: str
    by: str | None = None


class Tap(BaseModel):
    action: str
    key: str
    by: str = "Workshop"
    reason: str | None = None


class Clock(BaseModel):
    today: date


class Switch(By):
    on: bool


class NewRequest(By):
    order_id: str | None = None
    customer: str | None = None
    product: str | None = None
    pieces: int | None = None
    due: date | None = None
    priority: str | None = None
    note: str = ""


class Request_(By):
    line: str
    request: str | None = None


def desk() -> control.Control:
    global desk_control
    if desk_control is None:
        desk_control = make_control()
    return desk_control


def check_token(request: Request) -> None:
    expected = os.environ.get("THREADLINE_API_TOKEN")
    if not expected:
        return
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.query_params.get("token", "")
    if not hmac.compare_digest(given, expected):
        raise HTTPException(401, "This phone is not authorised.")


def guarded(call, *args, **kwargs):
    """Business refusals reach the phone as plain sentences, never as a server error."""
    try:
        return jsonable_encoder(call(*args, **kwargs))
    except KeyError as error:
        raise HTTPException(404, str(error.args[0]) if error.args else "Not found.") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/api/health")
def health():
    return jsonable_encoder({**desk().health(), "island_push": push.ready()})


@app.get("/api/today", dependencies=[Depends(check_token)])
def today():
    return guarded(desk().today)


@app.get("/api/requests", dependencies=[Depends(check_token)])
def requests():
    return guarded(desk().waiting_requests)


@app.post("/api/requests/open", dependencies=[Depends(check_token)])
def open_request(body: Request_):
    return guarded(desk().evaluate, body.line, by=body.by, request=body.request)


@app.post("/api/speak", dependencies=[Depends(check_token)])
def speak(body: Words):
    return guarded(desk().speak, body.text, body.by)


@app.post("/api/device", dependencies=[Depends(check_token)])
def add_device(body: Device):
    push.phone(body.token)
    return {"ok": True}


@app.get("/api/decisions/{token}/split", dependencies=[Depends(check_token)])
def split_option(token: str):
    return guarded(desk().split_option, token)


@app.post("/api/decisions/{token}/split", dependencies=[Depends(check_token)])
def confirm_split(token: str, body: By):
    return guarded(desk().confirm_split, token, by=body.by)


@app.post("/api/island", dependencies=[Depends(check_token)])
def watch_island(body: Watch):
    """The token for the batch on this phone's Island, so its next stage can reach it with the app closed."""
    return guarded(lambda: push.watch(body.token, body.key, ops.island(desk().job(body.key))) or {"ok": True})


@app.post("/api/transcribe", dependencies=[Depends(check_token)])
async def transcribe(request: Request, language: str = "en"):
    """A WAV clip from the phone, read back as words. With "auto" the language comes from the voice, and is sent back so
    the phone need not ask again. The phone keeps its own words if this cannot answer."""
    if language not in ("auto", "en", "hi", "zh"):
        raise HTTPException(422, "That language is not supported.")
    if not hearing.ready(language):
        raise HTTPException(503, "Whisper is not set up on this Mac.")
    audio = await request.body()
    if language == "auto":
        language = await asyncio.to_thread(hearing.detect, audio)
    return {"text": await asyncio.to_thread(hearing.listen, audio, desk().hearing_hints(language), language), "language": language}


@app.post("/api/language", dependencies=[Depends(check_token)])
async def spoken_language(request: Request):
    """Which language this clip is in, ahead of its words, so the phone can say so straight away."""
    if not hearing.ready():
        raise HTTPException(503, "Whisper is not set up on this Mac.")
    return {"language": await asyncio.to_thread(hearing.detect, await request.body())}


@app.post("/api/decisions/{token}/confirm", dependencies=[Depends(check_token)])
def confirm(token: str, body: By):
    return guarded(desk().confirm, token, body.by)


@app.post("/api/decisions/{token}/override", dependencies=[Depends(check_token)])
def override(token: str, body: Override):
    return guarded(desk().override, token, body.workshop_id, body.reason, body.note, by=body.by)


@app.post("/api/decisions/{token}/answer", dependencies=[Depends(check_token)])
def answer(token: str, body: Answer):
    return guarded(desk().answer, token, body.field, body.value, by=body.by)


@app.post("/api/decisions/{token}/escalate", dependencies=[Depends(check_token)])
def escalate(token: str, body: Escalation):
    return guarded(desk().escalate, token, body.reason, body.note, by=body.by)


@app.get("/api/batches", dependencies=[Depends(check_token)])
def batches():
    world = desk().world()
    return jsonable_encoder([ops.job_view(j, world.today) for j in sorted(world.jobs.values(), key=lambda j: (j["back"] or world.today, j["order_id"] or ""))])


@app.get("/api/batches/{key}", dependencies=[Depends(check_token)])
def batch(key: str):
    world = desk().world()
    return guarded(lambda: {**ops.job_view(desk().job(key, world), world.today),
                            "letters": [l for l in world.letters.values() if l.get("job") == key]})


@app.post("/api/batches/{key}/received", dependencies=[Depends(check_token)])
def received(key: str, body: By):
    return guarded(desk().mark_received, key, body.by)


@app.post("/api/batches/{key}/offer", dependencies=[Depends(check_token)])
def offer(key: str, body: By):
    return guarded(desk().offer, key, body.by)


@app.post("/api/batches/{key}/chase", dependencies=[Depends(check_token)])
def chase(key: str, body: By):
    return guarded(desk().chase, key, body.by)


@app.post("/api/batches/{key}/letter", dependencies=[Depends(check_token)])
def new_letter(key: str, body: By):
    return guarded(desk().draft_letter, key, by=body.by)


@app.get("/api/workshops", dependencies=[Depends(check_token)])
def workshops():
    world = desk().world()
    return jsonable_encoder([ops.workshop_view(world, wid) for wid in world.base])


@app.get("/api/workshops/{wid}", dependencies=[Depends(check_token)])
def workshop(wid: str):
    world = desk().world()
    return guarded(lambda: {**ops.workshop_view(world, wid), "jobs": [ops.job_view(j, world.today) for j in ops.open_jobs(world, wid)]})


@app.get("/api/threads", dependencies=[Depends(check_token)])
def threads():
    return jsonable_encoder(ops.thread_summaries(desk().world()))


@app.get("/api/snapshot", dependencies=[Depends(check_token)])
def snapshot():
    """Everything the phone's main screens draw, in one answer, so the phone can tell at once if anything changed."""
    return {"today": today(), "jobs": batches(), "threads": threads(), "requests": requests()}


@app.get("/api/threads/{party}", dependencies=[Depends(check_token)])
def thread(party: str):
    return guarded(desk().thread, party)


@app.post("/api/threads/{party}/messages", dependencies=[Depends(check_token)])
def send_message(party: str, body: Words):
    return guarded(desk().say, party, body.text, by=body.by)


@app.get("/api/incidents/{incident_id}", dependencies=[Depends(check_token)])
def incident(incident_id: str):
    return guarded(desk().incident, incident_id)


@app.post("/api/incidents/{incident_id}/approve", dependencies=[Depends(check_token)])
def approve(incident_id: str, body: Approval):
    return guarded(desk().approve, incident_id, body.by, body.choices)


@app.post("/api/incidents/{incident_id}/dismiss", dependencies=[Depends(check_token)])
def dismiss(incident_id: str, body: By):
    return guarded(desk().dismiss, incident_id, body.by)


@app.get("/api/letters/{letter_id}", dependencies=[Depends(check_token)])
def letter(letter_id: str):
    return guarded(desk().letter, letter_id)


@app.post("/api/letters/{letter_id}/send", dependencies=[Depends(check_token)])
def send_letter(letter_id: str, body: Letter):
    return guarded(desk().send_letter, letter_id, body.text, body.by, body.acknowledged)


@app.get("/api/trail", dependencies=[Depends(check_token)])
def trail():
    """Newest first: every decision and everything that followed, in plain words."""
    world = desk().world()
    out = []
    for job in world.jobs.values():
        out += [{**entry, "order_id": job["order_id"], "key": job["key"]} for entry in job["log"]]
    for item in world.incidents.values():
        out.append({"at": item["at"], "on": None, "label": "Incident", "detail": item["summary"], "by": None, "order_id": None, "key": None})
        if item["resolution"]:
            out.append({"at": item["resolution"]["at"], "on": None, "label": "Plan approved" if item["status"] == "approved" else "Dismissed",
                        "detail": item["summary"], "by": item["resolution"].get("by"), "order_id": None, "key": None})
    for item in world.letters.values():
        if item["status"] == "sent":
            out.append({"at": item["sent_at"], "on": None, "label": "Client told" if item.get("delivered") else "Notice saved, client not on Telegram", "detail": item["customer"], "by": item.get("sent_by"), "order_id": item["order_id"], "key": item["job"]})
    return jsonable_encoder(sorted(out, key=lambda e: e["at"] or "", reverse=True)[:120])


@app.post("/api/roleplay/inbound", dependencies=[Depends(check_token)])
def roleplay_inbound(body: Inbound):
    """The other side of the conversation, for rehearsal: the same path as a real Telegram message."""
    return guarded(desk().inbound, body.party, body.text, channel="roleplay")      # Always in the role-played party's name.


@app.post("/api/roleplay/tap", dependencies=[Depends(check_token)])
def roleplay_tap(body: Tap):
    return guarded(desk().job_tap, body.action, body.key, body.by, channel="roleplay", reason=body.reason)


@app.get("/api/reasons", dependencies=[Depends(check_token)])
def reasons():
    return {"decline": list(control.DECLINE_REASONS)}


@app.post("/api/perf", dependencies=[Depends(check_token)])
async def perf(request: Request):
    """Timings from a test build. Kept apart from the records, so they never reach a screen."""
    body = await request.json()
    with PERF_LOG.open("a", encoding="utf-8") as stream:
        for entry in body.get("entries", []):
            stream.write(json.dumps({"at": ops.now(), **entry}) + "\n")
    return {"ok": True}


@app.get("/api/orders", dependencies=[Depends(check_token)])
def orders():
    return guarded(desk().order_book)


@app.post("/api/requests/new", dependencies=[Depends(check_token)])
def new_request(body: NewRequest):
    return guarded(desk().new_request, **body.model_dump())


@app.get("/api/automations", dependencies=[Depends(check_token)])
def automations():
    return guarded(desk().automations)


@app.post("/api/automations/{name}", dependencies=[Depends(check_token)])
def set_automation(name: str, body: Switch):
    return guarded(desk().set_automation, name, body.on, by=body.by)


@app.post("/api/automations/{name}/run", dependencies=[Depends(check_token)])
def run_automation(name: str):
    return guarded(desk().run_automation, name)


@app.post("/api/demo/reset", dependencies=[Depends(check_token)])
def demo_reset():
    return guarded(desk().reset_demo)


@app.post("/api/clock", dependencies=[Depends(check_token)])
def clock(body: Clock):
    return guarded(desk().set_clock, body.today)


def _latest(rows: list[dict]) -> dict | None:
    """The newest event that a person would want to hear about, for the phone's banner."""
    for row in reversed(rows):
        if row["kind"] == "message" and row["direction"] == "in":
            return {"kind": "message", "party": row["party"], "title": row["author"], "text": row["text"]}
        if row["kind"] == "incident":
            return {"kind": "incident", "id": row["id"], "title": row["summary"], "text": row.get("detail", "")}
    return None


def stamp(control_: control.Control) -> tuple:
    """Changes whenever the desk or the bot has written anything."""
    paths = (control_.ops_path, control_.decisions_path or Path("records/decisions.jsonl"), control_.path_received())
    return tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in paths)


@app.get("/api/stream", dependencies=[Depends(check_token)])
async def stream():
    """Server-sent events: 'something changed', so the phone refetches. Watches the log files, so the bot's writes count too."""
    control_ = desk()

    async def events():
        seen, count = stamp(control_), len(ops.rows(control_.ops_path))
        yield "event: ready\ndata: {}\n\n"
        beats = 0
        while True:
            await asyncio.sleep(0.2)
            beats += 1
            current = stamp(control_)
            if current != seen:
                seen = current
                rows = ops.rows(control_.ops_path)
                news, count = rows[count:], len(rows)     # Only what is new: your own action should not replay an old message.
                yield f"event: change\ndata: {json.dumps(_latest(news) or {}, ensure_ascii=False)}\n\n"
            elif beats % 25 == 0:       # Every 5 s, so a phone notices a dead link within seconds.
                yield ": still here\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.exception_handler(HTTPException)
async def plain_errors(_, error: HTTPException):
    return JSONResponse({"detail": error.detail}, status_code=error.status_code)


def make_control() -> control.Control:
    status = rehearsal.live_status()   # Loads .env for the running process; no value leaves it.
    source = os.environ.get("THREADLINE_READING", "live" if status["ready"] else "fixture")
    partner_call = (lambda prompt, text: intake._call_llm(prompt, text, schema=partners.SCHEMA)) if status["ready"] else None
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    transport = telegram_bot.ChatTransport(telegram_bot.TelegramAPI(token)) if token else None
    return control.Control(demo=os.environ.get("THREADLINE_MODE", "demo") != "live", transport=transport, source=source, partner_call=partner_call,
                           translator=(lambda prompt, text: intake._call_llm(prompt, text, schema=partners.TRANSLATION)) if status["ready"] else None,
                           notifier=lambda text: threading.Thread(target=push.alert, args=(text,), daemon=True).start())


def run_bot(control_: control.Control) -> None:
    allowed = {int(x) for x in os.environ.get("TELEGRAM_ALLOWED_CHATS", "").replace(" ", "").split(",") if x}
    api = telegram_bot.TelegramAPI(os.environ["TELEGRAM_BOT_TOKEN"])
    bot = telegram_bot.DispatchBot(api, allowed_chats=allowed, source=control_.source, control=control_)
    bot.log_path = control_.decisions_path
    print(f"Telegram connected. Authorised chats: {sorted(allowed) or 'none yet (send /chatid)'}", flush=True)
    telegram_bot.poll(bot)


def run_rules(control_: control.Control) -> None:
    """The switched-on automations, checked every half minute for as long as the desk runs."""
    while True:
        time.sleep(30)
        try:
            control_.automate()
        except Exception as error:
            print(f"Automations stopped for this pass: {error}", flush=True)


def run_island(control_: control.Control) -> None:
    """Sends any stage change to the phones watching that batch, for as long as the desk runs."""
    seen = None
    while True:
        time.sleep(1)
        try:
            current = stamp(control_)
            if current != seen and push.tracked:
                seen = current
                push.sync(control_.world())
        except Exception as error:
            print(f"Island updates stopped for this pass: {error}", flush=True)


def main():
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", action="store_true", help="also listen on the local network (needs THREADLINE_API_TOKEN)")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument("--check-push", action="store_true", help="ask Apple whether the Dynamic Island key works, then stop")
    args = parser.parse_args()
    if args.check_push:
        print(push.check())
        return
    saved = ROOT / "ios" / ".desk_token"   # Git-ignored; the same token a test phone build carries.
    if args.lan and not os.environ.get("THREADLINE_API_TOKEN") and saved.exists():
        os.environ["THREADLINE_API_TOKEN"] = saved.read_text().strip()
    if args.lan and not os.environ.get("THREADLINE_API_TOKEN"):
        sys.exit("Set THREADLINE_API_TOKEN first, so nobody else on the network can use this desk.")
    global desk_control
    desk_control = make_control()
    if desk_control.transport.connected:
        threading.Thread(target=run_bot, args=(desk_control,), daemon=True).start()
    threading.Thread(target=run_rules, args=(desk_control,), daemon=True).start()
    threading.Thread(target=run_island, args=(desk_control,), daemon=True).start()
    threading.Thread(target=importlib.import_module, args=("anthropic",), daemon=True).start()   # Loaded now, so the first request is not the slow one.
    health_ = desk_control.health()
    print(f"Threadline API on port {args.port}. Reading: {health_['source']}. Workshop replies read by: {health_['reader']}. Telegram: {health_['telegram']}.", flush=True)
    uvicorn.run(app, host="0.0.0.0" if args.lan else "127.0.0.1", port=args.port, log_level="warning", timeout_keep_alive=75)


if __name__ == "__main__":
    main()
