"""Build the Discord embed: a 3-column grid of inline fields with live timestamps.

Discord renders <t:...> timestamps in each viewer's own timezone and keeps the relative ones ticking,
so the message only needs editing when the next race changes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .schedule import Row, Side, weather_text

MAX_ROWS = 8  # 3 fields per row, Discord allows 25 fields per embed
COLOR = 0xE03C31


def _when(side: Side | None) -> str:
    if side is None:
        return "—"
    if side.next is None:
        return "no time set" if side.series.recurrence is None else "season over"
    ts = int(side.next.timestamp())
    return f"**<t:{ts}:R>**\n-# <t:{ts}:t> · {weather_text(side.week)}"


def _series_cell(row: Row) -> str:
    week = row.week
    if not week:
        return "Season over"
    meta = f"Week {week['week']}"
    if week.get("length"):
        meta += f" · {week['length']}"
    return f"{week['track']}\n-# {meta}"


def board_fields(rows: list[Row]) -> list[dict]:
    fields = []
    for row in rows[:MAX_ROWS]:
        fields += [
            {"name": row.label[:256], "value": _series_cell(row)[:1024], "inline": True},
            {"name": "Open", "value": _when(row.open), "inline": True},
            {"name": "Fixed", "value": _when(row.fixed), "inline": True},
        ]
    return fields


def board_embed(rows: list[Row], title: str, image_name: str | None = None) -> dict:
    """Embed as a plain dict (discord.Embed.from_dict turns it into an Embed)."""
    embed = {
        "title": title,
        "color": COLOR,
        "fields": board_fields(rows),
        "footer": {"text": "Times are in your local timezone · last change"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if len(rows) > MAX_ROWS:
        embed["description"] = f"-# Showing the first {MAX_ROWS} of {len(rows)} series"
    if image_name:
        embed["image"] = {"url": f"attachment://{image_name}"}
    return embed


def content_key(embed: dict) -> str:
    """What viewers see, minus the timestamp: used to skip edits that wouldn't change anything."""
    return json.dumps([embed.get("description"), embed.get("fields")], sort_keys=True)


def static_signature(rows: list[Row]) -> str:
    """Short hash of what the image shows (week/track/weather). Changes when the image needs re-uploading."""
    blob = json.dumps([[r.label, r.week, [s.week for s in r.sides]] for r in rows], default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def describe(rows: list[Row]) -> str:
    """Plain-text version of the board, for the local preview."""
    lines = []
    for f in board_fields(rows):
        lines.append(f"[{f['name']}] " + f["value"].replace("\n", " / "))
    return "\n".join(lines)
