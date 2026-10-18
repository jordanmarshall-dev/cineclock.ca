from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from zoneinfo import ZoneInfo

# Load Vancouver's rules from the pinned tzdata package rather than the OS copy.
# B.C. dropped seasonal clock changes in 2026, and an outdated system database
# would quietly show every winter screening an hour early.
with files("tzdata.zoneinfo.America").joinpath("Vancouver").open("rb") as f:
    VANCOUVER = ZoneInfo.from_file(f, key="America/Vancouver")


@dataclass(frozen=True)
class Screening:
    """One showing of one film at one venue."""

    venue: str
    title: str
    starts_at: datetime
    url: str
    info_url: str | None = None
    year: int | None = None
    note: str | None = None
    poster_url: str | None = None

    def __post_init__(self):
        # Scrapers must hand us a real moment in time, not a bare clock reading.
        if self.starts_at.tzinfo is None:
            raise ValueError("starts_at must be timezone-aware")
        object.__setattr__(self, "starts_at", self.starts_at.astimezone(UTC))

    @property
    def local_start(self) -> datetime:
        return self.starts_at.astimezone(VANCOUVER)
