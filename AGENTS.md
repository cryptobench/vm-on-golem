# Repository Guidelines

This monorepo contains services and GUIs for running virtual machines on the Golem Network. Keep changes small, well-tested, and scoped to a single package when possible.

This document is the **architectural baseline** for the repo. Some sections describe a target state that existing code does not yet meet — that is expected. The baseline is forward‑looking: new code MUST follow it, and existing code converges opportunistically as files are touched. There is no separate migration project — refactoring toward the baseline is part of the work whenever you are already in a file.

## Project Structure & Module Organization

- `central-discovery-server/` (Python 3.9): centralized FastAPI discovery backend (`central_discovery`, entries: `golem-central-discovery`, legacy `golem-discovery`).
- `provider-server/` (Python 3.11): Provider API/CLI (`provider`, entry: `golem-provider`).
- `requestor-server/` (Python 3.11): Requestor API/CLI (`requestor`, entry: `golem`).
- `port-checker-server/` (Python 3.10+): FastAPI utility (`port_checker`, entry: `port-checker`).
- `requestor-web/`: Next.js + Tailwind + ethers.js web app for requestors.
- `apps/provider-desktop/`: Tauri + Vite + React desktop shell for providers.
- `packages/design-system/`: shared Golem design tokens, Tailwind preset, and theme CSS.
- `packages/ui/`: shared reusable React UI components.
- `scripts/`: Utilities (e.g., `scripts/bump_versions.py`).
- Root `Makefile`, top-level docs, and per-service `tests/`.

## Build, Test, and Development Commands

- `make install` - Install Poetry dependencies for central discovery, port-checker, provider, requestor, and shared packages.
- `make test` - Run pytest for the four core Python services.
- `make local` - Preferred full-stack local workflow on ARM macOS: starts local central discovery, provider, port-checker proxy, requestor API, and requestor web with one supervisor process. This intentionally uses local central discovery for deterministic development; Arkiv remains the canonical product default outside this local workflow.
- `make start` - Start provider CLI, port-checker proxy, and requestor web (development mode).
- Per-service: `poetry -C <svc> run pytest`, `GOLEM_ENVIRONMENT=development poetry -C provider-server run golem-provider start`, `poetry -C central-discovery-server run golem-central-discovery`, `poetry -C requestor-server run golem server api --reload`.
- Provider desktop: `npm install && npm --workspace @golem/provider-desktop run dev` for local desktop development; `npm --workspace @golem/provider-desktop run tauri:build` for installers.

## Agent Server Policy

Codex agents MUST NOT start long-running local servers or GUI processes in this repository unless the user explicitly asks for it in the current turn. This includes `make local`, `make start`, `npm run dev`, `npm start`, `next dev`, Tauri apps, Uvicorn/FastAPI servers, provider/requestor CLIs, central discovery, and port-checker. For UI work, prefer static checks, unit/type tests, code inspection, or ask the user to run the app and provide a URL/screenshot.

## Discovery Naming & Backends

Discovery is a capability, not a single server. The repo supports two provider-discovery backends:

- **Central discovery**: the centralized FastAPI backend in `central-discovery-server/`. This is the default backend for packaged/distributed app flows.
- **Arkiv**: decentralized discovery through the current `golem-base-sdk` package. This remains a supported optional backend and the canonical product name for the decentralized backend in docs, user-facing UI, config, and new code.

Naming rules:

