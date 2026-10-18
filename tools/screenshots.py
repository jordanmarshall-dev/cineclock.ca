"""Take the README screenshots from a built site: the home page, the Films grid
and one film page, as they look on a phone.

    python -m cineclock.build
    python tools/screenshots.py

Serves the built site folder on a local port, opens it in Chromium at phone
size and writes docs/home.png, docs/films.png and docs/film.png. The film page
is the best-known film playing that has a backdrop and every score, so the
picture shows the page at its fullest. The Screenshots workflow runs this with
the live database; it needs Playwright (pip install playwright, then
python -m playwright install chromium).
"""

import os
import threading
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from cineclock import db
from cineclock.site import film_pages

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / os.environ.get("CINECLOCK_SITE", "site")
DOCS = ROOT / "docs"
PHONE = {"width": 390, "height": 844}


def showcase_film() -> str:
    """The slug of the film page to photograph."""
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    pages = film_pages(db.upcoming(conn, datetime.now(UTC)), db.films_by_key(conn)).values()
    conn.close()

    def complete(p):
        f = p.film
        return bool(
            f
            and f.backdrop_url
            and f.poster_url
            and f.letterboxd_rating
            and f.imdb_rating
            and f.rt_score is not None
        )

    full = [p for p in pages if complete(p)] or [p for p in pages if p.film and p.film.backdrop_url]
    best = max(full, key=lambda p: p.film.letterboxd_count or 0)
    return best.slug


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve() -> tuple[ThreadingHTTPServer, str]:
    handler = partial(QuietHandler, directory=str(SITE))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"


def settle(page):
    """Wait for fonts and every image in view, so nothing is caught half loaded."""
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.evaluate(
        """() => Promise.all([...document.images]
            .filter((img) => img.getBoundingClientRect().top < innerHeight)
            .map((img) => img.complete ? null
              : new Promise((r) => { img.onload = img.onerror = r; })))"""
    )
    page.wait_for_timeout(300)


def main():
    DOCS.mkdir(exist_ok=True)
    slug = showcase_film()
    server, base = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=PHONE, device_scale_factor=2)

            page.goto(base)
            settle(page)
            page.screenshot(path=DOCS / "home.png")

            # The grid, starting just under the filters.
            page.goto(base + "films/")
            settle(page)
            page.evaluate(
                """() => {
                  const grid = document.querySelector(".film-grid");
                  const header = document.querySelector(".site-header").offsetHeight;
                  scrollTo(0, grid.getBoundingClientRect().top + scrollY - header - 16);
                }"""
            )
            settle(page)
            page.screenshot(path=DOCS / "films.png")

            page.goto(base + f"films/{slug}/")
            settle(page)
            page.screenshot(path=DOCS / "film.png")
            browser.close()
    finally:
        server.shutdown()
    print(f"Wrote docs/home.png, docs/films.png and docs/film.png ({slug})")


if __name__ == "__main__":
    main()
