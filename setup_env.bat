@echo off
cd /d %~dp0

echo Criando ambiente virtual .venv (se ainda nao existir)...
python -m venv .venv

if not exist ".venv\Scripts\activate.bat" (
    echo Falha ao criar ambiente virtual .venv.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo Atualizando pip...
python -m pip install --upgrade pip

echo Instalando dependencias de requirements.txt...
pip install -r requirements.txt

echo Ambiente configurado. Use run_once.bat ou run_watch.bat para executar o sistema.
pause

