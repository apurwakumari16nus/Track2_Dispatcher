"""Build the Group01 submission PDFs and zip from the Markdown sources in this folder.

    uv run --with pypdf --with reportlab --with matplotlib --with markdown python submission/build.py [Name ...]
    uv run --with pypdf --with reportlab python submission/build.py --zip

Tables and charts are read from eval/ at build time, so a number in a PDF cannot drift from the
results files. Set the two links below once, and every document picks them up.
"""

from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "submission"
OUT = HERE / "Group01"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
GITHUB = "https://github.com/apurwakumari16nus/Track2_Dispatcher"
DEMO_LINK = "TO BE ADDED BEFORE SUBMISSION"
DOCS = {"Readme": "Readme", "Documentation": "Documentation", "Evaluation": "Evaluation", "Teams": "Teams",
        "Strategic_Recommendations": "Strategic recommendations"}
INK, COBALT, TEAL, CHAMP, MUTED, GRID = "#10263C", "#3278E9", "#0F9F8A", "#C8A36F", "#5B728B", "#DCE5EF"


def rows(path):
    return list(csv.DictReader(open(ROOT / path, encoding="utf-8")))


def yes(value):
    return "yes" if value == "True" else "no" if value == "False" else ""


def request_table():
    """All 30 supplied requests, one line each, from the recorded replay."""
    import json
    audit = {r["request_id"]: r for r in json.loads((ROOT / "eval/guardrails_v2/sonnet_dev/inbox_audit.json").read_text())["requests"]}
    review = {r["request_id"]: r for r in rows("eval/explanation_review.csv")}
    lines = ["| ID | Message, shortened | Expected | Ours | Workshop | Decision | Numbers | Explanation |", "|---|------|---|---|---|---|---|---|"]
    names = {"allocate": "extract", "clarify": "clarify", "refuse": "refuse", "decline": "decline"}
    for row in rows("eval/guardrails_v2/sonnet_dev/inbox_results.csv"):
        rid = row["request_id"]
        message = audit[rid]["raw_message"].split(":", 2)[-1].strip().replace("|", "/").replace(" — ", ", ").replace("…", "...")
        message = message[:58].rstrip() + ("..." if len(message) > 58 else "")
        chosen = audit[rid]["response"]["decision_record"].get("chosen_workshop") or ""
        check = review[rid]
        note = "ok"
        if check["late_flag_fits"] == "False":
            note = "late flag misplaced"
        elif check["constraint_named"] == "False":
            note = "reason not named"
        elif check["ask_needed"] == "False":
            note = "needless date ask"
        lines.append(f"| {rid} | {message} | {names[row['expected_behaviour']]} | {names[row['actual_behaviour']]} | {chosen} | {yes(row['decision_correct'])} | {yes(row['faithfulness_passed'])} | {note} |")
    return "\n".join(lines)


def behaviour_table(results, review_set):
    frame = rows(results)
    review = {r["request_id"]: r for r in rows("eval/explanation_review.csv") if r["set"] == review_set}
    names = (("allocate", "Extract"), ("clarify", "Clarify"), ("refuse", "Refuse"), ("decline", "Decline to answer"))
    lines = ["| Behaviour | Requests | Behaviour right | Decision right | Numbers traced to tools | Explanation fully clear |", "|---|---:|---:|---:|---:|---:|"]
    total = [0, 0, 0, 0, 0]

    def clear(row):
        check = review[row["request_id"]]
        return not any(check[k] == "False" for k in ("constraint_named", "late_flag_fits", "ask_needed"))

    for key, label in names:
        part = [r for r in frame if r["expected_behaviour"] == key]
        counts = [len(part), sum(r["behaviour_correct"] == "True" for r in part), sum(r["decision_correct"] == "True" for r in part),
                  sum(r["faithfulness_passed"] == "True" for r in part), sum(clear(r) for r in part)]
        total = [a + b for a, b in zip(total, counts)]
        lines.append(f"| {label} | {counts[0]} | {counts[1]}/{counts[0]} | {counts[2]}/{counts[0]} | {counts[3]}/{counts[0]} | {counts[4]}/{counts[0]} |")
    lines.append(f"| **All** | **{total[0]}** | **{total[1]}/{total[0]}** | **{total[2]}/{total[0]}** | **{total[3]}/{total[0]}** | **{total[4]}/{total[0]}** |")
    return "\n".join(lines)


