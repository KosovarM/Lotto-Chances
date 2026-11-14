from __future__ import annotations

import argparse
import json
import sys
from datetime import date
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

    ticket = sub.add_parser("ticket", help="Read a receipt photo and check it")
    ticket.add_argument("photo", type=Path, help="Photo of a Lotto 6aus49 receipt")
    ticket.add_argument("--date", type=date.fromisoformat, default=None,
                        help="First draw date (YYYY-MM-DD) if it is not readable")

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

    if args.command == "ticket":
        return _ticket(args.photo, args.date)

    if args.command == "web":
        from lotto.web.app import create_app

        create_app().run(host=args.host, port=args.port, debug=False)
        return 0

    return 1


def _ticket(photo: Path, first_draw: date | None) -> int:
    from lotto.analyze import DISCLAIMER
    from lotto.ticket.prizes import CLASS_LABELS, check_ticket
    from lotto.ticket.scan import scan_image

    scan = scan_image(photo.read_bytes())
    for tip in scan.tips:
        cells = " ".join(
            f"{c.value if c.value is not None else '??':>2}{'?' if c.suspicious else ' '}" for c in tip.cells
        )
        print(f"{tip.index:2d}. {cells}")
    print(f"Superzahl: {scan.superzahl if scan.superzahl is not None else '??'}")
    if scan.warnings:
        print("Check:", ", ".join(scan.warnings))
    first = first_draw or scan.first_draw
    if first is None:
        print("Draw date not readable. Run again with --date YYYY-MM-DD.")
        return 2
    if scan.superzahl is None or any(t.numbers is None for t in scan.tips):
        print("Some values could not be read (marked ?). Use the web UI to correct them.")
        return 2
    tips = [(t.index, t.numbers) for t in scan.tips if t.numbers]
    total = 0.0
    for outcome in check_ticket(tips, scan.superzahl, first, scan.draw_weekdays, scan.weeks or 1,
                                losnummer=scan.losnummer, spiel77=bool(scan.spiel77),
                                super6=bool(scan.super6)):
        if outcome.result is None:
            print(f"{outcome.draw_date}: not drawn / published yet")
            continue
        print(f"{outcome.draw_date}: {list(outcome.result.numbers)} SZ {outcome.result.superzahl}")
        for t in outcome.tips:
            if t.prize_class:
                pay = f"{t.payout:.2f} EUR" if t.payout is not None else "payout not published yet"
                print(f"  tip {t.index}: class {t.prize_class} ({CLASS_LABELS[t.prize_class]}) -> {pay}")
        total += outcome.total
    print(f"Total: {total:.2f} EUR (no guarantee; the lottery's own check is binding)")
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
