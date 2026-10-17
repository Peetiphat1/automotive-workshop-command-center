import sys
from datetime import datetime
from core.database import SessionLocal
from models.db_models import StockItem, StockHistory

db = SessionLocal()

# 1. Clean up bogus dummy item if present
bogus_items = db.query(StockItem).filter(StockItem.name_th.like('%this is not checking%')).all()
for b in bogus_items:
    print(f"Removing bogus item {b.id}: {b.name_th}")
    db.query(StockHistory).filter(StockHistory.stock_item_id == b.id).delete()
    db.delete(b)
db.commit()

# 2. List of 32 parts from invoice ORCM6908000203
# Supplier: ห้างหุ้นส่วนจำกัด สุวรรณการช่าง ทีทีเจ (SUWAN KARNCHANG TTJ Part., Ltd.)
parts_data = [
    {
        "sku": "1006045",
        "name_th": "เกจวัดบูส PPRC Pressure 45Psi",
        "name_en": "PPRC Boost Pressure Gauge 45Psi",
        "category": "เกจวัดและอุปกรณ์",
        "qty": 5,
        "unit": "Pcs.",
        "cost": 1750.0,
    },
    {
        "sku": "1006064",
        "name_th": "เกจวัดบูส PPRC Pressure 35 psi หน้าน้ำมัน 65M",
        "name_en": "PPRC Boost Gauge 35psi Oil Filled 65M",
        "category": "เกจวัดและอุปกรณ์",
        "qty": 2,
        "unit": "Pcs.",
        "cost": 1650.0,
    },
    {
        "sku": "1006065",
        "name_th": "เกจวัดบูส PPRC Blower Pressure 60psi หน้าน้ำมัน",
        "name_en": "PPRC Blower Pressure Gauge 60psi Oil Filled",
        "category": "เกจวัดและอุปกรณ์",
        "qty": 3,
        "unit": "Pcs.",
        "cost": 1650.0,
    },
    {
        "sku": "1006068",
        "name_th": "เกจวัดบูส PPRC Pressure 60Psi Limited หน้ามุก",
        "name_en": "PPRC Boost Gauge 60Psi Limited Pearl Dial",
        "category": "เกจวัดและอุปกรณ์",
        "qty": 1,
        "unit": "Pcs.",
        "cost": 2090.0,
    },
    {
        "sku": "1006069",
        "name_th": "เกจวัดบูส PPRC 60psi MonoGram หน้าทอง",
        "name_en": "PPRC Boost Gauge 60psi MonoGram Gold Dial",
        "category": "เกจวัดและอุปกรณ์",
        "qty": 1,
        "unit": "Pcs.",
        "cost": 2090.0,
    },
    {
        "sku": "6029692315",
        "name_th": "ขาวัดบูท ดำ+แหวนกด",
        "name_en": "Boost Gauge Bracket Black with Press Ring",
        "category": "ขายึดและอุปกรณ์ตกแต่ง",
        "qty": 5,
        "unit": "ชิ้น",
        "cost": 350.0,
    },
    {
        "sku": "6029692367",
        "name_th": "ขาวัดบูท เลส+แหวนกด",
        "name_en": "Boost Gauge Bracket Stainless with Press Ring",
        "category": "ขายึดและอุปกรณ์ตกแต่ง",
        "qty": 2,
        "unit": "ชิ้น",
        "cost": 350.0,
    },
    {
        "sku": "6029693105",
        "name_th": "ขาวัดบูท 52 mm. ดำ+แหวน",
        "name_en": "Boost Gauge Bracket 52mm Black with Ring",
        "category": "ขายึดและอุปกรณ์ตกแต่ง",
        "qty": 3,
        "unit": "ชิ้น",
        "cost": 350.0,
    },
    {
        "sku": "6029693182",
        "name_th": "ขาวัดบูท 52 mm. เลส+แหวน",
        "name_en": "Boost Gauge Bracket 52mm Stainless with Ring",
        "category": "ขายึดและอุปกรณ์ตกแต่ง",
        "qty": 2,
        "unit": "ชิ้น",
        "cost": 350.0,
    },
    {
        "sku": "2120768484-02",
        "name_th": "ฝาวาล์ว U2 ทำสี น้ำเงิน",
        "name_en": "Valve Cover U2 Painted Blue",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "Pcs.",
        "cost": 3500.0,
    },
    {
        "sku": "7101309802",
        "name_th": "หน้าเครื่องบน Dmax/All-New น้ำเงิน",
        "name_en": "Upper Timing Cover Dmax/All-New Blue",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 580.0,
    },
    {
        "sku": "71013010202",
        "name_th": "หน้าเครื่องล่าง U1-U4/1.9 3D น้ำเงิน",
        "name_en": "Lower Timing Cover U1-U4/1.9 3D Blue",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 520.0,
    },
    {
        "sku": "5408103602",
        "name_th": "วินข้อเหวี่ยง U1-3 + ดุมเหล็ก น้ำเงิน",
        "name_en": "Crankshaft Pulley U1-3 + Steel Hub Blue",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 4600.0,
    },
    {
        "sku": "5103407902",
        "name_th": "วินปั๊มน้ำ Dmax น้ำเงิน",
        "name_en": "Water Pump Pulley Dmax Blue",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 2500.0,
    },
    {
        "sku": "1203806802",
        "name_th": "ครอบคอมแอร์ Dmax/All-New billet น้ำเงิน",
        "name_en": "Billet A/C Compressor Cover Dmax/All-New Blue",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 2400.0,
    },
    {
        "sku": "6705809902",
        "name_th": "วินไดร์ชาร์จ U1-4/Vigo/Revo/1.9 น้ำเงิน+น็อต",
        "name_en": "Alternator Pulley U1-4/Vigo/Revo/1.9 Blue + Bolts",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 960.0,
    },
    {
        "sku": "3107105602",
        "name_th": "ลูกรอกสายพาน U1-4+น็อต billet น้ำเงิน",
        "name_en": "Billet Idler Pulley U1-4 + Bolts Blue",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 1200.0,
    },
    {
        "sku": "7309603302",
        "name_th": "แป้นคอน้ำบน Dmax/All-New/U4 น้ำเงิน",
        "name_en": "Upper Water Outlet Neck Dmax/All-New/U4 Blue",
        "category": "ระบบระบายความร้อน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 780.0,
    },
    {
        "sku": "2306806102",
        "name_th": "ครอบไอระบายเดิม U1-3 น้ำเงิน",
        "name_en": "Breather Cover OEM Style U1-3 Blue",
        "category": "ระบบระบายไอ",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 460.0,
    },
    {
        "sku": "2201309302",
        "name_th": "ฝาน้ำมันเครื่อง U1-4/1.9 billet น้ำเงิน",
        "name_en": "Billet Engine Oil Cap U1-4/1.9 Blue",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 460.0,
    },
    {
        "sku": "1277905688",
        "name_th": "สายระบาย AN10 ปลดไว ดำ",
        "name_en": "AN10 Quick-Release Breather Hose Black",
        "category": "ระบบระบายไอ",
        "qty": 2,
        "unit": "เส้น",
        "cost": 980.0,
    },
    {
        "sku": "2120768484-09",
        "name_th": "ฝาวาล์ว U2 ทำสี เงิน",
        "name_en": "Valve Cover U2 Painted Silver",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "Pcs.",
        "cost": 3500.0,
    },
    {
        "sku": "7101309809",
        "name_th": "หน้าเครื่องบน Dmax/All-New เงิน",
        "name_en": "Upper Timing Cover Dmax/All-New Silver",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 580.0,
    },
    {
        "sku": "71013010209",
        "name_th": "หน้าเครื่องล่าง U1-U4/1.9 3D เงิน",
        "name_en": "Lower Timing Cover U1-U4/1.9 3D Silver",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 520.0,
    },
    {
        "sku": "5408103609",
        "name_th": "วินข้อเหวี่ยง U1-3 + ดุมเหล็ก เงิน",
        "name_en": "Crankshaft Pulley U1-3 + Steel Hub Silver",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 4600.0,
    },
    {
        "sku": "5103407909",
        "name_th": "วินปั๊มน้ำ Dmax เงิน",
        "name_en": "Water Pump Pulley Dmax Silver",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 2500.0,
    },
    {
        "sku": "1203806809",
        "name_th": "ครอบคอมแอร์ Dmax/All-New billet เงิน",
        "name_en": "Billet A/C Compressor Cover Dmax/All-New Silver",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 2400.0,
    },
    {
        "sku": "6705809909",
        "name_th": "วินไดร์ชาร์จ U1-4/Vigo/Revo/1.9 เงิน+น็อต",
        "name_en": "Alternator Pulley U1-4/Vigo/Revo/1.9 Silver + Bolts",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 960.0,
    },
    {
        "sku": "3107105609",
        "name_th": "ลูกรอกสายพาน U1-4+น็อต billet เงิน",
        "name_en": "Billet Idler Pulley U1-4 + Bolts Silver",
        "category": "มู่เล่ย์และสายพาน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 1200.0,
    },
    {
        "sku": "7309603309",
        "name_th": "แป้นคอน้ำบน Dmax/All-New/U4 เงิน",
        "name_en": "Upper Water Outlet Neck Dmax/All-New/U4 Silver",
        "category": "ระบบระบายความร้อน",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 780.0,
    },
    {
        "sku": "2306806109",
        "name_th": "ครอบไอระบายเดิม U1-3 เงิน",
        "name_en": "Breather Cover OEM Style U1-3 Silver",
        "category": "ระบบระบายไอ",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 460.0,
    },
    {
        "sku": "2201309209",
        "name_th": "ฝาน้ำมันเครื่อง U1-4/1.9 เงิน",
        "name_en": "Billet Engine Oil Cap U1-4/1.9 Silver",
        "category": "ตกแต่งห้องเครื่องยนต์",
        "qty": 1,
        "unit": "ชิ้น",
        "cost": 460.0,
    },
]

