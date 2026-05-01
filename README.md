# auto-invest

Python-driven investment automation system. The service runs as a long-lived
background worker; Claude is invoked only for judgment-heavy decision points.

Built with Spec-Driven Development (SDD) using
[spec-kit](https://github.com/github/spec-kit).

## Status

Scaffolding only. Specifications drive the implementation — see `.specify/`
and the `/speckit-*` commands inside Claude Code.

## Development

```bash
uv sync                  # install dependencies
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
```