- Use `discovery` for the capability or package area, not as a synonym for the centralized server.
- Use `central-discovery-server/`, `central_discovery`, `CentralDiscovery*`, and `central` for the centralized backend. Do not add new `discovery-server` paths or names.
- Use `Arkiv*`, `arkiv`, and `ARKIV_*` for the decentralized backend. Do not use "Golem Base" in new user-facing docs/UI/config except when referring to legacy compatibility or the current SDK/package name.
- Keep existing `golem-base`, `GOLEM_BASE_*`, `GolemBase*`, and `golem_base_*` aliases working where they are already part of persisted config, public CLI flags, tests, or SDK imports. Treat them as compatibility shims, not canonical names.
- Provider-side publishing uses publisher terminology: `DiscoveryPublisher`, `CentralDiscoveryPublisher`, `ArkivDiscoveryPublisher`, `CompositeDiscoveryPublisher`, and `DiscoveryPublishingService`.
- Requestor-side provider lookup uses backend/client terminology: `CentralDiscoveryClient`, `ArkivDiscoveryClient`, and pure DTOs in `requestor/discovery/domain.py`.
- Cross-backend selection is config-driven: providers use `DISCOVERY_BACKEND=arkiv|central|both`; requestors use `GOLEM_REQUESTOR_DISCOVERY_BACKEND=arkiv|central`; the web profile mode is `arkiv|central`.
- If a new discovery backend is added, add it as an adapter implementing the same service-facing boundary. Do not branch backend-specific RPC/HTTP logic through routes, UI components, or business services.

Documentation rules:

- `docs/discovery.md` is the source of truth for discovery architecture. Update it when backend behavior, names, or compatibility aliases change.
- Central discovery docs live under `central-discovery-server/README.md`; they must not describe central discovery as the whole discovery system.
- User-facing copy should say "Arkiv" and "central discovery"; reserve "Golem Base" for legacy alias notes or SDK/package references.

## Architecture Baseline

Each Python service is organized as a set of **vertical-slice features**. A feature owns its data, its rules, and its HTTP surface - wired together by thin layers, each with one job.

```
<service>/<package>/<feature>/
    models.py      # SQLAlchemy models - schema only, no business logic
    repo.py        # All DB access - no business rules, no HTTP, no external calls
    services.py    # Business logic - calls repos and other services; no HTTP, no ORM queries
    api.py         # FastAPI router - HTTP to DTO to service only
    domain.py      # Pydantic DTOs (commands, results, events) - no infra deps
    errors.py      # Typed domain exceptions (optional, see "Error Handling")
    __init__.py
```

**Layer direction:** API -> Services -> Repositories -> Models. No reverse dependencies. The domain layer (`domain.py`) is pure - it imports nothing from FastAPI, SQLAlchemy, aiohttp, or any other infrastructure.

**Wiring:** services and repositories are instantiated at the API layer via FastAPI `Depends`. Complex services may centralize wiring in a `wiring.py` (or `container.py`). Never instantiate a repo or service inside a route handler body — pass it in.

**Extensibility:**

- Data sources can change without altering service APIs.
- Adapters (HTTP clients, RPC clients, SSH transports) can be replaced without touching services.
- Business rules change without touching routes.

**Cross‑feature communication:** features call each other through services, never by reaching into another feature's repo or models. If two features need the same DB query, the repo that owns the table exposes it; the other feature calls the owning service or repo, never duplicates the query.

```python
# ✅ Route delegates to a service; service uses its repo
@router.post("/vms")
def create_vm(cmd: CreateVMCommand, svc: VMService = Depends(get_vm_service)) -> VMResult:
    return svc.create(cmd)

# ❌ Route does ORM work directly
@router.post("/vms")
def create_vm(payload: dict, db: Session = Depends(get_db)):
    vm = VM(**payload); db.add(vm); db.commit(); return vm
```

## File Granularity

**Tiny, focused files. No god services.**

- One service class per file. One router per resource per file.
- Soft guideline: ~200 lines per file, ~50 lines per function/method. Crossing the threshold is a signal to split, not a hard rule — but if you're routinely past it, the design is wrong.
- Split services by **capability**, not by entity. A `VMService` that does create/start/stop/snapshot/migrate/bill is a god object. Prefer `VMLifecycleService`, `VMSnapshotService`, `VMBillingService`.
- No utility grab‑bags. A `utils.py` with thirty unrelated helpers is a smell. Helpers live next to their caller until reused twice; only then are they promoted to a shared module — and that module is named for what it does, not for being a utility (`time_format.py`, not `helpers.py`).

