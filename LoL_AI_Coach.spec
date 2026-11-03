# -*- mode: python ; coding: utf-8 -*-
# Gera dist/LoL_AI_Coach/ com o executável. Use scripts/build.ps1 para montar o .zip.

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LoL_AI_Coach",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX aumenta os falsos positivos de antivírus; o ganho de tamanho não compensa.
    upx=False,
    # O coach é um app de terminal: escolha de personalidade e logs aparecem no console.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LoL_AI_Coach",
)
