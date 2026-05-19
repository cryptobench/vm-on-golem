---
name: golem-ui-design
description: Use for any UI design, frontend implementation, component extraction, provider desktop UI, or requestor web UI work in this repo. Enforces generalized reusable components in packages/ui and feature-specific composition in app code.
---

# Golem UI Design

Use this skill whenever changing UI in `requestor-web`, `apps/provider-desktop`, `packages/ui`, or `packages/design-system`.

## Core Rule

Build generalized reusable components first, then compose them inside feature flows.

- Reusable components live in `packages/ui`.
- Design tokens, theme CSS, and Tailwind preset live in `packages/design-system`.
- Feature flows stay in the app or feature folder that owns the behavior.
- Move existing files with `mv` when relocating them, then patch imports and boundaries.
- `packages/ui/COMPONENTS.md` is the shared component inventory. Update it in the same change whenever a shared component is added, renamed, removed, or materially changes purpose.

## What Belongs In `packages/ui`

Shared components must be product-neutral and reusable for unrelated future features.

Good shared components:

- `Button`
- `Dialog`
- `Tabs`
- `StatusBadge`
- `Table`
- `Skeleton`
- `PageHeader`
- `FormField`
- `Stepper`
- `Toast`

Shared components must not import:

- Next.js modules
- Tauri modules
- provider APIs
- requestor APIs
- generated API clients
- wallet logic
- feature/domain modules

## What Does Not Belong In `packages/ui`

Feature compositions are not shared components. They can use shared components, but they stay with the feature that owns their behavior.

Do not move these kinds of components into `packages/ui`:

- `RentVmDialog`
- `ProviderStartPanel`
- `WalletConnectFlow`
- `VmRentalSummary`

Example: `Dialog` is reusable and belongs in `packages/ui`; `RentVmDialog` is a requestor feature composition that uses `Dialog`.

## Workflow

1. Check `packages/ui` for an existing component before creating UI.
2. If a needed visual primitive does not exist, add or extend a generalized component in `packages/ui`.
3. Compose feature-specific screens/dialogs/panels in the owning app or feature folder.
4. Use `@golem/design-system` tokens and shared Tailwind classes; avoid raw hex colors and ad hoc pixel values.
5. Update `packages/ui/COMPONENTS.md` for any shared component inventory change.
6. Verify both provider desktop and requestor web still compile when shared component APIs change.
