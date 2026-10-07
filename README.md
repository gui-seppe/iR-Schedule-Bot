# iRacing Schedule Bot

A Discord bot that keeps one message in a channel showing your tracked iRacing series:

- **Image** with the static info: series, week, track, Open/Fixed weather.
- **Embed text** with live countdowns (`<t:…:R>`) for the next Open and Fixed race. Discord updates these
  on each viewer's screen, so the bot only edits the message right after a tracked race starts or the week rolls over.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
```

1. Create a bot at https://discord.com/developers/applications, copy its token, and invite it to your
   server with the *Send Messages*, *Embed Links* and *Attach Files* permissions.
2. `cp .env.example .env` and fill in `DISCORD_TOKEN` and `CHANNEL_ID` (right-click the channel → Copy ID,
   with Developer Mode on).
3. Convert the season PDF:
   ```bash
   python scripts/parse_schedule.py path/to/2026s4.pdf
   ```
   The script lists series whose race times can't be read from the PDF (e.g. "4 Timeslots Per Week").
   Add those to `overrides` in the config if you track them.
4. `cp config.example.json config.json` and list the series you want. `open` / `fixed` take the full
   series name from the PDF (or any unique part of it). Either can be omitted.

## Hosting on GitHub Actions (no server)

`.github/workflows/board.yml` runs `python -m bot.oneshot` every 5 minutes: it posts through a channel
webhook, edits the message only when something changed, and exits.

1. Discord: channel settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.
2. Push this repo to GitHub as a **public** repository (Actions minutes are unlimited for public repos; a
   private repo would run out of its 2,000 free minutes). The webhook URL stays secret (next step).
3. Repo → Settings → Secrets and variables → Actions:
   - *Secrets* tab → New secret `WEBHOOK_URL` = the webhook URL.
4. Actions tab → *Update board* → Run workflow. It posts the message and prints its ID.
5. Same settings page → *Variables* tab → New variable `MESSAGE_ID` = that ID. From now on runs edit that message.

Notes: scheduled runs can be delayed by a few minutes at busy times, so the board may move on to the next
race a few minutes after the start. GitHub pauses scheduled workflows in repos with no commits for 60 days:
committing the new season's `schedule.json` keeps it alive (or re-enable it from the Actions tab).

New season: `python scripts/parse_schedule.py new.pdf`, update `config.json` names, commit and push.

## Run locally

```bash
python -m bot.preview                      # renders preview.png + prints the embed text, no Discord needed
python -m bot.preview --now 2026-10-10T12:00
python -m bot.main                         # the bot
python -m pytest                           # tests
```

## Sections

Instead of a flat `rows` list, `config.json` can group rows into sections. Each becomes its own embed
with its own color (up to 6 rows per section):

```json
"sections": [
  {"title": "⚡ Sprint", "color": "#E03C31", "rows": [ ... ]},
  {"title": "⏱️ Endurance", "color": "#F5A623", "rows": [ ... ]}
]
```

## Overrides

Race times come from the "Races every…" line of each series. To set or fix them by hand:

```json
"overrides": {
  "Series name": {"kind": "interval", "period": 120, "offsets": [15]},
  "Other series": {"kind": "weekly", "slots": [["Sat", "18:00"], ["Sun", "01:00"]], "first_week_only": false}
}
```

`interval`: races every `period` minutes, at `offsets` minutes after the period start (periods are anchored to
00:00 UTC, so `period: 120, offsets: [60]` means odd hours). `weekly`: fixed UTC day/time slots.
All times are UTC; race weeks start at 00:00 UTC on the date printed in the PDF.
