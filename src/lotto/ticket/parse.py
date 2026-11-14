"""Turn OCR tokens of a Lotto 6aus49 receipt into tips, Superzahl and draw dates.

Receipts are a fixed grid: a row label ("1." … "12.") followed by six
right-aligned numbers. The parser uses that geometry instead of trusting
the OCR's own grouping:

1. Straighten the coordinates (photos are rarely level).
2. Fit the row positions from the row labels (tolerates a missed label).
3. Fit the six column positions from the numbers' right edges.
4. Put each number into its cell; re-read missing or merged cells with a
   crop-level recognizer when one is supplied.
5. Check each tip against the game rules (six different numbers 1-49,
   printed ascending) and flag what breaks them.

Metadata (Superzahl, Spieltag, Laufzeit, dates, Losnummer, Super 6 /
Spiel 77, Betrag) is read from text lines.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, timedelta
from statistics import median

from lotto.ticket.models import SATURDAY, WEDNESDAY, Cell, Tip, TicketScan, Token

# (box in image pixels) -> (text, confidence)
CropReader = Callable[[tuple[float, float, float, float]], tuple[str, float]]

LOW_CONFIDENCE = 0.80
PRICE_PER_TIP = 1.20  # EUR, since 2020
PRICE_SPIEL77 = 2.50
PRICE_SUPER6 = 1.25
MAX_FEE = 1.50  # processing fee differs per state lottery

_ROW_LABEL = re.compile(r"^([1-9]|1[0-9]|2[0-4])\s*[.,:;]$")
# No trailing \b: OCR sometimes glues the date to the receipt id ("14.11.20262671.…").
_DATE = re.compile(r"(?<!\d)(\d{1,2})[.,](\d{1,2})[.,]((?:19|20)\d{2})")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1",
                              "i": "1", "Z": "2", "z": "2", "S": "5", "s": "5", "B": "8",
                              "g": "9", "q": "9"})


# --------------------------------------------------------------------------- geometry


def _skew_degrees(tokens: list[Token]) -> float:
    """Median slope of wide text lines; numbers alone are too short to measure."""
    angles = [
        t.angle
        for t in tokens
        if len(t.text) >= 4 and (t.x1 - t.x0) > 2.5 * t.height and abs(t.angle) < 30
    ]
    return median(angles) if angles else 0.0


class _Frame:
    """Rotate image coordinates into a level frame and back."""

    def __init__(self, degrees: float) -> None:
        rad = math.radians(degrees)
        self.cos, self.sin = math.cos(rad), math.sin(rad)

    def level(self, x: float, y: float) -> tuple[float, float]:
        return x * self.cos + y * self.sin, -x * self.sin + y * self.cos

    def image(self, x: float, y: float) -> tuple[float, float]:
        return x * self.cos - y * self.sin, x * self.sin + y * self.cos

    def level_token(self, t: Token) -> Token:
        """Move the token into the level frame and undo the tilt's box growth.

        An axis-aligned box around tilted text is taller than the text
        (W = w cos + h sin, H = w sin + h cos); solve for the real w, h.
        """
        cx, cy = self.level(t.cx, t.cy)
        bw, bh = t.x1 - t.x0, t.y1 - t.y0
        c, s = self.cos, abs(self.sin)
        det = c * c - s * s
        w, h = bw, bh
        if det > 0.5:
            w = max((bw * c - bh * s) / det, bw * 0.3)
            h = max((bh * c - bw * s) / det, bh * 0.3)
        return replace(t, x0=cx - w / 2, x1=cx + w / 2, y0=cy - h / 2, y1=cy + h / 2)

    def image_box(self, box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = box
        cx, cy = self.image((x0 + x1) / 2, (y0 + y1) / 2)
        hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
        return cx - hw, cy - hh, cx + hw, cy + hh


def _lines(tokens: list[Token], tol: float) -> list[list[Token]]:
    """Group tokens into text lines by vertical centre."""
    lines: list[list[Token]] = []
    for t in sorted(tokens, key=lambda t: t.cy):
        if t.height > 2.5 * (t.x1 - t.x0) and len(t.text) > 2:
            continue  # vertical side print ("WESTLOTTO", "Hinweise siehe Rückseite")
        if lines and abs(median(x.cy for x in lines[-1]) - t.cy) < tol:
            lines[-1].append(t)
        else:
            lines.append([t])
    return [sorted(line, key=lambda t: t.x0) for line in lines]


def _line_text(line: list[Token]) -> str:
    return " ".join(t.text for t in line)


# --------------------------------------------------------------------------- numbers


def _to_int(text: str, max_digits: int = 2) -> int | None:
    cleaned = text.strip().rstrip(".,").translate(_DIGIT_FIXES)
    cleaned = cleaned.replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) > max_digits:
        return None
    return int(cleaned)


def _split_numeric(t: Token) -> list[Token]:
    """'16 20' read as one box -> two tokens with interpolated x."""
    parts = [p for p in re.finditer(r"\S+", t.text)]
    if len(parts) <= 1:
        return [t]
    width = (t.x1 - t.x0) / max(len(t.text), 1)
    return [
        replace(t, text=m.group(), x0=t.x0 + m.start() * width, x1=t.x0 + m.end() * width)
        for m in parts
    ]


def _fit_rows(labels: list[tuple[int, Token]]) -> tuple[dict[int, float], float] | None:
    """Least-squares fit y = a + b * index over the row labels."""
    if len(labels) < 2:
        if len(labels) == 1:
            idx, tok = labels[0]
            return {idx: tok.cy}, tok.height * 1.05
        return None
    xs = [i for i, _ in labels]
    ys = [t.cy for _, t in labels]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    a = my - b * mx
    if b <= 0:
        return None
    return {i: a + b * i for i in range(1, max(xs) + 1)}, b


def _pick_labels(tokens: list[Token]) -> list[tuple[int, Token]]:
    """Row labels that line up in one column and count upwards."""
    cands = []
    for t in tokens:
        m = _ROW_LABEL.match(t.text.translate(_DIGIT_FIXES).replace(" ", ""))
        if m:
            cands.append((int(m.group(1)), t))
    if not cands:
        return []
    # The label column: most labels share roughly the same right edge.
    best: list[tuple[int, Token]] = []
    for _, anchor in cands:
        tol = anchor.height * 1.5
        group = sorted(
            (c for c in cands if abs(c[1].x1 - anchor.x1) < tol), key=lambda c: c[1].cy
        )
        # keep only labels whose number increases with y
        seq: list[tuple[int, Token]] = []
        for idx, tok in group:
            if not seq or idx > seq[-1][0]:
                seq.append((idx, tok))
        if len(seq) > len(best):
            best = seq
    return best


def _columns(rows: dict[int, list[Token]], spacing_hint: float) -> list[float]:
    """Right-edge x of the six number columns."""
    full = [sorted(r, key=lambda t: t.x1) for r in rows.values() if len(r) == 6]
    if full:
        return [median(r[j].x1 for r in full) for j in range(6)]
    # No complete row: cluster all right edges into up to six groups.
    edges = sorted(t.x1 for r in rows.values() for t in r)
    clusters: list[list[float]] = []
    for e in edges:
        if clusters and e - clusters[-1][-1] < spacing_hint:
            clusters[-1].append(e)
        else:
            clusters.append([e])
    return [median(c) for c in clusters][:6]


def _read_grid(
    tokens: list[Token], frame: _Frame, read_crop: CropReader | None
) -> tuple[list[Tip], float, float | None]:
    """Return tips, the row height and the y of the last row (level frame)."""
    labels = _pick_labels(tokens)
    fit = _fit_rows(labels)
    if fit is None:
        return [], median(t.height for t in tokens) if tokens else 20.0, None
    row_y, row_h = fit
    label_right = median(t.x1 for _, t in labels)
    last_y = row_y[max(row_y)]

    numeric: list[Token] = []
    for t in tokens:
        if t.x0 <= label_right - row_h * 0.2:
            continue
        if not (row_y[min(row_y)] - row_h * 0.6 < t.cy < last_y + row_h * 0.6 or t.height > 1.5 * row_h):
            continue
        for part in _split_numeric(t):
            if _to_int(part.text, max_digits=6) is not None:
                numeric.append(part)

    rows: dict[int, list[Token]] = {i: [] for i in row_y}
    tall: list[Token] = []
    for t in numeric:
        if t.height > 1.5 * row_h:
            tall.append(t)
            continue
        idx = min(row_y, key=lambda i: abs(row_y[i] - t.cy))
        if abs(row_y[idx] - t.cy) < row_h * 0.5 and _to_int(t.text) is not None:
            rows[idx].append(t)

    cols = _columns(rows, spacing_hint=row_h)
    if len(cols) < 6:
        # Not enough geometry to place missing cells; keep what we have in order.
        return (
            [_tip_from_values(i, [(_to_int(t.text), t.score) for t in sorted(r, key=lambda t: t.x1)])
             for i, r in rows.items()],
            row_h,
            last_y,
        )
    spacing = median(b - a for a, b in zip(cols, cols[1:]))

    # Merged vertical boxes ("1" "4" "4" read as "144"): spread one digit per row.
    tall_cells: dict[tuple[int, int], tuple[int, float]] = {}
    for t in tall:
        j = min(range(6), key=lambda c: abs(cols[c] - t.x1))
        if abs(cols[j] - t.x1) > spacing * 0.5:
            continue
        spanned = [i for i in row_y if t.y0 <= row_y[i] <= t.y1]
        digits = re.sub(r"\D", "", t.text.translate(_DIGIT_FIXES))
        if spanned and len(digits) == len(spanned):
            for i, d in zip(spanned, digits):
                tall_cells[(i, j)] = (int(d), min(t.score, 0.6))

    tips: list[Tip] = []
    for i in sorted(rows):
        slots: list[list[Token]] = [[] for _ in range(6)]
        for t in rows[i]:
            j = min(range(6), key=lambda c: abs(cols[c] - t.x1))
            if abs(cols[j] - t.x1) < spacing * 0.5:
                slots[j].append(t)
        def reread(j: int, row: int = i) -> tuple[int | None, float]:
            if read_crop is None:
                return None, 0.0
            box = (cols[j] - spacing * 0.85, row_y[row] - row_h * 0.5,
                   cols[j] + spacing * 0.08, row_y[row] + row_h * 0.5)
            text, score = read_crop(frame.image_box(box))
            return _to_int(text), score

        values: list[tuple[int | None, float]] = []
        for j, slot in enumerate(slots):
            if slot:
                text = "".join(t.text for t in sorted(slot, key=lambda t: t.x0))
                values.append((_to_int(text), min(t.score for t in slot)))
                continue
            value = reread(j)
            if value[0] is None:
                value = tall_cells.get((i, j), (None, 0.0))
            values.append(value)

        tip = _tip_from_values(i, values)
        # Second look at cells that break the rules (e.g. a "7" read as "1"
        # between 4 and 16): keep the crop's reading if it breaks fewer rules.
        if read_crop is not None:
            for j, cell in enumerate(tip.cells):
                if not cell.suspicious or not slots[j]:
                    continue
                alt = reread(j)
                if alt[0] is None or alt[0] == cell.value:
                    continue
                trial = list(values)
                trial[j] = alt
                candidate = _tip_from_values(i, trial)
                if _breaks(candidate) < _breaks(tip):
                    values, tip = trial, candidate
        tips.append(tip)
    # Drop trailing rows that are completely empty (fit extrapolation).
    while tips and all(c.value is None for c in tips[-1].cells):
        tips.pop()
    return tips, row_h, last_y


def _tip_from_values(index: int, values: list[tuple[int | None, float]]) -> Tip:
    cells = [Cell(value=v, confidence=s) for v, s in values]
    while len(cells) < 6:
        cells.append(Cell(value=None, confidence=0.0))
    cells = cells[:6]
    _flag_rule_breaks(cells)
    return Tip(index=index, cells=cells)


def _breaks(tip: Tip) -> int:
    return sum(c.suspicious for c in tip.cells)


def _flag_rule_breaks(cells: list[Cell]) -> None:
    """Receipts print six different numbers 1-49 in ascending order."""
    vals = [c.value for c in cells]
    for k, c in enumerate(cells):
        v = c.value
        if v is None or not 1 <= v <= 49 or c.confidence < LOW_CONFIDENCE:
            c.suspicious = True
            continue
        if vals.count(v) > 1:
            c.suspicious = True
        prev = next((p for p in reversed(vals[:k]) if p is not None), None)
        nxt = next((p for p in vals[k + 1:] if p is not None), None)
        if (prev is not None and v <= prev) or (nxt is not None and v >= nxt):
            c.suspicious = True


# --------------------------------------------------------------------------- metadata


def _parse_date(text: str) -> date | None:
    m = _DATE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _weekdays(text: str) -> tuple[int, ...]:
    low = text.lower()
    days = set()
    if re.search(r"mittwoch|\bmi\b", low):
        days.add(WEDNESDAY)
    if re.search(r"samstag|\bsa\b", low):
        days.add(SATURDAY)
    return tuple(sorted(days))


def _yes_no(text: str) -> bool | None:
    low = text.lower()
    if re.search(r"\bja\b", low):
        return True
    if re.search(r"ne[il1]n", low):
        return False
    return None


def next_draw_after(moment: datetime, weekdays: tuple[int, ...] = (WEDNESDAY, SATURDAY)) -> date:
    """First draw a ticket bought at ``moment`` takes part in.

    Sales close at 18:00 on Wednesdays and 19:00 on Saturdays.
    """
    cutoff = {WEDNESDAY: 18, SATURDAY: 19}
    day = moment.date()
    if day.weekday() in weekdays and moment.hour < cutoff.get(day.weekday(), 18):
        return day
    day += timedelta(days=1)
    while day.weekday() not in weekdays:
        day += timedelta(days=1)
    return day


def _read_metadata(scan: TicketScan, lines: list[list[Token]]) -> None:
    texts = [(_line_text(line), line) for line in lines]

    for k, (text, _line) in enumerate(texts):
        low = text.lower()

        if "superzah" in low and scan.superzahl is None:
            after = low.split("superzah", 1)[1]
            digits = re.findall(r"\d", after.translate(_DIGIT_FIXES))
            if digits:
                scan.superzahl = int(digits[-1])

        if "spieltag" in low and not scan.draw_weekdays:
            scan.draw_weekdays = _weekdays(low.split("spieltag", 1)[1])
            if scan.first_draw is None and _parse_date(text):
                scan.first_draw = _parse_date(text)

        if "laufzeit" in low:
            m = re.search(r"laufzeit\D*(\d+)\s*woche", low)
            if m:
                scan.weeks = int(m.group(1))
            if _parse_date(text):
                scan.first_draw = _parse_date(text)

        if "losnummer" in low and scan.losnummer is None:
            for _, nxt in texts[k : k + 3]:
                for t in nxt:
                    if re.fullmatch(r"\d{7}", t.text.replace(" ", "")):
                        scan.losnummer = t.text.replace(" ", "")
                        break
                if scan.losnummer:
                    break

        if re.search(r"super\s*6", low):
            seg = re.split(r"super\s*6", low, maxsplit=1)[1]
            scan.super6 = _yes_no(re.split(r"spiel\s*77", seg)[0])
        if re.search(r"spiel\s*77", low):
            scan.spiel77 = _yes_no(re.split(r"spiel\s*77", low, maxsplit=1)[1])

        if "betrag" in low:
            m = re.search(r"(\d+)[.,](\d{2})", low.split("betrag", 1)[1])
            if m:
                scan.amount_eur = float(f"{m.group(1)}.{m.group(2)}")

        if _TIME.search(text) and _parse_date(text) and scan.purchased_at is None:
            d, tm = _parse_date(text), _TIME.search(text)
            assert d is not None and tm is not None
            try:
                scan.purchased_at = datetime(
                    d.year, d.month, d.day, int(tm.group(1)), int(tm.group(2)), int(tm.group(3) or 0)
                )
            except ValueError:
                pass

    # Draw date on the line right under "Spieltag …" (layout variant).
    if scan.first_draw is None:
        for k, (text, _) in enumerate(texts):
            if "spieltag" in text.lower():
                for nxt_text, _ in texts[k + 1 : k + 3]:
                    if _parse_date(nxt_text) and not _TIME.search(nxt_text):
                        scan.first_draw = _parse_date(nxt_text)
                        break
                break


def _finish(scan: TicketScan) -> None:
    if not scan.draw_weekdays and scan.first_draw and scan.first_draw.weekday() in (WEDNESDAY, SATURDAY):
        scan.draw_weekdays = (scan.first_draw.weekday(),)

    if scan.first_draw and scan.draw_weekdays and scan.first_draw.weekday() not in scan.draw_weekdays:
        scan.warnings.append("date_not_draw_day")
        scan.first_draw = None

    if scan.first_draw is None and scan.purchased_at is not None:
        scan.first_draw = next_draw_after(scan.purchased_at, scan.draw_weekdays or (WEDNESDAY, SATURDAY))
        scan.first_draw_inferred = True
        scan.warnings.append("date_inferred")

    if scan.superzahl is None:
        scan.warnings.append("superzahl_missing")
    if any(t.needs_review for t in scan.tips):
        scan.warnings.append("tips_need_review")

    # Cross-check: does the paid amount fit the number of tips we found?
    if scan.amount_eur is not None and scan.tips:
        draws = (scan.weeks or 1) * max(len(scan.draw_weekdays), 1)
        expected = draws * (
            len(scan.tips) * PRICE_PER_TIP
            + (PRICE_SPIEL77 if scan.spiel77 else 0)
            + (PRICE_SUPER6 if scan.super6 else 0)
        )
        fee = round(scan.amount_eur - expected, 2)
        if not 0 <= fee <= MAX_FEE:
            scan.warnings.append("amount_mismatch")


# --------------------------------------------------------------------------- entry


def parse_ticket(tokens: list[Token], read_crop: CropReader | None = None) -> TicketScan:
    """Parse OCR tokens of one receipt. ``read_crop`` re-reads single cells."""
    scan = TicketScan()
    if not tokens:
        scan.warnings.append("no_text")
        return scan
    frame = _Frame(_skew_degrees(tokens))
    level = [frame.level_token(t) for t in tokens]

    tips, row_h, _ = _read_grid(level, frame, read_crop)
    scan.tips = tips
    if not tips:
        scan.warnings.append("no_tips")

    _read_metadata(scan, _lines(level, tol=row_h * 0.45))
    _finish(scan)
    return scan
