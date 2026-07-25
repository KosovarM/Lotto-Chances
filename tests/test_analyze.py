from datetime import date

import pytest

from lotto.analyze import frequency_table, load_draws_from_json, weekly_summaries
from lotto.models import Draw


def test_draw_validates_sorted_numbers():
    with pytest.raises(ValueError):
        Draw(draw_date=date(2025, 1, 1), numbers=(3, 2, 4, 5, 6, 7))


def test_frequency_table_counts():
    draws = [
        Draw(draw_date=date(2025, 1, 1), numbers=(1, 2, 3, 4, 5, 6)),
        Draw(draw_date=date(2025, 1, 8), numbers=(1, 2, 3, 7, 8, 9)),
    ]
    freqs = {f.number: f.count for f in frequency_table(draws)}
    assert freqs[1] == 2
    assert freqs[6] == 1
    assert freqs[49] == 0


def test_load_sample_json(sample_path):
    draws = load_draws_from_json(sample_path)
    assert len(draws) >= 10
    assert all(len(d.numbers) == 6 for d in draws)


def test_weekly_summaries_group_by_iso_week(sample_path):
    draws = load_draws_from_json(sample_path)
    summaries = weekly_summaries(draws)
    assert summaries
    assert all(s.draw_count >= 1 for s in summaries)


@pytest.fixture
def sample_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "data" / "sample_draws.json"
