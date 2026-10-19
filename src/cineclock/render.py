"""The one Jinja setup, shared by the web app and the static site build."""

import hashlib
import os
import re
import struct
from functools import cache
from importlib import metadata
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from cineclock.tags import filter_slugs, kind, said_by_tags, slug
from cineclock.timefmt import clock, stamp
from cineclock.venues import room_label

RELAY_URL = "https://cineclock-relay.cineclock-relay.workers.dev"

STATIC = Path(__file__).parent / "static"

env = Environment(loader=PackageLoader("cineclock"), autoescape=select_autoescape())
env.filters["clock"] = clock
env.filters["stamp"] = stamp
env.filters["tagslug"] = slug
env.filters["filter_slugs"] = filter_slugs
env.filters["tagkind"] = kind
env.filters["said_by_tags"] = said_by_tags
env.filters["runtime"] = lambda minutes: (
    f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"
)
env.filters["room_label"] = lambda s: room_label(s.venue, s.room)
# TMDB serves the same poster at several widths; the popup on a film page uses a bigger one.
env.filters["large_poster"] = lambda url: (url or "").replace("/t/p/w500/", "/t/p/w780/")


def asset_version(name: str) -> str:
    """A short fingerprint of a static file, so browsers fetch it again when it changes.

    Phones keep stylesheets cached; without this a new page can arrive with
    the old styles and look broken.
    """
    data = (STATIC / name).read_bytes()
    return hashlib.sha256(data).hexdigest()[:10]


env.globals["asset_version"] = asset_version

try:
    env.globals["version"] = metadata.version("cineclock")
except metadata.PackageNotFoundError:
    env.globals["version"] = "dev"

# The Letterboxd relay (relay/worker.js on Cloudflare). Empty means only synced
# profiles can connect.
env.globals["relay_url"] = os.environ.get("CINECLOCK_RELAY", RELAY_URL)

# Link previews need full URLs, not the relative ones the pages use.
env.globals["site_url"] = os.environ.get("CINECLOCK_URL", "https://cineclock.ca/")


def has_asset(name: str) -> bool:
    return (STATIC / name).exists()


env.globals["has_asset"] = has_asset


@cache
def image_size(name: str) -> tuple[float, float] | None:
    """Pixel size of a PNG (from its header) or an SVG (from its viewBox)."""
    path = STATIC / name
    if not path.exists():
        return None
    if path.suffix == ".svg":
        box = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', path.read_text())
        return (float(box[1]), float(box[2])) if box else None
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    return float(width), float(height)


def logo_size(name: str, area: float, min_height: float) -> tuple[int, int]:
    """Width and height that give every logo the same area on screen.

    Theatre logos range from nearly square to seven times wider than tall.
    Fixing the height makes the wide ones huge; fixing the width makes the
    square ones huge. Matching the area keeps them looking about the same size.
    """
    width, height = image_size(name) or (3.0, 1.0)
    ratio = width / height
    h = max((area / ratio) ** 0.5, min_height)
    return round(h * ratio), round(h)


env.globals["logo_size"] = logo_size