def simulator_table():
    data = rows("eval/results.csv")
    seeds = rows("eval/results_per_seed.csv")

    def spread(policy, objective):
        values = [float(r["pct_late"]) for r in seeds if r["policy"] == policy and r["objective"] == objective and r["shock"] == "False"]
        mean = sum(values) / len(values)
        return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** .5

    def get(policy, objective, shock):
        return next(r for r in data if r["policy"] == policy and r["objective"] == objective and r["shock"] == shock)

    order = (("random_choice", "none", "Baseline: random choice"), ("greedy_biggest", "none", "Baseline: greedy biggest"), ("cheapest", "none", "Baseline: cheapest"),
             ("earliest_finish", "none", "Simple rule: earliest finish"), ("allocator", "lateness", "**Ours: lateness (primary)**"),
             ("allocator", "fairness", "Ours: fairness (second objective)"), ("allocator", "hybrid_lateness_fairness", "Ours: hybrid 90% lateness, 10% fairness"),
             ("allocator", "defect", "Ours: lowest defect (reported only)"))
    lines = ["| Policy | % late (SD) | Late days | Busiest share % | % defective pieces | Total cost | % late, closure | Late days, closure |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for policy, objective, label in order:
        n, s = get(policy, objective, "False"), get(policy, objective, "True")
        lines.append(f"| {label} | {float(n['pct_late']):.1f} ({spread(policy, objective):.1f}) | {float(n['late_days']):.2f} | {float(n['max_share']):.1f} | {float(n['pct_defect_pieces']):.1f} | {float(n['total_cost']):,.0f} | {float(s['pct_late']):.1f} | {float(s['late_days']):.2f} |")
    return "\n".join(lines)


def reader_table():
    lines = ["| Reader | Supplied 30: behaviour | Decision | Held-out 16: behaviour | Decision | Red-team 16: behaviour | Decision |", "|---|---:|---:|---:|---:|---:|---:|"]
    labels = {"id_only": "Order ID regex only", "keywords_blind": "Keyword rules, author blind to the requests", "keywords_seen": "Keyword rules, author had read the requests"}
    sets = {name: rows(f"eval/rule_baseline/{name}.csv") for name in ("dev", "heldout", "redteam")}
    for reader, label in labels.items():
        cells = []
        for frame in sets.values():
            part = [r for r in frame if r["reader"] == reader]
            cells += [f"{sum(r['behaviour_correct'] == 'True' for r in part)}/{len(part)}", f"{sum(r['decision_correct'] == 'True' for r in part)}/{len(part)}"]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    cells = []
    for path in ("eval/guardrails_v2/sonnet_dev/inbox_results.csv", "eval/guardrails_v2/sonnet_heldout/inbox_results.csv", "eval/redteam/after/inbox_results.csv"):
        part = rows(path)
        cells += [f"{sum(r['behaviour_correct'] == 'True' for r in part)}/{len(part)}", f"{sum(r['decision_correct'] == 'True' for r in part)}/{len(part)}"]
    lines.append("| **Sonnet 5.5 with guards (ours)** | " + " | ".join(f"**{c}**" for c in cells) + " |")
    return "\n".join(lines)


def charts():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 9, "axes.edgecolor": GRID, "text.color": INK,
                         "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK})
    (HERE / "figures").mkdir(exist_ok=True)
    data = rows("eval/results.csv")
    keys = (("cheapest", "none", "Cheapest"), ("greedy_biggest", "none", "Greedy biggest"), ("random_choice", "none", "Random"),
            ("allocator", "fairness", "Fairness"), ("allocator", "hybrid_lateness_fairness", "Hybrid 90/10"),
            ("earliest_finish", "none", "Earliest finish"), ("allocator", "lateness", "Lateness (ours)"))
    fig, ax = plt.subplots(figsize=(6.8, 2.5))
    for i, (policy, objective, label) in enumerate(keys):
        normal = float(next(r for r in data if r["policy"] == policy and r["objective"] == objective and r["shock"] == "False")["pct_late"])
        closed = float(next(r for r in data if r["policy"] == policy and r["objective"] == objective and r["shock"] == "True")["pct_late"])
        ax.barh(i + .19, normal, .36, color=COBALT, label="Normal" if i == 0 else None)
        ax.barh(i - .19, closed, .36, color=CHAMP, label="Workshop closed" if i == 0 else None)
        ax.text(max(normal, closed) + 1, i, f"{normal:.1f} / {closed:.1f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(keys)), [k[2] for k in keys])
    ax.set_xlabel("% of batches late, mean of 10 seeds")
    ax.set_xlim(0, 104)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(HERE / "figures/late_by_policy.png", dpi=220)
    plt.close(fig)

    frame = {name: rows(f"eval/rule_baseline/{name}.csv") for name in ("dev", "heldout", "redteam")}
    system = {"dev": rows("eval/guardrails_v2/sonnet_dev/inbox_results.csv"), "heldout": rows("eval/guardrails_v2/sonnet_heldout/inbox_results.csv"), "redteam": rows("eval/redteam/after/inbox_results.csv")}
    groups = (("dev", "Supplied 30"), ("heldout", "Held-out 16"), ("redteam", "Red-team 16"))
    series = (("id_only", "ID regex", "#B9C7D6"), ("keywords_blind", "Keywords, blind author", CHAMP), ("ours", "Sonnet with guards", COBALT))
    fig, ax = plt.subplots(figsize=(6.8, 2.1))
    for g, (name, label) in enumerate(groups):
        for s, (reader, _, colour) in enumerate(series):
            part = system[name] if reader == "ours" else [r for r in frame[name] if r["reader"] == reader]
            share = 100 * sum(r["behaviour_correct"] == "True" for r in part) / len(part)
            ax.bar(g + (s - 1) * .26, share, .24, color=colour, label=series[s][1] if g == 0 else None)
            ax.text(g + (s - 1) * .26, share + 1.5, f"{sum(r['behaviour_correct'] == 'True' for r in part)}", ha="center", fontsize=8)
    ax.set_xticks(range(3), [g[1] for g in groups])
    ax.set_ylabel("% behaviour right")
    ax.set_ylim(0, 140)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper center", fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "figures/readers.png", dpi=220)
    plt.close(fig)


def render(name, title):
    text = (HERE / f"{name}.md").read_text(encoding="utf-8")
    text = (text.replace("{{SIMULATOR}}", simulator_table() if "{{SIMULATOR}}" in text else "")
            .replace("{{READERS}}", reader_table() if "{{READERS}}" in text else "")
            .replace("{{REQUESTS}}", request_table() if "{{REQUESTS}}" in text else "")
            .replace("{{DEV}}", behaviour_table("eval/guardrails_v2/sonnet_dev/inbox_results.csv", "dev") if "{{DEV}}" in text else "")
            .replace("{{HELDOUT}}", behaviour_table("eval/guardrails_v2/sonnet_heldout/inbox_results.csv", "heldout") if "{{HELDOUT}}" in text else "")
            .replace("{{GITHUB}}", GITHUB).replace("{{DEMO_LINK}}", DEMO_LINK))
    import markdown
    text = re.sub(r'<div class="(small|failure)">', r'<div class="\1" markdown="1">', text)
    html_body = markdown.markdown(text, extensions=["tables", "fenced_code", "md_in_html", "sane_lists"])
    css = (HERE / "style.css").read_text(encoding="utf-8").replace("{{FONTS}}", (ROOT / "src/static/fonts").as_uri())
    page = HERE / f".{name}.html"
    page.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><base href='{HERE.as_uri()}/'><style>{css}</style></head><body>{html_body}</body></html>", encoding="utf-8")
    raw = HERE / f".{name}.raw.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={raw}", page.as_uri()], capture_output=True, check=True, timeout=120)
    return stamp(raw, OUT / f"{name}.pdf", title), raw, page


