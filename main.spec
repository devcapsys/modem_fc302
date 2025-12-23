# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# Collect data for required packages
mysql_datas, mysql_binaries, mysql_hiddenimports = collect_all('mysql.connector')
reportlab_datas, reportlab_binaries, reportlab_hiddenimports = collect_all('reportlab')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[] + mysql_binaries + reportlab_binaries,
    datas=[
        ('logo-big.png', '.'),
        ('steps', 'steps'),
        ('assets', 'assets'),
    ] + mysql_datas + reportlab_datas,
    hiddenimports=[
        # PyQt6 modules
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        
        # Database connectivity
        'mysql.connector',
        
        # PDF generation
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        
        # Configuration module
        'configuration',
        
    ] + mysql_hiddenimports + reportlab_hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='main',
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
    icon='logo-big.png',
)