total_imported = 0
total_updated = 0
grand_cost = 0

for item_info in parts_data:
    sku = item_info["sku"]
    name_th = item_info["name_th"]
    qty = item_info["qty"]
    cost = item_info["cost"]
    # 35% margin rounded to nearest 10 baht
    sell_price = round(cost * 1.35 / 10) * 10
    grand_cost += (cost * qty)

    # Check existing by SKU or exact name
    existing = db.query(StockItem).filter(
        (StockItem.sku == sku) | (StockItem.name_th == name_th)
    ).first()

    if existing:
        q_before = existing.quantity
        existing.quantity += qty
        existing.unit_cost = cost
        if existing.sell_price == 0 or existing.sell_price < cost:
            existing.sell_price = sell_price
        db.commit()

        hist = StockHistory(
            stock_item_id=existing.id,
            change_type="in",
            delta=qty,
            quantity_before=q_before,
            quantity_after=existing.quantity,
            reason="เพิ่มสต็อกตามใบเสร็จ หจก. สุวรรณการช่าง ทีทีเจ (ORCM6908000203)",
            changed_by="AI Copilot (ใบเสร็จรับเงิน)",
        )
        db.add(hist)
        db.commit()
        total_updated += 1
        print(f"Updated existing item #{existing.id} ({existing.sku}): {existing.name_th} (+{qty} -> {existing.quantity})")
    else:
        new_item = StockItem(
            name_th=name_th,
            name_en=item_info.get("name_en"),
            sku=sku,
            category=item_info["category"],
            quantity=qty,
            unit_cost=cost,
            sell_price=sell_price,
            reorder_level=1,
            notes="นำเข้าจากใบเสร็จ หจก. สุวรรณการช่าง ทีทีเจ เลขที่ ORCM6908000203 (27/08/2569)",
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
            reason="นำเข้าอะไหล่ใหม่ตามใบเสร็จ หจก. สุวรรณการช่าง ทีทีเจ (ORCM6908000203)",
            changed_by="AI Copilot (ใบเสร็จรับเงิน)",
        )
        db.add(hist)
        db.commit()
        total_imported += 1
        print(f"Created new item #{new_item.id} ({new_item.sku}): {new_item.name_th} (qty={qty}, cost=฿{cost}, sell=฿{sell_price})")

print(f"\nFinished! Total new items created: {total_imported}, Total existing items updated: {total_updated}")
print(f"Total parts on paper: {len(parts_data)}, Total paper cost calculated: ฿{grand_cost:,.2f}")
