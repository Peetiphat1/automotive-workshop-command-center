# 🚀 วิธีการรันโปรเจกต์ (How to Run This Project)

คู่มือนี้สำหรับรัน **Automotive Workshop Command Center** ด้วยตัวเองได้ง่ายๆ ทั้งบน **Windows (PC)** และ **Linux / macOS** โดยมีระบบติดตั้งสภาพแวดล้อม (Environment) และเปิดเว็บให้โดยอัตโนมัติ

---

## ⚡ วิธีรันแบบโปรแกรมคลิกเดียว (One-Click Run)

### 🪟 สำหรับ Windows (Real PC):
1. แตกไฟล์ ZIP ออกมาไว้ในเครื่อง (เช่น โฟลเดอร์ที่ต้องการ หรือ Desktop)
2. **ดับเบิ้ลคลิกที่ไฟล์:**
   ```
   START.bat   (หรือ run.bat)
   ```
3. ✨ **ระบบจะทำงานทุกอย่างให้อัตโนมัติ:**
   - ตรวจหา Python ในเครื่อง
   - สร้าง Virtual Environment (`.venv`) ให้อัตโนมัติ
   - ดาวน์โหลดและติดตั้ง Library ทั้งหมดจาก `requirements.txt` ให้อัตโนมัติ
   - ตั้งค่าตัวแปรสภาพแวดล้อม (`.env`) ให้อัตโนมัติ
   - **เปิดหน้าเว็บเบราว์เซอร์เข้า Dashboard ให้อัตโนมัติ!**

> 💡 **ข้อกำหนดเบื้องต้น:**  
> คอมพิวเตอร์ต้องติดตั้ง **Python 3.10 ขึ้นไป** ([ดาวน์โหลดฟรีที่ python.org](https://www.python.org/downloads/))  
> *(ข้อสำคัญ: ตอนติดตั้งอย่าลืมติ๊กถูกที่ช่อง **"Add python.exe to PATH"**)*

---

### 🐧 / 🍎 สำหรับ Linux หรือ macOS:
ดับเบิ้ลคลิกหรือเปิด Terminal แล้วรัน:
```bash
./START_MAC_LINUX.sh
# หรือ
./run.sh
```

---

## 🌐 ลิงก์เข้าใช้งานระบบเมื่อ Server รันอยู่

เมื่อเซิร์ฟเวอร์เริ่มทำงานแล้ว สามารถเปิดเบราว์เซอร์เข้าใช้งานตาม URL ต่อไปนี้:

| หน้าที่ | URL | รายละเอียด |
|---|---|---|
| **Dashboard หลัก** | [http://localhost:8000/dashboard](http://localhost:8000/dashboard) | หน้าจอควบคุมหลักของอู่ซ่อมรถ |
| **จัดการสต็อกและอะไหล่** | [http://localhost:8000/stock](http://localhost:8000/stock) | เช็คสต็อก, เบิกจ่าย, สั่งซื้ออะไหล่ |
| **สแกนป้ายทะเบียน/อะไหล่** | [http://localhost:8000/scan](http://localhost:8000/scan) | ฟังก์ชันกล้อง / OCR ตรวจจับป้ายทะเบียน |
| **ติดตามสถานะการซ่อม** | [http://localhost:8000/track](http://localhost:8000/track) | หน้าสำหรับลูกค้าตรวจเช็คสถานะการซ่อม |
| **API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | เอกสารและทดสอบ REST API ทุกตัว |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | ตรวจสอบสถานะการทำงานของระบบ |

> 🔐 **รหัสผ่านร้าน (ปิดอยู่):** ตอนนี้เปิดใช้ได้เลยโดยไม่ต้องใส่รหัส — ถ้าต้องการให้ถามรหัส ให้ใส่ `REQUIRE_PASSWORD=true` ในไฟล์ `.env` แล้วรีสตาร์ทโปรแกรม (รหัสคือค่า `MOCK_API_KEY`)

---

## ⏹ วิธีหยุดการทำงาน (Stop Server)
- **Windows**: ปิดหน้าต่างสีดำ (Command Prompt) หรือกด `Ctrl + C`
- **Linux / macOS**: กด `Ctrl + C` ใน Terminal

---

## 🔧 การแก้ปัญหาเบื้องต้น (Troubleshooting)

### 1. หน้าต่างขึ้นว่า "ไม่พบ Python ในเครื่องของคุณ" (Python was not found)
- แปลว่าเครื่องยังไม่ได้ติดตั้ง Python หรือตอนติดตั้งไม่ได้ติ๊ก **"Add python.exe to PATH"**
- ให้ดาวน์โหลดตัวติดตั้งจาก [python.org](https://www.python.org/downloads/) แล้วติดตั้งใหม่ โดยอย่าลืมติ๊กช่อง Add Python to PATH

### 2. กรณีพอร์ต 8000 ชน (Port 8000 already in use)
หากมีโปรแกรมอื่นใช้พอร์ต 8000 อยู่:
- บน **Windows**: เปิด Command Prompt สั่ง `netstat -ano | findstr 8000` แล้วสั่ง `taskkill /PID <PID_NUMBER> /F`
- บน **Linux/macOS**: สั่ง `fuser -k 8000/tcp`
