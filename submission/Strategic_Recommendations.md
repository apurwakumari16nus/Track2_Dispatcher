# Strategic recommendations

Where else can GenAI help industry? Group 01, Track 2. Three low-hanging opportunities, chosen with a test we measured on our own system.

**Our answer.** Do not start from "which industry needs AI". Start from a narrower question: where do small firms coordinate work through chat, against a record that can be checked, with a real cost when someone gets it wrong? Most of the famous answers are already crowded. Three are not, and two of them sit inside the supply chain we just built for.

<div class="key">
<div><b>36.4%</b>of orders subcontracted without authorisation, in 32,477 apparel orders (Caro et al., 2021)</div>
<div><b>14 Dec 2027</b>EU ban on products made with forced labour starts to apply</div>
<div><b>1 year</b>to return inputs from an Indian job worker before GST is due on them</div>
<div><b>75%</b>of Indian truck operators have fewer than five trucks (Redseer, 2024)</div>
</div>

## 1. What our own project taught us

We built a dispatch desk expecting the AI's value to be in the decision. Our tests said otherwise:

- On the course simulator, a one-line rule (earliest finish) **tied** our allocator on every metric.
- On unseen chat requests, keyword rules written without sight of the messages got **8 of 16** right. Our LLM reader got **15 of 16**. On a second set of 34 new requests, it got **33 of 34** on behaviour. We have not run the keyword rules on that set.
- Keyword rules written *with* sight of the messages got 16 of 16 on those messages, then fell to 9 of 16 on new ones.
- Reading one message cost about **one US cent** and two seconds.

So GenAI's value here is narrow and cheap. It turns messy messages nobody planned for into checked records, and it knows when to ask. The decision itself can stay plain code. That gives a screen for any new idea. We apply these five tests:

1. **Chat in, record out.** Is work coordinated through messages that a fixed form can capture?
2. **A record to check against.** Can code test what the model read?
3. **A cost to being wrong.** Does a mistake carry a legal or money cost, so a person's approval is worth paying for?
4. **Nobody holds the risk.** Does it avoid carrying stock, credit or freight on its own balance sheet?
5. **Few funded players.** Is the workflow still open?

Test 4 comes from the most expensive lesson nearby. Convoy, a digital freight broker, was valued at $3.8 billion about 18 months before it closed in October 2023. FreightWaves' account is that it undercut the market, never earned real margins, and its automation did not turn into profit [1].

## 2. Screening nine candidates

| Candidate | Chat in, record out | Check | Cost of error | No risk held | Open? | Verdict |
|---|---|---|---|---|---|---|
| **Apparel sub-tier evidence** | Yes | Yes | High | Yes | Mostly | **Pick 1** |
| **Job-work ledger, Indian garment firms** | Yes | Yes | High | Yes | Yes, at the chat step | **Pick 2** |
| **Small-fleet trip confirmation, India** | Yes | Yes | Medium | Yes, if not a broker | Partly | **Pick 3** |
| Fax referral intake, US clinics | Yes | Yes | High | Yes | No. Tennr raised $101M at $605M in 2025 [S] | Crowded |
| Freight forwarder email | Yes | Yes | Medium | Yes | No. Freightmate $5M; others funded [S] | Crowded |
| Port agent email | Yes | Partly | Medium | Yes | No. Sedna about $86M in total [S] | Crowded |
| Home-services call handling | Voice | Weak | Low | Yes | No. Several funded voice agents [S] | Crowded |
| Construction RFIs | Yes | Partly | High | Yes | Unclear. Zero RFI $14M seed [S]; Procore not checked | Hold |
| EUDR smallholder plot data | Yes | Yes | High | Yes | Not checked | Watch. Applies from 30 Dec 2026 [2] |

[S] means we saw the figure only in a search summary. See section 6.

## 3. Opportunity 1: hidden subcontracting evidence for apparel

### The problem

