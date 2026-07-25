from datetime import date

import pytest

from lotto.fetch import (
    _cache_data_is_stale,
    _last_scheduled_draw_day,
)
from lotto.models import Draw


def _draw(d: str) -> Draw:
    return Draw(draw_date=date.fromisoformat(d), numbers=(1, 2, 3, 4, 5, 6))


def test_last_scheduled_draw_day_saturday():
    assert _last_scheduled_draw_day(date(2026, 7, 25)) == date(2026, 7, 25)


def test_last_scheduled_draw_day_sunday_falls_back_to_saturday():
    assert _last_scheduled_draw_day(date(2026, 7, 26)) == date(2026, 7, 25)


def test_cache_data_is_stale_when_missing_saturday_draw():
    draws = [_draw("2026-07-22")]
    assert _cache_data_is_stale(draws, reference=date(2026, 7, 25)) is True


def test_cache_data_is_stale_when_current():
    draws = [_draw("2026-07-25")]
    assert _cache_data_is_stale(draws, reference=date(2026, 7, 25)) is False
