@echo off
cd /d "%~dp0"
where ollama >nul 2>nul
if errorlevel 1 (
  echo Installer Ollama fra https://ollama.com hvis du vil køre lokalt.
)
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install requests edge-tts
) else (
  call .venv\Scripts\activate.bat
  pip install -q requests edge-tts
)
echo.
echo Åbn Chrome/Edge: http://127.0.0.1:7860
echo Tryk Tale eller hold mellemrum — tillad mikrofon.
echo.
python -m lite --web
pause
