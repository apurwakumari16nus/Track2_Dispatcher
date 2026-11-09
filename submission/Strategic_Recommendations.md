# Strategic recommendations

Where else can GenAI help industry? This paper is Group 01's answer for Track 2. We suggest three opportunities that a small team could start on soon, and we chose them with a test based on what we measured on our own system.

We did not start by asking which industry needs AI. We asked a narrower question: where do small firms coordinate work through chat, against a record that can be checked, with a real cost when someone gets it wrong? Most of the well-known answers to that question already have funded companies in them. Three do not, and two of those three are inside the supply chain our project was built for:

- evidence of hidden subcontracting in apparel supply chains,
- a job-work ledger for Indian garment firms,
- trip confirmation for small truck fleets in India.

## 1. What our own project taught us

We built a dispatch desk and expected the AI to add most value in making the decision. Our tests showed something different:

- On the course simulator, a one-line rule (pick the earliest finish) tied our allocator on every metric.
- On chat requests the system had not seen, keyword rules written without looking at the messages got 8 of 16 right. Our LLM reader got 15 of 16. On a second set of 34 new requests, it got 33 of 34 on behaviour, and the same keyword rules got 16 of 34.
- Keyword rules written after looking at the messages got 16 of 16 on those messages, then dropped to 9 of 16 on new ones.
- Reading one message cost about one US cent and took about two seconds.

So in our project, GenAI was useful for one narrow and cheap job. It turned messy, unplanned messages into records that code could check, and it knew when to ask a follow-up question. The decision itself could stay as plain code.

We turned this into five tests for any new idea:

1. **Chat in, record out.** Is the work coordinated through messages that a fixed form could capture?
2. **A record to check against.** Can code test what the model read?
3. **A cost to being wrong.** Does a mistake carry a legal or money cost, so that paying for a person's approval makes sense?
4. **Nobody holds the risk.** Can the business avoid carrying stock, credit or freight on its own balance sheet?
5. **Few funded players.** Is the workflow still open?

Test 4 comes from an expensive failure in a nearby market. Convoy, a digital freight broker, was valued at $3.8 billion about 18 months before it closed in October 2023. FreightWaves reports that it undercut the market, never earned real margins, and that its automation did not turn into profit [1].

## 2. Screening nine candidates

We scored nine ideas against the five tests. The scores are our own judgement.

| Candidate | Chat in, record out | Check | Cost of error | No risk held | Open? | Verdict |
|---|---|---|---|---|---|---|
| Apparel sub-tier evidence | Yes | Yes | High | Yes | Mostly | Pick 1 |
| Job-work ledger, Indian garment firms | Yes | Yes | High | Yes | Yes, at the chat step | Pick 2 |
| Small-fleet trip confirmation, India | Yes | Yes | Medium | Yes, if not a broker | Partly | Pick 3 |
| Fax referral intake, US clinics | Yes | Yes | High | Yes | No. Tennr raised $101M at $605M in 2025 [S] | Crowded |
| Freight forwarder email | Yes | Yes | Medium | Yes | No. Freightmate $5M; others funded [S] | Crowded |
| Port agent email | Yes | Partly | Medium | Yes | No. Sedna about $86M in total [S] | Crowded |
| Home-services call handling | Voice | Weak | Low | Yes | No. Several funded voice agents [S] | Crowded |
| Construction RFIs | Yes | Partly | High | Yes | Unclear. Zero RFI $14M seed [S]; Procore not checked | Hold |
| EUDR smallholder plot data | Yes | Yes | High | Yes | Not checked | Watch. Applies from 30 Dec 2026 [2] |

[S] means we saw the figure only in a search summary (see section 6). An RFI is a request for information, the formal question a contractor sends about drawings or specifications on a building project. EUDR is the EU Deforestation Regulation, which asks companies to show where certain commodities were grown.

## 3. Opportunity 1: hidden subcontracting evidence for apparel

### The problem

A brand places an order with a factory, and the factory quietly passes some of the work to another workshop. The best data we found comes from Caro et al. (2021), who studied 32,477 orders handled by one global sourcing manager, made in 226 factories for 30 buyers. In that data, 36.4% of orders were subcontracted without authorisation [3]. The authors warn that this is one dataset and should not be read as an industry rate. The brands that need this evidence have trouble getting it, because the workshop at the bottom of the chain has no system to fill in.

### Why now

Two EU rules have changed recently, and much of the common advice has not caught up.

