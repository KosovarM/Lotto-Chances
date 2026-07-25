from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lotto.analyze import (
    DEFAULT_SAMPLE,
    format_frequency_report,
    load_draws_from_json,
    weekly_summaries,
)
from lotto.fetch import fetch_draws_last_year, load_draws_from_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lotto",
        description="Lotto 6aus49 historical statistics (learning project)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Number frequency analysis")
    analyze.add_argument(
        "--data",
        type=Path,
        default=None,
        help="JSON or CSV file with draws (default: fetch/cache/sample)",
    )
    analyze.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    weekly = sub.add_parser("weekly", help="Per-week summary")
    weekly.add_argument("--data", type=Path, default=None)

    web = sub.add_parser("web", help="Start web UI")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)

    return parser


def _load_draws(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_draws_from_csv(path)
    return load_draws_from_json(path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "analyze":
        draws = _load_draws(args.data) if args.data else fetch_draws_last_year()
        if args.format == "json":
            from lotto.analyze import frequency_table

            payload = {
                "draw_count": len(draws),
                "frequencies": [
                    {"number": f.number, "count": f.count, "pct": round(f.pct, 2)}
                    for f in frequency_table(draws)
                ],
            }
            print(json.dumps(payload, indent=2))
        else:
            print(format_frequency_report(draws))
        return 0

    if args.command == "weekly":
        draws = _load_draws(args.data) if args.data else fetch_draws_last_year()
        for s in weekly_summaries(draws):
            print(
                f"ISO {s.iso_year}-W{s.iso_week:02d}: "
                f"{s.draw_count} draw(s), top={list(s.top_numbers)}"
            )
        return 0

    if args.command == "web":
        from lotto.web.app import create_app

        create_app().run(host=args.host, port=args.port, debug=False)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