```
# ✅ Capability-scoped
payments/
    capture_service.py
    refund_service.py
    payout_service.py

# ❌ Entity-scoped god service
payments/
    payment_service.py   # 900 lines, every payment-related verb
```

## Domain DTOs & Validation

All command and result objects crossing a service boundary are Pydantic models defined in `domain.py`. Never pass raw dicts between layers. Never accept untyped `**kwargs` at a service entry point.

```python
# domain.py
class CreateVMCommand(BaseModel):
    requestor_id: str
    cpu: int
    memory_mb: int

class VMResult(BaseModel):
    id: str
    status: VMStatus
    endpoint: str | None
```

Validation happens **at the boundary** — Pydantic does it on the way in. Inside the service, trust the types.

## Error Handling

Each service defines typed exceptions in `<package>/errors.py`. A single global FastAPI exception handler maps them to HTTP responses.

```python
# errors.py
class DomainError(Exception): ...
class NotFoundError(DomainError): ...
class ConflictError(DomainError): ...
class ValidationError(DomainError): ...
class UnauthorizedError(DomainError): ...
```

```python
# services.py
if vm is None:
    raise NotFoundError(f"vm {vm_id} not found")
```

```python
# api wiring
@app.exception_handler(NotFoundError)
def _not_found(_, exc): return JSONResponse({"detail": str(exc)}, status_code=404)
```

**Rules:**

- Never raise `HTTPException` from inside a service — that leaks HTTP into the domain. Raise a typed domain error; let the handler translate.
- Never return `None` or an empty list to signal failure. Raise.
- Refactor any `HTTPException(...)` call you encounter inside service code when you touch the file.

## DRY & KISS — Non‑Negotiable

- **No copy‑paste‑modify.** If a feature duplicates existing logic, refactor into a shared abstraction first.
- **Refactor proactively.** When you encounter a violation in code you're already changing, fix it as part of the change. Don't file a ticket.
- **Simplicity over cleverness.** If a design needs paragraph‑length comments to explain, it's too complex.

## No Silent Fallbacks — Ever

- Errors propagate. No bare `except: pass`, no `except Exception: return None`, no `try/except` that discards failures.
- Never return a default value (`None`, `[]`, `{}`, `0`) when an operation failed unexpectedly. A function that silently returns `None` on error hides bugs and surfaces them far from the root cause.
- `skipTest` is acceptable only for genuinely unsupported environments (no Docker, no GPU). It is not acceptable for "expected fixture data wasn't there." If the data should be there, assert it.
- If something fails, it must be visible — raise, or log at ERROR and re‑raise. Logging without re‑raising is allowed only when the caller cannot recover and the program must continue (e.g., a background task that must not crash the loop).

## Configuration

- Each service has a Pydantic `BaseSettings` class (typically in `config.py` or `settings.py`).
- Settings are sourced from per‑service `.env.dev` plus the unified `GOLEM_ENVIRONMENT` variable.
- No hardcoded URLs, ports, chain addresses, contract addresses, RPC endpoints, or file paths anywhere outside settings.
- Settings are read once at startup and injected — not re‑read at call time.

```python
# ✅
class Settings(BaseSettings):
    discovery_url: HttpUrl
    chain_rpc_url: HttpUrl
    db_path: Path
settings = Settings()

# ❌
DISCOVERY_URL = "http://discovery.golem.network:9001"
```

## Logging