A brand orders from a factory. The factory quietly passes work to another one. In the best data we found, a global sourcing manager's 32,477 orders from 226 factories for 30 buyers, **36.4% of orders were subcontracted without authorisation** [3]. The authors caution that this is one dataset and not an industry rate. The people who most need this evidence cannot easily see it, because the workshop at the bottom of the chain has no system to fill in.

### Why now

The rules have moved, and the common advice is out of date.

- **The EU's due-diligence law shrank.** After the Omnibus deal, CSDDD covers only companies above 5,000 staff and EUR 1.5 billion turnover, with compliance from 26 July 2029. Requests to partners below 5,000 staff are a last resort, and must be "targeted, reasonable and proportionate" [4].
- **The Forced Labour Regulation did not.** It applies from **14 December 2027**, covers every product on the EU market, and companies may be asked in an investigation how they address forced-labour risk in their supply chains [5].

**Our insight.** Demand is moving from annual reports to proof for a specific product, and the law now frowns on burying small partners in surveys. A portal questionnaire is the wrong shape for that. One question, about one order, in the workshop's own language, in the app it already uses, is the right shape: targeted, and proportionate by construction. That is exactly what our desk already sends.

### A second insight: the buyer can tell where to ask

Caro et al. found subcontracting is predictable. At 25% below the usual price, the chance rises by at least 3.3 percentage points. Their model predicted more than 80% of orders correctly out of sample [3]. So brands partly create the behaviour they audit. A sensible product does not ask everyone everything. It uses order price and factory history to choose which orders get a question, which also keeps within the proportionate rule.

### Who is there

TrusTrace is the clear leader, with a $24M growth round in January 2024 and customers including Adidas and Asics [6]. It sells to brands, and works best with suppliers who will use a platform. We could not establish how far any platform reaches into unregistered workshops, and we could not find usable data on Sourcemap or Retraced. **So "few people doing it" is our judgement, not a finding.** Test it with one call to a sourcing manager before building.

### Implementation

| Step | What to build | From our code |
|---|---|---|
| Schema | Order, unit, who made it, subcontracted yes/no, photo or document | Change the extraction form |
| Check | Against the purchase order and approved-factory list | The same post-check pattern |
| Ask | One message per order in the workshop's language, on Telegram or an approved WhatsApp route | `languages.py`, `partners.py` |
| Approve | A compliance officer reviews mismatches. Nothing is auto-cleared | The same slide to approve |
| Report | Per-order evidence pack, with who said what and when | The audit log |

Pilot: one agent or mid-size brand, one country, 50 orders, 8 weeks, two people. At 20 messages per order and one cent each, reading costs about $10 for the pilot. **Stop if** fewer than half of workshops answer, or the buyer will not act on a mismatch.

**The honest weakness.** A workshop hiding subcontracting will not say so in chat. This tool makes honest answers cheap and lies easier to spot by cross-checking. It does not detect a determined liar. Photos, payment records and audits still matter.

## 4. Opportunity 2: job-work ledger for Indian garment firms

### The problem

Our own project sends batches to outside workshops. In India this has a tax form attached. A manufacturer can send goods to a job worker on a delivery challan, with no GST at dispatch. The cost is a paper trail [7]:

- Inputs must come back within **one year**, and capital goods within three. If not, the original dispatch is treated as a supply, with GST and interest.
- The principal files Form ITC-04, quarterly above ₹5 crore turnover and half-yearly below.
- Goods sent between job workers still count under the original dispatch.

Terra Insight describes what this requires: match each return to its outbound challan, treat multi-hop chains as one batch, allow for process wastage, and age every open balance [7]. That is what our desk's event log does, for a different purpose.

**Our insight.** The record the taxman wants is already being typed, into chat. "Sent 400 pieces to Ravi's unit", "120 back today", "20 rejected": these messages *are* the ledger. The accounting packages start after someone has keyed that in. A chat reader sits one step earlier, at the point where data is actually created.

