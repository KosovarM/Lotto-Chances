"""Prize classes of Lotto 6aus49, Spiel 77 and Super 6, and checking a receipt."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from lotto.results import DrawResult, ResultUnavailable
from lotto.results import get_result as fetch_result

# (matching numbers, Superzahl matches) -> prize class
_CLASSES = {
    (6, True): 1, (6, False): 2,
    (5, True): 3, (5, False): 4,
    (4, True): 5, (4, False): 6,
    (3, True): 7, (3, False): 8,
    (2, True): 9,
}
CLASS_LABELS = {1: "6 + SZ", 2: "6", 3: "5 + SZ", 4: "5", 5: "4 + SZ",
                6: "4", 7: "3 + SZ", 8: "3", 9: "2 + SZ"}
# Class 9 pays a fixed 6 EUR; every other class is shared among its winners.
FIXED_CLASS9_EUR = 6.00
# Spiel 77 / Super 6: matching end digits of the Losnummer -> class (fixed payouts
# come from the result data; class 1 of Spiel 77 is a jackpot).
SPIEL77_CLASS = {7: 1, 6: 2, 5: 3, 4: 4, 3: 5, 2: 6, 1: 7}
SUPER6_CLASS = {6: 1, 5: 2, 4: 3, 3: 4, 2: 5, 1: 6}


def prize_class(matches: int, superzahl_hit: bool) -> int | None:
    return _CLASSES.get((matches, superzahl_hit))


def trailing_matches(ticket: str, drawn: str) -> int:
    """How many end digits agree (Spiel 77 / Super 6 rule)."""
    n = 0
    for a, b in zip(reversed(ticket), reversed(drawn)):
        if a != b:
            break
        n += 1
    return n


@dataclass
class TipOutcome:
    index: int
    numbers: tuple[int, ...]
    hits: tuple[int, ...]
    superzahl_hit: bool
    prize_class: int | None
    payout: float | None  # None: class won, but payout not published yet


@dataclass
class DrawOutcome:
    draw_date: date
    result: DrawResult | None  # None: draw pending / no data
    tips: list[TipOutcome] = field(default_factory=list)
    spiel77_class: int | None = None
    spiel77_payout: float | None = None
    super6_class: int | None = None
    super6_payout: float | None = None

    @property
    def total(self) -> float:
        parts = [t.payout for t in self.tips if t.payout]
        parts += [p for p in (self.spiel77_payout, self.super6_payout) if p]
        return round(sum(parts), 2)

    @property
    def has_unpriced_win(self) -> bool:
        return any(t.prize_class and t.payout is None for t in self.tips) or (
            (self.spiel77_class is not None and self.spiel77_payout is None)
            or (self.super6_class is not None and self.super6_payout is None)
        )


def draw_dates(first: date, weekdays: tuple[int, ...], weeks: int) -> list[date]:
    """All draws a receipt covers: ``weeks`` weeks from ``first`` on ``weekdays``."""
    days = weekdays or (first.weekday(),)
    end = first + timedelta(weeks=max(weeks, 1))
    out, day = [], first
    while day < end:
        if day.weekday() in days:
            out.append(day)
        day += timedelta(days=1)
    return out


def evaluate_draw(
    tips: list[tuple[int, tuple[int, ...]]],
    superzahl: int | None,
    result: DrawResult,
    *,
    losnummer: str | None = None,
    spiel77: bool = False,
    super6: bool = False,
) -> DrawOutcome:
    outcome = DrawOutcome(draw_date=result.draw_date, result=result)
    sz_hit = superzahl is not None and superzahl == result.superzahl
    drawn = set(result.numbers)
    for index, numbers in tips:
        hits = tuple(sorted(drawn & set(numbers)))
        cls = prize_class(len(hits), sz_hit)
        payout = result.quotes.get(cls) if cls else None
        if cls == 9 and payout is None:
            payout = FIXED_CLASS9_EUR
        outcome.tips.append(TipOutcome(index, numbers, hits, sz_hit, cls, payout))

    if losnummer and spiel77 and result.spiel77:
        cls77 = SPIEL77_CLASS.get(trailing_matches(losnummer, result.spiel77))
        outcome.spiel77_class = cls77
        outcome.spiel77_payout = result.spiel77_quotes.get(cls77) if cls77 else None
    if losnummer and super6 and result.super6:
        cls6 = SUPER6_CLASS.get(trailing_matches(losnummer[-6:], result.super6))
        outcome.super6_class = cls6
        outcome.super6_payout = result.super6_quotes.get(cls6) if cls6 else None
    return outcome


def check_ticket(
    tips: list[tuple[int, tuple[int, ...]]],
    superzahl: int | None,
    first_draw: date,
    weekdays: tuple[int, ...],
    weeks: int,
    *,
    losnummer: str | None = None,
    spiel77: bool = False,
    super6: bool = False,
    get_result: Callable[[date], DrawResult] | None = None,
) -> list[DrawOutcome]:
    """Check every draw the receipt covers. Draws without a result yet come back
    with ``result=None``."""
    fetch = get_result or fetch_result
    outcomes: list[DrawOutcome] = []
    for day in draw_dates(first_draw, weekdays, weeks):
        try:
            result = fetch(day)
        except ResultUnavailable:
            outcomes.append(DrawOutcome(draw_date=day, result=None))
            continue
        outcomes.append(
            evaluate_draw(tips, superzahl, result, losnummer=losnummer, spiel77=spiel77, super6=super6)
        )
    return outcomes
