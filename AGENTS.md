# Repository Guidelines

## Project Structure & Module Organization

This repository packages the `akshare` Python library. Source code lives under `akshare/`, organized by data domain such as `stock_fundamental/`, `fund/`, `economic/`, `index/`, `spot/`, and shared helpers in `akshare/utils/`. Tests are in `tests/`; current tests use `test_*.py` files and import public package functions. Documentation lives in `docs/`, with API/data pages under `docs/data/`. Package metadata and tool configuration are in `pyproject.toml`; `setup.py` only delegates to setuptools.

## Build, Test, and Development Commands

- `python -m pip install -e ".[dev]"`: install the package in editable mode with development tools.
- `python -m pytest tests`: run the test suite.
- `ruff check akshare tests`: lint Python files using the project Ruff rules.
- `ruff format akshare tests`: format Python files with Ruff.
- `pre-commit install`: enable local hooks for formatting, linting, metadata checks, and commit-message validation.
- `python -m build`: build source and wheel distributions if `build` is installed.

## Coding Style & Naming Conventions

Use Python 3.9+ compatible code unless a dependency or config requires otherwise. Ruff is the source of truth: 4-space indentation, 88-character lines, double quotes, and standard Pyflakes/pycodestyle checks. Keep module names lowercase with underscores, matching existing files such as `fund_scale_em.py` and `stock_finance_sina.py`. Public data functions should use descriptive snake_case names and return stable pandas-friendly structures when possible.

## Testing Guidelines

Use pytest. Place tests in `tests/` and name files `test_<area>.py`; test functions should start with `test_`. Prefer small tests around public functions and utility behavior. For network-backed data interfaces, keep tests deterministic where possible and avoid brittle assertions on live market values. Run `python -m pytest tests` before opening a pull request.

## Commit & Pull Request Guidelines

History includes short maintenance commits like `Dev (#7284)` and conventional messages such as `feat: add version 1.18.62` and `fix: fix stock_market_activity_legu`. The pre-commit config enforces conventional commit messages, so prefer `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, or `chore:` prefixes.

Pull requests should describe the changed data interface or behavior, include reproduction steps for fixes, link related issues, and note any external data-source assumptions. Include tests or explain why testing is impractical for live upstream data changes.

## Security & Configuration Tips

Do not commit API keys, private credentials, cookies, or downloaded large datasets. The pre-commit hooks check for private keys and large files, but contributors remain responsible for reviewing generated artifacts before commit.
