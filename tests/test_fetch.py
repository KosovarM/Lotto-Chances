from datetime import date, timedelta
from pathlib import Path

import pytest

from lotto.fetch import filter_last_year, load_draws_from_csv
from lotto.models import Draw


def test_load_csv_sample(tmp_path: Path):
    csv_text = """date,n1,n2,n3,n4,n5,n6,superzahl
2026-01-01,1,2,3,4,5,6,7
2026-01-08,7,8,9,10,11,12,
"""
    path = tmp_path / "draws.csv"
    path.write_text(csv_text, encoding="utf-8")
    draws = load_draws_from_csv(path)
    assert len(draws) == 2
    assert draws[0].numbers == (1, 2, 3, 4, 5, 6)
    assert draws[0].superzahl == 7
    assert draws[1].superzahl is None


def test_filter_last_year():
    today = date(2026, 7, 25)
    draws = [
        Draw(draw_date=date(2025, 1, 1), numbers=(1, 2, 3, 4, 5, 6)),
        Draw(draw_date=date(2026, 1, 1), numbers=(7, 8, 9, 10, 11, 12)),
        Draw(draw_date=date(2026, 7, 1), numbers=(13, 14, 15, 16, 17, 18)),
    ]
    filtered = filter_last_year(draws, reference=today)
    assert len(filtered) == 2
    assert filtered[0].draw_date == date(2026, 1, 1)
