# Final demo voiceover (120 seconds)

About 260 words, read at a calm 130 to 135 words a minute, which leaves room for clicks. Section times match
`final_demo_storyboard.md`.

**[0:00–0:10] Introduction**
This is Threadline, a dispatch desk for Sweater Co. Every day, requests to send garment batches to partner workshops arrive in a busy group chat.

**[0:10–0:24] Interpret the request**
Here, the boss needs one hundred and fifty vests for Cotton Club by the ninth of April, as fast as possible. A language model reads the message and turns it into structured fields. It does not choose the workshop.

**[0:24–0:38] Validate and evaluate**
Python then checks every field against the order book, confirms the dates, and evaluates all eight workshops for eligibility, queue, return date and cost. Each stage is timed and traced.

**[0:38–0:54] The recommendation**
The engine recommends Nimble Needle: back on the fourth of April, five days early, at a cost of one hundred and eighty. Every number is checked against the tools. It wins because it finishes zero point three days sooner than FreshStart.

**[0:54–1:12] The network**
The workshop network shows the same decision. The batch is checked against every workshop, three are ruled out with a reason, and the route goes to Nimble Needle. FreshStart, the alternative, would be cheaper but a little later.

**[1:12–1:22] Human confirmation**
Nothing happens until the dispatcher confirms. One click records the decision and updates the queue, once.

**[1:22–1:35] Audit evidence**
The audit record keeps the original message, the parsed request, the candidates and the reason, so the decision can be reviewed later.

**[1:35–1:50] Simulation results**
We also tested the policy in the course simulator over ten seeds. It keeps late batches at one point six seven percent, far below the supplied baselines, and ties the strongest simple rule, earliest finish.

**[1:50–2:00] Conclusion**
Threadline keeps the roles separate: AI interprets the request, deterministic Python decides, and a person approves.
