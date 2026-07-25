from datetime import date

import pytest

from lotto.analyze import (
    analyze_series,
    filter_draws_by_date,
    parse_number_series,
    superzahl_frequency,
)
from lotto.models import Draw


def _draw(d: str, nums: tuple[int, ...], sz: int | None = None) -> Draw:
    return Draw(draw_date=date.fromisoformat(d), numbers=nums, superzahl=sz)


def test_filter_draws_by_date():
    draws = [
        _draw("2026-01-01", (1, 2, 3, 4, 5, 6)),
        _draw("2026-06-01", (7, 8, 9, 10, 11, 12)),
    ]
    result = filter_draws_by_date(draws, start=date(2026, 5, 1), end=date(2026, 12, 31))
    assert len(result) == 1


def test_superzahl_frequency():
    draws = [
        _draw("2026-01-01", (1, 2, 3, 4, 5, 6), 3),
        _draw("2026-01-08", (7, 8, 9, 10, 11, 12), 3),
        _draw("2026-01-15", (13, 14, 15, 16, 17, 18), 7),
    ]
    stats = {s.digit: s.count for s in superzahl_frequency(draws)}
    assert stats[3] == 2
    assert stats[7] == 1


def test_analyze_series_exact_and_partial():
    draws = [
        _draw("2026-01-01", (1, 2, 3, 4, 5, 6)),
        _draw("2026-01-08", (1, 2, 3, 7, 8, 9)),
        _draw("2026-01-15", (10, 11, 12, 13, 14, 15)),
    ]
    result = analyze_series(draws, (1, 2, 3, 4, 5, 6))
    assert result.exact_matches == 1
    assert result.subset_matches == 1

    short = analyze_series(draws, (1, 2, 3))
    assert short.subset_matches == 2


def test_parse_number_series():
    assert parse_number_series("3, 12, 18, 27, 33, 45") == (3, 12, 18, 27, 33, 45)


def test_parse_number_series_rejects_invalid():
    with pytest.raises(ValueError):
        parse_number_series("1, 1, 2, 3, 4, 5")
    with pytest.raises(ValueError):
        parse_number_series("1, 2, 3, 4, 5, 6, 7")
