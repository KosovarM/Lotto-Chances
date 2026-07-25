# CodeProject1

Learning project: **Cursor agents + Obsidian brain + GitHub + VS Code**, built around a **Lotto 6aus49** statistics tool.

## Disclaimer

This app analyzes **historical** draw frequencies. Lottery draws are independent random events. **Past results do not increase your chance of winning.** Use for learning and statistics only.

## Quick start

```powershell
cd C:\Users\Kosov\.cursor\Repositories\CodeProject1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m lotto.cli --help
pytest
```

## Commands

```powershell
# Analyze sample/cached draws (default: bundled sample data)
python -m lotto.cli analyze

# JSON output
python -m lotto.cli analyze --format json

# Web UI
python -m lotto.cli web
# Open http://127.0.0.1:5000

# Weekly breakdown
python -m lotto.cli weekly
```

## Project brain (Obsidian)

`C:\Users\Kosov\OneDrive\Documents\ObsidianVaults\CodingProjekt1\CodingProjekt`

Start at `00 Start.md` — agents, changelog, errors.

## Agents

See [AGENTS.md](AGENTS.md). In Cursor, invoke e.g. `@cp1-research`, `@cp1-coder`.

## Status — Projekt 1 abgeschlossen (2026-07-25)

- [x] Agent framework + Obsidian vault
- [x] Lotto 6aus49 CLI + Web UI (EN/DE)
- [x] Live CSV fetch + draw-day cache refresh
- [x] GitHub: https://github.com/KosovarM/CodeProject1
- [x] 19 tests passing

**Nächstes Projekt:** Lokales Serien-Streaming — siehe Obsidian [[10 Project]]

## License

MIT (learning project)
