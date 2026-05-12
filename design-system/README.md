# Golem Design System

Shared tokens for the requestor web app and provider desktop GUI.

- `tokens/theme.css` defines CSS custom properties for runtime styling.
- `tokens/*.ts` exposes the same token names for Tailwind and TypeScript config.

The requestor web app imports these tokens from `requestor-web/tailwind.config.ts`
and `requestor-web/app/globals.css`. The provider GUI links the CSS token file
from `provider-gui/index.html`.
