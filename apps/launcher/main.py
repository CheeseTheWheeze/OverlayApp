from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from core.paths import ensure_data_dirs, get_app_root, get_data_root, get_logs_dir
from core.version import __version__


APP_EXE_NAME = "GrapplingOverlay.exe"
APP_BUNDLE_DIR = "app"
APP_ZIP_NAME = "GrapplingOverlay-Windows.zip"
LAUNCHER_EXE_NAME = "GrapplingOverlayLauncher.exe"
DEFAULT_REPO = (
    os.environ.get("GRAPPLING_OVERLAY_REPO")
    or os.environ.get("GITHUB_REPOSITORY")
    or "GrapplingOverlay/OverlayApp"
)


def _show_message(title: str, message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    else:
        print(f"{title}: {message}")


def _show_error(title: str, message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    else:
        print(f"{title}: {message}")


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("grappling_overlay_launcher")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    log_path = get_logs_dir() / "launcher.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GrapplingOverlay Launcher")
    parser.add_argument("--check", action="store_true", help="Check for updates and exit")
    parser.add_argument("--update", action="store_true", help="Check for and install updates")
    parser.add_argument("--launch", action="store_true", help="Launch the app and exit")
    parser.add_argument("--self-test", action="store_true", help="Run launcher self-test and exit")
    return parser.parse_args(argv[1:])


def _get_launcher_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _copy_launcher_to_data_root(logger: logging.Logger) -> None:
    if not getattr(sys, "frozen", False):
        return
    source = Path(sys.executable).resolve()
    target = get_data_root() / LAUNCHER_EXE_NAME
    if target.exists() and target.samefile(source):
        return
    try:
        shutil.copy2(source, target)
        logger.info("Copied launcher to %s", target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to copy launcher to data root: %s", exc)


def _get_bundled_app_dir(launcher_dir: Path) -> Path | None:
    candidate = launcher_dir / APP_BUNDLE_DIR
    if candidate.exists():
        return candidate
    return None


def _validate_bundled_app(bundled_app: Path) -> None:
    exe_path = bundled_app / APP_EXE_NAME
    if not exe_path.exists():
        raise RuntimeError(f"Bundled app missing {APP_EXE_NAME} at {bundled_app}")


def _read_current_path(app_root: Path) -> Path | None:
    current_file = app_root / "current.txt"
    if not current_file.exists():
        return None
    value = current_file.read_text(encoding="utf-8").strip()
    if not value:
        return None
    return Path(value)


def _version_from_path(path: Path) -> str | None:
    parts = path.resolve().parts
    if "versions" not in parts:
        return None
    index = parts.index("versions")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _read_current_version(app_root: Path) -> str | None:
    current_path = _read_current_path(app_root)
    if current_path is None:
        return None
    return _version_from_path(current_path)


def _write_current_path(app_root: Path, target_dir: Path, logger: logging.Logger) -> None:
    current_file = app_root / "current.txt"
    temp_file = app_root / f"current.txt.{os.getpid()}.tmp"
    temp_file.write_text(str(target_dir.resolve()), encoding="utf-8")
    os.replace(temp_file, current_file)
    logger.info("Updated current pointer to %s", target_dir)


def _select_app_dir(version_root: Path) -> Path:
    if (version_root / APP_BUNDLE_DIR).exists():
        return version_root / APP_BUNDLE_DIR
    if (version_root / "GrapplingOverlay").exists():
        return version_root / "GrapplingOverlay"
    return version_root


def _cleanup_legacy_current(app_root: Path, logger: logging.Logger) -> None:
    current_dir = app_root / "current"
    if not current_dir.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = app_root / f"current_old_{timestamp}"
    try:
        if current_dir.is_dir() and not current_dir.is_symlink():
            shutil.rmtree(current_dir)
            logger.info("Removed legacy current folder: %s", current_dir)
            return
        current_dir.unlink()
        logger.info("Removed legacy current pointer: %s", current_dir)
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to remove legacy current; renaming: %s", exc)
        try:
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            current_dir.rename(backup)
            logger.info("Renamed legacy current to %s", backup)
        except Exception as rename_exc:  # noqa: BLE001
            logger.warning("Failed to rename legacy current: %s", rename_exc)


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as handle:
        handle.extractall(dest_dir)


def _resolve_packaged_app_root(staging_dir: Path) -> Path:
    bundled_app = staging_dir / APP_BUNDLE_DIR
    if bundled_app.exists():
        return bundled_app
    legacy_dir = staging_dir / "GrapplingOverlay"
    if legacy_dir.exists():
        return legacy_dir
    legacy_exe = staging_dir / APP_EXE_NAME
    if legacy_exe.exists():
        return staging_dir
    raise RuntimeError("Packaged app payload missing.")


def _install_version_from_zip(
    zip_path: Path,
    version: str,
    app_root: Path,
    logger: logging.Logger,
) -> Path:
    versions_dir = app_root / "versions"
    version_root = versions_dir / version
    if version_root.exists():
        logger.info("Version already installed: %s", version)
        return _select_app_dir(version_root)

    versions_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="grapplingoverlay_", dir=app_root))
    logger.info("Extracting %s to %s", zip_path, staging_dir)
    _extract_zip(zip_path, staging_dir)
    app_source = _resolve_packaged_app_root(staging_dir)
    version_root.mkdir(parents=True, exist_ok=True)
    if app_source.name == APP_BUNDLE_DIR:
        shutil.copytree(app_source, version_root / APP_BUNDLE_DIR)
    elif app_source.name == "GrapplingOverlay":
        shutil.copytree(app_source, version_root / "GrapplingOverlay")
    else:
        for item in staging_dir.iterdir():
            shutil.move(str(item), version_root / item.name)
    shutil.rmtree(staging_dir, ignore_errors=True)
    logger.info("Installed version %s into %s", version, version_root)
    return _select_app_dir(version_root)


