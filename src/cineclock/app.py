import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cineclock import db
from cineclock.render import env
from cineclock.views import group_by_day

app = FastAPI(title="cineclock")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(env=env)


def get_conn() -> Iterator[Connection]:
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    try:
        yield conn
    finally:
        conn.close()


def get_now() -> datetime:
    return datetime.now(UTC)


@app.get("/", response_class=HTMLResponse)
def whats_on(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    now: Annotated[datetime, Depends(get_now)],
):
    days = group_by_day(db.upcoming(conn, now), now)
    context = {"days": days, "static": "/static/", "updated": None}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/health")
def health():
    return {"status": "ok"}
