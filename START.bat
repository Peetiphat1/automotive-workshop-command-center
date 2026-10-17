@echo off
setlocal enabledelayedexpansion
title Zero Garage - Automotive Workshop Command Center
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================================================
echo             ZERO GARAGE - AUTOMOTIVE WORKSHOP COMMAND CENTER
echo ==============================================================================
echo.

REM 1. Check if running from inside Temp / Zip preview
echo "%~dp0" | findstr /i "Temp" >nul
if %errorlevel% equ 0 (
    echo [WARNING] คุณกำลังเปิดโปรแกรมจากในไฟล์ ZIP โดยตรง!
    echo กรุณาคลิกขวาที่ไฟล์ ZIP แล้วเลือก "Extract All..." [แตกไฟล์ทั้งหมด] ก่อนเปิดใช้งาน
    echo.
    echo Please EXTRACT the zip file before running START.bat!
    pause
    exit /b 1
)

REM 2. Find Python
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :python_found
)

REM Try py launcher
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 --version >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py -3"
        goto :python_found
    )
)

REM Search in common AppData and Program Files
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :python_found
    )
)
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :python_found
    )
)
for /d %%D in ("C:\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :python_found
    )
)

REM Try python in PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    python --version >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
        goto :python_found
    )
)

REM If still not found
echo ==============================================================================
echo [ERROR] ไม่พบ Python ในเครื่องของคุณ [Python is not installed or not in PATH]
echo ==============================================================================
echo.
echo ระบบต้องการ Python 3.10 ขึ้นไปในการทำงาน
echo.
where winget >nul 2>nul
if %errorlevel% equ 0 (
    echo ระบบตรวจพบ winget สามารถติดตั้ง Python ให้โดยอัตโนมัติได้
    set /p "CHOICE=ต้องการให้ติดตั้ง Python 3.12 ให้อัตโนมัติทันทีหรือไม่? [Y/N]: "
    if /i "!CHOICE!"=="Y" (
        echo.
        echo [INFO] กำลังติดตั้ง Python 3.12 กรุณารอสักครู่...
        winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
        echo.
        echo [INFO] ติดตั้งเสร็จแล้ว! กรุณาปิดหน้าต่างนี้แล้วดับเบิ้ลคลิก START.bat ใหม่อีกครั้ง
        pause
        exit /b 0
    )
)
echo.
echo กรุณาดาวน์โหลดและติดตั้ง Python ได้ที่: https://www.python.org/downloads/
echo ** ข้อสำคัญ: ในหน้าต่างติดตั้ง อย่าลืมติ๊กถูกที่ [X] Add python.exe to PATH **
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:python_found
echo [OK] ใช้งาน Python: !PYTHON_EXE!
echo.

REM 3. Auto-copy .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] สร้างไฟล์คอนฟิก .env อัตโนมัติ...
        copy /y ".env.example" ".env" >nul
    )
)

REM 4. Setup Virtual Environment & Dependencies
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] กำลังเตรียมสภาพแวดล้อมระบบครั้งแรก [.venv]...
    echo [INFO] กรุณารอสักครู่ [ขั้นตอนนี้ทำเฉพาะครั้งแรก]...
    echo.
    !PYTHON_EXE! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] ไม่สามารถสร้าง Virtual Environment ได้
        pause
        exit /b 1
    )
    echo [INFO] กำลังติดตั้ง Library ที่จำเป็นจาก requirements.txt...
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] การติดตั้งไลบรารีไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
        pause
        exit /b 1
    )
    echo.
    echo [OK] ติดตั้ง Library เรียบร้อยแล้ว!
    echo.
) else (
    echo [OK] สภาพแวดล้อมระบบ .venv พร้อมใช้งานแล้ว
)

REM 5. Auto open browser in background
start "" cmd /c "ping 127.0.0.1 -n 4 >nul & start http://localhost:8000/dashboard"

REM 6. Run Server
echo ==============================================================================
echo  Starting Zero Garage Command Center...
echo  Dashboard : http://localhost:8000/dashboard
echo  API Docs  : http://localhost:8000/docs
echo.
echo  * กำลังเปิดหน้าต่างเบราว์เซอร์อัตโนมัติ...
echo  * กด Ctrl+C ในหน้าต่างนี้เมื่อต้องการหยุดการทำงาน
echo ==============================================================================
echo.

.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo [ERROR] เซิร์ฟเวอร์หยุดทำงานกะทันหัน
    pause
)
