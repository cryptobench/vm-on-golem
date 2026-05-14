# Golem Requestor Desktop

Tauri + Vite + React shell for the requestor desktop installer.

## Development

Build the frontend without starting the desktop app:

```sh
npm --workspace @golem/requestor-desktop run build
```

Run the desktop app only when explicitly needed:

```sh
npm --workspace @golem/requestor-desktop run dev
```

## Runtime Config

The desktop shell injects the same discovery and payment runtime config used by
requestor-web. Provider API traffic goes directly to provider-advertised
endpoints; the desktop app does not bundle or manage a port-checker sidecar.
