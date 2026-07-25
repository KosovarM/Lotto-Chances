"""Fetch historical Lotto 6aus49 draws.

TODO (Research → Coder): Wire a stable public data source.
Until then, use local JSON cache via load_draws_from_json().
"""

from __future__ import annotations

from pathlib import Path

from lotto.analyze import load_draws_from_json
from lotto.models import Draw

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "draws_cache.json"


def fetch_draws_last_year() -> list[Draw]:
    """Placeholder: load cache or sample until live fetch is implemented."""
    cache = DEFAULT_CACHE
    if cache.exists():
        return load_draws_from_json(cache)
    sample = Path(__file__).resolve().parents[2] / "data" / "sample_draws.json"
    return load_draws_from_json(sample)
