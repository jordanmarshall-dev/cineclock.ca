"""Build the site as plain files for free static hosting: python -m cineclock.build

The output folder holds index.html and the fonts. GitHub Pages serves it.
"""

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from cineclock import db
from cineclock.models import VANCOUVER
from cineclock.render import env
from cineclock.views import clock, group_by_day

STATIC = Path(__file__).parent / "static"


def updated_label(now: datetime) -> str:
    local = now.astimezone(VANCOUVER)
    return f"{local:%a %b} {local.day}, {clock(now)}"


def build(conn: Connection, out_dir: Path, now: datetime) -> None:
    days = group_by_day(db.upcoming(conn, now), now)
    html = env.get_template("index.html").render(
        days=days, static="static/", updated=updated_label(now)
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(STATIC, out_dir / "static")
    (out_dir / "index.html").write_text(html)


def main():
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    out_dir = Path(os.environ.get("CINECLOCK_SITE", "site"))
    build(conn, out_dir, datetime.now(UTC))
    conn.close()
    print(f"Built {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
