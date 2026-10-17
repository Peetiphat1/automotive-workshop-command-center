#!/usr/bin/env bash
# ==============================================================================
# Script to run Automotive Workshop Command Center (Linux / macOS)
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=============================================================================="
echo "      AUTOMOTIVE WORKSHOP COMMAND CENTER - AUTO LAUNCHER"
echo "=============================================================================="
echo ""

# 1. Auto-copy .env if missing
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[INFO] สร้างไฟล์คอนฟิก .env อัตโนมัติ (Creating .env from .env.example)..."
    cp .env.example .env
fi

# 2. Check virtual environment & python
if [ ! -d ".venv" ]; then
    echo "[INFO] ตรวจพบการเปิดใช้งานครั้งแรก กำลังสร้างสภาพแวดล้อมระบบ (.venv)..."
    if command -v python3 &>/dev/null; then
        PYTHON_EXEC="python3"
    elif command -v python &>/dev/null; then
        PYTHON_EXEC="python"
    else
        echo "[ERROR] ไม่พบ Python ในเครื่อง! กรุณาติดตั้ง Python 3.10 ขึ้นไป"
        echo "[ERROR] Python 3 was not found! Please install Python 3.10+."
        exit 1
    fi

    $PYTHON_EXEC -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] ไม่สามารถสร้าง Virtual Environment ได้"
        exit 1
    fi

    echo "[INFO] กำลังติดตั้ง Library ที่จำเป็นจาก requirements.txt..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] ไม่สามารถติดตั้ง dependencies ได้"
        exit 1
    fi
    echo "[SUCCESS] ติดตั้งสำเร็จเรียบร้อย!"
    echo ""
else
    echo "[INFO] สภาพแวดล้อมระบบพร้อมใช้งาน (.venv พร้อมแล้ว)"
fi

# 3. Auto-open browser in background
(
    sleep 3
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:8000/dashboard" &>/dev/null
    elif command -v open &>/dev/null; then
        open "http://localhost:8000/dashboard" &>/dev/null
    fi
) &

# 4. Start Server
echo "=============================================================================="
echo " Starting Automotive Workshop Command Center..."
echo " Dashboard : http://localhost:8000/dashboard"
echo " API Docs  : http://localhost:8000/docs"
echo " (กำลังเปิดเบราว์เซอร์อัตโนมัติ... / Opening browser automatically...)"
echo "=============================================================================="
echo ""

exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
