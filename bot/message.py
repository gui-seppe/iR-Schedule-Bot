"""Embed text with live Discord timestamps (the countdowns update client-side)."""
from __future__ import annotations

from .schedule import Row, Side


def _when(side: Side | None) -> str:
    if side is None:
        return "—"
    if side.next is None:
        return "no time set" if side.series.recurrence is None else "season over"
    ts = int(side.next.timestamp())
    return f"<t:{ts}:t> · <t:{ts}:R>"


def describe(rows: list[Row]) -> str:
    lines = []
    for row in rows:
        lines.append(f"**{row.label}**")
        parts = []
        if row.open:
            parts.append(f"Open {_when(row.open)}")
        if row.fixed:
            parts.append(f"Fixed {_when(row.fixed)}")
        lines.append(" " + "  |  ".join(parts))
    return "\n".join(lines)[:4096]
