# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SnapSorter.

This file is committed on purpose. A spec is a build input rather than a
generated artifact, so keeping it in the repo makes the exact command line
reproducible on any machine instead of depending on `pyi-makespec` defaults.
Regenerate it only if the entry point changes.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Pillow resolves its codec plugins lazily inside Image.open(), so static
# analysis cannot see them. collect_all bundles the plugins, their data
# files and the extension modules; without this the frozen app raises
# UnidentifiedImageError on perfectly valid photos.
pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")

# CustomTkinter loads its colour theme from assets/themes/*.json at import
# time via an importlib.resources lookup. Those files are invisible to
# static analysis, so a build without them dies with FileNotFoundError
# before the first window appears.
ctk_datas = collect_data_files("customtkinter")

analysis = Analysis(
    ["gui.py"],
    pathex=[],
    # These must be passed into Analysis(), not appended to analysis.datas
    # afterwards: collect_all yields 2-tuples (src, dest_dir) whereas the
    # TOC attributes hold 3-tuples (dest, src, typecode). Analysis()
    # normalises either form; EXE() only accepts the latter.
    binaries=pil_binaries,
    datas=pil_datas + ctk_datas,
    # gui.py imports these directly, but they are listed so the GUI
    # dependencies survive stripping, alongside Pillow's hidden imports.
    hiddenimports=[
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "customtkinter",
    ] + pil_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="SnapSorter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is not installed; leaving this True only prints a notice per build.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # --windowed: no console window behind the file dialogs.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
