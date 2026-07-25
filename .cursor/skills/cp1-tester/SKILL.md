---
name: cp1-tester
description: Tests CodingProjekt1 features via pytest and manual checks; reports pass/fail for the Lotto analyzer. Use after Coder handoff or when validating acceptance criteria.
disable-model-invocation: true
---

# CP1 Tester Agent

Read vault spec: `Agents/05-Tester.md`.

## Commands

```powershell
cd C:\Users\Kosov\.cursor\Repositories\CodeProject1
.\.venv\Scripts\Activate.ps1
pytest -v
python -m lotto.cli analyze --help
```

## Rules

- Log failures in vault `80 Error collection.md` using Error Report template.
- Fix only test code; production fixes go back to Coder.
- Report includes exact commands and versions.
