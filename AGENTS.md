# Repository Guidelines

This monorepo contains services and GUIs for running virtual machines on the Golem Network. Keep changes small, well‑tested, and scoped to a single package when possible.

## Project Structure & Module Organization
- `discovery-server/` (Python 3.9): FastAPI discovery service (`discovery`, entry: `golem-discovery`).
- `provider-server/` (Python 3.11): Provider API/CLI (`provider`, entries: `golem-provider`, `dev`).
- `requestor-server/` (Python 3.11): Requestor API/CLI (`requestor`, entry: `golem`).
- `port-checker-server/` (Python 3.9+): FastAPI utility (`port_checker`, entry: `port-checker`).
- `provider-gui/`, `requestor-gui/`: Electron apps (development shells for provider/requestor GUIs).
- `scripts/`: Utilities (e.g., `scripts/bump_versions.py`).
- Root `Makefile`, top-level docs, and per-service `tests/`.

## Build, Test, and Development Commands
- `make install` – Install Poetry dependencies for discovery, provider, requestor.
- `make test` – Run pytest for the three core Python services.
- `make start` – Start provider CLI, port-checker proxy, and requestor web (development mode).
- Per-service: `poetry -C <svc> run pytest`, `poetry -C provider-server run dev`, `poetry -C discovery-server run golem-discovery`, `poetry -C requestor-server run golem server api --reload`.
- GUIs: in `provider-gui/` or `requestor-gui/`: `npm install && npm start`.

## Coding Style & Naming Conventions
- Python: format with Black (88 cols), import-order via isort (profile `black`), type-hint new/changed code. 4-space indents. Names: `snake_case` (functions), `PascalCase` (classes), `lower_snake` (modules).
- Lint/type-check (service-local): `poetry -C <svc> run black . && poetry -C <svc> run isort . && poetry -C <svc> run pylint <pkg> && poetry -C <svc> run mypy <pkg>`.
- JS (Electron): follow existing patterns; keep modules small and pure where possible.
 - Web UI (requestor-web): whenever a view has asynchronous data fetching or deferred computation, render skeleton placeholders instead of raw "Loading…" text. Use `Skeleton` and `TableSkeleton` components for page-level and table views; spinners are reserved for inline button actions (e.g., submitting, connecting). Ensure fallbacks for `Suspense` also use skeletons.

### Loading UX (requestor-web)
- Use `Skeleton`/`TableSkeleton` for all async view loading, including `Suspense` fallbacks. Do not show generic "Loading…" strings for page content.
- Use `Spinner` only inside interactive controls for short, inline actions (e.g., Create, Connect, Copy, Stop). Never use spinners for entire sections/pages.
- When showing a spinner on a button, disable the control and keep the label present (e.g., "Creating…").
- Ensure spinner contrast on primary buttons; set `text-white` (or an appropriate contrasting color) so the spinner is visible against the button background.
- Keep spinners compact near text: typically `h-4 w-4`; use `h-3.5 w-3.5` in badges.
- Do not mix skeletons and spinners for the same content area at the same time. Prefer skeletons for content; spinners only augment action buttons.

## Testing Guidelines
- Framework: `pytest` (+ `pytest-asyncio`, `pytest-cov`).
- Location/names: `<service>/tests/` with files like `test_*.py` and functions `test_*`.
- Prefer fast, isolated unit tests; avoid real network/chain access—mock I/O.
- Run locally with `make test` or `poetry -C <svc> run pytest`.

## Commit & Pull Request Guidelines
- Commits: imperative mood, scoped prefix when helpful (e.g., `provider: fix config reload`).
- PRs: include summary, rationale, linked issues, API changes, and screenshots for GUI changes. Ensure `make test` passes.
- Releases: CI bumps versions on `main` for changed services; avoid manual version edits. For advanced use, see `scripts/bump_versions.py`.

## Security & Configuration Tips
- Do not commit secrets. Use per-service `.env.dev` and the unified environment var `GOLEM_ENVIRONMENT`.
- Use the Python version specified in each service’s `pyproject.toml`. Install via Poetry to isolate environments.
