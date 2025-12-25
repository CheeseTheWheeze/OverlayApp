# Day-1 Windows Test Instructions

## Release (copy/paste only)
1. Download the latest Release zip from GitHub.
2. Unzip `GrapplingOverlayLauncher-windows.zip` to a folder (e.g., `C:\GrapplingOverlay`).
3. Double-click `GrapplingOverlayLauncher.exe`.
4. Confirm the preview window appears and closes after a short run.
5. Open `%LOCALAPPDATA%\GrapplingOverlay\outputs\pose_tracks.json` to confirm output is written.
6. Check logs:
   - `%LOCALAPPDATA%\GrapplingOverlay\logs\app.log`

## Optional: From source (developers)
> These steps are optional and only needed for development.

```cmd
cd C:\path\to\GrapplingOverlay
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m apps.windows.main --test-mode --headless
pytest
```

## Test runner
You can run the Day-1 test runner by double-clicking `test_day1.cmd` in the repo root.
