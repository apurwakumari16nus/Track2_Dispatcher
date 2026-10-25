"""The Telegram channel, offline: a fake Bot API and the hand-written extraction fixtures. No network, no model call."""

import copy
import json
from pathlib import Path

import pytest

import desk
import intake
import records
import telegram_bot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/intake_extractions.json").read_text())
CHAT = 4242


class FakeAPI:
    def __init__(self):
        self.sent, self.edits, self.answers, self.next_id = [], [], [], 100

    def send(self, chat_id, text, *, reply_to=None, buttons=None):
        self.next_id += 1
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons, "message_id": self.next_id})
        return {"message_id": self.next_id}

    def edit(self, chat_id, message_id, text, *, buttons=None):
        self.edits.append({"message_id": message_id, "text": text, "buttons": buttons})

    def answer(self, callback_id, text=None):
        self.answers.append(text)

    def typing(self, chat_id):
        pass


def extraction(request_id):
    return {**copy.deepcopy(FIXTURE["defaults"]), **copy.deepcopy(FIXTURE["requests"][request_id])}


@pytest.fixture
def bot(monkeypatch, tmp_path):
    monkeypatch.setattr(records, "DEFAULT_PATH", tmp_path / "live.jsonl")
    monkeypatch.setattr(desk, "REHEARSAL_LOG", tmp_path / "rehearsal.jsonl")
    reply = {"payload": extraction("R09")}
    monkeypatch.setattr(intake, "_call_llm", lambda prompt, message: intake.LLMReply(json.dumps(reply["payload"]), {"model": "test"}))
    api = FakeAPI()
    instance = telegram_bot.DispatchBot(api, allowed_chats={CHAT}, source="live")
    instance.reply = reply
    return instance, api


def message(text, chat=CHAT, reply_to=None, mid=1):
    msg = {"message_id": mid, "chat": {"id": chat}, "from": {"first_name": "Aditya"}, "text": text}
    if reply_to:
        msg["reply_to_message"] = {"message_id": reply_to}
    return {"message": msg}


def tap(api, data, chat=CHAT):
    return {"callback_query": {"id": "cb", "data": data, "from": {"first_name": "Aditya"}, "message": {"chat": {"id": chat}}}}


def button(api, prefix):
    rows = (api.edits[-1]["buttons"] if api.edits and api.edits[-1]["buttons"] else api.sent[-1]["buttons"]) or []
    return next(b["callback_data"] for row in rows for b in row if b["callback_data"].startswith(prefix))


def test_an_unknown_chat_is_ignored_and_only_told_its_id_on_request(bot):
    instance, api = bot
    instance.handle(message("ORD-045, 150 vests, due 9 Apr", chat=999))
    assert not api.sent and not instance.pending                      # No reply, no model call.
    instance.handle(message("/chatid", chat=999))
    assert "999" in api.sent[-1]["text"] and "not authorised" in api.sent[-1]["text"]


def test_a_request_gets_a_recommendation_and_one_tap_confirms_it_once(bot):
    instance, api = bot
    instance.handle(message("ORD-045, 150 vests for Cotton Club, due Apr 09, fastest please"))
    card = api.sent[-1]
    assert "Recommended: Nimble Needle" in card["text"] and "Not confirmed" in card["text"]
    assert not records.DEFAULT_PATH.exists()                           # A recommendation writes nothing.
    data = button(api, "c:")
    instance.handle(tap(api, data))
    rows = records.load()
    assert len(rows) == 1
    confirmation = rows[0]["decision_record"]["constraints_applied"]["confirmation"]
    assert confirmation["channel"] == "telegram" and confirmation["confirmed_by"] == "Aditya"
    assert "Confirmed by Aditya" in api.edits[-1]["text"]
    instance.handle(tap(api, data))                                    # A second tap writes nothing.
    assert len(records.load()) == 1 and api.answers[-1] == "Already confirmed."
    queues, _, confirmed = desk.queues_from_log(instance.workshops)
    assert confirmed == 1 and queues["W6"] > instance.workshops["W6"].queue0   # The shared workload moved.


def test_a_recommendation_made_on_an_old_workload_is_refreshed_not_confirmed(bot):
    instance, api = bot
    instance.handle(message("ORD-045, 150 vests, due Apr 09", mid=1))
    first = button(api, "c:")
    instance.handle(message("ORD-045 again, 150 vests, due Apr 09", mid=2))
    second = button(api, "c:")
    instance.handle(tap(api, first))
    instance.handle(tap(api, second))                                  # Computed before the first confirmation.
    assert len(records.load()) == 1 and "workload changed" in api.answers[-1].lower()


def test_clarification_answers_by_button_and_by_reply(bot):
    instance, api = bot
    instance.reply["payload"] = extraction("R01")
    instance.handle(message("Need scarves for Harbor Knits sent out today, usual quantities."))
    assert "Needs a reply" in api.sent[-1]["text"]
    choice = button(api, "o:")
    instance.handle(tap(api, choice))
    parsed = next(iter(instance.pending.values())).preview.response.parsed_request
    assert parsed.order_id == choice.split(":")[2] and parsed.answers_applied[0]["field"] == "order_id"
    instance.reply["payload"] = extraction("R05")
    instance.handle(message("ORD-066 due date just moved up, will confirm the new date after the call", mid=7))
    asked = api.sent[-1]
    assert "Keep" in json.dumps(asked["buttons"])                      # The date on file, one tap away.
    instance.handle(message("20 Apr", reply_to=asked["message_id"], mid=8))
    parsed = [p for p in instance.pending.values() if p.message_id == asked["message_id"]][0].preview.response.parsed_request
    assert parsed.due_date.isoformat() == "2026-04-20" and parsed.behaviour == "allocate"


def test_escalation_and_split_are_recorded_and_only_the_split_moves_the_queue(bot):
    instance, api = bot
    instance.reply["payload"] = extraction("R30")
    instance.handle(message("ORD-099 1500 polo shirts, deadline Apr 05", mid=1))
    instance.handle(tap(api, button(api, "e:")))
    assert records.load()[0]["decision_record"]["constraints_applied"]["confirmation"]["escalated"]
    assert desk.queues_from_log(instance.workshops)[2] == 0
    instance.handle(message("ORD-099 1500 polo shirts, deadline Apr 05", mid=2))
    instance.handle(tap(api, button(api, "s:")))
    assert "Single or split" in api.edits[-1]["text"]
    instance.handle(tap(api, button(api, "S:")))
    row = records.load()[-1]
    assert row["decision_record"]["split_allocation"] and "Split confirmed" in api.edits[-1]["text"]
    queues, _, confirmed = desk.queues_from_log(instance.workshops)
    assert confirmed == 1 and {p["workshop_id"] for p in row["decision_record"]["split_allocation"]["parts"]} == {
        w for w in queues if queues[w] != instance.workshops[w].queue0}
