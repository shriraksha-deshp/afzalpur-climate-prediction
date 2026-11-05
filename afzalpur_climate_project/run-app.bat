@echo off
title Afzalpur Taluk Climate & Drought Portal
color 0B
echo ======================================================================
echo    AFZALPUR TALUK CLIMATE & DROUGHT PREDICTION SYSTEM (1996 - 2055)
echo ======================================================================
echo.
echo [1/3] Checking and installing Python dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing dependencies.
    pause
    exit /b %errorlevel%
)
echo.
echo [2/3] Running Machine Learning Forecast Engine (Random Forest)...
python scripts/forecast_engine.py
if %errorlevel% neq 0 (
    echo Error during forecast calculation.
    pause
    exit /b %errorlevel%
)
echo.
echo [3/3] Launching web portal server at http://localhost:8080 ...
start "" "http://localhost:8080"
python src/server.py
pause
