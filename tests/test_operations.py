"""Sprint 3: the two-way loop with workshops and clients (ops.py, partners.py, recovery.py, control.py)."""

from datetime import date, datetime, timedelta
import json
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import jwt
import pytest

import control
import intake
import island
import ops
import partners
import telegram_bot


class Chat:
    connected = True

    def __init__(self):
        self.sent = []

    def send(self, binding, text, buttons=None):
        self.sent.append((binding["chat_id"], text, buttons))
        return True


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(control.inbox_store, "PATH", tmp_path / "messages.jsonl")
    d = control.Control(demo=True, source="fixture", decisions_path=tmp_path / "rehearsal_decisions.jsonl", ops_path=tmp_path / "ops.jsonl",
                        received=tmp_path / "received.jsonl", transport=Chat())
    d.reset_demo()
    return d


def busiest(d):
    world = d.world()
    return max(world.base, key=lambda wid: len(ops.open_jobs(world, wid)))


# Reading a reply ------------------------------------------------------------------

WEDNESDAY = date(2026, 4, 1)


@pytest.mark.parametrize("phrase, expected", [
    ("Monday", date(2026, 4, 6)), ("next monday", date(2026, 4, 6)), ("tomorrow", date(2026, 4, 2)), ("Wednesday", date(2026, 4, 8)),
    ("in 3 days", date(2026, 4, 4)), ("in two days", date(2026, 4, 3)), ("8 April", date(2026, 4, 8)), ("Apr 8", date(2026, 4, 8)),
    ("end of the week", date(2026, 4, 3)), ("next week", date(2026, 4, 6)), ("soon", None), ("Monday or Tuesday", None),
])
def test_python_works_out_the_date(phrase, expected):
    assert partners.read_date(phrase, WEDNESDAY) == expected


@pytest.mark.parametrize("text, kind", [
    ("Accepted, thanks", "accepts"), ("Sorry we cannot take this one, too busy", "declines"), ("Power cut, we are closed till Monday", "closed"),
    ("We are back to work", "reopened"), ("Need 2 more days for ORD-041", "delay"), ("Rate is going up, 1.8 per piece", "price_change"),
    ("We can only do 90 a day this week", "capacity_change"), ("Batch is finished", "ready"), ("Shipped this morning", "shipped"),
    ("Do you want it folded?", "question"), ("The weather is lovely", "other"),
])
def test_the_rule_reader_covers_the_common_replies(text, kind):
    assert partners.rule_reply(text)["kind"] == kind


def model_says(**fields):
    base = {"kind": "other", "order_id": None, "date_text": None, "delay_days": None, "capacity_per_day": None, "price_per_piece": None, "reason": None}
    return lambda prompt, text: intake.LLMReply(json.dumps({**base, **fields}), {})


def test_a_number_the_sender_never_wrote_is_dropped():
    reading = partners.read("We will be a bit late", role="workshop", today=WEDNESDAY, order_ids=[], call=model_says(kind="delay", delay_days=4))
    assert reading["delay_days"] is None and reading["checks"][0]["check"] == "delay_days"


def test_a_spelled_number_is_kept():
    reading = partners.read("Two more days please", role="workshop", today=WEDNESDAY, order_ids=[], call=model_says(kind="delay", delay_days=2))
    assert reading["delay_days"] == 2


def test_an_order_they_do_not_hold_and_never_wrote_is_dropped():
    reading = partners.read("Running late", role="workshop", today=WEDNESDAY, order_ids=["ORD-041"], call=model_says(kind="delay", order_id="ORD-099"))
    assert reading["order_id"] is None


def test_a_broken_model_reply_falls_back_to_rules_and_says_so():
    reading = partners.read("Accepted", role="workshop", today=WEDNESDAY, order_ids=[], call=lambda p, t: intake.LLMReply("not json", {}))
    assert reading["source"] == "rules" and reading["kind"] == "accepts" and reading["checks"][0]["check"] == "model"


def test_a_message_the_reader_cannot_place_goes_to_a_person():
    assert partners.read("Call me", role="workshop", today=WEDNESDAY, order_ids=[])["needs_person"]


# The loop --------------------------------------------------------------------------

def test_confirming_sends_the_job_to_the_workshops_chat(desk):
    world = desk.world()
    desk.bind("W6", 111)
    card = desk.evaluate(next(m for m in desk.messages if m.startswith("R09 ")), request="R09")
    assert card["card"] == "recommendation"
    result = desk.confirm(card["token"], "Aditya")
    assert result["job"]["stage"] == "offered"
    if result["job"]["workshop_id"] == "W6":
        assert "ORD-045" in desk.transport.sent[-1][1]
    assert world.today == date(2026, 4, 1)
    assert "R09" not in [r["id"] for r in desk.waiting_requests()]


def test_a_second_confirm_writes_nothing_new(desk):
    card = desk.evaluate(next(m for m in desk.messages if m.startswith("R09 ")))
    desk.confirm(card["token"])
    jobs = len(desk.world().jobs)
    desk.confirm(card["token"])
    assert len(desk.world().jobs) == jobs


def test_a_tap_moves_the_job_without_any_reading(desk):
    key = next(j["key"] for j in desk.world().jobs.values() if j["stage"] == "offered")
    desk.job_tap("accepts", key, "Owner")
    assert desk.job(key)["stage"] == "accepted"


def test_a_closure_changes_nothing_until_the_dispatcher_approves(desk):
    wid = busiest(desk)
    before = desk.world()
    desk.inbound(wid, "Power cut, we are closed till Monday", by="Owner")
    world = desk.world()
    assert world.workshops[wid].status == "ACTIVE" and world.queues == before.queues
    [incident] = [i for i in world.incidents.values() if i["status"] == "open"]
    assert incident["until"] == "2026-04-06" and incident["changes"] == {"status": "SUSPENDED"}
    desk.approve(incident["id"], "Aditya")
    world = desk.world()
    assert world.workshops[wid].status == "SUSPENDED"
    assert world.incidents[incident["id"]]["status"] == "approved"


def test_a_closure_ends_on_its_own_date(desk):
    wid = busiest(desk)
    desk.inbound(wid, "Closed till Monday", by="Owner")
    incident = next(iter(desk.world().incidents.values()))
    desk.approve(incident["id"])
    desk.set_clock(date(2026, 4, 6))
    assert desk.world().workshops[wid].status == "ACTIVE"


