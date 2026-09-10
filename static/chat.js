// ── Auto Service Command Center — chat.js v4.0.0 ──
const API_URL = '/api/v1';
const API_KEY = 'workshop-secret-2026';
const HEADERS = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };

let allTickets = [];
let allStock = [];
let allCustomers = [];
let allAppointments = [];
let allPurchases = [];
let allSuppliers = [];
let allExpenses = [];
let posCart = [];
let pendingTicketId = null;
let calYear = new Date().getFullYear();
let calMonth = new Date().getMonth(); // 0-based

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initApp();

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            toggleCopilot();
        }
    });

    // Set today's date as default in modals
    const today = new Date().toISOString().split('T')[0];
    const apptDateEl = document.getElementById('appt-date');
    if (apptDateEl) apptDateEl.value = today;
    const expDateEl = document.getElementById('expense-date');
    if (expDateEl) expDateEl.value = today;
});

async function initApp() {
    await Promise.all([
        fetchTicketsData(),
        fetchStockData(),
        fetchCustomersData(),
        fetchAppointments(),
        fetchWatchlist()
    ]);
}

// ── TAB SWITCHING ──
function switchTab(e, tabId) {
    if (e) e.preventDefault();

    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

    const selectedNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (selectedNav) selectedNav.classList.add('active');

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) targetTab.classList.add('active');

    lucide.createIcons();

    // Lazy load per tab
    if (tabId === 'appointments') renderCalendar();
    if (tabId === 'suppliers') loadSuppliers();
    if (tabId === 'purchases') loadPurchases();
    if (tabId === 'reports') loadReports();
    if (tabId === 'expenses') loadExpenses();
    if (tabId === 'stock') loadStockHistory();
    if (tabId === 'pos') loadPOSHistory();
}

