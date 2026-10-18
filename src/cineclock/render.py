"""The one Jinja setup, shared by the web app and the static site build."""

import hashlib
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from cineclock.tags import slug
from cineclock.timefmt import clock

STATIC = Path(__file__).parent / "static"

env = Environment(loader=PackageLoader("cineclock"), autoescape=select_autoescape())
env.filters["clock"] = clock
env.filters["tagslug"] = slug


def asset_version(name: str) -> str:
    """A short fingerprint of a static file, so browsers fetch it again when it changes.

    Phones keep stylesheets cached; without this a new page can arrive with
    the old styles and look broken.
    """
    data = (STATIC / name).read_bytes()
    return hashlib.sha256(data).hexdigest()[:10]


env.globals["asset_version"] = asset_version


def has_asset(name: str) -> bool:
    return (STATIC / name).exists()


env.globals["has_asset"] = has_asset
