@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS lite

echo === JARVIS lite start ===
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo FEJL: Python mangler. Installer Python 3.11+ fra python.org og tick "Add to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo Opretter .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo FEJL: kunne ikke oprette .venv
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q requests edge-tts

if not exist .env (
  echo Opretter tom .env fra .env.example ...
  copy /Y .env.example .env >nul
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo FEJL: Ollama mangler. Installer fra https://ollama.com/download og start Ollama.
  pause
  exit /b 1
)

echo Checker Ollama ...
curl -s -m 3 http://127.0.0.1:11434/api/tags >nul 2>nul
if errorlevel 1 (
  echo Starter Ollama ...
  start "" ollama serve
  timeout /t 3 /nobreak >nul
)

curl -s -m 3 http://127.0.0.1:11434/api/tags | findstr /I "qwen2.5:3b" >nul
if errorlevel 1 (
  echo Henter lokal model qwen2.5:3b (foerste gang kan tage et par minutter) ...
  ollama pull qwen2.5:3b
)

echo.
echo Starter web-UI ...
echo Abner Chrome/Edge: http://127.0.0.1:7860
echo Vaelg Motor = Lokal (Ollama). Tryk Start samtale og tillad mikrofon.
echo.

start "" http://127.0.0.1:7860
python -m lite --web
echo.
echo Serveren stoppede.
pause
