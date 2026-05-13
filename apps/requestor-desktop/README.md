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

## Sidecar

The app bundles `golem-port-checker` as a Tauri sidecar. Stage the sidecar
before running `cargo check` or `tauri build`:

```sh
poetry -C port-checker-server run python ../scripts/build_port_checker_cli.py --onefile
```

The staged binary lives under `src-tauri/binaries/` and is intentionally ignored
by git.
