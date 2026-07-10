@echo off
title SmartEnroll UTH - Khoi dong he thong
echo ==================================================
echo         KHOI DONG SMARTENROLL UTH (WINDOWS)
echo ==================================================
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] May tinh cua ban chua cai dat Python hoac chua them vao PATH!
    echo Vui long tai va cai dat Python tai: https://www.python.org/downloads/
    pause
    exit /b
)

:: 2. Kiem tra va khoi tao Virtual Environment (venv)
if not exist venv (
    echo [INFO] Dang khoi tao moi truong ao (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Khong the tao venv!
        pause
        exit /b
      )
)

:: 3. Kiem tra thu vien va tu dong cai dat
echo [INFO] Kiem tra va cap nhat thu vien phu thuoc...
venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Co loi khi cai dat dependencies bang pip.
)

:: 4. Chay file start.py
echo.
echo [SUCCESS] Moi thu da san sang! Dang chay SmartEnroll...
echo ==================================================
venv\Scripts\python start.py
pause
