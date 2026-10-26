"""Draw the picture that shows up when someone shares a cineclock link
(Discord, iMessage, Slack and so on): the theatre photos side by side, faded,
with the wordmark, the tagline and every theatre's logo on top.

    python tools/share_image.py

Writes src/cineclock/static/brand/share.png at 1200x630, the size link
previews expect. Needs Playwright and Chromium. Not part of the site build;
rerun it when a theatre is added.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from cineclock.venues import VENUES

STATIC = Path(__file__).resolve().parent.parent / "src" / "cineclock" / "static"
OUT = STATIC / "brand" / "share.png"


def page() -> str:
    photos = "".join(
        f'<div style="background-image: url(theatres/{v.slug}.jpg); '
        f'background-position: {v.photo_focus}"></div>'
        for v in VENUES
        if (STATIC / "theatres" / f"{v.slug}.jpg").exists()
    )
    logos = "".join(
        f'<img src="logos/{v.mark}" alt="">'
        for v in VENUES
        if v.mark and (STATIC / "logos" / v.mark).exists()
    )
    return f"""<!doctype html>
<style>
  @font-face {{ font-family: "Instrument Sans"; src: url(fonts/instrument-sans.woff2);
                font-weight: 400 700; }}
  body {{ margin: 0; width: 1200px; height: 630px; background: #14181c; overflow: hidden;
         font-family: "Instrument Sans"; position: relative; }}
  .photos {{ position: absolute; inset: 0; display: flex; opacity: 0.55; }}
  .photos div {{ flex: 1; background-size: cover; }}
  .shade {{ position: absolute; inset: 0;
           background: radial-gradient(ellipse at 50% 55%,
                                       rgba(20,24,28,0.92) 30%, rgba(20,24,28,0.55) 80%); }}
  .body {{ position: absolute; inset: 0; display: flex; flex-direction: column;
          align-items: center; justify-content: center; gap: 28px; }}
  .wordmark {{ height: 120px; }}
  .tagline {{ margin: 0; color: #dde5ed; font-size: 40px; font-weight: 600; }}
  .logos {{ display: flex; align-items: center; gap: 44px; margin-top: 24px; }}
  .logos img {{ height: 34px; }}
  .bar {{ position: absolute; left: 0; right: 0; bottom: 0; height: 10px; background: #8830df; }}
</style>
<div class="photos">{photos}</div>
<div class="shade"></div>
<div class="body">
  <img class="wordmark" src="brand/cineclock-wordmark.png" alt="">
  <p class="tagline">Support local cinemas.</p>
  <div class="logos">{logos}</div>
</div>
<div class="bar"></div>
"""


def main():
    html = STATIC / "_share.html"
    html.write_text(page())
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            tab = browser.new_page(viewport={"width": 1200, "height": 630})
            tab.goto(html.as_uri(), wait_until="networkidle")
            tab.screenshot(path=OUT)
            browser.close()
    finally:
        html.unlink()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