// ── DATA FETCHING ──
async function fetchTicketsData() {
    try {
        const res = await fetch(`${API_URL}/tickets/`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();
        allTickets = data.items || data || [];
        renderDashboardStats();
        renderTicketsTable();
        renderFullRepairsTable();
    } catch (err) { console.error('Fetch tickets error:', err); }
}

async function fetchStockData() {
    try {
        const res = await fetch(`${API_URL}/stock/`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();
        allStock = (Array.isArray(data) ? data : (data.items || [])).map(s => ({
            ...s,
            name: s.name_th || s.name_en || s.name || 'ไม่ระบุ',
            price: s.sell_price || s.price || 0,
            cost: s.unit_cost || s.cost || 0,
            code: s.sku || s.code || '',
            unit: s.unit || 'ชิ้น',
        }));
        renderStockTable();
        renderQuickStock();
    } catch (err) { console.error('Fetch stock error:', err); }
}

async function fetchCustomersData() {
    try {
        const res = await fetch(`${API_URL}/customers/`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();
        allCustomers = data.items || data || [];
        renderCustomersTable();
    } catch (err) { console.error('Fetch customers error:', err); }
}

async function fetchAppointments() {
    try {
        const res = await fetch(`${API_URL}/appointments/`, { headers: HEADERS });
        if (!res.ok) return;
        allAppointments = await res.json();
        updateApptKpi();
    } catch (err) { console.error('Fetch appointments error:', err); }
}

async function fetchWatchlist() {
    const container = document.getElementById('watchlist-container');
    if (!container) return;
    try {
        const res = await fetch(`${API_URL}/customers/1/profile`, { headers: HEADERS });
        if (!res.ok) throw new Error('Failed');
        const profile = await res.json();
        const watchlist = [];
        (profile.vehicles || []).forEach(v => {
            (v.health_watchlist || []).forEach(w => {
                watchlist.push({ ...w, vehicle_plate: v.plate, car_brand: v.brand });
            });
        });
        if (watchlist.length === 0) {
            container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">ไม่มีรายการเตือนภัย</p>`;
            return;
        }
        container.innerHTML = watchlist.slice(0, 5).map(w => `
            <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.82rem;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <strong style="color:${w.is_overdue ? '#f87171' : '#34d399'}">${w.component}</strong>
                    <div style="font-size:0.72rem;color:var(--text-muted);">${w.vehicle_plate} — ${w.condition}</div>
                </div>
                <span class="pill ${w.is_overdue ? 'danger' : ''}">${w.is_overdue ? 'เกินกำหนด' : 'ปกติ'}</span>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">ไม่สามารถโหลด Watchlist ได้</p>`;
    }
}

// ── DASHBOARD ──
function renderDashboardStats() {
    const pendingCount = allTickets.filter(t => t.status === 'PENDING_MECHANIC_APPROVAL').length;
    const activeCount = allTickets.filter(t => t.status === 'APPROVED' || t.status === 'PENDING_MECHANIC_APPROVAL').length;
    const totalRev = allTickets.reduce((acc, t) => acc + (t.final_cost || t.total_estimated_cost || 0), 0);

    const el = id => document.getElementById(id);
    if (el('kpi-revenue')) el('kpi-revenue').innerText = `฿${totalRev.toLocaleString('th-TH')}`;
    if (el('kpi-active-repairs')) el('kpi-active-repairs').innerText = `${activeCount} คัน`;
    if (el('kpi-pending-approval')) el('kpi-pending-approval').innerText = `รอช่างอนุมัติ ${pendingCount} คัน`;
    if (el('badge-repairs')) el('badge-repairs').innerText = activeCount;

    const lowStockCount = allStock.filter(s => s.quantity <= s.reorder_level).length;
    if (el('kpi-low-stock')) el('kpi-low-stock').innerText = `${lowStockCount} รายการ`;
    if (el('badge-stock-warn')) el('badge-stock-warn').innerText = lowStockCount;
}

function updateApptKpi() {
    const today = new Date().toDateString();
    const todayAppts = allAppointments.filter(a => {
        const d = new Date(a.appointment_date);
        return d.toDateString() === today;
    });
    const el = document.getElementById('kpi-appointments');
    if (el) el.innerText = `${todayAppts.length} นัด`;
}

function statusBadgeHtml(status) {
    const map = {
        'PENDING_MECHANIC_APPROVAL': '<span class="status-badge pending">⏳ รออนุมัติ</span>',
        'APPROVED': '<span class="status-badge approved">🟢 กำลังซ่อม</span>',
        'COMPLETED': '<span class="status-badge" style="background:rgba(16,185,129,0.2);color:#34d399;">✅ เสร็จสิ้น</span>',
        'CANCELLED': '<span class="status-badge" style="background:rgba(100,116,139,0.2);color:#94a3b8;">❌ ยกเลิก</span>',
    };
    return map[status] || `<span class="status-badge draft">${status}</span>`;
}

function renderTicketsTable(statusFilter = 'all') {
    const tbody = document.getElementById('tickets-tbody');
    if (!tbody) return;
    let filtered = statusFilter === 'all' ? allTickets : allTickets.filter(t => t.status === statusFilter);
    if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่พบข้อมูลงานซ่อม</td></tr>`;
        return;
    }
    tbody.innerHTML = filtered.map(t => {
        const cost = (t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH');
        return `<tr>
            <td><strong style="color:#93c5fd;">#${t.id}</strong></td>
            <td><strong>${t.vehicle_plate || 'ไม่ระบุ'}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${t.car_model || ''}</div></td>
            <td>${t.customer_name || 'ลูกค้าทั่วไป'}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-secondary);">${t.raw_input || '—'}</td>
            <td style="color:#34d399;font-weight:600;">฿${cost}</td>
            <td>${statusBadgeHtml(t.status)}</td>
            <td>${t.status === 'PENDING_MECHANIC_APPROVAL'
                ? `<button class="btn-primary" style="padding:4px 10px;font-size:0.75rem;" onclick="openApproveModal(${t.id})">✓ อนุมัติ</button>`
                : `<a href="/track?q=${t.id}" target="_blank" class="btn-sm" style="text-decoration:none;">ดูสถานะ</a>`
            }</td>
        </tr>`;
    }).join('');
    lucide.createIcons();
}

function renderFullRepairsTable() {
    const container = document.getElementById('full-repairs-table-container');
    if (!container) return;
    if (!allTickets.length) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:30px;">ยังไม่มีงานซ่อม</p>`;
        return;
    }
    container.innerHTML = `
        <div class="table-responsive">
            <table class="data-table">
                <thead><tr><th>Ticket #</th><th>ทะเบียน / รุ่น</th><th>ลูกค้า</th><th>รายการ</th><th>ราคา</th><th>สถานะ</th><th>วันที่</th><th>จัดการ</th></tr></thead>
                <tbody>${allTickets.map(t => {
                    const cost = (t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH');
                    const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString('th-TH') : '—';
                    return `<tr>
                        <td><strong style="color:#93c5fd;">#${t.id}</strong></td>
                        <td><strong>${t.vehicle_plate || 'ไม่ระบุ'}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${t.car_model || ''}</div></td>
                        <td>${t.customer_name || 'ลูกค้าทั่วไป'}</td>
                        <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.raw_input || '—'}</td>
                        <td style="color:#34d399;font-weight:600;">฿${cost}</td>
                        <td>${statusBadgeHtml(t.status)}</td>
                        <td style="color:var(--text-muted);font-size:0.8rem;">${dateStr}</td>
                        <td>${t.status === 'PENDING_MECHANIC_APPROVAL'
                            ? `<button class="btn-primary" style="padding:4px 10px;font-size:0.75rem;" onclick="openApproveModal(${t.id})">✓ อนุมัติ</button>`
                            : `<a href="/track?q=${t.id}" target="_blank" class="btn-sm" style="text-decoration:none;">ดูสถานะ</a>`
                        }</td>
                    </tr>`;
                }).join('')}</tbody>
            </table>
        </div>`;
}

function filterDashTickets(btn, status) {
    document.querySelectorAll('.table-filter-pills .pill').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    renderTicketsTable(status);
}

// ── QUICK STOCK ──
function renderQuickStock() {
    const container = document.getElementById('quick-stock-container');
    if (!container) return;
    const lowItems = allStock.filter(s => s.quantity <= s.reorder_level);
    const displayItems = lowItems.length > 0 ? lowItems.slice(0, 5) : allStock.slice(0, 5);
    if (!displayItems.length) { container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">ไม่มีข้อมูลสต๊อก</p>`; return; }
    container.innerHTML = displayItems.map(s => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.82rem;">
            <div><strong>${s.name}</strong><div style="font-size:0.75rem;color:var(--text-muted);">฿${(s.price||0).toLocaleString('th-TH')}</div></div>
            <span class="pill ${s.quantity <= s.reorder_level ? 'danger' : ''}">${s.quantity} ${s.unit}</span>
        </div>
    `).join('');
}

// ── STOCK TABLE + HISTORY ──
function renderStockTable() {
    const tbody = document.getElementById('stock-tbody');
    if (!tbody) return;
    if (!allStock.length) { tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่มีข้อมูลสต๊อก</td></tr>`; return; }
    tbody.innerHTML = allStock.map(s => `
        <tr>
            <td><code style="background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;font-size:0.78rem;">${s.code}</code></td>
            <td><strong>${s.name}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${s.name_en || ''}</div></td>
            <td><span class="pill">${s.category || '—'}</span></td>
            <td>฿${(s.cost||0).toLocaleString('th-TH')}</td>
            <td style="color:#34d399;font-weight:600;">฿${(s.price||0).toLocaleString('th-TH')}</td>
            <td><strong>${s.quantity}</strong> ${s.unit}</td>
            <td>${s.quantity <= s.reorder_level ? '<span class="status-badge pending">⚠️ ควรสั่งซื้อ</span>' : '<span class="status-badge approved">✓ ปกติ</span>'}</td>
            <td><button class="btn-sm" onclick="quickAdjustStock(${s.id},'${s.name}')">ปรับสต็อก</button></td>
        </tr>
    `).join('');
}

async function quickAdjustStock(id, name) {
    const delta = prompt(`ปรับจำนวน "${name}"\nพิมพ์ + หรือ - เช่น +10 หรือ -3:`, '+1');
    if (!delta) return;
    const num = parseInt(delta.replace('+', ''));
    if (isNaN(num)) return showToast('รูปแบบไม่ถูกต้อง');
    const reason = prompt('เหตุผลในการปรับ:', 'ปรับสต็อกด้วยตนเอง') || '';
    try {
        const res = await fetch(`${API_URL}/stock/${id}/adjust`, {
            method: 'PUT', headers: HEADERS,
            body: JSON.stringify({ delta: num, reason, changed_by: 'ผู้จัดการ' })
        });
        if (!res.ok) throw new Error('Failed');
        showToast(`✅ ปรับสต็อก "${name}" ${num > 0 ? '+' : ''}${num} เรียบร้อย`);
        fetchStockData();
        loadStockHistory();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

async function loadStockHistory() {
    const container = document.getElementById('stock-history-list');
    if (!container) return;
    try {
        const res = await fetch(`${API_URL}/stock/history/all?limit=30`, { headers: HEADERS });
        if (!res.ok) throw new Error();
        const history = await res.json();
        if (!history.length) {
            container.innerHTML = `<p style="color:var(--text-muted);padding:16px;text-align:center;">ยังไม่มีประวัติการเปลี่ยนแปลง</p>`;
            return;
        }
        container.innerHTML = `<div class="table-responsive"><table class="data-table">
            <thead><tr><th>วันที่/เวลา</th><th>รายการ</th><th>ประเภท</th><th>การเปลี่ยนแปลง</th><th>ก่อน</th><th>หลัง</th><th>เหตุผล</th><th>บันทึกโดย</th></tr></thead>
            <tbody>${history.map(h => `
                <tr>
                    <td style="font-size:0.78rem;color:var(--text-muted);">${h.created_at ? new Date(h.created_at).toLocaleString('th-TH') : '—'}</td>
                    <td><strong>${h.item_name}</strong><div style="font-size:0.72rem;color:var(--text-muted);">${h.item_sku || ''}</div></td>
                    <td><span class="pill">${h.change_type}</span></td>
                    <td><span class="delta-badge ${h.delta >= 0 ? 'pos' : 'neg'}">${h.delta >= 0 ? '+' : ''}${h.delta}</span></td>
                    <td style="color:var(--text-muted);">${h.quantity_before}</td>
                    <td style="font-weight:700;">${h.quantity_after}</td>
                    <td style="color:var(--text-secondary);font-size:0.8rem;">${h.reason || '—'}</td>
                    <td style="font-size:0.8rem;">${h.changed_by}</td>
                </tr>
            `).join('')}</tbody>
        </table></div>`;
    } catch {
        container.innerHTML = `<p style="color:var(--text-muted);padding:16px;text-align:center;">ไม่สามารถโหลดประวัติได้</p>`;
    }
}

// ── CUSTOMERS 360° ──
async function renderCustomersTable() {
    const tbody = document.getElementById('customers-tbody');
    if (!tbody) return;
    if (!allCustomers.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่มีข้อมูลลูกค้า</td></tr>`;
        return;
    }
    tbody.innerHTML = allCustomers.map(c => `
        <tr id="cust-row-${c.id}">
            <td><strong>${c.name}</strong></td>
            <td>${c.phone || '—'}</td>
            <td>${c.line_id || '—'}</td>
            <td><span style="color:var(--text-muted);">กำลังโหลด...</span></td>
            <td><span style="color:var(--text-muted);">—</span></td>
            <td><span style="color:var(--text-muted);">—</span></td>
            <td><button class="btn-primary" style="padding:4px 12px;font-size:0.78rem;" onclick="viewCustomerProfile(${c.id})">ดู 360°</button></td>
        </tr>
    `).join('');

    // Load profile details per customer
    allCustomers.forEach(async c => {
        try {
            const res = await fetch(`${API_URL}/customers/${c.id}/profile`, { headers: HEADERS });
            if (!res.ok) return;
            const profile = await res.json();
            const vehicles = profile.vehicles || [];
            const tickets = profile.ticket_history || [];
            const row = document.getElementById(`cust-row-${c.id}`);
            if (row) {
                const cells = row.querySelectorAll('td');
                cells[3].innerHTML = `<strong style="color:#60a5fa;">${vehicles.length} คัน</strong>`;
                cells[4].innerHTML = vehicles[0] ? `<span class="pill">${vehicles[0].plate}</span>` : '—';
                cells[5].innerHTML = `${tickets.length} ครั้ง`;
            }
        } catch {}
    });
}

async function viewCustomerProfile(id) {
    try {
        const res = await fetch(`${API_URL}/customers/${id}/profile`, { headers: HEADERS });
        const profile = await res.json();
        const c = profile.customer;
        const vehicles = profile.vehicles || [];
        const tickets = profile.ticket_history || [];
        const totalSpent = tickets.reduce((acc, t) => acc + (t.final_cost || t.total_estimated_cost || 0), 0);

        document.getElementById('profile-modal-name').textContent = `👤 ${c.name}`;
        document.getElementById('profile-modal-sub').textContent = `📞 ${c.phone || '—'}  |  LINE: ${c.line_id || '—'}  |  📧 ${c.email || '—'}`;

        document.getElementById('profile-stats').innerHTML = `
            <div class="profile-stat-card"><div class="val">${vehicles.length}</div><div class="lbl">จำนวนรถ</div></div>
            <div class="profile-stat-card"><div class="val">${tickets.length}</div><div class="lbl">งานซ่อมทั้งหมด</div></div>
            <div class="profile-stat-card"><div class="val">฿${totalSpent.toLocaleString('th-TH')}</div><div class="lbl">ยอดใช้จ่ายทั้งหมด</div></div>
        `;

        document.getElementById('profile-cars').innerHTML = vehicles.map(v => `
            <div class="profile-car-chip">
                <i data-lucide="car" style="width:14px;height:14px;"></i>
                <strong>${v.plate}</strong> — ${v.brand} ${v.model} (${v.year || '—'})
                <span style="font-size:0.72rem;color:var(--text-muted);">${(v.current_mileage||0).toLocaleString()} กม.</span>
            </div>
        `).join('');

        document.getElementById('profile-history-tbody').innerHTML = tickets.length
            ? tickets.map(t => `
                <tr>
                    <td style="color:#93c5fd;">#${t.id}</td>
                    <td style="font-size:0.78rem;color:var(--text-muted);">${t.created_at ? new Date(t.created_at).toLocaleDateString('th-TH') : '—'}</td>
                    <td>${t.vehicle_plate || '—'}</td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.raw_input || '—'}</td>
                    <td style="color:#34d399;font-weight:600;">฿${(t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH')}</td>
                    <td>${statusBadgeHtml(t.status)}</td>
                </tr>
            `).join('')
            : `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:12px;">ยังไม่มีประวัติงานซ่อม</td></tr>`;

        document.getElementById('profile-modal').style.display = 'flex';
        lucide.createIcons();
    } catch { showToast('❌ ไม่สามารถโหลดข้อมูลลูกค้าได้'); }
}

function closeProfileModal() {
    document.getElementById('profile-modal').style.display = 'none';
}

// ── CALENDAR ──
const DAY_LABELS = ['อา', 'จ', 'อ', 'พ', 'พฤ', 'ศ', 'ส'];
const MONTH_NAMES_TH = ['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];

function changeCalMonth(delta) {
    calMonth += delta;
    if (calMonth > 11) { calMonth = 0; calYear++; }
    if (calMonth < 0) { calMonth = 11; calYear--; }
    renderCalendar();
}

function renderCalendar() {
    const labelsEl = document.getElementById('cal-day-labels');
    const gridEl = document.getElementById('cal-grid');
    const labelEl = document.getElementById('cal-month-label');
    if (!gridEl) return;

    labelEl.textContent = `${MONTH_NAMES_TH[calMonth]} ${calYear + 543}`;

    // Day labels
    if (labelsEl) {
        labelsEl.innerHTML = DAY_LABELS.map(d => `<div class="cal-day-label">${d}</div>`).join('');
    }

    const firstDay = new Date(calYear, calMonth, 1).getDay();
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const prevDays = new Date(calYear, calMonth, 0).getDate();
    const today = new Date();

    let cells = '';
    // Prev month days
    for (let i = firstDay - 1; i >= 0; i--) {
        cells += `<div class="cal-day other-month"><div class="day-num">${prevDays - i}</div></div>`;
    }
    // This month days
    for (let d = 1; d <= daysInMonth; d++) {
        const isToday = today.getDate() === d && today.getMonth() === calMonth && today.getFullYear() === calYear;
        const dateStr = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const dayAppts = allAppointments.filter(a => {
            const ad = new Date(a.appointment_date);
            return ad.getFullYear() === calYear && ad.getMonth() === calMonth && ad.getDate() === d;
        });
        const chipsHtml = dayAppts.slice(0, 3).map(a =>
            `<div class="cal-appt-chip ${a.status}" onclick="showDayAppts('${dateStr}', event)" title="${a.customer_name}: ${a.service_type || ''}">${a.time_slot || ''} ${a.customer_name}</div>`
        ).join('');
        cells += `<div class="cal-day${isToday ? ' today' : ''}" onclick="showDayAppts('${dateStr}', event)">
            <div class="day-num">${d}</div>
            ${chipsHtml}
            ${dayAppts.length > 3 ? `<div style="font-size:0.65rem;color:var(--text-muted);margin-top:2px;">+${dayAppts.length - 3} เพิ่มเติม</div>` : ''}
        </div>`;
    }
    gridEl.innerHTML = cells;
}

function showDayAppts(dateStr, e) {
    if (e) e.stopPropagation();
    const card = document.getElementById('appt-day-card');
    const titleEl = document.getElementById('appt-day-title');
    const listEl = document.getElementById('appt-day-list');
    if (!card) return;

    const dayAppts = allAppointments.filter(a => {
        const ad = new Date(a.appointment_date);
        const aStr = `${ad.getFullYear()}-${String(ad.getMonth()+1).padStart(2,'0')}-${String(ad.getDate()).padStart(2,'0')}`;
        return aStr === dateStr;
    });

    const [y, m, d] = dateStr.split('-');
    const dateLabel = new Date(dateStr).toLocaleDateString('th-TH', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
    titleEl.innerHTML = `<i data-lucide="calendar-check"></i> นัดหมาย ${dateLabel}`;

    if (!dayAppts.length) {
        listEl.innerHTML = `<p style="color:var(--text-muted);padding:16px;text-align:center;">ไม่มีนัดหมายในวันนี้</p>`;
    } else {
        listEl.innerHTML = dayAppts.map(a => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border);">
                <div>
                    <div style="font-weight:700;">${a.time_slot || '—'} น. — <span style="color:#60a5fa;">${a.customer_name}</span></div>
                    <div style="font-size:0.82rem;color:var(--text-muted);margin-top:2px;">${a.vehicle_plate || ''} ${a.vehicle_info || ''} | ${a.service_type || ''}</div>
                    ${a.customer_phone ? `<div style="font-size:0.78rem;color:var(--text-muted);">📞 ${a.customer_phone}</div>` : ''}
                </div>
                <span class="cal-appt-chip ${a.status}" style="font-size:0.75rem;padding:4px 10px;">${
                    {confirmed:'✅ ยืนยัน', pending:'⏳ รอยืนยัน', completed:'🏁 เสร็จสิ้น', cancelled:'❌ ยกเลิก'}[a.status] || a.status
                }</span>
            </div>
        `).join('');
    }

    card.style.display = 'block';
    lucide.createIcons();
    card.scrollIntoView({ behavior: 'smooth' });
}

// ── SUPPLIERS ──
async function loadSuppliers() {
    const grid = document.getElementById('supplier-grid');
    if (!grid) return;
    try {
        const res = await fetch(`${API_URL}/suppliers/`, { headers: HEADERS });
        if (!res.ok) throw new Error();
        allSuppliers = await res.json();
        if (!allSuppliers.length) {
            grid.innerHTML = `<p style="color:var(--text-muted);padding:20px;">ยังไม่มีผู้จำหน่าย</p>`;
            return;
        }
        grid.innerHTML = allSuppliers.map(s => `
            <div class="supplier-card">
                <div class="sup-name">🏭 ${s.name}</div>
                ${s.phone ? `<div class="sup-info"><i data-lucide="phone" style="width:13px;height:13px;"></i> ${s.phone}</div>` : ''}
                ${s.email ? `<div class="sup-info"><i data-lucide="mail" style="width:13px;height:13px;"></i> ${s.email}</div>` : ''}
                ${s.line_id ? `<div class="sup-info"><i data-lucide="message-circle" style="width:13px;height:13px;"></i> LINE: ${s.line_id}</div>` : ''}
                ${s.address ? `<div class="sup-info" style="font-size:0.75rem;"><i data-lucide="map-pin" style="width:12px;height:12px;"></i> ${s.address}</div>` : ''}
                <div class="sup-stats">
                    <div class="sup-stat"><div class="n">${s.total_purchases || 0}</div><div class="l">ใบสั่งซื้อ</div></div>
                    <div class="sup-stat"><div class="n">฿${(s.total_amount || 0).toLocaleString('th-TH')}</div><div class="l">ยอดซื้อรวม</div></div>
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch {
        grid.innerHTML = `<p style="color:var(--text-muted);padding:20px;">ไม่สามารถโหลดข้อมูลได้</p>`;
    }
}

// ── PURCHASES HISTORY ──
async function loadPurchases() {
    const tbody = document.getElementById('purchases-tbody');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_URL}/suppliers/purchases/all`, { headers: HEADERS });
        if (!res.ok) throw new Error();
        allPurchases = await res.json();
        if (!allPurchases.length) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">ยังไม่มีประวัติการจัดซื้อ</td></tr>`;
            return;
        }
        tbody.innerHTML = allPurchases.map(b => `
            <tr>
                <td><strong style="color:#93c5fd;">${b.bill_number || '#' + b.id}</strong></td>
                <td style="font-size:0.82rem;color:var(--text-muted);">${b.bill_date ? new Date(b.bill_date).toLocaleDateString('th-TH') : '—'}</td>
                <td><strong>${b.supplier_name || 'ไม่ระบุ'}</strong></td>
                <td style="font-size:0.8rem;color:var(--text-secondary);">${(b.items || []).map(i => `${i.name} (${i.qty})`).join(', ') || '—'}</td>
                <td style="color:#34d399;font-weight:700;">฿${(b.total_amount || 0).toLocaleString('th-TH')}</td>
                <td style="font-size:0.8rem;color:var(--text-muted);">${b.notes || '—'}</td>
            </tr>
        `).join('');
    } catch {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

// ── POS HISTORY ──
let posHistoryFilter = 'all';
async function loadPOSHistory() {
    const tbody = document.getElementById('pos-history-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">กำลังโหลด...</td></tr>`;
    try {
        // Combine purchases and work orders for a full parts history
        const [purchRes, woRes] = await Promise.all([
            fetch(`${API_URL}/suppliers/purchases/all`, { headers: HEADERS }),
            fetch(`${API_URL}/stock/workorders/`, { headers: HEADERS }),
        ]);
        const purchases = purchRes.ok ? await purchRes.json() : [];
        const workorders = woRes.ok ? await woRes.json() : [];

        let rows = [];
        // Purchase rows
        purchases.forEach(b => {
            (b.items || []).forEach(item => {
                rows.push({
                    type: 'purchase',
                    date: b.bill_date,
                    label: '📦 จัดซื้อ',
                    name: item.name,
                    qty: item.qty,
                    unit_price: item.unit_price,
                    total: item.total,
                    ref: `บิล ${b.bill_number || '#' + b.id} (${b.supplier_name || 'ไม่ระบุ'})`
                });
            });
        });
        // Work order rows
        workorders.forEach(wo => {
            const items = wo.line_items ? (typeof wo.line_items === 'string' ? JSON.parse(wo.line_items) : wo.line_items) : [];
            items.filter(i => i.name && !i.name.includes('Labor') && !i.name.includes('ค่าแรง')).forEach(item => {
                rows.push({
                    type: 'repair',
                    date: wo.created_at,
                    label: '🔧 ใช้ซ่อม',
                    name: item.name,
                    qty: item.qty,
                    unit_price: item.unit_price,
                    total: item.total,
                    ref: `Work Order #${wo.id} (${wo.vehicle_plate || '—'})`
                });
            });
        });

        // Filter
        if (posHistoryFilter !== 'all') {
            rows = rows.filter(r => r.type === posHistoryFilter);
        }
        rows.sort((a, b) => new Date(b.date) - new Date(a.date));

        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่มีประวัติ</td></tr>`;
            return;
        }
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td style="font-size:0.78rem;color:var(--text-muted);">${r.date ? new Date(r.date).toLocaleDateString('th-TH') : '—'}</td>
                <td><span class="pill">${r.label}</span></td>
                <td><strong>${r.name}</strong></td>
                <td style="text-align:center;">${r.qty}</td>
                <td>฿${(r.unit_price||0).toLocaleString('th-TH')}</td>
                <td style="color:#34d399;font-weight:600;">฿${(r.total||0).toLocaleString('th-TH')}</td>
                <td style="font-size:0.78rem;color:var(--text-muted);">${r.ref}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

function filterPOSHistory(btn, filter) {
    posHistoryFilter = filter;
    document.querySelectorAll('.pos-history-filter .pill').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    loadPOSHistory();
}

// ── REPORTS ──
async function loadReports() {
    const grid = document.getElementById('reports-grid');
    if (!grid) return;
    try {
        const now = new Date();
        const [y, m] = [now.getFullYear(), now.getMonth() + 1];
        const res = await fetch(`${API_URL}/finance/summary/${y}/${m}`, { headers: HEADERS });
        let summary = null;
        if (res.ok) { const d = await res.json(); summary = d.summary; }

        const income = summary?.total_income || 47500;
        const expense = summary?.total_expense || 28350;
        const profit = summary?.net_profit || (income - expense);
        const maxVal = Math.max(income, expense, 100000);

        // KPI cards + category breakdown
        grid.innerHTML = `
            <div class="report-card">
                <div class="report-card-header">
                    <div class="report-card-title"><i data-lucide="trending-up" style="color:#34d399;width:18px;height:18px;"></i> รายรับรวม</div>
                    <strong style="color:#34d399;font-size:1.1rem;">฿${income.toLocaleString('th-TH')}</strong>
                </div>
                <div class="report-bar"><div class="report-bar-fill income" style="width:${(income/maxVal*100).toFixed(0)}%"></div></div>
                <div class="report-row"><span class="lbl">ค่าซ่อมรถ</span><span class="val green">฿${(income*0.75).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',')} </span></div>
                <div class="report-row"><span class="lbl">ขายอะไหล่</span><span class="val green">฿${(income*0.25).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}</span></div>
            </div>
            <div class="report-card">
                <div class="report-card-header">
                    <div class="report-card-title"><i data-lucide="trending-down" style="color:#f87171;width:18px;height:18px;"></i> รายจ่ายรวม</div>
                    <strong style="color:#f87171;font-size:1.1rem;">฿${expense.toLocaleString('th-TH')}</strong>
                </div>
                <div class="report-bar"><div class="report-bar-fill expense" style="width:${(expense/maxVal*100).toFixed(0)}%"></div></div>
                <div class="report-row"><span class="lbl">ซื้ออะไหล่</span><span class="val red">฿${(expense*0.63).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}</span></div>
                <div class="report-row"><span class="lbl">ค่าน้ำ/ไฟ/เช่า</span><span class="val red">฿${(expense*0.37).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}</span></div>
            </div>
            <div class="report-card">
                <div class="report-card-header">
                    <div class="report-card-title"><i data-lucide="circle-dollar-sign" style="color:#60a5fa;width:18px;height:18px;"></i> กำไรสุทธิ</div>
                    <strong style="${profit >= 0 ? 'color:#60a5fa' : 'color:#f87171'};font-size:1.1rem;">฿${profit.toLocaleString('th-TH')}</strong>
                </div>
                <div class="report-bar"><div class="report-bar-fill profit" style="width:${Math.min(100,(profit/income*100)).toFixed(0)}%"></div></div>
                <div class="report-row"><span class="lbl">Gross Margin</span><span class="val blue">${((profit/income)*100).toFixed(1)}%</span></div>
                <div class="report-row"><span class="lbl">เดือนนี้ (${MONTH_NAMES_TH[now.getMonth()]})</span><span class="val ${profit>=0?'green':'red'}">${profit>=0?'📈 กำไร':'📉 ขาดทุน'}</span></div>
            </div>
            <div class="report-card">
                <div class="report-card-header">
                    <div class="report-card-title"><i data-lucide="wrench" style="color:#fbbf24;width:18px;height:18px;"></i> งานซ่อม</div>
                    <strong style="color:#fbbf24;font-size:1.1rem;">${allTickets.length} งาน</strong>
                </div>
                <div class="report-bar"><div class="report-bar-fill" style="width:100%;background:linear-gradient(90deg,#f59e0b,#fbbf24);"></div></div>
                <div class="report-row"><span class="lbl">เสร็จสิ้น</span><span class="val">${allTickets.filter(t=>t.status==='COMPLETED').length} งาน</span></div>
                <div class="report-row"><span class="lbl">รออนุมัติ</span><span class="val">${allTickets.filter(t=>t.status==='PENDING_MECHANIC_APPROVAL').length} งาน</span></div>
            </div>
        `;
        lucide.createIcons();
    } catch {
        grid.innerHTML = `<p style="color:var(--text-muted);padding:20px;">ไม่สามารถโหลดรายงานได้</p>`;
    }
}

// ── EXPENSES ──
async function loadExpenses() {
    const tbody = document.getElementById('expenses-tbody');
    const catGrid = document.getElementById('expense-cat-grid');
    const totalBadge = document.getElementById('expense-total-badge');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_URL}/expenses/`, { headers: HEADERS });
        if (!res.ok) throw new Error();
        const data = await res.json();
        allExpenses = data.items || [];
        const total = data.total || 0;
        if (totalBadge) totalBadge.textContent = `฿${total.toLocaleString('th-TH')}`;

        // Category summary cards
        const catMap = {};
        allExpenses.forEach(e => {
            catMap[e.category] = (catMap[e.category] || 0) + e.amount;
        });
        const catIcons = { 'ค่าไฟฟ้า':'⚡', 'ค่าน้ำประปา':'💧', 'ค่าเช่า':'🏠', 'ค่าอินเทอร์เน็ต':'🌐', 'อื่นๆ':'📦' };
        if (catGrid) {
            catGrid.innerHTML = Object.entries(catMap).map(([cat, amt]) => `
                <div class="expense-cat-card">
                    <div class="expense-cat-icon" style="background:rgba(59,130,246,0.15);">${catIcons[cat] || '📂'}</div>
                    <div>
                        <div style="font-weight:700;font-size:0.9rem;">${cat}</div>
                        <div style="color:#34d399;font-weight:700;font-size:1.05rem;">฿${amt.toLocaleString('th-TH')}</div>
                    </div>
                </div>
            `).join('');
        }

        if (!allExpenses.length) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">ยังไม่มีรายการค่าใช้จ่าย</td></tr>`;
            return;
        }
        tbody.innerHTML = allExpenses.map(e => `
            <tr>
                <td style="font-size:0.82rem;color:var(--text-muted);">${e.expense_date ? new Date(e.expense_date).toLocaleDateString('th-TH') : '—'}</td>
                <td><span class="pill">${e.category}</span></td>
                <td>${e.description || '—'}</td>
                <td style="color:#f87171;font-weight:700;">฿${(e.amount||0).toLocaleString('th-TH')}</td>
                <td style="font-size:0.8rem;">${e.added_by || '—'}</td>
                <td>${e.image_path
                    ? `<span class="bill-img-link" onclick="viewBillImg('${e.image_path}')">📎 ดูบิล</span>`
                    : '<span style="color:var(--text-muted);font-size:0.78rem;">—</span>'
                }</td>
            </tr>
        `).join('');
    } catch {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

function viewBillImg(path) {
    const overlay = document.getElementById('bill-img-overlay');
    const img = document.getElementById('bill-img-el');
    if (overlay && img) { img.src = path; overlay.style.display = 'flex'; }
}
function closeBillImg() {
    document.getElementById('bill-img-overlay').style.display = 'none';
}

// ── MODAL HELPERS ──
function openAddAppointmentModal() {
    document.getElementById('appt-modal').style.display = 'flex';
}
function closeApptModal() {
    document.getElementById('appt-modal').style.display = 'none';
}
async function submitAppointment() {
    const customer = document.getElementById('appt-customer')?.value.trim();
    const date = document.getElementById('appt-date')?.value;
    if (!customer || !date) return alert('กรุณากรอกชื่อลูกค้าและวันที่');
    const payload = {
        customer_name: customer,
        customer_phone: document.getElementById('appt-phone')?.value || null,
        vehicle_plate: document.getElementById('appt-plate')?.value || null,
        vehicle_info: document.getElementById('appt-vehicle')?.value || null,
        appointment_date: new Date(date + 'T' + (document.getElementById('appt-time')?.value || '09:00')).toISOString(),
        time_slot: document.getElementById('appt-time')?.value || '09:00',
        service_type: document.getElementById('appt-service')?.value || null,
        status: 'confirmed'
    };
    try {
        const res = await fetch(`${API_URL}/appointments/`, { method:'POST', headers:HEADERS, body:JSON.stringify(payload) });
        if (!res.ok) throw new Error();
        showToast('✅ บันทึกนัดหมายเรียบร้อย!');
        closeApptModal();
        await fetchAppointments();
        renderCalendar();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

function openAddExpenseModal() {
    document.getElementById('expense-modal').style.display = 'flex';
}
function closeExpenseModal() {
    document.getElementById('expense-modal').style.display = 'none';
}
async function submitExpense() {
    const amount = parseFloat(document.getElementById('expense-amount')?.value);
    if (!amount || amount <= 0) return alert('กรุณากรอกจำนวนเงิน');
    const payload = {
        category: document.getElementById('expense-cat')?.value || 'อื่นๆ',
        description: document.getElementById('expense-desc')?.value || '',
        amount,
        expense_date: new Date(document.getElementById('expense-date')?.value || new Date()).toISOString(),
        added_by: document.getElementById('expense-by')?.value || 'ผู้จัดการ'
    };
    try {
        const res = await fetch(`${API_URL}/expenses/`, { method:'POST', headers:HEADERS, body:JSON.stringify(payload) });
        if (!res.ok) throw new Error();
        showToast(`✅ บันทึกค่าใช้จ่าย ฿${amount.toLocaleString('th-TH')} เรียบร้อย!`);
        closeExpenseModal();
        loadExpenses();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

function openAddSupplierModal() {
    document.getElementById('supplier-modal').style.display = 'flex';
}
function closeSupplierModal() {
    document.getElementById('supplier-modal').style.display = 'none';
}
async function submitSupplier() {
    const name = document.getElementById('sup-name')?.value.trim();
    if (!name) return alert('กรุณากรอกชื่อผู้จำหน่าย');
    const payload = {
        name,
        phone: document.getElementById('sup-phone')?.value || null,
        email: document.getElementById('sup-email')?.value || null,
        line_id: document.getElementById('sup-line')?.value || null,
        address: document.getElementById('sup-address')?.value || null,
    };
    try {
        const res = await fetch(`${API_URL}/suppliers/`, { method:'POST', headers:HEADERS, body:JSON.stringify(payload) });
        if (!res.ok) throw new Error();
        showToast('✅ เพิ่มผู้จำหน่ายเรียบร้อย!');
        closeSupplierModal();
        loadSuppliers();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

function openAddStockModal() {
    showToast('📦 เปิดฟอร์มเพิ่มอะไหล่ใหม่ — ใช้ AI หรือเพิ่มผ่านปุ่มด้านล่าง');
}

// ── GLOBAL SEARCH ──
function handleGlobalSearch(e) {
    if (e.key !== 'Enter') return;
    const q = document.getElementById('global-search')?.value.trim();
    if (!q) return;
    const matchTickets = allTickets.filter(t => (t.vehicle_plate||'').includes(q) || (t.customer_name||'').includes(q) || String(t.id) === q);
    const matchStock = allStock.filter(s => (s.name||'').includes(q) || (s.code||'').includes(q));
    const matchCustomers = allCustomers.filter(c => (c.name||'').includes(q) || (c.phone||'').includes(q));
    let msg = `🔍 ผลการค้นหา "${q}":\n`;
    if (matchTickets.length) msg += `• งานซ่อม: ${matchTickets.length} รายการ\n`;
    if (matchCustomers.length) msg += `• ลูกค้า: ${matchCustomers.map(c=>c.name).join(', ')}\n`;
    if (matchStock.length) msg += `• อะไหล่: ${matchStock.map(s=>s.name).join(', ')}\n`;
    if (!matchTickets.length && !matchCustomers.length && !matchStock.length) msg += 'ไม่พบข้อมูล';
    showToast(msg.trim());
}

function openPOSModal() { switchTab(null, 'pos'); }

// ── INTAKE MODAL ──
function openNewIntakeModal() {
    document.getElementById('intake-modal').style.display = 'flex';
}
function closeIntakeModal() {
    document.getElementById('intake-modal').style.display = 'none';
}
async function submitIntakeModal() {
    const plate = document.getElementById('intake-plate')?.value.trim() || '';
    const mechanic = document.getElementById('intake-mechanic')?.value.trim() || 'ช่าง';
    const rawInput = document.getElementById('intake-raw').value.trim();
    if (!rawInput) return alert('โปรดกรอกรายละเอียดใบประเมินช่าง');
    closeIntakeModal();
    showToast('📄 กำลังสแกนอ่านใบประเมินช่าง...');
    try {
        const res = await fetch(`${API_URL}/tickets/ingest`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({ vehicle_plate: plate, raw_input: `ใบประเมินช่าง (${mechanic}): ${rawInput}` })
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        showToast(`✅ เปิด Ticket #${data.id} สำเร็จ!`);
        fetchTicketsData();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

// ── APPROVE MODAL ──
function openApproveModal(id) {
    pendingTicketId = id;
    document.getElementById('approve-modal-id').innerText = `#${id}`;
    document.getElementById('approve-modal').style.display = 'flex';
}
function closeModal() {
    document.getElementById('approve-modal').style.display = 'none';
}
async function submitApproval() {
    const name = document.getElementById('approve-name').value.trim();
    const notes = document.getElementById('approve-notes').value.trim();
    const cost = document.getElementById('approve-cost').value;
    if (!name) return alert('โปรดกรอกชื่อช่าง');
    closeModal();
    showToast(`⏳ กำลังส่งผลการอนุมัติ Ticket #${pendingTicketId}...`);
    try {
        const res = await fetch(`${API_URL}/tickets/${pendingTicketId}/approve`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({ approved_by: name, mechanic_notes: notes || undefined, final_cost: cost ? parseFloat(cost) : undefined })
        });
        if (!res.ok) throw new Error();
        showToast(`✅ อนุมัติ Ticket #${pendingTicketId} เรียบร้อย!`);
        fetchTicketsData();
    } catch { showToast('❌ เกิดข้อผิดพลาด'); }
}

function saveSheetUrl() {
    const url = document.getElementById('sheets-url')?.value;
    const status = document.getElementById('sheets-status');
    if (!url) return;
    localStorage.setItem('sheets_webhook_url', url);
    if (status) { status.textContent = '✅ บันทึกเรียบร้อย'; status.style.color = '#34d399'; }
}

// ── AI COPILOT ──
function toggleCopilot() {
    const drawer = document.getElementById('ai-copilot-drawer');
    const chevron = document.getElementById('copilot-chevron');
    if (!drawer) return;
    drawer.classList.toggle('collapsed');
    if (chevron) chevron.style.transform = drawer.classList.contains('collapsed') ? 'rotate(180deg)' : 'rotate(0deg)';
}

function fillInput(text) {
    const input = document.getElementById('chat-input');
    if (input) { input.value = text; input.focus(); }
}

function sendQuick(cmd) {
    if (cmd === 'watchlist') fillInput('ดู Watchlist รายการเตือนภัยรถ');
    else if (cmd === 'summary') fillInput('สรุปรายงาน P&L ประจำเดือนนี้');
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    const thread = document.getElementById('chat-thread');

    thread.innerHTML += `<div class="msg-row user"><div class="bubble user-bubble">${text}</div></div>`;
    thread.scrollTop = thread.scrollHeight;

    const botMsgId = `bot-${Date.now()}`;
    thread.innerHTML += `
        <div class="msg-row bot" id="${botMsgId}">
            <div class="avatar-bot"><i data-lucide="cpu"></i></div>
            <div class="bubble bot-bubble"><p>กำลังประมวลผล R.O.S.E. Agent...</p></div>
        </div>`;
    thread.scrollTop = thread.scrollHeight;
    lucide.createIcons();

    try {
        const res = await fetch(`${API_URL}/chat/`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({ message: text })
        });
        const botMsgEl = document.getElementById(botMsgId);
        if (!res.ok) throw new Error('API Error');
        const data = await res.json();

        // Format the response text with markdown-like rendering
        const formatted = (data.text || '')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:3px;">$1</code>')
            .replace(/\n/g, '<br>');

        botMsgEl.querySelector('.bubble').innerHTML = `<p>${formatted}</p>`;

        // Refresh data based on response type
        if (data.type === 'ticket') fetchTicketsData();
        if (data.type === 'stock') fetchStockData();
        if (data.type === 'expense') loadExpenses();
        if (data.type === 'appointment') { fetchAppointments(); renderCalendar(); }
        if (data.type === 'approve_prompt' && data.data?.ticket_id) openApproveModal(data.data.ticket_id);

    } catch (err) {
        const botMsgEl = document.getElementById(botMsgId);
        if (botMsgEl) botMsgEl.querySelector('.bubble').innerHTML = `<p style="color:#ef4444;">เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง</p>`;
    }
}

function showToast(msg) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.animation = 'slideIn 0.3s reverse forwards'; setTimeout(() => toast.remove(), 300); }, 4000);
}
