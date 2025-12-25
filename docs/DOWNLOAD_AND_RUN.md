# Download & Run GrapplingOverlay (Windows)

1. Download the `GrapplingOverlay-windows.zip` artifact from GitHub Actions.
2. Unzip it to a folder of your choice.
3. Double-click `GrapplingOverlay.exe`.

## What you get

The app opens a small window with:

- **Run Test Mode (synthetic)** — Generates `outputs/pose_tracks.json` and shows a PASS dialog.
- **Open Video File…** — Select a video to preview an overlay and write `outputs/pose_tracks.json`.
- **Open Logs Folder** — Opens the log directory in Explorer.

## Logs

Logs are always written to:

- `%LOCALAPPDATA%\GrapplingOverlay\logs\app.log`
- `.\logs\app.log` (next to the exe)

If the app hits a startup error, it shows a Windows error dialog and tells you where the logs are.
