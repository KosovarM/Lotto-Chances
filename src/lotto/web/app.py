from __future__ import annotations

from datetime import date, timedelta

from flask import Flask, render_template, request, session

from lotto.analyze import (
    analyze_series,
    filter_draws_by_date,
    frequency_table,
    parse_number_series,
    superzahl_frequency,
)
from lotto.fetch import fetch_all_draws
from lotto.web.i18n import SUPPORTED, t

PRESETS = {
    "1m": 30,
    "3m": 91,
    "6m": 183,
    "1y": 365,
    "all": None,
    "custom": "custom",
}


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "lotto-dev-key-change-in-production"

    @app.context_processor
    def inject_lang():
        lang = _resolve_lang()
        return {"lang": lang, "t": lambda k: t(lang, k)}

    app.add_template_global(_query_suffix, name="query_suffix")

    @app.route("/", methods=["GET"])
    def index():
        lang = _resolve_lang()
        if request.args.get("lang") in SUPPORTED:
            session["lang"] = request.args["lang"]
            lang = request.args["lang"]

        force_refresh = request.args.get("refresh") == "1"
        all_draws = fetch_all_draws(force_refresh=force_refresh)
        form = _default_form(all_draws) if not all_draws else _form_from_request(all_draws)
        latest_draw = all_draws[-1] if all_draws else None
        recent_draws = list(reversed(all_draws[-20:])) if all_draws else []

        if not all_draws:
            return render_template(
                "index.html",
                error=t(lang, "no_data"),
                frequencies=[],
                superzahl_stats=[],
                series_result=None,
                form=form,
                latest_draw=None,
                recent_draws=[],
            )

        if form["tab"] == "latest":
            return render_template(
                "index.html",
                form=form,
                latest_draw=latest_draw,
                recent_draws=recent_draws,
                error=None,
            )

        start, end = _date_range(form, all_draws)
        filtered = filter_draws_by_date(all_draws, start=start, end=end)

        series_result = None
        series_error = None
        if form["series"]:
            try:
                numbers = parse_number_series(form["series"])
                series_result = analyze_series(filtered, numbers)
            except ValueError:
                series_error = t(lang, "invalid_series")

        freqs = frequency_table(filtered)
        freqs_sorted = sorted(freqs, key=lambda f: (-f.count, f.number))
        sz_stats = sorted(superzahl_frequency(filtered), key=lambda s: (-s.count, s.digit))
        top_sz = next((s for s in sz_stats if s.count > 0), None)

        return render_template(
            "index.html",
            frequencies=freqs_sorted,
            superzahl_stats=sz_stats,
            top_superzahl=top_sz,
            series_result=series_result,
            series_error=series_error,
            draw_count=len(filtered),
            date_start=start,
            date_end=end,
            form=form,
            latest_draw=latest_draw,
            recent_draws=recent_draws,
            error=None if filtered else t(lang, "no_data"),
        )

    def _resolve_lang() -> str:
        if request.args.get("lang") in SUPPORTED:
            return request.args["lang"]
        return session.get("lang", "en")

    return app


def _default_form(all_draws: list) -> dict:
    end = all_draws[-1].draw_date if all_draws else date.today()
    start = end - timedelta(days=365)
    return {
        "preset": "1y",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "series": "",
        "tab": "stats",
    }


def _form_from_request(all_draws: list) -> dict:
    end_default = all_draws[-1].draw_date if all_draws else date.today()
    start_default = end_default - timedelta(days=365)
    tab = request.args.get("tab", "stats")
    if tab not in ("stats", "latest"):
        tab = "stats"
    return {
        "preset": request.args.get("preset", "1y"),
        "start": request.args.get("start", start_default.isoformat()),
        "end": request.args.get("end", end_default.isoformat()),
        "series": request.args.get("series", "").strip(),
        "tab": tab,
        "refresh": request.args.get("refresh") == "1",
    }


def _query_suffix(form: dict) -> str:
    from urllib.parse import urlencode

    params = {
        "preset": form["preset"],
        "start": form["start"],
        "end": form["end"],
        "series": form["series"],
        "tab": form["tab"],
    }
    return urlencode(params)


def _date_range(form: dict, all_draws: list) -> tuple[date | None, date | None]:
    if not all_draws:
        return None, None

    data_end = all_draws[-1].draw_date
    data_start = all_draws[0].draw_date
    preset = form["preset"]

    if preset == "all":
        return data_start, data_end
    if preset == "custom":
        start = date.fromisoformat(form["start"]) if form["start"] else data_start
        end = date.fromisoformat(form["end"]) if form["end"] else data_end
        return start, end

    days = PRESETS.get(preset, 365)
    if days is None:
        return data_start, data_end
    end = data_end
    start = end - timedelta(days=days)
    return start, end


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
