@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo       LoL AI Coach v3.1 - Inicializador
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python nao foi encontrado no PATH.
  echo Instale Python 3.11+ e marque "Add Python to PATH".
  pause
  exit /b 1
)

if not exist venv\Scripts\python.exe (
  echo Criando ambiente virtual...
  python -m venv venv
  if errorlevel 1 (
    echo ERRO: Nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
  )
)

echo.
echo Verificando/instalando dependencias...
venv\Scripts\python.exe -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 echo AVISO: Nao foi possivel atualizar o pip. Continuando...

venv\Scripts\python.exe -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
  echo.
  echo ERRO: Falha ao instalar alguma dependencia.
  pause
  exit /b 1
)

echo.
echo Iniciando o coach...
echo.
venv\Scripts\python.exe main.py
set ERR=%ERRORLEVEL%

echo.
if not "%ERR%"=="0" echo O coach foi encerrado com codigo %ERR%.
pause
exit /b %ERR%
