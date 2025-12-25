from __future__ import annotations

import ctypes
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Iterable

import numpy as np


def get_base_dir() -> Path:
    if getattr(__import__("sys"), "frozen", False):
        return Path(__import__("sys").executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_local_appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "GrapplingOverlay"
    return Path.home() / ".grappling_overlay"


def setup_logging(log_dir: Path, appdata_log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    appdata_log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("grappling_overlay")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    appdata_handler = logging.FileHandler(appdata_log_dir / "app.log", encoding="utf-8")
    appdata_handler.setFormatter(formatter)
    logger.addHandler(appdata_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Logging initialized")
    return logger


def verify_and_prepare_dirs(paths: Iterable[Path], logger: logging.Logger) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            logger.info("Verified writable directory: %s", path)
        except OSError as exc:
            logger.error("Directory not writable: %s (%s)", path, exc)
            raise


def verify_required_dlls(base_dir: Path, logger: logging.Logger) -> None:
    if os.name != "nt" or not getattr(__import__("sys"), "frozen", False):
        return
    required = ["vcruntime140.dll", "vcruntime140_1.dll"]
    missing = [dll for dll in required if not (base_dir / dll).exists()]
    if not missing:
        return
    logger.warning("Missing runtime DLLs: %s", ", ".join(missing))
    resources_dir = base_dir / "resources" / "dlls"
    repaired = []
    for dll in missing:
        candidate = resources_dir / dll
        if candidate.exists():
            (base_dir / dll).write_bytes(candidate.read_bytes())
            repaired.append(dll)
    if repaired:
        logger.info("Restored DLLs: %s", ", ".join(repaired))
    still_missing = [dll for dll in required if not (base_dir / dll).exists()]
    if still_missing:
        raise RuntimeError(
            "Required runtime DLLs are missing: " + ", ".join(still_missing)
        )


def show_error(message: str, title: str = "GrapplingOverlay Error") -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    else:
        print(message)


def serialize_json(data: Dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def synthetic_frames(count: int, width: int = 640, height: int = 480):
    for idx in range(count):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        color = (0, 255, 0)
        center = (50 + idx * 5, 50 + idx * 3)
        cv2 = __import__("cv2")
        cv2.circle(frame, center, 20, color, -1)
        yield frame