def _install_version_from_bundle(
    bundled_app: Path,
    version: str,
    app_root: Path,
    logger: logging.Logger,
) -> Path:
    versions_dir = app_root / "versions"
    version_root = versions_dir / version
    if version_root.exists():
        logger.info("Version already installed: %s", version)
        return _select_app_dir(version_root)
    versions_dir.mkdir(parents=True, exist_ok=True)
    version_root.mkdir(parents=True, exist_ok=True)
    target_dir = version_root / APP_BUNDLE_DIR
    shutil.copytree(bundled_app, target_dir)
    logger.info("Installed bundled version %s into %s", version, version_root)
    return target_dir


def _find_latest_installed(app_root: Path) -> Path | None:
    versions_dir = app_root / "versions"
    if not versions_dir.exists():
        return None
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for entry in versions_dir.iterdir():
        if not entry.is_dir():
            continue
        version_key = _parse_version(entry.name)
        candidates.append((version_key, _select_app_dir(entry)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GrapplingOverlayLauncher"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _download_file(url: str, dest_path: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GrapplingOverlayLauncher"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        dest_path.write_bytes(response.read())


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_version(version: str) -> tuple[int, ...]:
    clean = version.lstrip("v").split("-")[0]
    parts = []
    for part in clean.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    return tuple(parts or [0])


def _update_from_release(
    repo: str,
    app_root: Path,
    logger: logging.Logger,
    show_ui: bool = True,
) -> bool:
    release = _fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    version_tag = release.get("tag_name", "")
    version = version_tag.lstrip("v") or version_tag
    if not version:
        raise RuntimeError("Latest release does not contain a tag name.")
    current_version = _read_current_version(app_root)
    if current_version and _parse_version(version) <= _parse_version(current_version):
        message = f"Up to date: v{current_version}"
        logger.info(message)
        if show_ui:
            _show_message("GrapplingOverlay", message)
        else:
            print(message)
        return False

    assets = release.get("assets", [])
    app_asset = next((asset for asset in assets if asset.get("name") == APP_ZIP_NAME), None)
    if not app_asset:
        raise RuntimeError(f"Release asset {APP_ZIP_NAME} not found.")

    sha256_expected = None
    latest_asset = next((asset for asset in assets if asset.get("name") == "latest.json"), None)
    if latest_asset:
        latest_data = _fetch_json(latest_asset["browser_download_url"])
        for asset in latest_data.get("assets", []):
            if asset.get("name") == APP_ZIP_NAME:
                sha256_expected = asset.get("sha256")
                break

    downloads_dir = app_root / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    download_path = downloads_dir / APP_ZIP_NAME
    logger.info("Downloading %s", app_asset["browser_download_url"])
    _download_file(app_asset["browser_download_url"], download_path)

    if sha256_expected:
        sha256_actual = _hash_file(download_path)
        if sha256_actual.lower() != sha256_expected.lower():
            raise RuntimeError("Downloaded update failed sha256 verification.")

    app_dir = _install_version_from_zip(download_path, version, app_root, logger)
    _write_current_path(app_root, app_dir, logger)
    logger.info("Update installed to version %s", version)
    message = f"Updated to v{version}. Launching now."
    if show_ui:
        _show_message("GrapplingOverlay", message)
    else:
        print(message)
    return True


def _check_for_updates(
    repo: str,
    app_root: Path,
    logger: logging.Logger,
    show_ui: bool = True,
) -> bool:
    release = _fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    version_tag = release.get("tag_name", "")
    version = version_tag.lstrip("v") or version_tag
    if not version:
        raise RuntimeError("Latest release does not contain a tag name.")

    current_version = _read_current_version(app_root)
    if current_version and _parse_version(version) <= _parse_version(current_version):
        message = f"Up to date: v{current_version}"
        logger.info(message)
        if show_ui:
            _show_message("GrapplingOverlay", message)
        else:
            print(message)
        return False

    message = f"Update available: v{version}"
    logger.info(message)
    if show_ui:
        _show_message("GrapplingOverlay", message)
    else:
        print(message)
    return True


def _launch_app(app_root: Path, logger: logging.Logger) -> None:
    current_dir = _read_current_path(app_root)
    if current_dir is None or not current_dir.exists():
        current_dir = _find_latest_installed(app_root)
    if current_dir is None or not current_dir.exists():
        raise RuntimeError("No installed app version found.")
    exe_path = current_dir / APP_EXE_NAME
    if not exe_path.exists():
        raise RuntimeError(f"Unable to find {APP_EXE_NAME} in {current_dir}")
    logger.info("Launching app: %s", exe_path)
    subprocess.Popen([str(exe_path)], close_fds=True)


def _ensure_app_installed(
    bundle_root: Path,
    app_root: Path,
    logger: logging.Logger,
) -> None:
    bundled_app = _get_bundled_app_dir(bundle_root)
    if bundled_app is None:
        raise RuntimeError("Bundled app folder missing. Reinstall the launcher package.")
    _validate_bundled_app(bundled_app)

    _cleanup_legacy_current(app_root, logger)
    current_path = _read_current_path(app_root)
    if current_path and current_path.exists():
        exe_path = current_path / APP_EXE_NAME
        if exe_path.exists():
            return
        logger.warning("Current pointer invalid; reinstalling from bundled app.")

    app_dir = _install_version_from_bundle(bundled_app, __version__, app_root, logger)
    _write_current_path(app_root, app_dir, logger)


def launcher_self_test(
    bundle_root: Path,
    logger: logging.Logger,
) -> int:
    logger.info("Running launcher self-test.")
    try:
        if not bundle_root.exists():
            raise RuntimeError(f"Bundle root does not exist: {bundle_root}")
        bundled_app = bundle_root / APP_BUNDLE_DIR / APP_EXE_NAME
        if not bundled_app.exists():
            raise RuntimeError(f"Bundled app exe missing: {bundled_app}")

        data_root = get_data_root()
        data_root.mkdir(parents=True, exist_ok=True)
        test_path = data_root / "launcher_write_test.tmp"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)

        logger.info("Launcher self-test completed successfully.")
        print("Launcher self-test passed.")
        return 0
    except Exception as exc:  # noqa: BLE001
        traceback_text = traceback.format_exc()
        log_path = get_logs_dir() / "launcher.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\nLauncher self-test failed:\n")
                handle.write(traceback_text)
                handle.write("\n")
        except Exception:  # noqa: BLE001
            pass
        logger.exception("Launcher self-test failed: %s", exc)
        print(f"Launcher self-test failed: {exc}")
        print(traceback_text)
        return 1


