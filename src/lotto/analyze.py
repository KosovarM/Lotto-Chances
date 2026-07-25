from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from lotto.models import Draw, NumberFrequency, WeeklySummary

DISCLAIMER = (
    "Note: Past draw frequencies do not predict future results. "
    "Each draw is independent."
)

DEFAULT_SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_draws.json"


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


def frequency_table(draws: list[Draw]) -> list[NumberFrequency]:
    counter: Counter[int] = Counter()
    for draw in draws:
        counter.update(draw.numbers)
    total = sum(counter.values()) or 1
    return [
        NumberFrequency(number=n, count=counter.get(n, 0), pct=100.0 * counter.get(n, 0) / total)
        for n in range(1, 50)
    ]


def weekly_summaries(draws: list[Draw], top_k: int = 3) -> list[WeeklySummary]:
    by_week: dict[tuple[int, int], list[Draw]] = {}
    for draw in draws:
        iso = draw.draw_date.isocalendar()
        key = (iso.year, iso.week)
        by_week.setdefault(key, []).append(draw)

    summaries: list[WeeklySummary] = []
    for (year, week), week_draws in sorted(by_week.items()):
        counter: Counter[int] = Counter()
        for d in week_draws:
            counter.update(d.numbers)
        top = tuple(n for n, _ in counter.most_common(top_k))
        summaries.append(
            WeeklySummary(
                iso_year=year,
                iso_week=week,
                draw_count=len(week_draws),
                top_numbers=top,
            )
        )
    return summaries


def format_frequency_report(draws: list[Draw], limit: int = 10) -> str:
    freqs = frequency_table(draws)
    ranked = sorted(freqs, key=lambda f: (-f.count, f.number))
    lines = [
        f"Lotto 6aus49 analysis — {len(draws)} draw(s)",
        DISCLAIMER,
        "",
        f"Top {limit} numbers by frequency:",
    ]
    for f in ranked[:limit]:
        lines.append(f"  {f.number:2d}  count={f.count}  ({f.pct:.1f}% of number slots)")
    return "\n".join(lines)
