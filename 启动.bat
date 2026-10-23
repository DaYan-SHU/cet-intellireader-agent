@echo off
chcp 65001 >nul
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo 未检测到 uv，请先安装：https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

uv sync
if errorlevel 1 (
    echo 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)

uv run streamlit run main.py
pause
