# GrapplingOverlay

## Quickstart (Windows Release)
1. Download the latest Release zip.
2. Unzip `GrapplingOverlayLauncher-windows.zip`.
3. Double-click `GrapplingOverlayLauncher.exe`.

Logs are written to:
- `%LOCALAPPDATA%\GrapplingOverlay\logs\app.log`

Outputs are written to:
- `%LOCALAPPDATA%\GrapplingOverlay\outputs\pose_tracks.json`

See `docs/INSTALL_AND_UPDATE.md` for update instructions.

## Developer (optional)
> These steps are only required if you want to run from source.

```cmd
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m apps.windows.main --test-mode --headless
pytest
```

## Repository layout
- `core/` inference + smoothing + prediction (shared, no UI)
- `apps/windows/` Windows entrypoint + packaging
- `apps/api/` API wrapper stub (future)
- `adapters/` webcam/file/API input sources
- `training/` dataset registry + model versioning stubs
- `docs/` docs
- `tests/` validation tests
- `packaging/` build scripts

See `docs/DAY1_TEST_WINDOWS.md` for detailed Day-1 testing steps.
