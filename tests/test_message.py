from datetime import datetime, timezone

from bot.message import EMPTY, MAX_ROWS, board_embeds, content_key, section_fields
from bot.schedule import build_sections
from tests.test_schedule import CONFIG, DATA

NOW = datetime(2026, 10, 7, 21, 30, tzinfo=timezone.utc)

SECTIONED = {
    **CONFIG,
    "rows": None,
    "sections": [
        {"title": "Sprint", "color": "#E03C31", "rows": CONFIG["rows"][:1]},
        {"title": "Endurance", "color": "#F5A623", "rows": CONFIG["rows"][1:]},
    ],
}


def test_sections_become_colored_embeds():
    embeds = board_embeds(build_sections(SECTIONED, DATA, NOW))
    assert [e["title"] for e in embeds] == ["Sprint", "Endurance"]
    assert [e["color"] for e in embeds] == [0xE03C31, 0xF5A623]
    assert "footer" in embeds[-1] and "footer" not in embeds[0]


def test_flat_rows_config_still_works():
    (sec,) = build_sections(CONFIG, DATA, NOW)
    assert len(sec.rows) == 3


def test_row_fields_and_placeholders():
    sprint, endurance = build_sections(SECTIONED, DATA, NOW)
    name, open_, fixed = section_fields(sprint.rows)
    assert name["name"] == "SLM" and "Thompson" in name["value"]
    ts = int(datetime(2026, 10, 7, 22, 15, tzinfo=timezone.utc).timestamp())
    assert f"<t:{ts}:R>" in open_["value"] and "☀️ 20°C" in open_["value"]
    assert fixed["name"] == "🔵 Fixed"
    fields = section_fields(endurance.rows)
    # IMSA row has no fixed series: placeholder keeps the 3-column grid
    assert [f["name"] for f in fields] == ["IMSA MPC", "🟢 Open", "\u200b", "SLM Tour", "\u200b", "🔵 Fixed"]
    assert fields[2] is EMPTY and fields[4] is EMPTY
    assert fields[0]["value"].endswith("\n\u200b") and not fields[3]["value"].endswith("\u200b")


def test_content_key_ignores_timestamp():
    secs = build_sections(SECTIONED, DATA, NOW)
    a, b = board_embeds(secs), board_embeds(secs)
    b[-1]["timestamp"] = "2030-01-01T00:00:00+00:00"
    assert content_key("x", a) == content_key("x", b)
    assert content_key("x", a) != content_key("y", a)


def test_row_cap():
    (sec,) = build_sections(CONFIG, DATA, NOW)
    sec.rows = sec.rows * 4
    (embed,) = board_embeds([sec])
    assert len(embed["fields"]) <= 25 and f"first {MAX_ROWS}" in embed["description"]
