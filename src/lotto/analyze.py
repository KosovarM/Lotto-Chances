from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from lotto.models import (
    Draw,
    NumberFrequency,
    SeriesMatchResult,
    SuperzahlFrequency,
    WeeklySummary,
)

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


def filter_draws_by_date(
    draws: list[Draw],
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[Draw]:
    result = draws
    if start is not None:
        result = [d for d in result if d.draw_date >= start]
    if end is not None:
        result = [d for d in result if d.draw_date <= end]
    return result


def superzahl_frequency(draws: list[Draw]) -> list[SuperzahlFrequency]:
    counter: Counter[int] = Counter()
    for draw in draws:
        if draw.superzahl is not None:
            counter[draw.superzahl] += 1
    total = sum(counter.values()) or 1
    return [
        SuperzahlFrequency(
            digit=d,
            count=counter.get(d, 0),
            pct=100.0 * counter.get(d, 0) / total,
        )
        for d in range(10)
    ]


def parse_number_series(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return ()
    numbers = tuple(sorted({int(p) for p in parts}))
    if len(numbers) != len(parts):
        raise ValueError("duplicate numbers")
    if any(n < 1 or n > 49 for n in numbers):
        raise ValueError("numbers must be between 1 and 49")
    if len(numbers) > 6:
        raise ValueError("at most 6 numbers allowed")
    return numbers


def analyze_series(draws: list[Draw], numbers: tuple[int, ...]) -> SeriesMatchResult:
    if not numbers:
        raise ValueError("at least one number required")

    draw_count = len(draws)
    exact = 0
    subset = 0
    partial_counter: Counter[int] = Counter()
    target = set(numbers)

    for draw in draws:
        matched = len(target & set(draw.numbers))
        partial_counter[matched] += 1
        if matched == len(numbers):
            subset += 1
        if len(numbers) == 6 and draw.numbers == numbers:
            exact += 1

    denom = draw_count or 1
    partial = tuple(
        (k, partial_counter[k], 100.0 * partial_counter[k] / denom)
        for k in sorted(partial_counter)
    )
    return SeriesMatchResult(
        numbers=numbers,
        draw_count=draw_count,
        exact_matches=exact,
        exact_pct=100.0 * exact / denom,
        subset_matches=subset,
        subset_pct=100.0 * subset / denom,
        partial_matches=partial,
    )


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
