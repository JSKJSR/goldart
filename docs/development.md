# Developer Guide

## Technical Stack
- **Python**: 3.9+
- **Framework**: Flask 3
- **Database**: PostgreSQL (Supabase)
- **Data Source**: Twelve Data API

## Development Workflow
1. **Plan**: For any non-trivial task, enter Plan Mode.
2. **Implement**: Keep logic in `core/` and keep routes thin.
3. **Test**: Run `pytest` before submitting any changes.
4. **Lint**: Run `ruff check .` to ensure code style consistency.
5. **Document**: Update `CHANGELOG.md` and any relevant documentation.

## Testing
We use `pytest`. All tests are located in the `tests/` directory.
```bash
pytest
```

## Linting
We use `ruff`.
```bash
ruff check .
```
