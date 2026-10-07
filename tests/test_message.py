from datetime import datetime, timezone

from bot.message import MAX_ROWS, board_embed, content_key
from bot.schedule import build_board
from tests.test_schedule import CONFIG, DATA


def test_grid_three_fields_per_row():
    rows = build_board(CONFIG, DATA, datetime(2026, 10, 7, 21, 30, tzinfo=timezone.utc))
    fields = board_embed(rows, "T")["fields"]
    assert len(fields) == 3 * len(rows) and all(f["inline"] for f in fields)
    name, open_, fixed = fields[:3]
    assert name["name"] == "SLM" and name["value"].startswith("Thompson")
    ts = int(datetime(2026, 10, 7, 22, 15, tzinfo=timezone.utc).timestamp())
    assert f"<t:{ts}:R>" in open_["value"] and "20°C, dry" in open_["value"]
    assert fields[5]["value"] == "—"  # IMSA row has no fixed series


def test_content_key_ignores_timestamp():
    rows = build_board(CONFIG, DATA, datetime(2026, 10, 7, 21, 30, tzinfo=timezone.utc))
    a, b = board_embed(rows, "T"), board_embed(rows, "T")
    b["timestamp"] = "2030-01-01T00:00:00+00:00"
    assert content_key(a) == content_key(b)


def test_row_cap():
    rows = build_board(CONFIG, DATA, datetime(2026, 10, 7, tzinfo=timezone.utc)) * 4
    embed = board_embed(rows, "T")
    assert len(embed["fields"]) == 3 * MAX_ROWS and "first 8" in embed["description"]
