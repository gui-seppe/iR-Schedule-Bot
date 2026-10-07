"""Render the board locally without Discord.

Run: python -m bot.preview [--config config.json] [--now 2026-10-07T21:30]
Writes preview.png and prints the embed text.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .message import describe
from .render import render_board
from .schedule import build_sections, load_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--now", help="ISO time in UTC, default: now")
    ap.add_argument("-o", "--out", default="preview.png")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

    now = (datetime.fromisoformat(args.now).replace(tzinfo=timezone.utc) if args.now
           else datetime.now(timezone.utc))
    config = load_json(args.config)
    data = load_json(config.get("schedule_file", "data/schedule.json"))
    sections = build_sections(config, data, now)
    rows = [r for sec in sections for r in sec.rows]

    Path(args.out).write_bytes(render_board(rows, config.get("title", "Tracked series")))
    print(describe(sections))
    for row in rows:
        for kind, side in (("open", row.open), ("fixed", row.fixed)):
            if side:
                print(f"  {row.label} {kind}: {side.next:%a %d %b %H:%M} UTC" if side.next
                      else f"  {row.label} {kind}: -")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
