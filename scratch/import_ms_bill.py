import json
import os
import shutil
from datetime import datetime
from core.database import SessionLocal
from models.db_models import Supplier, PurchaseBill, StockItem, StockHistory

def run_import():
    db = SessionLocal()
    
    # ── 1. Copy bill images to static/uploads/bills/ ──
    os.makedirs("static/uploads/bills", exist_ok=True)
    os.makedirs("static/uploads/stock/bills", exist_ok=True)
    
    file_mapping = {
        "1000014306.jpg": ["SO6908141_1.jpg", "1000014306.jpg"],
        "1000014309.jpg": ["SO6908141_2.jpg", "1000014309.jpg"],
        "1000014307.jpg": ["SO6908141_3.jpg", "1000014307.jpg"],
        "1000014308.jpg": ["SO6908141_4.jpg", "1000014308.jpg"],
    }
    
    for src_name, targets in file_mapping.items():
        src_path = os.path.join("bill", src_name)
        if os.path.exists(src_path):
            for tgt in targets:
                shutil.copy2(src_path, os.path.join("static/uploads/bills", tgt))
                shutil.copy2(src_path, os.path.join("static/uploads/stock/bills", tgt))
            print(f"Copied {src_name} -> {targets}")
        else:
            print(f"Warning: {src_path} not found")

    # ── 2. Supplier: MS (Monza / MS Billet) ──
    supplier = db.query(Supplier).filter(Supplier.name.like("%MS%")).first()
    if not supplier:
        supplier = Supplier(
            name="MS (Monza Factory / MS Billet)",
            phone="081-999-8877",
            email="sales@ms-billet.com",
            address="20/1 ถ.โกมารภัจจ์ ต.ตลาดใหญ่ อ.เมือง จ.ภูเก็ต 83000",
            notes="ผู้ผลิตและจำหน่ายอะไหล่แต่ง Billet อลูมิเนียม เกจวัด และอุปกรณ์ตกแต่งห้องเครื่อง",
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        print(f"Created Supplier: ID {supplier.id} - {supplier.name}")
    else:
        print(f"Found Supplier: ID {supplier.id} - {supplier.name}")

    # ── 3. 70 Line Items Transcribed from all 4 Pages ──
    # Format: (page_num, sku, raw_desc, clean_name_th, name_en, category, qty, unit, cost, sell_price)
    items_data = [
        # ── Page 1 (1000014306.jpg) ──
        (1, "MS-B-9132", "ฝาพาวเวอร์ ISUZU BILLET * 1500", "ฝาพาวเวอร์ ISUZU BILLET", "Power Steering Cap ISUZU BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 4, "ชิ้น", 1200.0, 1500.0),
        (1, "MS-B-9096", "ครอบกระป๋องเวสเกต BILLET * 950", "ครอบกระป๋องเวสเกต BILLET", "Wastegate Canister Cover BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 10, "ชิ้น", 750.0, 950.0),
        (1, "MS-B-9081", "ครอบที่วัดน้ำมันเครื่อง ISU * 950", "ครอบที่วัดน้ำมันเครื่อง ISUZU BILLET", "Dipstick Cover ISUZU BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 10, "ชิ้น", 750.0, 950.0),
        (1, "MS-B-9106", "ปลอกรัดท่อน้ำ BILLET:คู่ * 1400", "ปลอกรัดท่อน้ำ BILLET (คู่)", "Radiator Hose Clamp Set BILLET (Pair)", "ท่อและระบบทางเดินน้ำ", 5, "ชุด", 1100.0, 1400.0),
        (1, "MS-B-9001", "ฝาน้ำมันเครื่อง Billet * 600", "ฝาน้ำมันเครื่อง Billet", "Engine Oil Cap Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 10, "ชิ้น", 400.0, 600.0),
        (1, "MS-B-9003", "ปิดไอระบาย Billet * 400", "ปิดไอระบาย Billet", "Breather Plug Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 10, "ชิ้น", 350.0, 400.0),
        (1, "MS-B-9004", "ปิดปั๊มลม 1.9 Billet * 900", "ปิดปั๊มลม 1.9 Billet", "Air Pump Delete Plate 1.9 Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 700.0, 900.0),
        (1, "MS-T-9141", "ขาบูสท์ห่วง TITANIUM * 1400", "ขาบูสท์ห่วง TITANIUM", "Boost Gauge Ring Mount TITANIUM", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 1000.0, 1400.0),
        (1, "MS-L-9138", "ขาวัดบูสท์ (แบบห่วง) STAINLESS * 100", "ขาวัดบูสท์ (แบบห่วง) STAINLESS", "Boost Gauge Ring Mount Stainless", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 700.0, 1000.0),
        (1, "MS-L-9139", "ขาวัดบูสท์ (แบบห่วง) BLACK * 1100", "ขาวัดบูสท์ (แบบห่วง) BLACK", "Boost Gauge Ring Mount Black", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 750.0, 1100.0),
        (1, "MS-L-9020", "ขาวัดบูสท์สแตนเลส * 600", "ขาวัดบูสท์สแตนเลส", "Boost Gauge Bracket Stainless", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 400.0, 600.0),
        (1, "MS-L-9021", "ขาวัดบูสท์ Black * 700", "ขาวัดบูสท์ Black", "Boost Gauge Bracket Black", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 450.0, 700.0),
        (1, "MS-T-9001", "ขาวัดบูสท์ TITANIUM * 800", "ขาวัดบูสท์ TITANIUM", "Boost Gauge Bracket TITANIUM", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 600.0, 800.0),
        (1, "MS-T-9003", "ขาล็อคหลัง+ปิดหลัง TITANIUM * 800", "ขาล็อคหลัง+ปิดหลัง TITANIUM", "Rear Gauge Lock & Cover TITANIUM", "เกจวัดและอุปกรณ์", 2, "ชุด", 600.0, 800.0),
        (1, "MS-L-9023", "ขาล็อคหลัง+ปิดหลัง SST * 300", "ขาล็อคหลัง+ปิดหลัง Stainless", "Rear Gauge Lock & Cover Stainless", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 200.0, 300.0),
        (1, "MS-L-9022", "ขาล็อคหลัง+ปิดหลัง Black * 400", "ขาล็อคหลัง+ปิดหลัง Black", "Rear Gauge Lock & Cover Black", "เกจวัดและอุปกรณ์", 2, "ชิ้น", 250.0, 400.0),
        (1, "MS-B-9100", "แบตเตอร์รี่ล็อค BILLET * 950", "แบตเตอร์รี่ล็อค BILLET", "Billet Battery Tie Down Bracket", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชุด", 750.0, 950.0),
        (1, "MS-B-9012", "Adaptor Boots 3.0 * 750", "Adaptor Boots 3.0", "Silicone Boots Adapter 3.0", "ท่อและระบบทางเดินน้ำ", 5, "ชิ้น", 450.0, 750.0),
        (1, "MS-B-9011", "Adaptor Boot 1.9 * 750", "Adaptor Boot 1.9", "Silicone Boot Adapter 1.9", "ท่อและระบบทางเดินน้ำ", 5, "ชิ้น", 450.0, 750.0),
        (1, "MS-L-9162", "อแดปเตอร์บูสท์ U5 * 750", "อแดปเตอร์บูสท์ U5", "Boost Sensor Adapter U5", "เกจวัดและอุปกรณ์", 5, "ชิ้น", 550.0, 750.0),

        # ── Page 2 (1000014309.jpg) ──
        (2, "MS-F-9006", "อแดปเตอร์กระป๋องเวสเกต 3.0 * 750", "อแดปเตอร์กระป๋องเวสเกต 3.0", "Wastegate Actuator Adapter 3.0", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชุด", 450.0, 750.0),
        (2, "MS-B-9130", "ฝาหม้อน้ำ BILLET * 950", "ฝาหม้อน้ำ BILLET", "Radiator Cap BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 750.0, 950.0),
        (2, "MS-E-9005", "EGR 1.9 Billet * 600", "แผ่นอุด EGR 1.9 Billet", "EGR Block-off Plate 1.9 Billet", "ระบบ EGR และไอเสีย", 2, "ชิ้น", 250.0, 600.0),
        (2, "MS-D-9010", "ท่อน้ำวน * 350", "ท่อน้ำวน", "Bypass Coolant Hose Tube", "ท่อและระบบทางเดินน้ำ", 2, "ชิ้น", 250.0, 350.0),
        (2, "MS-E-9033", "EGR 2.2 Maxforce. BILLET * 650", "แผ่นอุด EGR 2.2 Maxforce BILLET", "EGR Delete Plate 2.2 Maxforce BILLET", "ระบบ EGR และไอเสีย", 10, "ชิ้น", 300.0, 650.0),
        (2, "MS-E-9009", "EGR REVO BILLET * 900", "แผ่นอุด EGR REVO BILLET", "EGR Delete Plate REVO BILLET", "ระบบ EGR และไอเสีย", 4, "ชุด", 700.0, 900.0),
        (2, "MS-V-9001-A", "ถังพักน้ำสั้น* งานไดร์สี เงิน * 1700", "ถังพักน้ำสั้น งานไดร์สี เงิน", "Short Coolant Overflow Tank Anodized Silver", "ถังน้ำและถังดักไอ", 5, "ชุด", 1200.0, 1700.0),
        (2, "MS-B-9039", "ชุดน็อตฝาวาล์ว 16pcs. Billet * 1100", "ชุดน็อตฝาวาล์ว 16pcs. Billet", "Valve Cover Bolt Set 16pcs Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 4, "ชิ้น", 800.0, 1100.0),
        (2, "MS-B-9055", "ชุดน็อตหน้าเครื่อง Billet * 1100", "ชุดน็อตหน้าเครื่อง Billet", "Front Engine Dress-up Bolts Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 4, "ชุด", 900.0, 1100.0),
        (2, "MS-B-9079", "ครอบรางดีเซล 1.9 BILLET * 2400", "ครอบรางดีเซล 1.9 BILLET", "Common Rail Fuel Rail Cover 1.9 BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 3, "ชิ้น", 1900.0, 2400.0),
        (2, "MS-V-9007", "ถัง A นอน * 2000", "ถัง A นอน Billet", "Catch Can Horizontal Type A", "ถังน้ำและถังดักไอ", 2, "ชุด", 1500.0, 2000.0),
        (2, "MS-V-9013", "ถังดักไอใหญ่ * 2000", "ถังดักไอใหญ่ Billet", "Large Oil Catch Can Billet", "ถังน้ำและถังดักไอ", 2, "ชิ้น", 1700.0, 2000.0),
        (2, "MS-V-9011", "ถังพาเวอร์เสียบ * 1800", "ถังเพาเวอร์เสียบ Billet", "Power Steering Reservoir Tank Billet", "ถังน้ำและถังดักไอ", 2, "ชุด", 1400.0, 1800.0),
        (2, "MS-B-9126", "อแดปเตอร์ไอระบาย AN10 (2pot) * 1300", "อแดปเตอร์ไอระบาย AN10 (2pot)", "Breather Adapter AN10 Dual Port", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชุด", 1000.0, 1300.0),
        (2, "MS-B-9064", "อแดปเตอร์ไอระบายออกบน AN10 * 500", "อแดปเตอร์ไอระบายออกบน AN10", "Breather Top Outlet Adapter AN10", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 400.0, 500.0),
        (2, "MS-B-9057", "ฝาน้ำมันเครื่อง REVO สูง * 850", "ฝาน้ำมันเครื่อง REVO สูง Billet", "Engine Oil Cap REVO High Profile Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 550.0, 850.0),
        (2, "MS-V-9052", "ท่อเติมน้ำ REVO * 1800", "ท่อเติมน้ำ REVO Billet", "Radiator Filler Neck REVO Billet", "ท่อและระบบทางเดินน้ำ", 4, "ชิ้น", 1300.0, 1800.0),
        (2, "MS-R-9012", "เสื้อ MS * 490", "เสื้อยืด MS Official", "MS Official T-Shirt", "ของแต่งและอุปกรณ์เสริม", 2, "ตัว", 350.0, 490.0),
        (2, "MS-B-9072", "ขาแบตเตอรี่ BILLET. REVO * 950", "ขาแบตเตอรี่ BILLET REVO", "Battery Tie Down Bracket BILLET REVO", "อุปกรณ์แต่งห้องเครื่อง Billet", 4, "ชุด", 750.0, 950.0),
        (2, "MS-B-9080", "ครอบที่วัดน้ำมันเครื่อง GD * 950", "ครอบที่วัดน้ำมันเครื่อง GD Billet", "Dipstick Cover GD Engine Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 750.0, 950.0),

        # ── Page 3 (1000014307.jpg) ──
        (3, "MS-B-9085", "ฝาครอบกระปุกเบรค TOYOTA * 950", "ฝาครอบกระปุกเบรค TOYOTA BILLET", "Brake Reservoir Cap TOYOTA BILLET", "ระบบเบรค", 3, "ชิ้น", 700.0, 950.0),
        (3, "MS-D-9005", "อะแดปเตอร์ไอระบาย REVO * 600", "อะแดปเตอร์ไอระบาย REVO", "Breather Adapter REVO", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 400.0, 600.0),
        (3, "MS-V-9001-B", "ท่อเติมน้ำ 2020 * 1700", "ท่อเติมน้ำ D-Max 2020 Billet", "Radiator Filler Tube 2020 Billet", "ท่อและระบบทางเดินน้ำ", 3, "ชุด", 1300.0, 1700.0),
        (3, "MS-B-9016", "แผ่นปิดท่อน้ำ 1.9 * 650", "แผ่นปิดท่อน้ำ 1.9 Billet", "Coolant Block-off Plate 1.9 Billet", "ท่อและระบบทางเดินน้ำ", 5, "ชุด", 450.0, 650.0),
        (3, "MS-D-9026", "ท่อไหลกลับ 1.9 Aluminium * 1300", "ท่อไหลกลับ 1.9 Aluminium", "Turbo Return Pipe 1.9 Aluminium", "ท่อและระบบทางเดินน้ำ", 4, "ชิ้น", 1000.0, 1300.0),
        (3, "MS-D-9027", "ท่อไหลกลับ Allnew Aluminium * 1300", "ท่อไหลกลับ Allnew Aluminium", "Turbo Return Pipe Allnew Aluminium", "ท่อและระบบทางเดินน้ำ", 1, "ชิ้น", 1000.0, 1300.0),
        (3, "MS-B-9028", "ขาไดร์ชาร์จ D-max/EURO4 * 850", "ขาไดร์ชาร์จ D-max / EURO4 Billet", "Alternator Bracket D-max / EURO4 Billet", "อุปกรณ์แต่งห้องเครื่อง Billet", 5, "ชิ้น", 650.0, 850.0),
        (3, "MS-B-9120", "ฝาครอบเบรค ISUZU BILLET * 1400", "ฝาครอบเบรค ISUZU BILLET", "Brake Master Cylinder Cover ISUZU BILLET", "ระบบเบรค", 5, "ชุด", 1000.0, 1400.0),
        (3, "MS-B-9030", "ห่วงหม้อลม Billet 1.9 * 350", "ห่วงหม้อลม Billet 1.9", "Brake Booster Ring Billet 1.9", "ระบบเบรค", 6, "ชิ้น", 250.0, 350.0),
        (3, "MS-B-9019", "Adapter วาล์วน้ำ D-MAX * 850", "Adapter วาล์วน้ำ D-MAX", "Thermostat Housing Adapter D-MAX", "ท่อและระบบทางเดินน้ำ", 2, "ชิ้น", 650.0, 850.0),
        (3, "MS-B-9022", "หัวเกียร์ Billet * 400", "หัวเกียร์ Billet", "Manual Shift Knob Billet", "ของแต่งและอุปกรณ์เสริม", 5, "ชิ้น", 250.0, 400.0),
        (3, "MS-V-9039", "กระปุกเบรค Allnew D-max * 2500", "กระปุกเบรค Allnew D-max Billet", "Brake Fluid Reservoir Allnew D-max Billet", "ระบบเบรค", 5, "ชิ้น", 2000.0, 2500.0),
        (3, "MS-A-0002", "Auto meter หน้าขาว * 6000", "เกจ์วัด Auto Meter หน้าขาว", "Auto Meter Gauge White Face", "เกจวัดและอุปกรณ์", 3, "ชิ้น", 6300.0, 7500.0),
        (3, "MS-B-9044-P3", "มู่เล่ปั๊มน้ำ BILLET * 2900", "มู่เล่ปั๊มน้ำ BILLET", "Water Pump Pulley BILLET", "มู่เล่และลูกรอก", 1, "ชิ้น", 2600.0, 2900.0),
        (3, "MS-B-9045", "มู่เล่เครื่อง BILLET * 3900", "มู่เล่เครื่อง Crankshaft BILLET", "Crankshaft Pulley BILLET", "มู่เล่และลูกรอก", 1, "ชิ้น", 3600.0, 3900.0),
        (3, "MS-B-9046", "มู่เล่เพาเวอร์ Billet * 2200", "มู่เล่เพาเวอร์ Billet", "Power Steering Pulley Billet", "มู่เล่และลูกรอก", 1, "ชิ้น", 1800.0, 2200.0),
        (3, "MS-B-9047-P3", "มู่เล่ไดร์ชาร์จ Billet * 1800", "มู่เล่ไดร์ชาร์จ Billet", "Alternator Pulley Billet", "มู่เล่และลูกรอก", 1, "ชิ้น", 1400.0, 1800.0),
        (3, "MS-B-9095", "ครอบคอมแอร์ 1.9 BILLET * 2200", "ครอบคอมแอร์ 1.9 BILLET", "A/C Compressor Cover 1.9 BILLET", "อุปกรณ์แต่งห้องเครื่อง Billet", 1, "ชุด", 1800.0, 2200.0),
        (3, "MS-N-9004", "น็อตมู่เล่+แหวน เลส * 400", "น็อตมู่เล่+แหวน เลส", "Pulley Bolt & Washer Stainless", "มู่เล่และลูกรอก", 2, "ชิ้น", 280.0, 400.0),
        (3, "MS-B-9075", "ครอบคอมแอร์ BILLET. 3.0 2020 * 2400", "ครอบคอมแอร์ BILLET 3.0 2020", "A/C Compressor Cover BILLET 3.0 2020", "อุปกรณ์แต่งห้องเครื่อง Billet", 1, "ชุด", 2000.0, 2400.0),

        # ── Page 4 (1000014308.jpg) ──
        (4, "MS-B-9044-P4", "มู่เล่ปั๊มน้ำ BILLET * 2900", "มู่เล่ปั๊มน้ำ BILLET", "Water Pump Pulley BILLET", "มู่เล่และลูกรอก", 1, "ชิ้น", 2600.0, 2900.0),
        (4, "MS-B-9058", "มู่เล่เครื่อง D-max BILLET * 2200", "มู่เล่เครื่อง D-max BILLET", "Engine Crank Pulley D-max BILLET", "มู่เล่และลูกรอก", 1, "ชิ้น", 1800.0, 2200.0),
        (4, "MS-B-9047-P4", "มู่เล่ไดร์ชาร์จ Billet * 1800", "มู่เล่ไดร์ชาร์จ Billet", "Alternator Pulley Billet", "มู่เล่และลูกรอก", 1, "ชิ้น", 1400.0, 1800.0),
        (4, "MS-B-9097", "ลูกรอกสายพาน 1.9 BILLET * 2500", "ลูกรอกสายพาน 1.9 BILLET", "Belt Tensioner Pulley 1.9 BILLET", "มู่เล่และลูกรอก", 1, "ชุด", 2000.0, 2500.0),
        (4, "MS-I-9034", "ชุดอินเตอร์ 1.9 2020 งานดัด * 17999", "ชุดอินเตอร์คูลเลอร์ 1.9 2020 งานดัด", "Intercooler Kit 1.9 2020 Mandrel Bent", "ระบบอินเตอร์คูลเลอร์", 1, "ชุด", 15999.0, 17999.0),
        (4, "MS-I-9001", "ชุดอินเตอร์งานดัด REVO * 14500", "ชุดอินเตอร์คูลเลอร์งานดัด REVO", "Intercooler Kit REVO Mandrel Bent", "ระบบอินเตอร์คูลเลอร์", 1, "ชุด", 12000.0, 14500.0),
        (4, "MS-I-9017", "อะแดปเตอร์ Turbo REVO * 750", "อะแดปเตอร์ Turbo REVO", "Turbo Outlet Adapter REVO", "ระบบอินเตอร์คูลเลอร์", 1, "ชิ้น", 650.0, 750.0),
        (4, "MS-I-9018", "อะแดปเตอร์ ไอดี REVO * 850", "อะแดปเตอร์ ไอดี REVO", "Intake Manifold Adapter REVO", "ระบบอินเตอร์คูลเลอร์", 1, "ชิ้น", 750.0, 850.0),
        (4, "MS-I-9000", "ชุดอินเตอร์ 4JJ3 * 14500", "ชุดอินเตอร์คูลเลอร์ 4JJ3", "Intercooler Kit 4JJ3", "ระบบอินเตอร์คูลเลอร์", 1, "ชุด", 12000.0, 14500.0),
        (4, "MS-U-9017", "กรองอากาศ MS * 800", "กรองอากาศ MS High Flow", "MS High Flow Air Filter", "ของแต่งและอุปกรณ์เสริม", 3, "ชุด", 550.0, 800.0),
    ]

    total_amount = sum(row[6] * row[8] for row in items_data)
    print(f"Total calculated bill amount: ฿{total_amount:,.2f} across {len(items_data)} items")

    # ── 4. Create / Update PurchaseBill ──
    pb_items = []
    for (page_num, sku, raw_desc, clean_th, en, cat, qty, unit, cost, sell) in items_data:
        pb_items.append({
            "sku": sku,
            "name": clean_th,
            "qty": qty,
            "unit": unit,
            "unit_price": cost,
            "total": round(qty * cost, 2),
            "page": page_num,
            "bill_image": f"/static/uploads/bills/SO6908141_{page_num}.jpg"
        })

    pb = db.query(PurchaseBill).filter(PurchaseBill.bill_number == "SO6908141").first()
    if not pb:
        pb = PurchaseBill(
            supplier_id=supplier.id,
            bill_number="SO6908141",
            bill_date=datetime(2026, 8, 28, 10, 0),
            items=json.dumps(pb_items, ensure_ascii=False),
            total_amount=round(total_amount, 2),
            image_path="/static/uploads/bills/SO6908141_1.jpg",
            notes="ใบส่งสินค้าชั่วคราว เลขที่ SO6908141 (28/08/2569) 4 หน้า 70 รายการ รวม ฿241,159.00 (MS Billet / Monza)"
        )
        db.add(pb)
        db.commit()
        db.refresh(pb)
        print(f"Created PurchaseBill #{pb.id}: {pb.bill_number} (฿{pb.total_amount:,.2f})")
    else:
        pb.items = json.dumps(pb_items, ensure_ascii=False)
        pb.total_amount = round(total_amount, 2)
        pb.image_path = "/static/uploads/bills/SO6908141_1.jpg"
        db.commit()
        print(f"Updated PurchaseBill #{pb.id}: {pb.bill_number}")

    # ── 5. Insert / Update 70 Stock Items ──
    created_count = 0
    updated_count = 0

    for (page_num, sku, raw_desc, clean_th, en, cat, qty, unit, cost, sell) in items_data:
        bill_page_path = f"/static/uploads/bills/SO6908141_{page_num}.jpg"
        
        # Check existing item by SKU or exact name
        existing = db.query(StockItem).filter(
            (StockItem.sku == sku) | (StockItem.name_th == clean_th)
        ).first()

        if existing:
            q_before = existing.quantity
            existing.quantity += qty
            existing.unit_cost = cost
            if existing.sell_price == 0 or existing.sell_price < cost:
                existing.sell_price = sell
            existing.bill_path = bill_page_path
            db.commit()

            hist = StockHistory(
                stock_item_id=existing.id,
                change_type="in",
                delta=qty,
                quantity_before=q_before,
                quantity_after=existing.quantity,
                reason=f"เพิ่มสต็อกตามใบส่งสินค้า SO6908141 (หน้า {page_num})",
                changed_by="ระบบนำเข้าบิล (MS SO6908141)",
            )
            db.add(hist)
            db.commit()
            updated_count += 1
        else:
            new_item = StockItem(
                name_th=clean_th,
                name_en=en,
                sku=sku,
                category=cat,
                quantity=qty,
                unit_cost=cost,
                sell_price=sell,
                reorder_level=2,
                bill_path=bill_page_path,
                notes=f"นำเข้าจากใบส่งสินค้า MS เลขที่ SO6908141 หน้า {page_num} (28/08/2569)"
            )
            db.add(new_item)
            db.commit()
            db.refresh(new_item)

            hist = StockHistory(
                stock_item_id=new_item.id,
                change_type="in",
                delta=qty,
                quantity_before=0,
                quantity_after=qty,
                reason=f"นำเข้าอะไหล่ใหม่ตามใบส่งสินค้า SO6908141 หน้า {page_num}",
                changed_by="ระบบนำเข้าบิล (MS SO6908141)",
            )
            db.add(hist)
            db.commit()
            created_count += 1

    print(f"\nDone! Created: {created_count}, Updated: {updated_count}")
    print(f"Total stock items now in database: {db.query(StockItem).count()}")

if __name__ == "__main__":
    run_import()
