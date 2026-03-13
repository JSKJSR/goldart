## 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity
### 2. Subagent Strategy
- Use subagents liberally to keep main contect window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problens, throw more compute at it via subagents
- One tack per subagent for focused execution
### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Create the `tasks/` directory if it doesn't exist
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project
### 4. Verification Before Done
- Never mark a task complete without proving it works
- Test behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests (`pytest`), check logs, demonstrate correctness
### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it
### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how
## Task Management
## Core Principles
- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes.
- **Minimal impact**: Touch only what's necessary 
- **No Shortcuts**: No "quick fixes" or workarounds. Fix it right the first time.

## Before completing any task, run these checks:
- Scan for hardcoded secrets, API keys, passwords
- Check for SQL injection, shell injection, path traversal
- Verify all user inputs are validated
- Run the test suite: `pytest`
- Lint code: `ruff check .`

## commands
- `python app.py` — Start development server
- `pytest` — Run unit tests
- `ruff check .` — Lint all files

## Documentation
- always document the changes in the documentation files
- keep the language simple so it can be used by other developers