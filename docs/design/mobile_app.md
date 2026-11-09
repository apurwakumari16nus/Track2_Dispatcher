# Threadline for iPhone

The dispatcher's phone and the workshops' Telegram are two ends of one conversation.

* **Workshops and clients stay in Telegram.** They install nothing, tap a button or
  reply in their own words, in any language.
* **The dispatcher works on the phone.** Speak a request, see what changed, approve a
  plan, message anyone. Everything said in Telegram appears here as it happens.
* **The roles have not changed.** The model reads, Python decides, a person approves.

```
 iPhone (SwiftUI)                 src/api.py            src/control.py           existing engine
 voice, Siri, widgets   <---->   FastAPI + live  <--->  one place for every <--->  intake, allocator,
                                 event stream           action                     desk, audit log
 Telegram (workshops,            telegram_bot.py  <--->  same control.py
 clients, team chat)
```

## Why native SwiftUI, not Capacitor

Capacitor wraps a web app that runs in the phone's browser engine. Streamlit runs on a
server, so there was nothing to wrap: the UI had to be rebuilt either way. Siri, Live
Activities, widgets and on-device speech are all native Swift, even inside Capacitor.
SwiftUI gives them directly, along with the system tab bar, haptics and Liquid Glass.

## Run it

Terminal, from the repository root:

```bash
uv run python src/api.py
```

Then open `ios/Threadline.xcodeproj` in Xcode, pick a simulator and press Run. The app
connects to `http://127.0.0.1:8600`.

### On your iPhone

The project is signed with team `GA5MADTKBJ`, the paid developer account.

1. Put the Mac and the phone on the same network. The phone's own hotspot works well, and
   is the safest choice for a demo because venue Wi-Fi often blocks devices from seeing each other.
2. Start the desk on the network. It reads its token from `ios/.desk_token`, a git-ignored
   file, or from `THREADLINE_API_TOKEN` if you set one:

```bash
uv run python src/api.py --lan
```

3. Plug in the phone and press Run in Xcode.
4. In the app: Settings, enter `http://<your Mac's name>.local:8600` and the token.

A test build can carry the address and token instead, so there is nothing to type: pass
`THREADLINE_HOST` and `THREADLINE_TOKEN` to `xcodebuild`. Leave them out of any build that
goes to TestFlight.

If `ios/project.yml` changes, regenerate the project with `xcodegen generate` in `ios/`.

### Connect Telegram

The bot token and allowed chats in `.env` are the same ones as before. The API runs the
bot itself, so do not run `src/telegram_bot.py` at the same time.

1. Make one Telegram group with Topics turned on, and add the bot.
2. Add the group's ID to `TELEGRAM_ALLOWED_CHATS` (`/chatid` shows it).
3. Make a topic per role-played workshop and client. In each, send `/iam QuickStitch` or
   `/iam Cotton Club`. That is the whole set-up.
4. The General topic stays the team's request chat, as it is today.
5. Send `/iam Team` in the team's chat or topic. Alerts with Approve and the morning brief
   arrive there, and `/brief` and `/where ORD-041` work there. Those two do not work in a
   workshop's or client's chat, because clients never see which workshop has the work.
6. Workshops can send `/jobs` and clients `/status`. Each sees only their own orders.

## What happens when a workshop writes

| They say | Threadline does |
|---|---|
| Accepted, started, ready, shipped (button or words) | Moves the batch straight away |
| Cannot take it | Opens a decision to place it elsewhere |
| Closed, running late, new capacity, new price | Opens an incident. Nothing changes until the dispatcher approves the plan |
| A vague reply ("running late") | Asks them for the missing date or order, automatically |
| A question, a quality problem, anything unclear | Puts it in front of a person and changes nothing |

Numbers the sender never wrote are dropped, and dates are worked out by Python. "Closed
till Monday" becomes 6 April without the model doing the arithmetic. Hinglish works:
*"light gayi hai, monday tak band rahega"* was read as closed until 6 April in a live test.

Approved changes are overlays on the supplied snapshot, so the existing engine runs
unchanged and every change traces back to who approved it. A closure ends on its own date.

## How an order is shown

Every order has one colour, one symbol and one name for each point in its life. Telegram uses
the same names in the same order, so a workshop's card and the dispatcher's phone read alike.

| Stage | Colour | Symbol | Meaning | In Telegram |
|---|---|---|---|---|
| In review | Slate | Magnifier | Waiting for your decision | |
| Sent | Violet | Paper plane | Waiting for the workshop to accept | 🟣 |
| Accepted | Cobalt | Thumbs up | Accepted, not started yet | 🔵 |
| Sewing | Cyan | Scissors | Being made at the workshop | ✂️ |
| Completed | Teal | Box | Finished at the workshop, which is free for new work | 📦 🚚 |
| Back | Green | Tick | Received and checked in | ✅ |

