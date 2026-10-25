"""Threadline in the group chat: a Telegram bot over the same engine and audit log as the desk.

Someone posts a request in the chat; the bot replies in the thread with the
engine's recommendation and buttons. Nothing is allocated until a person taps
Confirm. The same roles hold as on the desk: the model reads the message, Python
decides, a person approves. Every confirmation, split and escalation is written
to the same audit log the Audit Trail reads, marked channel "telegram" with the
name of the person who tapped.

Run it from the repository root (long polling, so no public address is needed):

    uv run python src/telegram_bot.py

.env needs TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHATS (comma-separated chat
IDs; an unknown chat is told its ID and otherwise ignored, so strangers cannot
spend model credits). TELEGRAM_READING picks live (default), cached or fixture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "harness")]

import desk  # noqa: E402
import intake  # noqa: E402
from objectives import PRESETS  # noqa: E402
import rehearsal  # noqa: E402
import tools  # noqa: E402
import tracing  # noqa: E402
from ui import explain  # noqa: E402

ORDER_ID = re.compile(r"\bORD-\d+\b", re.I)


class TelegramAPI:
    """The few Bot API methods the bot needs, over HTTPS with the standard library."""

    def __init__(self, token: str, timeout: float = 40):
        self.base, self.timeout = f"https://api.telegram.org/bot{token}/", timeout

    def call(self, method: str, **params) -> dict | list:
        request = urllib.request.Request(self.base + method, data=json.dumps(params).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {body.get('description')}")
        return body["result"]

    def send(self, chat_id, text, *, reply_to=None, buttons=None) -> dict:
        params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        return self.call("sendMessage", **params)

    def edit(self, chat_id, message_id, text, *, buttons=None) -> dict:
        return self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML",
                         disable_web_page_preview=True, reply_markup={"inline_keyboard": buttons or []})

    def answer(self, callback_id, text=None):
        return self.call("answerCallbackQuery", callback_query_id=callback_id, **({"text": text} if text else {}))

    def typing(self, chat_id):
        return self.call("sendChatAction", chat_id=chat_id, action="typing")

    def updates(self, offset, timeout=30) -> list:
        return self.call("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])


@dataclass
class Pending:
    """One recommendation waiting for a tap. Kept in memory; a restart expires the buttons, never a decision."""
    preview: object
    message: str
    chat_id: int
    message_id: int | None = None
    reply_to: int | None = None
    answers: dict = field(default_factory=dict)
    split: dict | None = None
    done: str | None = None


def plural(product: str) -> str:
    """Same rule as the desk: scarf to scarves, vest to vests."""
    word = str(product).lower()
    return word[:-1] + "ves" if word.endswith("f") else word if word.endswith("s") else word + "s"


def e(value) -> str:
    return html.escape(str(value), quote=False)


class DispatchBot:
    def __init__(self, api, *, allowed_chats: set[int], source: str = "live", objective: str = "lateness", clock=None):
        self.api, self.allowed, self.source, self.config = api, allowed_chats, source, PRESETS[objective]
        self.orders, self.workshops, _ = desk.load_inputs()
        self.pending: dict[str, Pending] = {}
        self.saved: dict = {}
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.log_path = desk.audit_path(source)

    # Updates -------------------------------------------------------------------

    def handle(self, update: dict) -> None:
        if "callback_query" in update:
            self.on_button(update["callback_query"])
        elif "message" in update and update["message"].get("text"):
            self.on_message(update["message"])

    def authorised(self, chat_id) -> bool:
        return int(chat_id) in self.allowed

    def on_message(self, msg: dict) -> None:
        chat_id, text = msg["chat"]["id"], msg["text"].strip()
        command = text.split()[0].split("@")[0].lower() if text.startswith("/") else None
        if command == "/chatid" or not self.authorised(chat_id):
            if command in ("/chatid", "/start"):   # Otherwise an unknown chat is ignored: no reply, no model call.
                self.api.send(chat_id, f"This chat's ID is <code>{chat_id}</code>."
                              + ("" if self.authorised(chat_id) else " It is not authorised yet: add it to TELEGRAM_ALLOWED_CHATS."))
            return
        if command in ("/start", "/help"):
            self.api.send(chat_id, "<b>Threadline dispatch desk</b>\nPost a request as you would in the chat, for example "
                          "<i>ORD-045, 150 vests for Cotton Club, due 9 Apr, fastest please</i>.\nI reply with the engine's "
                          "recommendation. Nothing is allocated until someone taps Confirm.\n/queues shows the current workload.")
            return
        if command == "/queues":
            self.api.send(chat_id, self.queue_text())
            return
        if command:
            return
        reply = (msg.get("reply_to_message") or {}).get("message_id")
        answered = next((k for k, p in self.pending.items() if p.message_id == reply and p.chat_id == chat_id and not p.done), None)
        if answered:
            self.answer_from_text(answered, text, msg)
            return
        sender = (msg.get("from") or {}).get("first_name") or "Someone"
        self.evaluate(chat_id, f"{sender}: {text}", reply_to=msg["message_id"])

    # Evaluation ----------------------------------------------------------------

    def evaluate(self, chat_id, message, *, reply_to=None, answers=None, key=None):
        queues, allocator, _ = desk.queues_from_log(self.workshops, self.log_path)
        try:
            self.api.typing(chat_id)
        except Exception:
            pass
        meta = {"kind": "evaluation", "channel": "telegram", "source": self.source, "request_id": None,
                "message_sha": tracing.message_digest(message), "objective": self.config.name}
        error, preview = None, None
        try:
            with tracing.trace(**meta) as run, intake.extraction_source(rehearsal.make_source(self.source, record_live=False)):
                preview = desk.make_preview(message, desk.TODAY, self.config, self.orders, self.workshops, queues, allocator,
                                            0, self.source, answers)
        except Exception as caught:
            error = caught
        finally:
            try:
                tracing.save(run.to_dict())
            except Exception:
                pass
        if error is not None:
            title, action, _ = intake.ERROR_CATEGORIES.get(getattr(error, "category", None), ("Request not processed", "Try again.", True))
            self.api.send(chat_id, f"<b>{e(title)}</b>\n{e(action)}\nNothing was allocated.", reply_to=reply_to)
            return None
        key = key or uuid4().hex[:8]
        item = self.pending.get(key) or Pending(preview, message, chat_id, reply_to=reply_to)
        item.preview, item.answers = preview, dict(answers or {})
        self.pending[key] = item
        text, buttons = self.card(key, item)
        if item.message_id:
            self.api.edit(chat_id, item.message_id, text, buttons=buttons)
        else:
            item.message_id = self.api.send(chat_id, text, reply_to=reply_to, buttons=buttons)["message_id"]
        return key

    def card(self, key, item: Pending):
        response = item.preview.response
        parsed, record = response.parsed_request, response.decision_record
        chosen = explain.chosen_row(record)
        if parsed.behaviour == "clarify":
            return self.clarify_card(key, item)
        if parsed.behaviour == "decline" or chosen is None:
            reason = ("That order is not in orders.csv." if parsed.reason == "order not found"
                      else "That information is not in the supplied data." if parsed.behaviour == "decline"
                      else "No active workshop can take this batch as one job.")
            return f"<b>Cannot act on this request</b>\n{e(reason)}\nNothing was allocated.", None
        awkward = record.get("awkward_case") == "none_makes_date"
        head = (f"<b>No workshop meets {e(explain.short_date(parsed.due_date))}.</b> Least late: <b>{e(chosen['name'])}</b>" if awkward
                else f"<b>{e(self.workshops[parsed.suggested_workshop].name if parsed.suggested_workshop in self.workshops else 'The named workshop')}"
                     f" cannot take it.</b> Best alternative: <b>{e(chosen['name'])}</b>" if parsed.behaviour == "refuse"
                else f"<b>Recommended: {e(chosen['name'])}</b>")
        spare = chosen["days_to_spare"]
        won = explain.why_won(record)
        lines = [head,
                 f"{e(parsed.order_id)} · {parsed.pieces:,} {e(plural(parsed.product))}" + (f" for {e(parsed.customer)}" if parsed.customer else ""),
                 f"Back {e(explain.short_date(chosen['eta_date']))} · " + (f"{explain.days(-spare)} late" if spare < 0 else f"{explain.days(spare)} to spare")
                 + f" · cost {chosen['total_cost']:,.0f} · defect risk {chosen['expected_defect_rate']:.0%}",
                 f"Why: {e(won['sentence'] if won else record['reason_chosen'])}"]
        if (response.faithfulness or {}).get("passed"):
            lines.append("Every number checked against the tools.")
        changes = [f"{c['field'].replace('_', ' ')} {c.get('previous') or 'not stated'} → {c['value']}" for c in parsed.answers_applied]
        if changes:
            lines.append("Your answers: " + e("; ".join(changes)))
        lines.append("<i>Not confirmed. Nothing is allocated until you tap.</i>")
        label = "Accept late return" if awkward else f"Confirm {chosen['name']}"
        buttons = [[{"text": label, "callback_data": f"c:{key}"}],
                   [{"text": "Single or split?", "callback_data": f"s:{key}"}, {"text": "Escalate", "callback_data": f"e:{key}"}]]
        if item.preview.block_reason:
            lines[-1] = f"<i>Cannot confirm yet: {e(item.preview.block_reason)}</i>"
            buttons = [[{"text": "Escalate", "callback_data": f"e:{key}"}]]
        return "\n".join(lines), buttons

    def clarify_card(self, key, item: Pending):
        parsed, record = item.preview.response.parsed_request, item.preview.response.decision_record
        options = record.get("tool_outputs", {}).get("order_options", [])
        prompt = explain.clarify_prompt(parsed.to_dict(), options)
        lines = ["<b>Needs a reply before allocating</b>", e(prompt["question"])]
        buttons = [[{"text": f"{o['order_id']} · {o['product']}, {o['pieces']:,}", "callback_data": f"o:{key}:{o['order_id']}"}]
                   for o in prompt["options"][:6]]
        row = self.orders[self.orders["order_id"] == parsed.order_id]
        if parsed.order_id and (parsed.date_not_confirmed or parsed.due_date is None) and len(row):
            due = str(row.iloc[0]["due_date"])[:10]
            buttons.append([{"text": f"Keep {explain.short_date(due)}, the date on file", "callback_data": f"d:{key}"}])
        lines.append("<i>Tap an answer, or reply to this message with it (a date, an order number or a quantity).</i>")
        return "\n".join(lines), buttons or None

    # Buttons -------------------------------------------------------------------

    def on_button(self, cb: dict) -> None:
        chat_id = cb["message"]["chat"]["id"]
        who = (cb.get("from") or {}).get("first_name") or "Someone"
        if not self.authorised(chat_id):
            self.api.answer(cb["id"], "This chat is not authorised.")
            return
        action, key, *rest = cb.get("data", "").split(":")
        item = self.pending.get(key)
        if item is None:
            self.api.answer(cb["id"], "This recommendation expired. Send the request again.")
            return
        if item.done:
            self.api.answer(cb["id"], f"Already {item.done}.")
            return
        if action == "c":
            self.confirm(key, item, who, cb["id"])
        elif action == "s":
            self.show_split(key, item, cb["id"])
        elif action == "S":
            self.confirm_split(key, item, who, cb["id"])
        elif action == "k":
            text, buttons = self.card(key, item)
            self.api.edit(item.chat_id, item.message_id, text, buttons=buttons)
            self.api.answer(cb["id"])
        elif action == "e":
            self.escalate(key, item, who, cb["id"])
        elif action == "o":
            self.api.answer(cb["id"], f"Using {rest[0]}")
            self.give(key, item, "order_id", rest[0])
        elif action == "d":
            due = str(self.orders[self.orders["order_id"] == item.preview.response.parsed_request.order_id].iloc[0]["due_date"])[:10]
            self.api.answer(cb["id"], "Keeping the date on file")
            self.give(key, item, "due_date", due)

    def give(self, key, item, field_name, value):
        answers = {**item.answers, field_name: {"value": value, "at": self.clock().isoformat(timespec="seconds")}}
        self.evaluate(item.chat_id, item.message, answers=answers, key=key)

    def answer_from_text(self, key, text, msg):
        item = self.pending[key]
        order = ORDER_ID.search(text)
        when = intake._calendar_date(text, desk.TODAY)
        if order:
            self.give(key, item, "order_id", order.group(0).upper())
        elif when:
            self.give(key, item, "due_date", when.isoformat())
        elif text.replace(",", "").isdigit():
            self.give(key, item, "pieces", int(text.replace(",", "")))
        else:   # Anything else is read by the model with the original message.
            item.message = f"{item.message} Reply: {text}"
            self.evaluate(item.chat_id, item.message, answers=item.answers, key=key)

    def fresh(self, item) -> bool:
        """A recommendation is only confirmable on the workload it was computed for."""
        queues, allocator, _ = desk.queues_from_log(self.workshops, self.log_path)
        current = desk.signature(item.message, desk.TODAY, self.config, self.orders, self.workshops, queues, 0, self.source, item.answers)
        return current == item.preview.signature

    def append(self):
        return (lambda response: desk.records.append(response, self.log_path)) if self.log_path else None

    def stamp(self) -> str:
        return self.clock().strftime("%H:%M UTC")

    def confirm(self, key, item, who, callback_id):
        if not self.fresh(item):
            self.api.answer(callback_id, "The workload changed. Updating the recommendation.")
            self.evaluate(item.chat_id, item.message, answers=item.answers, key=key)
            return
        try:
            desk.confirm_preview(item.preview, item.preview.signature, self.saved, append=self.append(), channel="telegram", by=who)
        except (ValueError, OSError) as error:
            self.api.answer(callback_id, f"Not saved: {error}"[:190])
            return
        item.done = "confirmed"
        chosen = explain.chosen_row(item.preview.response.decision_record)
        text, _ = self.card(key, item)
        body = text.rsplit("\n", 1)[0].replace("<b>Recommended: ", "<b>Confirmed: ", 1)
        self.api.edit(item.chat_id, item.message_id, body + f"\n✅ <b>Confirmed by {e(who)}</b> at {self.stamp()}. Audit record saved. "
                      f"Nothing was sent to {e(chosen['name'])}.")
        self.api.answer(callback_id, "Confirmed")

    def show_split(self, key, item, callback_id):
        parsed, record = item.preview.response.parsed_request, item.preview.response.decision_record
        chosen = explain.chosen_row(record)
        queues, _, _ = desk.queues_from_log(self.workshops, self.log_path)
        batch = {"order_id": parsed.order_id, "pieces": parsed.pieces, "category": parsed.category,
                 "due_date": parsed.due_date, "sent_date": desk.TODAY}
        try:
            split = tools.estimate_split(batch, self.workshops, queues, desk.TODAY, record["constraints_applied"]["exclude"],
                                         record["chosen_workshop"])
        except ValueError as error:
            split = {"available": False, "reason": str(error)}
        item.split = split
        lines = [f"<b>Single or split for {e(parsed.order_id)}?</b>",
                 f"Single: <b>{e(chosen['name'])}</b>, back {e(explain.short_date(chosen['eta_date']))}, cost {chosen['total_cost']:,.0f}, "
                 f"defect risk {chosen['expected_defect_rate']:.1%}"]
        buttons = [[{"text": f"Keep {chosen['name']}", "callback_data": f"k:{key}"}]]
        if split.get("available"):
            defect = desk.split_defect_rate(split, self.workshops)
            parts = " + ".join(f"{p['name']} {p['pieces']:,}" for p in split["parts"])
            lines.append(f"Split: <b>{e(parts)}</b>, back {e(explain.short_date(split['eta_date']))}, cost {split['total_cost']:,.0f}, "
                         f"defect risk {defect:.1%}")
            days = chosen["total_days"] - split["total_days"]
            lines.append(f"<i>The split saves {days:.1f} days of production time.</i>" if days > 0.05 else "<i>The split is not faster.</i>")
            buttons.insert(0, [{"text": "Confirm the split", "callback_data": f"S:{key}"}])
        else:
            lines.append(f"No legal two-workshop split: {e(split.get('reason', ''))}.")
        self.api.edit(item.chat_id, item.message_id, "\n".join(lines), buttons=buttons)
        self.api.answer(callback_id)

    def confirm_split(self, key, item, who, callback_id):
        if not item.split or not item.split.get("available") or not self.fresh(item):
            self.api.answer(callback_id, "The workload changed. Updating the recommendation.")
            self.evaluate(item.chat_id, item.message, answers=item.answers, key=key)
            return
        queues, allocator, _ = desk.queues_from_log(self.workshops, self.log_path)
        try:
            desk.confirm_split(item.preview, item.preview.signature, self.saved, item.split, self.workshops, queues, allocator,
                               append=self.append(), channel="telegram", by=who)
        except (ValueError, OSError) as error:
            self.api.answer(callback_id, f"Not saved: {error}"[:190])
            return
        item.done = "confirmed"
        parts = " and ".join(f"{p['name']} ({p['pieces']:,})" for p in item.split["parts"])
        self.api.edit(item.chat_id, item.message_id, f"<b>Split confirmed: {e(parts)}</b>\nBack {e(explain.short_date(item.split['eta_date']))}, "
                      f"combined cost {item.split['total_cost']:,.0f}.\n✅ <b>Confirmed by {e(who)}</b> at {self.stamp()}. Audit record saved.")
        self.api.answer(callback_id, "Split confirmed")

    def escalate(self, key, item, who, callback_id):
        parsed = item.preview.response.parsed_request
        try:
            desk.escalate(item.preview, "Planner", f"Raised from the group chat by {who}.", append=self.append(), channel="telegram", by=who)
        except OSError as error:
            self.api.answer(callback_id, f"Not saved: {error}"[:190])
            return
        item.done = "escalated"
        self.api.edit(item.chat_id, item.message_id, f"<b>Escalated to the planner</b> ({e(parsed.order_id or 'request')})\n"
                      f"Raised by {e(who)} at {self.stamp()}. Nothing was allocated. Recorded in the audit log.")
        self.api.answer(callback_id, "Escalated")

    def queue_text(self) -> str:
        queues, _, confirmed = desk.queues_from_log(self.workshops, self.log_path)
        rows = [f"{w.name}: {queues[wid]:.1f} days" + (" (suspended)" if w.status != "ACTIVE" else "")
                for wid, w in sorted(self.workshops.items(), key=lambda kv: queues[kv[0]])]
        return "<b>Workload now</b>\n" + e("\n".join(rows)) + f"\n<i>1 April snapshot plus {confirmed} confirmed decision{'' if confirmed == 1 else 's'}.</i>"


def main():
    intake.llm_settings()   # Loads .env.
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Set TELEGRAM_BOT_TOKEN in .env (create a bot with @BotFather).")
    allowed = {int(x) for x in os.environ.get("TELEGRAM_ALLOWED_CHATS", "").replace(" ", "").split(",") if x}
    source = os.environ.get("TELEGRAM_READING", "live")
    bot = DispatchBot(TelegramAPI(token), allowed_chats=allowed, source=source)
    print(f"Threadline bot running. Reading: {source}. Authorised chats: {sorted(allowed) or 'none yet (send /chatid)'}", flush=True)
    offset = None
    while True:
        try:
            for update in bot.api.updates(offset):
                offset = update["update_id"] + 1
                try:
                    bot.handle(update)
                except Exception as error:   # One bad update never stops the desk.
                    print(f"update {update.get('update_id')} failed: {type(error).__name__}: {error}", flush=True)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
            print(f"Telegram unreachable ({error}); retrying in 5 s", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
