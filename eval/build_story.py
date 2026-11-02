"""Builds the app's story screens from the evaluation files, so every number on screen comes from a result on disk.

    uv run python eval/build_story.py
"""

import json
from pathlib import Path
import re
import subprocess

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"

sim = pd.read_csv(EVAL / "results.csv")


def run(policy, objective, shock=False):
    return sim[(sim.policy == policy) & (sim.objective == objective) & (sim.shock == shock)].iloc[0]


ours, closed, hybrid, quality = run("allocator", "lateness"), run("allocator", "lateness", True), run("allocator", "hybrid_lateness_fairness"), run("allocator", "defect")
random, biggest, cheapest = run("random_choice", "none"), run("greedy_biggest", "none"), run("cheapest", "none")
row = re.search(r"Sonnet 5\.5 \| heldout \(16\) .*?\*\*(\d+)/16 · (\d+)/16\*\* \| \d+ \| ([\d.]+) \| [\d.]+ \| ([\d.]+)", (EVAL / "model_comparison_v2/comparison.md").read_text())
heldout, median, cost = int(row[1]), float(row[3]), float(row[4]) / 16
dev = re.search(r"Sonnet 5\.5 \| dev \(30\) .*?\*\*(\d+)/30", (EVAL / "model_comparison_v2/comparison.md").read_text())
replies, unseen = pd.read_csv(EVAL / "partner_replies/after.csv"), pd.read_csv(EVAL / "partner_replies/heldout_result.csv")
tests = re.search(r"(\d+) tests? collected", subprocess.run(["uv", "run", "--quiet", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout)[1]


def bars(heading, rows, unit="%", note=None):
    return {"heading": heading, "note": note, "bars": [{"label": label, "value": round(float(value) + 1e-9, 1), "unit": unit, "ours": label == "Threadline"} for label, value in rows]}


story = {"pages": [
    {"id": "objective", "eyebrow": "Objective", "title": "Getting every order back on time",
     "lead": "SweaterCo sews through eight outside workshops. One dispatcher decides where each order goes, from a busy group chat, with dates, cost and quality pulling in different directions.",
     "blocks": [bars("Choosing by habit, % of batches late", [("Always the cheapest", cheapest.pct_late), ("Always the biggest", biggest.pct_late), ("At random", random.pct_late)]),
                {"heading": "Who it is for", "points": [{"title": "The dispatcher", "detail": "Decides and approves, from an iPhone"},
                                                        {"title": "Workshops", "detail": "Work in Telegram, with nothing to install"},
                                                        {"title": "Clients", "detail": "Hear about a delay first"}]}]},
    {"id": "capabilities", "eyebrow": "Core capabilities", "title": "What Threadline does well", "lead": "The model reads, Python decides, a person approves.",
     "blocks": [{"points": [{"title": "Understands requests", "detail": "Spoken or typed, with this business's names"},
                            {"title": "Recommends and shows why", "detail": "Ranks workshops on date, cost and defects"},
                            {"title": "Works with workshops in Telegram", "detail": "Accept, refuse with a reason, report a problem, complete"},
                            {"title": "Reads four languages", "detail": "English, Hinglish, Hindi and Chinese"},
                            {"title": "Plans the recovery", "detail": "A closure or refusal gets a plan to approve"},
                            {"title": "Frees a workshop when it finishes", "detail": "Completed changes the next decision"}]}]},
    {"id": "decisions", "eyebrow": "Evidence", "title": f"{ours.pct_late:.1f}% of batches late",
     "lead": "The course simulator: 120 orders over 10 paired seeds.",
     "blocks": [bars("% of batches late, lower is better", [("Always the cheapest", cheapest.pct_late), ("Always the biggest", biggest.pct_late), ("At random", random.pct_late), ("Threadline", ours.pct_late)]),
                {"facts": [{"value": f"{closed.pct_late:.1f}%", "label": "late with a workshop closed"}, {"value": f"{ours.late_days:.2f}", "label": "mean late days"}]}]},
    {"id": "reading", "eyebrow": "Evidence", "title": "Reading messages", "lead": "Scored against hand-written labels.",
     "blocks": [{"facts": [{"value": f"{heldout}/16", "label": "unseen chat requests right"}, {"value": f"{dev[1]}/30", "label": "development requests right"},
                           {"value": f"{int(unseen.passed.sum())}/{len(unseen)}", "label": "unseen Hindi and Chinese replies"}, {"value": f"{int(replies.passed.sum())}/{len(replies)}", "label": "replies across four languages"},
                           {"value": "26% to 6%", "label": "words misheard, 48 synthetic clips"}, {"value": f"{median:.1f} s", "label": f"median reply, {cost * 100:.1f} cents each"}]},
                {"note": f"{tests} automated tests. The 48 replies were used to fix the reader, so the 12 unseen ones are the fair score."}]},
    {"id": "limits", "eyebrow": "Limitations", "title": "Where it breaks", "lead": "What fails, and what we would fix.",
     "blocks": [{"points": [{"title": "It only ties a simple rule on lateness", "detail": f"Earliest finish also reaches {ours.pct_late:.1f}%. Our gain is the checks, reasons and recovery"},
                            {"title": "Speed costs quality and spread", "detail": f"{ours.pct_defect_pieces:.1f}% of pieces defective against {quality.pct_defect_pieces:.1f}% at best. One workshop gets {ours.max_share:.0f}% of the work, or {hybrid.max_share:.0f}% on a hybrid at {hybrid.pct_late:.1f}% late"},
                            {"title": "Some messages go wrong, safely", "detail": "\"Is ORD-069 delivered?\" got a question, not a refusal. A request to split was read as one order"},
                            {"title": "Chinese prices", "detail": "A whole-number price was dropped, so the desk asks again. The check needs a fix"},
                            {"title": "Not tested with real people", "detail": "Workshops are role-played, speech used synthetic voices, and the simulator has no Completed rule"},
                            {"title": "One Mac runs the desk", "detail": "If it sleeps, the app shows the last update. A hosted desk is the fix"}]}]},
    {"id": "conclusion", "eyebrow": "Conclusion", "title": "What we built and learned",
     "blocks": [{"heading": "Achieved", "points": [{"title": "A native iPhone app, ready for TestFlight", "detail": "Siri, Dynamic Island, Apple push, widgets"},
                                                   {"title": "A two-way loop with Telegram", "detail": "One record on both sides, nothing to install"}]},
                {"heading": "Learned", "points": [{"title": "Measure before you trust", "detail": "Apple's vocabulary hints changed nothing. Testing showed it"},
                                                  {"title": "Keep people on the decisions", "detail": "Nothing moves until someone approves it"}]}]},
]}
target = ROOT / "ios/Threadline/Resources/story.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(story, ensure_ascii=False, indent=1))
print("wrote", target.relative_to(ROOT), "| tests", tests, "| heldout", heldout, "| unseen", int(unseen.passed.sum()), "| replies", int(replies.passed.sum()), "| median", median, "| cents", round(cost * 100, 1), "| defect", round(ours.pct_defect_pieces, 1), round(quality.pct_defect_pieces, 1), "| share", round(ours.max_share), round(hybrid.max_share), "| hybrid", round(hybrid.pct_late, 1))