- Use stdlib `logging` (or `structlog` where structured context is valuable). Never `print()`.
- One module‑level logger per file: `logger = logging.getLogger(__name__)`.
- Log at service/business boundaries, lifecycle transitions, background task start/stop, external calls, and failure/compensation paths. Do not log every read, poll, loop tick, or per-message event at INFO.
- Levels:
    - **ERROR** — operation cannot complete, startup fails, or an unexpected exception is re-raised. Include `exc_info=True` where useful.
    - **WARNING** — recoverable degradation, rejected/invalid external state, retryable upstream failure, or best-effort cleanup failure.
    - **INFO** — meaningful production state changes (startup/shutdown, VM lifecycle, payment submitted, advertisement published).
    - **DEBUG** — noisy diagnostics: polling, per-attempt checks, unchanged state, request/response summaries, and repeated monitor details.
- Include identifiers (vm_id, requestor_id, request_id) in log records, not just human prose.
- Never log secrets, private keys, SSH keys, auth tokens, full request bodies, or full transaction payloads.

## Database Discipline

- SQLAlchemy queries live in repos only. Service code never imports `Session` or builds `select(...)` statements.
- Avoid N+1: use `selectinload`/`joinedload` for relationships you'll touch.
- Prefer bulk operations (`bulk_save_objects`, `Session.execute(insert(...).values([...]))`) over loops.
- Migrations via Alembic, scoped per service. Never edit the DB schema by hand.
- Repos return either domain DTOs or models — pick one per repo and stay consistent. Most repos should return DTOs so the service never sees a detached SQLAlchemy instance.

## Coding Style & Naming Conventions

- Python: format with Black (88 cols), import order via isort (profile `black`), type‑hint new/changed code. 4‑space indents. Names: `snake_case` (functions), `PascalCase` (classes), `lower_snake` (modules).
- Lint/type‑check (service‑local): `poetry -C <svc> run black . && poetry -C <svc> run isort . && poetry -C <svc> run pylint <pkg> && poetry -C <svc> run mypy <pkg>`.
- JS/TS: follow existing patterns; keep modules small and pure where possible.

## Frontend Standards

### Shared UI Architecture

- Use the repo-local `golem-ui-design` skill for UI design, frontend implementation, component extraction, provider desktop UI, and requestor web UI work.
- Reusable UI components live in `packages/ui`. New UI must first look for an existing generalized component before creating one.
- `packages/ui/COMPONENTS.md` is the source-of-truth shared component inventory. Update it in the same change whenever a shared component is added, renamed, removed, or materially changes purpose.
- Feature-specific flows are not shared components, even when implemented as React components. For example, `Dialog` is a reusable component; `RentVmDialog` is a requestor feature composition that uses `Dialog`.
- If a feature needs a new visual pattern, create or extend a generalized component in `packages/ui`, then compose it inside the feature.
- Shared components must not import Next.js, Tauri, provider APIs, requestor APIs, wallet logic, generated clients, or feature/domain modules.
- Shared styling comes from `packages/design-system` tokens and the shared Tailwind preset. Do not add app-local styling tokens when a shared token should exist.
- When moving existing UI into shared packages, use `mv` for file relocation and then apply small patches for imports/package boundaries.

### requestor-web (Next.js + Tailwind)

**API boundary:** all calls to backend services go through Orval-generated clients, optionally behind thin runtime adapters in `lib/api/` (or equivalent). Components never call `fetch()` directly for backend APIs. Frontend code MUST NOT define manual request/response DTOs for backend APIs; the OpenAPI spec and Orval output are the only source of truth. UI-local state types are allowed only when they are not backend contracts. Regenerate OpenAPI and Orval (`make api-generate`, or `npm --prefix requestor-web run api:generate` after `make openapi`) before frontend changes that touch API usage, payloads, responses, or backend-facing data flow.

**Token‑based styling — mandatory:** colors, spacing, typography come from Tailwind config tokens (and any `tokens.ts` extension). No raw hex codes, no inline pixel values. Refactor hardcoded values you encounter.

#### Loading UX

