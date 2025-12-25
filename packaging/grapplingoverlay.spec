# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(__file__).resolve().parents[1]
entrypoint = project_root / "apps" / "windows" / "main.py"

cv2_datas, cv2_binaries, cv2_hidden = collect_all("cv2")


def _find_vcruntime() -> list[tuple[str, str]]:
    candidates = ["vcruntime140.dll", "vcruntime140_1.dll"]
    search_dirs = [
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "DLLs",
        Path(sys.base_prefix) / "Library" / "bin",
    ]
    found = []
    for base in search_dirs:
        for name in candidates:
            path = base / name
            if path.exists():
                found.append((str(path), "."))
    return found


a = Analysis(
    [str(entrypoint)],
    pathex=[str(project_root)],
    binaries=cv2_binaries + _find_vcruntime(),
    datas=cv2_datas,
    hiddenimports=cv2_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GrapplingOverlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="GrapplingOverlay",
)
