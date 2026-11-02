"""End-to-end response time in the app: click Evaluate -> the answer card is on screen (all 30 inbox requests, live model)."""
import csv, json, time, statistics
from playwright.sync_api import sync_playwright
URL = "http://localhost:8503"
RESULT = ".st-key-rec, .st-key-clarify, .st-key-desk_failure, .st-key-decline, .st-key-desk_outcome"
def settle(page):
    for _ in range(400):
        w = page.locator('[data-testid="stStatusWidget"]')
        if w.count() == 0 or not w.first.is_visible(): return
        time.sleep(.05)
rows = []
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    page.goto(URL, wait_until="networkidle"); page.get_by_text("Turn requests into").first.wait_for(timeout=60000); time.sleep(2)
    for n in range(1, 31):
        rid = f"R{n:02d}"
        page.locator(f".st-key-inb_{rid} button").first.click(); settle(page); time.sleep(.8)
        before = page.locator(".st-key-desk_timing").first.inner_text() if page.locator(".st-key-desk_timing").count() else ""
        t0 = time.perf_counter()
        page.locator(".st-key-desk_dispatch button").first.click()
        # Done when the run indicator is gone and a new timing bar is on screen.
        while True:
            time.sleep(.05)
            if time.perf_counter() - t0 > 120: break
            w = page.locator('[data-testid="stStatusWidget"]')
            busy = w.count() > 0 and w.first.is_visible()
            tb = page.locator(".st-key-desk_timing")
            if not busy and tb.count() and tb.first.inner_text() != before: break
        t = time.perf_counter() - t0
        txt = page.locator(".st-key-desk_timing").first.inner_text() if page.locator(".st-key-desk_timing").count() else ""
        server = txt.split("Evaluation completed in ")[1].split(" s")[0] if "Evaluation completed in " in txt else ""
        rows.append({"request": rid, "app_seconds": round(t, 2), "server_seconds": server})
        print(rid, round(t, 2), server, flush=True)
    b.close()
with open("e2e_timing.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
ts = [r["app_seconds"] for r in rows]
print(json.dumps({"n": len(ts), "median": statistics.median(ts), "p90": sorted(ts)[int(.9 * len(ts)) - 1], "max": max(ts), "under_10s": sum(t < 10 for t in ts)}))
