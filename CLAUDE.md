# CLAUDE.md

Project-specific instructions for Claude Code.

## Skills

This project uses CodiHaus Claude Skills. Available skills:

| Skill | Purpose |
|-------|---------|
| `/debrief` | Create BRD and use cases from requirements |
| `/dev-scout` | Explore and document existing codebase |
| `/dev-arch` | Make architecture decisions |
| `/dev-specs` | Create implementation specifications |
| `/dev-coding` | Implement features from specs |
| `/dev-test` | Automated UI testing |
| `/dev-review` | Code review with quality checks |
| `/dev-changelog` | Document what was implemented |

### Utility Skills (called by other skills)

| Skill | Purpose |
|-------|---------|
| `/utils/diagram` | Mermaid diagram validation |
| `/utils/docs-graph` | Documentation relationship viewer |
| `/utils/gemini` | Large codebase scanning |

See `.claude/skills/_registry.md` for full documentation.

## Project Overview

{Add your project description here}

## Tech Stack

{List your technologies here}

## Development

### Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

### Testing

```bash
npm test
```

## Conventions

{Add any project-specific conventions here}
