"""Parse iRacing "Races every ..." rules and generate session start times (UTC)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DAY_NAMES = {v: k.capitalize() for k, v in DAYS.items()}

_DAY_RE = r"\b(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b"
_TIME_RE = r"\b\d{1,2}(?::\d{2})?\b"


@dataclass
class Recurrence:
    """Either a fixed interval anchored at 00:00 UTC, or a list of weekly slots."""

    kind: str  # "interval" | "weekly"
    period: int = 0  # minutes (interval)
    offsets: list[int] = field(default_factory=list)  # minutes from period start (interval)
    slots: list[tuple[int, int]] = field(default_factory=list)  # (weekday, minute of day) (weekly)
    first_week_only: bool = False  # "every other Saturday": race only in the first 7 days of a week

    def to_dict(self) -> dict:
        if self.kind == "interval":
            return {"kind": "interval", "period": self.period, "offsets": self.offsets}
        return {
            "kind": "weekly",
            "slots": [[DAY_NAMES[d], f"{m // 60:02d}:{m % 60:02d}"] for d, m in self.slots],
            "first_week_only": self.first_week_only,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Recurrence:
        if d["kind"] == "interval":
            return cls("interval", period=d["period"], offsets=list(d["offsets"]))
        slots = []
        for day, hhmm in d["slots"]:
            h, m = hhmm.split(":")
            slots.append((DAYS[day[:3].lower()], int(h) * 60 + int(m)))
        return cls("weekly", slots=slots, first_week_only=d.get("first_week_only", False))

    def occurrences(self, start: datetime, end: datetime):
        """Yield session start times in [start, end), sorted."""
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.kind == "interval":
            t = day
            while t < end:
                for off in self.offsets:
                    x = t + timedelta(minutes=off)
                    if start <= x < end:
                        yield x
                t += timedelta(minutes=self.period)
        else:
            slots = sorted(self.slots, key=lambda s: s[1])
            while day < end:
                for wd, minute in slots:
                    if day.weekday() == wd:
                        x = day + timedelta(minutes=minute)
                        if start <= x < end:
                            yield x
                day += timedelta(days=1)


def parse_rule(text: str) -> Recurrence | None:
    """Best-effort parse of the schedule line. Returns None when it can't be derived."""
    t = text.lower().split("|")[0]
    if "timeslot" in t:
        return None
    if "gmt" in t:
        return _parse_weekly(t)
    return _parse_interval(t)


def _parse_weekly(t: str) -> Recurrence | None:
    groups: list[tuple[list[int], list[int]]] = []
    days: list[int] = []
    times: list[int] = []
    for tok in re.findall(f"{_DAY_RE}|{_TIME_RE}", t):
        if tok[0].isalpha():
            if times:
                groups.append((days, times))
                days, times = [], []
            days.append(DAYS[tok[:3]])
        else:
            h, _, m = tok.partition(":")
            times.append(int(h) * 60 + int(m or 0))
    if days and times:
        groups.append((days, times))
    slots = sorted({(d, m) for ds, ms in groups for d in ds for m in ms})
    if not slots:
        return None
    return Recurrence("weekly", slots=slots, first_week_only="every other" in t)


def _parse_interval(t: str) -> Recurrence | None:
    if re.search(r"\b(30|thirty) min", t):
        period = 30
    elif re.search(r"\b2 hours", t):
        period = 120
    elif "hour" in t:
        period = 60
    else:
        period = None

    mins = {int(x) for x in re.findall(r":(\d{2})", t)}
    mins |= {int(x) for x in re.findall(r"\b(\d{1,2}) (?:past|after)", t)}
    mins |= {int(x) for x in re.findall(r"&\s*(\d{2})\b", t)}
    if any(k in t for k in ("on the hour", "top of the hour", "on the 00")):
        mins.add(0)
    if "half past" in t:
        mins.add(30)
    mins = sorted(m for m in mins if m < 60)

    if period == 30:
        if not mins:
            mins = [0, 30]
        elif len(mins) == 1:
            mins = sorted({mins[0], (mins[0] + 30) % 60})
        return Recurrence("interval", period=60, offsets=mins)
    if period == 120:
        base = mins[0] if mins else 0
        return Recurrence("interval", period=120, offsets=[base + (60 if "odd" in t else 0)])
    if period == 60 or (period is None and mins):
        return Recurrence("interval", period=60, offsets=mins or [0])
    return None
