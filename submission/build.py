"""Build the Group01 submission Word files, PDFs and zip from the Markdown sources in this folder.

    uv run --with pypdf --with reportlab --with matplotlib --with markdown --with python-docx python submission/build.py [Name ...] [--docx]
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


def body(name):
    text = (HERE / f"{name}.md").read_text(encoding="utf-8")
    text = (text.replace("{{SIMULATOR}}", simulator_table() if "{{SIMULATOR}}" in text else "")
            .replace("{{READERS}}", reader_table() if "{{READERS}}" in text else "")
            .replace("{{REQUESTS}}", request_table() if "{{REQUESTS}}" in text else "")
            .replace("{{DEV}}", behaviour_table("eval/guardrails_v2/sonnet_dev/inbox_results.csv", "dev") if "{{DEV}}" in text else "")
            .replace("{{HELDOUT}}", behaviour_table("eval/guardrails_v2/sonnet_heldout/inbox_results.csv", "heldout") if "{{HELDOUT}}" in text else "")
            .replace("{{GITHUB}}", GITHUB).replace("{{DEMO_LINK}}", DEMO_LINK))
    import markdown
    text = re.sub(r'<div class="(small|failure)">', r'<div class="\1" markdown="1">', text)
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "md_in_html", "sane_lists"])

    def figure(match):
        alt = re.search(r'alt="([^"]*)"', match.group(1))
        text = match.group(2) or (alt.group(1) if alt else "")
        caption = f"<figcaption>{text}</figcaption>" if text else ""
        return f"<figure>{match.group(1)}{caption}</figure>"
    return re.sub(r"(?:<p>\s*)?(<img[^>]*>)(?:\s*</p>)?(?:\s*<p class=\"fig\">(.*?)</p>)?", figure, html, flags=re.S)


def render(name, title):
    html_body = body(name)
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


def word(name, title):
    """The same document as an editable Word file, built from the same HTML as the PDF."""
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    from lxml import html as lxml_html

    def rgb(hex_colour):
        return RGBColor.from_string(hex_colour.lstrip("#"))

    def shade(cell, fill):
        props = cell._tc.get_or_add_tcPr()
        node = OxmlElement("w:shd")
        node.set(qn("w:val"), "clear"), node.set(qn("w:fill"), fill.lstrip("#"))
        props.append(node)

    def soften(grid):
        props = grid._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            line = OxmlElement(f"w:{edge}")
            line.set(qn("w:val"), "none" if edge in ("left", "right", "insideV") else "single")
            line.set(qn("w:sz"), "4"), line.set(qn("w:color"), "D5DCE4")
            borders.append(line)
        props.append(borders)
        margins = OxmlElement("w:tblCellMar")
        for edge, twips in (("top", 45), ("bottom", 45), ("left", 90), ("right", 90)):
            node = OxmlElement(f"w:{edge}")
            node.set(qn("w:w"), str(twips)), node.set(qn("w:type"), "dxa")
            margins.append(node)
        props.append(margins)

    def field(paragraph, code):
        run = paragraph.add_run()
        for kind, text in (("begin", None), (None, code), ("end", None)):
            if kind:
                node = OxmlElement("w:fldChar")
                node.set(qn("w:fldCharType"), kind)
            else:
                node = OxmlElement("w:instrText")
                node.set(qn("xml:space"), "preserve")
                node.text = text
            run._r.append(node)
        run.font.size, run.font.color.rgb = Pt(7.5), rgb(MUTED)

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2)
    section.top_margin, section.bottom_margin = Cm(1.8), Cm(1.8)
    styles = doc.styles
    styles["Normal"].font.name, styles["Normal"].font.size = "Arial", Pt(10.5)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    styles["Normal"].paragraph_format.line_spacing = 1.15
    for level, size, colour in ((1, 22, INK), (2, 14, INK), (3, 11, "#3A4757")):
        style = styles[f"Heading {level}"]
        style.font.name, style.font.size, style.font.bold, style.font.color.rgb = "Arial", Pt(size), True, rgb(colour)
        for attribute in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            style.element.rPr.rFonts.attrib.pop(qn(attribute), None)
        style.paragraph_format.space_before, style.paragraph_format.space_after = Pt(14 if level < 3 else 9), Pt(4)
    styles["Footer"].font.size, styles["Footer"].font.color.rgb = Pt(7.5), rgb(MUTED)
    footer = section.footer.paragraphs[0]
    run = footer.add_run(f"Group 01  Threadline  {title}    Page ")
    run.font.size, run.font.color.rgb = Pt(7.5), rgb(MUTED)
    field(footer, "PAGE")
    footer.add_run(" of ").font.size = Pt(7.5)
    field(footer, "NUMPAGES")

    def inline(paragraph, node, bold=False, italic=False, code=False, size=None):
        if node.text:
            put(paragraph, node.text, bold, italic, code, size)
        for child in node:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag == "br":
                paragraph.add_run().add_break()
            elif tag == "img":
                picture(paragraph, child)
            else:
                inline(paragraph, child, bold or tag in ("strong", "b", "th"), italic or tag in ("em", "i"), code or tag == "code", size)
            if child.tail:
                put(paragraph, child.tail, bold, italic, code, size)

    def put(paragraph, text, bold, italic, code, size):
        text = re.sub(r"\s+", " ", text)
        if not text.strip() and not paragraph.runs:
            return
        run = paragraph.add_run(text)
        run.bold, run.italic = bold, italic
        if code:
            run.font.name, run.font.color.rgb = "Menlo", rgb(INK)
            run.font.size = Pt((size or 10) - 1)
        elif size:
            run.font.size = Pt(size)

    def picture(paragraph, node):
        from PIL import Image
        path = (HERE / node.get("src")).resolve()
        width, height = Image.open(path).size
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.keep_with_next = True
        paragraph.add_run().add_picture(str(path), width=Cm(min(16.5, 11.5 * width / height)))

    def table(container, node, size):
        rows_ = node.xpath(".//tr")
        width = max(len(r.xpath("./th|./td")) for r in rows_)
        grid = container.add_table(rows=len(rows_), cols=width)
        grid.style, grid.alignment = "Table Grid", WD_TABLE_ALIGNMENT.CENTER
        soften(grid)
        for i, row in enumerate(rows_):
            for j, cell_node in enumerate(row.xpath("./th|./td")):
                cell = grid.cell(i, j)
                paragraph = cell.paragraphs[0]
                paragraph.paragraph_format.space_after = Pt(0)
                if "right" in (cell_node.get("style") or "") or cell_node.get("align") == "right":
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                inline(paragraph, cell_node, bold=cell_node.tag == "th", size=size)
                if cell_node.tag == "th":
                    shade(cell, "#F0F3F6")
        weights = [4 + min(40, max(9, *(len(r.xpath("./th|./td")[j].text_content()) if j < len(r.xpath("./th|./td")) else 0 for r in rows_)))
                   for j in range(width)]
        floors = [.35 + .2 * max((len(word) for r in rows_ if j < len(r.xpath("./th|./td"))
                                  for word in r.xpath("./th|./td")[j].text_content().split()), default=1) for j in range(width)]
        sizes = [max(floor, 17 * share / sum(weights)) for floor, share in zip(floors, weights)]
        give = [size - floor for size, floor in zip(sizes, floors)]
        excess = sum(sizes) - 17
        if excess > 0 and sum(give):
            sizes = [size - excess * g / sum(give) for size, g in zip(sizes, give)]
        grid.autofit = False
        for j, size in enumerate(sizes):
            grid.columns[j].width = Cm(size)
            for cell in grid.columns[j].cells:
                cell.width = Cm(size)
        if rows_ and rows_[0].xpath("./th"):
            node_ = OxmlElement("w:tblHeader")
            node_.set(qn("w:val"), "true")
            grid.rows[0]._tr.get_or_add_trPr().append(node_)
        container.add_paragraph().paragraph_format.space_after = Pt(2)

    def block(container, node, size=None, list_style=None):
        for child in node:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag in ("h1", "h2", "h3", "h4"):
                inline(container.add_paragraph(style=f"Heading {min(int(tag[1]), 3)}"), child)
            elif tag == "p":
                paragraph = container.add_paragraph(style=list_style) if list_style else container.add_paragraph()
                inline(paragraph, child, size=8.5 if child.get("class") == "fig" else size)
                if child.get("class") == "fig":
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        run.font.color.rgb = rgb(MUTED)
                if node.tag == "body" and child.getprevious() is not None and child.getprevious().tag == "h1":
                    for run in paragraph.runs:
                        run.font.color.rgb = rgb(MUTED)
            elif tag in ("ul", "ol"):
                for item in child.xpath("./li"):
                    style = "List Bullet" if tag == "ul" else "List Number"
                    if item.xpath("./p|./ul|./ol"):
                        block(container, item, size, style)
                    else:
                        inline(container.add_paragraph(style=style), item, size=size)
            elif tag == "table":
                table(container, child, size or 8.5)
            elif tag == "pre":
                paragraph = container.add_paragraph()
                paragraph.paragraph_format.left_indent = Cm(.4)
                for k, line in enumerate(child.text_content().rstrip("\n").split("\n")):
                    if k:
                        paragraph.add_run().add_break()
                    run = paragraph.add_run(line)
                    run.font.name, run.font.size = "Menlo", Pt(8.5)
            elif tag == "div" and child.find(".//svg") is not None:
                drawing = child.find(".//svg")
                _, _, width, height = (float(v) for v in drawing.get("viewbox", drawing.get("viewBox")).split())
                page = HERE / f".{name}.svg.html"
                shot = HERE / f".{name}.svg.png"
                page.write_text("<html><body style='margin:0;background:#fff'>" + lxml_html.tostring(drawing, encoding="unicode")
                                .replace("<svg", "<svg style='width:1600px;height:auto;display:block'", 1) + "</body></html>", encoding="utf-8")
                subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--screenshot={shot}",
                                f"--window-size=1600,{round(1600 * height / width)}", page.as_uri()], capture_output=True, check=True, timeout=120)
                paragraph = container.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.add_run().add_picture(str(shot), width=Cm(16.5))
                page.unlink(), shot.unlink()
            elif tag == "div" and child.get("class") == "key":
                items = child.xpath("./div")
                strip = container.add_table(rows=1, cols=len(items))
                strip.style = "Table Grid"
                for cell, item in zip(strip.rows[0].cells, items):
                    shade(cell, "#EEF4FC")
                    figure = item.find("b")
                    run = cell.paragraphs[0].add_run(figure.text_content())
                    run.bold, run.font.size, run.font.color.rgb = True, Pt(13), rgb(COBALT)
                    note = cell.add_paragraph((figure.tail or "").strip())
                    note.runs[0].font.size = Pt(8)
                container.add_paragraph().paragraph_format.space_after = Pt(2)
            elif tag == "div" and child.get("class") == "note":
                box = container.add_table(rows=1, cols=1)
                box.style = "Table Grid"
                cell = box.cell(0, 0)
                shade(cell, "#F4F1EA")
                first = cell.paragraphs[0]
                if len(child) == 0 or all(c.tag not in ("p", "ul", "ol", "table", "h3") for c in child):
                    inline(first, child, size=9.5)
                else:
                    block(cell, child, 9.5)
                    if not first.text:
                        first._p.getparent().remove(first._p)
                container.add_paragraph().paragraph_format.space_after = Pt(2)
            elif tag in ("div", "blockquote", "li"):
                block(container, child, 8.5 if child.get("class") == "small" else size, list_style)
            elif tag == "figure":
                picture(container.add_paragraph(), child.find("img"))
                caption = child.find("figcaption")
                if caption is not None:
                    line = container.add_paragraph()
                    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = line.add_run(caption.text_content())
                    run.font.size, run.font.color.rgb = Pt(8.5), rgb(MUTED)
            elif tag == "img":
                picture(container.add_paragraph(), child)
            elif tag == "hr":
                container.add_paragraph()

    tree = lxml_html.fromstring(f"<html><body>{body(name)}</body></html>")
    block(doc, tree.find("body"))
    doc.core_properties.title, doc.core_properties.author = f"Group 01 Threadline: {title}", "DSS5105 Group 01"
    doc.save(OUT / f"{name}.docx")


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
        word(name, DOCS[name])
        print(f"{name}.docx")
        if "--docx" in sys.argv:
            continue
        pages, raw, page = render(name, DOCS[name])
        raw.unlink()
        page.unlink()
        print(f"{name}.pdf  {pages} pages")


if __name__ == "__main__":
    main()
