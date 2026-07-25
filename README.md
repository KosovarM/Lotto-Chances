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

# Weekly breakdown
python -m lotto.cli weekly
```

## Project brain (Obsidian)

`C:\Users\Kosov\OneDrive\Documents\ObsidianVaults\CodingProjekt1\CodingProjekt`

Start at `00 Start.md` — agents, changelog, errors.

## Agents

See [AGENTS.md](AGENTS.md). In Cursor, invoke e.g. `@cp1-research`, `@cp1-coder`.

## Status

- [x] Agent framework + vault
- [x] Analyzer skeleton with sample data
- [ ] Live fetch from official/historical source (Research → Coder)
- [ ] GitHub remote + first push

## License

MIT (learning project)
