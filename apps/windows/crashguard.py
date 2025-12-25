from __future__ import annotations

import ctypes
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_log_dirs() -> tuple[Path, Path]:
    base_log = get_base_dir() / "logs"
    local_base = os.environ.get("LOCALAPPDATA")
    if local_base:
        appdata_log = Path(local_base) / "GrapplingOverlay" / "logs"
    else:
        appdata_log = Path.home() / ".grappling_overlay" / "logs"
    return base_log, appdata_log


def ensure_dirs() -> None:
    for path in get_log_dirs():
        path.mkdir(parents=True, exist_ok=True)


def _append_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        pass


def write_fallback_log(text: str) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = f"{timestamp} {text}\n"
    for log_dir in get_log_dirs():
        _append_text(log_dir / "app.log", payload)


def init_logging() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("grappling_overlay")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    try:
        for log_dir in get_log_dirs():
            handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.info("Logging initialized")
    except Exception as exc:  # noqa: BLE001
        write_fallback_log(f"Logging initialization failed: {exc}")
    return logger


def show_error_box(title: str, message: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:  # noqa: BLE001
            write_fallback_log("Failed to show error dialog")
    print(f"{title}: {message}")


def _log_paths_text(paths: Iterable[Path]) -> str:
    return "\n".join(str(path / "app.log") for path in paths)


def guarded_main(callable_main: Callable[[list[str]], int], argv: list[str]) -> int:
    base_dir = get_base_dir()
    try:
        os.chdir(base_dir)
    except OSError as exc:
        write_fallback_log(f"Failed to change working directory: {exc}")

    logger = init_logging()
    try:
        return int(callable_main(argv))
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001
        traceback_text = traceback.format_exc()
        try:
            logger.exception("Unhandled exception: %s", exc)
        except Exception:  # noqa: BLE001
            write_fallback_log(traceback_text)
        log_locations = _log_paths_text(get_log_dirs())
        message = (
            "GrapplingOverlay hit an error and must close.\n\n"
            f"{exc}\n\n"
            "Logs were written to:\n"
            f"{log_locations}"
        )
        show_error_box("GrapplingOverlay Error", message)
        return 1
