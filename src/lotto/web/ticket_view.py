"""Web glue for the receipt check: form state <-> scan, validation, evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from lotto.ticket.models import SATURDAY, WEDNESDAY, TicketScan
from lotto.ticket.prizes import DrawOutcome, check_ticket

MAX_TIPS = 12
MAX_WEEKS = 10


@dataclass
class TicketForm:
    """What the correction form shows; strings so wrong input can be echoed back."""

    rows: list[list[dict[str, Any]]] = field(default_factory=list)  # {"v": str, "bad": bool}
    superzahl: str = ""
    first_draw: str = ""
    first_draw_inferred: bool = False
    weeks: str = "1"
    wed: bool = False
    sat: bool = True
    losnummer: str = ""
    super6: bool = False
    spiel77: bool = False
    errors: list[str] = field(default_factory=list)  # i18n keys
    bad_rows: list[int] = field(default_factory=list)  # 1-based tip numbers


def empty_form(rows: int = 6) -> TicketForm:
    return TicketForm(rows=[[{"v": "", "bad": False} for _ in range(6)] for _ in range(rows)])


def form_from_scan(scan: TicketScan) -> TicketForm:
    form = TicketForm(
        rows=[
            [{"v": "" if c.value is None else str(c.value), "bad": c.suspicious} for c in tip.cells]
            for tip in scan.tips[:MAX_TIPS]
        ],
        superzahl="" if scan.superzahl is None else str(scan.superzahl),
        first_draw=scan.first_draw.isoformat() if scan.first_draw else "",
        first_draw_inferred=scan.first_draw_inferred,
        weeks=str(scan.weeks or 1),
        wed=WEDNESDAY in scan.draw_weekdays,
        sat=SATURDAY in scan.draw_weekdays or not scan.draw_weekdays,
        losnummer=scan.losnummer or "",
        super6=bool(scan.super6),
        spiel77=bool(scan.spiel77),
    )
    if not form.rows:
        form.rows = empty_form().rows
    return form


def form_from_post(data: Any) -> TicketForm:
    rows = []
    for i in range(1, MAX_TIPS + 1):
        if f"n_{i}_1" not in data:
            break
        rows.append([{"v": data.get(f"n_{i}_{j}", "").strip(), "bad": False} for j in range(1, 7)])
    return TicketForm(
        rows=rows or empty_form().rows,
        superzahl=data.get("superzahl", "").strip(),
        first_draw=data.get("first_draw", "").strip(),
        weeks=data.get("weeks", "1").strip() or "1",
        wed=data.get("wed") == "1",
        sat=data.get("sat") == "1",
        losnummer=data.get("losnummer", "").strip(),
        super6=data.get("super6") == "1",
        spiel77=data.get("spiel77") == "1",
    )


@dataclass
class ValidTicket:
    tips: list[tuple[int, tuple[int, ...]]]
    superzahl: int
    first_draw: date
    weekdays: tuple[int, ...]
    weeks: int
    losnummer: str | None
    super6: bool
    spiel77: bool


def validate(form: TicketForm) -> ValidTicket | None:
    """Check the form like the game rules do; mark problems on the form."""
    tips: list[tuple[int, tuple[int, ...]]] = []
    for i, row in enumerate(form.rows, start=1):
        raw = [c["v"] for c in row]
        if not any(raw):
            continue  # empty rows are ignored
        nums = [int(v) if v.isdigit() else None for v in raw]
        ok = all(n is not None and 1 <= n <= 49 for n in nums) and len(set(nums)) == 6
        if not ok:
            form.bad_rows.append(i)
            for c, n in zip(row, nums):
                c["bad"] = n is None or not 1 <= n <= 49 or nums.count(n) > 1
            continue
        tips.append((i, tuple(sorted(n for n in nums if n is not None))))
    if form.bad_rows:
        form.errors.append("err_tip_invalid")
    if not tips and not form.bad_rows:
        form.errors.append("err_no_tips")

    superzahl = int(form.superzahl) if form.superzahl.isdigit() and int(form.superzahl) <= 9 else None
    if superzahl is None:
        form.errors.append("err_superzahl")

    weekdays = tuple(d for d, on in ((WEDNESDAY, form.wed), (SATURDAY, form.sat)) if on)
    first: date | None = None
    try:
        first = date.fromisoformat(form.first_draw) if form.first_draw else None
    except ValueError:
        first = None
    if first is None:
        form.errors.append("err_date_missing")
    elif first.weekday() not in (WEDNESDAY, SATURDAY):
        form.errors.append("err_date_not_draw_day")
        first = None
    elif not weekdays:
        weekdays = (first.weekday(),)
    if first is not None and first.weekday() not in weekdays:
        weekdays = tuple(sorted({*weekdays, first.weekday()}))

    weeks = int(form.weeks) if form.weeks.isdigit() else 0
    if not 1 <= weeks <= MAX_WEEKS:
        form.errors.append("err_weeks")

    los = form.losnummer.replace(" ", "")
    if (form.super6 or form.spiel77) and not (los.isdigit() and len(los) == 7):
        form.errors.append("err_losnummer")

    if form.errors or first is None or superzahl is None:
        return None
    return ValidTicket(tips, superzahl, first, weekdays, weeks, los or None, form.super6, form.spiel77)


def evaluate(ticket: ValidTicket) -> list[DrawOutcome]:
    return check_ticket(
        ticket.tips,
        ticket.superzahl,
        ticket.first_draw,
        ticket.weekdays,
        ticket.weeks,
        losnummer=ticket.losnummer,
        spiel77=ticket.spiel77,
        super6=ticket.super6,
    )
