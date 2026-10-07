"""Render the static part of the board (series, track, weather) as a PNG table."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from .schedule import Row, weather_text

BG = (30, 31, 34)
HEADER_BG = (43, 45, 49)
ROW_ALT = (37, 38, 42)
TEXT = (219, 222, 225)
MUTED = (148, 155, 164)
ACCENT = (224, 60, 49)

FONT_CANDIDATES = {
    False: ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"],
    True: ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "DejaVuSans-Bold.ttf"],
}

# (header, width px)
COLUMNS = [("Series", 260), ("Wk", 50), ("Track", 460), ("Weather Open", 190), ("Weather Fixed", 190)]
PAD = 18
ROW_H = 44
TITLE_H = 64


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _cells(row: Row) -> list[str]:
    week = row.week
    return [
        row.label,
        str(week["week"]) if week else "—",
        week["track"] if week else "Season over",
        weather_text(row.open.week) if row.open else "—",
        weather_text(row.fixed.week) if row.fixed else "—",
    ]


def render_board(rows: list[Row], title: str) -> bytes:
    width = PAD * 2 + sum(w for _, w in COLUMNS)
    height = TITLE_H + ROW_H * (len(rows) + 1) + PAD
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    f_title, f_head, f_cell, f_label = _font(28, True), _font(18, True), _font(20), _font(20, True)

    d.rectangle([0, 0, 6, TITLE_H], fill=ACCENT)
    d.text((PAD + 4, TITLE_H // 2), title, font=f_title, fill=TEXT, anchor="lm")

    y = TITLE_H
    d.rectangle([0, y, width, y + ROW_H], fill=HEADER_BG)
    x = PAD
    for name, w in COLUMNS:
        d.text((x, y + ROW_H // 2), name.upper(), font=f_head, fill=MUTED, anchor="lm")
        x += w

    for i, row in enumerate(rows):
        y += ROW_H
        if i % 2:
            d.rectangle([0, y, width, y + ROW_H], fill=ROW_ALT)
        x = PAD
        for j, (cell, (_, w)) in enumerate(zip(_cells(row), COLUMNS)):
            font = f_label if j == 0 else f_cell
            d.text((x, y + ROW_H // 2), _fit(d, cell, font, w - 14), font=font,
                   fill=TEXT if j != 1 else MUTED, anchor="lm")
            x += w

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
