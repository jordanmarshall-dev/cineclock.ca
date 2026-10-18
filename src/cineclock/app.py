"""Local preview server: fastapi dev src/cineclock/app.py

Serves exactly the pages the static build writes, straight from the database,
so what you see here is what goes live.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from cineclock import db
from cineclock.site import pages

app = FastAPI(title="cineclock")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def get_conn() -> Iterator[Connection]:
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    try:
        yield conn
    finally:
        conn.close()


def get_now() -> datetime:
    return datetime.now(UTC)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/{path:path}", response_class=HTMLResponse)
def page(
    path: str,
    conn: Annotated[Connection, Depends(get_conn)],
    now: Annotated[datetime, Depends(get_now)],
):
    if path and not path.endswith(("/", ".html")):
        # Same as GitHub Pages: /films/x goes to /films/x/
        return RedirectResponse(f"/{path}/")
    key = path + "index.html" if path == "" or path.endswith("/") else path
    built = pages(conn, now)
    if key not in built:
        raise HTTPException(status_code=404)
    return built[key]