The EU's due-diligence law has become much narrower. This law is the Corporate Sustainability Due Diligence Directive (CSDDD), which makes large companies check for human-rights and environmental harm in their supply chains. After the Omnibus deal, an EU package that simplified it, the CSDDD covers only companies with more than 5,000 staff and EUR 1.5 billion turnover, and compliance starts on 26 July 2029. Companies should only ask partners with fewer than 5,000 staff for information as a last resort, and the request must be "targeted, reasonable and proportionate" [4].

The Forced Labour Regulation (FLR) was not narrowed. It bans products made with forced labour from the EU market and applies from 14 December 2027. It covers every product sold in the EU, and in an investigation a company can be asked how it deals with forced-labour risk in its supply chain [5].

Taken together, we think demand is moving away from annual reports and towards proof about a specific product. At the same time, the rules discourage sending long surveys to small partners. A questionnaire on a supplier portal does not fit that situation well. A single question about a single order, sent in the workshop's own language through the app it already uses, fits better, because it is targeted and proportionate from the start. Our desk already sends messages of this kind.

### The buyer can tell where to ask

Caro et al. also found that subcontracting can be predicted. When the order price is 25% below the usual price, the chance of subcontracting rises by at least 3.3 percentage points. Their model predicted more than 80% of orders correctly on data it had not been trained on [3]. This means brands partly cause the behaviour they later audit. A sensible product would not ask every workshop about every order. It would use the order price and the factory's history to decide which orders get a question, which also helps meet the proportionate requirement.

### Who is already there

TrusTrace is the clear leader. It raised a $24M growth round in January 2024 [6], and the same report [6] lists Adidas and Asics among its customers. TrusTrace sells to brands and works best with suppliers who are willing to use a platform. We could not find out how far any platform reaches into unregistered workshops, and we could not find usable data on Sourcemap or Retraced. So our view that few companies are doing this is a judgement, and we have no data to back it. One phone call to a sourcing manager before building would test it.

### Implementation

| Step | What to build | What we reuse from our code |
|---|---|---|
| Schema | Order, unit, who made it, subcontracted yes/no, photo or document | Change the extraction form |
| Check | Compare against the purchase order and the approved-factory list | The same post-check pattern |
| Ask | One message per order in the workshop's language, on Telegram or an approved WhatsApp route | `languages.py`, `partners.py` |
| Approve | A compliance officer reviews mismatches. Nothing is cleared automatically | The same slide to approve |
| Report | An evidence pack for each order, showing who said what and when | The audit log |

For a pilot we would work with one sourcing agent or mid-size brand in one country, covering 50 orders over 8 weeks with two people. At 20 messages per order and one cent per message, reading would cost about $10 for the whole pilot. We would stop the pilot if fewer than half of the workshops answer, or if the buyer will not act on a mismatch.

### Weakness

A workshop that is hiding subcontracting will not admit it in chat. The tool makes honest answers cheap to give and makes false answers easier to spot through cross-checks. It will not catch someone who is determined to lie, so photos, payment records and audits are still needed.

## 4. Opportunity 2: job-work ledger for Indian garment firms

### The problem