### Who is there

Plenty of software files the return or prints the challan: Udyog ERP, LOGIC ERP, Vyapar, and an Odoo add-on [S]. A Capterra listing for Kamna, a production tracker for garment job-work houses, says many owners still run lots through paper registers, WhatsApp groups or Excel [S]. That is a vendor's claim, but it matches what we saw in our own brief. In one search we found no product that reads the chat and fills the ledger. That is thin evidence of absence, and Kamna is the first competitor to look at closely.

### Implementation

| Step | What to build |
|---|---|
| Schema | Challan, job worker, goods, quantity, direction, rejected, date |
| Check | Quantity against open balance. Python ages each challan and flags those near one year |
| Approve | Accountant confirms exceptions, not every line |
| Output | Section 143 register, and an ITC-04 export for the firm's accountant |

Effort is the lowest of the three, because the checks are simple arithmetic. Pilot: one Tiruppur or Ludhiana unit with five job workers, one quarter, compared line by line with its filed return. Our cost figures suggest about $0.22 per day at 20 messages. **Stop if** the accountant's line-match rate falls below what they get by hand.

**Risks.** Tax advice has liability, so this must prepare records for a professional and not file. Filing rules change, and our source is a vendor explainer, so a tax professional must check the current rules first. WhatsApp's API rules also apply, as section 5 covers.

## 5. Opportunity 3: trip confirmation for small truck fleets

### The problem

Redseer puts India at about 12.5 million trucks and 3.5 million operators, with about 75% owning fewer than five, mostly reached through brokers. It reports 24 to 48 hours idle per wait for a load [8]. The channel is telling: Tender Truck reported moving to WhatsApp after drivers would not adopt its app [S].

**Our insight.** Failed logistics startups tried to be the market. Convoy held the risk and the price. Our screen says to do something duller: be the record. A trip message ("loaded", "stuck at the border", "delivered, 2 cartons short") becomes a checked entry against the load. Proof of delivery and payment disputes get easier. No truck, no credit, no price risk.

### Who is there

BlackBuck, Vahak and TrucksUp run marketplaces and apps [S]. They are well funded, so this idea is not "nobody is here". The opening is the fleet owner's own record across all brokers, which a single marketplace has no reason to build. **This is the weakest of the three on "few people doing it", and the one to drop first.**

### Implementation

Schema: load, truck, event, shortage, document photo. Check: against the booking. Approve: the fleet owner confirms disputes. Pilot: ten small fleets, one lane, six weeks, with Hindi and regional voice notes, which our Whisper work has **not** tested on real speakers. **Stop if** drivers will not send one message per trip.

### A platform risk for all three

Since 15 January 2026, Meta's terms bar AI providers from distributing general-purpose chatbots through the WhatsApp Business API. A business using AI to serve its own customers is not affected [9]. A narrow, schema-bound tool should sit on the right side of that line, but Meta decides at its discretion, and the rule was written for customer service. Get a proper reading before building on it. Telegram, which we used, has no such rule that we found, but we did not measure how many Indian workshops use it. This is our biggest open risk for opportunities 2 and 3.

## 6. Broader recommendations, and how far to trust this paper

**For any firm considering GenAI:**

1. **Write the simple rule first and measure it.** If a rule ties your model, you have learned where the value is not. We found this cheaply, and it changed our whole product.
2. **Test keywords written blind.** The gap between rules written with and without sight of the messages shows whether you need a model at all. Regular messages may not need one.
3. **Let the model read and let code decide.** It costs a cent to read, and the audit trail is what a regulator will ask for.
4. **Do not hold the risk.** Be the record, not the market.

