"""Build the Discord message: one embed per section (e.g. Sprint / Endurance), each a grid of inline fields.

Discord renders <t:...> timestamps in each viewer's own timezone and keeps the relative ones ticking,
so the message only needs editing when the next race changes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .schedule import Row, Section, Side

MAX_ROWS = 8  # per section: 3 fields per row, Discord allows 25 fields per embed
DEFAULT_COLOR = 0xE03C31
EMPTY = {"name": "\u200b", "value": "\u200b", "inline": True}
SIDE_TITLES = {"open": "🟢 Open", "fixed": "🔵 Fixed"}


def _weather(week: dict | None) -> str:
    if not week:
        return ""
    if week.get("weather"):
        return week["weather"]
    if week.get("temp_c") is None:
        return "constant weather"
    rain = week.get("rain") or "None"
    return f"☀️ {week['temp_c']}°C" if rain == "None" else f"🌧️ {week['temp_c']}°C · {rain}"


def _when(side: Side) -> str:
    if side.next is None:
        return "no time set" if side.series.recurrence is None else "season over"
    ts = int(side.next.timestamp())
    return f"**<t:{ts}:R>**\n-# <t:{ts}:t> · {_weather(side.week)}"


def _series_cell(row: Row) -> str:
    week = row.week
    if not week:
        return "Season over"
    meta = f"Week {week['week']}"
    if week.get("length"):
        meta += f" · {week['length']}"
    return f"🏁 {week['track']}\n-# {meta}"


def section_fields(rows: list[Row]) -> list[dict]:
    """Three inline fields per row (series | open | fixed), so rows line up as a grid."""
    fields = []
    shown = rows[:MAX_ROWS]
    for i, row in enumerate(shown):
        gap = "\n\u200b" if i < len(shown) - 1 else ""  # one blank line between series
        fields.append({"name": row.label[:256], "value": _series_cell(row)[:1000] + gap, "inline": True})
        for kind in ("open", "fixed"):
            side = getattr(row, kind)
            if side:
                fields.append({"name": SIDE_TITLES[kind], "value": _when(side), "inline": True})
            else:
                fields.append(EMPTY)
    return fields


def _color(value) -> int:
    if isinstance(value, str):
        return int(value.lstrip("#"), 16)
    return DEFAULT_COLOR if value is None else int(value)


def board_embeds(sections: list[Section], image_name: str | None = None) -> list[dict]:
    """One embed dict per section (discord.Embed.from_dict turns each into an Embed)."""
    embeds = []
    for sec in sections:
        embed = {"title": sec.title, "color": _color(sec.color), "fields": section_fields(sec.rows)}
        if len(sec.rows) > MAX_ROWS:
            embed["description"] = f"-# Showing the first {MAX_ROWS} of {len(sec.rows)} series"
        embeds.append(embed)
    if embeds:
        embeds[-1]["footer"] = {"text": "Times are in your local timezone · last change"}
        embeds[-1]["timestamp"] = datetime.now(timezone.utc).isoformat()
        if image_name:
            embeds[-1]["image"] = {"url": f"attachment://{image_name}"}
    return embeds


def heading(config: dict) -> str:
    return f"## {config.get('title', 'Tracked series')}"


def content_key(content: str | None, embeds: list[dict]) -> str:
    """What viewers see, minus the timestamp: used to skip edits that wouldn't change anything."""
    return json.dumps([content or "", [[e.get("title"), e.get("color"), e.get("description"), e.get("fields")]
                                       for e in embeds]], sort_keys=True)


def static_signature(rows: list[Row]) -> str:
    """Short hash of what the image shows (week/track/weather). Changes when the image needs re-uploading."""
    blob = json.dumps([[r.label, r.week, [s.week for s in r.sides]] for r in rows], default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def describe(sections: list[Section]) -> str:
    """Plain-text version of the board, for the local preview."""
    lines = []
    for sec in sections:
        lines.append(f"== {sec.title} ==")
        for f in section_fields(sec.rows):
            if f is not EMPTY:
                lines.append(f"[{f['name']}] " + f["value"].replace("\n", " / "))
    return "\n".join(lines)