The rule behind the colours: cool colours walk from violet towards green as a batch gets
closer to home, warm colours always mean a problem, and green is only reached when a person
has checked the batch in. A colour never stands alone: the symbol and name travel with it.

* **The line.** Today and Work both show every stage with its count. Tap a stage to see only
  those orders.
* **Work.** Problems sit together under Needs you (declined, no answer yet, overdue, late).
  Then one section per stage, each with its own thread.
* **Order tags.** Every order is a garment swing tag: the stage on the dyed stub, then who has
  it and when it is expected back. The section's thread runs through each tag's eyelet.
* **The calendar.** Coming back shows two weeks or the whole month, with a stitch in the
  stage's colour under each day a batch returns.
* **The loom.** Network draws each workshop across the next 14 days, with each batch as a
  stitch in its stage's colour, ending the day it is due back.
* **Sewn details.** The dyed cards have a seam just inside the edge, like a woven label, and
  the slide to confirm sews its two seams as the knob passes, with a small tick per stitch.
* **Dark mode.** A deep indigo and teal backdrop with a fine twill weave, frosted glass cards
  that pick up the colour behind them, and a quieter batch of the same dye. Settings has a
  System, Light or Dark choice.

## Speed

* **Reading only where there is something to read.** The New request form already holds every
  field, so it skips the model: it answers at once and costs nothing, and every Python check
  still runs. A spoken request, or a form with a note, is read by the model and takes a few seconds.
* **Double sends.** The same words from the same party within two minutes are not read again,
  and the same problem never opens twice.
* **Timing a real phone.** Build with `THREADLINE_PROBE=1` and the app reports frame timings and desk calls per screen to `records/perf.jsonl`. It works over Wi-Fi, where Instruments may not attach. Leave it out of any build that goes to TestFlight.
* **Run a Release build on a real phone.** Debug builds are far slower there. The Xcode scheme
  runs Release for this reason. Low Power Mode also slows the phone, so turn it off for a demo.

## Your own requests

Press + on Today or Work.

* **From the order book.** Search the orders with no workshop yet, and choose what matters most.
* **A new order.** Choose the customer and product, then enter the pieces and date. It joins
  the book as the next order number. The supplied file is never changed.
* **By voice.** Say "300 hoodies for TrendCart, back by 20 April". If it is not in the book,
  the app asks before adding it.

Either way it is written as a sentence and read and checked like any other request, and it
stays In review until a decision goes out. Sending it clears any chat line for the same order.

## Why both, and not just one

Each works alone, and each does something the other cannot.

| | Telegram | The app |
|---|---|---|
| **Who it is for** | Workshops, clients, and the team on the move | The dispatcher |
| **Why that** | Nobody installs anything, it works on a cheap phone, and they can reply in their own words | One person watching 8 workshops and many orders needs the whole picture |
| **What it is good at** | Getting a reply, and reaching you when the app is closed | Seeing everything at once: the line, the calendar, the loom, plans and history |
| **What it cannot do** | Show what breaks if a workshop closes, or who has room next week | Reach a workshop that will never install it |

They share one record, so nothing is typed twice:

* A workshop's tap moves the order on your phone, and it appears as a coloured status in the conversation.
* A workshop or client can send /jobs or /status for their own work, without waiting for you.
* When something goes wrong, the team chat gets the plan with an Approve button, so a closure
  never waits for someone to open the app. Changing the plan batch by batch, and reviewing
  client notices, stay in the app.
* /brief and /where answer the team in the chat. An order posted there lands in the same list.
* Open in Telegram, from a conversation, jumps to that workshop's topic.

## Automations

Settings, Automations. All three are off until someone switches them on, and each has Run now.

| Rule | What it does |
|---|---|
| Chase a silent workshop | After 2 hours with no answer, sends one reminder from a fixed template |
| Check the day before | Asks for a status the day before a batch is booked back |
| Morning brief to the team | Posts the brief in the team's Telegram chat at 08:30 |

They only ask questions. None of them moves a batch or writes to a client, and every message
they send is labelled "Sent by Threadline". They run while the desk is running.

The same screen lists recipes for the Shortcuts app, such as a brief when you arrive at the
factory, or an NFC tag at the goods door that marks a batch received.

## One order, one batch

An order already at a workshop cannot be sent again. A second recommendation for it shows who
has it instead of the slide. Sending an order by voice also clears the group chat line that
named it, so a request cannot be booked twice from two places.

## Escalation

* **To the workshop:** silent offers and overdue batches surface as a one-tap reminder.
* **To the client:** when a batch will miss its date, a notice is drafted from the record.
  The dispatcher reviews it, and edited numbers are checked against the record again
  before it leaves. A changed date stops and asks.
* **To the planner:** Escalate on any recommendation, as before.

Clients never see which workshop has the work.

## When a workshop is free