**Evidence quality.** Sources marked **opened** are pages we opened and checked the stated facts against. **Search summary** means we saw the claim only in a search result, usually because the page refused automated access. A team member should open those pages before relying on them. We did not find, and do not claim: the number of unregistered garment workshops, the share of Indian freight arranged by chat, the CBP's UFLPA totals (its dashboard would not load for us), or current data on Sourcemap and Retraced. Scores in section 2 are our judgement. No customer was interviewed, and that is the first thing to do.

## Sources

| # | Source | Status |
|---:|---|---|
| 1 | FreightWaves, "Convoy shutdown", 26 Oct 2023. [Link](https://www.freightwaves.com/news/convoy-shutdown-trucking-startup) | Opened |
| 2 | European Commission, Transition Pathways: EUDR simplification review, 2026. [Link](https://transition-pathways.europa.eu/textiles/legislative-developments/commission-publishes-simplification-review-eu-deforestation) | Opened |
| 3 | Caro, Lane, Sáez de Tejada Cuenca, "Can Brands Claim Ignorance?", *Management Science* 67(4), 2021. [Full text](https://escholarship.org/uc/item/9qj0v9x5) | Opened |
| 4 | Clifford Chance, "Omnibus I: the EU concludes CSDDD and CSRD reforms", Feb 2026. [Link](https://www.cliffordchance.com/insights/resources/blogs/business-and-human-rights-insights/2026/02/omnibus-i-the-european-union-concludes-csddd-and-csrd-reforms.html) | Opened |
| 5 | European Commission, Forced Labour Regulation (EU) 2024/3015 page. [Link](https://single-market-economy.ec.europa.eu/single-market/goods/forced-labour-regulation_en) | Opened |
| 6 | Supply Chain Dive, "TrusTrace lands $24M", 19 Jan 2024. [Link](https://www.supplychaindive.com/news/trustrace-investment-funding/704931/) | Opened |
| 7 | Terra Insight, "ITC-04 quarterly return: textile job-work reconciliation", 6 Jul 2026. A vendor explainer citing CGST s.143 and Rules 45 and 55. [Link](https://www.terra-insight.com/insights/itc-04-quarterly-return-textile-job-work-reconciliation) | Opened |
| 8 | Redseer, "Unlocking growth in India's fragmented trucking sector", 12 Dec 2024. [Link](https://redseer.com/articles/unlocking-growth-in-indias-fragmented-trucking-sector/) | Opened |
| 9 | TechCrunch, "WhatsApp changes its terms to bar general-purpose chatbots", 18 Oct 2025. [Link](https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/) | Opened |
| S | Tennr: [Fierce Healthcare](https://fiercehealthcare.com/health-tech/tennr-clinches-101m-build-out-ai-automates-patient-referral-workflows). Freightmate: [GeekWire](https://www.geekwire.com/2025/flexport-amazon-vets-raise-5m-to-automate-data-and-document-processing-for-freight-forwarders/). Sedna: [Hellenic Shipping News](https://www.hellenicshippingnews.com/sedna-announces-additional-42m-investment-advancing-its-data-driven-platform-for-maritime/). Zero RFI: [Pulse 2.0](https://pulse2.com/zero-rfi-13-8-million-raised-for-ai-construction-platform-launch-and-roll-up-strategy/). Tender Truck: [YourStory](https://yourstory.com/2025/12/bridging-the-gap-how-tender-truck-is-fixing-indias-broken-trucking-market). Kamna: [Capterra](https://www.capterra.in/software/1105299/Kamna). BlackBuck: [TechCrunch](https://techcrunch.com/2019/05/01/indias-blackbuck-raises-150-million-to-digitize-freight-and-logistics-across-india). Job-work software: [Udyog](https://www.udyogsoftware.com/erp-software-for-garment-manufacturing), [LOGIC ERP](https://www.logicerp.com/blog/?p=6981), [Vyapar](https://vyaparapp.in/videos/how-to-make-job-work-challan), [Odoo add-on](https://ecosire.com/apps/odoo/odoo-jobwork-challan-gst-india) | Search summary |
