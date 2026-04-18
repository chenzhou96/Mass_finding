# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

project_root = Path(SPECPATH)
icon_file = project_root / 'package' / 'resources' / 'icon.ico'


datas = [
    (str(project_root / 'package' / 'config' / 'chem_element_config.json'), 'package/config'),
    (str(project_root / 'package' / 'resources' / 'icon.ico'), 'package/resources'),
    (str(project_root / 'package' / 'resources' / 'icon.icns'), 'package/resources'),
] + collect_data_files('rdkit')

binaries = collect_dynamic_libs('rdkit')

hiddenimports = [
    'PIL._tkinter_finder',
    'rdkit',
    'rdkit.Chem',
    'rdkit.Chem.Draw',
    'rdkit.Chem.rdDepictor',
    'rdkit.DataStructs',
    'rdkit.Geometry',
] + collect_submodules('rdkit.Chem')

excludes = [
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'matplotlib',
    'scipy',
    'pandas',
    'notebook',
    'jupyterlab',
    'IPython',
    'tables',
    'sqlalchemy',
    'plotly',
    'bokeh',
    'dask',
    'distributed',
    'xarray',
]


a = Analysis(
    [str(project_root / 'run.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MassFinding',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_file),
)
