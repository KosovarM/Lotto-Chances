"""Receipt parser tests. No OCR engine needed: tokens are recorded or built by hand."""

import json
from datetime import date, datetime
from pathlib import Path

from lotto.ticket.models import SATURDAY, WEDNESDAY, Token
from lotto.ticket.parse import next_draw_after, parse_ticket

FIXTURES = Path(__file__).parent / "fixtures"

# Ground truth of the real receipt the recorded tokens come from.
TRUTH = [
    (5, 12, 17, 23, 30, 36), (3, 7, 16, 20, 26, 32), (6, 10, 14, 24, 27, 29),
    (1, 6, 17, 19, 36, 41), (4, 7, 16, 19, 21, 32), (4, 7, 9, 18, 21, 23),
    (10, 14, 17, 20, 29, 32), (4, 18, 20, 24, 30, 48), (22, 31, 34, 37, 45, 48),
    (2, 4, 12, 16, 27, 31), (4, 16, 20, 22, 26, 31), (3, 12, 16, 20, 30, 32),
]


def _recorded_tokens() -> list[Token]:
    raw = json.loads((FIXTURES / "westlotto_receipt_tokens.json").read_text(encoding="utf-8"))
    return [Token(**t) for t in raw]


def test_recorded_receipt_reads_all_numbers_and_metadata():
    scan = parse_ticket(_recorded_tokens())
    assert [t.numbers for t in scan.tips] == TRUTH
    assert scan.superzahl == 5
    assert scan.first_draw == date(2026, 11, 14)
    assert scan.draw_weekdays == (SATURDAY,)
    assert scan.weeks == 1
    assert scan.purchased_at == datetime(2026, 11, 14, 18, 54, 59)
    assert scan.losnummer == "1234567"
    assert scan.super6 is False and scan.spiel77 is False
    assert scan.amount_eur == 14.90
    assert "amount_mismatch" not in scan.warnings


def test_merged_vertical_box_is_split_but_flagged():
    # The OCR merged first-column digits of several rows into one tall box;
    # without a crop reader they are spread one per row and marked for review.
    scan = parse_ticket(_recorded_tokens())
    flagged = {(t.index, k) for t in scan.tips for k, c in enumerate(t.cells) if c.suspicious}
    assert flagged, "split cells must be flagged"
    assert all(k == 0 for _, k in flagged)


def test_crop_reader_fills_missing_cells():
    tokens = [t for t in _recorded_tokens() if t.height < 60 or not t.text.isdigit()]
    calls = []

    def reader(box):
        calls.append(box)
        return "", 0.0

    scan = parse_ticket(tokens, read_crop=reader)
    assert calls, "missing cells should be re-read"
    missing = [c for t in scan.tips for c in t.cells if c.value is None]
    assert missing and all(c.suspicious for c in missing)


# ---------------------------------------------------------------- synthetic layouts

ROW_H = 40.0
COLS = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0]


def _tok(text, x1, y, w=None, h=30.0, score=0.99, angle=0.0):
    w = w if w is not None else 18.0 * len(text)
    return Token(text=text, x0=x1 - w, y0=y - h / 2, x1=x1, y1=y + h / 2, score=score, angle=angle)


def _receipt(tips, *, extra=(), skip=()):
    toks = [_tok("Spielvoraussagen", 400, 60, w=300)]
    for i, tip in enumerate(tips, start=1):
        y = 100 + i * ROW_H
        toks.append(_tok(f"{i}.", 150, y))
        for j, n in enumerate(tip):
            if (i, j) not in skip:
                toks.append(_tok(str(n), COLS[j], y))
    last = 100 + len(tips) * ROW_H
    toks.append(_tok("Superzahl", 260, last + ROW_H, w=170))
    toks.append(_tok("7", COLS[-1], last + ROW_H))
    toks.extend(extra(last) if callable(extra) else extra)
    return toks


TIPS = [(1, 8, 15, 22, 33, 49), (2, 9, 16, 23, 34, 40), (3, 10, 17, 24, 35, 41)]


def test_layout_with_two_draw_days_and_weeks():
    def extra(last):
        return [
            _tok("Spieltag Mittwoch + Samstag", 700, last + 3 * ROW_H, w=480),
            _tok("Laufzeit: 2 Wochen", 400, last + 4 * ROW_H, w=300),
            _tok("11.11.2026", 800, last + 4 * ROW_H, w=170),
        ]

    scan = parse_ticket(_receipt(TIPS, extra=extra))
    assert [t.numbers for t in scan.tips] == TIPS
    assert scan.superzahl == 7
    assert scan.draw_weekdays == (WEDNESDAY, SATURDAY)
    assert scan.weeks == 2
    assert scan.first_draw == date(2026, 11, 11)


def test_misread_breaking_order_is_flagged():
    bad = [(1, 8, 15, 22, 33, 49), (2, 9, 76, 23, 34, 40)]  # "16" read as "76"
    scan = parse_ticket(_receipt(bad))
    assert scan.tips[1].needs_review
    assert scan.tips[1].cells[2].suspicious
    assert not scan.tips[0].needs_review


def test_missing_cell_is_reread_from_crop():
    def reader(box):
        x0, y0, x1, y1 = box
        assert x0 < COLS[3] <= x1 + 1  # the crop covers the missing column
        return "23", 0.97

    scan = parse_ticket(_receipt(TIPS, skip={(2, 3)}), read_crop=reader)
    assert scan.tips[1].numbers == TIPS[1]


def test_tilted_photo_coordinates_are_levelled():
    import math

    angle = 3.0
    rad = math.radians(angle)
    tilted = []
    for t in _receipt(TIPS):
        cx, cy = t.cx, t.cy
        nx, ny = cx * math.cos(rad) - cy * math.sin(rad), cx * math.sin(rad) + cy * math.cos(rad)
        tilted.append(Token(t.text, nx - (t.x1 - t.x0) / 2, ny - t.height / 2,
                            nx + (t.x1 - t.x0) / 2, ny + t.height / 2, t.score, angle))
    scan = parse_ticket(tilted)
    assert [t.numbers for t in scan.tips] == TIPS


def test_date_glued_to_receipt_id_and_inferred_draw_date():
    def extra(last):
        return [
            _tok("Spieltag Samstag", 600, last + 3 * ROW_H, w=300),
            _tok("14.11.20261111.2222.3333/01 18:54:59", 800, last + 6 * ROW_H, w=650),
        ]

    scan = parse_ticket(_receipt(TIPS, extra=extra))
    assert scan.purchased_at == datetime(2026, 11, 14, 18, 54, 59)
    assert scan.first_draw == date(2026, 11, 14)
    assert scan.first_draw_inferred
    assert "date_inferred" in scan.warnings


def test_missing_superzahl_is_reported():
    toks = [t for t in _receipt(TIPS) if t.text != "Superzahl"]
    scan = parse_ticket(toks)
    assert scan.superzahl is None
    assert "superzahl_missing" in scan.warnings


def test_no_text():
    assert "no_text" in parse_ticket([]).warnings


def test_next_draw_after_respects_sales_cutoff():
    assert next_draw_after(datetime(2026, 11, 14, 18, 54)) == date(2026, 11, 14)
    assert next_draw_after(datetime(2026, 11, 14, 19, 5)) == date(2026, 11, 18)
    assert next_draw_after(datetime(2026, 11, 11, 18, 30)) == date(2026, 11, 14)
    assert next_draw_after(datetime(2026, 11, 12, 9, 0), (SATURDAY,)) == date(2026, 11, 14)
