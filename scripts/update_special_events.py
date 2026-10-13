"""Refresh data/special_events.json from iracing.com (calendar + race-week posts).

Usage: python scripts/update_special_events.py [-o data/special_events.json]
Exits 0 without touching the file if iracing.com can't be reached, so a temporary outage keeps the last data.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.special_events import fetch  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="data/special_events.json")
    args = ap.parse_args()
    try:
        data = fetch()
    except Exception as e:  # network/site problems: keep the previous file
        print(f"::warning::Could not refresh special events: {e}")
        return

    out = Path(args.out)
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    if old.get("events") == data["events"]:
        print("Special events unchanged")
        return
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for ev in data["events"]:
        slots = len(ev.get("sessions", []))
        print(f"{ev['start']}  {ev['name']}  ({slots} timeslots)" if slots else f"{ev['start']}  {ev['name']}")


if __name__ == "__main__":
    main()