- Use `Skeleton`/`TableSkeleton` for all async view loading, including `Suspense` fallbacks. Do not show generic "Loading…" strings for page content.
- Use `Spinner` only inside interactive controls for short, inline actions (Create, Connect, Copy, Stop). Never use spinners for entire sections/pages.
- When showing a spinner on a button, disable the control and keep the label present (e.g., "Creating…").
- Ensure spinner contrast on primary buttons; set `text-white` (or an appropriate contrasting color) so the spinner is visible against the button background.
- Keep spinners compact near text: typically `h-4 w-4`; use `h-3.5 w-3.5` in badges.
- Do not mix skeletons and spinners for the same content area at the same time. Prefer skeletons for content; spinners only augment action buttons.

#### UI Consistency

- Buttons: use the shared `.btn` styles for all buttons. Buttons must have a consistent height (`h-10`) whether placed horizontally or stacked vertically. Do not override button height ad‑hoc; if a special case is unavoidable, prefer utility classes that preserve `h-10`.
- Spinners in buttons: keep compact (`h-4 w-4`) and place inline before the label. Keep the label visible (e.g., "Creating…"). Ensure sufficient contrast (`text-white` on primary).
- Action groups: align horizontal button groups to the same height; vertical stacks use the same button height for all items.

### Provider Desktop (Tauri + Vite + React)

- The provider desktop frontend uses `@golem/ui` and `@golem/design-system`; it must not define provider-only copies of shared primitives.
- Renderer code never talks to disk, chain RPC, or local CLI processes directly. All such access goes through focused Tauri commands.
- Tauri commands own provider sidecar lifecycle and expose small command surfaces such as start, stop, status, and API base URL.
- Keep modules small and pure where possible.

## Testing Guidelines

- Framework: `pytest` (+ `pytest-asyncio`, `pytest-cov`).
- Location/names: `<service>/tests/` with files like `test_*.py` and functions `test_*`.
- Run locally with `make test` or `poetry -C <svc> run pytest`.

### Integration‑First Philosophy

Tests must exercise **actual production code paths**. If a test passes but production could still break, the test is worthless.

- **Wire up the real stack.** Real router → real service → real repo → real (test) DB (in‑memory or temp‑file SQLite). Never mock internal layers.
- **Stub only at true system boundaries:** Golem Network RPC, blockchain RPC, external HTTP services (port‑checker, discovery when testing a different service), SSH transports, email/SMS. Internal services and repos are never mocked.
- **>2 mocks beyond external boundaries** is a design smell — refactor the code, don't pile on mocks.
- **Never mock the thing you're testing.** API tests hit real endpoints via the FastAPI test client (full middleware → router → service → repo → DB).
- **No silent fallbacks in tests.** If a precondition fails (expected data is `None`, a list is empty, an event wasn't created), the test MUST fail with a hard assertion. Never silently skip, log a note, or return early when something expected is missing.

```python
# ✅ Real stack
svc = VMLifecycleService(repo=VMRepo(session))
result = svc.create(CreateVMCommand(requestor_id="r1", cpu=2, memory_mb=4096))
assert session.query(VM).count() == 1

# ✅ Stub at the network boundary
with patch("provider.network.rpc_client.GolemRPC.send") as send:
    send.return_value = {"ok": True}
    ...

# ❌ Mock an internal repo
@patch("provider.vm.repo.VMRepo.get")  # defeats the purpose
```

### Coverage

Backend changes ship with tests covering changed logic end‑to‑end — happy path AND every negative path for each scenario. Aim for 100% coverage on touched code.

## Commit & Pull Request Guidelines

- Commits: imperative mood, scoped prefix when helpful (e.g., `provider: fix config reload`).
- PRs: include summary, rationale, linked issues, API changes, and screenshots for GUI changes. Ensure `make test` passes.
- Releases: CI bumps versions on `main` for changed services; avoid manual version edits. For advanced use, see `scripts/bump_versions.py`.

## Security & Configuration Tips

- Do not commit secrets. Use per‑service `.env.dev` and the unified `GOLEM_ENVIRONMENT` variable.
- Use the Python version specified in each service's `pyproject.toml`. Install via Poetry to isolate environments.
