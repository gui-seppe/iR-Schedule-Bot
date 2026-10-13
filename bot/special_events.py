"""Special events from iracing.com (they're not in the season PDF).

- The calendar page (https://www.iracing.com/specialevents/) has every event's name, dates and car classes.
- On the Monday of race week iRacing publishes a "THIS WEEK: iRacing <event> | Special Event" post with the
  track and every timeslot ("Timeslot #1: Friday at 22:00 GMT ..."). We find it via the site's WordPress API.

Only the standard library is used, so this runs anywhere without extra installs.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

CALENDAR_URL = "https://www.iracing.com/specialevents/"
POSTS_URL = ("https://www.iracing.com/wp-json/wp/v2/posts?search=special%20event&per_page=30"
             "&_fields=date_gmt,slug,link,title,content")
USER_AGENT = "Mozilla/5.0 (iR-Schedule-Bot; +https://github.com/gui-seppe/iR-Schedule-Bot)"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}

_RANGE_RE = re.compile(
    r"([A-Za-z]+)\.?\s+(\d{1,2})\s*[-–—]\s*(?:([A-Za-z]+)\.?\s+)?(\d{1,2}),?\s*(\d{4})")
_SINGLE_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s*(\d{4})")
_SLOT_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?(\d{1,2}):(\d{2})\s*GMT", re.I)


# ---------- parsing (pure functions, tested offline) ----------

def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")).strip()


def _lines(fragment: str) -> list[str]:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"</(p|h\d|li|div|tr)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", l).strip() for l in t.splitlines() if l.strip()]


def parse_dates(text: str | None) -> tuple[date, date] | None:
    """'October 16-18, 2026', 'Oct 30-31, 2026', 'June 30 – July 6, 2026', 'May 29 – 31, 2026'."""
    if not text:
        return None
    text = text.replace("_", "")
    if m := _RANGE_RE.search(text):
        m1, d1, m2, d2, year = m.groups()
        mon1 = MONTHS.get(m1[:3].lower())
        mon2 = MONTHS.get((m2 or m1)[:3].lower())
        if mon1 and mon2:
            y = int(year)
            start = date(y if mon1 <= mon2 else y - 1, mon1, int(d1))
            return start, date(y, mon2, int(d2))
    if m := _SINGLE_RE.search(text):
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            d = date(int(m.group(3)), mon, int(m.group(2)))
            return d, d
    return None


def parse_calendar(page_html: str) -> list[dict]:
    events = []
    for sec in page_html.split("<section")[1:]:
        name = re.search(r"<h2[^>]*>(.*?)</h2>", sec, re.S)
        if not name:
            continue
        when = re.search(r"<strong><em>(.*?)</em></strong>|<em><strong>(.*?)</strong></em>", sec, re.S)
        dates = parse_dates(_text(when.group(1) or when.group(2))) if when else None
        if not dates:
            continue  # TBD / no date: nothing to schedule
        tag = re.search(r'letter-spacing:3px"[^>]*>(.*?)</p>', sec, re.S)
        track = re.search(r'href="https://www\.iracing\.com/tracks/[^"]*"[^>]*>(.*?)</a>', sec, re.S)
        classes = [_text(c) for c in re.findall(r"<summary>(.*?)</summary>", sec, re.S)]
        events.append({
            "name": _text(name.group(1)),
            "start": dates[0].isoformat(),
            "end": dates[1].isoformat(),
            "tag": _text(tag.group(1)).title() if tag else None,
            "track": _text(track.group(1)) if track else None,
            "classes": [re.sub(r"\s+", " ", c) for c in classes if c],
        })
    return events


def parse_post(post: dict) -> dict:
    """Pull title, track and weekday/time slots out of a 'THIS WEEK: ... | Special Event' post."""
    lines = _lines(post["content"]["rendered"])
    title = _text(post["title"]["rendered"])
    title = re.sub(r"^THIS WEEK:\s*", "", title, flags=re.I)
    title = re.sub(r"\s*\|\s*Special Event\s*$", "", title, flags=re.I)

    track = next((l.split(":", 1)[1].strip() for l in lines if l.upper().startswith("TRACK:")), None)
    slot_lines = [l for l in lines if l.lower().startswith("timeslot")]
    if not slot_lines:  # fall back to the "TIMES TO RACE" block
        idx = next((i for i, l in enumerate(lines) if "TIMES TO RACE" in l.upper()), None)
        slot_lines = lines[idx + 1: idx + 12] if idx is not None else []
    slots = []
    for l in slot_lines:
        if m := _SLOT_RE.search(l):
            slots.append((WEEKDAYS[m.group(1).lower()], int(m.group(2)) * 60 + int(m.group(3))))
    return {
        "title": title,
        "track": track.title() if track and track.isupper() else track,
        "slots": slots,
        "published": post["date_gmt"][:10],
        "url": post.get("link"),
    }


def resolve_slots(slots: list[tuple[int, int]], start: date, end: date) -> list[str]:
    """Turn (weekday, minute) slots into UTC datetimes within the event's date range (one day of slack
    either side, e.g. a 'Sunday 00:00 GMT' slot for a Fri-Sat event)."""
    days = [start + timedelta(days=i) for i in range(-1, (end - start).days + 2)]
    out = []
    for wd, minute in slots:
        d = next((d for d in days if d.weekday() == wd), None)
        if d:
            dt = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=minute)
            out.append(dt.isoformat())
    return sorted(set(out))


def _tokens(s: str) -> set[str]:
    stop = {"iracing", "presented", "by", "the", "of", "powered", "special", "event", "hours", "hour", "hr", "hrs"}
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in stop}


def attach_posts(events: list[dict], posts: list[dict]) -> list[dict]:
    """Match each calendar event with its race-week post: published in the 8 days before the event starts,
    best name overlap wins."""
    for ev in events:
        start, end = date.fromisoformat(ev["start"]), date.fromisoformat(ev["end"])
        candidates = [p for p in posts
                      if start - timedelta(days=8) <= date.fromisoformat(p["published"]) <= start + timedelta(days=1)]
        if not candidates:
            continue
        best = max(candidates, key=lambda p: len(_tokens(p["title"]) & _tokens(ev["name"])))
        if len(candidates) > 1 and not _tokens(best["title"]) & _tokens(ev["name"]):
            continue  # several posts that week and none clearly about this event
        ev["title"] = best["title"]
        ev["url"] = best["url"]
        if best["track"]:
            ev["track"] = best["track"]
        ev["sessions"] = resolve_slots(best["slots"], start, end)
    return events


# ---------- fetching ----------

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch(today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    events = [e for e in parse_calendar(_get(CALENDAR_URL))
              if date.fromisoformat(e["end"]) >= today - timedelta(days=1)]
    posts = [parse_post(p) for p in json.loads(_get(POSTS_URL))
             if p["slug"].startswith("this-week-iracing") and "special" in p["slug"]]
    events = attach_posts(events, posts)
    events.sort(key=lambda e: e["start"])
    return {"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": events}


# ---------- selection for the board ----------

def upcoming(data: dict, now: datetime, weeks: int = 2) -> list[dict]:
    """Events of this week and next (Monday-based weeks), still running or yet to start."""
    monday = (now - timedelta(days=now.weekday())).date()
    horizon = monday + timedelta(weeks=weeks)
    out = []
    for ev in data.get("events", []):
        start, end = date.fromisoformat(ev["start"]), date.fromisoformat(ev["end"])
        if start >= horizon:
            continue
        sessions = [datetime.fromisoformat(s) for s in ev.get("sessions", [])]
        # Keep an event until its last session has had time to finish (24h races), else until its end date.
        finish = (max(sessions) + timedelta(hours=26)) if sessions else \
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        if finish > now:
            out.append(ev)
    return out
