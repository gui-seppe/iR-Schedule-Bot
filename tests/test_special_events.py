from datetime import date, datetime, timezone

import pytest

from bot.message import event_field
from bot.special_events import attach_posts, parse_calendar, parse_dates, parse_post, resolve_slots, upcoming

UTC = timezone.utc


@pytest.mark.parametrize("text,expected", [
    ("October 16-18, 2026", (date(2026, 10, 16), date(2026, 10, 18))),
    ("Oct 30-31, 2026", (date(2026, 10, 30), date(2026, 10, 31))),
    ("November 27–29, 2026", (date(2026, 11, 27), date(2026, 11, 29))),
    ("May 29 – 31, 2026", (date(2026, 5, 29), date(2026, 5, 31))),
    ("June 30 – July 6, 2026", (date(2026, 6, 30), date(2026, 7, 6))),
    ("February 11-18, 202_6", (date(2026, 2, 11), date(2026, 2, 18))),
    ("Date : TBD", None),
    (None, None),
])
def test_parse_dates(text, expected):
    assert parse_dates(text) == expected


CALENDAR_HTML = """
<h2>Upcoming Events</h2>
<section class="wp-block-cover" id="indy-8hr"><div>
<p class="is-style-default" style="color:#ffffffba;letter-spacing:3px">TEAM EVENT</p>
<h2 class="wp-block-heading">8 Hours of Indianapolis</h2>
<p><strong><em>October 16-18, 2026</em></strong></p>
<p>The&nbsp;<strong>8 Hours</strong> is held at <a href="https://www.iracing.com/tracks/indianapolis-motor-speedway/">Indianapolis Motor Speedway</a>.</p>
<details><summary>GT3</summary></details>
</div></section>
<section id="dale"><h2>Dale Jr Charity Event</h2><p><strong><em>Date : TBD</em></strong></p></section>
<section id="ff"><h2>iRacing FF1600 Festival</h2><p><strong><em>Oct 30-31, 2026</em></strong></p>
<details><summary>Ray FF1600</summary></details></section>
"""


def test_parse_calendar():
    indy, ff = parse_calendar(CALENDAR_HTML)  # TBD event skipped
    assert indy == {"name": "8 Hours of Indianapolis", "start": "2026-10-16", "end": "2026-10-18",
                    "tag": "Team Event", "track": "Indianapolis Motor Speedway", "classes": ["GT3"]}
    assert ff["name"] == "iRacing FF1600 Festival" and ff["tag"] is None and ff["classes"] == ["Ray FF1600"]


POST = {
    "date_gmt": "2026-10-12T08:00:44",
    "link": "https://www.iracing.com/this-week-iracing-indy-8-hour-special-event/",
    "title": {"rendered": "THIS WEEK: iRacing Indy 8 Hour presented by PC&#8217;s by THOMAS | Special Event"},
    "content": {"rendered": """
<p>TRACK: INDIANAPOLIS MOTOR SPEEDWAY &#8211; ROAD COURSE</p>
<p>CARS COMPETING: GT3 Class</p>
<h4>TIMES TO RACE</h4>
<p>Timeslot #1: Friday at 22:00 GMT (6:00 p.m. ET)<br>
Timeslot #2: Saturday at 7:00 GMT (3:00 a.m. ET)<br>
Timeslot #3: Saturday at 12:00 GMT (8:00 a.m. ET) &lt;- BROADCASTED SPLIT<br>
Timeslot #4: Saturday at 16:00 GMT (12:00 p.m. ET)<br>
Timeslot #5: Sunday at 00:00 GMT (8:00 p.m. ET Saturday)</p>
<h4>ABOUT</h4><p>The event will be scheduled in the sim for October 10th at 10:50 AM.</p>
"""},
}


def test_parse_post():
    p = parse_post(POST)
    assert p["title"] == "iRacing Indy 8 Hour presented by PC’s by THOMAS"
    assert p["track"] == "Indianapolis Motor Speedway – Road Course"
    assert p["slots"] == [(4, 22 * 60), (5, 7 * 60), (5, 12 * 60), (5, 16 * 60), (6, 0)]


def test_resolve_slots_includes_sunday_after_range():
    slots = [(4, 22 * 60), (6, 0)]
    assert resolve_slots(slots, date(2026, 10, 16), date(2026, 10, 17)) == [
        "2026-10-16T22:00:00+00:00", "2026-10-18T00:00:00+00:00"]


def test_attach_posts_matches_by_week_and_name():
    events = parse_calendar(CALENDAR_HTML)
    attach_posts(events, [parse_post(POST)])
    indy, ff = events
    assert indy["track"] == "Indianapolis Motor Speedway – Road Course"
    assert len(indy["sessions"]) == 5 and indy["sessions"][0] == "2026-10-16T22:00:00+00:00"
    assert "sessions" not in ff  # its post isn't out yet


def test_upcoming_this_and_next_week():
    data = {"events": [
        {"name": "Indy", "start": "2026-10-16", "end": "2026-10-18",
         "sessions": ["2026-10-16T22:00:00+00:00", "2026-10-18T00:00:00+00:00"]},
        {"name": "Next week", "start": "2026-10-23", "end": "2026-10-25"},
        {"name": "In three weeks", "start": "2026-10-30", "end": "2026-10-31"},
    ]}
    tue = datetime(2026, 10, 13, 12, tzinfo=UTC)
    assert [e["name"] for e in upcoming(data, tue)] == ["Indy", "Next week"]
    # Indy stays listed while its last (Sunday 00:00) race runs, then drops off
    assert "Indy" in [e["name"] for e in upcoming(data, datetime(2026, 10, 18, 20, tzinfo=UTC))]
    assert "Indy" not in [e["name"] for e in upcoming(data, datetime(2026, 10, 19, 3, tzinfo=UTC))]


def test_event_field_strikes_past_and_highlights_next():
    ev = {"name": "Indy", "start": "2026-10-16", "end": "2026-10-18", "classes": ["GT3"],
          "sessions": ["2026-10-16T22:00:00+00:00", "2026-10-17T07:00:00+00:00", "2026-10-17T12:00:00+00:00"]}
    f = event_field(ev, datetime(2026, 10, 17, 1, tzinfo=UTC))
    past, nxt, later = f["value"].splitlines()[-3:]
    assert past.startswith("~~<t:") and nxt.startswith("**<t:") and ":R>" in nxt and later.startswith("<t:")
    assert f["inline"] is False and "Oct 16–18" in f["value"]


def test_event_field_without_times():
    f = event_field({"name": "FF1600", "start": "2026-10-30", "end": "2026-10-31"}, datetime(2026, 10, 20, tzinfo=UTC))
    assert "Monday of race week" in f["value"]
