# Lotto Chances

Historical statistics for the German **Lotto 6aus49**, as a command-line tool and a bilingual (EN/DE) web UI.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.x-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-pytest-yellow)

Lotto Chances (formerly *CodeProject1*) downloads the full Lotto 6aus49 draw history, caches it locally, and shows how often each number and Superzahl appeared within a time range you choose. You can also check how often your own series of numbers came up in past draws. It started as a learning project, built with a Cursor-agent workflow and an Obsidian vault as the "project brain" (see [AGENTS.md](AGENTS.md)).

> [!IMPORTANT]
> **Past results do not change your odds.** Each draw is an independent random event. This tool describes what *happened*. It does not predict what *will* happen. See [docs/DISCLAIMER.md](docs/DISCLAIMER.md).

## Features

**Statistics**
- Frequency table for main numbers 1–49 (count and share of number slots).
- Superzahl frequency (0–9) and the most common Superzahl in the range.
- Per-week summary (ISO weeks) with the top numbers of each week.
- Number-series check: enter 1–6 numbers and see exact 6-number matches, how often all of your numbers were drawn together, and a breakdown of partial matches.

**Web UI** (Flask)
- **Statistics** tab with timeframe presets (1, 3, 6 or 12 months, all data) or a custom date range.
- **Latest draw** tab with the most recent draw, its Superzahl, and the last 20 draws.
- English/German language switch (remembered in the session).
- "Refresh data" button that forces a new download.
- Disclaimer shown on every page.

**CLI**
- `analyze`: top-10 numbers by frequency, as text or JSON.
- `weekly`: per-ISO-week summary.
- `web`: starts the web UI with a configurable host and port.
- `--data` accepts your own CSV or JSON draw file.

**Data handling**
- Downloads the complete draw history (1955 to today) as CSV from a public archive.
- Local cache in `data/`, refreshed when it is older than 7 days or is missing the most recent Wednesday/Saturday draw.
- Works offline: if the download fails, it uses the existing cache and then the bundled sample data.

## Tech stack

- Python 3.11+
- [Flask](https://flask.palletsprojects.com/) 3 with Jinja2 templates and plain CSS (no JavaScript framework)
- Python standard library for the CLI (`argparse`), the HTTP download (`urllib`) and CSV/JSON parsing
- [pytest](https://pytest.org/) for tests
- setuptools packaging (`src/` layout)

## Getting started

**Requirements:** Python 3.11 or newer.

```bash
git clone https://github.com/KosovarM/Lotto-Chances.git
cd Lotto-Chances
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install the package with its dev dependencies and run the tests:

```bash
pip install -e ".[dev]"
pytest
```

`pip install -r requirements.txt` also works if you only want the dependencies. In that case, run the CLI with `src/` on `PYTHONPATH`.

## Usage

The first run downloads the draw history into `data/draws_cache.csv`. By default, CLI commands analyze the **last 365 days**.

```bash
# Top-10 number frequencies (text)
lotto analyze            # or: python -m lotto.cli analyze

# Full frequency table as JSON
lotto analyze --format json

# Analyze your own file (CSV: date,n1..n6,superzahl; or JSON like data/sample_draws.json)
lotto analyze --data data/sample_draws.json

# Per-week summary
lotto weekly

# Web UI at http://127.0.0.1:5000
lotto web
lotto web --host 0.0.0.0 --port 8080
```

`lotto-web` is a shortcut that starts the web UI on `127.0.0.1:5000`.

In the web UI, use `?lang=de` or the language switch for German, and **Refresh data** to force a new download.

## Configuration

There are no environment variables. The CLI flags above (`--data`, `--format`, `--host`, `--port`) are the only settings. The cache lifetime (7 days) and the data source URLs are constants in `src/lotto/fetch.py`.

> [!NOTE]
> The web UI is meant for local use. It runs Flask's built-in server with a hard-coded session key, so don't expose it to the internet as it is.

## Project structure

```text
Lotto-Chances/
├── src/lotto/
│   ├── cli.py          # argparse CLI: analyze, weekly, web
│   ├── analyze.py      # frequencies, Superzahl stats, weekly summaries, series check
│   ├── fetch.py        # CSV download, cache freshness, offline fallback
│   ├── models.py       # Draw and result dataclasses (with validation)
│   └── web/            # Flask app, EN/DE strings, templates, CSS
├── data/
│   └── sample_draws.json   # bundled sample (the download cache is git-ignored)
├── docs/               # disclaimer and data-source notes
├── tests/              # pytest suite
├── AGENTS.md           # Cursor agent roles used during development
└── pyproject.toml
```

## Documentation

- [docs/DISCLAIMER.md](docs/DISCLAIMER.md): what the statistics mean and what they don't
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md): where the draw data comes from, its format and licensing notes
- [AGENTS.md](AGENTS.md): the agent workflow used to build the project

## License

MIT. This is a learning project, and the draw data belongs to its upstream sources (see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)).
