# Golem Design System

Shared tokens for the requestor web app and provider desktop app.

- `tokens/theme.css` defines CSS custom properties for runtime styling.
- `tokens/*.ts` exposes the same token names for Tailwind and TypeScript config.

Apps import these tokens through the `@golem/design-system` package, including
the shared Tailwind preset and `tokens/theme.css`.
