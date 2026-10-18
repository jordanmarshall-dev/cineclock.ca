"""The one Jinja setup, shared by the web app and the static site build."""

from jinja2 import Environment, PackageLoader, select_autoescape

from cineclock.tags import slug
from cineclock.timefmt import clock

env = Environment(loader=PackageLoader("cineclock"), autoescape=select_autoescape())
env.filters["clock"] = clock
env.filters["tagslug"] = slug
