"""Build the site as plain files for free static hosting: python -m cineclock.build

Writes every page (home, films, venues), the stylesheet and fonts, and a
stats.json summary for checking a deploy. GitHub Pages serves the folder.
"""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from cineclock import db
from cineclock.site import pages, stats

STATIC = Path(__file__).parent / "static"


def build(conn: Connection, out_dir: Path, now: datetime) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(STATIC, out_dir / "static")
    built = pages(conn, now)
    for path, html in built.items():
        target = out_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html)
    (out_dir / "stats.json").write_text(json.dumps(stats(conn, now), indent=2))
    return len(built)


def main():
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    out_dir = Path(os.environ.get("CINECLOCK_SITE", "site"))
    count = build(conn, out_dir, datetime.now(UTC))
    conn.close()
    print(f"Built {count} pages in {out_dir}")


if __name__ == "__main__":
    main()
