# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Dynamic / Hidden Imports ──────────────────────────────────────────────────
hiddenimports = []
hiddenimports += collect_submodules('ui')
hiddenimports += collect_submodules('backend')
hiddenimports += collect_submodules('pytablericons')

# Explicitly ensure critical third-party dependencies are resolved
hiddenimports += [
    'PIL._tkinter_finder',
    'python_calamine',
    'python_calamine._python_calamine',
    'openpyxl',
    'pandas',
    'qrcode',
    'qrcode.image.pil',
    'flask',
    'werkzeug',
    'jinja2',
    'jinja2.ext',
    'rapidfuzz',
]

# ── Bundled Data Files ────────────────────────────────────────────────────────
datas = [
    ('ignored_words.json', '.'),
    ('USER_GUIDE.md', '.'),
]
datas += collect_data_files('pytablericons')
datas += collect_data_files('flask')
datas += collect_data_files('jinja2')

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6',
        'shiboken6',
        'ui_qt',
        'archive',
        'pytest',
        '_pytest',
        'pytest_xvfb',
        'xvfbwrapper',
        'pygments',
        'tests',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Arbor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
