@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo Starting WebSale Backend with virtual environment...
    ".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
) else (
    echo Starting WebSale Backend with system python...
    python manage.py runserver 0.0.0.0:8000
)

pause