def stamp(source, target, title):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    reader, writer = PdfReader(source), PdfWriter()
    total = len(reader.pages)
    for number, page in enumerate(reader.pages, 1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        layer = BytesIO()
        pen = canvas.Canvas(layer, pagesize=(width, height))
        pen.setFont("Helvetica", 7.5)
        pen.setFillColorRGB(.36, .45, .55)
        pen.drawString(54, 26, f"Group 01  Threadline  {title}")
        pen.drawRightString(width - 54, 26, f"Page {number} of {total}")
        pen.save()
        layer.seek(0)
        page.merge_page(PdfReader(layer).pages[0])
        writer.add_page(page)
    writer.add_metadata({"/Title": f"Group 01 Threadline: {title}", "/Author": "DSS5105 Group 01"})
    with open(target, "wb") as handle:
        writer.write(handle)
    return total


def assemble():
    wanted = ["Readme.pdf", "Slide.pptx", "Video.mp4", "Documentation.pdf", "Evaluation.pdf", "Teams.pdf", "Strategic_Recommendations.pdf"]
    if (ROOT / "Presentation_Group01.pptx").exists():
        shutil.copy2(ROOT / "Presentation_Group01.pptx", OUT / "Slide.pptx")
    missing = [name for name in wanted if not (OUT / name).exists()]
    if missing:
        print("Not zipped. Missing:", ", ".join(missing))
        return
    with zipfile.ZipFile(HERE / "Group01.zip", "w", zipfile.ZIP_STORED) as archive:
        for name in wanted:
            archive.write(OUT / name, name)
    print("Wrote", HERE / "Group01.zip")


def main():
    OUT.mkdir(exist_ok=True)
    if "--zip" in sys.argv:
        return assemble()
    chosen = [a for a in sys.argv[1:] if a in DOCS] or list(DOCS)
    if "Evaluation" in chosen:
        charts()
    for name in chosen:
        pages, raw, page = render(name, DOCS[name])
        raw.unlink()
        page.unlink()
        print(f"{name}.pdf  {pages} pages")


if __name__ == "__main__":
    main()
