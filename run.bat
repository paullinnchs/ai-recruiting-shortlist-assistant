@echo off
where python >nul 2>nul
if %errorlevel%==0 (
    python src\main.py
    exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
    py src\main.py
    exit /b %errorlevel%
)

echo Python was not found. Install Python 3, then run this script again.
exit /b 1
