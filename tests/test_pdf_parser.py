from pathlib import Path

import pytest

from bot.pdf_parser import parse_text

FIXTURE = Path(__file__).parent / "fixtures" / "sample.txt"


@pytest.fixture(scope="module")
def series():
    return {s.name: s for s in parse_text(FIXTURE.read_text(encoding="utf-8"))}


def test_series_found(series):
    assert list(series) == [
        "Mini Stock Rookie Series by Thrustmaster - 2026 Season 4",
        "ARCA Menards Series - 2026 Season 4 - Fixed",
        "Draft Master Challenge by Simagic - 2026 Season 4",
        "Production Endurance Challenge - 2026 Season 4",
        "Big Block Modified Series - 2026 Season 4",
        "INDYCAR Series - Oval - Fixed - 2026 Season 4",
        "Super Late Model Tour - 2026 Season Fixed",
    ]


def test_basic_week(series):
    s = series["Mini Stock Rookie Series by Thrustmaster - 2026 Season 4"]
    assert s.cars == "Mini Stock"
    assert s.recurrence == {"kind": "interval", "period": 60, "offsets": [15, 45]}
    w1, w2 = s.weeks
    assert (w1.week, w1.start, w1.track) == (1, "2026-09-15", "Charlotte Motor Speedway - Oval")
    assert (w1.temp_c, w1.temp_f, w1.rain, w1.length) == (29, 84, "None", "15 laps")
    assert w2.track == "Langley Speedway" and w2.length == "35 laps"


def test_wrapped_track_name(series):
    w2 = series["ARCA Menards Series - 2026 Season 4 - Fixed"].weeks[1]
    assert w2.track == "World Wide Technology Raceway (Gateway) - Oval"
    w6 = series["Production Endurance Challenge - 2026 Season 4"].weeks[1]
    assert w6.track == "Nürburgring Grand-Prix-Strecke - Kurzanbindung w/out Arena"


def test_weekly_cars(series):
    s = series["Draft Master Challenge by Simagic - 2026 Season 4"]
    assert s.weeks[0].track == "Talladega Superspeedway"
    assert s.weeks[0].cars == "Gen 4 Grand National"
    assert s.weeks[1].cars.startswith("NASCAR Cup Series Next Gen Chevrolet Camaro ZL1")


def test_team_event(series):
    s = series["Production Endurance Challenge - 2026 Season 4"]
    assert s.cars.endswith("Toyota GR86")
    assert s.recurrence["kind"] == "weekly"
    assert s.weeks[0].rain == "29%" and s.weeks[0].length == "120 mins"


def test_heat_racing_and_constant_weather(series):
    assert series["Big Block Modified Series - 2026 Season 4"].weeks[0].length == "50 laps"
    w = series["INDYCAR Series - Oval - Fixed - 2026 Season 4"].weeks[0]
    assert w.temp_c is None and w.rain is None and w.length == "60 laps"


def test_unparseable_rule(series):
    s = series["Super Late Model Tour - 2026 Season Fixed"]
    assert s.rule == "4 Timeslots Per Week" and s.recurrence is None
