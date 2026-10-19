"""Record the somaari.in demo loop with Playwright (headless Chromium, no desktop needed).

New plan -> paste the sample plan -> Generate plan -> review the dated tasks -> Add to plan ->
Calendar week view with the tasks on their days. Run by record.sh, which starts a throwaway server.

Usage: python record.py URL PLAN_FILE OUT_DIR
Writes OUT_DIR/raw.webm and OUT_DIR/raw.times (START/END: seconds into raw.webm to keep).
"""

import os
import shutil
import sys
import time

from playwright.sync_api import sync_playwright

W, H = 1280, 720

# The page has no cursor in a headless recording; this draws one that follows the mouse.
CURSOR = """
addEventListener("DOMContentLoaded", () => {
  const c = document.createElement("div");
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l14 9-6.5 1.2L14 19l-2.6 1.2-3.4-6.6L3 18z"'
    + ' fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: "fixed", left: "0", top: "0", zIndex: "2147483647",
    pointerEvents: "none", transform: "translate(-100px,-100px)" });
  document.documentElement.appendChild(c);
  addEventListener("mousemove", (e) => { c.style.transform = `translate(${e.clientX - 3}px,${e.clientY - 2}px)`; }, true);
});
"""


def main(url, plan_file, out_dir):
    plan = open(plan_file, encoding="utf-8").read()
    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                  record_video_dir=out_dir, record_video_size={"width": W, "height": H},
                                  timezone_id="Asia/Kolkata", locale="en-IN")
        ctx.add_init_script(CURSOR)
        page = ctx.new_page()
        t0 = time.monotonic()
        mark = lambda: round(time.monotonic() - t0, 2)

        def click(locator, pause=0.4):
            box = locator.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=18)
            time.sleep(0.15)
            locator.click()
            time.sleep(pause)

        page.goto(url)
        page.locator("#plan-text").wait_for()
        page.mouse.move(W * 0.7, H * 0.8)
        page.wait_for_load_state("networkidle")
        time.sleep(0.6)
        start = mark()

        click(page.locator("#plan-text"))
        page.locator("#plan-text").fill(plan)       # a paste
        time.sleep(1.2)
        click(page.get_by_role("button", name="Generate plan"))
        page.locator(".plan-preview").wait_for()
        time.sleep(2.0)                             # the dated tasks
        add = page.get_by_role("button", name="tasks to plan")
        page.mouse.wheel(0, 900)
        time.sleep(0.9)
        click(add, pause=1.0)
        page.get_by_text("Added").first.wait_for()
        page.mouse.wheel(0, -900)
        time.sleep(0.5)
        click(page.locator('nav .nav[data-route="calendar"]'))
        time.sleep(3.0)                             # the week with the new tasks
        end = mark()

        video = page.video
        ctx.close()
        shutil.move(video.path(), os.path.join(out_dir, "raw.webm"))
        browser.close()
    with open(os.path.join(out_dir, "raw.times"), "w") as f:
        f.write(f"START={start}\nEND={end}\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
