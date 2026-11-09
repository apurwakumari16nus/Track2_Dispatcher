# Threadline in the group chat (Telegram)

**Status (24 October 2026): Phase 1 built and tested offline with a fake Bot API
(5 tests). It has not yet run against real Telegram.** That needs the bot token
below.

## Why this exists

Requests arrive in a group chat. Without the bot, the dispatcher reads the chat,
opens the desk, copies the text, evaluates it, confirms it, then messages the
workshop. With the bot, the recommendation appears in the same thread, and one tap
confirms it into the same audit log. The roles are unchanged: the model reads, Python
decides, a person approves. The bot never confirms on its own.

## What it does now (Phase 1)

* Replies to a request with the engine's recommendation: return date, spare days,
  cost, defect risk, the reason it won, and whether the evidence check passed.
* **Confirm** writes one audit record (`channel: telegram`, `confirmed_by: <name>`).
  A second tap writes nothing.
* **Single or split?** compares the single workshop with the fastest legal split;
  **Confirm the split** records it and loads each part onto its own workshop.
* **Escalate** records that the request went to the planner. Nothing is allocated.
* **Clarifications** come with answer buttons (the candidate orders, the date on file).
  You can also reply to the bot's message with a date, an order number or a quantity.
  Python applies the answer and keeps the previous value, as on the desk.
* **Shared workload.** Every evaluation starts from the 1 April snapshot plus every
  confirmed decision in the audit log (`desk.queues_from_log`). A recommendation made
  before someone else confirmed is refreshed, not confirmed.
* `/queues` shows the current workload; `/chatid` shows a chat's ID.
* **Unknown chats are ignored.** They get no reply and no model call, so strangers
  cannot spend model credits.

## Set up (about five minutes)

1. In Telegram, message **@BotFather** → `/newbot` → choose a name (for example
   "Threadline Dispatch") and a username ending in `bot`. Copy the token it gives you.
2. Still in BotFather: `/setprivacy` → choose your bot → **Disable**. This lets it read
   ordinary messages in a group, not only commands.
3. Put the token in `.env` yourself: `TELEGRAM_BOT_TOKEN=...`. Never commit it;
   `.env` is git-ignored.
4. Create a group (for example "Sweater Co dispatch"), add the bot, and send `/chatid`.
5. Put that ID in `.env`: `TELEGRAM_ALLOWED_CHATS=-100...`.
6. Run: `uv run python src/telegram_bot.py`. Keep it running while you demo.

With `TELEGRAM_READING=live` (the default), each request is one model call, about one
US cent with Sonnet 5.5. Confirmations then go to the live audit log, which the Audit
Trail page shows immediately.

## Recording it (about 20 seconds)

Telegram Desktop on the left, the Audit Trail on the right (Live log).

1. In the group, type: *ORD-045, 150 vests for Cotton Club, due 9 Apr, fastest please.*
2. The bot replies: Recommended Nimble Needle, back 4 Apr, 5 days to spare, cost 180.
3. Tap **Confirm Nimble Needle**. The message turns to "Confirmed by …".
4. On the right, the new record appears in the Audit Trail (refresh the page if needed).

## Next phases (lowest effort for the most value first)

| Phase | What | Why it is worth it | Effort |
|---|---|---|---|
| 2 | Workshop loop: the chosen workshop gets the batch in its own chat with Accept / Decline, then Started / Done | Replaces the manual "message the workshop" step; actual dates feed the queue; plan against actual becomes observed evidence | About a day |
| 3 | Morning briefing to the group: batches at risk, overloaded queues, disruption flags, each with buttons | Managers act on exceptions; uses the existing ETA, queue and shock tools | Half a day |
| 3 | Siri Shortcut: speak a request, it is posted to the bot | Hands-free capture from the lock screen; test on the device first | Hours |
| 4 | iPhone widget or Live Activity (TestFlight, internal testers only) | Pending approvals on the lock screen; strong on video | One to two days |
