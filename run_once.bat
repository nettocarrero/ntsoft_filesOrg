@echo off
cd /d %~dp0

if not exist ".venv" (
    echo Ambiente virtual .venv nao encontrado. Execute setup_env.bat primeiro.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m app.main

