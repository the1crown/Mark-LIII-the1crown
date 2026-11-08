@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS lite

echo === JARVIS lite start ===
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo FEJL: Python mangler. Installer Python 3.11+ fra python.org ^(tick Add to PATH^).
  pause
  exit /b 1
)

if not exist .venv (
  echo Opretter .venv ...
  python -m venv .venv || (echo FEJL: venv & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q requests edge-tts

if not exist .env if exist .env.example copy /Y .env.example .env >nul

where ollama >nul 2>nul
if errorlevel 1 (
  echo ADVARSEL: Ollama ikke fundet. Cloud/Mistral kan stadig virke hvis .env har noegle.
) else (
  curl -s -m 2 http://127.0.0.1:11434/api/tags >nul 2>nul
  if errorlevel 1 (
    echo Starter Ollama ...
    start "" ollama serve
    timeout /t 4 /nobreak >nul
  )
  curl -s -m 3 http://127.0.0.1:11434/api/tags 2>nul | findstr /I "qwen2.5:3b" >nul
  if errorlevel 1 (
    echo Henter qwen2.5:3b ...
    ollama pull qwen2.5:3b
  )
)

echo.
echo Starter server FOER browser ...
start "JARVIS-lite-server" cmd /c "cd /d \"%CD%\" && call .venv\Scripts\activate.bat && python -m lite --web"

echo Venter paa http://127.0.0.1:7860 ...
set /a n=0
:waitloop
set /a n+=1
curl -s -m 1 http://127.0.0.1:7860/api/health >nul 2>nul
if not errorlevel 1 goto ready
if %n% GEQ 45 (
  echo FEJL: Serveren svarede ikke paa port 7860.
  echo Er porten optaget? Proev: netstat -ano ^| findstr :7860
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo Server OK. Aabner browser ...
start "" http://127.0.0.1:7860/
echo.
echo Lad dette vindue staa aabent. Luk det for at stoppe.
echo Hvis siden er tom: tryk F5. Motor = Lokal eller Mistral.
pause
endlocal
