# Golem Provider Desktop

Tauri + Vite + React shell for the provider desktop installer.

## Provider Data Catalogue

The designer-facing provider data catalogue lives in
[`PROVIDER_DATA_CATALOGUE.md`](./PROVIDER_DATA_CATALOGUE.md). It lists the data
the provider can expose to desktop screens using realistic key/value examples.

## Development

Build the frontend without starting the desktop app:

```sh
npm --workspace @golem/provider-desktop run build
```

Run the desktop app only when explicitly needed:

```sh
npm --workspace @golem/provider-desktop run dev
```

## Sidecar

The app bundles `golem-provider` as a Tauri sidecar. Stage the sidecar before
running `cargo check` or `tauri build`:

```sh
poetry -C provider-server run python ../scripts/build_provider_cli.py --onefile
```

The staged binary lives under `src-tauri/binaries/` and is intentionally ignored
by git.
