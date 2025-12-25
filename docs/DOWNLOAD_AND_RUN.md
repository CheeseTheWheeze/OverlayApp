# Download & Run GrapplingOverlay (Windows)

1. Download `GrapplingOverlayLauncher-windows.zip` from the latest GitHub Release.
2. Unzip it to a folder of your choice.
3. Double-click `GrapplingOverlayLauncher.exe`.

## What you get

The app opens a small window with:

- **Run Test Mode (synthetic)** — Generates `pose_tracks.json` and shows a PASS dialog.
- **Open Video File…** — Select a video to preview an overlay and write `pose_tracks.json`.
- **Open Logs Folder** — Opens the log directory in Explorer.
- **Open Outputs Folder** — Opens the outputs directory in Explorer.
- **Open Data Folder** — Opens the persistent data root in Explorer.

## Logs

Logs are always written to `%LOCALAPPDATA%\GrapplingOverlay\logs\app.log`.

Outputs are written to `%LOCALAPPDATA%\GrapplingOverlay\outputs\pose_tracks.json`.

If the app hits a startup error, it shows a Windows error dialog and tells you where the logs are.
