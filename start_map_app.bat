@echo off
setlocal
echo ===============================================
echo     Flask App Auto Setup and Runner by Syed Shayan Ahmed🙂
echo ===============================================
echo.

:: --------- 1. Check Python ----------
where python >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b
) else (
    python --version
)

:: --------- 2. Create venv if not exists ----------
if not exist venv (
    echo [>] Creating virtual environment...
    python -m venv venv
)

:: --------- 3. Activate venv ----------
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [!] Failed to activate virtual environment.
    pause
    exit /b
)

:: --------- 4. Upgrade pip ----------
python -m pip install --upgrade pip

:: --------- 5. Install dependencies ----------
set REQS=flask folium pyproj pillow mercantile requests

for %%p in (%REQS%) do (
    python -c "import %%p" 2>nul
    if errorlevel 1 (
        echo [>] Installing %%p...
        pip install %%p
    ) else (
        echo [+] %%p already installed.
    )
)

:: --------- 6. Launch Flask app ----------
echo.
echo [>] Running Flask app...
start "" python app.py
echo [i] Flask app launched. Opening browser...
timeout /t 3 >nul
start "" http://127.0.0.1:5000/
pause
