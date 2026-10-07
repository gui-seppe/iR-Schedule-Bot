"""Convert the season PDF into data/schedule.json.

Usage: python scripts/parse_schedule.py path/to/schedule.pdf [-o data/schedule.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.pdf_parser import parse_pdf, to_json_dict  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="data/schedule.json")
    args = ap.parse_args()

    series = parse_pdf(args.pdf)
    Path(args.out).write_text(json.dumps(to_json_dict(series), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Parsed {len(series)} series -> {args.out}")
    no_rule = [s for s in series if not s.recurrence]
    if no_rule:
        print(f"\n{len(no_rule)} series need a manual 'overrides' entry in config.json:")
        for s in no_rule:
            print(f"  - {s.name}   [{s.rule}]")
    odd = [(s.name, w.week) for s in series for w in s.weeks if not w.track or not w.length]
    if odd:
        print(f"\n{len(odd)} weeks with missing track/length (check the PDF):")
        for name, wk in odd:
            print(f"  - {name} week {wk}")


if __name__ == "__main__":
    main()
