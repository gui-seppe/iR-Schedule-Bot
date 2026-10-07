from datetime import datetime, timezone

import pytest

from bot.recurrence import Recurrence, parse_rule

# (rule text from the 2026 S4 PDF, period, offsets)
INTERVAL_CASES = [
    ("Races every 30 minutes at :15 and :45", 60, [15, 45]),
    ("Races every 30 minutes", 60, [0, 30]),
    ("Races every 30 minutes at :15 & :45", 60, [15, 45]),
    ("Races every 30 minutes at :00 & :30", 60, [0, 30]),
    ("Races every 30 minutes at :00 & 30", 60, [0, 30]),
    ("Races every 30 minutes at :15 and :45 past", 60, [15, 45]),
    ("Open Qualifier every 30 mins at :15 & :45 past", 60, [15, 45]),
    ("Races at :15 and :45", 60, [15, 45]),
    ("Races every thirty minutes on the hour and :30 past", 60, [0, 30]),
    ("Races hourly at :45 past", 60, [45]),
    ("Races every hour at :45", 60, [45]),
    ("Races every hour on the hour", 60, [0]),
    ("Every hour on the :30", 60, [30]),
    ("Races hourly at the top of the hour", 60, [0]),
    ("Races every hour at half past", 60, [30]),
    ("Races on the hour every hour", 60, [0]),
    ("Races hourly on the 00", 60, [0]),
    ("Races at every hour at :15", 60, [15]),
    ("Races every hour at :15 after", 60, [15]),
    ("Race every hour at the top of the hour", 60, [0]),
    ("Races on every hour on the hour | Qualifying every hour at :30", 60, [0]),
    ("Races at 15 past every 2 hours", 120, [15]),
    ("Races every 2 hours on the hour", 120, [0]),
    ("Races every 2 hours at :30", 120, [30]),
    ("Races 45 past every 2 hours", 120, [45]),
    ("Races every 2 hours at the :30", 120, [30]),
    ("Races every odd 2 hours on the hour", 120, [60]),
    ("Races every even 2 hours at :30 past", 120, [30]),
]


@pytest.mark.parametrize("text,period,offsets", INTERVAL_CASES)
def test_interval_rules(text, period, offsets):
    r = parse_rule(text)
    assert r is not None and r.kind == "interval"
    assert (r.period, r.offsets) == (period, offsets)


WEEKLY_CASES = [
    ("Races on Saturday at 7 & 17:00 GMT & Sunday at 0 & 13 GMT",
     [("Sat", "07:00"), ("Sat", "17:00"), ("Sun", "00:00"), ("Sun", "13:00")]),
    ("Races Friday at 19 GMT, Saturday at 7 GMT, Sunday at 18 GMT",
     [("Fri", "19:00"), ("Sat", "07:00"), ("Sun", "18:00")]),
    ("Races Saturdays 9 and 19 GMT and Sundays 17 GMT",
     [("Sat", "09:00"), ("Sat", "19:00"), ("Sun", "17:00")]),
    ("Races Thur & Sat at 10, 19 GMT & Fri & Sun at 1,4 GMT",
     [("Thu", "10:00"), ("Thu", "19:00"), ("Fri", "01:00"), ("Fri", "04:00"),
      ("Sat", "10:00"), ("Sat", "19:00"), ("Sun", "01:00"), ("Sun", "04:00")]),
    ("Races Weds 2 GMT, Sat 8 GMT, Sun 19 GMT, & Mon at 18 GMT",
     [("Mon", "18:00"), ("Wed", "02:00"), ("Sat", "08:00"), ("Sun", "19:00")]),
]


@pytest.mark.parametrize("text,slots", WEEKLY_CASES)
def test_weekly_rules(text, slots):
    r = parse_rule(text)
    assert r is not None and r.kind == "weekly"
    assert sorted(tuple(s) for s in r.to_dict()["slots"]) == sorted(slots)


def test_every_other_flag():
    r = parse_rule("Races every other Saturday at 4 & 15 GMT and Sunday at 0 GMT, 20 GMT")
    assert r.first_week_only


@pytest.mark.parametrize("text", ["5 Timeslots Per Week", "Four timeslots per race week"])
def test_unparseable(text):
    assert parse_rule(text) is None


def test_occurrences_two_hourly_odd():
    r = parse_rule("Races every odd 2 hours on the hour")
    start = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc)
    assert [x.hour for x in r.occurrences(start, end)] == [1, 3, 5]


def test_roundtrip_dict():
    r = parse_rule("Races Thur & Sat at 10, 19 GMT & Fri & Sun at 1,4 GMT")
    assert Recurrence.from_dict(r.to_dict()).slots == r.slots
