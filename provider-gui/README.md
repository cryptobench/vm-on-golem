Provider GUI

Overview

- Electron-based GUI for the provider.
- Auto-launches when you run `golem-provider start` on systems with a GUI and Node/Electron available.
- Shows provider status, advertised resources, pricing, and running VMs. Provides a Stop button to shut the provider down.

Development

- Run locally: `npm install && npm start` inside `provider-gui/`.
- The GUI reads the provider API base URL from `PROVIDER_API_URL` (defaults to `http://127.0.0.1:7466/api/v1`).

Provider Integration

- The provider exposes new endpoints used by the GUI:
  - `GET /api/v1/summary` – status, resources, pricing, and VM list
  - `POST /api/v1/admin/shutdown` – schedule a graceful shutdown

Notes

- If Node/Electron are not available, the provider runs headless (CLI/API only).
- You can force-disable the GUI with `golem-provider start --no-gui` or `GOLEM_PROVIDER_LAUNCH_GUI=0`.
