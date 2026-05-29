"""Ad-hoc cross-engine layout probe for fork #343 (Safari cover misalignment).

Launches BOTH webkit (Safari engine) and chromium against cwn-local, logs in
as cwng84test, loads the books grid, and measures the box model of the cover
image, the title, and the hover overlay (<a>::after) for the first few books.

Prints the cover-bottom → title-top gap (the overlap symptom: negative = the
title overlaps the cover) and the overlay-vs-image alignment delta per engine.

Run: /Users/acoundou/.pyenv/versions/3.12.7/bin/python3 tests/manual/measure_cover_grid.py
NOT a pytest — a diagnostic harness kept under tests/manual/ for repro.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8086"
USER, PW = "cwng84test", "cwng-test-84"

MEASURE_JS = r"""
() => {
  const books = Array.from(document.querySelectorAll('.book')).slice(0, 4);
  return books.map((b, i) => {
    const cover = b.querySelector('.cover');
    const a = b.querySelector('.cover > a');
    const img = b.querySelector('.cover img');
    const meta = b.querySelector('.meta');
    const title = b.querySelector('.meta .title');
    const r = el => { if (!el) return null; const x = el.getBoundingClientRect();
      return {x: Math.round(x.x), y: Math.round(x.y), w: Math.round(x.width), h: Math.round(x.height),
              bottom: Math.round(x.bottom), top: Math.round(x.top)}; };
    const imgBox = r(img), titleBox = r(title), aBox = r(a), coverBox = r(cover), metaBox = r(meta);
    // The hover overlay (a::after) is position:absolute, width/height 100% of its
    // containing block. We can't getBoundingClientRect a pseudo directly, but we
    // can read the <a> box (its nearest positioned ancestor candidate) + the
    // computed style of the pseudo.
    const aAfter = a ? getComputedStyle(a, '::after') : null;
    return {
      index: i,
      img: imgBox,
      title: titleBox,
      a: aBox,
      cover: coverBox,
      meta: metaBox,
      // overlap symptom: gap between bottom of the cover image and top of the title.
      // negative => title overlaps the cover art.
      cover_to_title_gap: (imgBox && titleBox) ? (titleBox.top - imgBox.bottom) : null,
      // overlay sizing: <a> box vs img box — if they differ, the absolute
      // overlay (sized to the <a>/containing block) misaligns with the img.
      a_vs_img_w_delta: (aBox && imgBox) ? (aBox.w - imgBox.w) : null,
      a_vs_img_h_delta: (aBox && imgBox) ? (aBox.h - imgBox.h) : null,
      a_vs_img_x_delta: (aBox && imgBox) ? (aBox.x - imgBox.x) : null,
      a_vs_img_y_delta: (aBox && imgBox) ? (aBox.y - imgBox.y) : null,
      after_height: aAfter ? aAfter.height : null,
      after_width: aAfter ? aAfter.width : null,
    };
  });
}
"""


def run(engine_name, browser_type, viewport):
    browser = browser_type.launch(headless=True)
    ctx = browser.new_context(viewport=viewport)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    # login form — scope to the form so we don't hit the (hidden) search button
    pg.fill('#username', USER)
    pg.fill('#password', PW)
    pg.press('#password', 'Enter')
    pg.wait_for_load_state("networkidle")
    pg.goto(f"{BASE}/", wait_until="networkidle")
    pg.wait_for_timeout(800)
    data = pg.evaluate(MEASURE_JS)
    print(f"\n===== {engine_name} (viewport {viewport['width']}x{viewport['height']}) =====")
    for d in data:
        print(f" book[{d['index']}] img={d['img']}")
        print(f"           title={d['title']}")
        print(f"           a(overlay-box)={d['a']}")
        print(f"           cover_to_title_gap={d['cover_to_title_gap']}px "
              f"(NEGATIVE = title overlaps cover)")
        print(f"           a_vs_img deltas: w={d['a_vs_img_w_delta']} h={d['a_vs_img_h_delta']} "
              f"x={d['a_vs_img_x_delta']} y={d['a_vs_img_y_delta']} "
              f"(non-zero = hover overlay misaligned)")
    browser.close()
    return data


if __name__ == "__main__":
    with sync_playwright() as p:
        run("WEBKIT/Safari desktop", p.webkit, {"width": 1440, "height": 900})
        run("CHROMIUM desktop", p.chromium, {"width": 1440, "height": 900})
        run("WEBKIT/Safari mobile", p.webkit, {"width": 390, "height": 844})
