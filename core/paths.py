from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "GrapplingOverlay"


def get_data_root() -> Path:
    local_base = os.environ.get("LOCALAPPDATA")
    if local_base:
        return Path(local_base) / APP_NAME
    return Path.home() / ".grappling_overlay"


def get_logs_dir() -> Path:
    return get_data_root() / "logs"


def get_outputs_dir() -> Path:
    return get_data_root() / "outputs"


def get_profiles_dir() -> Path:
    return get_data_root() / "profiles"


def get_models_dir() -> Path:
    return get_data_root() / "models"


def get_datasets_dir() -> Path:
    return get_data_root() / "datasets"


def get_app_root() -> Path:
    return get_data_root() / "app"


def ensure_data_dirs() -> None:
    for path in (
        get_logs_dir(),
        get_outputs_dir(),
        get_profiles_dir(),
        get_models_dir(),
        get_datasets_dir(),
        get_app_root(),
    ):
        path.mkdir(parents=True, exist_ok=True)
