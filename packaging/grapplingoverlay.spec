# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project_root = Path.cwd()
entrypoint = project_root / "apps" / "windows" / "main.py"

cv2_datas, cv2_binaries, cv2_hidden = collect_all("cv2")

a = Analysis(
    [str(entrypoint)],
    pathex=[str(project_root)],
    binaries=cv2_binaries,
    datas=cv2_datas,
    hiddenimports=cv2_hidden,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GrapplingOverlay",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GrapplingOverlay",
)