def test_the_plan_keeps_work_in_production_where_it_is(desk):
    wid = busiest(desk)
    desk.inbound(wid, "Closed till Monday", by="Owner")
    incident = next(iter(desk.world().incidents.values()))
    plan = desk.incident(incident["id"])["plan"]
    assert plan["rows"]
    for row in plan["rows"]:
        if row["stage"] == "in_production":
            assert row["action"] == "wait"
        if row["action"] == "move":
            assert row["move"]["workshop_id"] != wid and row["why"]


def test_moved_batches_leave_one_queue_and_join_the_other(desk):
    wid = busiest(desk)
    desk.inbound(wid, "Closed till Monday", by="Owner")
    incident = next(iter(desk.world().incidents.values()))
    plan = desk.incident(incident["id"])["plan"]
    moves = [r for r in plan["rows"] if r["action"] == "move"]
    assert moves
    before = desk.world()
    desk.approve(incident["id"])
    after = desk.world()
    assert after.queues[wid] < before.queues[wid]
    for row in moves:
        job = after.jobs[row["job"]]
        assert job["workshop_id"] == row["move"]["workshop_id"] and job["moved_from"] == before.jobs[row["job"]]["workshop"] and job["stage"] == "offered"


def test_a_vague_closure_opens_the_incident_and_asks_when(desk):
    wid = busiest(desk)
    desk.inbound(wid, "We have had a fire, closed for now", by="Owner")
    world = desk.world()
    assert any(m["automatic"] and "reopen" in m["text"] for m in world.threads[wid] if m["direction"] == "out")
    incident = next(iter(world.incidents.values()))
    assert all(row["action"] in ("move", "person") or row["stage"] == "in_production" for row in desk.incident(incident["id"])["plan"]["rows"])


def test_a_delay_asks_for_a_date_when_none_is_given(desk):
    wid = busiest(desk)
    order = ops.open_jobs(desk.world(), wid)[0]["order_id"]
    desk.inbound(wid, f"{order} is running late", by="Owner")
    world = desk.world()
    assert not world.incidents and "What date" in world.threads[wid][-1]["text"]


def test_a_delay_past_the_customer_date_drafts_a_client_notice(desk):
    world = desk.world()
    job = next(j for j in ops.open_jobs(world) if j["stage"] == "in_production" and j["customer"])
    desk.inbound(job["workshop_id"], f"{job['order_id']} will come back on 30 April", by="Owner")
    incident = next(iter(desk.world().incidents.values()))
    desk.approve(incident["id"])
    world = desk.world()
    assert world.jobs[job["key"]]["back"] == date(2026, 4, 30)
    [letter] = world.letters.values()
    assert letter["status"] == "draft" and job["customer"] in letter["text"] and "30 Apr 2026" in letter["text"]
    assert desk.letter(letter["id"])["check"]["passed"]


def test_a_client_notice_with_a_changed_date_stops_for_a_person(desk):
    world = desk.world()
    job = next(j for j in ops.open_jobs(world) if j["stage"] == "in_production" and j["customer"])
    desk.inbound(job["workshop_id"], f"{job['order_id']} will come back on 30 April", by="Owner")
    desk.approve(next(iter(desk.world().incidents.values()))["id"])
    letter = next(iter(desk.world().letters.values()))
    edited = letter["text"].replace("30 Apr 2026", "2 Apr 2026")
    assert desk.send_letter(letter["id"], edited) == {"sent": False, "unmatched": ["2 Apr 2026"]}
    assert desk.send_letter(letter["id"], edited, acknowledged=True)["sent"]
    assert desk.world().letters[letter["id"]]["status"] == "sent"


def test_an_unconnected_party_is_marked_not_delivered(desk):
    message = desk.say("W3", "Hello", by="Aditya")
    assert message["delivered"] is False and message["channel"] == "app"


def test_a_workshop_never_sees_another_partys_chat(desk):
    desk.bind("W1", 111)
    desk.bind("W2", 222)
    desk.say("W2", "Hello", by="Aditya")
    assert [chat for chat, _, _ in desk.transport.sent] == [222]


def test_price_change_needs_approval_and_then_changes_the_estimates(desk):
    desk.inbound("W3", "Rates are going up, 1.1 per piece from now", by="Owner")
    world = desk.world()
    assert world.workshops["W3"].cost == 0.8
    desk.approve(next(iter(world.incidents.values()))["id"])
    assert desk.world().workshops["W3"].cost == 1.1


def test_speaking_routes_without_the_model(desk):
    assert desk.speak("brief me")["card"] == "answer"
    assert desk.speak("what's due back tomorrow")["card"] == "answer"
    assert desk.speak("how is SteadyHands")["title"] == "SteadyHands"
    draft = desk.speak("tell Quick Stitch we need it by Friday")
    assert draft["card"] == "draft" and draft["party"] == "W1" and draft["text"] == "We need it by Friday"
    job = ops.open_jobs(desk.world())[0]
    number = int(job["order_id"].split("-")[1])
    assert desk.speak(f"order {number} came back")["action"] == "received"


def test_spoken_order_numbers_become_order_ids():
    assert control.spoken("order 45 needs a home") == "ORD-045 needs a home"
    assert control.spoken("ORD 045, 150 vests") == "ORD-045, 150 vests"
    assert control.spoken("order number 7") == "ORD-007"


def test_the_reset_keeps_chat_connections(desk):
    desk.bind("W1", 111)
    desk.reset_demo()
    assert "W1" in desk.world().bindings


# Telegram ---------------------------------------------------------------------------

class FakeBotAPI:
    def __init__(self):
        self.sent, self.edits, self.answers = [], [], []

    def send(self, chat_id, text, *, reply_to=None, buttons=None, thread_id=None):
        self.sent.append({"chat": chat_id, "text": text, "buttons": buttons, "thread": thread_id})
        return {"message_id": len(self.sent)}

    def edit(self, chat_id, message_id, text, *, buttons=None):
        self.edits.append({"text": text, "buttons": buttons})

    def answer(self, callback_id, text=None):
        self.answers.append(text)

    def typing(self, chat_id):
        pass


def bot_for(d):
    api = FakeBotAPI()
    d.transport = telegram_bot.ChatTransport(api)
    return telegram_bot.DispatchBot(api, allowed_chats={-100}, source="fixture", control=d), api


def message(text, thread=None):
    return {"message": {"message_id": 9, "chat": {"id": -100}, "text": text, "message_thread_id": thread, "from": {"first_name": "Raju"}}}


