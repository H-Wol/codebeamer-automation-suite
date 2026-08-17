# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata


REPOSITORY_ROOT = Path(SPECPATH).resolve().parent


def _is_runtime_xlwings_module(module_name: str) -> bool:
    runtime_modules = {
        "xlwings",
        "xlwings._types",
        "xlwings._win32patch",
        "xlwings._xlwindows",
        "xlwings.base_classes",
        "xlwings.constants",
        "xlwings.expansion",
        "xlwings.main",
        "xlwings.utils",
    }
    return module_name in runtime_modules or module_name.startswith("xlwings.conversion")


cryptography_datas, cryptography_binaries, cryptography_hiddenimports = collect_all(
    "cryptography"
)

datas = [
    (str(REPOSITORY_ROOT / "VERSION"), "."),
    (str(REPOSITORY_ROOT / "src" / "gui" / "assets"), "src/gui/assets"),
]
datas += cryptography_datas
datas += copy_metadata("keyring")
datas += copy_metadata("xlwings")

hiddenimports = [
    "PySide6.QtSvg",
    "keyring.backends.Windows",
    "keyring.backends.fail",
    "keyring.backends.null",
    "pythoncom",
    "pywintypes",
    "win32api",
    "win32con",
    "win32cred",
    "win32gui",
    "win32process",
    "win32timezone",
    "win32ctypes.pywin32.pywintypes",
    "win32ctypes.pywin32.win32cred",
]
hiddenimports += cryptography_hiddenimports
hiddenimports += collect_submodules("xlwings", filter=_is_runtime_xlwings_module)
hiddenimports += collect_submodules("win32com")

a = Analysis(
    [str(REPOSITORY_ROOT / "gui_main.py")],
    pathex=[str(REPOSITORY_ROOT)],
    binaries=cryptography_binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["xlwings._xlmac"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CodebeamerAutomationSuite",
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
    contents_directory="_internal",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CodebeamerAutomationSuite",
)
