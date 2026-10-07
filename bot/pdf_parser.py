"""Turn the iRacing season schedule PDF into structured data."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .recurrence import parse_rule

LICENSE_RE = re.compile(r"^(?:Rookie|Class [A-D]) \(\d\.\d\) --> Pro/WC")
WEEK_RE = re.compile(r"^Week (\d+) \((\d{4}-\d{2}-\d{2})\)\s*(.*)$")
INGAME_DATE_RE = re.compile(r"^\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?: \d+x)?\)$")
TEMP_RE = re.compile(r"(\d+)°F/(\d+)°C")
RAIN_RE = re.compile(r"Rain chance (None|\d+%)")
LENGTH_RE = re.compile(r"\b(\d+)\s*(laps|mins)\b")
HEAT_FEATURE_RE = re.compile(r"\bF:(\d+)L\b")


@dataclass
class Week:
    week: int
    start: str  # YYYY-MM-DD, UTC
    track: str
    cars: str | None = None  # only for series whose cars change weekly
    temp_c: int | None = None
    temp_f: int | None = None
    rain: str | None = None  # "None", "26%"; None when weather is constant/unknown
    length: str | None = None


@dataclass
class Series:
    name: str
    cars: str
    license: str
    rule: str
    recurrence: dict | None
    weeks: list[Week] = field(default_factory=list)


def extract_text(pdf_path: str | Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_pdf(pdf_path: str | Path) -> list[Series]:
    return parse_text(extract_text(pdf_path))


def parse_text(text: str) -> list[Series]:
    lines = [_clean(l) for l in text.splitlines()]
    lines = [l for l in lines if l]
    license_idxs = [i for i, l in enumerate(lines) if LICENSE_RE.match(l)]

    # Series name = closest line above the license line mentioning "Season";
    # everything between them is the car list (may wrap over several lines).
    heads = []
    for li in license_idxs:
        ni = next(j for j in range(li - 1, -1, -1) if "season" in lines[j].lower())
        heads.append((ni, li))

    series = []
    for k, (ni, li) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        cars = " ".join(lines[ni + 1 : li])
        rule = lines[li + 1]
        rec = parse_rule(rule)
        s = Series(
            name=lines[ni],
            cars=cars,
            license=lines[li],
            rule=rule,
            recurrence=rec.to_dict() if rec else None,
        )
        s.weeks = _parse_weeks(lines[li + 2 : end], weekly_cars="see race week" in cars.lower())
        series.append(s)
    return series


def _parse_weeks(lines: list[str], weekly_cars: bool) -> list[Week]:
    weeks: list[Week] = []
    cur = None  # (num, start, head_lines, body_lines, seen_date)
    for line in lines:
        m = WEEK_RE.match(line)
        if m:
            if cur:
                weeks.append(_build_week(*cur[:4], weekly_cars))
            cur = [int(m.group(1)), m.group(2), [m.group(3)] if m.group(3) else [], [], False]
            continue
        if cur is None:
            continue
        if not cur[4] and INGAME_DATE_RE.match(line):
            cur[4] = True
        elif cur[4]:
            cur[3].append(line)
        else:
            cur[2].append(line)
    if cur:
        weeks.append(_build_week(*cur[:4], weekly_cars))
    return weeks


def _build_week(num, start, head, body, weekly_cars) -> Week:
    if weekly_cars:
        track, cars = (head[0] if head else ""), " ".join(head[1:]) or None
    else:
        track, cars = " ".join(head), None
    text = " ".join(body)
    w = Week(week=num, start=start, track=_clean(track), cars=cars)
    if t := TEMP_RE.search(text):
        w.temp_f, w.temp_c = int(t.group(1)), int(t.group(2))
    if r := RAIN_RE.search(text):
        w.rain = r.group(1)
    if f := HEAT_FEATURE_RE.search(text):
        w.length = f"{f.group(1)} laps"
    elif n := LENGTH_RE.search(text):
        w.length = f"{n.group(1)} {n.group(2)}"
    return w


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def to_json_dict(series: list[Series]) -> dict:
    return {"series": [asdict(s) for s in series]}
