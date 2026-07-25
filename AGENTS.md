# Agents — CodingProjekt1

This repo implements the agent workflow documented in the Obsidian vault (`30 Agenten.md`).

## Roles

| Skill | Role | Code? |
|-------|------|-------|
| *(this chat)* | Project Leader | Orchestration only |
| `@cp1-research` | Research | No |
| `@cp1-architect` | Architect | Specs only |
| `@cp1-coder` | Coder | Yes |
| `@cp1-tester` | Tester | Tests only |
| `@cp1-critic` | Critic | No |
| `@cp1-documenter` | Documenter | Docs only |

## Typical flow

```
Leader → Research? → Architect? → Coder → Tester → Critic → Documenter
```

## Tips

- **New chat per agent** keeps context clean for long tasks.
- Research outputs go to vault `70 Documentation/Research/`.
- Never skip the lottery disclaimer in user-facing features.

## Cursor locations

- Rules: `.cursor/rules/`
- Skills: `.cursor/skills/cp1-*/SKILL.md`
