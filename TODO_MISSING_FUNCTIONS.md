# 📋 Roadmap: สรุปรายการฟังก์ชันที่ขาดหายไปและแนวทางแก้ไข (Zero Garage)

บันทึกสรุปสำหรับตรวจสอบและกลับมาพัฒนาต่อ:

---

## 1. ✅ สิ่งที่ได้รับการแก้ไขและเตรียมพร้อมไว้แล้ว
1. **Vehicle Health Route (แก้บั๊ก 404)**:
   - เพิ่ม Route alias `@router.get("/customers/vehicles/{plate}/health")` ใน [routers/customers.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/routers/customers.py) เรียบร้อยแล้ว ระบบดึงข้อมูลรถอัตโนมัติตอนพิมพ์ทะเบียนในฟอร์มรับรถจะไม่เกิด Error 404
2. **Schema & Backend Service สำหรับแก้ใบแจ้งซ่อม**:
   - เพิ่ม `TicketUpdateRequest` ใน [models/schemas.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/models/schemas.py)
   - เพิ่มฟังก์ชัน `update_ticket()` ใน [services/ticket_service.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/services/ticket_service.py)
3. **Shortcut Script**:
   - [create_shortcut.ps1](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/create_shortcut.ps1) สร้าง Desktop Shortcut ไว้ที่หน้าจอ Desktop เรียบร้อย
4. **Unit Tests**:
   - ผ่านทั้งหมด 124/124 การทดสอบ

---

## 2. 📝 รายการที่ต้องต่อยอดในภายหลัง (To-Do Later)

### 1) เปิด Route PUT ให้ Ticket ใน Router
- **ไฟล์**: [routers/tickets.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/routers/tickets.py)
- **โค้ดที่ต้องเพิ่ม**:
  ```python
  from models.schemas import TicketUpdateRequest

  @router.put("/{ticket_id}", response_model=TicketResponse, summary="Update an existing ticket")
  def update_ticket(ticket_id: int, req: TicketUpdateRequest, db: Session = Depends(get_db)):
      return ticket_service.update_ticket(db, ticket_id, req)
  ```

### 2) UI ปุ่มและหน้าต่างแก้ไขใบแจ้งซ่อม (Edit Ticket Modal)
- **ไฟล์**: [static/index.html](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/static/index.html) & [static/chat.js](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/static/chat.js)
- เพิ่มปุ่ม `✏️ แก้ไข` ในตารางงานซ่อม ([`renderTicketActionsHtml`](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/static/chat.js#L589))
- เพิ่ม Modal `#edit-ticket-modal` และฟังก์ชัน `openEditTicketModal(id)` / `submitEditTicket()`

### 3) UI ปุ่มและหน้าต่างแก้ไขนัดหมาย (Edit Appointment Modal)
- **ไฟล์**: [static/index.html](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/static/index.html) & [static/chat.js](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/static/chat.js)
- Backend มี `PUT /api/v1/appointments/{id}` รองรับอยู่แล้วใน [routers/appointments.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/routers/appointments.py)
- เพิ่มปุ่ม `✏️ แก้ไข` ข้างปุ่มลบในหน้านัดหมาย และฟังก์ชัน `openEditAppointmentModal(id)` / `submitEditAppointment()`

### 4) ใบเบิกอะไหล่/งานซ่อมด่วน (Work Orders)
- **ไฟล์**: [routers/stock.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/routers/stock.py)
- เพิ่ม `PUT /api/v1/stock/work-orders/{id}` และ `DELETE /api/v1/stock/work-orders/{id}`

### 5) การยกเลิกบิลขายหน้าร้าน (Void / Cancel POS Sale)
- **ไฟล์**: [routers/stock.py](file:///c:/Users/Admin/Downloads/automotive-workshop-command-center%281%29/routers/stock.py)
- เพิ่ม `POST /api/v1/stock/pos/sales/{id}/void` คืนสต๊อกสินค้าเข้าคลังอัตโนมัติ
