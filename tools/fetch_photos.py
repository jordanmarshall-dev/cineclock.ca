"""Download every credited theatre photo from Wikimedia Commons and grade it.

    python tools/fetch_photos.py

The list lives in venues.py (each Venue's and Room's `photo`), next to the
credit the page prints. Run by the Photos workflow, which commits the results.
Needs Pillow and httpx.
"""

import io
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from grade_photo import MAX_SIDE, grade
from PIL import Image

from cineclock.venues import VENUES

STATIC = Path(__file__).resolve().parent.parent / "src" / "cineclock" / "static"
HEADERS = {"User-Agent": "cineclock/2 (https://cineclock.ca; jordanmarshallmedia@gmail.com)"}


def targets():
    for venue in VENUES:
        if venue.photo:
            yield venue.photo, STATIC / "theatres" / f"{venue.slug}.jpg"
        for room in venue.rooms:
            if room.photo:
                yield room.photo, STATIC / "rooms" / f"{room.id}.jpg"


def main() -> int:
    failed = 0
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60) as client:
        for photo, dest in targets():
            if photo.source_url or photo.placeholder:
                continue  # committed by hand
            url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(photo.file)
            response = client.get(url, params={"width": 1600})
            if response.status_code != 200:
                print(f"{photo.file}: HTTP {response.status_code}")
                failed += 1
                continue
            out = grade(Image.open(io.BytesIO(response.content)))
            out.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            out.save(dest, quality=80, optimize=True, progressive=True)
            print(f"{photo.file} -> {dest.relative_to(STATIC)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
