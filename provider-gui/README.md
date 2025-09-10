Provider GUI

Overview

- Electron-based GUI for the provider.
- Auto-launches when you run `golem-provider start` on systems with a GUI and Node/Electron available.
- Shows provider status, advertised resources, pricing, and running VMs. Provides a Stop button to shut the provider down.

Development

- Run locally: `npm install && npm start` inside `provider-gui/`.
- The GUI reads the provider API base URL from `PROVIDER_API_URL` (defaults to `http://127.0.0.1:7466/api/v1`).
- Start/Stop buttons in development:
  - By default, they invoke the provider via Poetry: `poetry -C provider-server run golem-provider start --daemon` and `stop`.
  - Override the launch command with `PROVIDER_CLI_CMD`, e.g.:
    - `PROVIDER_CLI_CMD="poetry -C provider-server run golem-provider" npm start`
    - `PROVIDER_CLI_CMD="golem-provider" npm start`
  - In packaged builds, the app uses the embedded CLI.

Provider Integration

- The provider exposes new endpoints used by the GUI:
  - `GET /api/v1/summary` – status, resources, pricing, and VM list
  - `POST /api/v1/admin/shutdown` – schedule a graceful shutdown

Notes

- If Node/Electron are not available, the provider runs headless (CLI/API only).
- You can force-disable the GUI with `golem-provider start --no-gui` or `GOLEM_PROVIDER_LAUNCH_GUI=0`.

Packaging and Releases

- Artifact names include OS and architecture for clarity, for example:
  - `Golem Provider-<version>-mac-arm64.dmg`
  - `Golem Provider-<version>-mac-x64.pkg`
  - `Golem Provider-<version>-win-x64-Setup.exe`
  - `Golem Provider-<version>-linux-x64.AppImage`

macOS “App is damaged” message

If you build locally without Apple code signing/notarization, macOS Gatekeeper may show:

“Golem Provider is damaged and can’t be opened. You should move it to the Bin.”

This is Gatekeeper blocking an unsigned/notarized app that has the quarantine attribute.

- Quick local workaround (for builds you trust):
  1) Remove quarantine: `xattr -dr com.apple.quarantine /path/to/Golem\ Provider-<ver>-mac-<arch>.dmg`
  2) Open the DMG and run the app (or right-click the app and choose “Open”).

- Proper fix for distribution: Code sign and notarize the macOS build.
  - CI can sign and notarize if these GitHub Secrets are set:
    - `APPLE_ID` (Apple ID email)
    - `APPLE_APP_SPECIFIC_PASSWORD` (app-specific password)
    - `APPLE_TEAM_ID` (Team ID)
    - `CSC_LINK` (base64 or URL to Developer ID Application .p12)
    - `CSC_KEY_PASSWORD` (password for the .p12)
  - The build is configured with hardened runtime and entitlements at `build/macos/entitlements.plist`.
