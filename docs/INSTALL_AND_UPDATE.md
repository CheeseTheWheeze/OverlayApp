# GrapplingOverlay Install & Update

## First install
1. Download `GrapplingOverlay-Windows.zip` from the latest GitHub Release.
2. Unzip it anywhere (e.g., `C:\GrapplingOverlay`).
3. Double-click `GrapplingOverlayLauncher.exe`.

The launcher installs the bundled app into:
`%LOCALAPPDATA%\GrapplingOverlay\app\versions\<version>\` and sets
`%LOCALAPPDATA%\GrapplingOverlay\app\current\` as the active version.

## Updates
1. In the app, go to **Help → Check for Updates** or **Help → Update Now**.
2. The app exits and the launcher checks GitHub Releases for the latest version.
3. If a newer release is available, it downloads and switches to the new version.

If you host your own releases, set `GRAPPLING_OVERLAY_REPO=owner/repo` before
launching to point the updater at your repository.

## Persistent data
All user data lives under `%LOCALAPPDATA%\GrapplingOverlay\`:
- `logs/`
- `outputs/`
- `profiles/`
- `models/`
- `datasets/`
