from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# Days a Lotto 6aus49 draw takes place (Mon=0): Wednesday and Saturday.
WEDNESDAY = 2
SATURDAY = 5


@dataclass(frozen=True)
class Token:
    """One piece of text found by OCR, with its box in image pixels."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float = 1.0
    angle: float = 0.0  # slope of the box's top edge, in degrees

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class Cell:
    """One number on the receipt. ``value`` is None when it could not be read."""

    value: int | None
    confidence: float = 1.0
    suspicious: bool = False  # breaks the rules (range, order, duplicate) or low confidence


@dataclass
class Tip:
    index: int  # "1." … "12." on the receipt
    cells: list[Cell]

    @property
    def numbers(self) -> tuple[int, ...] | None:
        """The six numbers if all are read and valid, else None."""
        nums = tuple(c.value for c in self.cells if c.value is not None)
        if len(nums) != 6 or len(self.cells) != 6:
            return None
        if len(set(nums)) != 6 or any(not 1 <= n <= 49 for n in nums):
            return None
        return tuple(sorted(nums))

    @property
    def needs_review(self) -> bool:
        return self.numbers is None or any(c.suspicious for c in self.cells)


@dataclass
class TicketScan:
    """Everything read from the receipt. Fields stay None when not found."""

    tips: list[Tip] = field(default_factory=list)
    superzahl: int | None = None
    draw_weekdays: tuple[int, ...] = ()  # subset of (WEDNESDAY, SATURDAY)
    weeks: int | None = None  # "Laufzeit"
    first_draw: date | None = None
    first_draw_inferred: bool = False  # derived from the purchase time, not printed
    purchased_at: datetime | None = None
    losnummer: str | None = None
    super6: bool | None = None
    spiel77: bool | None = None
    amount_eur: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def needs_date(self) -> bool:
        return self.first_draw is None