def main(argv: list[str]) -> int:
    ensure_data_dirs()
    logger = _setup_logger()
    logger.info("Launcher starting (bundle v%s)", __version__)

    args = _parse_args(argv)
    bundle_root = _get_launcher_dir()
    app_root = get_app_root()
    app_root.mkdir(parents=True, exist_ok=True)

    _copy_launcher_to_data_root(logger)

    if args.self_test:
        return launcher_self_test(bundle_root, logger)

    _ensure_app_installed(bundle_root, app_root, logger)

    if args.check or args.update or args.launch:
        repo = DEFAULT_REPO
        if (args.check or args.update) and not repo:
            _show_error(
                "GrapplingOverlay",
                "Update repo not configured. Set GRAPPLING_OVERLAY_REPO=owner/repo.",
            )
            return 1
        if args.check:
            try:
                _check_for_updates(repo, app_root, logger, show_ui=True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Update check failed: %s", exc)
                _show_error(
                    "GrapplingOverlay Update Failed",
                    f"{exc}\n\nSee launcher.log for details.",
                )
                return 1
        if args.update:
            try:
                _update_from_release(repo, app_root, logger, show_ui=False)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Update failed: %s", exc)
                print(f"Update failed: {exc}")
                return 1
        if args.launch:
            try:
                _launch_app(app_root, logger)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to launch app: %s", exc)
                print(f"Failed to launch app: {exc}")
                return 1
        return 0

    def open_folder(path: Path, label: str) -> None:
        logger.info("Opening %s folder: %s", label, path)
        if os.name == "nt":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def launch_gui() -> None:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.title("GrapplingOverlay Launcher")
        root.geometry("360x280")
        root.resizable(False, False)

        status_var = tk.StringVar(value=f"Bundle v{__version__}")
        status_label = tk.Label(root, textvariable=status_var, font=("Segoe UI", 10))
        status_label.pack(pady=8)

        def on_launch():
            try:
                _launch_app(app_root, logger)
                root.destroy()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to launch app: %s", exc)
                _show_error("GrapplingOverlay", f"Failed to launch app:\n{exc}")

        def on_check_updates():
            repo = DEFAULT_REPO
            if not repo:
                _show_error(
                    "GrapplingOverlay",
                    "Update repo not configured. Set GRAPPLING_OVERLAY_REPO=owner/repo.",
                )
                return
            try:
                _check_for_updates(repo, app_root, logger, show_ui=True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Update check failed: %s", exc)
                _show_error(
                    "GrapplingOverlay Update Failed",
                    f"{exc}\n\nSee launcher.log for details.",
                )

        def on_update_now():
            repo = DEFAULT_REPO
            if not repo:
                _show_error(
                    "GrapplingOverlay",
                    "Update repo not configured. Set GRAPPLING_OVERLAY_REPO=owner/repo.",
                )
                return
            try:
                updated = _update_from_release(repo, app_root, logger, show_ui=True)
                if updated:
                    _launch_app(app_root, logger)
                    root.destroy()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Update failed: %s", exc)
                _show_error(
                    "GrapplingOverlay Update Failed",
                    f"{exc}\n\nSee launcher.log for details.",
                )

        def on_open_data():
            try:
                open_folder(get_data_root(), "data")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to open data folder: %s", exc)
                messagebox.showerror("Open Data Error", f"Unable to open data folder:\n{exc}")

        def on_open_logs():
            try:
                open_folder(get_logs_dir(), "logs")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to open logs folder: %s", exc)
                messagebox.showerror("Open Logs Error", f"Unable to open logs folder:\n{exc}")

        button_frame = tk.Frame(root)
        button_frame.pack(padx=16, pady=6, fill="x")

        tk.Button(button_frame, text="Launch App", command=on_launch).pack(fill="x", pady=4)
        tk.Button(button_frame, text="Check for Updates", command=on_check_updates).pack(
            fill="x", pady=4
        )
        tk.Button(button_frame, text="Update Now", command=on_update_now).pack(
            fill="x", pady=4
        )
        tk.Button(button_frame, text="Open Data Folder", command=on_open_data).pack(
            fill="x", pady=4
        )
        tk.Button(button_frame, text="Open Logs", command=on_open_logs).pack(fill="x", pady=4)

        root.mainloop()

    launch_gui()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception:  # noqa: BLE001
        log_path = get_logs_dir() / "launcher.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\nUnhandled exception:\n")
            handle.write(traceback.format_exc())
            handle.write("\n")
        _show_error(
            "GrapplingOverlay Launcher Error",
            f"An unexpected error occurred. Details were written to:\n{log_path}",
        )
        sys.exit(1)
