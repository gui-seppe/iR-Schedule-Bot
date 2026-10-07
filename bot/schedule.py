"""Build the board: for each tracked row, current week info + next Open/Fixed start."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .recurrence import Recurrence

WEEK = timedelta(days=7)


def _utc_day(s: str) -> datetime:
    return datetime.combine(date.fromisoformat(s), datetime.min.time(), tzinfo=timezone.utc)


class SeriesSchedule:
    def __init__(self, raw: dict, override: dict | None = None):
        self.name: str = raw["name"]
        rec = override or raw.get("recurrence")
        self.recurrence = Recurrence.from_dict(rec) if rec else None
        self.weeks = sorted(raw["weeks"], key=lambda w: w["start"])

    def windows(self):
        """Yield (week, start, end) for every race week, in order."""
        starts = [_utc_day(w["start"]) for w in self.weeks]
        for i, (w, start) in enumerate(zip(self.weeks, starts)):
            if i + 1 < len(starts):
                end = starts[i + 1]
            elif i > 0:
                end = start + max(starts[i] - starts[i - 1], WEEK)
            else:
                end = start + WEEK
            yield w, start, end

    def current_week(self, now: datetime) -> dict | None:
        """Week running now, or the next upcoming one if the season hasn't started yet."""
        for w, start, end in self.windows():
            if end > now:
                return w
        return None

    def week_at(self, t: datetime) -> dict | None:
        return next((w for w, start, end in self.windows() if start <= t < end), None)

    def next_session(self, now: datetime) -> datetime | None:
        if not self.recurrence:
            return None
        for _, start, end in self.windows():
            if end <= now:
                continue
            if self.recurrence.first_week_only:
                end = min(end, start + WEEK)
            for t in self.recurrence.occurrences(max(start, now), end):
                if t > now:
                    return t
        return None

    def next_boundary(self, now: datetime) -> datetime | None:
        """Next week rollover (track/weather change)."""
        for _, start, end in self.windows():
            if start > now:
                return start
            if end > now:
                return end
        return None


@dataclass
class Side:
    series: SeriesSchedule
    week: dict | None
    next: datetime | None


@dataclass
class Row:
    label: str
    open: Side | None
    fixed: Side | None

    @property
    def sides(self) -> list[Side]:
        return [s for s in (self.open, self.fixed) if s]

    @property
    def week(self) -> dict | None:
        return next((s.week for s in self.sides if s.week), None)


class ConfigError(Exception):
    pass


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_series(data: dict, query: str) -> dict:
    """Exact name match (case-insensitive), otherwise a unique substring match."""
    q = query.casefold()
    all_series = data["series"]
    exact = [s for s in all_series if s["name"].casefold() == q]
    if exact:
        return exact[0]
    partial = [s for s in all_series if q in s["name"].casefold()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise ConfigError(f"No series matches {query!r}")
    names = "\n  ".join(s["name"] for s in partial)
    raise ConfigError(f"{query!r} is ambiguous, use the full name. Candidates:\n  {names}")


def build_board(config: dict, data: dict, now: datetime) -> list[Row]:
    overrides = {k.casefold(): v for k, v in config.get("overrides", {}).items()}
    # Special events aren't in the season PDF: they're declared in config in the same shape.
    data = {"series": data["series"] + config.get("special_events", [])}
    rows = []
    for r in config["rows"]:
        sides = {}
        for kind in ("open", "fixed"):
            if not r.get(kind):
                sides[kind] = None
                continue
            raw = find_series(data, r[kind])
            sched = SeriesSchedule(raw, overrides.get(raw["name"].casefold()))
            nxt = sched.next_session(now)
            # Show the week of the next race (matters for weekend-only events whose race already ran).
            week = (sched.week_at(nxt) if nxt else None) or sched.current_week(now)
            sides[kind] = Side(sched, week, nxt)
        rows.append(Row(r.get("label") or (r.get("open") or r.get("fixed")), sides["open"], sides["fixed"]))
    return rows


@dataclass
class Section:
    title: str
    color: str | int | None
    rows: list[Row]


def build_sections(config: dict, data: dict, now: datetime) -> list[Section]:
    """Config either has "sections" (each with title/color/rows) or a flat "rows" list."""
    secs = config.get("sections") or [{"title": config.get("title", "Tracked series"), "rows": config["rows"]}]
    return [Section(s.get("title", ""), s.get("color"), build_board({**config, "rows": s["rows"]}, data, now))
            for s in secs]


def next_change(rows: list[Row], now: datetime) -> datetime | None:
    """When the board should be refreshed next: the earliest race start or week rollover."""
    times = []
    for row in rows:
        for side in row.sides:
            if side.next:
                times.append(side.next)
            if b := side.series.next_boundary(now):
                times.append(b)
    return min(times, default=None)


def weather_text(week: dict | None) -> str:
    if not week:
        return "—"
    if week.get("weather"):
        return week["weather"]
    if week.get("temp_c") is None:
        return "Constant"
    rain = week.get("rain") or "None"
    return f"{week['temp_c']}°C, " + ("dry" if rain == "None" else f"rain {rain}")