Our own project sends batches of work to outside workshops. In India this practice is called job work: a manufacturer (the principal) sends goods to another unit (the job worker) for processing and keeps ownership of them. It comes with tax paperwork. The goods can travel on a delivery challan, which is a dispatch note, without paying GST (India's goods and services tax) when they leave. In return, the principal has to keep a paper trail [7]:

- Inputs must come back within one year, and capital goods within three years. If they do not, the original dispatch is treated as a sale, and GST and interest become due.
- The principal files Form ITC-04, a return listing goods sent to and received from job workers. Firms with turnover above ₹5 crore file it every quarter, and smaller firms file it every six months.
- Goods passed from one job worker to another still count under the original dispatch.

Terra Insight describes what keeping this trail involves. Each return has to be matched to its outbound challan, a chain of several job workers has to be treated as one batch, process wastage has to be allowed for, and every open balance has to be aged [7]. Our desk's event log already does this kind of tracking, for a different purpose.

The record the tax authorities want is already being typed, but into chat. Messages like "Sent 400 pieces to Ravi's unit", "120 back today" and "20 rejected" contain the ledger. Accounting packages only start working after someone has keyed these messages in by hand. A chat reader would sit one step earlier, where the data is first created.

### Who is already there

Plenty of software can file the return or print the challan, including Udyog ERP, LOGIC ERP, Vyapar and an Odoo add-on [S]. A Capterra listing for Kamna, a production tracker for garment job-work houses, says many owners still track lots in paper registers, WhatsApp groups or Excel [S]. That is a vendor's claim, but it matches what we saw in our own project brief. In one search we did not find any product that reads the chat and fills in the ledger. One search is weak evidence that no such product exists, and Kamna is the first competitor we would look at closely.

### Implementation

| Step | What to build |
|---|---|
| Schema | Challan, job worker, goods, quantity, direction, rejected, date |
| Check | Compare quantity against the open balance. Python ages each challan and flags those close to one year |
| Approve | The accountant confirms exceptions, not every line |
| Output | The register required under section 143 of India's CGST Act, and an ITC-04 export for the firm's accountant |

This is the easiest of the three to build, because the checks are simple arithmetic. For a pilot we would work with one unit in Tiruppur or Ludhiana that uses five job workers, for one quarter, and compare our output line by line with the return it filed. Based on our cost figures, this would cost about $0.22 per day at 20 messages. We would stop if the accountant's line-match rate is lower than what they get by hand.

### Risks

Tax advice carries legal liability, so the tool should prepare records for a tax professional and should never file anything itself. Filing rules change, and our source is a vendor's explainer, so a tax professional needs to check the current rules first. WhatsApp's API rules also apply, as described at the end of section 5.

## 5. Opportunity 3: trip confirmation for small truck fleets

### The problem

Redseer estimates that India has about 12.5 million trucks and 3.5 million operators. About 75% of operators own fewer than five trucks, and most find loads through brokers. Redseer also reports that a truck sits idle for 24 to 48 hours each time it waits for a load [8]. Chat is already the main channel: Tender Truck reported moving to WhatsApp after drivers would not use its app [S].

Logistics startups that failed in this area tried to run the market themselves. Convoy took on the freight risk and set the price. Our tests point to a duller role: keep the record. A trip message such as "loaded", "stuck at the border" or "delivered, 2 cartons short" becomes a checked entry against the booked load. That makes proof of delivery and payment disputes easier to handle. The business would own no trucks, give no credit and take no price risk.

### Who is already there

BlackBuck, Vahak and TrucksUp run freight marketplaces and apps [S]. They are well funded, so this space is not empty. The gap we see is a record that belongs to the fleet owner and covers all of their brokers. A single marketplace has little reason to build that. This opportunity is the weakest of the three on the "few funded players" test, and it is the one we would drop first.

### Implementation

| Step | What to build |
|---|---|
| Schema | Load, truck, event, shortage, document photo |
| Check | Compare against the booking |
| Approve | The fleet owner confirms disputes |
| Pilot | Ten small fleets on one route for six weeks, with voice notes in Hindi and regional languages |

Our Whisper speech-to-text work has not been tested on real speakers of these languages, so the voice part is unproven. We would stop the pilot if drivers will not send one message per trip.

### A platform risk for all three

Since 15 January 2026, Meta's terms have banned AI providers from offering general-purpose chatbots through the WhatsApp Business API. A business that uses AI to serve its own customers is not affected [9]. A narrow tool that only fills a fixed form should be on the allowed side of that line. However, Meta decides at its own discretion, and the rule was written with customer service in mind, so a proper legal reading is needed before building on WhatsApp. Telegram, which we used in our project, has no such rule as far as we found, but we did not measure how many Indian workshops use it. This is the biggest open risk for opportunities 2 and 3.

## 6. Broader recommendations and limits of this paper

### Advice for any firm considering GenAI

1. **Write the simple rule first and measure it.** If a simple rule matches your model, you have learned where the model adds no value. We found this out cheaply, and it changed our whole product.
2. **Test keyword rules written without looking at the messages.** Compare them with rules written after looking. The gap tells you whether you need a model at all. Regular, predictable messages may not need one.
3. **Let the model read and let code decide.** Reading costs about a cent per message, and the audit trail this produces is what a regulator will ask for.
4. **Avoid holding the risk.** Keeping the record is a safer business than running the market.

### How far to trust this paper

Sources marked "Opened" are pages we opened, and we checked the stated facts against them. "Search summary" means we saw the claim only in a search result, usually because the page blocked automated access. A team member should open those pages before anyone relies on them.

We did not find, and do not claim:

- the number of unregistered garment workshops,
- the share of Indian freight arranged by chat,
- the totals published by US Customs and Border Protection (CBP) under the Uyghur Forced Labor Prevention Act (UFLPA), because its dashboard would not load for us,
- current data on Sourcemap and Retraced.

The scores in section 2 are our judgement. We did not interview any customers, and that should be the first next step.

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
