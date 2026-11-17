"""Take the task-list screenshots with Playwright (headless Chromium). Run by take.sh.

Usage: python take.py BASE_URL OUT_DIR
"""

import os
import re
import sys
import urllib.request

from playwright.sync_api import sync_playwright

CLOCK = "2026-10-14T09:00:00+05:30"   # Wed 14 Oct, the seed week moved on by take.sh


def themes(base):
    """Every theme id in the served somaari-common theme.js, in picker order (one theme-<id>.png each)."""
    with urllib.request.urlopen(base.rstrip("/") + "/theme/theme.js") as r:
        js = r.read().decode("utf-8")
    block = js[js.index("var THEMES = {"):js.index("};", js.index("var THEMES = {"))]
    return re.findall(r'"([a-z0-9-]+)"\s*:\s*\{', block)


# (file, theme, route, width, height, action); the theme-<id>.png shots are added per theme in main().
SHOTS = [
    ("today.png", "rangoli", "today", 1400, 560, None),
    ("edit.png", "rangoli", "today", 1400, 560, "edit"),
    ("done.png", "rangoli", "done", 1400, 620, None),
    ("calendar-week.png", "rangoli", "calendar", 1400, 600, None),
    ("phone-today.png", "rangoli", "today", 390, 844, None),
    ("phone-dashboard.png", "rangoli", "dashboard", 390, 844, "scroll-main"),
]


def main(base, out_dir):
    shots = [(f"theme-{t}.png", t, "dashboard", 1400, 1020, None) for t in themes(base)] + SHOTS
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        for name, theme, route, w, h, action in shots:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                      timezone_id="Asia/Kolkata", locale="en-IN")
            page = ctx.new_page()
            page.clock.set_fixed_time(CLOCK)
            page.goto(f"{base}?theme={theme}#/{route}")
            page.locator(f"#page-{route}:not([hidden])").wait_for()
            page.wait_for_load_state("networkidle")
            page.locator(f"#page-{route} .tkey").first.wait_for()
            if action == "edit":
                page.locator("#page-today .row .edit-btn").first.click()
                page.locator("#page-today .row.editing").wait_for()
                page.locator("#page-today .row.editing input").first.evaluate("e => e.blur()")
            elif action == "scroll-main":
                page.locator("#main").evaluate("e => e.scrollIntoView()")
            page.mouse.move(w - 2, h - 2)
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(out_dir, name))
            print("wrote", name)
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main(*sys.argv[1:3])
