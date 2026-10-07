from datetime import datetime, timezone

import pytest

from bot.schedule import ConfigError, build_board, find_series, next_change

UTC = timezone.utc


def week(n, start, track, temp=20):
    return {"week": n, "start": start, "track": track, "temp_c": temp, "rain": "None"}


DATA = {
    "series": [
        {
            "name": "Super Late Model Series - 2026 Season 4",
            "recurrence": {"kind": "interval", "period": 120, "offsets": [15]},
            "weeks": [week(4, "2026-10-06", "Thompson"), week(5, "2026-10-13", "Richmond")],
        },
        {
            "name": "Super Late Model Series - 2026 Season 4 - Fixed",
            "recurrence": {"kind": "interval", "period": 120, "offsets": [15]},
            "weeks": [week(4, "2026-10-06", "Thompson", 19), week(5, "2026-10-13", "Richmond")],
        },
        {
            "name": "IMSA Michelin Pilot Challenge - 2026 Season 4",
            "recurrence": {"kind": "weekly", "slots": [["Sat", "04:00"], ["Sat", "15:00"], ["Sun", "00:00"]],
                           "first_week_only": True},
            "weeks": [week(2, "2026-10-10", "Road Atlanta"), week(3, "2026-10-24", "Charlotte Roval")],
        },
        {"name": "Super Late Model Tour - 2026 Season Fixed", "recurrence": None,
         "weeks": [week(23, "2026-10-13", "South Boston")]},
    ]
}

CONFIG = {
    "rows": [
        {"label": "SLM", "open": "Super Late Model Series - 2026 Season 4",
         "fixed": "Super Late Model Series - 2026 Season 4 - Fixed"},
        {"label": "IMSA MPC", "open": "IMSA Michelin"},
        {"label": "SLM Tour", "fixed": "Super Late Model Tour"},
    ],
    "overrides": {"Super Late Model Tour - 2026 Season Fixed": {"kind": "weekly", "slots": [["Sun", "14:00"]]}},
}


def dt(*a):
    return datetime(*a, tzinfo=UTC)


def test_board_next_sessions():
    now = dt(2026, 10, 7, 21, 30)  # Wednesday
    slm, imsa, tour = build_board(CONFIG, DATA, now)
    assert slm.week["track"] == "Thompson"
    assert slm.open.next == dt(2026, 10, 7, 22, 15)
    assert slm.fixed.week["temp_c"] == 19
    assert imsa.open.next == dt(2026, 10, 10, 4, 0)
    assert tour.open is None
    assert tour.fixed.next == dt(2026, 10, 18, 14, 0)  # season not started yet -> first race
    assert tour.week["track"] == "South Boston"


def test_every_other_week_skips_off_week():
    now = dt(2026, 10, 11, 1, 0)  # after the Sunday 00:00 race of week 2
    imsa = build_board(CONFIG, DATA, now)[1]
    assert imsa.open.next == dt(2026, 10, 24, 4, 0)


def test_rollover_changes_track():
    now = dt(2026, 10, 13, 0, 5)
    slm = build_board(CONFIG, DATA, now)[0]
    assert slm.week["track"] == "Richmond"


def test_next_change_is_earliest_start():
    now = dt(2026, 10, 7, 21, 30)
    assert next_change(build_board(CONFIG, DATA, now), now) == dt(2026, 10, 7, 22, 15)


def test_find_series_ambiguous():
    with pytest.raises(ConfigError, match="ambiguous"):
        find_series(DATA, "Super Late Model Series")
