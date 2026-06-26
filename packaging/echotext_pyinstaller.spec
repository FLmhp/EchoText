# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from kivy.tools.packaging.pyinstaller_hooks import get_deps_all, hookspath, runtime_hooks

block_cipher = None

kivy_deps = get_deps_all()
project_root = Path.cwd()
branding_dir = project_root / "assets" / "branding"

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=kivy_deps["binaries"],
    datas=[
        (str(branding_dir / "EchoText.ico"), "assets/branding"),
        (str(branding_dir / "echotext-icon-256.png"), "assets/branding"),
        (str(branding_dir / "echotext-icon-1024.png"), "assets/branding"),
    ],
    hiddenimports=kivy_deps["hiddenimports"],
    hookspath=hookspath(),
    hooksconfig={},
    runtime_hooks=runtime_hooks(),
    excludes=kivy_deps["excludes"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EchoText",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(branding_dir / "EchoText.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EchoText",
)
