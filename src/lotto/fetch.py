from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from lotto.models import Draw

CSV_URL = (
    "https://raw.githubusercontent.com/daowa89/lottery-archive/"
    "main/de/lotto_6aus49/results.csv"
)
JSON_FALLBACK = (
    "https://johannesfriedrich.github.io/LottoNumberArchive/"
    "Lottonumbers_tidy_complete.json"
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CSV_CACHE = DATA_DIR / "draws_cache.csv"
JSON_CACHE = DATA_DIR / "draws_cache.json"
SAMPLE_JSON = DATA_DIR / "sample_draws.json"
CACHE_MAX_AGE_DAYS = 7


def _parse_superzahl(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return int(text)


def load_draws_from_csv(path: Path) -> list[Draw]:
    draws: list[Draw] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            numbers = tuple(
                sorted(int(row[f"n{i}"]) for i in range(1, 7))
            )
            draws.append(
                Draw(
                    draw_date=date.fromisoformat(row["date"].strip()),
                    numbers=numbers,
                    superzahl=_parse_superzahl(row.get("superzahl")),
                )
            )
    return sorted(draws, key=lambda d: d.draw_date)


def load_draws_from_json(path: Path) -> list[Draw]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    draws: list[Draw] = []
    for item in raw:
        draws.append(
            Draw(
                draw_date=date.fromisoformat(item["draw_date"]),
                numbers=tuple(sorted(item["numbers"])),
                superzahl=item.get("superzahl"),
            )
        )
    return sorted(draws, key=lambda d: d.draw_date)


def filter_last_year(draws: list[Draw], *, reference: date | None = None) -> list[Draw]:
    end = reference or date.today()
    start = end - timedelta(days=365)
    return [d for d in draws if start <= d.draw_date <= end]


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = date.today() - date.fromtimestamp(path.stat().st_mtime)
    return age.days < CACHE_MAX_AGE_DAYS


def download_csv(url: str = CSV_URL, dest: Path = CSV_CACHE) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response:
        dest.write_bytes(response.read())
    return dest


def fetch_draws_last_year(*, force_refresh: bool = False) -> list[Draw]:
    """Load draws from cache or remote CSV; return last 365 days."""
    if force_refresh or not _cache_is_fresh(CSV_CACHE):
        try:
            download_csv()
        except (URLError, OSError, ValueError):
            if CSV_CACHE.exists():
                pass
            elif JSON_CACHE.exists():
                return filter_last_year(load_draws_from_json(JSON_CACHE))
            elif SAMPLE_JSON.exists():
                return filter_last_year(load_draws_from_json(SAMPLE_JSON))
            raise

    if CSV_CACHE.exists():
        return filter_last_year(load_draws_from_csv(CSV_CACHE))

    if JSON_CACHE.exists():
        return filter_last_year(load_draws_from_json(JSON_CACHE))

    return filter_last_year(load_draws_from_json(SAMPLE_JSON))
