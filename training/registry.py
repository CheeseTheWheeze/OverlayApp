from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


REGISTRY_DIR = Path("data_registry")
DATASETS_FILE = REGISTRY_DIR / "datasets.json"
MODELS_FILE = REGISTRY_DIR / "model_versions.json"


def _ensure_registry() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if not DATASETS_FILE.exists():
        DATASETS_FILE.write_text(json.dumps({"datasets": []}, indent=2), encoding="utf-8")
    if not MODELS_FILE.exists():
        MODELS_FILE.write_text(json.dumps({"models": []}, indent=2), encoding="utf-8")


def register_dataset(metadata: Dict[str, Any]) -> None:
    _ensure_registry()
    data = json.loads(DATASETS_FILE.read_text(encoding="utf-8"))
    data.setdefault("datasets", []).append(metadata)
    DATASETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_model(metadata: Dict[str, Any]) -> None:
    _ensure_registry()
    data = json.loads(MODELS_FILE.read_text(encoding="utf-8"))
    data.setdefault("models", []).append(metadata)
    MODELS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
