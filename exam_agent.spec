# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for pkg in [
    'langchain_core',
    'langchain_deepseek',
    'langgraph',
    'langgraph.checkpoint',
    'langchain_tavily',
    'dotenv',
]:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception as e:
        print(f"警告: collect_all('{pkg}') 失败: {e}")

extra_hiddenimports = [
    'langchain_deepseek.chat_models',
    'langgraph.graph',
    'langgraph.checkpoint.memory',
    'langchain_tavily',
    'dotenv.main',
    'docx',
    'docx.document',
    'docx.shared',
    'docx.enum.text',
    'docx.enum.table',
    'lxml',
    'lxml.etree',
    'lxml._elementpath',
]
hiddenimports += extra_hiddenimports

a = Analysis(
    ['main_tk.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'jupyter',
        'IPython',
        '.env',  
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
    name='ExamAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 程序，不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可指定图标路径，如 'icon.ico'
)
