# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Op^3 Studio -- the standalone Windows
executable of the op3_viz web application.

Build:
    pyinstaller op3_studio.spec

Output:
    dist/op3_studio/op3_studio.exe  (plus bundled Python runtime + libs)

Run:
    dist/op3_studio/op3_studio.exe
    # then open http://127.0.0.1:8050/ in a browser

Notes
-----
1. This is a *onedir* build, not a *onefile* build. Onedir is faster
   to start and does not unpack a temp dir on every launch. Typical
   size: 350-450 MB including Dash, Plotly, NumPy, OpenSeesPy, and
   PyVista.
2. The private data tree is NOT bundled. Set OP3_PHD_ROOT before
   launching the .exe to point at the private data; otherwise the
   viewer renders the graceful-degradation error card.
3. The build assumes PyInstaller 6.0+ and Python 3.12. Older Python
   versions may not bundle OpenSeesPy correctly.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all Dash / Plotly submodules + asset files
hidden = (
    collect_submodules("dash") +
    collect_submodules("plotly") +
    collect_submodules("op3_viz") +
    collect_submodules("op3") +
    [
        "dash.dependencies",
        "dash.html",
        "dash.dcc",
        "dash._callback_context",
        "openseespy.opensees",
        "openfast_io.FAST_output_reader",
    ]
)

datas = (
    collect_data_files("dash") +
    collect_data_files("plotly") +
    collect_data_files("dash_core_components", includes=["*.json"]) +
    [
        ("sample_projects", "sample_projects"),
    ]
)

a = Analysis(
    ["op3_studio_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib.tests", "numpy.tests", "scipy.tests",
        "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6",
    ],
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
    name="op3_studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # keep the console so users see the "Dash running on..."
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="op3_studio",
)
