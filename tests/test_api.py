"""The phone's HTTP surface: thin routes over control.py, plain refusals, and the access token."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
import control
import hearing
import island


@pytest.fixture
def phone(tmp_path, monkeypatch):
    monkeypatch.setattr(control.inbox_store, "PATH", tmp_path / "messages.jsonl")
    monkeypatch.delenv("THREADLINE_API_TOKEN", raising=False)
    api.desk_control = control.Control(demo=True, source="fixture", decisions_path=tmp_path / "rehearsal_decisions.jsonl", ops_path=tmp_path / "ops.jsonl",
                                       received=tmp_path / "received.jsonl")
    with TestClient(api.app) as client:
        assert client.post("/api/demo/reset").json() == {"jobs": 8}
        yield client
    api.desk_control = None


def test_today_is_ready_to_draw(phone):
    today = phone.get("/api/today").json()
    assert today["today"] == "2026-04-01" and today["out"] == 8 and len(today["network"]) == 8
    assert all({"title", "detail", "action", "target"} <= set(card) for card in today["attention"])


def test_a_request_goes_from_speech_to_a_batch(phone):
    line = next(m for m in api.desk_control.messages if m.startswith("R09 "))
    card = phone.post("/api/requests/open", json={"line": line, "request": "R09"}).json()
    assert card["card"] == "recommendation" and card["chosen"]["name"] and card["metrics"]
    confirmed = phone.post(f"/api/decisions/{card['token']}/confirm", json={"by": "Aditya"}).json()
    assert confirmed["job"]["confirmed_by"] == "Aditya"
    key = confirmed["key"].replace(":", "%3A")
    assert phone.get(f"/api/batches/{key}").json()["stage"] == "offered"


def test_a_workshop_reply_reaches_the_phone_and_approval_works(phone):
    reading = phone.post("/api/roleplay/inbound", json={"party": "W1", "text": "Power cut, closed till Monday", "by": "Owner"}).json()
    assert reading["kind"] == "closed" and reading["date"] == "2026-04-06"
    card = next(c for c in phone.get("/api/today").json()["attention"] if c["kind"] == "incident")
    incident = phone.get(f"/api/incidents/{card['target']['id']}").json()
    assert incident["workshop"] == "QuickStitch" and incident["plan"]["rows"]
    result = phone.post(f"/api/incidents/{card['target']['id']}/approve", json={"by": "Aditya"}).json()
    assert result["moved"] >= 1
    assert phone.post(f"/api/incidents/{card['target']['id']}/approve", json={"by": "Aditya"}).status_code == 409


def test_a_bad_reference_is_a_plain_sentence(phone):
    response = phone.get("/api/incidents/nothing")
    assert response.status_code == 404 and response.json()["detail"] == "That incident is not on record."


def test_the_token_is_required_once_set(phone, monkeypatch):
    monkeypatch.setenv("THREADLINE_API_TOKEN", "test-token-not-real")
    assert phone.get("/api/today").status_code == 401
    assert phone.get("/api/today", headers={"Authorization": "Bearer test-token-not-real"}).status_code == 200
    assert phone.get("/api/health").status_code == 200   # Says only whether the desk is up.


def test_the_demo_starts_with_real_conversations(phone):
    threads = phone.get("/api/threads").json()
    assert {t["name"] for t in threads if t["type"] == "client"} >= {"TrendCart", "Harbor Knits"}
    quick = next(t for t in threads if t["name"] == "QuickStitch")
    assert quick["last_text"].startswith("Accepted (ORD-")
    last = phone.get(f"/api/threads/{quick['party']}").json()["messages"][-1]
    assert last["author"] == "QuickStitch" and last["channel"] == "roleplay"


def test_a_banner_only_announces_what_is_new():
    message = {"kind": "message", "direction": "in", "party": "W1", "author": "QuickStitch", "text": "Accepted"}
    assert api._latest([message])["title"] == "QuickStitch"
    assert api._latest([{"kind": "decision", "id": "x"}]) is None


def test_the_trail_does_not_claim_a_client_was_told_when_they_were_not(phone):
    desk = api.desk_control
    late = next(j for j in desk.world().jobs.values() if j["customer"])
    letter = desk.draft_letter(late["key"])
    desk.send_letter(letter["id"], acknowledged=True)
    labels = [e["label"] for e in phone.get("/api/trail").json()]
    assert "Notice saved, client not on Telegram" in labels and "Client told" not in labels


def test_role_play_is_labelled_as_role_play(phone):
    key = next(j["key"] for j in api.desk_control.world().jobs.values() if j["stage"] == "offered")
    phone.post("/api/roleplay/tap", json={"action": "accepts", "key": key, "by": "Owner"})
    assert all(e["detail"] != "Tapped in Telegram" for e in phone.get("/api/trail").json())


def test_one_call_carries_everything_the_main_screens_draw(phone):
    snapshot = phone.get("/api/snapshot").json()
    assert snapshot["today"]["out"] == 8 and len(snapshot["jobs"]) == 8 and snapshot["threads"] and snapshot["requests"]
    assert phone.get("/api/snapshot").content == phone.get("/api/snapshot").content    # Unchanged desk, identical answer.


def test_the_form_answers_without_the_model(phone, monkeypatch):
    def refuse(*_):
        raise AssertionError("A form has nothing for the model to read.")
    monkeypatch.setattr(api.intake, "_call_llm", refuse)
    card = phone.post("/api/requests/new", json={"customer": "TrendCart", "product": "Hoodie", "pieces": 300, "due": "2026-04-20", "priority": "Fastest"}).json()
    assert card["card"] == "recommendation" and card["reading"] == "form" and card["order_id"] == "ORD-121" and card["can_confirm"]


def test_a_role_played_message_comes_from_the_party_not_the_phone(phone):
    phone.post("/api/roleplay/inbound", json={"party": "W2", "text": "Folded or on hangers?", "by": "Dispatcher"})
    last = phone.get("/api/threads/W2").json()["messages"][-1]
    assert last["author"] == "SteadyHands" and last["channel"] == "roleplay"


def test_a_test_build_can_report_its_timings(phone, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PERF_LOG", tmp_path / "perf.jsonl")
    assert phone.post("/api/perf", json={"entries": [{"screen": "today/root", "hitches": 3}]}).json() == {"ok": True}
    assert '"hitches": 3' in (tmp_path / "perf.jsonl").read_text()


def test_the_desk_listens_with_this_business_names_in_mind(phone, monkeypatch):
    heard = {}

    def whisper(command, **_):
        heard["hints"] = command[command.index("--prompt") + 1]
        return SimpleNamespace(stdout=" 300 hoodies for TrendCart,\n back by 20 April.\n[BLANK_AUDIO]\n")

    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing.subprocess, "run", whisper)
    assert phone.post("/api/transcribe", content=b"RIFF").json() == {"text": "300 hoodies for TrendCart, back by 20 April.", "language": "en"}
    assert "QuickStitch" in heard["hints"] and "Cotton Club" in heard["hints"]


def test_without_whisper_the_phone_keeps_its_own_words(phone, monkeypatch):
    monkeypatch.setattr(hearing, "ready", lambda language="en": False)
    assert phone.post("/api/transcribe", content=b"RIFF").status_code == 503
    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing, "BINARY", "/nonexistent/whisper-cli")
    assert phone.post("/api/transcribe", content=b"RIFF").json() == {"text": "", "language": "en"}


@pytest.mark.parametrize("named, language", [("en", "en"), ("hi", "hi"), ("ur", "hi"), ("zh", "zh"), ("fr", "en")])
def test_the_desk_works_out_the_language_from_the_voice(phone, monkeypatch, named, language):
    heard = {}

    def whisper(command, **_):
        if "-dl" in command:
            heard["checked"] = command
            return SimpleNamespace(stdout="", stderr=f"whisper_full_with_state: auto-detected language: {named} (p = 0.91)\n")
        heard["command"] = command
        return SimpleNamespace(stdout=" words\n", stderr="")

    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing.subprocess, "run", whisper)
    monkeypatch.setattr(hearing.Path, "exists", lambda self: True)
    assert phone.post("/api/transcribe?language=auto", content=b"RIFF").json() == {"text": "words", "language": language}
    assert str(hearing.ANY_LANGUAGE) in heard["checked"]
    assert heard["command"][heard["command"].index("-l") + 1] == language
    assert str(hearing.MODEL if language == "en" else hearing.ANY_LANGUAGE) in heard["command"]


def test_the_language_can_be_checked_on_its_own_before_any_words(phone, monkeypatch):
    def whisper(command, **_):
        assert "-dl" in command
        return SimpleNamespace(stdout="", stderr="auto-detected language: hi (p = 0.91)\n")

    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing.subprocess, "run", whisper)
    monkeypatch.setattr(hearing.Path, "exists", lambda self: True)
    assert phone.post("/api/language", content=b"RIFF").json() == {"language": "hi"}
    monkeypatch.setattr(hearing, "ready", lambda language="en": False)
    assert phone.post("/api/language", content=b"RIFF").status_code == 503


def test_a_failed_language_check_falls_back_to_english(phone, monkeypatch):
    def whisper(command, **_):
        if "-dl" in command:
            raise hearing.subprocess.TimeoutExpired(command, 20)
        return SimpleNamespace(stdout=" words\n", stderr="")

    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing.subprocess, "run", whisper)
    monkeypatch.setattr(hearing.Path, "exists", lambda self: True)
    assert phone.post("/api/transcribe?language=auto", content=b"RIFF").json() == {"text": "words", "language": "en"}


def test_the_phone_can_hand_over_an_island_token_and_only_a_real_one(phone, monkeypatch, tmp_path):
    monkeypatch.setattr(api, "push", island.Island(tokens=tmp_path / "island.json", keys=tmp_path))
    key = next(iter(api.desk().world().jobs))
    assert phone.post("/api/island", json={"key": key, "token": "ab" * 32}).json() == {"ok": True}
    assert api.push.tracked["ab" * 32]["job"] == key
    assert phone.post("/api/island", json={"key": key, "token": "../../etc"}).status_code == 422
    assert phone.post("/api/island", json={"key": "nope", "token": "cd" * 32}).status_code >= 400
    assert phone.get("/api/health").json()["island_push"] is False


def test_hindi_and_mandarin_use_the_multi_language_model(phone, monkeypatch):
    heard = {}

    def whisper(command, **_):
        heard["command"] = command
        return SimpleNamespace(stdout=" ORD-041 कहाँ है?\n")

    monkeypatch.setattr(hearing, "ready", lambda language="en": True)
    monkeypatch.setattr(hearing.subprocess, "run", whisper)
    assert phone.post("/api/transcribe?language=hi", content=b"RIFF").json() == {"text": "ORD-041 कहाँ है?", "language": "hi"}
    assert str(hearing.ANY_LANGUAGE) in heard["command"] and heard["command"][heard["command"].index("-l") + 1] == "hi"
    phone.post("/api/transcribe", content=b"RIFF")
    assert str(hearing.MODEL) in heard["command"]
    assert phone.post("/api/transcribe?language=fr", content=b"RIFF").status_code == 422



@pytest.mark.parametrize("reading, cleaned", [
    ("300 hoodies for TrendCart. 300 hoodies for TrendCart.", "300 hoodies for TrendCart."),
    ("Where is order 41? Where is order 41?", "Where is order 41?"),
    ("Tell QuickStitch we need it by Friday. Tell QuickStitch we", "Tell QuickStitch we need it by Friday."),
    ("Back by April 20th. Fastest please now. Fastest please now. Thanks", "Back by April 20th. Fastest please now. Thanks"),
    ("300 हुडी Cotton Club के लिए. 300 हुडी Cotton Club के लिए.", "300 हुडी Cotton Club के लिए."),
    ("今天我需要处理什么?今天我需要处理什么?", "今天我需要处理什么?"),
    ("Order 41, order 41, is it ready?", "Order 41, order 41, is it ready?"),
    ("300 hoodies for TrendCart, back by 20 April.", "300 hoodies for TrendCart, back by 20 April."),
])
def test_words_whisper_read_out_twice_are_kept_once(reading, cleaned):
    assert hearing.once(reading) == cleaned