A workshop's queue and its share of the work count only what is still in its hands. A batch
leaves both as soon as the workshop marks it Completed, not when it comes back, because
transport does not tie up its machines. A batch it declines leaves too. Completed then shows
as "completed and not back yet" on the workshop's page. So a workshop that finishes early gets
the next suitable order straight away: when Nimble Needle completes ORD-041, the same request
for 300 cardigans moves from FreshStart, back 7 April, to Nimble Needle, back 5 April.

## Voice

**Live words.** Speech has two layers. The phone's own recogniser puts words on screen the
moment you say them, in a lighter ink. Every couple of seconds the clip so far goes to the
desk on your Mac, where Whisper reads it knowing this business's workshops, customers and
goods, and those words replace the phone's in full ink. The audio goes no further than your
Mac, is deleted once read, and costs nothing. If the desk cannot answer, the phone's words
stand. The facts lift out as chips while you talk. That preview uses simple rules and does
not count. The finished request is what the model reads.

We measured this on 48 spoken dispatch requests in four synthetic voices, two of them Indian
English: Apple's model got 26% of words wrong and 123 of 140 key terms right, and the same
figures for Whisper with the names as hints were 6% and 139. Telling Apple's model the names
made no measurable difference, and neither did changing its accent setting. These are
synthetic voices, so a real speaker in a real room will differ.

**One input for everything.** Fixed rules route what you said: a briefing, a question
about a batch or workshop, a message for someone, an arrival, or a new request. Only a
new request costs a model call. Anything that writes still waits for a person.

**Siri.** These work without opening the app:

* "Hey Siri, brief me in Threadline"
* "Hey Siri, new request in Threadline", which asks for the request, says the
  recommendation and asks "Send it?"
* "Hey Siri, talk to Threadline", which opens it listening. Add this to the Action
  button or Control Center.
* "Hey Siri, where's a batch in Threadline"
* "Hey Siri, chase workshops in Threadline", which reminds anyone who has not answered
* "Hey Siri, a batch arrived in Threadline", which asks which order, then asks you to confirm

**Listen.** The button on Today reads the brief aloud, for when your hands are full. It uses
its own wording, closer to how a colleague would say it, one sentence at a time with a pause
between. It picks the best voice on the phone, and Settings, Voice for the brief lets you
choose. The iPhone's free Premium voices are much better than the ones it ships with, and
only the phone's owner can download them.

## Known limits

* **Real iPhone.** The app runs on an iPhone 15 Pro Max on iOS 27.0.1 and reaches the desk over the phone's hotspot. Real speech, Siri, the widget and real Telegram delivery are being tested next. The Action button is shown in the demo as an option, and is not needed for it.
* **Speech in the simulator.** The simulator has no dependable microphone, so it plays a labelled sample sentence instead, and Listen shows its state without sound because the simulator's voice library stalls the app. Real speech and Listen only run on a phone.
* **The Dynamic Island without the app open.** iOS stops the app about 30 seconds after you leave it, so the desk sends later stage changes through Apple's push service. That needs an `AuthKey_XXXXXXXXXX.p8` file from the Apple Developer site in the `ios` folder, which is never committed. Without it the Island catches up when you next open the app. The Mac needs internet access for pushes to go out. Tested on the real iPhone: a stage change sent 89 seconds after the app was last active reached the locked phone and lit the screen. Test builds use Apple's sandbox server, and the desk tries the production server if a token belongs there, so TestFlight needs no change here, though that path is untested.
* **Automations.** The three desk rules are tested and run from the app, but the morning brief has not yet gone to a real Telegram chat. The Shortcuts actions and NFC recipe need a real iPhone.
* **Telegram link-up.** Team alerts, Approve in the chat, /jobs, /status and the status lines are covered by automated tests with a stand-in for Telegram. None has been tried in a real group yet.
* **The web desk.** The Streamlit desk still shows queues without the Completed rule, because it reads the original log. The phone and Telegram use the rule. The evaluation is unaffected, because it has no stage events.
* **New orders on the web desk.** Orders added on the phone are known to the phone and Telegram. The Streamlit desk reads the supplied file, so it does not show them.
* **Rehearse.** The buttons on an order and the Rehearse screen stand in for a workshop. They take the same path as Telegram and are labelled role-play on the record. They only appear in demo mode.
* **Lock Screen alerts need push.** Live updates arrive while the app is open. Alerts with
  the app closed need an APNs key from the developer account, which is not set up yet.
* **Streamlit queues.** The web desk reads the audit log only, so it does not show moved
  batches. The phone is the source of truth for anything after a decision.
* **Demo data.** The default mode writes to rehearsal logs and starts from eight real
  decisions on the supplied requests. Workshop replies in role-play are labelled.
* **Delay estimates.** A closure pushes a batch back by the days closed. That is an estimate
  until the workshop gives a date.
