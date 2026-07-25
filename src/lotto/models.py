from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class Draw:
    """Single Lotto 6aus49 draw (6 main numbers + optional superzahl)."""

    draw_date: date
    numbers: tuple[int, ...]  # exactly 6, sorted, range 1-49
    superzahl: int | None = None

    def __post_init__(self) -> None:
        if len(self.numbers) != 6:
            raise ValueError("Lotto 6aus49 requires exactly 6 main numbers")
        if any(n < 1 or n > 49 for n in self.numbers):
            raise ValueError("Main numbers must be in 1..49")
        if list(self.numbers) != sorted(self.numbers):
            raise ValueError("numbers must be sorted")
        if self.superzahl is not None and (self.superzahl < 0 or self.superzahl > 9):
            raise ValueError("superzahl must be 0..9")


@dataclass(frozen=True)
class NumberFrequency:
    number: int
    count: int
    pct: float


@dataclass(frozen=True)
class WeeklySummary:
    iso_year: int
    iso_week: int
    draw_count: int
    top_numbers: tuple[int, ...]


@dataclass(frozen=True)
class SuperzahlFrequency:
    digit: int
    count: int
    pct: float


@dataclass(frozen=True)
class SeriesMatchResult:
    numbers: tuple[int, ...]
    draw_count: int
    exact_matches: int
    exact_pct: float
    subset_matches: int
    subset_pct: float
    partial_matches: tuple[tuple[int, int, float], ...]


def validate_draws(draws: Iterable[Draw]) -> list[Draw]:
    return list(draws)