def test_iam_binds_a_topic_and_jobs_go_to_that_topic(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Quick Stitch", thread=7))
    assert desk.world().bindings["W1"] == {"chat_id": -100, "thread_id": 7}
    key = next(k for k, j in desk.world().jobs.items() if j["workshop_id"] == "W1")
    desk.offer(key)
    last = api.sent[-1]
    assert last["thread"] == 7 and "Can you take it?" in last["text"]
    assert {"Accept", "Cannot take it"} == {b["text"] for row in last["buttons"] for b in row}


def test_a_workshop_tap_updates_its_card_and_the_job(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam QuickStitch", thread=7))
    key = next(k for k, j in desk.world().jobs.items() if j["workshop_id"] == "W1")
    desk.offer(key)
    bot.handle({"callback_query": {"id": "1", "data": f"j:accepts:{key}", "from": {"first_name": "Raju"},
                                   "message": {"message_id": 3, "text": "New job", "chat": {"id": -100}}}})
    assert desk.job(key)["stage"] == "accepted"
    assert api.edits[-1]["buttons"][0][0]["text"] == "Started"


def test_a_message_in_a_workshop_topic_is_read_as_a_reply_not_a_request(desk):
    bot, _ = bot_for(desk)
    bot.handle(message("/iam QuickStitch", thread=7))
    bot.handle(message("Power cut, closed till Monday", thread=7))
    world = desk.world()
    assert any(i["workshop_id"] == "W1" for i in world.incidents.values())
    assert not bot.pending


def test_a_chat_outside_the_allowed_list_cannot_bind(desk):
    bot, _ = bot_for(desk)
    update = message("/iam QuickStitch")
    update["message"]["chat"]["id"] = -999
    bot.handle(update)
    assert not desk.world().bindings


def test_an_order_cannot_go_out_twice(desk):
    line = next(m for m in desk.messages if "ORD-045" in m)
    rid = line.split()[0]
    first = desk.evaluate(line, by="Aditya")                        # Said out loud, so not tied to the chat line.
    assert first["can_confirm"], first
    workshop = first["chosen"]["name"]
    desk.confirm(first["token"], by="Aditya")
    assert rid not in {r["id"] for r in desk.waiting_requests()}    # The chat line naming it is cleared too.
    second = desk.evaluate(line, by="Aditya")
    assert second["can_confirm"] is False and second["block_reason"] == f"ORD-045 is already with {workshop}."
    assert second["headline"] == "Already sent"
    with pytest.raises(ValueError, match="already with"):
        desk.confirm(second["token"], by="Aditya")


@pytest.mark.parametrize("connected", [True, False])
def test_a_notice_records_whether_it_reached_the_client(desk, connected):
    job = next(j for j in desk.world().jobs.values() if j["customer"])
    if connected:
        desk.bind(ops.CLIENT + job["customer"], 501)
    letter = desk.draft_letter(job["key"])
    desk.send_letter(letter["id"], acknowledged=True)
    assert desk.world().letters[letter["id"]]["delivered"] is connected


# Automations ------------------------------------------------------------------------

def silent_job(d):
    return next(j for j in d.world().jobs.values() if ops.is_silent(j, d.world().today))


def test_a_reminder_clears_the_silent_card(desk):
    job = silent_job(desk)
    desk.chase(job["key"])
    assert not any(c["kind"] == "silent" and c["target"]["id"] == job["key"] for c in ops.attention(desk.world()))


def test_rules_stay_off_until_switched_on(desk):
    silent_job(desk)
    assert desk.automate() == []
    assert all(not a["on"] for a in desk.automations())


def test_a_silent_workshop_is_chased_once_and_nothing_else_changes(desk):
    job = silent_job(desk)
    desk.set_automation("chase_silent", True)
    desk.bind(job["workshop_id"], -100, 7)
    assert desk.automate() == [f"{job['workshop']} reminded about {job['order_id']}"]
    assert desk.automate() == []
    after = desk.job(job["key"])
    assert after["stage"] == "offered" and after["back"] == job["back"] and after["workshop_id"] == job["workshop_id"]
    last = desk.world().threads[job["workshop_id"]][-1]
    assert last["automatic"] is True and last["author"] == "Threadline"


def test_the_day_before_check_asks_once(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "in_production")
    desk.set_clock(job["back"] - timedelta(days=1))
    desk.set_automation("check_due", True)
    desk.bind(job["workshop_id"], -100, 7)
    done = desk.automate()
    assert f"{job['workshop']} asked about {job['order_id']}" in done
    assert desk.automate() == []
    assert desk.job(job["key"])["stage"] == "in_production"


def test_the_morning_brief_goes_to_the_team_once_a_day_after_half_past_eight(desk):
    desk.bind(ops.TEAM, 900)
    desk.set_automation("morning_brief", True)
    assert desk.automate(datetime(2026, 4, 1, 8, 29)) == []
    assert desk.automate(datetime(2026, 4, 1, 8, 30)) == ["Brief posted in the team chat"]
    assert desk.automate(datetime(2026, 4, 1, 9, 0)) == []
    chat, text, _ = desk.transport.sent[-1]
    assert chat == 900 and "batches are out" in text


def test_running_the_brief_without_a_team_chat_says_so(desk):
    assert desk.run_automation("morning_brief")["text"] == "The team chat is not connected. Send /iam Team there."


def test_a_reset_switches_every_rule_off(desk):
    desk.set_automation("chase_silent", True)
    desk.reset_demo()
    assert all(not a["on"] for a in desk.automations())


def test_an_unknown_rule_is_refused(desk):
    with pytest.raises(KeyError):
        desk.set_automation("delete_everything", True)


def test_the_team_chat_asks_and_is_not_treated_as_a_workshop(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    assert desk.world().bindings[ops.TEAM] == {"chat_id": -100, "thread_id": 3}
    bot.handle(message("/brief", thread=3))
    assert "batches are out" in api.sent[-1]["text"]
    order = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "in_production")
    bot.handle(message(f"/where {order['order_id']}", thread=3))
    assert order["workshop"] in api.sent[-1]["text"]
    assert ops.TEAM not in desk.world().threads


def test_a_client_chat_cannot_ask_where_a_batch_is(desk):
    bot, api = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["customer"])
    bot.handle(message(f"/iam {job['customer']}", thread=8))
    before = len(api.sent)
    bot.handle(message(f"/where {job['order_id']}", thread=8))
    bot.handle(message("/brief", thread=8))
    assert len(api.sent) == before


# Your own requests ------------------------------------------------------------------

def test_the_order_book_offers_only_orders_with_no_workshop(desk):
    book = desk.order_book()
    out = {j["order_id"] for j in desk.world().jobs.values()}
    assert book["open"] and not out & {o["order_id"] for o in book["open"]}
    assert "Hoodie" in book["products"] and "TrendCart" in book["customers"] and book["priorities"][0] == "Balanced"


def test_a_new_order_joins_the_book_and_the_supplied_file_is_untouched(desk):
    before = len(desk.supplied)
    order = desk.add_order("TrendCart", "Hoodie", 300, date(2026, 4, 20), by="Aditya")
    assert order["order_id"] == "ORD-121" and order["category"] == "TOPS" and len(desk.supplied) == before
    assert "ORD-121" in {o["order_id"] for o in desk.order_book()["open"]}
    assert control.Control(demo=True, source="fixture", decisions_path=desk.decisions_path, ops_path=desk.ops_path, received=desk.received).orders["order_id"].iloc[-1] == "ORD-121"


@pytest.mark.parametrize("fields, message", [(("", "Hoodie", 300, date(2026, 4, 20)), "who the order"), (("TrendCart", "Socks", 300, date(2026, 4, 20)), "product"),
                                             (("TrendCart", "Hoodie", 0, date(2026, 4, 20)), "how many"), (("TrendCart", "Hoodie", 300, date(2026, 4, 1)), "after today")])
def test_a_bad_new_order_is_refused_in_plain_words(desk, fields, message):
    with pytest.raises(ValueError, match=message):
        desk.add_order(*fields)


def test_your_request_stays_in_review_until_a_decision_goes_out(desk, monkeypatch):
    monkeypatch.setattr(desk, "evaluate", lambda text, **kw: {"text": text, **kw})
    order = desk.order_book()["open"][0]
    card = desk.new_request(order_id=order["order_id"], priority="Fastest", note="Keep it with one workshop", by="Aditya")
    assert card["request"] == "A1" and "fastest please" in card["text"] and "Keep it with one workshop" in card["text"]
    first = desk.waiting_requests()[0]
    assert first["id"] == "A1" and first["channel"] == "your request" and first["sender"] == "Aditya"
    desk.log("request_done", line="A1", by="Aditya")
    assert "A1" not in {r["id"] for r in desk.waiting_requests()}


def test_a_new_order_can_be_said_out_loud_and_nothing_is_added_until_you_tap(desk):
    size = len(desk.orders)
    card = desk.speak("300 hoodies for TrendCart, back by 20 April, fastest please")
    assert card["card"] == "action" and card["action"] == "new_order" and len(desk.orders) == size
    assert card["fields"] == {"customer": "TrendCart", "product": "Hoodie", "pieces": 300, "due": date(2026, 4, 20), "priority": "Fastest"}


# Telegram and the phone working together ---------------------------------------------

def test_a_closure_reaches_the_team_chat_and_can_be_approved_there(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    bot.handle(message("/iam QuickStitch", thread=7))
    bot.handle(message("closed till monday", thread=7))
    alert = next(m for m in api.sent if m["buttons"] and m["thread"] == 3)
    assert "QuickStitch reports closed" in alert["text"] and "move to" in alert["text"]
    data = alert["buttons"][0][0]["callback_data"]
    incident = data.split(":")[2]
    assert desk.world().incidents[incident]["status"] == "open"
    bot.handle({"callback_query": {"id": "1", "data": data, "from": {"first_name": "Mei"}, "message": {"message_id": 5, "chat": {"id": -100}, "text": alert["text"]}}})
    assert desk.world().incidents[incident]["status"] == "approved" and "Approved by Mei" in api.edits[-1]["text"]


def test_a_workshop_and_a_client_see_only_their_own_work(desk):
    bot, api = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["customer"] and j["stage"] == "in_production")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    bot.handle(message("/jobs", thread=7))
    assert job["order_id"] in api.sent[-1]["text"] and "✂️" in api.sent[-1]["text"]
    bot.handle(message(f"/iam {job['customer']}", thread=8))
    bot.handle(message("/status", thread=8))
    reply = api.sent[-1]["text"]
    assert job["order_id"] in reply and not any(w.name in reply for w in desk.base.values())


def test_a_tapped_decline_opens_a_plan_and_the_card_shows_the_status(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    desk.job_tap("declines", job["key"], "Owner")
    kinds = [c["kind"] for c in ops.attention(desk.world())]
    assert "incident" in kinds and "declined" not in kinds


def test_a_status_line_matches_the_app(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "in_production")
    assert ops.stage_line(job) == "✂️ In production ▰▰▰▱▱"


def test_a_supergroup_topic_gets_a_link_and_a_private_chat_does_not():
    assert ops.telegram_link({"chat_id": -1001234567890, "thread_id": 7}) == "https://t.me/c/1234567890/7"
    assert ops.telegram_link({"chat_id": 555}) is None and ops.telegram_link(None) is None


def test_an_order_added_on_the_phone_is_known_in_telegram(desk):
    bot, _ = bot_for(desk)
    desk.add_order("TrendCart", "Hoodie", 300, date(2026, 4, 20), by="Aditya")
    assert "ORD-121" in set(bot.orders["order_id"])


def test_the_chat_cannot_send_an_order_the_phone_already_sent(desk):
    bot, api = bot_for(desk)
    job = next(iter(ops.open_jobs(desk.world())))
    item = type("Item", (), {"preview": type("Preview", (), {"token": "other", "response": type("Response", (), {"parsed_request": type("Parsed", (), {"order_id": job["order_id"]})})})})
    assert bot.already_out(item, "1") is True
    assert api.answers[-1] == f"{job['order_id']} is already with {job['workshop']}."


def test_a_decline_is_described_as_a_decline(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    desk.job_tap("declines", job["key"], "Owner")
    world = desk.world()
    incident = next(i for i in world.incidents.values() if i["type"] == "declined")
    assert incident["detail"] == "It needs a new workshop."
    row = desk.incident(incident["id"])["plan"]["rows"][0]
    assert row["stay"]["note"] == "Cannot take it" and "reopens" not in row["why"]


def test_an_overdue_card_says_its_goods_properly(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "in_production")
    desk.set_clock(job["back"] + timedelta(days=1))
    card = next(c for c in ops.attention(desk.world()) if c["kind"] == "overdue" and c["target"]["id"] == job["key"])
    assert card["detail"] == f"{job['workshop']}, {control.goods(job)}"
    assert card["detail"].endswith("s")


def test_a_second_iam_changes_who_a_chat_speaks_for(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam FreshStart"))
    bot.handle(message("/iam Quick Stitch"))
    assert desk.party_for(-100) == "W1" and "W8" not in desk.world().bindings
    bot.handle(message("/jobs"))
    assert all(any(j["order_id"] in sent["text"] for sent in api.sent) for j in ops.open_jobs(desk.world(), "W1"))


def test_the_same_message_twice_is_read_once_and_opens_one_problem(desk):
    calls = []

    def model_is_down(prompt, text):
        calls.append(text)
        raise intake.IntakeError("no model in this test")

    desk.partner_call = model_is_down
    for _ in range(6):
        desk.inbound("W1", "Power cut, closed till Monday", channel="roleplay")
    world = desk.world()
    assert len(calls) == 1
    assert sum(m["text"].startswith("Power cut") for m in world.threads["W1"]) == 1
    assert sum(i["status"] == "open" for i in world.incidents.values()) == 1


def test_the_same_closure_in_other_words_is_still_one_problem(desk):
    desk.inbound("W1", "Power cut, closed till Monday", channel="roleplay")
    desk.inbound("W1", "Sorry, we are closed until Monday", channel="roleplay")
    assert sum(i["status"] == "open" for i in desk.world().incidents.values()) == 1
    assert sum(m["direction"] == "in" and "Monday" in m["text"] for m in desk.world().threads["W1"]) == 2


def test_two_workshops_saying_the_same_thing_are_two_problems(desk):
    desk.inbound("W1", "Power cut, closed till Monday", channel="roleplay")
    desk.inbound("W2", "Power cut, closed till Monday", channel="roleplay")
    assert sum(i["status"] == "open" for i in desk.world().incidents.values()) == 2


def test_the_same_words_later_on_are_a_new_message(desk, monkeypatch):
    desk.inbound("W1", "Any news?", channel="roleplay")
    monkeypatch.setattr(ops, "age_seconds", lambda _: control.REPEAT_SECONDS + 1)
    desk.inbound("W1", "Any news?", channel="roleplay")
    assert sum(m["text"] == "Any news?" for m in desk.world().threads["W1"]) == 2


# A dropped network ------------------------------------------------------------------

class Stop(BaseException):
    pass


def test_a_dropped_connection_does_not_end_the_bot(desk, monkeypatch):
    bot, api = bot_for(desk)
    seen = []

    def updates(_offset):
        seen.append(1)
        if len(seen) == 1:
            raise ConnectionResetError(54, "Connection reset by peer")
        raise Stop

    api.updates = updates
    monkeypatch.setattr(telegram_bot.time, "sleep", lambda _: None)
    with pytest.raises(Stop):
        telegram_bot.poll(bot)
    assert len(seen) == 2


def test_a_drop_while_sending_keeps_the_message_and_marks_it_undelivered(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Quick Stitch"))

    def drop(*_, **__):
        raise ConnectionResetError(54, "Connection reset by peer")

    api.send = drop
    sent = desk.say("W1", "How is it looking?", by="Aditya")
    assert sent["delivered"] is False
    assert desk.world().threads["W1"][-1]["text"] == "How is it looking?"


def test_the_morning_brief_waits_for_a_team_chat(desk):
    desk.set_automation("morning_brief", True)
    assert desk.automate(datetime(2026, 4, 1, 9, 0)) == []
    desk.bind(ops.TEAM, 900)
    assert desk.automate(datetime(2026, 4, 1, 9, 1)) == ["Brief posted in the team chat"]



def test_one_chat_can_play_any_workshop_and_its_waiting_offers_follow(desk):
    bot, api = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    assert any("Can you take it?" in sent["text"] and job["order_id"] in sent["text"] and sent["buttons"] for sent in api.sent)
    bot.handle(message("/iam", thread=7))
    picks = [b["callback_data"] for row in api.sent[-1]["buttons"] for b in row]
    assert f"b:{job['workshop_id']}" in picks and f"b:{ops.TEAM}" in picks
    other = next(wid for wid in desk.base if wid != job["workshop_id"])
    bot.handle({"callback_query": {"id": "1", "data": f"b:{other}", "from": {"first_name": "Raju"},
                                   "message": {"message_id": 3, "text": "Who?", "chat": {"id": -100}, "message_thread_id": 7}}})
    assert desk.party_for(-100, 7) == other


def test_jobs_gives_each_open_batch_a_card_that_moves_it_on(desk):
    bot, api = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "in_production")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    bot.handle(message("/jobs", thread=7))
    card = next(sent for sent in api.sent if job["order_id"] in sent["text"] and sent["buttons"])
    tap = card["buttons"][0][0]
    assert tap["text"] == "Completed"
    bot.handle({"callback_query": {"id": "1", "data": tap["callback_data"], "from": {"first_name": "Raju"},
                                   "message": {"message_id": 3, "text": card["text"], "chat": {"id": -100}}}})
    assert desk.job(job["key"])["stage"] == "ready"
    assert job["order_id"] in api.edits[-1]["text"] and api.edits[-1]["buttons"][0][0]["text"] == "Shipped"


def test_the_spoken_brief_reads_like_a_person_talking(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    desk.job_tap("declines", job["key"], "Owner")
    spoken = ops.spoken_brief(desk.world())
    assert spoken.split()[0] in ("Morning.", "Afternoon.", "Evening.")
    assert "ORD-" not in spoken and "cannot" not in spoken
    assert not any(ch.isupper() for name in ("QuickStitch", "FreshStart") if name in spoken for ch in name[1:])


# The Dynamic Island through Apple's push service ------------------------------------

class Apple:
    """Answers like Apple's server: each reply is a status and a reason, then success."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def post(self, url, json, headers):
        self.calls.append({"url": url, "aps": json["aps"], "headers": headers})
        status, reason = self.replies.pop(0) if self.replies else (200, None)
        return SimpleNamespace(status_code=status, content=b"x" if reason else b"", json=lambda: {"reason": reason})


@pytest.fixture
def pushed(tmp_path):
    """An Island with a throwaway signing key, watching a batch that is waiting on a workshop."""
    private = ec.generate_private_key(ec.SECP256R1())
    (tmp_path / "AuthKey_TESTKEY123.p8").write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return SimpleNamespace(tokens=tmp_path / "island.json", keys=tmp_path, public=private.public_key())


def watching(desk, pushed, *replies):
    apple = Apple(*replies)
    watcher = island.Island(tokens=pushed.tokens, keys=pushed.keys, client=apple)
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    watcher.watch("ab" * 32, job["key"], ops.island(job))
    return watcher, apple, job


def test_a_stage_change_reaches_the_island_signed_and_in_the_app_s_own_words(desk, pushed):
    watcher, apple, job = watching(desk, pushed)
    watcher.sync(desk.world())
    assert not apple.calls                                  # Nothing has changed yet.
    desk.job_tap("accepts", job["key"], "Owner")
    watcher.sync(desk.world())
    watcher.sync(desk.world())
    assert len(apple.calls) == 1                            # Sent once, not on every pass.
    call = apple.calls[0]
    assert call["url"] == f"https://api.sandbox.push.apple.com/3/device/{'ab' * 32}"
    assert call["headers"]["apns-push-type"] == "liveactivity" and call["headers"]["apns-topic"].endswith(".push-type.liveactivity")
    assert call["aps"]["event"] == "update" and call["aps"]["content-state"] == ops.island(desk.job(job["key"]))
    assert call["aps"]["content-state"]["status"] == "Accepted" and call["aps"]["content-state"]["step"] == 1
    signature = call["headers"]["authorization"].removeprefix("bearer ")
    assert jwt.get_unverified_header(signature)["kid"] == "TESTKEY123"
    assert jwt.decode(signature, pushed.public, algorithms=["ES256"])["iss"] == island.TEAM


def test_a_refusal_shows_as_a_warm_alert_with_sound(desk, pushed):
    watcher, apple, job = watching(desk, pushed)
    desk.job_tap("declines", job["key"], "Owner")
    watcher.sync(desk.world())
    state = apple.calls[0]["aps"]["content-state"]
    assert state["alert"] is True and job["workshop"] in state["status"] and state["step"] == 0
    assert apple.calls[0]["aps"]["alert"]["sound"] == "default"


def test_a_batch_that_has_gone_ends_its_island(desk, pushed):
    watcher, apple, job = watching(desk, pushed)
    desk.reset_demo()
    watcher.tracked["ab" * 32]["job"] = "no-such-batch"
    watcher.sync(desk.world())
    assert apple.calls[0]["aps"]["event"] == "end" and "dismissal-date" in apple.calls[0]["aps"]
    assert not watcher.tracked


def test_a_token_for_the_other_server_is_tried_there_and_a_dead_one_is_dropped(desk, pushed):
    watcher, apple, job = watching(desk, pushed, (400, "BadDeviceToken"))
    desk.job_tap("accepts", job["key"], "Owner")
    watcher.sync(desk.world())
    assert [c["url"].split("/3/")[0] for c in apple.calls] == list(island.SERVERS)
    assert watcher.tracked["ab" * 32]["state"]["status"] == "Accepted"
    desk.job_tap("started", job["key"], "Owner")
    apple.replies = [(410, "Unregistered")]
    watcher.sync(desk.world())
    assert not watcher.tracked


def test_a_failed_push_is_tried_again_on_the_next_pass_and_tokens_survive_a_restart(desk, pushed):
    watcher, apple, job = watching(desk, pushed, (500, "InternalServerError"))
    desk.job_tap("accepts", job["key"], "Owner")
    watcher.sync(desk.world())
    assert watcher.tracked["ab" * 32]["state"]["step"] == 0
    restarted = island.Island(tokens=pushed.tokens, keys=pushed.keys, client=apple)
    restarted.sync(desk.world())
    assert restarted.tracked["ab" * 32]["state"]["step"] == 1


def test_without_a_key_nothing_is_sent(desk, tmp_path):
    apple = Apple()
    watcher = island.Island(tokens=tmp_path / "island.json", keys=tmp_path, client=apple)
    job = next(j for j in ops.open_jobs(desk.world()) if j["stage"] == "offered")
    watcher.watch("ab" * 32, job["key"], ops.island(job))
    desk.job_tap("accepts", job["key"], "Owner")
    watcher.sync(desk.world())
    assert not apple.calls and not watcher.ready() and "No AuthKey" in watcher.check()


# Completed frees the workshop ---------------------------------------------------------

def request(desk):
    return desk.new_request(customer="TrendCart", product="Cardigan", pieces=300, due=date(2026, 4, 20), priority="Fastest")


def test_completed_frees_the_workshop_before_the_batch_is_back(desk):
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-041")
    wid = job["workshop_id"]
    before = desk.world().queues[wid]
    desk.job_tap("started", job["key"], "Raju")
    assert desk.world().queues[wid] == before                # Being sewn still occupies the workshop.
    desk.job_tap("ready", job["key"], "Raju")
    world = desk.world()
    assert world.queues[wid] == pytest.approx(before - job["pieces"] / desk.base[wid].capacity)
    view = ops.workshop_view(world, wid)
    assert view["open_jobs"] == 0 and view["completed"] == 1 and view["pieces_out"] == job["pieces"]
    freed = world.queues[wid]
    desk.job_tap("shipped", job["key"], "Raju")
    assert desk.world().queues[wid] == freed
    desk.mark_received(job["key"])
    assert desk.world().queues[wid] == freed                 # Coming back frees nothing more: it was already free.


def test_a_workshop_finishing_early_changes_the_next_recommendation(desk):
    assert request(desk)["chosen"]["name"] == "FreshStart"
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-041")
    desk.job_tap("ready", job["key"], "Raju")
    after = request(desk)
    assert after["chosen"]["name"] == "Nimble Needle" and str(after["chosen"]["back"]) == "2026-04-05"


def test_a_refused_batch_does_not_sit_in_the_workshop_s_queue(desk):
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-095")
    before = desk.world().queues[job["workshop_id"]]
    desk.job_tap("declines", job["key"], "Raju", reason="No capacity right now")
    assert desk.world().queues[job["workshop_id"]] < before


def test_a_completed_batch_is_not_counted_in_how_much_a_workshop_holds(desk):
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-041")
    before = desk.world().allocator.pieces_by_workshop[job["workshop_id"]]
    desk.job_tap("ready", job["key"], "Raju")
    assert desk.world().allocator.pieces_by_workshop[job["workshop_id"]] == before - job["pieces"]


def test_a_finished_batch_is_not_moved_when_its_workshop_closes(desk):
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-041")
    desk.job_tap("ready", job["key"], "Raju")
    desk.inbound(job["workshop_id"], "Power cut, closed till Monday")
    incident = next(i for i in desk.world().incidents.values() if i["status"] == "open")
    row = next(r for r in desk.incident(incident["id"])["plan"]["rows"] if r["job"] == job["key"])
    assert row["action"] != "move" and row["why"] == "Already finished, so it stays."


# Reasons, from both sides ---------------------------------------------------------------

def tap(bot, data, thread=7, text="ORD, goods. Back soon."):
    bot.handle({"callback_query": {"id": "1", "data": data, "from": {"first_name": "Raju"}, "message": {"message_id": 3, "text": text, "chat": {"id": -100}, "message_thread_id": thread}}})


def test_a_workshop_says_why_it_cannot_take_a_job_and_the_team_hears_why(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-095")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    offer = next(s for s in api.sent if "ORD-095" in s["text"] and s["buttons"])
    assert offer["buttons"][0][1]["callback_data"] == f"j:why:{job['key']}"
    tap(bot, f"j:why:{job['key']}")
    assert desk.job(job["key"])["stage"] == "offered"          # Nothing is recorded until there is a reason.
    assert [b["text"] for row in api.edits[-1]["buttons"] for b in row] == [*control.DECLINE_REASONS, "Back"]
    tap(bot, f"j:card:{job['key']}")
    assert api.edits[-1]["buttons"][0][0]["text"] == "Accept"
    tap(bot, f"j:no0:{job['key']}")
    world = desk.world()
    incident = next(i for i in world.incidents.values() if i["status"] == "open")
    assert world.jobs[job["key"]]["stage"] == "declined" and incident["reason"] == "No capacity right now"
    assert world.threads[job["workshop_id"]][-1]["text"].endswith(": No capacity right now")
    alert = next(s for s in api.sent if s["thread"] == 3 and "cannot take" in s["text"])
    assert "Reason given: No capacity right now" in alert["text"]


def test_a_workshop_can_escalate_a_problem_from_the_job_card(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-063")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    tap(bot, f"j:problem:{job['key']}")
    tap(bot, f"j:fix0:{job['key']}")
    incident = next(i for i in desk.world().incidents.values() if i["status"] == "open")
    assert incident["reason"] == "Machine down" and desk.job(job["key"])["stage"] == "in_production"
    assert [c["kind"] for c in ops.attention(desk.world())][0] == "incident"
    assert any("Reason given: Machine down" in s["text"] and s["buttons"] for s in api.sent if s["thread"] == 3)


def test_a_workshop_can_report_days_late_and_the_plan_tells_the_client(desk):
    bot, _ = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-017")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    tap(bot, f"j:late3:{job['key']}")
    incident = next(i for i in desk.world().incidents.values() if i["status"] == "open")
    assert incident["delay_days"] == 3
    assert desk.approve(incident["id"])["letters"] == 1
    assert str(desk.job(job["key"])["back"]) == "2026-04-12"


def test_the_dispatcher_must_give_a_reason_to_escalate(desk):
    card = desk.new_request(customer="Maple & Co", product="Vest", pieces=250, due=date(2026, 4, 18), priority="Cheapest")
    assert "Customer needs a decision" in card["escalate_reasons"]
    with pytest.raises(ValueError, match="Pick a reason"):
        desk.escalate(card["token"], "Because")
    with pytest.raises(ValueError, match="short note"):
        desk.escalate(card["token"], "Other", "  ")
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    desk.escalate(card["token"], "Cost or margin", "Margin is thin on this one")
    assert "Cost or margin. Margin is thin on this one" in api.sent[-1]["text"]
    assert not any(j["order_id"] == card["order_id"] for j in desk.world().jobs.values())


# The team chat follows the work -----------------------------------------------------------

def test_the_team_chat_hears_accepted_and_completed_but_role_play_stays_quiet(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team", thread=3))
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-041")
    desk.job_tap("ready", job["key"], "Raju")
    assert "Nimble Needle completed ORD-041" in api.sent[-1]["text"] and "room again" in api.sent[-1]["text"]
    said = len(api.sent)
    other = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-063")
    desk.job_tap("ready", other["key"], "Raju", channel="roleplay")
    assert len(api.sent) == said


def test_one_workshop_never_sees_the_others_workload(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam FreshStart", thread=7))
    said = len(api.sent)
    bot.handle(message("/queues", thread=7))
    assert len(api.sent) == said or "Workload now" not in api.sent[-1]["text"]
    bot.handle(message("/iam Team", thread=3))
    bot.handle(message("/queues", thread=3))
    assert "Workload now" in api.sent[-1]["text"]


def test_a_workshop_s_help_is_about_its_own_chat(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam FreshStart", thread=7))
    bot.handle(message("/help", thread=7))
    assert "FreshStart" in api.sent[-1]["text"] and "/jobs" in api.sent[-1]["text"]
    assert "Post a request" not in api.sent[-1]["text"]


def test_a_refused_batch_cannot_be_kept_where_it_was_refused(desk):
    job = next(j for j in desk.world().jobs.values() if j["order_id"] == "ORD-095")
    desk.job_tap("declines", job["key"], "Raju", reason="No capacity right now")
    incident = next(i for i in desk.world().incidents.values() if i["status"] == "open")
    row = desk.incident(incident["id"])["plan"]["rows"][0]
    assert row["can_keep"] is False and row["action"] == "move"
    desk.approve(incident["id"], choices={job["key"]: "wait"})      # An old screen asking to keep it changes nothing.
    assert desk.job(job["key"])["workshop_id"] != job["workshop_id"]


def test_a_delayed_batch_can_still_be_kept(desk):
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-017")
    desk.job_tap("late3", job["key"], "Raju")
    incident = next(i for i in desk.world().incidents.values() if i["status"] == "open")
    assert desk.incident(incident["id"])["plan"]["rows"][0]["can_keep"] is True


@pytest.mark.parametrize("message, value", [("ORD-041 में दो दिन और लगेंगे", 2), ("ORD-041 还需要两天", 2), ("ORD-041 needs two more days", 2), ("ORD-041 needs 2 more days", 2)])
def test_a_number_written_in_any_of_these_languages_counts_as_stated(message, value):
    assert partners._said(value, message)


def test_a_number_nobody_wrote_is_still_dropped_in_any_language():
    assert not partners._said(5, "ORD-041 में दो दिन और लगेंगे") and not partners._said(5, "ORD-041 还需要两天")


# A split from the app, and phone alerts -------------------------------------------------

def test_the_app_can_compare_and_confirm_a_split(desk):
    card = desk.new_request(customer="TrendCart", product="Cardigan", pieces=1500, due=date(2026, 4, 20), priority="Fastest")
    option = desk.split_option(card["token"])
    assert option["available"] and len(option["parts"]) == 2 and sum(p["pieces"] for p in option["parts"]) == 1500
    assert option["single"]["name"] == card["chosen"]["name"]
    before = len(desk.world().jobs)
    done = desk.confirm_split(card["token"])
    world = desk.world()
    assert done["card"] == "confirmed" and len(world.jobs) == before + 2
    sent = [j for j in world.jobs.values() if j["order_id"] == card["order_id"]]
    assert {j["stage"] for j in sent} == {"offered"} and all(j["split"] for j in sent)


def test_a_split_cannot_be_confirmed_before_it_is_compared(desk):
    card = desk.new_request(customer="TrendCart", product="Cardigan", pieces=1500, due=date(2026, 4, 20), priority="Fastest")
    with pytest.raises(ValueError, match="split"):
        desk.confirm_split(card["token"])


def test_what_the_team_hears_also_reaches_the_phone(desk):
    heard = []
    desk.notifier = heard.append
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-095")
    desk.job_tap("no0", job["key"], "Raju")
    assert "SteadyHands cannot take ORD-095" in heard[-1] and "Reason given: No capacity right now" in heard[-1]


def test_a_phone_alert_is_addressed_to_the_app_and_a_dead_phone_is_forgotten(pushed):
    apple = Apple((200, None), (410, "Unregistered"))
    watcher = island.Island(tokens=pushed.tokens, keys=pushed.keys, client=apple, devices=pushed.keys / "devices.json")
    watcher.phone("ab" * 32)
    watcher.phone("ab" * 32)
    watcher.phone("cd" * 32)
    assert len(watcher.phones) == 2
    watcher.alert("SteadyHands cannot take ORD-095\nReason given: No capacity right now\nApprove here, or open Threadline to change the plan first.")
    call = apple.calls[0]
    assert call["headers"]["apns-topic"] == island.APP and call["headers"]["apns-push-type"] == "alert"
    assert call["aps"]["alert"] == {"title": "SteadyHands cannot take ORD-095", "body": "Reason given: No capacity right now"}
    assert watcher.phones == ["ab" * 32]



# Automations only spend a reminder when it can arrive -------------------------------------

def test_a_reminder_waits_for_the_workshop_to_connect_and_then_goes_once(desk):
    bot, api = bot_for(desk)
    desk.set_automation("chase_silent", True)
    assert desk.automate() == []                                      # SteadyHands has no chat yet, so nothing is spent.
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-095")
    assert desk.job(job["key"])["reminded_at"] is None
    assert any(c["title"] == "No answer from SteadyHands" for c in ops.attention(desk.world()))
    bot.handle(message("/iam SteadyHands", thread=7))
    assert desk.automate() == ["SteadyHands reminded about ORD-095"]
    assert "A reminder about ORD-095" in api.sent[-1]["text"] and api.sent[-1]["buttons"]
    assert desk.automate() == []


def test_run_now_says_when_a_workshop_cannot_be_reached(desk):
    assert desk.run_automation("chase_silent")["text"] == "SteadyHands has no chat connected, so no reminder went."


def test_the_check_before_a_due_date_waits_for_a_chat_too(desk):
    bot, api = bot_for(desk)
    desk.set_clock(date(2026, 4, 3))
    assert desk.run_automation("check_due")["done"] == []
    bot.handle(message("/iam FreshStart", thread=7))
    assert desk.run_automation("check_due")["done"] == ["FreshStart asked about ORD-063"]


def test_moving_the_team_chat_to_a_workshop_says_so(desk):
    bot, api = bot_for(desk)
    bot.handle(message("/iam Team"))
    bot.handle(message("/iam SteadyHands"))
    assert any("no team chat" in s["text"] for s in api.sent)


# Hindi and Mandarin ------------------------------------------------------------------------

@pytest.mark.parametrize("language, offer, accept", [("hi", "SweaterCo से नया काम", "स्वीकार करें"), ("zh", "SweaterCo 新订单", "接受")])
def test_a_workshop_gets_job_cards_in_its_language_and_the_record_stays_english(desk, language, offer, accept):
    bot, api = bot_for(desk)
    job = next(j for j in ops.open_jobs(desk.world()) if j["order_id"] == "ORD-095")
    bot.handle(message(f"/iam {job['workshop']}", thread=7))
    bot.handle(message("/language", thread=7))
    picks = [b["callback_data"] for row in api.sent[-1]["buttons"] for b in row]
    assert picks == ["l:en", "l:hi", "l:zh"]
    bot.handle({"callback_query": {"id": "1", "data": f"l:{language}", "from": {"first_name": "Raju"}, "message": {"message_id": 3, "text": "", "chat": {"id": -100}, "message_thread_id": 7}}})
    desk.chase(job["key"], by="Dispatcher")
    card = api.sent[-1]
    assert card["buttons"][0][0]["text"] == accept
    desk.offer(job["key"])
    assert offer in api.sent[-1]["text"] and "ORD-095" in api.sent[-1]["text"]
    assert desk.world().threads[job["workshop_id"]][-1]["text"].startswith("New job from SweaterCo")
    bot.handle({"callback_query": {"id": "1", "data": f"j:why:{job['key']}", "from": {"first_name": "Raju"}, "message": {"message_id": 3, "text": "x", "chat": {"id": -100}, "message_thread_id": 7}}})
    assert api.edits[-1]["buttons"][0][0]["callback_data"] == f"j:no0:{job['key']}" and api.edits[-1]["buttons"][0][0]["text"] != "No capacity right now"
    bot.handle({"callback_query": {"id": "1", "data": f"j:no0:{job['key']}", "from": {"first_name": "Raju"}, "message": {"message_id": 3, "text": "x", "chat": {"id": -100}, "message_thread_id": 7}}})
    assert next(i for i in desk.world().incidents.values() if i["status"] == "open")["reason"] == "No capacity right now"


def test_a_language_choice_survives_a_demo_reset(desk):
    desk.set_language("W2", "zh")
    desk.reset_demo()
    assert desk.language("W2") == "zh" and desk.language("W1") == "en"


def test_every_job_card_wording_has_both_translations():
    import languages
    assert set(languages.WORDS["hi"]) == set(languages.WORDS["zh"])
    for reason in (*control.DECLINE_REASONS, *control.PROBLEM_REASONS, *ops.STAGES.values()):
        assert reason == "Completed" or reason in languages.WORDS["hi"] or reason in languages.WORDS["zh"]
    assert set(languages.PRODUCTS["hi"]) == set(languages.PRODUCTS["zh"]) == {"Hoodie", "Vest", "Scarf", "Beanie", "Cardigan", "Crewneck sweater", "Polo shirt"}


def test_a_request_in_hindi_is_read_in_english_and_shown_for_checking(desk):
    desk.translator = lambda prompt, text: SimpleNamespace(content=json.dumps({"english": "Where is ORD-041?"}))
    card = desk.speak("ORD-041 कहाँ है?")
    assert card["read_as"] == "Where is ORD-041?" and "Nimble Needle" in card["text"]


def test_english_is_never_sent_for_translation(desk):
    def refuse(*_):
        raise AssertionError("translated")
    desk.translator = refuse
    assert "read_as" not in desk.speak("Where is ORD-041?")
    assert "read_as" not in desk.speak("ORD-041 kahan hai?")


def test_a_failed_translation_does_not_stop_the_desk(desk):
    def broken(*_):
        raise intake.IntakeError("down")
    desk.translator = broken
    assert partners.english("ORD-041 कहाँ है?", [], broken) is None

