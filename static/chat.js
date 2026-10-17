// ── Auto Service Command Center — chat.js v4.0.0 ──
const API_URL = '/api/v1';
const API_KEY = ''; // real key is added by auth.js
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

function onDOMReady(fn) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
    } else {
        fn();
    }
}

onDOMReady(async () => {
    // Ensure shop name defaults to Zero Garage & phone to 095-418-5332
    if (!localStorage.getItem('shop_name') || localStorage.getItem('shop_name').includes('R.O.S.E.') || localStorage.getItem('shop_name').includes('Auto Service')) {
        localStorage.setItem('shop_name', 'Zero Garage');
    }
    if (!localStorage.getItem('shop_phone') || localStorage.getItem('shop_phone') === '—' || localStorage.getItem('shop_phone') === '02-000-0000' || localStorage.getItem('shop_phone') === '081-234-5678') {
        localStorage.setItem('shop_phone', '095-418-5332');
    }
    lucide.createIcons();
    await initApp();
    restoreActiveTab();
    initChatImageEvents();

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

// ── TAB SWITCHING & ROUTING ──
function switchTab(e, tabId, subId = null) {
    // Support single argument usage e.g. switchTab('stock') or switchTab(event, 'stock')
    if (typeof e === 'string') {
        subId = tabId;
        tabId = e;
        e = null;
    }
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    if (!tabId) return;

    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

    const selectedNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (selectedNav) selectedNav.classList.add('active');

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) targetTab.classList.add('active');

    if (window.lucide) lucide.createIcons();

    // Persist current tab and route into localStorage & hash
    try {
        localStorage.setItem('activeTab', tabId);
        if (tabId === 'reports' && subId) {
            localStorage.setItem('activeSubReport', subId);
            if (window.location.hash !== `#reports/${subId}`) {
                history.replaceState(null, '', `#reports/${subId}`);
            }
        } else {
            if (tabId !== 'reports') localStorage.removeItem('activeSubReport');
            if (window.location.hash !== `#${tabId}`) {
                history.replaceState(null, '', `#${tabId}`);
            }
        }
    } catch (_) {}

    // Lazy load per tab
    if (tabId === 'appointments') renderCalendar();
    if (tabId === 'suppliers') loadSuppliers();
    if (tabId === 'purchases') loadPurchases();
    if (tabId === 'reports') {
        if (subId && window.reportsApp && window.reportsApp.openReport) {
            window.reportsApp.openReport(subId);
        } else {
            loadReports();
        }
    }
    if (tabId === 'expenses') loadExpenses();
    if (tabId === 'stock') {
        if (typeof fetchStockData === 'function') fetchStockData();
        loadStockHistory();
    }
    if (tabId === 'customers') {
        if (typeof fetchCustomersData === 'function') fetchCustomersData();
    }
    if (tabId === 'repairs') {
        if (typeof fetchTicketsData === 'function') fetchTicketsData();
    }
    if (tabId === 'pos') loadPOSHistory();
    if (tabId === 'settings') loadSettings();
}

function restoreActiveTab() {
    let tab = 'dashboard';
    let sub = null;

    const hash = window.location.hash.replace(/^#\/?/, '');
    if (hash) {
        const parts = hash.split('/');
        tab = parts[0];
        if (parts.length > 1) sub = parts[1];
    } else {
        const savedTab = localStorage.getItem('activeTab');
        if (savedTab) tab = savedTab;
        if (tab === 'reports') {
            const savedSub = localStorage.getItem('activeSubReport');
            if (savedSub) sub = savedSub;
        }
    }

    const targetTab = document.getElementById(`tab-${tab}`);
    if (targetTab) {
        switchTab(null, tab, sub);
    } else {
        switchTab(null, 'dashboard');
    }
}

window.addEventListener('hashchange', () => {
    restoreActiveTab();
});

// ── DATA FETCHING ──
async function fetchTicketsData() {
    try {
        const res = await fetch(`${API_URL}/tickets/`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();
        const rawItems = Array.isArray(data) ? data : (data.items || []);
        const seen = new Set();
        allTickets = [];
        for (const t of rawItems) {
            if (t && t.id && !seen.has(t.id)) {
                seen.add(t.id);
                allTickets.push(t);
            }
        }
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
        const res = await fetch(`${API_URL}/customers/?limit=200`, { headers: HEADERS });
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
        renderDashboardAppointments();
        if (typeof renderCalendar === 'function') renderCalendar();
    } catch (err) { console.error('Fetch appointments error:', err); }
}

function renderDashboardAppointments() {
    const container = document.getElementById('dashboard-appts-container');
    if (!container) return;

    if (!allAppointments || allAppointments.length === 0) {
        container.innerHTML = `
            <div style="text-align:center;padding:16px 8px;color:var(--text-muted);font-size:12.5px;">
                <i data-lucide="calendar" style="width:22px;height:22px;margin-bottom:4px;opacity:0.5;display:inline-block;"></i>
                <div>ยังไม่มีนัดหมายในระบบ</div>
                <button onclick="openAddAppointmentModal()" class="btn-sm" style="margin-top:8px;background:rgba(81,107,240,0.15);border:1px solid rgba(81,107,240,0.3);color:#93c5fd;padding:4px 10px;border-radius:6px;cursor:pointer;">+ เพิ่มนัดหมาย</button>
            </div>`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    const sorted = [...allAppointments].sort((a, b) => {
        const da = new Date(a.appointment_date || 0);
        const db = new Date(b.appointment_date || 0);
        return da - db;
    });

    const todayStr = new Date().toISOString().split('T')[0];
    const upcoming = sorted.filter(a => {
        const dStr = (a.appointment_date || '').split('T')[0];
        return dStr >= todayStr;
    });
    const displayList = upcoming.length > 0 ? upcoming.slice(0, 5) : sorted.slice(-5).reverse();

    const statusMap = {
        confirmed: { label: 'ยืนยันแล้ว', color: '#34d399', bg: 'rgba(16,185,129,0.15)' },
        pending: { label: 'รอยืนยัน', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
        completed: { label: 'เสร็จสิ้น', color: '#60a5fa', bg: 'rgba(59,130,246,0.15)' },
        cancelled: { label: 'ยกเลิก', color: '#94a3b8', bg: 'rgba(100,116,139,0.15)' },
    };

    container.innerHTML = displayList.map(a => {
        const d = new Date(a.appointment_date);
        const dateFormatted = !isNaN(d) ? d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' }) : 'ไม่ระบุ';
        const st = statusMap[a.status] || { label: a.status, color: '#94a3b8', bg: 'rgba(255,255,255,0.06)' };

        return `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);gap:8px;cursor:pointer;" onclick="switchTab(null,'appointments')">
                <div style="display:flex;align-items:center;gap:10px;overflow:hidden;">
                    <div style="text-align:center;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:4px 6px;min-width:52px;flex-shrink:0;">
                        <div style="font-size:11px;color:var(--text-muted);">${dateFormatted}</div>
                        <div style="font-size:12px;font-weight:700;color:var(--accent);">${a.time_slot || '10:00'}</div>
                    </div>
                    <div style="overflow:hidden;">
                        <div style="font-size:13px;font-weight:700;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                            ${_escHtml(a.customer_name)}
                        </div>
                        <div style="font-size:11.5px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                            ${_escHtml(a.service_type || 'ตรวจเช็ค')}
                        </div>
                    </div>
                </div>
                <span style="font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:10px;background:${st.bg};color:${st.color};white-space:nowrap;flex-shrink:0;">
                    ${st.label}
                </span>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function fetchWatchlist() {
    const container = document.getElementById('watchlist-container');
    if (!container) return;
    container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">กำลังโหลด Watchlist...</p>`;
    try {
        // Fetch ALL customers then aggregate all vehicle watchlist items
        const custRes = await fetch(`${API_URL}/customers/?limit=200`, { headers: HEADERS });
        if (!custRes.ok) throw new Error('Failed to fetch customers');
        const custData = await custRes.json();
        const customers = custData.items || custData || [];

        const watchlist = [];
        // Fetch each customer profile in parallel (limit concurrency to avoid overload)
        await Promise.all(customers.map(async c => {
            try {
                const res = await fetch(`${API_URL}/customers/${c.id}/profile`, { headers: HEADERS });
                if (!res.ok) return;
                const profile = await res.json();
                (profile.vehicles || []).forEach(v => {
                    (v.health_watchlist || []).forEach(w => {
                        watchlist.push({ ...w, vehicle_plate: v.plate, car_brand: v.brand, car_model: v.model });
                    });
                });
            } catch {}
        }));

        // Sort: overdue first
        watchlist.sort((a, b) => (b.is_overdue ? 1 : 0) - (a.is_overdue ? 1 : 0));

        if (watchlist.length === 0) {
            container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">🎉 รถทุกคันปกติดี ไม่มีรายการเตือนภัย</p>`;
            return;
        }
        container.innerHTML = watchlist.slice(0, 8).map(w => `
            <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.82rem;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <strong style="color:${w.is_overdue ? '#f87171' : '#fbbf24'}">${w.component}</strong>
                    <div style="font-size:0.72rem;color:var(--text-muted);">${w.vehicle_plate} (${w.car_brand || ''} ${w.car_model || ''}) — ${w.condition}</div>
                </div>
                <span class="pill ${w.is_overdue ? 'danger' : 'warning'}">${w.is_overdue ? 'เกินกำหนด' : 'ใกล้กำหนด'}</span>
            </div>
        `).join('');
        if (watchlist.length > 8) {
            container.innerHTML += `<div style="text-align:center;font-size:0.75rem;color:var(--text-muted);padding:6px 0;">และอีก ${watchlist.length - 8} รายการ</div>`;
        }
    } catch (err) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:8px 0;">ไม่สามารถโหลด Watchlist ได้</p>`;
    }
}

// ── DASHBOARD ──
function renderDashboardStats() {
    const pendingCount = allTickets.filter(t => t.status === 'PENDING_MECHANIC_APPROVAL').length;
    const activeCount = allTickets.filter(t => t.status === 'APPROVED' || t.status === 'PENDING_MECHANIC_APPROVAL').length;

    const el = id => document.getElementById(id);
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    if (el('kpi-active-repairs')) el('kpi-active-repairs').innerText = `${activeCount} ${isEn ? 'vehicles' : 'คัน'}`;
    if (el('kpi-pending-approval')) el('kpi-pending-approval').innerText = isEn ? `${pendingCount} awaiting approval` : `รอช่างอนุมัติ ${pendingCount} คัน`;
    if (el('badge-repairs')) el('badge-repairs').innerText = activeCount;

    const lowStockCount = allStock.filter(s => s.quantity <= s.reorder_level).length;
    if (el('kpi-low-stock')) el('kpi-low-stock').innerText = `${lowStockCount} ${isEn ? 'items' : 'รายการ'}`;
    if (el('badge-stock-warn')) el('badge-stock-warn').innerText = lowStockCount;

    // Fetch real monthly revenue with month-over-month comparison
    fetchMonthlyRevenueKPI();
}

async function fetchMonthlyRevenueKPI() {
    const el = id => document.getElementById(id);
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    try {
        const now = new Date();
        const cy = now.getFullYear();
        const cm = String(now.getMonth() + 1).padStart(2, '0');

        // Previous month
        const prevDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const py = prevDate.getFullYear();
        const pm = String(prevDate.getMonth() + 1).padStart(2, '0');

        const [currRes, prevRes] = await Promise.all([
            fetch(`${API_URL}/finance/summary/${cy}/${cm}`, { headers: HEADERS }),
            fetch(`${API_URL}/finance/summary/${py}/${pm}`, { headers: HEADERS }),
        ]);

        const currData = currRes.ok ? await currRes.json() : null;
        const prevData = prevRes.ok ? await prevRes.json() : null;

        let currRev = currData?.summary?.total_income ?? 0;
        const prevRev = prevData?.summary?.total_income ?? 0;

        // Auto-sync fallback: If ledger summary is missing tickets from this month,
        // compute from allTickets (COMPLETED & APPROVED) in the current month
        if (Array.isArray(allTickets) && allTickets.length > 0) {
            const ticketRevThisMonth = allTickets
                .filter(t => t.status === 'COMPLETED' || t.status === 'APPROVED')
                .filter(t => {
                    const dateStr = t.updated_at || t.approved_at || t.created_at;
                    if (!dateStr) return false;
                    const d = new Date(dateStr);
                    return d.getFullYear() === cy && (d.getMonth() + 1) === Number(cm);
                })
                .reduce((sum, t) => sum + (Number(t.final_cost) || Number(t.total_estimated_cost) || 0), 0);

            if (ticketRevThisMonth > currRev) {
                currRev = ticketRevThisMonth;
            }
        }

        if (el('kpi-revenue')) el('kpi-revenue').innerText = `฿${currRev.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        const subEl = el('kpi-revenue-sub');
        if (subEl) {
            if (prevRev > 0) {
                const pct = ((currRev - prevRev) / prevRev * 100).toFixed(1);
                const isUp = parseFloat(pct) >= 0;
                subEl.innerHTML = `<i data-lucide="${isUp ? 'arrow-up-right' : 'arrow-down-right'}"></i> ${isUp ? '+' : ''}${pct}% ${isEn ? 'from last month' : 'จากเดือนที่แล้ว'}`;
                subEl.style.color = isUp ? '#34d399' : '#f87171';
            } else if (currRev > 0) {
                subEl.innerHTML = `<i data-lucide="trending-up"></i> ${isEn ? 'First month with revenue' : 'เดือนแรกที่มีรายได้'}`;
                subEl.style.color = '#34d399';
            } else {
                subEl.innerHTML = isEn ? 'No revenue yet this month' : `ยังไม่มีรายได้เดือนนี้`;
                subEl.style.color = 'var(--text-muted)';
            }
            if (window.lucide) lucide.createIcons();
        }
    } catch (err) {
        console.error('Revenue KPI error:', err);
    }
}

function updateApptKpi() {
    const today = new Date().toDateString();
    const todayAppts = allAppointments.filter(a => {
        const d = new Date(a.appointment_date);
        return d.toDateString() === today;
    });
    const el = document.getElementById('kpi-appointments');
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    if (el) el.innerText = `${todayAppts.length} ${isEn ? 'appts' : 'นัด'}`;
}

function statusBadgeHtml(status) {
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    const map = {
        'PENDING_MECHANIC_APPROVAL': isEn ? '<span class="status-badge pending">⏳ Pending</span>' : '<span class="status-badge pending">⏳ รออนุมัติ</span>',
        'APPROVED': isEn ? '<span class="status-badge approved">🟢 In Progress</span>' : '<span class="status-badge approved">🟢 กำลังซ่อม</span>',
        'COMPLETED': isEn ? '<span class="status-badge" style="background:rgba(16,185,129,0.2);color:#34d399;">✅ Completed</span>' : '<span class="status-badge" style="background:rgba(16,185,129,0.2);color:#34d399;">✅ เสร็จสิ้น</span>',
        'CANCELLED': isEn ? '<span class="status-badge" style="background:rgba(100,116,139,0.2);color:#94a3b8;">❌ Cancelled</span>' : '<span class="status-badge" style="background:rgba(100,116,139,0.2);color:#94a3b8;">❌ ยกเลิก</span>',
    };
    return map[status] || `<span class="status-badge draft">${status}</span>`;
}

function formatTicketInputHtml(raw) {
    if (!raw) return '—';
    const match = raw.match(/\[แนบภาพถ่าย:\s*([^\]]+)\]/);
    if (match) {
        const imgUrl = match[1].trim();
        const cleanText = raw.replace(/\[แนบภาพถ่าย:\s*[^\]]+\]/, '').trim();
        return `<div style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${cleanText || 'เปิดใบรับรถพร้อมภาพ'}</div>
                <span class="btn-ticket-photo" onclick="viewBillImg('${imgUrl}')">📷 ดูรูปภาพรถ</span>`;
    }
    return `<div style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(raw)}</div>`;
}

// ── TICKET DETAIL MODAL (ข้อมูลงานซ่อมโดยละเอียด) ──
let currentDetailTicket = null;

async function openTicketDetailModal(ticketId) {
    let t = allTickets.find(x => x.id === parseInt(ticketId));
    try {
        const res = await fetch(`${API_URL}/tickets/${ticketId}`, { headers: HEADERS });
        if (res.ok) t = await res.json();
    } catch {}

    if (!t) return alert('ไม่พบข้อมูลงานซ่อม');
    currentDetailTicket = t;

    // Header info
    document.getElementById('td-modal-id').textContent = `#${t.id}`;
    document.getElementById('td-modal-status-badge').innerHTML = statusBadgeHtml(t.status);
    const dateStr = t.created_at ? new Date(t.created_at).toLocaleString('th-TH') : '—';
    const updatedStr = t.updated_at ? ` (อัปเดตล่าสุด: ${new Date(t.updated_at).toLocaleString('th-TH')})` : '';
    document.getElementById('td-modal-date').textContent = `เปิดงานเมื่อ: ${dateStr}${updatedStr}`;

    // Customer card
    document.getElementById('td-customer-name').textContent = t.customer_name || 'ลูกค้าทั่วไป';
    document.getElementById('td-customer-phone').innerHTML = t.customer_phone 
        ? `<i data-lucide="phone" style="width:13px;height:13px;"></i> <a href="tel:${t.customer_phone}" style="color:var(--text-secondary);text-decoration:none;">${t.customer_phone}</a>`
        : `<i data-lucide="phone" style="width:13px;height:13px;"></i> —`;
    
    document.getElementById('td-customer-line').innerHTML = t.customer_line_id
        ? `<i data-lucide="message-circle" style="width:13px;height:13px;"></i> LINE: <strong>${t.customer_line_id}</strong>`
        : `<i data-lucide="message-circle" style="width:13px;height:13px;color:var(--text-muted);"></i> <span style="color:var(--text-muted);">LINE: —</span>`;

    const custBtn = document.getElementById('td-btn-view-customer');
    if (custBtn) {
        custBtn.style.display = t.customer_id ? 'inline-block' : 'none';
    }

    // Vehicle card
    document.getElementById('td-vehicle-plate').textContent = t.vehicle_plate || 'ไม่ระบุ';
    document.getElementById('td-vehicle-model').textContent = t.car_model || '—';
    document.getElementById('td-vehicle-mileage').innerHTML = `<i data-lucide="gauge" style="width:13px;height:13px;display:inline-block;vertical-align:-1px;"></i> เลขไมล์ตอนรับรถ: <strong>${(t.mileage || 0).toLocaleString()} กม.</strong>`;

    // Mechanic & Symptoms
    document.getElementById('td-mechanic-name').textContent = t.mechanic_name || 'ช่างประจำ';
    document.getElementById('td-approved-by').textContent = t.approved_by 
        ? `${t.approved_by} ${t.approved_at ? '(' + new Date(t.approved_at).toLocaleDateString('th-TH') + ')' : ''}`
        : '— รออนุมัติ —';
    
    document.getElementById('td-raw-input').textContent = t.raw_input || '—';

    const notesCont = document.getElementById('td-notes-container');
    if (t.mechanic_notes) {
        notesCont.style.display = 'block';
        document.getElementById('td-mechanic-notes').textContent = t.mechanic_notes;
    } else {
        notesCont.style.display = 'none';
    }

    const diagCont = document.getElementById('td-diagnosed-container');
    const diagList = t.diagnosed_issues || [];
    if (diagList.length > 0) {
        diagCont.style.display = 'block';
        document.getElementById('td-diagnosed-issues').innerHTML = diagList.map(d => `
            <span class="pill" style="background:rgba(59,130,246,0.12);color:#93c5fd;border:1px solid rgba(59,130,246,0.3);font-size:0.75rem;">
                ${d.component || d.issue}: ${d.description || d.severity || ''}
            </span>
        `).join('');
    } else {
        diagCont.style.display = 'none';
    }

    // Line items table
    const lineTbody = document.getElementById('td-line-items-tbody');
    const items = t.line_items || [];
    if (!items.length) {
        lineTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--text-muted);">ไม่มีรายการแยกย่อย</td></tr>`;
    } else {
        lineTbody.innerHTML = items.map((it, idx) => {
            const qty = it.qty || it.quantity || 1;
            const price = it.unit_price || it.price || 0;
            const total = it.total || (qty * price);
            return `
                <tr>
                    <td style="color:var(--text-muted);">${idx + 1}</td>
                    <td><strong>${it.name_th || it.name || '—'}</strong></td>
                    <td style="text-align:center;">${qty}</td>
                    <td style="text-align:right;">฿${price.toLocaleString('th-TH', {minimumFractionDigits:2})}</td>
                    <td style="text-align:right;font-weight:600;color:#34d399;">฿${total.toLocaleString('th-TH', {minimumFractionDigits:2})}</td>
                </tr>
            `;
        }).join('');
    }

    // Cost summary
    document.getElementById('td-labor-cost').textContent = `฿${(t.estimated_labor_cost || 0).toLocaleString('th-TH')}`;
    document.getElementById('td-parts-cost').textContent = `฿${(t.estimated_parts_cost || 0).toLocaleString('th-TH')}`;
    const finalAmount = t.final_cost || t.total_estimated_cost || 0;
    document.getElementById('td-total-cost').textContent = `฿${finalAmount.toLocaleString('th-TH', {minimumFractionDigits:2})}`;

    // Workflow button
    const wfCont = document.getElementById('td-workflow-btn-container');
    if (t.status === 'PENDING_MECHANIC_APPROVAL' || t.status === 'DRAFT_ESTIMATE') {
        wfCont.innerHTML = `<button type="button" class="btn-primary" style="padding:8px 14px;font-size:0.84rem;font-weight:600;display:inline-flex;align-items:center;gap:6px;" onclick="closeTicketDetailModal();openApproveModal(${t.id})"><i data-lucide="shield-check" style="width:14px;height:14px;"></i> ✓ อนุมัติเริ่มงาน</button>`;
    } else if (t.status === 'APPROVED' || t.status === 'IN_PROGRESS') {
        wfCont.innerHTML = `<button type="button" class="btn-success" style="background:#10b981;border:1px solid #059669;color:#fff;padding:8px 14px;font-size:0.84rem;border-radius:6px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px;" onclick="closeTicketDetailModal();openCompleteModal(${t.id})"><i data-lucide="check-circle" style="width:14px;height:14px;"></i> 🏁 แจ้งซ่อมเสร็จ</button>`;
    } else if (t.status === 'COMPLETED') {
        wfCont.innerHTML = `<span class="pill" style="background:rgba(16,185,129,0.15);color:#34d399;font-size:0.84rem;padding:6px 12px;border:1px solid rgba(16,185,129,0.3);font-weight:600;"><i data-lucide="check" style="width:14px;height:14px;display:inline-block;vertical-align:-2px;"></i> ซ่อมเสร็จสิ้นแล้ว</span>`;
    } else {
        wfCont.innerHTML = '';
    }

    document.getElementById('ticket-detail-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeTicketDetailModal() {
    document.getElementById('ticket-detail-modal').style.display = 'none';
}

function printWorkOrderFromCurrentDetail() {
    if (currentDetailTicket) printWorkOrderFromTicket(currentDetailTicket);
}

function printInvoiceFromCurrentDetail() {
    if (currentDetailTicket) printInvoiceFromTicket(currentDetailTicket);
}

function openTrackFromCurrentDetail() {
    if (currentDetailTicket) window.open('/track?q=' + currentDetailTicket.id, '_blank');
}

function openTicketCustomer360() {
    if (currentDetailTicket?.customer_id) {
        closeTicketDetailModal();
        switchTab('customers');
        viewCustomerProfile(currentDetailTicket.customer_id);
    }
}

function renderTicketActionsHtml(t) {
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    let mainActionBtn = '';
    if (t.status === 'PENDING_MECHANIC_APPROVAL' || t.status === 'DRAFT_ESTIMATE') {
        mainActionBtn = `<button class="btn-primary" style="padding:4px 9px;font-size:0.75rem;" onclick="openApproveModal(${t.id})">${isEn ? '✓ Approve' : '✓ อนุมัติเริ่มงาน'}</button>`;
    } else if (t.status === 'APPROVED' || t.status === 'IN_PROGRESS') {
        mainActionBtn = `<button class="btn-success" style="background:#10b981;border:1px solid #059669;color:#fff;padding:4px 9px;font-size:0.75rem;border-radius:6px;font-weight:600;cursor:pointer;" onclick="openCompleteModal(${t.id})">${isEn ? '🏁 Complete' : '🏁 แจ้งซ่อมเสร็จ'}</button>`;
    } else if (t.status === 'COMPLETED') {
        mainActionBtn = `<span class="btn-sm" style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);color:#34d399;font-size:0.75rem;padding:3px 7px;cursor:default;">${isEn ? '✓ Finished' : '✓ ซ่อมเสร็จแล้ว'}</span>`;
    } else {
        mainActionBtn = `<a href="/track?q=${t.id}" target="_blank" class="btn-sm" style="text-decoration:none;">${isEn ? 'Track' : 'ดูสถานะ'}</a>`;
    }

    return `
        <button class="btn-sm" style="background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);color:#60a5fa;display:inline-flex;align-items:center;gap:3px;" onclick="openTicketDetailModal(${t.id})" title="${isEn ? 'View repair details' : 'ดูข้อมูลงานซ่อมโดยละเอียด'}"><i data-lucide="clipboard-list" style="width:12px;height:12px;"></i> ${isEn ? 'Details' : 'ข้อมูล'}</button>
        ${mainActionBtn}
        ${fxTicketExtraButtons(t)}
        <button class="btn-sm" style="background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.3);color:#60a5fa;display:inline-flex;align-items:center;gap:3px;" onclick="openEditTicketModal(${t.id})" title="${isEn ? 'Edit ticket' : 'แก้ไขงานซ่อม'}"><i data-lucide="pencil" style="width:12px;height:12px;"></i> ${isEn ? 'Edit' : 'แก้ไข'}</button>
        <button class="btn-sm" style="background:rgba(52,211,153,0.12);border-color:rgba(52,211,153,0.35);color:#34d399;" onclick="printWorkOrderFromTicket(allTickets.find(x=>x.id===${t.id}))" title="${isEn ? 'Print Work Order' : 'พิมพ์ใบแจ้งงาน (Work Order)'}">📋 ${isEn ? 'Work Order' : 'ใบแจ้งงาน'}</button>
        <button class="btn-sm" style="background:rgba(99,102,241,0.15);border-color:rgba(99,102,241,0.4);color:#a5b4fc;" onclick="printInvoiceFromTicket(allTickets.find(x=>x.id===${t.id}))" title="${isEn ? 'Print Invoice' : 'พิมพ์ใบเสร็จ (Invoice)'}">🖨️ ${isEn ? 'Invoice' : 'ใบเสร็จ'}</button>
        <button class="btn-sm" style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.35);color:#f87171;display:inline-flex;align-items:center;gap:4px;" onclick="deleteTicket(${t.id})" title="${isEn ? 'Delete ticket' : 'ลบงานซ่อม'}"><i data-lucide="trash-2" style="width:12px;height:12px;"></i> ${isEn ? 'Delete' : 'ลบ'}</button>
    `;
}

function renderTicketsTable(statusFilter = 'all') {
    const tbody = document.getElementById('tickets-tbody');
    if (!tbody) return;
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    let filtered = statusFilter === 'all' ? allTickets : allTickets.filter(t => t.status === statusFilter);
    if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">${isEn ? 'No repair orders found' : 'ไม่พบข้อมูลงานซ่อม'}</td></tr>`;
        return;
    }
    tbody.innerHTML = filtered.map(t => {
        const cost = (t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH');
        const lineItems = t.line_items || [];
        const linePreview = lineItems.length > 0
            ? lineItems.slice(0,3).map(i => `<div style="font-size:0.75rem;color:var(--text-secondary);">${(isEn && i.name) ? i.name : (i.name_th || i.name)}${i.total>0?' — ฿'+i.total.toLocaleString('th-TH'):''}</div>`).join('')
                + (lineItems.length > 3 ? `<div style="font-size:0.72rem;color:var(--text-muted);">+${lineItems.length-3} ${isEn ? 'more...' : 'รายการ...'}</div>` : '')
            : formatTicketInputHtml(t.raw_input);
        const unspec = isEn ? 'Unspecified' : 'ไม่ระบุ';
        const walkin = isEn ? 'General Walk-in' : 'ลูกค้าทั่วไป';
        return `<tr>
            <td><strong style="color:#93c5fd;cursor:pointer;text-decoration:underline;" onclick="openTicketDetailModal(${t.id})" title="${isEn ? 'Click to view details' : 'คลิกเพื่อดูข้อมูลงานซ่อม'}">#${t.id}</strong></td>
            <td><strong>${t.vehicle_plate || unspec}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${t.car_model || ''}</div></td>
            <td>${t.customer_name || walkin}</td>
            <td>${linePreview}</td>
            <td style="color:#34d399;font-weight:600;">฿${cost}${fxPaymentBadge(t)}</td>
            <td>${statusBadgeHtml(t.status)}${fxDecisionBadge(t)}</td>
            <td style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;">${renderTicketActionsHtml(t)}</td>
        </tr>`;
    }).join('');
    if (window.lucide) lucide.createIcons();
}

let currentRepairsStatusFilter = 'all';
let currentRepairsSearchQuery = '';

function filterRepairsStatus(btn, status) {
    document.querySelectorAll('#tab-repairs .table-filter-pills .pill').forEach(el => el.classList.remove('active'));
    if (btn) btn.classList.add('active');
    currentRepairsStatusFilter = status;
    renderFullRepairsTable();
}

function filterRepairsTable() {
    currentRepairsSearchQuery = (document.getElementById('repairs-search-input')?.value || '').trim().toLowerCase();
    renderFullRepairsTable();
}

function renderFullRepairsTable() {
    const container = document.getElementById('full-repairs-table-container');
    if (!container) return;
    const isEn = typeof getAppLanguage === 'function' && getAppLanguage() === 'en';
    
    let list = allTickets;
    if (currentRepairsStatusFilter !== 'all') {
        list = list.filter(t => t.status === currentRepairsStatusFilter);
    }
    if (currentRepairsSearchQuery) {
        list = list.filter(t => {
            const id = String(t.id);
            const plate = (t.vehicle_plate || '').toLowerCase();
            const model = (t.car_model || '').toLowerCase();
            const cust = (t.customer_name || '').toLowerCase();
            const mech = (t.mechanic_name || '').toLowerCase();
            const raw = (t.raw_input || '').toLowerCase();
            return id.includes(currentRepairsSearchQuery) || plate.includes(currentRepairsSearchQuery) ||
                   model.includes(currentRepairsSearchQuery) || cust.includes(currentRepairsSearchQuery) ||
                   mech.includes(currentRepairsSearchQuery) || raw.includes(currentRepairsSearchQuery);
        });
    }

    if (!list.length) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:30px;">${currentRepairsSearchQuery ? (isEn ? 'No repairs matching search query' : 'ไม่พบงานซ่อมที่ตรงกับการค้นหา') : (isEn ? 'No repairs in this category' : 'ยังไม่มีงานซ่อมในหมวดนี้')}</p>`;
        return;
    }
    container.innerHTML = `
        <div class="table-responsive">
            <table class="data-table">
                <thead><tr><th>Ticket #</th><th>${isEn ? 'Plate / Model' : 'ทะเบียน / รุ่น'}</th><th>${isEn ? 'Customer' : 'ลูกค้า'}</th><th>${isEn ? 'Items' : 'รายการ'}</th><th>${isEn ? 'Price' : 'ราคา'}</th><th>${isEn ? 'Status' : 'สถานะ'}</th><th>${isEn ? 'Date' : 'วันที่'}</th><th>${isEn ? 'Actions' : 'จัดการ'}</th></tr></thead>
                <tbody>${list.map(t => {
                    const cost = (t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH');
                    const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString(isEn ? 'en-US' : 'th-TH') : '—';
                    const lineItems = t.line_items || [];
                    const linePreview = lineItems.length > 0
                        ? lineItems.slice(0,3).map(i => `<div style="font-size:0.75rem;color:var(--text-secondary);">${(isEn && i.name) ? i.name : (i.name_th || i.name)}${i.total>0?' — ฿'+i.total.toLocaleString('th-TH'):''}</div>`).join('')
                            + (lineItems.length > 3 ? `<div style="font-size:0.72rem;color:var(--text-muted);">+${lineItems.length-3} ${isEn ? 'more...' : 'รายการ...'}</div>` : '')
                        : formatTicketInputHtml(t.raw_input);
                    const unspec = isEn ? 'Unspecified' : 'ไม่ระบุ';
                    const walkin = isEn ? 'General Walk-in' : 'ลูกค้าทั่วไป';
                    return `<tr>
                        <td><strong style="color:#93c5fd;cursor:pointer;text-decoration:underline;" onclick="openTicketDetailModal(${t.id})" title="${isEn ? 'Click to view details' : 'คลิกเพื่อดูข้อมูลงานซ่อม'}">#${t.id}</strong></td>
                        <td><strong>${t.vehicle_plate || unspec}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${t.car_model || ''}</div></td>
                        <td>${t.customer_name || walkin}</td>
                        <td>${linePreview}</td>
                        <td style="color:#34d399;font-weight:600;">฿${cost}${fxPaymentBadge(t)}</td>
                        <td>${statusBadgeHtml(t.status)}${fxDecisionBadge(t)}</td>
                        <td style="color:var(--text-muted);font-size:0.8rem;">${dateStr}</td>
                        <td style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;">${renderTicketActionsHtml(t)}</td>
                    </tr>`;
                }).join('')}</tbody>
            </table>
        </div>`;
    if (window.lucide) lucide.createIcons();
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

// ── STOCK SEARCH, CATEGORIES & TABLE ──
let stockSelectedItemId = null;
let stockSearchQuery = '';
let stockActiveCategory = 'All';
let _stockSearchDebounceTimer = null;

function renderStockCategories() {
    const pillsContainer = document.getElementById('stock-category-pills');
    if (!pillsContainer || !allStock || !allStock.length) return;

    // Unique categories from current stock
    const cats = ['All', ...new Set(allStock.map(s => s.category).filter(Boolean))];

    pillsContainer.innerHTML = cats.map(cat => {
        const isActive = stockActiveCategory === cat;
        const count = cat === 'All' ? allStock.length : allStock.filter(s => s.category === cat).length;
        const label = cat === 'All' ? 'ทั้งหมด' : cat;
        return `<button type="button" class="btn-sm" onclick="setStockCategory('${_escHtml(cat)}')" 
            style="padding:5px 12px; border-radius:9999px; font-size:0.78rem; cursor:pointer; white-space:nowrap; transition:all 0.15s ease;
                   background:${isActive ? '#3b82f6' : 'rgba(255,255,255,0.06)'};
                   color:${isActive ? '#ffffff' : 'var(--text-secondary)'};
                   border:1px solid ${isActive ? '#3b82f6' : 'rgba(255,255,255,0.1)'};
                   font-weight:${isActive ? '700' : '500'};">
            ${label} <span style="opacity:0.75; font-size:0.72rem; margin-left:3px;">(${count})</span>
        </button>`;
    }).join('');
}

function setStockCategory(cat) {
    stockActiveCategory = cat;
    stockSelectedItemId = null; // reset single-item lock when switching category
    renderStockCategories();
    renderStockTable();
}

// Search terms: comma separates multiple parts (OR), spaces inside a term must all match (AND)
// e.g. "น้ำมันเครื่อง, กรอง อากาศ" → items matching "น้ำมันเครื่อง" OR ("กรอง" AND "อากาศ")
function _stockMatchesQuery(s, q) {
    const hay = [s.name, s.code, s.name_en, s.category].map(v => (v || '').toLowerCase()).join(' ');
    const groups = q.toLowerCase().split(/[,，]/).map(g => g.trim()).filter(Boolean);
    if (!groups.length) return true;
    return groups.some(g => g.split(/\s+/).every(w => hay.includes(w)));
}

function handleStockSearchInput(val) {
    clearTimeout(_stockSearchDebounceTimer);
    const q = (val || '').trim();
    stockSearchQuery = q;
    // A new search always shows every match again
    stockSelectedItemId = null;

    const clearBtn = document.getElementById('stock-search-clear-btn');
    if (clearBtn) clearBtn.style.display = q ? 'inline-flex' : 'none';

    if (!q) {
        closeStockSearchDropdown();
        renderStockTable();
        return;
    }

    _stockSearchDebounceTimer = setTimeout(() => {
        renderStockSearchDropdown(q);
        renderStockTable();
    }, 100);
}

function renderStockSearchDropdown(q) {
    const dd = document.getElementById('stock-search-dropdown');
    if (!dd) return;

    const matches = (allStock || []).filter(s => _stockMatchesQuery(s, q));

    if (!matches.length) {
        dd.innerHTML = `<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:0.84rem;">ไม่พบอะไหล่ที่ตรงกับ "${_escHtml(q)}"</div>`;
        dd.style.display = 'block';
        return;
    }

    let html = `<div class="search-dropdown-group-title" style="padding:8px 14px;font-size:0.74rem;color:var(--text-muted);border-bottom:1px solid rgba(255,255,255,0.06);display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span>🔍 คลิกเพื่อไปที่รายการ • ค้นหาหลายชิ้นได้ด้วยเครื่องหมาย ,</span>
        <span style="color:#60a5fa;font-weight:700;white-space:nowrap;">พบ ${matches.length} รายการ</span>
    </div>
    <div class="search-dropdown-item" onclick="closeStockSearchDropdown()" style="padding:9px 14px;border-bottom:1px solid rgba(255,255,255,0.08);cursor:pointer;color:#6ee7b7;font-weight:700;font-size:0.84rem;">
        📋 แสดงผลทั้งหมด ${matches.length} รายการในตาราง (Enter)
    </div>`;

    html += matches.slice(0, 15).map(s => `
        <div class="search-dropdown-item" onclick="selectStockItem(${s.id})" style="padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer;display:flex;align-items:center;justify-content:space-between;">
            <div style="flex:1;min-width:0;">
                <div style="font-weight:700;color:#93c5fd;display:flex;align-items:center;gap:6px;">
                    📦 ${s.name}
                    ${s.code ? `<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;font-size:0.75rem;color:#cbd5e1;">${s.code}</code>` : ''}
                </div>
                <div class="item-sub" style="margin-top:2px;">
                    ${s.name_en ? `${s.name_en} | ` : ''}หมวด: ${s.category || '—'}
                </div>
            </div>
            <div style="text-align:right;flex-shrink:0;margin-left:12px;">
                <span class="pill ${s.quantity <= s.reorder_level ? 'danger' : ''}" style="font-size:0.75rem;font-weight:600;">
                    ${s.quantity} ${s.unit || 'ชิ้น'}
                </span>
                <div style="font-size:0.78rem;color:#34d399;font-weight:700;margin-top:2px;">฿${(s.price||0).toLocaleString('th-TH')}</div>
            </div>
        </div>
    `).join('');

    dd.innerHTML = html;
    dd.style.display = 'block';
    if (window.lucide) lucide.createIcons();
}

function closeStockSearchDropdown() {
    const dd = document.getElementById('stock-search-dropdown');
    if (dd) dd.style.display = 'none';
}

function selectStockItem(id) {
    const item = (allStock || []).find(s => s.id === id);
    if (!item) return;

    // Highlight the chosen item but keep every other search result visible
    stockSelectedItemId = id;
    closeStockSearchDropdown();
    renderStockTable();

    const row = document.getElementById(`stock-row-${id}`);
    if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function clearStockSearch() {
    stockSelectedItemId = null;
    stockSearchQuery = '';
    const input = document.getElementById('stock-search-input');
    if (input) input.value = '';
    const clearBtn = document.getElementById('stock-search-clear-btn');
    if (clearBtn) clearBtn.style.display = 'none';
    closeStockSearchDropdown();
    renderStockTable();
    showToast('📦 แสดงอะไหล่ทั้งหมดแล้ว');
}

function handleStockSearchKeydown(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        // Show every matching item in the table
        clearTimeout(_stockSearchDebounceTimer);
        stockSearchQuery = (document.getElementById('stock-search-input')?.value || '').trim();
        stockSelectedItemId = null;
        closeStockSearchDropdown();
        renderStockTable();
    } else if (e.key === 'Escape') {
        closeStockSearchDropdown();
    }
}

function renderStockTable() {
    const tbody = document.getElementById('stock-tbody');
    if (!tbody) return;

    renderStockCategories();

    if (!allStock || !allStock.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">ไม่มีข้อมูลสต๊อก</td></tr>`;
        return;
    }

    // Determine filtered items
    let items = allStock;

    // 1. Category filter
    if (stockActiveCategory && stockActiveCategory !== 'All') {
        items = items.filter(s => s.category === stockActiveCategory);
    }
    // 2. Search query filter (selected item is only highlighted, not filtered alone)
    if (stockSearchQuery) {
        items = items.filter(s => _stockMatchesQuery(s, stockSearchQuery));
    }

    // Update active filter banner
    const banner = document.getElementById('stock-active-filter-banner');
    const bannerText = document.getElementById('stock-active-filter-text');
    if (banner && bannerText) {
        if (stockSearchQuery) {
            bannerText.innerHTML = `ผลการค้นหาสำหรับ: "<strong style="color:#ffffff;">${_escHtml(stockSearchQuery)}</strong>" — <span style="color:#6ee7b7;font-weight:700;">พบ ${items.length} รายการ</span>`;
            banner.style.display = 'flex';
        } else {
            banner.style.display = 'none';
        }
    }

    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px;color:var(--text-muted);">
            <div style="font-size:1.1rem;margin-bottom:6px;">🔍 ไม่พบอะไหล่ที่ค้นหา</div>
            <button type="button" class="btn-sm" onclick="clearStockSearch()" style="margin-top:8px;padding:6px 14px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);color:#60a5fa;cursor:pointer;border-radius:6px;display:inline-flex;align-items:center;gap:6px;">
                <i data-lucide="refresh-cw" style="width:12px;height:12px;"></i> แสดงอะไหล่ทั้งหมด
            </button>
        </td></tr>`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    tbody.innerHTML = items.map(s => {
        const isSelected = stockSelectedItemId === s.id;
        const rowBg = isSelected ? 'background:rgba(59,130,246,0.15);border-left:4px solid #3b82f6;' : '';
        return `
        <tr id="stock-row-${s.id}" style="${rowBg}">
            <td><code style="background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;font-size:0.78rem;">${s.code}</code></td>
            <td><strong>${s.name}</strong><div style="font-size:0.75rem;color:var(--text-muted);">${s.name_en || ''}</div></td>
            <td><span class="pill">${s.category || '—'}</span></td>
            <td>฿${(s.cost||0).toLocaleString('th-TH')}</td>
            <td style="color:#34d399;font-weight:600;">฿${(s.price||0).toLocaleString('th-TH')}</td>
            <td><strong>${s.quantity}</strong> ${s.unit}${s.reserved ? `<div style="font-size:0.72rem;color:#fbbf24;" title="จองไว้สำหรับงานซ่อมที่ยังไม่เสร็จ">จอง ${s.reserved} · ขายได้ ${s.available}</div>` : ''}</td>
            <td>${s.quantity <= s.reorder_level ? '<span class="status-badge pending">⚠️ ควรสั่งซื้อ</span>' : '<span class="status-badge approved">✓ ปกติ</span>'}</td>
            <td style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                ${s.bill_path ? `<button class="btn-sm" style="color:#c4b5fd;background:rgba(167,139,250,0.15);border:1px solid rgba(167,139,250,0.35);padding:4px 8px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;border-radius:6px;" onclick="viewBillImg('${s.bill_path}')" title="ดูรูปภาพบิลจัดซื้อ"><i data-lucide="receipt" style="width:12px;height:12px;"></i> บิล</button>` : ''}
                <button class="btn-sm" onclick="quickAdjustStock(${s.id})">ปรับสต็อก</button>
                <button class="btn-sm" onclick="fxPrintLabels([${s.id}])" title="พิมพ์ฉลากบาร์โค้ด">🏷️</button>
                <button class="btn-sm" style="color:#60a5fa;background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.3);padding:4px 8px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;" onclick="openEditStockModal(${s.id})" title="แก้ไขสินค้า"><i data-lucide="pencil" style="width:12px;height:12px;"></i> แก้ไข</button>
                <button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);padding:4px 8px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;" onclick="deleteStockItem(${s.id})" title="ลบสินค้า"><i data-lucide="trash-2" style="width:12px;height:12px;"></i> ลบ</button>
            </td>
        </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function quickAdjustStock(id, name) {
    const item = (allStock || []).find(x => x.id === id);
    const itemName = name || item?.name || 'สินค้า';
    const delta = prompt(`ปรับจำนวน "${itemName}"\nพิมพ์ + หรือ - เช่น +10 หรือ -3:`, '+1');
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
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาด')); }
}

async function loadStockHistory() {
    const container = document.getElementById('stock-history-list');
    if (!container) return;
    try {
        const res = await fetch(`${API_URL}/stock/history/all?limit=30`, { headers: HEADERS });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
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

// ── CUSTOMERS 360° & MANUAL CUSTOMER MANAGEMENT ──
let currentProfileCustomerId = null;
let currentProfileData = null;

async function renderCustomersTable(filterText = '') {
    const tbody = document.getElementById('customers-tbody');
    if (!tbody) return;
    
    let list = allCustomers;
    const q = (filterText || document.getElementById('cust-search-input')?.value || '').trim().toLowerCase();
    if (q) {
        list = list.filter(c => {
            const name = (c.name || '').toLowerCase();
            const phone = (c.phone || '').toLowerCase();
            const line = (c.line_id || '').toLowerCase();
            const email = (c.email || '').toLowerCase();
            return name.includes(q) || phone.includes(q) || line.includes(q) || email.includes(q);
        });
    }

    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted);">${q ? 'ไม่พบข้อมูลลูกค้าที่ตรงกับการค้นหา' : 'ไม่มีข้อมูลลูกค้า'}</td></tr>`;
        return;
    }

    tbody.innerHTML = list.map(c => {
        const lineBadge = c.line_id
            ? `<span class="pill" style="background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid rgba(34,197,94,0.3);font-size:0.75rem;display:inline-flex;align-items:center;gap:4px;" title="LINE ID: ${c.line_id}"><i data-lucide="message-circle" style="width:12px;height:12px;"></i> ${c.line_id}</span>`
            : `<button class="btn-sm" style="padding:2px 8px;font-size:0.72rem;color:#4ade80;background:rgba(34,197,94,0.08);border:1px dashed rgba(34,197,94,0.4);border-radius:4px;cursor:pointer;" onclick="openEditCustomerModal(${c.id})"><i data-lucide="plus" style="width:10px;height:10px;display:inline-block;vertical-align:-1px;"></i> ใส่ LINE ID</button>`;

        const safeName = (c.name || '').replace(/'/g, "\\'");

        return `
            <tr id="cust-row-${c.id}">
                <td><strong>${c.name}</strong></td>
                <td><span style="font-family:monospace;font-size:0.85rem;">${c.phone || '—'}</span></td>
                <td>${lineBadge}</td>
                <td><span class="cust-cars-count" style="color:var(--text-muted);">กำลังโหลด...</span></td>
                <td><span class="cust-plate-preview" style="color:var(--text-muted);">—</span></td>
                <td><span class="cust-tickets-count" style="color:var(--text-muted);">—</span></td>
                <td>
                    <div style="display:flex;gap:5px;align-items:center;">
                        <button class="btn-primary" style="padding:4px 8px;font-size:0.75rem;display:inline-flex;align-items:center;gap:3px;" onclick="viewCustomerProfile(${c.id})" title="ดูข้อมูล 360°"><i data-lucide="eye" style="width:12px;height:12px;"></i> 360°</button>
                        <button class="btn-secondary" style="padding:4px 8px;font-size:0.75rem;display:inline-flex;align-items:center;gap:3px;" onclick="openEditCustomerModal(${c.id})" title="แก้ไขข้อมูลลูกค้า"><i data-lucide="edit-3" style="width:12px;height:12px;"></i> แก้ไข</button>
                        <button class="btn-secondary" style="padding:4px 8px;font-size:0.75rem;color:#38bdf8;border-color:rgba(56,189,248,0.3);display:inline-flex;align-items:center;gap:3px;" onclick="openAddVehicleModal(${c.id}, '${safeName}')" title="เพิ่มรถยนต์ให้ลูกค้ารายนี้"><i data-lucide="car" style="width:12px;height:12px;"></i> +รถ</button>
                        <button class="btn-secondary" style="padding:4px 6px;font-size:0.75rem;color:#f87171;border-color:rgba(248,113,113,0.3);" onclick="deleteCustomer(${c.id}, '${safeName}')" title="ลบข้อมูลลูกค้า"><i data-lucide="trash-2" style="width:12px;height:12px;"></i></button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();

    // Load profile details per customer in parallel
    list.forEach(async c => {
        try {
            const res = await fetch(`${API_URL}/customers/${c.id}/profile`, { headers: HEADERS });
            if (!res.ok) return;
            const profile = await res.json();
            const vehicles = profile.vehicles || [];
            const tickets = profile.ticket_history || [];
            const row = document.getElementById(`cust-row-${c.id}`);
            if (row) {
                const carsCell = row.querySelector('.cust-cars-count');
                const plateCell = row.querySelector('.cust-plate-preview');
                const ticketsCell = row.querySelector('.cust-tickets-count');
                if (carsCell) carsCell.innerHTML = `<strong style="color:#60a5fa;">${vehicles.length} คัน</strong>`;
                if (plateCell) plateCell.innerHTML = vehicles[0] ? `<span class="pill" style="font-size:0.75rem;">${vehicles[0].plate}</span>` : '—';
                if (ticketsCell) ticketsCell.innerHTML = `${tickets.length} ครั้ง`;
            }
        } catch {}
    });
}

function filterCustomersTable() {
    renderCustomersTable();
}

async function viewCustomerProfile(id) {
    try {
        currentProfileCustomerId = id;
        const res = await fetch(`${API_URL}/customers/${id}/profile`, { headers: HEADERS });
        const profile = await res.json();
        currentProfileData = profile;
        const c = profile.customer;
        const vehicles = profile.vehicles || [];
        const tickets = profile.ticket_history || [];
        const totalSpent = tickets.reduce((acc, t) => acc + (t.final_cost || t.total_estimated_cost || 0), 0);

        document.getElementById('profile-modal-name').textContent = `👤 ${c.name}`;
        
        const lineText = c.line_id 
            ? `<span style="color:#4ade80;font-weight:600;"><i data-lucide="message-circle" style="width:13px;height:13px;display:inline-block;vertical-align:-1px;"></i> LINE: ${c.line_id}</span>`
            : `<button class="btn-sm" style="padding:1px 6px;font-size:0.72rem;color:#4ade80;background:rgba(34,197,94,0.1);border:1px dashed rgba(34,197,94,0.4);" onclick="openEditCustomerModal(${c.id})">+ เพิ่ม LINE ID</button>`;

        document.getElementById('profile-modal-sub').innerHTML = `📞 ${c.phone || '—'}  |  ${lineText}  |  📧 ${c.email || '—'}`;

        document.getElementById('profile-stats').innerHTML = `
            <div class="profile-stat-card"><div class="val">${vehicles.length}</div><div class="lbl">จำนวนรถ</div></div>
            <div class="profile-stat-card"><div class="val">${tickets.length}</div><div class="lbl">งานซ่อมทั้งหมด</div></div>
            <div class="profile-stat-card"><div class="val">฿${totalSpent.toLocaleString('th-TH')}</div><div class="lbl">ยอดใช้จ่ายทั้งหมด</div></div>
        `;

        document.getElementById('profile-cars').innerHTML = vehicles.length
            ? vehicles.map(v => `
                <div class="profile-car-chip">
                    <i data-lucide="car" style="width:14px;height:14px;"></i>
                    <strong>${v.plate}</strong> — ${v.brand} ${v.model} (${v.year || '—'})
                    <span style="font-size:0.72rem;color:var(--text-muted);">${(v.current_mileage||0).toLocaleString()} กม.</span>
                </div>
            `).join('')
            : `<span style="color:var(--text-muted);font-size:0.82rem;">ยังไม่มีรถยนต์ในระบบ</span>`;

        document.getElementById('profile-history-tbody').innerHTML = tickets.length
            ? tickets.map(t => `
                <tr>
                    <td style="color:#93c5fd;">#${t.id}</td>
                    <td style="font-size:0.78rem;color:var(--text-muted);">${t.created_at ? new Date(t.created_at).toLocaleDateString('th-TH') : '—'}</td>
                    <td>${t.vehicle_plate || '—'}</td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.raw_input || '—'}</td>
                    <td style="color:#34d399;font-weight:600;">฿${(t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH')}</td>
                    <td>${statusBadgeHtml(t.status)}${fxDecisionBadge(t)}</td>
                </tr>
            `).join('')
            : `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:12px;">ยังไม่มีประวัติงานซ่อม</td></tr>`;

        document.getElementById('profile-modal').style.display = 'flex';
        if (window.lucide) lucide.createIcons();
    } catch (e) { showToast('❌ ' + (e.message || 'ไม่สามารถโหลดข้อมูลลูกค้าได้')); }
}

function closeProfileModal() {
    document.getElementById('profile-modal').style.display = 'none';
}

function editCurrentProfileCustomer() {
    if (currentProfileCustomerId) {
        openEditCustomerModal(currentProfileCustomerId);
    }
}

function addVehicleToCurrentProfileCustomer() {
    if (currentProfileCustomerId) {
        const custName = currentProfileData?.customer?.name || 'ลูกค้า';
        openAddVehicleModal(currentProfileCustomerId, custName);
    }
}

// ── ADD / EDIT CUSTOMER MODAL LOGIC ──
function openAddCustomerModal() {
    document.getElementById('customer-modal-title').innerHTML = '<i data-lucide="user-plus"></i> เพิ่มลูกค้าใหม่';
    document.getElementById('cust-modal-id').value = '';
    document.getElementById('cust-modal-name').value = '';
    document.getElementById('cust-modal-phone').value = '';
    document.getElementById('cust-modal-line').value = '';
    document.getElementById('cust-modal-email').value = '';
    
    // Reset initial car fields and show section
    document.getElementById('cust-modal-plate').value = '';
    document.getElementById('cust-modal-brand').value = '';
    document.getElementById('cust-modal-model').value = '';
    document.getElementById('cust-modal-mileage').value = '';
    const carSection = document.getElementById('cust-modal-car-section');
    if (carSection) carSection.style.display = 'block';

    document.getElementById('customer-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
    setTimeout(() => document.getElementById('cust-modal-name')?.focus(), 50);
}

async function openEditCustomerModal(id) {
    let customer = allCustomers.find(c => c.id === id);
    if (!customer) {
        try {
            const res = await fetch(`${API_URL}/customers/${id}`, { headers: HEADERS });
            if (res.ok) customer = await res.json();
        } catch {}
    }
    if (!customer) return alert('ไม่พบข้อมูลลูกค้า');

    document.getElementById('customer-modal-title').innerHTML = `<i data-lucide="edit-3"></i> แก้ไขข้อมูลลูกค้า: ${customer.name}`;
    document.getElementById('cust-modal-id').value = customer.id;
    document.getElementById('cust-modal-name').value = customer.name || '';
    document.getElementById('cust-modal-phone').value = customer.phone || '';
    document.getElementById('cust-modal-line').value = customer.line_id || '';
    document.getElementById('cust-modal-email').value = customer.email || '';

    // Hide optional initial car section when editing an existing customer
    const carSection = document.getElementById('cust-modal-car-section');
    if (carSection) carSection.style.display = 'none';

    document.getElementById('customer-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
    setTimeout(() => document.getElementById('cust-modal-line')?.focus(), 50);
}

function closeCustomerModal() {
    document.getElementById('customer-modal').style.display = 'none';
}

async function submitCustomerModal() {
    const id = document.getElementById('cust-modal-id').value;
    const name = document.getElementById('cust-modal-name').value.trim();
    const phone = document.getElementById('cust-modal-phone').value.trim();
    const lineId = document.getElementById('cust-modal-line').value.trim();
    const email = document.getElementById('cust-modal-email').value.trim();

    if (!name) return alert('กรุณากรอกชื่อลูกค้า');
    if (!phone) return alert('กรุณากรอกเบอร์โทรศัพท์');

    try {
        if (id) {
            // Update customer
            const payload = {
                name,
                phone,
                line_id: lineId || null,
                email: email || null
            };
            const res = await fetch(`${API_URL}/customers/${id}`, {
                method: 'PUT',
                headers: HEADERS,
                body: JSON.stringify(payload)
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                return alert(_apiErrorText(err, 'เกิดข้อผิดพลาดในการแก้ไขข้อมูลลูกค้า'));
            }
            showToast('✅ อัปเดตข้อมูลลูกค้าเรียบร้อยแล้ว');
            closeCustomerModal();
            await fetchCustomersData();
            if (currentProfileCustomerId === parseInt(id)) {
                viewCustomerProfile(parseInt(id));
            }
        } else {
            // Create new customer
            const plate = document.getElementById('cust-modal-plate')?.value.trim();
            const brand = document.getElementById('cust-modal-brand')?.value.trim();
            const model = document.getElementById('cust-modal-model')?.value.trim();
            const mileage = document.getElementById('cust-modal-mileage')?.value;

            const payload = {
                name,
                phone,
                line_id: lineId || null,
                email: email || null,
                plate: plate || null,
                brand: brand || null,
                model: model || null,
                mileage: mileage ? parseInt(mileage) : null
            };
            const res = await fetch(`${API_URL}/customers/`, {
                method: 'POST',
                headers: HEADERS,
                body: JSON.stringify(payload)
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                return alert(_apiErrorText(err, 'เกิดข้อผิดพลาดในการสร้างลูกค้าใหม่'));
            }
            const created = await res.json();
            showToast(`✅ เพิ่มลูกค้าใหม่ "${created.name}" สำเร็จ`);
            closeCustomerModal();
            await fetchCustomersData();
        }
    } catch (e) {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์');
    }
}

async function deleteCustomer(id, name) {
    if (!confirm(`คุณต้องการลบข้อมูลลูกค้า "${name}" ใช่หรือไม่?`)) return;
    try {
        const res = await fetch(`${API_URL}/customers/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return alert(_apiErrorText(err, 'ไม่สามารถลบข้อมูลลูกค้าได้'));
        }
        showToast(`🗑️ ลบข้อมูลลูกค้า "${name}" สำเร็จ`);
        if (currentProfileCustomerId === id) closeProfileModal();
        await fetchCustomersData();
    } catch {
        alert('เกิดข้อผิดพลาดในการลบข้อมูล');
    }
}

async function deleteTicket(id) {
    if (!confirm(`คุณต้องการลบงานซ่อม #${id} ใช่หรือไม่?\n(การดำเนินการนี้ไม่สามารถยกเลิกได้)`)) return;
    try {
        const res = await fetch(`${API_URL}/tickets/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return showToast(_apiErrorText(err, 'ไม่สามารถลบงานซ่อมได้'), 'danger');
        }
        showToast(`🗑️ ลบงานซ่อม #${id} สำเร็จ`);
        if (typeof closeTicketDetailModal === 'function') closeTicketDetailModal();
        await fetchTicketsData();
        if (typeof renderFullRepairsTable === 'function') renderFullRepairsTable();
        if (typeof renderTicketsTable === 'function') renderTicketsTable();
    } catch {
        showToast('เกิดข้อผิดพลาดในการลบงานซ่อม', 'danger');
    }
}

// ── EDIT TICKET ──
let _editingTicket = null;
const _MECH_LINE_RE = /ช่างผู้รับงาน:\s*[^\n\r|]*/;

function openEditTicketModal(id) {
    const t = (allTickets || []).find(x => x.id === id);
    if (!t) return showToast('❌ ไม่พบงานซ่อม');
    _editingTicket = t;
    const set = (elId, v) => { const el = document.getElementById(elId); if (el) el.value = v ?? ''; };
    document.getElementById('edit-ticket-title-id').textContent = `#${t.id}`;
    set('edit-ticket-plate', t.vehicle_plate);
    set('edit-ticket-car-model', t.car_model);
    set('edit-ticket-customer', t.customer_name);
    set('edit-ticket-phone', t.customer_phone);
    set('edit-ticket-line-id', t.customer_line_id);
    set('edit-ticket-mechanic', t.mechanic_name);
    set('edit-ticket-mileage', t.mileage);
    set('edit-ticket-status', t.status);
    set('edit-ticket-final-cost', t.final_cost);
    set('edit-ticket-notes', (t.mechanic_notes || '').replace(_MECH_LINE_RE, '').replace(/^[\s|]+|[\s|]+$/g, ''));
    set('edit-ticket-warranty-months', t.warranty_months || '');
    set('edit-ticket-warranty-note', t.warranty_note || '');
    if (typeof fxRenderPhotos === 'function') fxRenderPhotos(t);

    const container = document.getElementById('edit-ticket-lines');
    container.innerHTML = '';
    (t.line_items || []).forEach(i => {
        const qty = i.qty || 1;
        addIntakeLine(i.name_th || i.name, i.unit_price ?? (i.total / qty), 'edit-ticket-lines', qty, i.stock_item_id || null);
    });
    if (!(t.line_items || []).length) addIntakeLine('', '', 'edit-ticket-lines');
    if (!allStock.length) fetchStockData();
    updateIntakeTotal();
    document.getElementById('edit-ticket-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeEditTicketModal() {
    document.getElementById('edit-ticket-modal').style.display = 'none';
    closeIntakePartDropdown();
    _editingTicket = null;
}

async function submitEditTicket() {
    const t = _editingTicket;
    if (!t) return;
    const val = id => document.getElementById(id)?.value.trim() || '';
    const rows = _readLineRows('edit-ticket-lines');
    const lineTotal = rows.reduce((s, r) => s + r.total, 0);
    const oldItems = t.line_items || [];
    const mechanic = val('edit-ticket-mechanic');
    const notes = val('edit-ticket-notes');
    const newStatus = val('edit-ticket-status');
    const finalCost = parseFloat(val('edit-ticket-final-cost'));

    const payload = {
        customer_name: val('edit-ticket-customer') || null,
        customer_phone: val('edit-ticket-phone') || null,
        customer_line_id: val('edit-ticket-line-id'),
        vehicle_plate: val('edit-ticket-plate') || null,
        car_model: val('edit-ticket-car-model') || null,
        mechanic_notes: [mechanic ? `ช่างผู้รับงาน: ${mechanic}` : '', notes].filter(Boolean).join('\n'),
        line_items: rows.map(r => {
            const old = oldItems.find(i => (i.name_th || i.name) === r.desc);
            return {
                name: r.desc, name_th: r.desc, qty: r.qty, unit_price: r.price, total: r.total,
                type: old?.type || (r.stockId ? 'part' : null),
                stock_item_id: r.stockId,
            };
        }),
        final_cost: isNaN(finalCost) ? lineTotal : finalCost,
        warranty_months: parseInt(val('edit-ticket-warranty-months')) || 0,
        warranty_note: val('edit-ticket-warranty-note'),
    };
    const mileage = parseInt(val('edit-ticket-mileage'));
    if (!isNaN(mileage)) payload.mileage = mileage;
    // Completing goes through the normal "complete" step so income and stock are handled there
    const completingNow = newStatus === 'COMPLETED' && t.status !== 'COMPLETED';
    if (!completingNow) payload.status = newStatus;

    try {
        let res = await fetch(`${API_URL}/tickets/${t.id}`, { method: 'PUT', headers: HEADERS, body: JSON.stringify(payload) });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({}))));
        if (completingNow) {
            res = await fetch(`${API_URL}/tickets/${t.id}/complete`, {
                method: 'POST', headers: HEADERS,
                body: JSON.stringify({ final_cost: payload.final_cost, completed_by: mechanic || 'ช่างประจำ' })
            });
            if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({}))));
        }
        showToast(`✅ แก้ไขงานซ่อม #${t.id} เรียบร้อย`);
        closeEditTicketModal();
        await fetchTicketsData();
        if (typeof renderFullRepairsTable === 'function') renderFullRepairsTable();
        if (completingNow) fetchStockData();
    } catch (e) {
        showToast('❌ แก้ไขไม่สำเร็จ: ' + e.message);
    }
}

async function deleteAppointment(id, name) {
    const appt = (allAppointments || []).find(x => x.id === id);
    const apptName = name || appt?.customer_name || 'นัดหมายนี้';
    if (!confirm(`คุณต้องการลบนัดหมาย "${apptName}" ใช่หรือไม่?`)) return;
    try {
        const res = await fetch(`${API_URL}/appointments/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return showToast(_apiErrorText(err, 'ไม่สามารถลบนัดหมายได้'), 'danger');
        }
        showToast(`🗑️ ลบนัดหมาย "${apptName}" สำเร็จ`);
        await fetchAppointments();
        const card = document.getElementById('appt-day-card');
        if (card && card.style.display !== 'none') {
            renderCalendar();
        }
    } catch {
        showToast('เกิดข้อผิดพลาดในการลบนัดหมาย', 'danger');
    }
}

async function deleteStockItem(id, name) {
    const item = (allStock || []).find(x => x.id === id);
    const itemName = name || item?.name || 'สินค้านี้';
    if (!confirm(`คุณต้องการลบสินค้า "${itemName}" ออกจากสต็อก ใช่หรือไม่?\n(การดำเนินการนี้ไม่สามารถยกเลิกได้)`)) return;
    try {
        const res = await fetch(`${API_URL}/stock/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return showToast(_apiErrorText(err, 'ไม่สามารถลบสินค้าได้'), 'danger');
        }
        showToast(`🗑️ ลบสินค้า "${itemName}" สำเร็จ`);
        await fetchStockData();
        loadStockHistory();
    } catch {
        showToast('เกิดข้อผิดพลาดในการลบสินค้า', 'danger');
    }
}

async function deleteSupplier(id, name) {
    const sup = (allSuppliers || []).find(x => x.id === id);
    const supName = name || sup?.name || 'ผู้จัดจำหน่ายนี้';
    if (!confirm(`คุณต้องการลบผู้จัดจำหน่าย "${supName}" ใช่หรือไม่?\n(ข้อมูลการสั่งซื้อที่เกี่ยวข้องอาจถูกลบด้วย)`)) return;
    try {
        const res = await fetch(`${API_URL}/suppliers/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return showToast(_apiErrorText(err, 'ไม่สามารถลบผู้จัดจำหน่ายได้'), 'danger');
        }
        showToast(`🗑️ ลบผู้จัดจำหน่าย "${supName}" สำเร็จ`);
        await loadSuppliers();
    } catch {
        showToast('เกิดข้อผิดพลาดในการลบผู้จัดจำหน่าย', 'danger');
    }
}


// ── ADD VEHICLE MODAL LOGIC ──
function openAddVehicleModal(customerId, customerName) {
    document.getElementById('veh-modal-cust-id').value = customerId;
    document.getElementById('veh-modal-cust-name-label').textContent = customerName || `#${customerId}`;
    document.getElementById('veh-modal-plate').value = '';
    document.getElementById('veh-modal-brand').value = 'Toyota';
    document.getElementById('veh-modal-model').value = '';
    document.getElementById('veh-modal-year').value = new Date().getFullYear();
    document.getElementById('veh-modal-color').value = '';
    document.getElementById('veh-modal-mileage').value = '';

    document.getElementById('cust-vehicle-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
    setTimeout(() => document.getElementById('veh-modal-plate')?.focus(), 50);
}

function closeAddVehicleModal() {
    document.getElementById('cust-vehicle-modal').style.display = 'none';
}

async function submitAddVehicleModal() {
    const customerId = document.getElementById('veh-modal-cust-id').value;
    const plate = document.getElementById('veh-modal-plate').value.trim();
    const brand = document.getElementById('veh-modal-brand').value.trim() || 'Toyota';
    const model = document.getElementById('veh-modal-model').value.trim() || 'รถยนต์';
    const yearVal = document.getElementById('veh-modal-year').value;
    const color = document.getElementById('veh-modal-color').value.trim() || null;
    const mileageVal = document.getElementById('veh-modal-mileage').value;

    if (!plate) return alert('กรุณากรอกทะเบียนรถ');

    try {
        const payload = {
            plate,
            brand,
            model,
            year: yearVal ? parseInt(yearVal) : null,
            color,
            current_mileage: mileageVal ? parseInt(mileageVal) : 0
        };
        const res = await fetch(`${API_URL}/customers/${customerId}/vehicles`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            return alert(_apiErrorText(err, 'เกิดข้อผิดพลาดในการเพิ่มรถยนต์'));
        }
        showToast(`🚗 เพิ่มรถยนต์ทะเบียน "${plate}" สำเร็จ!`);
        closeAddVehicleModal();
        await fetchCustomersData();
        if (currentProfileCustomerId === parseInt(customerId)) {
            viewCustomerProfile(parseInt(customerId));
        }
    } catch {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์');
    }
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
            if (!a.appointment_date) return false;
            const rawDate = a.appointment_date.split('T')[0];
            if (rawDate === dateStr) return true;
            const ad = new Date(a.appointment_date);
            return ad.getFullYear() === calYear && ad.getMonth() === calMonth && ad.getDate() === d;
        });
        const chipsHtml = dayAppts.slice(0, 3).map(a =>
            `<div class="cal-appt-chip ${a.status}" onclick="showDayAppts('${dateStr}', event, true)" title="${a.customer_name}: ${a.service_type || ''}" style="display:flex;justify-content:space-between;align-items:center;padding:2px 4px;">
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${a.time_slot || ''} ${a.customer_name}</span>
                <span onclick="event.stopPropagation();deleteAppointment(${a.id})" style="cursor:pointer;color:#fca5a5;padding:0 3px;margin-left:3px;font-weight:bold;border-radius:3px;font-size:0.75rem;" onmouseover="this.style.background='rgba(239,68,68,0.3)'" onmouseout="this.style.background='transparent'" title="ลบนัดหมาย">✕</span>
            </div>`
        ).join('');
        cells += `<div class="cal-day${isToday ? ' today' : ''}" onclick="showDayAppts('${dateStr}', event, true)">
            <div class="day-num">${d}</div>
            ${chipsHtml}
            ${dayAppts.length > 3 ? `<div style="font-size:0.65rem;color:var(--text-muted);margin-top:2px;">+${dayAppts.length - 3} เพิ่มเติม</div>` : ''}
        </div>`;
    }
    gridEl.innerHTML = cells;

    // Automatically display today's appointments in day card
    const todayDateStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    showDayAppts(todayDateStr, null, false);
}

function showDayAppts(dateStr, e, shouldScroll = true) {
    if (e) e.stopPropagation();
    const card = document.getElementById('appt-day-card');
    const titleEl = document.getElementById('appt-day-title');
    const listEl = document.getElementById('appt-day-list');
    if (!card) return;

    const dayAppts = allAppointments.filter(a => {
        if (!a.appointment_date) return false;
        const rawDate = a.appointment_date.split('T')[0];
        if (rawDate === dateStr) return true;
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
            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border);gap:8px;">
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:700;">${a.time_slot || '—'} น. — <span style="color:#60a5fa;">${a.customer_name}</span></div>
                    <div style="font-size:0.82rem;color:var(--text-muted);margin-top:2px;">${a.vehicle_plate || ''} ${a.vehicle_info || ''} | ${a.service_type || ''}</div>
                    ${a.customer_phone ? `<div style="font-size:0.78rem;color:var(--text-muted);">📞 ${a.customer_phone}</div>` : ''}
                </div>
                <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                    <span class="cal-appt-chip ${a.status}" style="font-size:0.75rem;padding:4px 10px;">${
                        {confirmed:'✅ ยืนยัน', pending:'⏳ รอยืนยัน', completed:'🏁 เสร็จสิ้น', cancelled:'❌ ยกเลิก'}[a.status] || a.status
                    }</span>
                    <button class="btn-sm" style="color:#60a5fa;background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.3);border-radius:6px;padding:4px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;" onclick="openEditAppointmentModal(${a.id})" title="แก้ไขนัดหมาย"><i data-lucide="pencil" style="width:13px;height:13px;"></i> แก้ไข</button>
                    <button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.35);border-radius:6px;padding:4px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;" onclick="deleteAppointment(${a.id})" title="ลบนัดหมาย"><i data-lucide="trash-2" style="width:13px;height:13px;"></i> ลบ</button>
                </div>
            </div>
        `).join('');
    }

    card.style.display = 'block';
    lucide.createIcons();
    if (shouldScroll) {
        card.scrollIntoView({ behavior: 'smooth' });
    }
}

// ── SUPPLIERS ──
async function loadSuppliers() {
    const grid = document.getElementById('supplier-grid');
    if (!grid) return;
    try {
        const res = await fetch(`${API_URL}/suppliers/`, { headers: HEADERS });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        allSuppliers = await res.json();
        if (!allSuppliers.length) {
            grid.innerHTML = `<p style="color:var(--text-muted);padding:20px;">ยังไม่มีผู้จำหน่าย</p>`;
            return;
        }
        grid.innerHTML = allSuppliers.map(s => `
            <div class="supplier-card" id="supplier-card-${s.id}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <div class="sup-name" style="margin-bottom:0;cursor:pointer;color:#93c5fd;font-weight:700;" onclick="openSupplierDetailModal(${s.id})" title="คลิกเพื่อดูข้อมูลผู้จำหน่าย">🏭 ${s.name}</div>
                    <div style="display:flex;gap:4px;flex-shrink:0;">
                        <button class="btn-sm" style="color:#60a5fa;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.35);border-radius:6px;padding:3px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;" onclick="openEditSupplierModal(${s.id})" title="แก้ไขผู้จำหน่าย"><i data-lucide="pencil" style="width:12px;height:12px;"></i> แก้ไข</button>
                        <button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.35);border-radius:6px;padding:3px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;" onclick="deleteSupplier(${s.id})" title="ลบผู้จำหน่าย"><i data-lucide="trash-2" style="width:12px;height:12px;"></i> ลบ</button>
                    </div>
                </div>
                ${s.phone ? `<div class="sup-info"><i data-lucide="phone" style="width:13px;height:13px;"></i> ${s.phone}</div>` : ''}
                ${s.email ? `<div class="sup-info"><i data-lucide="mail" style="width:13px;height:13px;"></i> ${s.email}</div>` : ''}
                ${s.line_id ? `<div class="sup-info"><i data-lucide="message-circle" style="width:13px;height:13px;"></i> LINE: ${s.line_id}</div>` : ''}
                ${s.address ? `<div class="sup-info" style="font-size:0.75rem;"><i data-lucide="map-pin" style="width:12px;height:12px;"></i> ${s.address}</div>` : ''}
                <div class="sup-stats">
                    <div class="sup-stat"><div class="n">${s.total_purchases || 0}</div><div class="l">ใบสั่งซื้อ</div></div>
                    <div class="sup-stat"><div class="n">฿${(s.total_amount || 0).toLocaleString('th-TH')}</div><div class="l">ยอดซื้อรวม</div></div>
                </div>
                <div style="display:flex;gap:6px;margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.06);">
                    <button class="btn-sm" style="flex:1;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);color:#60a5fa;display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:6px 10px;cursor:pointer;border-radius:6px;font-weight:600;font-size:0.8rem;" onclick="openSupplierDetailModal(${s.id})">
                        <i data-lucide="info" style="width:13px;height:13px;"></i> ดูข้อมูลเพิ่มเติม
                    </button>
                    <button class="btn-sm" style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.35);color:#34d399;display:inline-flex;align-items:center;justify-content:center;gap:4px;padding:6px 10px;cursor:pointer;border-radius:6px;font-size:0.8rem;" onclick="openAddPurchaseModalForSupplierId(${s.id})" title="สั่งซื้ออะไหล่">
                        <i data-lucide="plus" style="width:13px;height:13px;"></i> สั่งซื้อ
                    </button>
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
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        allPurchases = await res.json();
        if (!allPurchases.length) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ยังไม่มีประวัติการจัดซื้อ</td></tr>`;
            return;
        }
        tbody.innerHTML = allPurchases.map(b => `
            <tr>
                <td><strong style="color:#93c5fd;">${b.bill_number || '#' + b.id}</strong></td>
                <td style="font-size:0.82rem;color:var(--text-muted);">${b.bill_date ? new Date(b.bill_date).toLocaleDateString('th-TH') : '—'}</td>
                <td><strong>${b.supplier_name || 'ไม่ระบุ'}</strong></td>
                <td style="font-size:0.8rem;color:var(--text-secondary);">${(b.items || []).map(i => `${i.name} (${i.qty})`).join(', ') || '—'}</td>
                <td style="color:#34d399;font-weight:700;">฿${(b.total_amount || 0).toLocaleString('th-TH')}</td>
                <td style="font-size:0.8rem;color:var(--text-muted);">
                    ${b.notes || '—'}
                    ${b.image_path ? `<div style="margin-top:4px;"><span class="bill-img-link" onclick="viewBillImg('${b.image_path}')" style="cursor:pointer;color:#60a5fa;display:inline-flex;align-items:center;gap:4px;">📎 ดูบิล</span></div>` : ''}
                </td>
                <td style="text-align:center;white-space:nowrap;">
                    <button class="btn-sm" style="color:#60a5fa;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.35);border-radius:6px;padding:4px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;margin-right:4px;" onclick="openEditPurchaseModal(${b.id})" title="แก้ไขบิลจัดซื้อ">
                        <i data-lucide="pencil" style="width:12px;height:12px;"></i> แก้ไข
                    </button>
                    <button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:6px;padding:4px 8px;cursor:pointer;" onclick="deletePurchaseBill(${b.id})" title="ลบรายการบิล">
                        <i data-lucide="trash-2" style="width:13px;height:13px;"></i>
                    </button>
                </td>
            </tr>
        `).join('');
        if (window.lucide) lucide.createIcons();
    } catch {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

// ── POS HISTORY ──
let posHistoryFilter = 'pos_sale';
async function loadPOSHistory() {
    const tbody = document.getElementById('pos-history-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted);">กำลังโหลด...</td></tr>`;
    try {
        // Combine purchases and work orders for a full parts history
        const [purchRes, woRes] = await Promise.all([
            fetch(`${API_URL}/suppliers/purchases/all`, { headers: HEADERS }),
            fetch(`${API_URL}/stock/workorders/`, { headers: HEADERS }),
        ]);
        const purchases = purchRes.ok ? await purchRes.json() : [];
        const workorders = woRes.ok ? await woRes.json() : [];

        let rows = [];
        // Purchase rows (จัดซื้ออะไหล่เข้าอู่)
        purchases.forEach(b => {
            (b.items || []).forEach(item => {
                rows.push({
                    type: 'purchase',
                    bill_id: b.id,
                    date: b.bill_date,
                    label: '📦 จัดซื้อ',
                    name: item.name,
                    qty: item.qty,
                    unit_price: item.unit_price,
                    total: item.total || (item.qty * item.unit_price),
                    ref: `บิลจัดซื้อ ${b.bill_number || '#' + b.id} (${b.supplier_name || 'ไม่ระบุ'})`,
                    image_path: b.image_path
                });
            });
        });
        // Work order rows (แยกงานซ่อม กับ คนซื้ออะไหล่อย่างเดียว)
        workorders.forEach(wo => {
            const items = wo.line_items ? (typeof wo.line_items === 'string' ? JSON.parse(wo.line_items) : wo.line_items) : [];
            const isPOS = !wo.vehicle_plate || (wo.description && wo.description.includes('POS')) || wo.mechanic_name === 'หน้าร้าน (POS)' || (wo.labor_cost === 0 && !wo.vehicle_plate);

            items.filter(i => i.name && !i.name.includes('Labor') && !i.name.includes('ค่าแรง')).forEach(item => {
                rows.push({
                    type: isPOS ? 'pos_sale' : 'repair',
                    wo_id: wo.id,
                    date: wo.work_date || wo.created_at,
                    label: isPOS ? '🛒 ขายอะไหล่ (POS)' : '🔧 ใช้ในซ่อม',
                    name: item.name,
                    qty: item.qty,
                    unit_price: item.unit_price,
                    total: item.total || (item.qty * item.unit_price),
                    ref: isPOS
                        ? `บิลขาย #${wo.id} (${wo.customer_name || 'ลูกค้าทั่วไป'})`
                        : `Work Order #${wo.id} (${wo.vehicle_plate || '—'})`,
                    customer: wo.customer_name || 'ลูกค้าทั่วไป',
                    is_pos: isPOS
                });
            });
        });

        // Filter
        if (posHistoryFilter !== 'all') {
            rows = rows.filter(r => r.type === posHistoryFilter);
        }
        rows.sort((a, b) => new Date(b.date) - new Date(a.date));

        if (!rows.length) {
            const emptyMsg = posHistoryFilter === 'pos_sale'
                ? 'ยังไม่มีรายการคนซื้ออะไหล่ — คลิก "+ บันทึกคนซื้ออะไหล่ (POS)" เพื่อเริ่มบันทึก'
                : 'ไม่มีประวัติ';
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:28px 16px;color:var(--text-muted);font-size:0.9rem;">
                <div style="margin-bottom:8px;font-size:1.6rem;">🛒</div>
                ${emptyMsg}
            </td></tr>`;
            return;
        }
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td style="font-size:0.78rem;color:var(--text-muted);">${r.date ? new Date(r.date).toLocaleDateString('th-TH') : '—'}</td>
                <td><span class="pill" style="${r.type === 'pos_sale' ? 'background:rgba(16,185,129,0.18);color:#34d399;border:1px solid rgba(16,185,129,0.35);font-weight:600;' : ''}">${r.label}</span></td>
                <td><strong>${r.name}</strong></td>
                <td style="text-align:center;">${r.qty}</td>
                <td>฿${(r.unit_price||0).toLocaleString('th-TH')}</td>
                <td style="color:#34d399;font-weight:600;">฿${(r.total||0).toLocaleString('th-TH')}</td>
                <td style="font-size:0.78rem;color:var(--text-muted);">
                    ${r.ref}
                    ${r.image_path ? `<span onclick="viewBillImg('${r.image_path}')" style="cursor:pointer;color:#60a5fa;margin-left:6px;" title="ดูรูปบิล">📎 ดูบิล</span>` : ''}
                </td>
                <td style="text-align:center;white-space:nowrap;">
                    ${r.type === 'purchase' && r.bill_id ? `<button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:6px;padding:3px 7px;cursor:pointer;" onclick="deletePurchaseBill(${r.bill_id})" title="ลบรายการบิลจัดซื้อ"><i data-lucide="trash-2" style="width:13px;height:13px;"></i></button>` : ''}
                    ${r.wo_id && r.is_pos ? `<button class="btn-sm" style="color:#60a5fa;background:rgba(96,165,250,0.12);border:1px solid rgba(96,165,250,0.28);border-radius:6px;padding:3px 7px;cursor:pointer;margin-right:4px;" onclick="printPOSReceipt(${r.wo_id})" title="พิมพ์ใบเสร็จ/บิลขาย"><i data-lucide="printer" style="width:13px;height:13px;"></i></button>` : ''}
                    ${r.wo_id && r.is_pos ? `<button class="btn-sm" style="color:#fbbf24;background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.28);border-radius:6px;padding:3px 7px;cursor:pointer;margin-right:4px;" onclick="openEditPOSModal(${r.wo_id})" title="แก้ไขบิลขาย"><i data-lucide="pencil" style="width:13px;height:13px;"></i></button>` : ''}
                    ${r.wo_id ? `<button class="btn-sm" style="color:#f87171;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:6px;padding:3px 7px;cursor:pointer;" onclick="deletePOSWorkOrder(${r.wo_id})" title="ยกเลิกบิล (คืนสินค้าเข้าสต็อก)"><i data-lucide="undo-2" style="width:13px;height:13px;"></i></button>` : ''}
                </td>
            </tr>
        `).join('');
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

function filterPOSHistory(btn, filter) {
    posHistoryFilter = filter;
    document.querySelectorAll('.pos-history-filter .pill').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    loadPOSHistory();
}

async function printPOSReceipt(woId) {
    try {
        const res = await fetch(`${API_URL}/stock/workorders/`, { headers: HEADERS });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        const list = await res.json();
        const wo = list.find(w => w.id === woId);
        if (!wo) { alert('ไม่พบข้อมูลรายการขาย'); return; }

        const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
        const shopPhone = localStorage.getItem('shop_phone') || '095-418-5332';
        const shopAddress = localStorage.getItem('shop_address') || '';
        const dateStr = wo.work_date ? new Date(wo.work_date).toLocaleDateString('th-TH', { year:'numeric', month:'long', day:'numeric', hour:'2-digit', minute:'2-digit' }) : new Date().toLocaleDateString('th-TH');
        const items = wo.line_items ? (typeof wo.line_items === 'string' ? JSON.parse(wo.line_items) : wo.line_items) : [];

        const printWin = window.open('', '_blank');
        if (!printWin) {
            alert('กรุณาอนุญาตป็อปอัปในเบราว์เซอร์เพื่อพิมพ์ใบเสร็จ');
            return;
        }
        printWin.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>ใบเสร็จรับเงิน / บิลขายอะไหล่ #${wo.id}</title>
                <style>
                    body { font-family: 'Sarabun', -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; color: #111; max-width: 480px; margin: 0 auto; }
                    .header { text-align: center; border-bottom: 2px dashed #999; padding-bottom: 12px; margin-bottom: 14px; }
                    .header h2 { margin: 0 0 4px; font-size: 1.3rem; }
                    .header p { margin: 2px 0; font-size: 0.85rem; color: #555; }
                    .meta { font-size: 0.85rem; margin-bottom: 12px; }
                    .meta div { margin-bottom: 3px; }
                    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 14px; }
                    th { border-bottom: 1px solid #333; padding: 6px 4px; text-align: left; }
                    td { padding: 6px 4px; border-bottom: 1px solid #eee; }
                    .total-box { border-top: 2px dashed #999; padding-top: 10px; text-align: right; font-size: 1.05rem; }
                    .footer { text-align: center; margin-top: 20px; font-size: 0.8rem; color: #777; border-top: 1px solid #eee; padding-top: 10px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>${shopName}</h2>
                    <p>${shopAddress}</p>
                    <p>โทร: ${shopPhone}</p>
                    ${(typeof fxShop !== 'undefined' && fxShop.vat_registered === '1' && fxShop.shop_tax_id) ? `<p>เลขประจำตัวผู้เสียภาษี: ${fxShop.shop_tax_id}</p>` : ''}
                    <h3 style="margin-top:8px;font-size:1rem;color:#059669;">${(typeof fxShop !== 'undefined' && fxShop.vat_registered === '1') ? 'ใบเสร็จรับเงิน / ใบกำกับภาษี (POS)' : 'ใบเสร็จรับเงิน / ขายอะไหล่หน้าร้าน (POS)'}</h3>
                </div>
                <div class="meta">
                    <div><strong>เลขที่บิล:</strong> POS-#${wo.id}</div>
                    <div><strong>วันที่:</strong> ${dateStr}</div>
                    <div><strong>ลูกค้า:</strong> ${wo.customer_name || 'ลูกค้าทั่วไป'}</div>
                    ${wo.customer_phone ? `<div><strong>เบอร์โทร:</strong> ${wo.customer_phone}</div>` : ''}
                    <div><strong>ประเภท:</strong> ซื้ออะไหล่หน้าร้าน (ไม่ได้เปิดงานซ่อม)</div>
                </div>
                <table>
                    <thead>
                        <tr><th>#</th><th>รายการ</th><th style="text-align:center;">จำนวน</th><th style="text-align:right;">ราคา</th><th style="text-align:right;">รวม</th></tr>
                    </thead>
                    <tbody>
                        ${items.map((it, idx) => `
                            <tr>
                                <td>${idx + 1}</td>
                                <td>${it.name}</td>
                                <td style="text-align:center;">${it.qty}</td>
                                <td style="text-align:right;">฿${(it.unit_price || 0).toLocaleString('th-TH')}</td>
                                <td style="text-align:right;">฿${(it.total || (it.qty * it.unit_price) || 0).toLocaleString('th-TH')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="total-box">
                    ${typeof fxVatBlock === 'function' ? fxVatBlock(wo.parts_cost || wo.total_cost || 0) : ''}
                    <strong>ยอดรวมสุทธิ: ฿${(wo.parts_cost || wo.total_cost || 0).toLocaleString('th-TH', { minimumFractionDigits: 2 })}</strong>
                </div>
                <div class="footer">
                    ขอบคุณที่ใช้บริการ / อะไหล่แท้คุณภาพ
                </div>
                <script>
                    window.onload = function() { window.print(); }
                </script>
            </body>
            </html>
        `);
        printWin.document.close();
    } catch (e) {
        alert('เกิดข้อผิดพลาดในการเปิดใบเสร็จ: ' + e.message);
    }
}

// ── POS SALE MODAL & OPERATIONS (คนซื้ออะไหล่อย่างเดียว ไม่ได้ทำงานซ่อม) ──
let _posRowCounter = 0;
let _cachedStockForPOS = [];

async function openAddPOSModal() {
    const modal = document.getElementById('pos-sale-modal');
    if (!modal) return;
    _editingPOSId = null;
    const title = document.getElementById('pos-modal-title');
    if (title) title.textContent = 'บันทึกคนซื้ออะไหล่หน้าร้าน (POS)';

    // Reset fields
    const custNameEl = document.getElementById('pos-cust-name');
    if (custNameEl) custNameEl.value = 'ลูกค้าทั่วไป (Walk-in)';

    const custPhoneEl = document.getElementById('pos-cust-phone');
    if (custPhoneEl) custPhoneEl.value = '';

    const dateEl = document.getElementById('pos-sale-date');
    if (dateEl) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        dateEl.value = `${yyyy}-${mm}-${dd}`;
    }

    const payEl = document.getElementById('pos-payment-method');
    if (payEl) payEl.value = 'เงินสด';

    const notesEl = document.getElementById('pos-notes');
    if (notesEl) notesEl.value = '';

    // Clear items container & add 1 blank row
    const container = document.getElementById('pos-items-container');
    if (container) {
        container.innerHTML = '';
        _posRowCounter = 0;
    }

    // Load stock items for autocomplete and pricing
    try {
        const sRes = await fetch(`${API_URL}/stock/`, { headers: HEADERS });
        if (sRes.ok) {
            _cachedStockForPOS = await sRes.json();
            const dl = document.getElementById('pos-stock-datalist');
            if (dl) {
                dl.innerHTML = _cachedStockForPOS.map(item => `<option value="${item.name_th}">${item.sku ? `[${item.sku}] ` : ''}คงเหลือ: ${item.quantity} | ราคาขาย: ฿${item.sell_price || 0}</option>`).join('');
            }
        }
    } catch (e) { console.warn('Could not load stock list for POS', e); }

    // Load customer names for autocomplete
    try {
        const cRes = await fetch(`${API_URL}/customers/`, { headers: HEADERS });
        if (cRes.ok) {
            const custs = await cRes.json();
            const cdl = document.getElementById('pos-cust-list');
            if (cdl) {
                cdl.innerHTML = custs.map(c => `<option value="${c.name}">${c.phone ? `(${c.phone})` : ''}</option>`).join('');
            }
        }
    } catch (e) { console.warn('Could not load customer list for POS', e); }

    addPOSItemRow();
    modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closePOSModal() {
    const modal = document.getElementById('pos-sale-modal');
    if (modal) modal.style.display = 'none';
}

function addPOSItemRow(name = '', qty = 1, unitPrice = 0) {
    const container = document.getElementById('pos-items-container');
    if (!container) return;
    const rowId = ++_posRowCounter;

    const row = document.createElement('div');
    row.id = `pos-row-${rowId}`;
    row.className = 'pos-item-row';
    row.style.cssText = 'display:flex;gap:8px;align-items:center;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);padding:8px 10px;border-radius:8px;';
    row.innerHTML = `
        <div style="flex:2;min-width:140px;">
            <input type="text" class="form-input pos-item-name" placeholder="เลือกหรือพิมพ์ชื่ออะไหล่" value="${name}" list="pos-stock-datalist" onchange="onPOSMatchStockItem(this, ${rowId})" oninput="recalcPOSTotals()" style="padding:6px 10px;font-size:0.86rem;">
            <div class="pos-item-stock-info" style="font-size:0.75rem;color:#94a3b8;margin-top:2px;"></div>
        </div>
        <div style="width:75px;">
            <input type="number" class="form-input pos-item-qty" placeholder="จำนวน" value="${qty}" min="1" step="1" oninput="recalcPOSTotals()" style="padding:6px 8px;font-size:0.86rem;text-align:center;">
        </div>
        <div style="width:115px;">
            <input type="number" class="form-input pos-item-price" placeholder="ราคาขาย/หน่วย" value="${unitPrice || ''}" min="0" step="any" oninput="recalcPOSTotals()" style="padding:6px 8px;font-size:0.86rem;text-align:right;">
        </div>
        <div style="width:105px;text-align:right;font-weight:600;color:#34d399;font-size:0.9rem;" class="pos-item-subtotal">
            ฿0.00
        </div>
        <button type="button" onclick="removePOSItemRow(${rowId})" style="flex-shrink:0;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#f87171;border-radius:6px;padding:6px 9px;cursor:pointer;" title="ลบรายการ">
            <i data-lucide="trash-2" style="width:14px;height:14px;"></i>
        </button>
    `;
    container.appendChild(row);
    if (window.lucide) lucide.createIcons();
    recalcPOSTotals();
}

function onPOSMatchStockItem(inputEl, rowId) {
    const val = inputEl.value.trim();
    if (!val || !_cachedStockForPOS.length) return;
    const match = _cachedStockForPOS.find(i => i.name_th === val || i.name_en === val || i.sku === val);
    const row = document.getElementById(`pos-row-${rowId}`);
    if (row && match) {
        row.dataset.stockId = match.id;
        const priceInput = row.querySelector('.pos-item-price');
        if (priceInput) {
            priceInput.value = match.sell_price || match.unit_cost || 0;
        }
        const infoEl = row.querySelector('.pos-item-stock-info');
        if (infoEl) {
            infoEl.innerHTML = `📦 ในคลังเหลือ: <strong style="color:${match.quantity > 0 ? '#4ade80' : '#f87171'}">${match.quantity}</strong> ชิ้น (SKU: ${match.sku || '-'})`;
        }
    }
    recalcPOSTotals();
}

function removePOSItemRow(rowId) {
    const container = document.getElementById('pos-items-container');
    if (!container) return;
    const rows = container.querySelectorAll('.pos-item-row');
    if (rows.length <= 1) {
        showToast('⚠️ ต้องมีอย่างน้อย 1 รายการ');
        return;
    }
    const row = document.getElementById(`pos-row-${rowId}`);
    if (row) row.remove();
    recalcPOSTotals();
}

function recalcPOSTotals() {
    let grandTotal = 0;
    const rows = document.querySelectorAll('.pos-item-row');
    rows.forEach(r => {
        const qtyEl = r.querySelector('.pos-item-qty');
        const priceEl = r.querySelector('.pos-item-price');
        const subtotalEl = r.querySelector('.pos-item-subtotal');

        const qty = parseFloat(qtyEl?.value) || 0;
        const price = parseFloat(priceEl?.value) || 0;
        const subtotal = Math.round(qty * price * 100) / 100;
        grandTotal += subtotal;

        if (subtotalEl) {
            subtotalEl.textContent = '฿' + subtotal.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    });

    const grandTotalEl = document.getElementById('pos-grand-total');
    if (grandTotalEl) {
        grandTotalEl.textContent = '฿' + grandTotal.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return grandTotal;
}

async function submitPOSSale() {
    const custName = document.getElementById('pos-cust-name')?.value.trim() || 'ลูกค้าทั่วไป (Walk-in)';
    const custPhone = document.getElementById('pos-cust-phone')?.value.trim();
    const saleDate = document.getElementById('pos-sale-date')?.value;
    const payMethod = document.getElementById('pos-payment-method')?.value || 'เงินสด';
    const notes = document.getElementById('pos-notes')?.value.trim() || '';

    const rows = document.querySelectorAll('.pos-item-row');
    const items = [];
    rows.forEach(r => {
        const name = r.querySelector('.pos-item-name')?.value.trim();
        const qty = parseFloat(r.querySelector('.pos-item-qty')?.value) || 1;
        const price = parseFloat(r.querySelector('.pos-item-price')?.value) || 0;
        const stockId = r.dataset.stockId ? parseInt(r.dataset.stockId) : null;
        if (name) {
            items.push({
                stock_item_id: stockId,
                name: name,
                qty: qty,
                unit_price: price,
                total: Math.round(qty * price * 100) / 100
            });
        }
    });

    if (!items.length) {
        alert('กรุณาระบุรายการอะไหล่อย่างน้อย 1 รายการ');
        return;
    }

    // Local Thai date + current time, no timezone suffix (the server stores local time)
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const timePart = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const datePart = saleDate || `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const payload = {
        customer_name: custName,
        customer_phone: custPhone || null,
        sale_date: `${datePart}T${timePart}`,
        payment_method: payMethod,
        items: items,
        notes: notes || null
    };

    const editingId = _editingPOSId;
    try {
        const res = await fetch(editingId ? `${API_URL}/stock/pos-sale/${editingId}` : `${API_URL}/stock/pos-sale`, {
            method: editingId ? 'PUT' : 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(_apiErrorText(err, 'บันทึกไม่สำเร็จ'));
        }
        const savedWO = await res.json();
        _editingPOSId = null;
        showToast(editingId
            ? `✅ แก้ไขบิลขาย #${editingId} เรียบร้อย (฿${(savedWO.parts_cost||0).toLocaleString('th-TH')})`
            : `✅ บันทึกขายอะไหล่ ฿${(savedWO.parts_cost||0).toLocaleString('th-TH')} เรียบร้อย!`);
        closePOSModal();
        if (typeof loadPOSHistory === 'function') loadPOSHistory();
        if (typeof loadStock === 'function') loadStock();
        if (typeof loadStockHistory === 'function') loadStockHistory();
        if (typeof loadStockGrid === 'function') loadStockGrid();
        if (typeof fetchStockData === 'function') fetchStockData();
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาดในการบันทึก: ' + e.message);
    }
}

async function deletePOSWorkOrder(id) {
    if (!confirm(`ยกเลิกบิล #${id} ใช่หรือไม่?\n\n• สินค้าในบิลจะถูกคืนเข้าสต็อก\n• รายรับของบิลนี้จะถูกลบออกจากบัญชี`)) return;
    try {
        const res = await fetch(`${API_URL}/stock/workorders/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast('✅ ยกเลิกบิลและคืนสต็อกเรียบร้อยแล้ว');
        if (typeof loadPOSHistory === 'function') loadPOSHistory();
        if (typeof loadStockHistory === 'function') loadStockHistory();
        if (typeof fetchStockData === 'function') fetchStockData();
    } catch {
        showToast('❌ ไม่สามารถยกเลิกบิลได้');
    }
}

let _editingPOSId = null;

async function openEditPOSModal(id) {
    let wo;
    try {
        const res = await fetch(`${API_URL}/stock/workorders/?limit=1000`, { headers: HEADERS });
        wo = (await res.json()).find(x => x.id === id);
    } catch {}
    if (!wo) return showToast('❌ ไม่พบบิลขาย');

    await openAddPOSModal();
    _editingPOSId = id;
    const set = (elId, v) => { const el = document.getElementById(elId); if (el) el.value = v ?? ''; };
    set('pos-cust-name', wo.customer_name);
    set('pos-cust-phone', wo.customer_phone);
    set('pos-sale-date', (wo.work_date || '').slice(0, 10));
    const pay = (wo.description || '').match(/\[(.+)\]/);
    if (pay) set('pos-payment-method', pay[1]);
    set('pos-notes', wo.notes);

    const container = document.getElementById('pos-items-container');
    container.innerHTML = '';
    const items = typeof wo.line_items === 'string' ? JSON.parse(wo.line_items || '[]') : (wo.line_items || []);
    items.forEach(it => {
        addPOSItemRow(it.name, it.qty, it.unit_price);
        const row = container.lastElementChild;
        if (row && it.stock_item_id) row.dataset.stockId = it.stock_item_id;
    });
    if (!items.length) addPOSItemRow();
    recalcPOSTotals();
    const title = document.getElementById('pos-modal-title');
    if (title) title.textContent = `แก้ไขบิลขาย #${id}`;
}

// ── MANUAL PURCHASE BILL MODAL & OPERATIONS ──
let _pbRowCounter = 0;
let _cachedStockForPB = [];

async function openAddPurchaseModal(prefillSupplier = '') {
    const modal = document.getElementById('purchase-modal');
    if (!modal) return;

    // Reset fields
    const supplierEl = document.getElementById('pb-supplier');
    if (supplierEl) supplierEl.value = prefillSupplier || '';

    const numberEl = document.getElementById('pb-number');
    if (numberEl) numberEl.value = '';

    const dateEl = document.getElementById('pb-date');
    if (dateEl) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        dateEl.value = `${yyyy}-${mm}-${dd}`;
    }

    const fileEl = document.getElementById('pb-file');
    if (fileEl) fileEl.value = '';

    const notesEl = document.getElementById('pb-notes');
    if (notesEl) notesEl.value = '';

    const stockCheckEl = document.getElementById('pb-update-stock');
    if (stockCheckEl) stockCheckEl.checked = true;

    // Reset items container
    const container = document.getElementById('pb-items-container');
    if (container) {
        container.innerHTML = '';
        _pbRowCounter = 0;
        addPurchaseItemRow();
    }

    // Populate Suppliers Datalist
    try {
        const res = await fetch(`${API_URL}/suppliers/`, { headers: HEADERS });
        if (res.ok) {
            const suppliers = await res.json();
            const dl = document.getElementById('pb-supplier-list');
            if (dl) {
                dl.innerHTML = suppliers.map(s => `<option value="${s.name}">${s.phone ? `(${s.phone})` : ''}</option>`).join('');
            }
        }
    } catch (e) { console.warn('Could not populate suppliers list', e); }

    // Populate Stock Items Datalist for autocomplete
    try {
        const sRes = await fetch(`${API_URL}/stock/`, { headers: HEADERS });
        if (sRes.ok) {
            _cachedStockForPB = await sRes.json();
            const sdl = document.getElementById('pb-stock-item-list');
            if (sdl) {
                sdl.innerHTML = _cachedStockForPB.map(item => `<option value="${item.name_th}">${item.sku ? `[${item.sku}] ` : ''}ทุน: ฿${item.unit_cost || 0}</option>`).join('');
            }
        }
    } catch (e) { console.warn('Could not populate stock items list', e); }

    recalcPurchaseTotals();
    modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closePurchaseModal() {
    const modal = document.getElementById('purchase-modal');
    if (modal) modal.style.display = 'none';
}

function addPurchaseItemRow(name = '', qty = 1, unitPrice = 0) {
    const container = document.getElementById('pb-items-container');
    if (!container) return;
    const rowId = ++_pbRowCounter;

    const row = document.createElement('div');
    row.id = `pb-row-${rowId}`;
    row.className = 'pb-item-row';
    row.style.cssText = 'display:flex;gap:8px;align-items:center;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);padding:8px 10px;border-radius:8px;';
    row.innerHTML = `
        <div style="flex:2;min-width:140px;">
            <input type="text" class="form-input pb-item-name" placeholder="ชื่ออะไหล่ / รายการ" value="${name}" list="pb-stock-item-list" onchange="onPBMatchStockItem(this, ${rowId})" oninput="recalcPurchaseTotals()" style="padding:6px 10px;font-size:0.86rem;">
        </div>
        <div style="width:75px;">
            <input type="number" class="form-input pb-item-qty" placeholder="จำนวน" value="${qty}" min="1" step="1" oninput="recalcPurchaseTotals()" style="padding:6px 8px;font-size:0.86rem;text-align:center;">
        </div>
        <div style="width:110px;">
            <input type="number" class="form-input pb-item-price" placeholder="ราคา/หน่วย" value="${unitPrice || ''}" min="0" step="any" oninput="recalcPurchaseTotals()" style="padding:6px 8px;font-size:0.86rem;text-align:right;">
        </div>
        <div style="width:110px;text-align:right;font-weight:600;color:#34d399;font-size:0.9rem;" class="pb-item-subtotal">
            ฿0.00
        </div>
        <button type="button" onclick="removePurchaseItemRow(${rowId})" style="flex-shrink:0;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#f87171;border-radius:6px;padding:6px 9px;cursor:pointer;" title="ลบรายการ">
            <i data-lucide="trash-2" style="width:14px;height:14px;"></i>
        </button>
    `;
    container.appendChild(row);
    if (window.lucide) lucide.createIcons();
    recalcPurchaseTotals();
}

function onPBMatchStockItem(inputEl, rowId) {
    const val = inputEl.value.trim();
    if (!val || !_cachedStockForPB.length) return;
    const match = _cachedStockForPB.find(i => i.name_th === val || i.sku === val);
    if (match) {
        const row = document.getElementById(`pb-row-${rowId}`);
        if (row) {
            const priceInput = row.querySelector('.pb-item-price');
            if (priceInput && (!priceInput.value || parseFloat(priceInput.value) === 0)) {
                priceInput.value = match.unit_cost || match.sell_price || 0;
            }
        }
    }
    recalcPurchaseTotals();
}

function removePurchaseItemRow(rowId) {
    const container = document.getElementById('pb-items-container');
    if (!container) return;
    const rows = container.querySelectorAll('.pb-item-row');
    if (rows.length <= 1) {
        showToast('⚠️ ต้องมีอย่างน้อย 1 รายการ');
        return;
    }
    const row = document.getElementById(`pb-row-${rowId}`);
    if (row) row.remove();
    recalcPurchaseTotals();
}

function recalcPurchaseTotals() {
    let grandTotal = 0;
    const rows = document.querySelectorAll('.pb-item-row');
    rows.forEach(r => {
        const qtyEl = r.querySelector('.pb-item-qty');
        const priceEl = r.querySelector('.pb-item-price');
        const subtotalEl = r.querySelector('.pb-item-subtotal');

        const qty = parseFloat(qtyEl?.value) || 0;
        const price = parseFloat(priceEl?.value) || 0;
        const subtotal = Math.round(qty * price * 100) / 100;
        grandTotal += subtotal;

        if (subtotalEl) {
            subtotalEl.textContent = '฿' + subtotal.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    });

    const grandTotalEl = document.getElementById('pb-grand-total');
    if (grandTotalEl) {
        grandTotalEl.textContent = '฿' + grandTotal.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return grandTotal;
}

async function submitPurchase() {
    const supplier = document.getElementById('pb-supplier')?.value.trim() || 'ไม่ระบุ';
    const billNumber = document.getElementById('pb-number')?.value.trim();
    const billDate = document.getElementById('pb-date')?.value;
    const notes = document.getElementById('pb-notes')?.value.trim() || '';
    const updateStock = document.getElementById('pb-update-stock')?.checked ?? true;

    if (!billDate) {
        alert('กรุณาเลือกวันที่ตามบิล');
        return;
    }

    const rows = document.querySelectorAll('.pb-item-row');
    const items = [];
    rows.forEach(r => {
        const name = r.querySelector('.pb-item-name')?.value.trim();
        const qty = parseFloat(r.querySelector('.pb-item-qty')?.value) || 1;
        const price = parseFloat(r.querySelector('.pb-item-price')?.value) || 0;
        if (name) {
            items.push({
                name: name,
                qty: qty,
                unit_price: price,
                total: Math.round(qty * price * 100) / 100
            });
        }
    });

    if (!items.length) {
        alert('กรุณากรอกชื่ออะไหล่อย่างน้อย 1 รายการ');
        return;
    }

    const grandTotal = recalcPurchaseTotals();

    // Handle optional image upload
    let imagePath = null;
    const fileInput = document.getElementById('pb-file');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            const upRes = await fetch(`${API_URL}/suppliers/purchases/upload-image`, {
                method: 'POST',
                body: formData
            });
            if (upRes.ok) {
                const upData = await upRes.json();
                imagePath = upData.image_path;
            }
        } catch (e) {
            console.warn('Image upload error:', e);
        }
    }

    const payload = {
        supplier_name: supplier,
        bill_number: billNumber || null,
        bill_date: billDate ? new Date(billDate).toISOString() : new Date().toISOString(),
        items: JSON.stringify(items),
        total_amount: grandTotal,
        image_path: imagePath,
        notes: notes || null,
        update_stock: updateStock
    };

    try {
        const res = await fetch(`${API_URL}/suppliers/purchases/`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(_apiErrorText(err, 'บันทึกไม่สำเร็จ'));
        }
        showToast(`✅ บันทึกประวัติการซื้อ ฿${grandTotal.toLocaleString('th-TH')} เรียบร้อย!`);
        closePurchaseModal();
        if (typeof loadPOSHistory === 'function') loadPOSHistory();
        if (typeof loadPurchases === 'function') loadPurchases();
        if (typeof loadSuppliers === 'function') loadSuppliers();
        if (typeof loadStockHistory === 'function') loadStockHistory();
        if (typeof loadStockGrid === 'function') loadStockGrid();
    } catch (e) {
        alert('❌ เกิดข้อผิดพลาดในการบันทึก: ' + e.message);
    }
}

async function deletePurchaseBill(id) {
    if (!confirm('คุณแน่ใจหรือไม่ว่าต้องการลบรายการบิลจัดซื้อนี้?')) return;
    try {
        const res = await fetch(`${API_URL}/suppliers/purchases/${id}`, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast('✅ ลบรายการจัดซื้อเรียบร้อยแล้ว');
        if (typeof loadPurchases === 'function') loadPurchases();
        if (typeof loadPOSHistory === 'function') loadPOSHistory();
        if (typeof loadSuppliers === 'function') loadSuppliers();
    } catch {
        showToast('❌ ไม่สามารถลบรายการได้');
    }
}

// ── EDIT PURCHASE BILL ──
function openEditPurchaseModal(id) {
    const bill = (allPurchases || []).find(b => b.id === id);
    if (!bill) return;

    const idEl = document.getElementById('edit-pb-id');
    if (idEl) idEl.value = bill.id;

    const numEl = document.getElementById('edit-pb-number');
    if (numEl) numEl.value = bill.bill_number || '';

    const dateEl = document.getElementById('edit-pb-date');
    if (dateEl) {
        if (bill.bill_date) {
            try {
                dateEl.value = new Date(bill.bill_date).toISOString().split('T')[0];
            } catch {
                dateEl.value = '';
            }
        } else {
            dateEl.value = '';
        }
    }

    const supEl = document.getElementById('edit-pb-supplier');
    if (supEl) supEl.value = bill.supplier_name && bill.supplier_name !== 'ไม่ระบุ' ? bill.supplier_name : '';

    const amtEl = document.getElementById('edit-pb-amount');
    if (amtEl) amtEl.value = bill.total_amount || 0;

    const itemsEl = document.getElementById('edit-pb-items-summary');
    if (itemsEl) {
        let itemsStr = '';
        if (Array.isArray(bill.items)) {
            itemsStr = bill.items.map(i => `${i.name || ''} (${i.qty || 1})`).join(', ');
        } else if (bill.items) {
            itemsStr = String(bill.items);
        }
        itemsEl.value = itemsStr;
    }

    const notesEl = document.getElementById('edit-pb-notes');
    if (notesEl) notesEl.value = bill.notes || '';

    const imgPathEl = document.getElementById('edit-pb-image-path');
    if (imgPathEl) imgPathEl.value = bill.image_path || '';

    const viewBtn = document.getElementById('edit-pb-view-bill-btn');
    if (viewBtn) {
        if (bill.image_path) {
            viewBtn.style.display = 'inline-flex';
        } else {
            viewBtn.style.display = 'none';
        }
    }

    const fileInput = document.getElementById('edit-pb-file');
    if (fileInput) fileInput.value = '';

    const modal = document.getElementById('edit-purchase-modal');
    if (modal) modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeEditPurchaseModal() {
    const modal = document.getElementById('edit-purchase-modal');
    if (modal) modal.style.display = 'none';
}

function viewEditPurchaseCurrentBill() {
    const imgPath = document.getElementById('edit-pb-image-path')?.value;
    if (imgPath) viewBillImg(imgPath);
}

async function saveEditPurchase() {
    const id = document.getElementById('edit-pb-id')?.value;
    if (!id) return;

    const billNumber = document.getElementById('edit-pb-number')?.value.trim();
    const billDate = document.getElementById('edit-pb-date')?.value;
    const supplierName = document.getElementById('edit-pb-supplier')?.value.trim();
    const amountVal = parseFloat(document.getElementById('edit-pb-amount')?.value) || 0;
    const itemsSummary = document.getElementById('edit-pb-items-summary')?.value.trim();
    const notes = document.getElementById('edit-pb-notes')?.value.trim();
    let imagePath = document.getElementById('edit-pb-image-path')?.value || null;

    const fileInput = document.getElementById('edit-pb-file');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            const uploadRes = await fetch(`${API_URL}/suppliers/purchases/upload-image`, {
                method: 'POST',
                headers: { 'Authorization': HEADERS['Authorization'] },
                body: formData
            });
            if (uploadRes.ok) {
                const uploadData = await uploadRes.json();
                imagePath = uploadData.image_path;
            }
        } catch (e) {
            console.error('Failed to upload bill image', e);
        }
    }

    let parsedItems = undefined;
    if (itemsSummary) {
        const parts = itemsSummary.split(',');
        parsedItems = parts.map(p => {
            const m = p.trim().match(/^(.*?)\s*\((\d+)\)$/);
            if (m) {
                return { name: m[1].trim(), qty: parseInt(m[2], 10), unit_price: 0, total: 0 };
            }
            return { name: p.trim(), qty: 1, unit_price: 0, total: 0 };
        }).filter(i => i.name);
    }

    const payload = {
        bill_number: billNumber || null,
        bill_date: billDate ? new Date(billDate).toISOString() : null,
        supplier_name: supplierName || null,
        total_amount: amountVal,
        notes: notes || null,
        image_path: imagePath
    };
    if (parsedItems) {
        payload.items = parsedItems;
    }

    try {
        const res = await fetch(`${API_URL}/suppliers/purchases/${id}`, {
            method: 'PUT',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Update failed');
        showToast('✅ แก้ไขข้อมูลบิลจัดซื้อเรียบร้อย!');
        closeEditPurchaseModal();
        if (typeof loadPurchases === 'function') loadPurchases();
        if (typeof loadSuppliers === 'function') loadSuppliers();
        if (typeof loadPOSHistory === 'function') loadPOSHistory();
    } catch (e) {
        showToast('❌ ไม่สามารถแก้ไขบิลจัดซื้อได้: ' + e.message);
    }
}

// ── REPORTS ──
async function loadReports() {
    if (window.reportsApp) {
        window.reportsApp.showReportHub();
        return;
    }
    const grid = document.getElementById('reports-grid');
    if (!grid) return;
    try {
        const now = new Date();
        const [y, m] = [now.getFullYear(), now.getMonth() + 1];
        const res = await fetch(`${API_URL}/finance/summary/${y}/${m}`, { headers: HEADERS });
        let summary = null;
        if (res.ok) { const d = await res.json(); summary = d.summary; }

        const income = summary?.total_income ?? 0;
        const expense = summary?.total_expense ?? 0;
        const profit = summary?.net_profit ?? (income - expense);
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
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
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
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ยังไม่มีรายการค่าใช้จ่าย</td></tr>`;
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
                <td style="white-space:nowrap;">
                    <button class="btn-sm" style="background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);color:#60a5fa;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:0.78rem;display:inline-flex;align-items:center;gap:4px;margin-right:4px;" onclick="openEditExpenseModal(${e.id})" title="แก้ไขค่าใช้จ่าย">
                        <i data-lucide="pencil" style="width:12px;height:12px;"></i> แก้ไข
                    </button>
                    <button class="btn-sm" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.35);color:#f87171;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:0.78rem;display:inline-flex;align-items:center;gap:4px;" onclick="deleteExpense(${e.id})" title="ลบค่าใช้จ่าย">
                        <i data-lucide="trash-2" style="width:12px;height:12px;"></i> ลบ
                    </button>
                </td>
            </tr>
        `).join('');
        if (window.lucide) lucide.createIcons();
    } catch {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">ไม่สามารถโหลดข้อมูลได้</td></tr>`;
    }
}

// ── EDIT EXPENSE ──
function openEditExpenseModal(id) {
    const e = allExpenses.find(x => x.id === id);
    if (!e) return;
    document.getElementById('edit-expense-id').value = e.id;
    document.getElementById('edit-expense-cat').value = e.category || '';
    document.getElementById('edit-expense-amount').value = e.amount || '';
    document.getElementById('edit-expense-desc').value = e.description || '';
    document.getElementById('edit-expense-by').value = e.added_by || '';
    if (e.expense_date) {
        const d = new Date(e.expense_date);
        document.getElementById('edit-expense-date').value = d.toISOString().split('T')[0];
    } else {
        document.getElementById('edit-expense-date').value = '';
    }
    document.getElementById('edit-expense-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}
function closeEditExpenseModal() {
    document.getElementById('edit-expense-modal').style.display = 'none';
}
async function saveEditExpense() {
    const id = document.getElementById('edit-expense-id').value;
    const amount = parseFloat(document.getElementById('edit-expense-amount').value);
    if (!id || !amount || amount <= 0) return showToast('กรุณากรอกจำนวนเงิน');
    const payload = {
        category: document.getElementById('edit-expense-cat').value || 'อื่นๆ',
        description: document.getElementById('edit-expense-desc').value || '',
        amount,
        expense_date: new Date(document.getElementById('edit-expense-date').value || new Date()).toISOString(),
        added_by: document.getElementById('edit-expense-by').value || 'ผู้จัดการ'
    };
    try {
        const res = await fetch(`${API_URL}/expenses/${id}`, { method:'PUT', headers:HEADERS, body:JSON.stringify(payload) });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast('✅ แก้ไขค่าใช้จ่ายเรียบร้อย!');
        closeEditExpenseModal();
        loadExpenses();
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาด')); }
}

async function deleteExpense(id) {
    if (!confirm('ยืนยันลบรายการค่าใช้จ่ายนี้?')) return;
    try {
        const res = await fetch(`${API_URL}/expenses/${id}`, { method: 'DELETE', headers: HEADERS });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast('✅ ลบรายการค่าใช้จ่ายเรียบร้อย');
        loadExpenses();
    } catch {
        showToast('❌ เกิดข้อผิดพลาดในการลบค่าใช้จ่าย');
    }
}

// ── EDIT STOCK ITEM (from main dashboard stock table) ──
function openEditStockModal(id) {
    const s = (allStock || []).find(x => x.id === id);
    if (!s) return;
    document.getElementById('edit-stock-id').value = s.id;
    document.getElementById('edit-stock-name-th').value = s.name_th || s.name || '';
    document.getElementById('edit-stock-name-en').value = s.name_en || '';
    document.getElementById('edit-stock-sku').value = s.sku || s.code || '';
    document.getElementById('edit-stock-category').value = s.category || '';
    document.getElementById('edit-stock-quantity').value = s.quantity ?? 0;
    document.getElementById('edit-stock-reorder').value = s.reorder_level ?? 5;
    document.getElementById('edit-stock-cost').value = s.unit_cost ?? s.cost ?? 0;
    document.getElementById('edit-stock-price').value = s.sell_price ?? s.price ?? 0;

    const billPathEl = document.getElementById('edit-stock-bill-path');
    const viewBillBtn = document.getElementById('edit-stock-view-bill-btn');
    const billFileInput = document.getElementById('edit-stock-bill-file');
    if (billFileInput) billFileInput.value = '';
    if (billPathEl) billPathEl.value = s.bill_path || '';
    if (viewBillBtn) {
        viewBillBtn.style.display = s.bill_path ? 'inline-flex' : 'none';
    }

    document.getElementById('edit-stock-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}
function closeEditStockModal() {
    document.getElementById('edit-stock-modal').style.display = 'none';
}
function viewStockCurrentBill() {
    const path = document.getElementById('edit-stock-bill-path')?.value;
    if (path) viewBillImg(path);
}
async function saveEditStock() {
    const id = document.getElementById('edit-stock-id').value;
    if (!id) return;
    const payload = {
        name_th: document.getElementById('edit-stock-name-th').value,
        name_en: document.getElementById('edit-stock-name-en').value || null,
        sku: document.getElementById('edit-stock-sku').value || null,
        category: document.getElementById('edit-stock-category').value,
        quantity: parseInt(document.getElementById('edit-stock-quantity').value) || 0,
        reorder_level: parseInt(document.getElementById('edit-stock-reorder').value) || 5,
        unit_cost: parseFloat(document.getElementById('edit-stock-cost').value) || 0,
        sell_price: parseFloat(document.getElementById('edit-stock-price').value) || 0,
    };
    if (!payload.name_th || !payload.category) return showToast('กรุณากรอกชื่อสินค้าและหมวดหมู่');
    try {
        const res = await fetch(`${API_URL}/stock/${id}`, { method:'PUT', headers:HEADERS, body:JSON.stringify(payload) });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));

        // If user uploaded a new bill file, upload it immediately
        const billFileInput = document.getElementById('edit-stock-bill-file');
        if (billFileInput && billFileInput.files && billFileInput.files.length > 0) {
            const formData = new FormData();
            formData.append('file', billFileInput.files[0]);
            await fetch(`${API_URL}/stock/upload-bill/${id}`, {
                method: 'POST',
                headers: {},
                body: formData
            });
        }

        showToast('✅ แก้ไขข้อมูลสินค้าเรียบร้อย!');
        closeEditStockModal();
        fetchStockData();
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาดในการบันทึก')); }
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
let _editingApptId = null;

function _fillApptForm(a) {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
    set('appt-customer', a.customer_name);
    set('appt-phone', a.customer_phone);
    set('appt-plate', a.vehicle_plate);
    set('appt-vehicle', a.vehicle_info);
    set('appt-date', a.appointment_date ? String(a.appointment_date).slice(0, 10) : '');
    set('appt-time', a.time_slot || (a.appointment_date ? String(a.appointment_date).slice(11, 16) : '09:00') || '09:00');
    set('appt-service', a.service_type);
    set('appt-status', a.status || 'confirmed');
}

function openAddAppointmentModal() {
    _editingApptId = null;
    _fillApptForm({ status: 'confirmed', time_slot: '09:00' });
    const title = document.getElementById('appt-modal-title');
    if (title) title.textContent = 'เพิ่มนัดหมายใหม่';
    document.getElementById('appt-modal').style.display = 'flex';
}
function openEditAppointmentModal(id) {
    const a = (allAppointments || []).find(x => x.id === id);
    if (!a) return showToast('❌ ไม่พบนัดหมาย');
    _editingApptId = id;
    _fillApptForm(a);
    const title = document.getElementById('appt-modal-title');
    if (title) title.textContent = `แก้ไขนัดหมาย — ${a.customer_name}`;
    document.getElementById('appt-modal').style.display = 'flex';
}
function closeApptModal() {
    document.getElementById('appt-modal').style.display = 'none';
    _editingApptId = null;
}
async function submitAppointment(allowOverlap = false) {
    const customer = document.getElementById('appt-customer')?.value.trim();
    const date = document.getElementById('appt-date')?.value;
    if (!customer || !date) return alert('กรุณากรอกชื่อลูกค้าและวันที่');
    const time = document.getElementById('appt-time')?.value || '09:00';
    const payload = {
        customer_name: customer,
        customer_phone: document.getElementById('appt-phone')?.value || null,
        vehicle_plate: document.getElementById('appt-plate')?.value || null,
        vehicle_info: document.getElementById('appt-vehicle')?.value || null,
        // Local Thai time, no timezone suffix — the server stores local time
        appointment_date: `${date}T${time}:00`,
        time_slot: time,
        service_type: document.getElementById('appt-service')?.value || null,
        status: document.getElementById('appt-status')?.value || 'confirmed',
        allow_overlap: allowOverlap,
    };
    const isEdit = _editingApptId !== null;
    try {
        const res = await fetch(isEdit ? `${API_URL}/appointments/${_editingApptId}` : `${API_URL}/appointments/`, {
            method: isEdit ? 'PUT' : 'POST', headers: HEADERS, body: JSON.stringify(payload)
        });
        if (res.status === 409) {
            const err = await res.json().catch(() => ({}));
            if (confirm(`⚠️ ${_apiErrorText(err, 'ช่วงเวลานี้มีนัดแล้ว')}\n\nต้องการบันทึกซ้อนเวลาเดิมหรือไม่?`)) return submitAppointment(true);
            return;
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(_apiErrorText(err));
        }
        showToast(isEdit ? '✅ แก้ไขนัดหมายเรียบร้อย!' : '✅ บันทึกนัดหมายเรียบร้อย!');
        closeApptModal();
        await fetchAppointments();
        renderCalendar();
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาด')); }
}

// Turn a FastAPI error body ({detail: "..."} or a 422 list) into one readable line
function _apiErrorText(err, fallback = 'เกิดข้อผิดพลาด') {
    if (!err || !err.detail) return fallback;
    if (typeof err.detail === 'string') return err.detail;
    if (Array.isArray(err.detail)) {
        return err.detail.map(d => {
            const field = (d.loc || []).slice(-1)[0];
            const msg = (d.msg || '').replace(/^Value error, /, '');
            return field ? `${field}: ${msg}` : msg;
        }).join(' • ');
    }
    return fallback;
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
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast(`✅ บันทึกค่าใช้จ่าย ฿${amount.toLocaleString('th-TH')} เรียบร้อย!`);
        closeExpenseModal();
        loadExpenses();
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาด')); }
}

let currentDetailSupplier = null;
let currentEditingSupplierId = null;

function openAddSupplierModal() {
    currentEditingSupplierId = null;
    const title = document.getElementById('supplier-modal-title');
    if (title) title.innerHTML = '<i data-lucide="building-2"></i> เพิ่มผู้จำหน่ายใหม่';
    const idEl = document.getElementById('sup-id');
    if (idEl) idEl.value = '';
    ['sup-name', 'sup-phone', 'sup-line', 'sup-email', 'sup-address', 'sup-notes'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const modal = document.getElementById('supplier-modal');
    if (modal) modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function openEditSupplierModal(s) {
    if (!s) return;
    if (typeof s === 'number' || typeof s === 'string') {
        const found = (allSuppliers || []).find(item => item.id == s);
        if (found) s = found;
        else return;
    }
    currentEditingSupplierId = s.id;
    const title = document.getElementById('supplier-modal-title');
    if (title) title.innerHTML = `<i data-lucide="edit-3"></i> แก้ไขข้อมูล: ${s.name}`;
    const idEl = document.getElementById('sup-id');
    if (idEl) idEl.value = s.id;
    const nameEl = document.getElementById('sup-name');
    if (nameEl) nameEl.value = s.name || '';
    const phoneEl = document.getElementById('sup-phone');
    if (phoneEl) phoneEl.value = s.phone || '';
    const lineEl = document.getElementById('sup-line');
    if (lineEl) lineEl.value = s.line_id || '';
    const emailEl = document.getElementById('sup-email');
    if (emailEl) emailEl.value = s.email || '';
    const addrEl = document.getElementById('sup-address');
    if (addrEl) addrEl.value = s.address || '';
    const notesEl = document.getElementById('sup-notes');
    if (notesEl) notesEl.value = s.notes || '';
    const modal = document.getElementById('supplier-modal');
    if (modal) modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeSupplierModal() {
    const modal = document.getElementById('supplier-modal');
    if (modal) modal.style.display = 'none';
    currentEditingSupplierId = null;
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
        notes: document.getElementById('sup-notes')?.value || null,
    };
    try {
        const url = currentEditingSupplierId ? `${API_URL}/suppliers/${currentEditingSupplierId}` : `${API_URL}/suppliers/`;
        const method = currentEditingSupplierId ? 'PUT' : 'POST';
        const res = await fetch(url, { method, headers: HEADERS, body: JSON.stringify(payload) });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        showToast(currentEditingSupplierId ? '✅ อัปเดตข้อมูลผู้จำหน่ายสำเร็จ!' : '✅ เพิ่มผู้จำหน่ายเรียบร้อย!');
        closeSupplierModal();
        await loadSuppliers();
        if (currentDetailSupplier && currentDetailSupplier.id === currentEditingSupplierId) {
            openSupplierDetailModal(currentEditingSupplierId);
        }
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาดในการบันทึกข้อมูล')); }
}

async function openSupplierDetailModal(supplierId) {
    try {
        const res = await fetch(`${API_URL}/suppliers/${supplierId}`, { headers: HEADERS });
        if (!res.ok) throw new Error('Supplier not found');
        const s = await res.json();
        currentDetailSupplier = s;

        const titleEl = document.getElementById('sd-modal-title');
        if (titleEl) titleEl.innerHTML = `<i data-lucide="building-2"></i> ${s.name}`;

        const phoneEl = document.getElementById('sd-phone');
        if (phoneEl) phoneEl.innerHTML = s.phone ? `<a href="tel:${s.phone}" style="color:#60a5fa;text-decoration:none;">📞 ${s.phone}</a>` : '<span style="color:var(--text-muted);">—</span>';

        const lineEl = document.getElementById('sd-line');
        if (lineEl) lineEl.innerHTML = s.line_id ? `<span style="color:#34d399;">LINE: ${s.line_id}</span>` : '<span style="color:var(--text-muted);">—</span>';

        const emailEl = document.getElementById('sd-email');
        if (emailEl) emailEl.innerHTML = s.email ? `<a href="mailto:${s.email}" style="color:#93c5fd;text-decoration:none;">✉️ ${s.email}</a>` : '<span style="color:var(--text-muted);">—</span>';

        const addrEl = document.getElementById('sd-address');
        if (addrEl) addrEl.textContent = s.address || '—';

        const notesEl = document.getElementById('sd-notes');
        if (notesEl) notesEl.textContent = s.notes || '—';

        const bills = s.purchase_bills || [];
        const totalAmount = bills.reduce((sum, b) => sum + (b.total_amount || 0), 0);
        const countEl = document.getElementById('sd-total-count');
        if (countEl) countEl.textContent = bills.length;
        const totalEl = document.getElementById('sd-total-amount');
        if (totalEl) totalEl.textContent = `฿${totalAmount.toLocaleString('th-TH')}`;

        const tbody = document.getElementById('sd-purchases-tbody');
        if (tbody) {
            if (!bills.length) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:16px;">ยังไม่มีประวัติการสั่งซื้อจากเจ้านี้</td></tr>`;
            } else {
                tbody.innerHTML = bills.map(b => {
                    const dateStr = b.bill_date ? new Date(b.bill_date).toLocaleDateString('th-TH') : '—';
                    const itemsStr = (b.items || []).map(i => `${i.name} (${i.qty} ชิ้น)`).join(', ') || '—';
                    return `<tr>
                        <td><strong style="color:#93c5fd;">${b.bill_number || '#' + b.id}</strong></td>
                        <td style="color:var(--text-muted);">${dateStr}</td>
                        <td style="font-size:0.8rem;color:var(--text-secondary);max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${itemsStr}">${itemsStr}</td>
                        <td style="color:#34d399;font-weight:700;">฿${(b.total_amount || 0).toLocaleString('th-TH')}</td>
                    </tr>`;
                }).join('');
            }
        }

        const modal = document.getElementById('supplier-detail-modal');
        if (modal) modal.style.display = 'flex';
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        showToast('ไม่สามารถโหลดข้อมูลผู้จำหน่ายได้', 'danger');
    }
}

function openAddPurchaseModalForSupplierId(id) {
    const s = (allSuppliers || []).find(x => x.id === id);
    openAddPurchaseModal(s ? s.name : '');
}

function closeSupplierDetailModal() {
    const modal = document.getElementById('supplier-detail-modal');
    if (modal) modal.style.display = 'none';
}

function openAddPurchaseForCurrentSupplier() {
    if (!currentDetailSupplier) return;
    const name = currentDetailSupplier.name;
    closeSupplierDetailModal();
    openAddPurchaseModal(name);
}

function deleteCurrentDetailSupplier() {
    if (!currentDetailSupplier) return;
    const id = currentDetailSupplier.id;
    const name = currentDetailSupplier.name;
    closeSupplierDetailModal();
    deleteSupplier(id, name);
}

function editCurrentDetailSupplier() {
    if (!currentDetailSupplier) return;
    const s = currentDetailSupplier;
    closeSupplierDetailModal();
    openEditSupplierModal(s);
}

function openAddStockModal() {
    // Clear form fields
    ['stock-name-th','stock-name-en','stock-sku','stock-cost','stock-price','stock-qty','stock-reorder'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const modal = document.getElementById('stock-modal');
    if (modal) {
        modal.style.display = 'flex';
        if (window.lucide) lucide.createIcons();
    }
}

function closeStockModal() {
    const modal = document.getElementById('stock-modal');
    if (modal) modal.style.display = 'none';
}

// ── REAL-TIME STOCK ROOM BARCODE SCANNER (Stock Tab) ─────────────────────────
let _stockBarcodeTimer = null;
let _stockScanMode = 'add'; // 'add' (+1) | 'deduct' (-1) | 'lookup' (0)
let _scannerSoundEnabled = true;
let _scanSessionCount = 0;
let _scanSessionHistory = []; // [{ id, sku, name_th, delta, before, after, time }]
let _audioCtx = null;

function playScannerBeep(type = 'success') {
    if (!_scannerSoundEnabled) return;
    try {
        if (!_audioCtx) {
            _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (_audioCtx.state === 'suspended') {
            _audioCtx.resume();
        }
        const now = _audioCtx.currentTime;
        const osc = _audioCtx.createOscillator();
        const gain = _audioCtx.createGain();
        osc.connect(gain);
        gain.connect(_audioCtx.destination);

        if (type === 'success') {
            // Crisp high-pitch warehouse scanner chirp (1050Hz -> 1400Hz)
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1050, now);
            osc.frequency.exponentialRampToValueAtTime(1400, now + 0.08);
            gain.gain.setValueAtTime(0.35, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);
            osc.start(now);
            osc.stop(now + 0.12);
            if (navigator.vibrate) navigator.vibrate(70);
        } else if (type === 'error') {
            // Low alert buzz for not found / error
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(220, now);
            osc.frequency.setValueAtTime(180, now + 0.1);
            gain.gain.setValueAtTime(0.3, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.26);
            osc.start(now);
            osc.stop(now + 0.26);
            if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
        } else if (type === 'undo') {
            // Descending tone for undo
            osc.type = 'sine';
            osc.frequency.setValueAtTime(750, now);
            osc.frequency.exponentialRampToValueAtTime(440, now + 0.12);
            gain.gain.setValueAtTime(0.3, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.14);
            osc.start(now);
            osc.stop(now + 0.14);
        }
    } catch (e) {
        console.warn('Audio synthesis failed:', e);
    }
}

function toggleScannerSound() {
    _scannerSoundEnabled = !_scannerSoundEnabled;
    const icon = document.getElementById('icon-sound');
    const label = document.getElementById('label-sound');
    if (icon) {
        icon.setAttribute('data-lucide', _scannerSoundEnabled ? 'volume-2' : 'volume-x');
        icon.style.color = _scannerSoundEnabled ? '#4ade80' : 'var(--text-muted)';
    }
    if (label) {
        label.innerText = _scannerSoundEnabled ? 'เสียงเปิด' : 'ปิดเสียง';
    }
    if (window.lucide) lucide.createIcons();
    if (_scannerSoundEnabled) playScannerBeep('success');
}

function setScannerMode(mode) {
    _stockScanMode = mode;
    const btnAdd = document.getElementById('btn-mode-add');
    const btnDeduct = document.getElementById('btn-mode-deduct');
    const btnLookup = document.getElementById('btn-mode-lookup');
    const badge = document.getElementById('scan-badge-mode');
    const hint = document.getElementById('scan-mode-hint-text');

    const resetStyle = (btn) => {
        if (!btn) return;
        btn.style.border = '1px solid var(--border)';
        btn.style.background = 'rgba(255,255,255,0.03)';
        btn.style.color = 'var(--text-muted)';
        btn.style.fontWeight = '600';
    };
    resetStyle(btnAdd);
    resetStyle(btnDeduct);
    resetStyle(btnLookup);

    if (mode === 'add') {
        if (btnAdd) {
            btnAdd.style.border = '1px solid #22c55e';
            btnAdd.style.background = 'rgba(34,197,94,0.18)';
            btnAdd.style.color = '#86efac';
            btnAdd.style.fontWeight = '700';
        }
        if (badge) {
            badge.innerText = 'ยิง +1 ทันที';
            badge.style.background = 'rgba(34,197,94,0.18)';
            badge.style.color = '#4ade80';
            badge.style.borderColor = 'rgba(34,197,94,0.35)';
        }
        if (hint) hint.innerText = 'ยิงบาร์โค้ด 1 ครั้ง = เพิ่มสต๊อก +1 ทันทีอัตโนมัติ';
    } else if (mode === 'deduct') {
        if (btnDeduct) {
            btnDeduct.style.border = '1px solid #ef4444';
            btnDeduct.style.background = 'rgba(239,68,68,0.18)';
            btnDeduct.style.color = '#fca5a5';
            btnDeduct.style.fontWeight = '700';
        }
        if (badge) {
            badge.innerText = 'ยิง -1 ทันที';
            badge.style.background = 'rgba(239,68,68,0.18)';
            badge.style.color = '#f87171';
            badge.style.borderColor = 'rgba(239,68,68,0.35)';
        }
        if (hint) hint.innerText = 'ยิงบาร์โค้ด 1 ครั้ง = ตัดสต๊อก -1 ทันทีอัตโนมัติ';
    } else {
        if (btnLookup) {
            btnLookup.style.border = '1px solid #3b82f6';
            btnLookup.style.background = 'rgba(59,130,246,0.18)';
            btnLookup.style.color = '#93c5fd';
            btnLookup.style.fontWeight = '700';
        }
        if (badge) {
            badge.innerText = 'ดูข้อมูลอย่างเดียว';
            badge.style.background = 'rgba(59,130,246,0.18)';
            badge.style.color = '#60a5fa';
            badge.style.borderColor = 'rgba(59,130,246,0.35)';
        }
        if (hint) hint.innerText = 'ยิงบาร์โค้ดเพื่อค้นหาและดูข้อมูล (ไม่เปลี่ยนจำนวน)';
    }

    // Keep focus on input
    const inp = document.getElementById('stock-barcode-input');
    if (inp) inp.focus();
}

function openStockScanner() {
    const modal = document.getElementById('stock-scanner-modal');
    if (!modal) return;
    const inp = document.getElementById('stock-barcode-input');
    if (inp) inp.value = '';
    modal.style.display = 'flex';
    setScannerMode(_stockScanMode);
    if (window.lucide) lucide.createIcons();
    requestAnimationFrame(() => { if (inp) inp.focus(); });
}

function closeStockScanner() {
    const modal = document.getElementById('stock-scanner-modal');
    if (modal) modal.style.display = 'none';
    clearTimeout(_stockBarcodeTimer);
}

function resetScanSession() {
    _scanSessionCount = 0;
    _scanSessionHistory = [];
    const countEl = document.getElementById('session-scan-count');
    if (countEl) countEl.innerText = '0';
    const container = document.getElementById('stock-scan-session-history-container');
    if (container) container.style.display = 'none';
    const resultEl = document.getElementById('stock-scanner-result');
    if (resultEl) resultEl.innerHTML = '';
    const inp = document.getElementById('stock-barcode-input');
    if (inp) { inp.value = ''; inp.focus(); }
}

function onStockBarcodeInput() {
    clearTimeout(_stockBarcodeTimer);
    _stockBarcodeTimer = setTimeout(() => {
        const val = document.getElementById('stock-barcode-input')?.value.trim();
        // Trigger auto-scan if string looks complete (typical barcode >= 3 chars)
        if (val && val.length >= 3) doStockBarcodeScanAction();
    }, 280);
}

async function doStockBarcodeScanAction() {
    clearTimeout(_stockBarcodeTimer);
    const inp = document.getElementById('stock-barcode-input');
    const sku = inp?.value.trim();
    if (!sku) return;

    // Immediately clear input and keep focused for seamless continuous scanning
    if (inp) inp.value = '';

    const resultEl = document.getElementById('stock-scanner-result');
    if (resultEl && resultEl.innerHTML === '') {
        resultEl.innerHTML = `<div style="display:flex;align-items:center;gap:8px;padding:12px 0;color:var(--text-muted);font-size:13px;"><i data-lucide="loader-2" style="width:16px;height:16px;"></i> กำลังประมวลผล...</div>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch(`${API_URL}/stock/barcode/scan`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify({
                sku: sku,
                action: _stockScanMode,
                reason: _stockScanMode === 'add' ? 'สแกนในห้องสต๊อก (+1)' : _stockScanMode === 'deduct' ? 'สแกนในห้องสต๊อก (-1)' : 'ค้นหาบาร์โค้ด'
            })
        });

        if (res.status === 404) {
            // Check via AI & Automotive Catalog Identification (Sources B & C)
            if (resultEl) {
                resultEl.innerHTML = `
                    <div style="padding:16px;border-radius:12px;background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.35);color:#c084fc;font-size:13px;display:flex;align-items:center;gap:12px;box-shadow:0 4px 16px rgba(139,92,246,0.15);">
                        <i data-lucide="sparkles" class="spin" style="width:22px;height:22px;color:#a855f7;flex-shrink:0;"></i>
                        <div>
                            <div style="font-weight:700;color:#f3e8ff;font-size:13.5px;">ไม่พบในสต็อก — กำลังสืบค้นด้วย AI</div>
                            <div style="font-size:11.5px;color:#d8b4fe;margin-top:2px;">ตรวจแคตตาล็อกยานยนต์ OEM & ฐานข้อมูลสากล (B & C)...</div>
                        </div>
                    </div>`;
                if (window.lucide) lucide.createIcons();
            }

            try {
                const identRes = await fetch(`${API_URL}/stock/barcode/identify/${encodeURIComponent(sku)}`, {
                    headers: HEADERS
                });
                if (identRes.ok) {
                    const identData = await identRes.json();
                    if (identData.identified) {
                        playScannerBeep('success');
                        renderStockScanIdentifiedCard(identData);
                        requestAnimationFrame(() => { if (inp) inp.focus(); });
                        return;
                    }
                }
            } catch (identErr) {
                console.warn('Identify lookup failed in dashboard scanner:', identErr);
            }

            playScannerBeep('error');
            renderScanNotFound(sku);
            requestAnimationFrame(() => { if (inp) inp.focus(); });
            return;
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(_apiErrorText(err, `HTTP ${res.status}`));
        }

        const data = await res.json();
        playScannerBeep('success');

        // Update session counts & history
        if (data.delta !== 0) {
            _scanSessionCount++;
            const countEl = document.getElementById('session-scan-count');
            if (countEl) countEl.innerText = _scanSessionCount;
        }

        const nowTime = new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        _scanSessionHistory.unshift({
            id: data.item.id,
            sku: data.item.sku,
            name_th: data.item.name_th,
            delta: data.delta,
            action: data.action,
            before: data.quantity_before,
            after: data.quantity_after,
            time: nowTime
        });

        renderScanSuccessCard(data);
        renderScanSessionHistory();

        // Refresh main stock table in background
        fetchStockData();

    } catch (err) {
        playScannerBeep('error');
        if (resultEl) {
            resultEl.innerHTML = `<div style="padding:12px;border-radius:8px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);color:#fca5a5;font-size:13px;display:flex;align-items:center;gap:8px;"><i data-lucide="alert-circle" style="width:18px;height:18px;"></i> ❌ เกิดข้อผิดพลาด: ${_escHtml(err.message)}</div>`;
            if (window.lucide) lucide.createIcons();
        }
    } finally {
        requestAnimationFrame(() => { if (inp) inp.focus(); });
    }
}

function renderScanSuccessCard(data) {
    const resultEl = document.getElementById('stock-scanner-result');
    if (!resultEl) return;
    const item = data.item;
    const isAdd = data.delta > 0;
    const isDeduct = data.delta < 0;
    const isLookup = data.delta === 0;

    const actionTitle = isAdd
        ? '✅ รับเข้าสำเร็จ (+1)'
        : isDeduct
        ? '🔻 ตัดออกสำเร็จ (-1)'
        : '🔍 พบข้อมูลสินค้า';
    const actionColor = isAdd ? '#4ade80' : isDeduct ? '#f87171' : '#60a5fa';
    const actionBg = isAdd ? 'rgba(34,197,94,0.14)' : isDeduct ? 'rgba(239,68,68,0.14)' : 'rgba(59,130,246,0.14)';
    const actionBorder = isAdd ? 'rgba(34,197,94,0.3)' : isDeduct ? 'rgba(239,68,68,0.3)' : 'rgba(59,130,246,0.3)';

    const isOut = item.quantity === 0;
    const isLow = item.quantity <= item.reorder_level && !isOut;
    const qtyColor = isOut ? '#f87171' : isLow ? '#fbbf24' : '#4ade80';

    resultEl.innerHTML = `
        <div style="background:var(--bg-app);border:1px solid ${actionBorder};border-radius:14px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,0.35);animation:fadeIn 0.2s ease;">
            <!-- Status banner -->
            <div style="padding:10px 16px;background:${actionBg};border-bottom:1px solid ${actionBorder};display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:12px;font-weight:700;color:${actionColor};display:flex;align-items:center;gap:6px;">
                    <i data-lucide="${isAdd ? 'check-circle' : isDeduct ? 'minus-circle' : 'search'}" style="width:15px;height:15px;"></i>
                    <span>${actionTitle}</span>
                </div>
                ${!isLookup ? `
                <button onclick="undoScanAction(${item.id}, ${data.delta})"
                  style="background:rgba(255,255,255,0.08);border:1px solid var(--border);color:var(--text-secondary);font-size:11px;font-weight:600;padding:3px 8px;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:4px;" title="ย้อนกลับการสแกนนี้">
                    <i data-lucide="rotate-ccw" style="width:12px;height:12px;"></i> ยกเลิกรายการนี้ (Undo)
                </button>` : ''}
            </div>

            <!-- Product info header -->
            <div style="padding:14px 16px 12px;border-bottom:1px solid var(--border);">
                <div style="font-size:17px;font-weight:800;color:var(--text-primary);line-height:1.25;margin-bottom:4px;">${_escHtml(item.name_th)}</div>
                ${item.name_en ? `<div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">${_escHtml(item.name_en)}</div>` : ''}
                <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                    <span style="font-size:11px;font-family:monospace;background:rgba(81,107,240,0.18);color:#93c5fd;border:1px solid rgba(81,107,240,0.35);padding:2px 8px;border-radius:4px;font-weight:700;">
                        SKU: ${_escHtml(item.sku || 'N/A')}
                    </span>
                    <span style="font-size:11px;background:rgba(255,255,255,0.06);color:var(--text-secondary);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:4px;">
                        ${_escHtml(item.category)}
                    </span>
                </div>
            </div>

            <!-- Big Stock Quantity Box -->
            <div style="display:flex;align-items:center;justify-content:space-around;padding:16px 14px;background:rgba(0,0,0,0.15);border-bottom:1px solid var(--border);">
                ${!isLookup ? `
                <div style="text-align:center;">
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px;">ก่อนหน้า</div>
                    <div style="font-size:24px;font-weight:700;color:var(--text-secondary);font-family:monospace;">${data.quantity_before}</div>
                </div>
                <div style="color:var(--text-muted);font-size:20px;font-weight:300;">➔</div>
                ` : ''}

                <div style="text-align:center;">
                    <div style="font-size:11px;color:${qtyColor};font-weight:700;margin-bottom:2px;">
                        ${!isLookup ? (isAdd ? '+1 ชิ้นแล้ว' : '-1 ชิ้นแล้ว') : 'คงเหลือปัจจุบัน'}
                    </div>
                    <div style="font-size:46px;font-weight:900;letter-spacing:-1px;color:${qtyColor};line-height:1;font-family:monospace;" id="inline-scan-qty-${item.id}">
                        ${item.quantity}
                    </div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
                        หน่วยคงเหลือ ${item.quantity <= item.reorder_level ? '(ต่ำกว่าจุดสั่งซื้อ ' + item.reorder_level + ')' : ''}
                    </div>
                </div>

                <div style="display:flex;flex-direction:column;gap:6px;">
                    <button onclick="inlineScanAdjust(${item.id}, 1)" style="padding:6px 12px;background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);color:#86efac;font-size:12px;font-weight:700;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:4px;">
                        <i data-lucide="plus" style="width:13px;height:13px;"></i> +1
                    </button>
                    <button onclick="inlineScanAdjust(${item.id}, -1)" style="padding:6px 12px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#fca5a5;font-size:12px;font-weight:700;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:4px;">
                        <i data-lucide="minus" style="width:13px;height:13px;"></i> -1
                    </button>
                </div>
            </div>

            <!-- Price info footer -->
            <div style="display:flex;padding:10px 14px;background:rgba(255,255,255,0.02);font-size:12px;align-items:center;">
                <div style="flex:1;text-align:center;">
                    <span style="color:var(--text-muted);">ต้นทุน:</span> <strong style="color:var(--text-primary);">฿${(item.unit_cost||0).toLocaleString('th-TH')}</strong>
                </div>
                <div style="width:1px;height:14px;background:var(--border);"></div>
                <div style="flex:1;text-align:center;">
                    <span style="color:var(--text-muted);">ราคาขาย:</span> <strong style="color:var(--accent);">฿${(item.sell_price||0).toLocaleString('th-TH')}</strong>
                </div>
                <div style="width:1px;height:14px;background:var(--border);"></div>
                <div style="flex:1;text-align:center;">
                    <a href="https://www.google.com/search?q=${encodeURIComponent((item.sku || '') + ' ' + (item.name_th || '') + ' auto part')}" target="_blank" rel="noopener noreferrer" style="color:#60a5fa;text-decoration:none;display:inline-flex;align-items:center;gap:4px;font-size:11.5px;">
                        <i data-lucide="external-link" style="width:12px;height:12px;"></i> Google
                    </a>
                </div>
            </div>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
}

let _activeDashboardIdentData = null;

function renderStockScanIdentifiedCard(data) {
    _activeDashboardIdentData = data;
    const resultEl = document.getElementById('stock-scanner-result');
    if (!resultEl) return;

    resultEl.innerHTML = `
        <div style="background:linear-gradient(145deg, rgba(139,92,246,0.09), rgba(81,107,240,0.06));border:1px solid rgba(139,92,246,0.4);border-radius:14px;overflow:hidden;box-shadow:0 8px 24px rgba(139,92,246,0.18);animation:fadeIn 0.25s ease;">
            <!-- Header -->
            <div style="padding:10px 16px;background:rgba(139,92,246,0.18);border-bottom:1px solid rgba(139,92,246,0.3);display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:12px;font-weight:700;color:#c084fc;display:flex;align-items:center;gap:6px;">
                    <i data-lucide="sparkles" style="width:15px;height:15px;"></i>
                    <span>ตรวจพบจาก AI & แคตตาล็อก</span>
                </div>
                <span style="font-size:11px;color:var(--text-muted);background:rgba(255,255,255,0.06);border:1px solid var(--border);padding:2px 8px;border-radius:10px;">
                    ${_escHtml(data.source || 'Automotive OEM Catalog')}
                </span>
            </div>

            <!-- Product info -->
            <div style="padding:14px 16px 12px;border-bottom:1px solid var(--border);">
                <div style="font-size:17px;font-weight:800;color:var(--text-primary);line-height:1.25;margin-bottom:4px;">
                    ${_escHtml(data.name_th)}
                </div>
                ${data.name_en ? `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">${_escHtml(data.name_en)}</div>` : ''}
                <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                    <span style="font-size:11px;font-family:monospace;background:rgba(81,107,240,0.18);color:#93c5fd;border:1px solid rgba(81,107,240,0.35);padding:2px 8px;border-radius:4px;font-weight:700;">
                        SKU: ${_escHtml(data.sku)}
                    </span>
                    <span style="font-size:11px;background:rgba(255,255,255,0.06);color:var(--text-secondary);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:4px;">
                        หมวด: ${_escHtml(data.category)}
                    </span>
                    ${data.brand ? `
                    <span style="font-size:11px;background:rgba(139,92,246,0.12);color:#c084fc;border:1px solid rgba(139,92,246,0.25);padding:2px 8px;border-radius:4px;">
                        ${_escHtml(data.brand)}
                    </span>` : ''}
                </div>
            </div>

            <!-- Vehicle Fitment -->
            ${data.compatible_vehicles ? `
            <div style="padding:10px 16px;background:rgba(0,0,0,0.2);border-bottom:1px solid var(--border);font-size:12px;">
                <div style="color:#60a5fa;font-weight:700;margin-bottom:3px;display:flex;align-items:center;gap:5px;">
                    <i data-lucide="car" style="width:14px;height:14px;"></i> รุ่นรถยนต์ที่รองรับ (Fitment):
                </div>
                <div style="color:var(--text-secondary);line-height:1.4;">
                    ${_escHtml(data.compatible_vehicles)}
                </div>
            </div>` : ''}

            <!-- Price Estimates -->
            <div style="display:flex;padding:12px 16px;background:rgba(255,255,255,0.02);font-size:12.5px;border-bottom:1px solid var(--border);">
                <div style="flex:1;text-align:center;">
                    <span style="color:var(--text-muted);">ราคาทุนประเมิน:</span> <strong style="color:var(--text-primary);margin-left:4px;">฿${(data.unit_cost||0).toLocaleString('th-TH')}</strong>
                </div>
                <div style="width:1px;background:var(--border);"></div>
                <div style="flex:1;text-align:center;">
                    <span style="color:var(--text-muted);">ราคาขายแนะนำ:</span> <strong style="color:var(--accent);margin-left:4px;">฿${(data.sell_price||0).toLocaleString('th-TH')}</strong>
                </div>
            </div>

            <!-- Action Buttons -->
            <div style="padding:14px 16px;display:flex;flex-direction:column;gap:8px;">
                <button onclick="openAddStockModalWithIdentified(_activeDashboardIdentData)"
                  style="display:flex;align-items:center;justify-content:center;gap:8px;padding:11px 16px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border:none;border-radius:9px;color:#fff;font-size:13.5px;font-weight:700;cursor:pointer;box-shadow:0 4px 14px rgba(124,58,237,0.4);transition:transform 0.15s;">
                    <i data-lucide="plus-circle" style="width:16px;height:16px;"></i> นำเข้าสต็อกด้วยข้อมูลนี้ (Add to Stock)
                </button>
                <a href="https://www.google.com/search?q=${encodeURIComponent((data.sku || '') + ' ' + (data.name_th || '') + ' auto part')}" target="_blank" rel="noopener noreferrer"
                  style="display:flex;align-items:center;justify-content:center;gap:6px;background:rgba(66,133,244,0.12);border:1px solid rgba(66,133,244,0.35);border-radius:8px;color:#93c5fd;padding:8px 12px;font-size:12.5px;font-weight:600;text-decoration:none;cursor:pointer;">
                    <i data-lucide="search" style="width:14px;height:14px;"></i> ตรวจสอบข้อมูลบน Google (Check on Google)
                </a>
                <button onclick="openAddStockModalWithSku('${_escHtml(data.sku)}')"
                  style="display:flex;align-items:center;justify-content:center;gap:6px;background:transparent;border:1px solid var(--border);border-radius:8px;color:var(--text-muted);padding:7px 12px;font-size:12px;cursor:pointer;">
                    <i data-lucide="edit-3" style="width:14px;height:14px;"></i> กรอกเองจากศูนย์ (Manual Entry)
                </button>
            </div>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
}

function openAddStockModalWithIdentified(data) {
    if (!data) return;
    closeStockScanner();
    openAddStockModal();
    setTimeout(() => {
        if (data.name_th) {
            const el = document.getElementById('stock-name-th');
            if (el) el.value = data.name_th;
        }
        if (data.name_en) {
            const el = document.getElementById('stock-name-en');
            if (el) el.value = data.name_en;
        }
        if (data.sku) {
            const el = document.getElementById('stock-sku');
            if (el) el.value = data.sku;
        }
        if (data.category) {
            const el = document.getElementById('stock-category');
            if (el) {
                let matched = false;
                for (let i = 0; i < el.options.length; i++) {
                    if (el.options[i].value === data.category || el.options[i].text === data.category) {
                        el.selectedIndex = i;
                        matched = true;
                        break;
                    }
                }
                if (!matched && el.options.length > 0) el.value = 'อื่นๆ';
            }
        }
        if (data.unit_cost) {
            const el = document.getElementById('stock-cost');
            if (el) el.value = data.unit_cost;
        }
        if (data.sell_price) {
            const el = document.getElementById('stock-price');
            if (el) el.value = data.sell_price;
        }
        const qtyEl = document.getElementById('stock-qty');
        if (qtyEl) {
            qtyEl.value = '1';
            qtyEl.focus();
            qtyEl.select();
        }
    }, 100);
}

function renderScanNotFound(sku) {
    const resultEl = document.getElementById('stock-scanner-result');
    if (!resultEl) return;
    resultEl.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px;padding:20px 16px;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.3);border-radius:14px;text-align:center;">
            <i data-lucide="package-x" style="width:40px;height:40px;color:#f87171;opacity:0.85;"></i>
            <div style="font-family:monospace;font-size:16px;font-weight:700;background:rgba(239,68,68,0.15);color:#fca5a5;padding:4px 14px;border-radius:6px;">"${_escHtml(sku)}"</div>
            <div style="font-size:13px;color:var(--text-primary);font-weight:600;">ไม่พบสินค้านี้ในระบบ (Not found in stock)</div>
            <div style="font-size:11px;color:var(--text-muted);">ตรวจสอบรหัสบาร์โค้ด หรือค้นหาบน Google ได้ทันที</div>
            <div style="display:flex;flex-direction:column;gap:8px;width:100%;margin-top:4px;">
                <a href="https://www.google.com/search?q=${encodeURIComponent(sku + ' อะไหล่ auto part')}" target="_blank" rel="noopener noreferrer"
                  style="display:flex;align-items:center;justify-content:center;gap:8px;padding:9px 16px;background:rgba(66,133,244,0.15);border:1px solid rgba(66,133,244,0.4);border-radius:8px;color:#93c5fd;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer;">
                    <i data-lucide="search" style="width:14px;height:14px;"></i> ค้นหาบาร์โค้ด "${_escHtml(sku)}" บน Google
                </a>
                <button onclick="openAddStockModalWithSku('${_escHtml(sku)}')"
                  style="display:flex;align-items:center;justify-content:center;gap:8px;padding:10px 20px;background:linear-gradient(135deg,var(--accent),#7c3aed);border:none;border-radius:8px;color:#fff;font-size:13px;font-weight:700;cursor:pointer;box-shadow:0 4px 14px rgba(81,107,240,0.35);">
                    <i data-lucide="plus-circle" style="width:16px;height:16px;"></i> เพิ่ม "${_escHtml(sku)}" เป็นสินค้าใหม่
                </button>
            </div>
        </div>`;
    if (window.lucide) lucide.createIcons();
}

function renderScanSessionHistory() {
    const container = document.getElementById('stock-scan-session-history-container');
    const listEl = document.getElementById('stock-scan-session-list');
    const totalEl = document.getElementById('session-items-total');
    if (!container || !listEl) return;

    if (_scanSessionHistory.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    if (totalEl) totalEl.innerText = `${_scanSessionHistory.length} รายการ`;

    listEl.innerHTML = _scanSessionHistory.map((item, idx) => {
        const isAdd = item.delta > 0;
        const isDeduct = item.delta < 0;
        const badgeColor = isAdd ? '#4ade80' : isDeduct ? '#f87171' : '#60a5fa';
        const badgeBg = isAdd ? 'rgba(34,197,94,0.15)' : isDeduct ? 'rgba(239,68,68,0.15)' : 'rgba(59,130,246,0.15)';
        const deltaText = isAdd ? '+1' : isDeduct ? '-1' : '0';

        return `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:7px 10px;background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:8px;font-size:12px;">
                <div style="display:flex;align-items:center;gap:8px;overflow:hidden;flex:1;">
                    <span style="font-size:10px;font-family:monospace;padding:2px 6px;border-radius:4px;background:${badgeBg};color:${badgeColor};font-weight:700;">
                        ${deltaText}
                    </span>
                    <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        <span style="font-weight:600;color:var(--text-primary);">${_escHtml(item.name_th)}</span>
                        <span style="font-size:10px;color:var(--text-muted);margin-left:4px;font-family:monospace;">(${_escHtml(item.sku)})</span>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;margin-left:8px;flex-shrink:0;">
                    <span style="font-size:11px;font-weight:700;color:var(--text-secondary);font-family:monospace;">คงเหลือ: ${item.after}</span>
                    <span style="font-size:10px;color:var(--text-muted);">${item.time}</span>
                </div>
            </div>
        `;
    }).join('');
}

async function undoScanAction(id, delta) {
    if (delta === 0) return;
    try {
        const revertDelta = -delta;
        const res = await fetch(`${API_URL}/stock/${id}/adjust`, {
            method: 'PUT',
            headers: HEADERS,
            body: JSON.stringify({ delta: revertDelta, reason: 'ยกเลิกการสแกนบาร์โค้ดล่าสุด' })
        });
        if (res.ok) {
            playScannerBeep('undo');
            const updated = await res.json();
            showToast('↩️ ยกเลิกรายการสำเร็จ');

            // Decrement session count
            if (_scanSessionCount > 0) _scanSessionCount--;
            const countEl = document.getElementById('session-scan-count');
            if (countEl) countEl.innerText = _scanSessionCount;

            // Update UI card
            const el = document.getElementById(`inline-scan-qty-${id}`);
            if (el) {
                el.innerText = updated.quantity;
                const isOut = updated.quantity === 0;
                const isLow = updated.quantity <= updated.reorder_level && !isOut;
                el.style.color = isOut ? '#f87171' : isLow ? '#fbbf24' : '#4ade80';
            }

            // Remove top entry from session history
            _scanSessionHistory.shift();
            renderScanSessionHistory();
            fetchStockData();
        }
    } catch (e) {
        console.error('Undo failed:', e);
    } finally {
        const inp = document.getElementById('stock-barcode-input');
        if (inp) inp.focus();
    }
}

async function inlineScanAdjust(id, delta) {
    try {
        const res = await fetch(`${API_URL}/stock/${id}/adjust`, {
            method: 'PUT', headers: HEADERS,
            body: JSON.stringify({ delta, reason: delta > 0 ? 'บาร์โค้ดสแกน — ปรับเพิ่ม' : 'บาร์โค้ดสแกน — ปรับลด' })
        });
        if (res.ok) {
            playScannerBeep(delta > 0 ? 'success' : 'undo');
            const updated = await res.json();
            const el = document.getElementById(`inline-scan-qty-${id}`);
            if (el) {
                el.innerText = updated.quantity;
                const isOut = updated.quantity === 0;
                const isLow = updated.quantity <= updated.reorder_level && !isOut;
                el.style.color = isOut ? '#f87171' : isLow ? '#fbbf24' : '#4ade80';
            }
            fetchStockData();
            showToast(delta > 0 ? '✅ ปรับเพิ่ม +1' : '✅ ปรับลด -1');
        }
    } catch (e) { console.error(e); }
    finally {
        const inp = document.getElementById('stock-barcode-input');
        if (inp) inp.focus();
    }
}

function openAddStockModalWithSku(sku) {
    closeStockScanner();
    openAddStockModal();
    setTimeout(() => {
        const el = document.getElementById('stock-sku');
        if (el) el.value = sku;
    }, 50);
}

function _escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}




async function submitAddStock() {
    const nameTh = document.getElementById('stock-name-th')?.value.trim();
    const sku    = document.getElementById('stock-sku')?.value.trim();
    const cost   = parseFloat(document.getElementById('stock-cost')?.value);
    const price  = parseFloat(document.getElementById('stock-price')?.value);
    const qty    = parseInt(document.getElementById('stock-qty')?.value) || 0;

    if (!nameTh) return alert('กรุณากรอกชื่ออะไหล่ภาษาไทย');
    if (!sku)    return alert('กรุณากรอกรหัสสินค้า (SKU)');
    if (isNaN(cost) || cost < 0) return alert('กรุณากรอกราคาต้นทุนที่ถูกต้อง');
    if (isNaN(price) || price < 0) return alert('กรุณากรอกราคาขายที่ถูกต้อง');

    const payload = {
        name_th:       nameTh,
        name_en:       document.getElementById('stock-name-en')?.value.trim() || null,
        sku:           sku,
        category:      document.getElementById('stock-category')?.value || 'อื่นๆ',
        unit_cost:     cost,
        sell_price:    price,
        quantity:      qty,
        reorder_level: parseInt(document.getElementById('stock-reorder')?.value) || 5,
    };

    try {
        const res = await fetch(`${API_URL}/stock/`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(_apiErrorText(err, 'เกิดข้อผิดพลาด'));
        }
        showToast(`✅ เพิ่มอะไหล่ "${nameTh}" เรียบร้อยแล้ว!`);
        closeStockModal();
        fetchStockData();
    } catch (err) {
        showToast(`❌ ไม่สามารถเพิ่มอะไหล่: ${err.message}`);
    }
}

// ── SMART GLOBAL SEARCH WITH DIRECT NAVIGATION ──
let _searchDropdownTimer = null;

function handleGlobalSearchInput(val) {
    clearTimeout(_searchDropdownTimer);
    _searchDropdownTimer = setTimeout(() => {
        renderGlobalSearchDropdown(val);
    }, 120);
}

function handleGlobalSearch(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const q = (document.getElementById('global-search')?.value || '').trim();
        if (!q) return;
        executeGlobalSearchNavigate(q);
    } else if (e.key === 'Escape') {
        closeGlobalSearchDropdown();
    }
}

function closeGlobalSearchDropdown() {
    const dd = document.getElementById('global-search-dropdown');
    if (dd) dd.style.display = 'none';
}

function renderGlobalSearchDropdown(query) {
    const dd = document.getElementById('global-search-dropdown');
    if (!dd) return;
    const q = (query || '').trim().toLowerCase();
    if (!q) {
        dd.style.display = 'none';
        return;
    }

    // Match Tickets
    const matchTickets = allTickets.filter(t => {
        const id = String(t.id);
        const plate = (t.vehicle_plate || '').toLowerCase();
        const cust = (t.customer_name || '').toLowerCase();
        const car = (t.car_model || '').toLowerCase();
        const raw = (t.raw_input || '').toLowerCase();
        return id === q || ('#' + id) === q || plate.includes(q) || cust.includes(q) || car.includes(q) || raw.includes(q);
    }).slice(0, 5);

    // Match Customers
    const matchCustomers = allCustomers.filter(c => {
        const name = (c.name || '').toLowerCase();
        const phone = (c.phone || '').toLowerCase();
        const line = (c.line_id || '').toLowerCase();
        return name.includes(q) || phone.includes(q) || line.includes(q);
    }).slice(0, 5);

    // Match Stock Items
    const matchStock = allStock.filter(s => {
        const name = (s.name || '').toLowerCase();
        const code = (s.code || '').toLowerCase();
        const en = (s.name_en || '').toLowerCase();
        const cat = (s.category || '').toLowerCase();
        return name.includes(q) || code.includes(q) || en.includes(q) || cat.includes(q);
    }).slice(0, 5);

    if (!matchTickets.length && !matchCustomers.length && !matchStock.length) {
        dd.innerHTML = `<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:0.84rem;">ไม่พบข้อมูลสำหรับ "${_escHtml(q)}"</div>`;
        dd.style.display = 'block';
        return;
    }

    let html = '';

    // Tickets section
    if (matchTickets.length > 0) {
        html += `<div class="search-dropdown-group-title"><i data-lucide="wrench" style="width:12px;height:12px;display:inline-block;vertical-align:-1px;"></i> งานซ่อม (Tickets)</div>`;
        html += matchTickets.map(t => {
            const cost = (t.final_cost || t.total_estimated_cost || 0).toLocaleString('th-TH');
            return `
                <div class="search-dropdown-item" onclick="navigateToTicket(${t.id})">
                    <div>
                        <strong>Ticket #${t.id}</strong> — <span style="color:#93c5fd;">${t.vehicle_plate || 'ไม่ระบุทะเบียน'}</span>
                        <div class="item-sub">ลูกค้า: ${t.customer_name || 'ลูกค้าทั่วไป'} | ${t.car_model || ''}</div>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:#34d399;font-weight:600;font-size:0.8rem;">฿${cost}</span>
                        <div style="font-size:0.7rem;">${statusBadgeHtml(t.status)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Customers section
    if (matchCustomers.length > 0) {
        html += `<div class="search-dropdown-group-title"><i data-lucide="users" style="width:12px;height:12px;display:inline-block;vertical-align:-1px;"></i> ลูกค้า (Customers)</div>`;
        html += matchCustomers.map(c => `
            <div class="search-dropdown-item" onclick="navigateToCustomer(${c.id})">
                <div>
                    <strong>👤 ${c.name}</strong>
                    <div class="item-sub">📞 ${c.phone || '—'} ${c.line_id ? '| LINE: ' + c.line_id : ''}</div>
                </div>
                <button class="btn-sm" style="font-size:0.7rem;padding:2px 8px;color:#60a5fa;border-color:rgba(96,165,250,0.3);background:rgba(96,165,250,0.1);">ดู 360°</button>
            </div>
        `).join('');
    }

    // Stock section
    if (matchStock.length > 0) {
        html += `<div class="search-dropdown-group-title"><i data-lucide="package" style="width:12px;height:12px;display:inline-block;vertical-align:-1px;"></i> อะไหล่ในคลัง (Stock)</div>`;
        html += matchStock.map(s => `
            <div class="search-dropdown-item" onclick="navigateToStock('${_escHtml(s.code || s.name)}')">
                <div>
                    <strong>📦 ${s.name}</strong>
                    <div class="item-sub">รหัส: ${s.code || '—'} | หมวด: ${s.category || '—'}</div>
                </div>
                <div style="text-align:right;">
                    <span class="pill ${s.quantity <= s.reorder_level ? 'danger' : ''}">${s.quantity} ${s.unit || 'ชิ้น'}</span>
                    <div style="font-size:0.74rem;color:#34d399;margin-top:2px;">฿${(s.price||0).toLocaleString('th-TH')}</div>
                </div>
            </div>
        `).join('');
    }

    dd.innerHTML = html;
    dd.style.display = 'block';
    if (window.lucide) lucide.createIcons();
}

function executeGlobalSearchNavigate(rawQ) {
    const q = rawQ.trim().toLowerCase();
    closeGlobalSearchDropdown();

    // 1. Direct ticket number match e.g. "1", "#1"
    const cleanId = q.replace('#', '');
    if (/^\d+$/.test(cleanId)) {
        const numId = parseInt(cleanId);
        const ticketExists = allTickets.find(t => t.id === numId);
        if (ticketExists) {
            navigateToTicket(numId);
            return;
        }
    }

    // 2. Ticket match by plate or text
    const matchTicket = allTickets.find(t => {
        const plate = (t.vehicle_plate || '').toLowerCase();
        const cust = (t.customer_name || '').toLowerCase();
        const car = (t.car_model || '').toLowerCase();
        return plate.includes(q) || cust.includes(q) || car.includes(q);
    });
    if (matchTicket) {
        navigateToTicket(matchTicket.id);
        return;
    }

    // 3. Customer match by name, phone or LINE
    const matchCust = allCustomers.find(c => {
        const name = (c.name || '').toLowerCase();
        const phone = (c.phone || '').toLowerCase();
        const line = (c.line_id || '').toLowerCase();
        return name.includes(q) || phone.includes(q) || line.includes(q);
    });
    if (matchCust) {
        navigateToCustomer(matchCust.id);
        return;
    }

    // 4. Stock match by name or code
    const matchItem = allStock.find(s => {
        const name = (s.name || '').toLowerCase();
        const code = (s.code || '').toLowerCase();
        return name.includes(q) || code.includes(q);
    });
    if (matchItem) {
        navigateToStock(matchItem.code || matchItem.name);
        return;
    }

    showToast(`🔍 ไม่พบข้อมูลที่ตรงกับ "${rawQ}"`);
}

function navigateToTicket(ticketId) {
    closeGlobalSearchDropdown();
    switchTab('repairs');
    openTicketDetailModal(ticketId);
    showToast(`🔧 กำลังแสดงข้อมูลงานซ่อม Ticket #${ticketId}`);
}

function navigateToCustomer(customerId) {
    closeGlobalSearchDropdown();
    switchTab('customers');
    viewCustomerProfile(customerId);
    showToast(`👤 กำลังแสดงข้อมูลลูกค้า 360°`);
}

function navigateToStock(query) {
    closeGlobalSearchDropdown();
    switchTab('stock');
    if (query) {
        const raw = String(query).trim();
        const input = document.getElementById('stock-search-input');
        if (input) input.value = raw;
        handleStockSearchInput(raw);
        closeStockSearchDropdown();
        // Highlight the closest match while still listing all results
        const q = raw.toLowerCase();
        const match = (allStock || []).find(s => (s.name || '').toLowerCase() === q || (s.code || '').toLowerCase() === q);
        if (match) setTimeout(() => selectStockItem(match.id), 150);
        return;
    }
    showToast(`📦 ไปที่คลังอะไหล่: ${query}`);
}

// Close search dropdowns when clicking outside
document.addEventListener('click', function(e) {
    const searchBox = document.querySelector('.header-search');
    if (searchBox && !searchBox.contains(e.target)) {
        closeGlobalSearchDropdown();
    }
    const stockSearch = document.getElementById('stock-search-input');
    const stockDropdown = document.getElementById('stock-search-dropdown');
    if (stockDropdown && stockSearch && !stockSearch.contains(e.target) && !stockDropdown.contains(e.target)) {
        closeStockSearchDropdown();
    }
});

function openPOSModal() { switchTab(null, 'pos'); }

// ── INTAKE MODAL ──
function openNewIntakeModal() {
    document.getElementById('intake-modal').style.display = 'flex';
    // Reset form
    ['intake-plate','intake-car-model','intake-customer','intake-phone','intake-line-id','intake-raw','intake-mileage'].forEach(id => {
        const el = document.getElementById(id); if (el) el.value = '';
    });
    const mechEl = document.getElementById('intake-mechanic');
    if (mechEl) mechEl.value = 'ช่างสมชาย';
    const wBanner = document.getElementById('fx-warranty-banner');
    if (wBanner) wBanner.style.display = 'none';
    // Add 2 default empty lines
    const container = document.getElementById('intake-lines-container');
    if (container) { container.innerHTML = ''; addIntakeLine(); addIntakeLine(); }
    updateIntakeTotal();
    if (window.lucide) lucide.createIcons();

    // Attach autofill listeners if not already attached
    _setupIntakeAutofill();
    // Make sure stock is loaded for the part search
    if (!allStock.length) fetchStockData();
}
function closeIntakeModal() {
    document.getElementById('intake-modal').style.display = 'none';
    closeIntakePartDropdown();
}

function _setupIntakeAutofill() {
    const phoneInput = document.getElementById('intake-phone');
    if (phoneInput && !phoneInput._autofillAttached) {
        phoneInput._autofillAttached = true;
        phoneInput.addEventListener('input', () => {
            const p = phoneInput.value.trim();
            if (p.length >= 8) {
                const found = allCustomers.find(c => c.phone && c.phone.replace(/\D/g, '') === p.replace(/\D/g, ''));
                if (found) {
                    const custEl = document.getElementById('intake-customer');
                    const lineEl = document.getElementById('intake-line-id');
                    if (custEl && !custEl.value) custEl.value = found.name;
                    if (lineEl && !lineEl.value && found.line_id) lineEl.value = found.line_id;
                }
            }
        });
    }

    const plateInput = document.getElementById('intake-plate');
    if (plateInput && !plateInput._autofillAttached) {
        plateInput._autofillAttached = true;
        plateInput.addEventListener('change', async () => {
            const pl = plateInput.value.trim();
            if (typeof fxCheckWarranty === 'function') fxCheckWarranty(pl);
            if (!pl) return;
            try {
                const res = await fetch(`${API_URL}/customers/vehicles/${encodeURIComponent(pl)}/health`, { headers: HEADERS });
                if (res.ok) {
                    const v = await res.json();
                    const carModelEl = document.getElementById('intake-car-model');
                    if (carModelEl && !carModelEl.value) carModelEl.value = `${v.brand} ${v.model}`.trim();
                    const mileageEl = document.getElementById('intake-mileage');
                    if (mileageEl && !mileageEl.value && v.current_mileage) mileageEl.value = v.current_mileage;
                    if (v.customer_id) {
                        const cust = allCustomers.find(c => c.id === v.customer_id);
                        if (cust) {
                            const custEl = document.getElementById('intake-customer');
                            const phoneEl = document.getElementById('intake-phone');
                            const lineEl = document.getElementById('intake-line-id');
                            if (custEl && !custEl.value) custEl.value = cust.name;
                            if (phoneEl && !phoneEl.value) phoneEl.value = cust.phone;
                            if (lineEl && !lineEl.value && cust.line_id) lineEl.value = cust.line_id;
                        }
                    }
                }
            } catch {}
        });
    }
}

// ── Intake line items table ──
let _intakeLineId = 0;
// Line rows are shared by the intake form (#intake-lines-container) and the edit-ticket form (#edit-ticket-lines)
function addIntakeLine(desc = '', price = '', containerId = 'intake-lines-container', qty = 1, stockId = null) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const id = ++_intakeLineId;
    const row = document.createElement('div');
    row.id = `intake-line-${id}`;
    row.className = 'intake-line-row';
    row.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:8px;';
    row.innerHTML = `
        <input type="text" class="form-input intake-line-desc" placeholder="🔍 ค้นหาอะไหล่ในคลัง หรือพิมพ์ เช่น ค่าแรง" value="${_escHtml(desc)}" style="flex:2;min-width:0;" autocomplete="off"
            oninput="updateIntakeTotal(); onIntakeLineSearch(${id})" onfocus="onIntakeLineSearch(${id})" onkeydown="onIntakeLineKeydown(event, ${id})">
        <input type="number" class="form-input intake-line-qty" title="จำนวน" placeholder="จำนวน" value="${qty}" step="1" min="1" style="width:64px;flex-shrink:0;text-align:center;" oninput="updateIntakeTotal()">
        <input type="number" class="form-input intake-line-price" placeholder="ราคา/หน่วย" value="${price}" step="0.01" min="0" style="flex:1;max-width:120px;min-width:80px;" oninput="updateIntakeTotal()">
        <button type="button" onclick="removeIntakeLine(${id})" style="flex-shrink:0;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#f87171;border-radius:7px;padding:7px 10px;cursor:pointer;"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
    `;
    if (stockId) {
        const d = row.querySelector('.intake-line-desc');
        d.dataset.stockId = stockId;
        d.dataset.stockName = desc;
    }
    container.appendChild(row);
    if (window.lucide) lucide.createIcons();
}

function _readLineRows(containerId) {
    const rows = [];
    document.querySelectorAll(`#${containerId} .intake-line-row`).forEach(row => {
        const descEl = row.querySelector('.intake-line-desc');
        const desc = descEl?.value.trim();
        if (!desc) return;
        const qty = Math.max(1, parseInt(row.querySelector('.intake-line-qty')?.value) || 1);
        const price = parseFloat(row.querySelector('.intake-line-price')?.value) || 0;
        rows.push({ desc, qty, price, total: Math.round(qty * price * 100) / 100, stockId: descEl.dataset.stockId ? parseInt(descEl.dataset.stockId) : null });
    });
    return rows;
}
function removeIntakeLine(id) {
    const el = document.getElementById(`intake-line-${id}`);
    if (el) el.remove();
    closeIntakePartDropdown();
    updateIntakeTotal();
}

// ── Intake line: search parts from stock ──
let _intakeDdLineId = null;
let _intakeDdMatches = [];
let _intakeDdActive = -1;

function _getIntakePartDropdown() {
    let dd = document.getElementById('intake-part-dropdown');
    if (!dd) {
        dd = document.createElement('div');
        dd.id = 'intake-part-dropdown';
        dd.style.cssText = 'position:fixed;z-index:10000;display:none;max-height:300px;overflow-y:auto;background:#1e293b;border:1px solid rgba(255,255,255,0.12);border-radius:10px;box-shadow:0 12px 32px rgba(0,0,0,0.5);';
        document.body.appendChild(dd);
    }
    return dd;
}

function onIntakeLineSearch(id) {
    const input = document.querySelector(`#intake-line-${id} .intake-line-desc`);
    if (!input) return;
    // Typing again detaches the row from a previously selected stock item
    if (input.dataset.stockId && input.value !== input.dataset.stockName) delete input.dataset.stockId;
    if (!allStock.length) { fetchStockData().then(() => _renderIntakePartDropdown(id)); return; }
    _renderIntakePartDropdown(id);
}

function _renderIntakePartDropdown(id) {
    const input = document.querySelector(`#intake-line-${id} .intake-line-desc`);
    if (!input || document.activeElement !== input) return;
    const dd = _getIntakePartDropdown();
    const query = input.value.trim().toLowerCase();

    _intakeDdLineId = id;
    _intakeDdActive = -1;
    _intakeDdMatches = (allStock || []).filter(s => {
        if (!query) return true;
        return [s.name, s.name_en, s.code, s.category].some(v => (v || '').toLowerCase().includes(query));
    }).slice(0, 30);

    if (!_intakeDdMatches.length) {
        if (!query) { closeIntakePartDropdown(); return; }
        dd.innerHTML = `<div style="padding:12px 14px;color:var(--text-muted);font-size:0.82rem;">ไม่พบอะไหล่ "${_escHtml(input.value.trim())}" ในคลัง — ใช้ข้อความที่พิมพ์ได้เลย</div>`;
    } else {
        dd.innerHTML = `<div style="padding:7px 14px;font-size:0.72rem;color:var(--text-muted);border-bottom:1px solid rgba(255,255,255,0.06);">📦 เลือกอะไหล่จากคลัง (${_intakeDdMatches.length}${_intakeDdMatches.length === 30 ? '+' : ''} รายการ)</div>` +
            _intakeDdMatches.map((s, i) => `
            <div class="intake-part-opt" data-idx="${i}" onmousedown="event.preventDefault(); selectIntakePart(${i})"
                style="padding:8px 14px;border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:10px;">
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;color:#93c5fd;font-size:0.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        ${_escHtml(s.name)}
                        ${s.code ? `<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:4px;font-size:0.72rem;color:#cbd5e1;">${_escHtml(s.code)}</code>` : ''}
                    </div>
                    <div style="font-size:0.72rem;color:var(--text-muted);">${s.category ? _escHtml(s.category) : '—'}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div style="font-size:0.84rem;color:#34d399;font-weight:700;">฿${(s.price || 0).toLocaleString('th-TH')}</div>
                    <div style="font-size:0.72rem;color:${(s.available ?? s.quantity) <= 0 ? '#f87171' : ((s.available ?? s.quantity) <= s.reorder_level ? '#fbbf24' : 'var(--text-muted)')};">${s.reserved ? `ว่าง ${s.available} (จอง ${s.reserved})` : `คงเหลือ ${s.quantity}`} ${s.unit || 'ชิ้น'}</div>
                </div>
            </div>`).join('');
    }

    const r = input.getBoundingClientRect();
    dd.style.left = r.left + 'px';
    dd.style.width = Math.max(r.width, 340) + 'px';
    const below = window.innerHeight - r.bottom;
    if (below < 220 && r.top > below) {
        dd.style.top = '';
        dd.style.bottom = (window.innerHeight - r.top + 4) + 'px';
    } else {
        dd.style.bottom = '';
        dd.style.top = (r.bottom + 4) + 'px';
    }
    dd.style.display = 'block';
}

function _highlightIntakePart() {
    document.querySelectorAll('#intake-part-dropdown .intake-part-opt').forEach(el => {
        const on = +el.dataset.idx === _intakeDdActive;
        el.style.background = on ? 'rgba(96,165,250,0.15)' : '';
        if (on) el.scrollIntoView({ block: 'nearest' });
    });
}

function onIntakeLineKeydown(e, id) {
    const dd = document.getElementById('intake-part-dropdown');
    if (!dd || dd.style.display === 'none' || _intakeDdLineId !== id || !_intakeDdMatches.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); _intakeDdActive = Math.min(_intakeDdActive + 1, _intakeDdMatches.length - 1); _highlightIntakePart(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); _intakeDdActive = Math.max(_intakeDdActive - 1, 0); _highlightIntakePart(); }
    else if (e.key === 'Enter' && _intakeDdActive >= 0) { e.preventDefault(); selectIntakePart(_intakeDdActive); }
    else if (e.key === 'Escape') { closeIntakePartDropdown(); }
}

function selectIntakePart(idx) {
    const s = _intakeDdMatches[idx];
    const row = document.getElementById(`intake-line-${_intakeDdLineId}`);
    if (!s || !row) return;
    const descEl = row.querySelector('.intake-line-desc');
    const priceEl = row.querySelector('.intake-line-price');
    descEl.value = s.name;
    descEl.dataset.stockId = s.id;
    descEl.dataset.stockName = s.name;
    if (priceEl) priceEl.value = s.price || '';
    closeIntakePartDropdown();
    updateIntakeTotal();
    if ((s.available ?? s.quantity) <= 0) showToast(`⚠️ "${s.name}" ไม่มีของว่าง${s.reserved ? ` (จองไว้ ${s.reserved})` : ''}`);
    // Add a fresh empty line if this was the last one, so the next part can be picked right away
    const container = row.parentElement;
    if (container && container.lastElementChild === row) addIntakeLine('', '', container.id);
}

function closeIntakePartDropdown() {
    const dd = document.getElementById('intake-part-dropdown');
    if (dd) dd.style.display = 'none';
    _intakeDdLineId = null;
}

document.addEventListener('focusout', e => {
    if (e.target.classList && e.target.classList.contains('intake-line-desc')) setTimeout(closeIntakePartDropdown, 120);
});
document.addEventListener('scroll', e => {
    if (_intakeDdLineId !== null && !(e.target.id === 'intake-part-dropdown')) closeIntakePartDropdown();
}, true);
function updateIntakeTotal() {
    const show = (containerId, displayId) => {
        const total = _readLineRows(containerId).reduce((s, r) => s + r.total, 0);
        const display = document.getElementById(displayId);
        if (display) display.textContent = '฿' + total.toLocaleString('th-TH', {minimumFractionDigits:0});
        return total;
    };
    show('edit-ticket-lines', 'edit-ticket-total-display');
    return show('intake-lines-container', 'intake-total-display');
}

function _buildIntakeLineItemsText() {
    // One line per item: "<desc> <total price>" — the intake parser reads the trailing number as the price
    return _readLineRows('intake-lines-container').map(r => {
        const label = r.qty > 1 ? `${r.desc} (${r.qty} ชิ้น)` : r.desc;
        return r.total > 0 ? `${label} ${r.total}` : label;
    }).join('\n');
}

function _getIntakeData() {
    const plate    = document.getElementById('intake-plate')?.value.trim() || '';
    const carModel = document.getElementById('intake-car-model')?.value.trim() || '';
    const customer = document.getElementById('intake-customer')?.value.trim() || '';
    const phone    = document.getElementById('intake-phone')?.value.trim() || '';
    const lineId   = document.getElementById('intake-line-id')?.value.trim() || '';
    const mechanic = document.getElementById('intake-mechanic')?.value.trim() || 'ช่าง';
    const mileage  = document.getElementById('intake-mileage')?.value || '';
    const note     = document.getElementById('intake-raw')?.value.trim() || '';
    const linesText = _buildIntakeLineItemsText();
    const rawInput = [linesText, note ? `หมายเหตุ: ${note}` : ''].filter(Boolean).join('\n');
    return { plate, carModel, customer, phone, lineId, mechanic, mileage, note, linesText, rawInput };
}

async function submitIntakeModal() {
    const d = _getIntakeData();
    if (!d.plate) return alert('กรุณากรอกทะเบียนรถ');
    if (!d.rawInput.trim()) return alert('กรุณากรอกรายการซ่อมหรืออาการ');
    closeIntakeModal();
    showToast('📄 กำลังเปิดงานซ่อม...');
    try {
        const payload = {
            vehicle_plate: d.plate,
            customer_name: d.customer || undefined,
            customer_phone: d.phone || undefined,
            customer_line_id: d.lineId || undefined,
            car_model: d.carModel || undefined,
            mechanic_name: d.mechanic || undefined,
            raw_input: `ใบแจ้งงาน (${d.mechanic}):\n${d.rawInput}`,
        };
        if (d.mileage) payload.mileage = parseInt(d.mileage);
        // Parts picked from stock — taken out of stock when the job is completed
        const stockLinks = _readLineRows('intake-lines-container')
            .filter(r => r.stockId)
            .map(r => ({ name: r.desc, stock_item_id: r.stockId, qty: r.qty }));
        if (stockLinks.length) payload.stock_links = stockLinks;
        const res = await fetch(`${API_URL}/tickets/ingest`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        const data = await res.json();
        // If client-provided fields are missing in data, enrich for printing
        if (!data.customer_name && d.customer) data.customer_name = d.customer;
        if (!data.customer_phone && d.phone) data.customer_phone = d.phone;
        if (!data.car_model && d.carModel) data.car_model = d.carModel;
        if (!data.mechanic_name && d.mechanic) data.mechanic_name = d.mechanic;

        showToast(`✅ เปิด Ticket #${data.id} สำเร็จ!`);
        fetchTicketsData();
        fetchCustomersData();
        // Auto-open print work order
        setTimeout(() => printWorkOrderFromTicket(data), 800);
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาด')); }
}

// ── Print Work Order (ใบแจ้งงาน) from the form (before saving) ──
function previewWorkOrder() {
    const d = _getIntakeData();
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const shopPhone = localStorage.getItem('shop_phone') || '095-418-5332';
    const shopAddress = localStorage.getItem('shop_address') || '';
    const now = new Date().toLocaleDateString('th-TH', {year:'numeric', month:'long', day:'numeric'});

    // Parse lines for the table
    const lineRows = _readLineRows('intake-lines-container').map(r => ({
        desc: r.qty > 1 ? `${r.desc} × ${r.qty}` : r.desc,
        price: r.total,
    }));
    const total = lineRows.reduce((s, r) => s + r.price, 0);

    const tableHtml = lineRows.length > 0 ? `
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;margin-bottom:16px;">
            <thead>
                <tr style="background:#f3f4f6;border-bottom:2px solid #111;">
                    <th style="padding:8px 10px;text-align:left;">#</th>
                    <th style="padding:8px 10px;text-align:left;">รายการซ่อม / อะไหล่</th>
                    <th style="padding:8px 10px;text-align:right;">ราคาประมาณ</th>
                </tr>
            </thead>
            <tbody>
                ${lineRows.map((r, i) => `
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:8px 10px;color:#6b7280;">${i+1}</td>
                        <td style="padding:8px 10px;">${r.desc || '—'}</td>
                        <td style="padding:8px 10px;text-align:right;">${r.price > 0 ? '฿' + r.price.toLocaleString('th-TH') : '—'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <div style="text-align:right;font-size:1rem;font-weight:700;margin-bottom:20px;">ยอดรวมประมาณ: ฿${total.toLocaleString('th-TH')}</div>
    ` : '<p style="color:#888;margin-bottom:20px;">— ยังไม่มีรายการ —</p>';

    _openPrintWindow(`
        <div style="text-align:center;margin-bottom:18px;padding-bottom:14px;border-bottom:2px solid #111;">
            <div style="font-size:1.5rem;font-weight:800;">${shopName}</div>
            ${shopAddress ? `<div style="font-size:0.82rem;color:#555;">${shopAddress}</div>` : ''}
            <div style="font-size:0.82rem;color:#555;">โทร: ${shopPhone}</div>
            <div style="font-size:1.1rem;font-weight:700;margin-top:10px;letter-spacing:0.05em;">ใบแจ้งงาน / Work Order</div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-bottom:14px;font-size:0.87rem;">
            <div>
                <div>วันที่รับรถ: <strong>${now}</strong></div>
                <div>ทะเบียนรถ: <strong>${d.plate || '—'}</strong></div>
                <div>ยี่ห้อ/รุ่น: <strong>${d.carModel || '—'}</strong></div>
            </div>
            <div style="text-align:right;">
                <div>ชื่อลูกค้า: <strong>${d.customer || '—'}</strong></div>
                <div>เบอร์โทร: <strong>${d.phone || '—'}</strong></div>
                <div>ช่างผู้รับงาน: <strong>${d.mechanic || '—'}</strong></div>
                ${d.mileage ? `<div>เลขไมล์: <strong>${parseInt(d.mileage).toLocaleString('th-TH')} กม.</strong></div>` : ''}
            </div>
        </div>

        <hr style="border:none;border-top:1px dashed #ccc;margin:14px 0;">
        ${tableHtml}

        ${d.note ? `<div style="margin-bottom:14px;padding:10px;background:#f9fafb;border-radius:6px;font-size:0.85rem;"><strong>อาการที่ลูกค้าแจ้ง:</strong> ${d.note}</div>` : ''}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:40px;font-size:0.85rem;">
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นลูกค้า</div>
                <div style="color:#888;margin-top:4px;">(${d.customer || '...........................'})</div>
            </div>
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นช่าง</div>
                <div style="color:#888;margin-top:4px;">(${d.mechanic || '...........................'})</div>
            </div>
        </div>
        <div style="text-align:center;margin-top:24px;padding-top:12px;border-top:1px dashed #ccc;color:#888;font-size:0.75rem;">
            หมายเหตุ: ราคาดังกล่าวเป็นราคาประมาณการเบื้องต้น อาจมีการเปลี่ยนแปลงตามผลการตรวจเช็คจริง
        </div>
    `, `ใบแจ้งงาน — ${d.plate || shopName}`);
}

// ── Print Work Order from saved ticket data ──
function printWorkOrderFromTicket(t) {
    if (!t) return;
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const shopPhone = localStorage.getItem('shop_phone') || '095-418-5332';
    const shopAddress = localStorage.getItem('shop_address') || '';
    const dateStr = new Date(t.created_at || Date.now()).toLocaleDateString('th-TH', {year:'numeric',month:'long',day:'numeric'});
    const lineItems = t.line_items || [];

    // Calculate sum of line items
    const itemsSum = lineItems.reduce((s, i) => s + (i.total || ((i.qty || 1) * (i.unit_price || 0)) || 0), 0);
    const total = itemsSum > 0 ? itemsSum : (t.total_estimated_cost || t.final_cost || 0);

    const tableHtml = lineItems.length > 0 ? `
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;margin-bottom:16px;">
            <thead>
                <tr style="background:#f3f4f6;border-bottom:2px solid #111;">
                    <th style="padding:8px 10px;text-align:left;">#</th>
                    <th style="padding:8px 10px;text-align:left;">รายการซ่อม / อะไหล่</th>
                    <th style="padding:8px 10px;text-align:center;">จำนวน</th>
                    <th style="padding:8px 10px;text-align:right;">ราคาประมาณ</th>
                </tr>
            </thead>
            <tbody>
                ${lineItems.map((item, i) => `
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:8px 10px;color:#6b7280;">${i+1}</td>
                        <td style="padding:8px 10px;">${item.name_th || item.name || '—'}</td>
                        <td style="padding:8px 10px;text-align:center;">${item.qty || 1} ${item.unit || 'รายการ'}</td>
                        <td style="padding:8px 10px;text-align:right;">${(item.total || (item.qty * item.unit_price) || 0) > 0 ? '฿' + (item.total || (item.qty * item.unit_price)).toLocaleString('th-TH') : '—'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <div style="text-align:right;font-size:1.05rem;font-weight:700;margin-bottom:20px;">ยอดรวมประมาณ: ฿${total.toLocaleString('th-TH')}</div>
    ` : `<p style="color:#888;padding:12px;">— ไม่มีรายการ (ช่างจะประเมินรายการหลังตรวจเช็คจริง) —</p>`;

    _openPrintWindow(`
        <div style="text-align:center;margin-bottom:18px;padding-bottom:14px;border-bottom:2px solid #111;">
            <div style="font-size:1.5rem;font-weight:800;">${shopName}</div>
            ${shopAddress ? `<div style="font-size:0.82rem;color:#555;">${shopAddress}</div>` : ''}
            <div style="font-size:0.82rem;color:#555;">โทร: ${shopPhone}</div>
            <div style="font-size:1.1rem;font-weight:700;margin-top:10px;letter-spacing:0.05em;">ใบแจ้งงาน / Work Order</div>
            <div style="font-size:0.82rem;color:#888;">เลขที่งาน: <strong>#${t.id}</strong></div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-bottom:14px;font-size:0.87rem;">
            <div>
                <div>วันที่รับรถ: <strong>${dateStr}</strong></div>
                <div>ทะเบียนรถ: <strong>${t.vehicle_plate || '—'}</strong></div>
                <div>ยี่ห้อ/รุ่น: <strong>${t.car_model || '—'}</strong></div>
            </div>
            <div style="text-align:right;">
                <div>ชื่อลูกค้า: <strong>${t.customer_name || 'ลูกค้าทั่วไป'}</strong></div>
                ${t.customer_phone ? `<div>เบอร์โทร: <strong>${t.customer_phone}</strong></div>` : ''}
                <div>ช่างผู้รับงาน: <strong>${t.mechanic_name || 'ช่างประจำ'}</strong></div>
            </div>
        </div>

        <hr style="border:none;border-top:1px dashed #ccc;margin:14px 0;">
        ${tableHtml}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:40px;font-size:0.85rem;">
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นลูกค้า</div>
                <div style="color:#888;margin-top:4px;">(${t.customer_name || '...........................'})</div>
            </div>
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นช่างผู้รับงาน</div>
                <div style="color:#888;margin-top:4px;">(${t.mechanic_name || '...........................'})</div>
            </div>
        </div>
        <div style="text-align:center;margin-top:24px;padding-top:12px;border-top:1px dashed #ccc;color:#888;font-size:0.75rem;">
            ราคาดังกล่าวเป็นราคาประมาณการ อาจมีการเปลี่ยนแปลงตามผลการตรวจเช็คจริง
        </div>
    `, `ใบแจ้งงาน #${t.id} — ${t.vehicle_plate || ''}`);
}

// ── Print Invoice/Receipt (ใบเสร็จรับเงิน) ──
function printInvoiceFromTicket(t) {
    if (!t) return;
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const shopPhone = localStorage.getItem('shop_phone') || '095-418-5332';
    const shopAddress = localStorage.getItem('shop_address') || '';
    const dateStr = (t.approved_at ? new Date(t.approved_at) : new Date()).toLocaleDateString('th-TH', {year:'numeric',month:'long',day:'numeric'});
    const lineItems = t.line_items || [];

    // Separate parts and labor cleanly
    const hasLaborInItems = lineItems.some(i => i.type === 'labor' || (i.name_th && i.name_th.includes('ค่าแรง')) || (i.name_th && i.name_th.includes('ค่าบริการ')));
    const laborOnlyFromTicket = (!hasLaborInItems && (t.estimated_labor_cost || 0) > 0) ? t.estimated_labor_cost : 0;

    let partsTotal = 0;
    let laborTotal = 0;
    lineItems.forEach(i => {
        const itemVal = i.total || ((i.qty || 1) * (i.unit_price || 0)) || 0;
        if (i.type === 'labor' || (i.name_th && (i.name_th.includes('ค่าแรง') || i.name_th.includes('ค่าบริการ')))) {
            laborTotal += itemVal;
        } else {
            partsTotal += itemVal;
        }
    });
    if (laborOnlyFromTicket > 0) {
        laborTotal += laborOnlyFromTicket;
    }

    const calculatedTotal = partsTotal + laborTotal;
    const total = (t.final_cost && t.final_cost > 0) ? t.final_cost : (calculatedTotal > 0 ? calculatedTotal : (t.total_estimated_cost || 0));

    const tableHtml = `
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;margin-bottom:16px;">
            <thead>
                <tr style="background:#111;color:#fff;">
                    <th style="padding:9px 10px;text-align:left;">#</th>
                    <th style="padding:9px 10px;text-align:left;">รายการ</th>
                    <th style="padding:9px 10px;text-align:center;">จำนวน</th>
                    <th style="padding:9px 10px;text-align:right;border-radius:0 4px 0 0;">ราคา</th>
                </tr>
            </thead>
            <tbody>
                ${lineItems.map((item, i) => `
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:8px 10px;color:#6b7280;">${i+1}</td>
                        <td style="padding:8px 10px;">${item.name_th || item.name || '—'}</td>
                        <td style="padding:8px 10px;text-align:center;">${item.qty || 1} ${item.unit || 'รายการ'}</td>
                        <td style="padding:8px 10px;text-align:right;">฿${(item.total || (item.qty * item.unit_price) || 0).toLocaleString('th-TH')}</td>
                    </tr>
                `).join('') || '<tr><td colspan="4" style="padding:12px;text-align:center;color:#888;">ไม่มีรายการอะไหล่</td></tr>'}
                ${laborOnlyFromTicket > 0 ? `
                <tr style="border-bottom:1px solid #e5e7eb;background:#f9fafb;">
                    <td style="padding:8px 10px;color:#6b7280;">${lineItems.length+1}</td>
                    <td style="padding:8px 10px;font-style:italic;">ค่าแรงบริการ</td>
                    <td style="padding:8px 10px;text-align:center;">—</td>
                    <td style="padding:8px 10px;text-align:right;">฿${laborOnlyFromTicket.toLocaleString('th-TH')}</td>
                </tr>` : ''}
            </tbody>
        </table>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;padding:10px 0;border-top:2px solid #111;font-size:0.9rem;">
            ${partsTotal > 0 ? `<div>ค่าอะไหล่รวม: <strong>฿${partsTotal.toLocaleString('th-TH')}</strong></div>` : ''}
            ${laborTotal > 0 ? `<div>ค่าแรงบริการรวม: <strong>฿${laborTotal.toLocaleString('th-TH')}</strong></div>` : ''}
            ${typeof fxVatBlock === 'function' ? fxVatBlock(total) : ''}
            <div style="font-size:1.25rem;font-weight:800;color:#111;border-top:2px solid #111;padding-top:8px;margin-top:4px;">
                รวมทั้งสิ้น: ฿${total.toLocaleString('th-TH')}
            </div>
            ${t.amount_paid > 0 && t.balance_due > 0 ? `<div>ชำระแล้ว: <strong>฿${t.amount_paid.toLocaleString('th-TH')}</strong> · คงค้าง: <strong>฿${t.balance_due.toLocaleString('th-TH')}</strong></div>` : ''}
        </div>
    `;

    const isVat = (typeof fxShop !== 'undefined') && fxShop.vat_registered === '1';
    const taxId = (typeof fxShop !== 'undefined') ? fxShop.shop_tax_id : '';
    const payLabel = { paid: '✅ ชำระครบแล้ว', partial: '🟡 ชำระบางส่วน', unpaid: '⏳ ยังไม่ชำระ' }[t.payment_status] || (t.status === 'COMPLETED' ? 'ซ่อมเสร็จ' : t.status);
    const photoList = (t.photos || []).slice();
    const rawImg = (t.raw_input || '').match(/\[แนบภาพถ่าย:\s*([^\]]+)\]/);
    if (rawImg) photoList.unshift({ path: rawImg[1].trim(), kind: 'before' });
    const photosHtml = photoList.length ? `
        <div style="margin-top:14px;">
            ${['before', 'after'].map(kind => {
                const list = photoList.filter(p => p.kind === kind);
                return list.length ? `<div style="font-weight:700;font-size:0.85rem;margin:8px 0 4px;">${kind === 'before' ? 'ภาพก่อนซ่อม' : 'ภาพหลังซ่อม'}</div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">${list.map(p => `<img src="${p.path}" style="width:150px;height:110px;object-fit:cover;border:1px solid #ddd;border-radius:4px;">`).join('')}</div>` : '';
            }).join('')}
        </div>` : '';
    const warrantyHtml = t.warranty_months ? `<div style="margin-top:12px;padding:10px;border:1px solid #10b981;border-radius:4px;font-size:0.85rem;">
        🛡️ <strong>รับประกัน ${t.warranty_months} เดือน</strong>${t.warranty_note ? ' — ' + t.warranty_note : ''}${t.warranty_until ? ` (ถึงวันที่ ${new Date(t.warranty_until).toLocaleDateString('th-TH', {year:'numeric',month:'long',day:'numeric'})})` : ''}
    </div>` : '';

    _openPrintWindow(`
        <div style="text-align:center;margin-bottom:18px;padding-bottom:14px;border-bottom:2px solid #111;">
            <div style="font-size:1.5rem;font-weight:800;">${shopName}</div>
            ${shopAddress ? `<div style="font-size:0.82rem;color:#555;">${shopAddress}</div>` : ''}
            <div style="font-size:0.82rem;color:#555;">โทร: ${shopPhone}</div>
            ${isVat && taxId ? `<div style="font-size:0.82rem;color:#555;">เลขประจำตัวผู้เสียภาษี: ${taxId}</div>` : ''}
            <div style="font-size:1.1rem;font-weight:700;margin-top:10px;letter-spacing:0.05em;">${isVat ? 'ใบเสร็จรับเงิน / ใบกำกับภาษี (Tax Invoice)' : 'ใบเสร็จรับเงิน / Receipt'}</div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-bottom:16px;font-size:0.87rem;">
            <div>
                <div>เลขที่ใบเสร็จ: <strong>#${t.id}</strong></div>
                <div>วันที่: <strong>${dateStr}</strong></div>
                <div>ทะเบียนรถ: <strong>${t.vehicle_plate || '—'}</strong>  ยี่ห้อ/รุ่น: <strong>${t.car_model || '—'}</strong></div>
            </div>
            <div style="text-align:right;">
                <div>ชื่อลูกค้า: <strong>${t.customer_name || '—'}</strong></div>
                ${t.mechanic_name ? `<div>ช่าง: <strong>${t.mechanic_name}</strong></div>` : ''}
                <div>การชำระ: <strong>${payLabel}</strong></div>
            </div>
        </div>

        <hr style="border:none;border-top:1px dashed #ccc;margin:14px 0;">
        ${tableHtml}

        ${t.mechanic_notes ? `<div style="margin-top:14px;padding:10px;background:#fffbeb;border-left:3px solid #f59e0b;border-radius:4px;font-size:0.85rem;"><strong>หมายเหตุช่าง:</strong> ${t.mechanic_notes}</div>` : ''}
        ${warrantyHtml}
        ${photosHtml}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:40px;font-size:0.85rem;">
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นผู้รับเงิน</div>
            </div>
            <div style="text-align:center;">
                <div style="border-top:1px solid #111;padding-top:8px;margin-top:40px;">ลายเซ็นลูกค้า</div>
                <div style="color:#888;margin-top:4px;">(${t.customer_name || '...........................'})</div>
            </div>
        </div>
        <div style="text-align:center;margin-top:20px;padding-top:12px;border-top:1px dashed #ccc;color:#888;font-size:0.75rem;">
            ขอบคุณที่ใช้บริการ — ${shopName}
        </div>
    `, `ใบเสร็จ #${t.id} — ${t.vehicle_plate || ''}`);
}

// ── Shared print window helper ──
function _openPrintWindow(bodyContent, title = 'พิมพ์เอกสาร') {
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const w = window.open('', '_blank', 'width=780,height=1000');
    w.document.write(`<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Sarabun', Arial, sans-serif; background: #fff; color: #111; padding: 32px 40px; max-width: 720px; margin: 0 auto; }
    .print-actions { position: fixed; top: 14px; right: 14px; display: flex; gap: 8px; z-index: 99; }
    @media print {
      .print-actions { display: none !important; }
      body { padding: 8mm 12mm; }
    }
  </style>
</head>
<body>
  <div class="print-actions">
    <button onclick="window.print()" style="background:#111;color:#fff;border:none;border-radius:6px;padding:8px 20px;cursor:pointer;font-size:14px;font-family:inherit;font-weight:700;">🖨️ พิมพ์ / PDF</button>
    <button onclick="window.close()" style="background:#e5e7eb;color:#111;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:14px;font-family:inherit;">✕ ปิด</button>
  </div>
  ${bodyContent}
</body>
</html>`);
    w.document.close();
    setTimeout(() => { try { w.focus(); } catch(e){} }, 300);
}


// ── APPROVE MODAL (อนุมัติเริ่มงาน) ──
function openApproveModal(id) {
    pendingTicketId = id;
    const t = allTickets.find(x => x.id === id);
    document.getElementById('approve-modal-id').innerText = `#${id}`;

    // Compute true items sum
    const lineItems = t?.line_items || [];
    const itemsSum = lineItems.reduce((s, i) => s + (i.total || ((i.qty || 1) * (i.unit_price || 0)) || 0), 0);
    const estimatedCost = itemsSum > 0 ? itemsSum : (t?.total_estimated_cost || 0);

    // Populate ticket preview summary
    const summaryEl = document.getElementById('approve-ticket-summary');
    if (summaryEl && t) {
        summaryEl.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <div><strong>ทะเบียน:</strong> ${t.vehicle_plate || '—'} <span style="color:var(--text-muted);">(${t.car_model || ''})</span></div>
                <div><strong>ลูกค้า:</strong> ${t.customer_name || 'ลูกค้าทั่วไป'}</div>
            </div>
            ${lineItems.length > 0 ? `
                <div style="margin:8px 0;max-height:110px;overflow-y:auto;background:rgba(0,0,0,0.2);border-radius:6px;padding:6px 10px;">
                    ${lineItems.map((item, idx) => `
                        <div style="display:flex;justify-content:space-between;font-size:0.8rem;padding:2px 0;">
                            <span>${idx+1}. ${item.name_th || item.name}</span>
                            <strong style="color:#93c5fd;">฿${(item.total || (item.qty*item.unit_price) || 0).toLocaleString('th-TH')}</strong>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            <div style="text-align:right;font-size:0.95rem;font-weight:700;color:#34d399;">
                ยอดรวมประเมิน: ฿${estimatedCost.toLocaleString('th-TH')}
            </div>
        `;
    }

    // Set name and cost properly (NEVER keep stale values)
    const nameEl = document.getElementById('approve-name');
    if (nameEl) nameEl.value = t?.mechanic_name || 'ช่างสมชาย';

    const notesEl = document.getElementById('approve-notes');
    if (notesEl) notesEl.value = '';

    const costEl = document.getElementById('approve-cost');
    if (costEl) costEl.value = estimatedCost;

    document.getElementById('approve-modal').style.display = 'flex';
}
function closeModal() {
    document.getElementById('approve-modal').style.display = 'none';
}
async function submitApproval() {
    const name = document.getElementById('approve-name').value.trim();
    const notes = document.getElementById('approve-notes').value.trim();
    const costVal = document.getElementById('approve-cost').value;
    if (!name) return alert('โปรดกรอกชื่อช่างผู้อนุมัติ');
    const finalCost = costVal !== '' ? parseFloat(costVal) : undefined;
    closeModal();
    showToast(`⏳ กำลังอนุมัติเริ่มงาน Ticket #${pendingTicketId}...`);
    try {
        const res = await fetch(`${API_URL}/tickets/${pendingTicketId}/approve`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({ approved_by: name, mechanic_notes: notes || undefined, final_cost: finalCost })
        });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        const approvedTicket = await res.json();
        showToast(`✅ อนุมัติเริ่มงาน Ticket #${pendingTicketId} เรียบร้อย! ช่างกำลังดำเนินการซ่อม`);
        fetchTicketsData();
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาดในการอนุมัติ')); }
}

// ── COMPLETE REPAIR MODAL (แจ้งซ่อมเสร็จ) ──
let pendingCompleteTicketId = null;
function openCompleteModal(id) {
    pendingCompleteTicketId = id;
    const t = allTickets.find(x => x.id === id);
    document.getElementById('complete-modal-id').innerText = `#${id}`;

    // Compute actual total
    const lineItems = t?.line_items || [];
    const itemsSum = lineItems.reduce((s, i) => s + (i.total || ((i.qty || 1) * (i.unit_price || 0)) || 0), 0);
    const cost = (t?.final_cost && t.final_cost > 0) ? t.final_cost : (itemsSum > 0 ? itemsSum : (t?.total_estimated_cost || 0));

    const summaryEl = document.getElementById('complete-ticket-summary');
    if (summaryEl && t) {
        summaryEl.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <div><strong>ทะเบียนรถ:</strong> <span style="color:#93c5fd;font-weight:700;">${t.vehicle_plate || '—'}</span> <span style="color:var(--text-muted);">(${t.car_model || ''})</span></div>
                <div><strong>ลูกค้า:</strong> ${t.customer_name || 'ลูกค้าทั่วไป'}</div>
            </div>
            ${lineItems.length > 0 ? `
                <div style="margin:8px 0;max-height:120px;overflow-y:auto;background:rgba(0,0,0,0.25);border-radius:6px;padding:6px 10px;">
                    ${lineItems.map((item, idx) => `
                        <div style="display:flex;justify-content:space-between;font-size:0.82rem;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                            <span>${idx+1}. ${item.name_th || item.name} (${item.qty||1} ${item.unit||'รายการ'})</span>
                            <strong style="color:#34d399;">฿${(item.total || (item.qty*item.unit_price) || 0).toLocaleString('th-TH')}</strong>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            <div style="display:flex;justify-content:space-between;align-items:center;padding-top:4px;">
                <span style="color:var(--text-secondary);">ช่างผู้รับงาน: <strong>${t.mechanic_name || 'ช่างประจำ'}</strong></span>
                <span style="font-size:0.95rem;font-weight:700;color:#34d399;">ยอดประเมินเดิม: ฿${(t.total_estimated_cost||itemsSum||0).toLocaleString('th-TH')}</span>
            </div>
        `;
    }

    const costInput = document.getElementById('complete-cost');
    if (costInput) costInput.value = cost;

    const byInput = document.getElementById('complete-by');
    if (byInput) byInput.value = t?.mechanic_name || 'ช่างสมชาย';

    const notesInput = document.getElementById('complete-notes');
    if (notesInput) notesInput.value = 'ซ่อมบำรุงและทดสอบระบบเรียบร้อย พร้อมส่งมอบรถ';

    const wm = document.getElementById('complete-warranty-months');
    if (wm) wm.value = t?.warranty_months || '';
    const wn = document.getElementById('complete-warranty-note');
    if (wn) wn.value = t?.warranty_note || '';
    const paid = t?.amount_paid || 0;
    const hint = document.getElementById('complete-balance-hint');
    if (hint) hint.textContent = paid > 0 ? `(รับมัดจำไว้แล้ว ฿${paid.toLocaleString('th-TH')} — จะรับเพิ่มเฉพาะส่วนที่เหลือ)` : '';
    const collect = document.getElementById('complete-collect-now');
    if (collect) collect.checked = true;

    document.getElementById('complete-modal').style.display = 'flex';
}
function closeCompleteModal() {
    document.getElementById('complete-modal').style.display = 'none';
}
async function submitComplete() {
    if (!pendingCompleteTicketId) return;
    const costVal = document.getElementById('complete-cost').value;
    const completedBy = document.getElementById('complete-by').value.trim();
    const notes = document.getElementById('complete-notes').value.trim();

    if (costVal === '' || parseFloat(costVal) < 0) return alert('กรุณากรอกยอดชำระสุทธิ');
    const finalCost = parseFloat(costVal);

    closeCompleteModal();
    showToast(`⏳ กำลังบันทึกงานซ่อมเสร็จ Ticket #${pendingCompleteTicketId}...`);
    try {
        const res = await fetch(`${API_URL}/tickets/${pendingCompleteTicketId}/complete`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({
                completed_by: completedBy || 'ช่างประจำ',
                final_cost: finalCost,
                completion_notes: notes || undefined,
                warranty_months: parseInt(document.getElementById('complete-warranty-months')?.value) || 0,
                warranty_note: document.getElementById('complete-warranty-note')?.value.trim() || '',
            })
        });
        if (!res.ok) throw new Error(_apiErrorText(await res.json().catch(() => ({})), ''));
        let completedTicket = await res.json();
        // Take the remaining balance now if the customer paid at pick-up
        if (document.getElementById('complete-collect-now')?.checked && completedTicket.balance_due > 0) {
            const pr = await fetch(`${API_URL}/payments/ticket/${completedTicket.id}`, {
                method: 'POST', headers: HEADERS,
                body: JSON.stringify({ amount: completedTicket.balance_due, method: document.getElementById('complete-pay-method')?.value || 'เงินสด', received_by: completedBy || null, note: 'ชำระตอนรับรถ' })
            });
            if (!pr.ok) showToast('⚠️ บันทึกงานเสร็จแล้ว แต่บันทึกรับเงินไม่สำเร็จ: ' + _apiErrorText(await pr.json().catch(() => ({}))));
            const fresh = await fetch(`${API_URL}/tickets/${completedTicket.id}`, { headers: HEADERS });
            if (fresh.ok) completedTicket = await fresh.json();
        }
        showToast(`✅ บันทึกงานซ่อม Ticket #${pendingCompleteTicketId} เสร็จสิ้นเรียบร้อย!`);
        fetchTicketsData();
        fetchStockData();

        // Prompt to print invoice
        if (confirm(`งานซ่อม Ticket #${pendingCompleteTicketId} เสร็จสมบูรณ์แล้ว!\nต้องการเปิดพิมพ์ใบเสร็จรับเงิน (Invoice) คิดเงินลูกค้าทันทีหรือไม่?`)) {
            printInvoiceFromTicket(completedTicket);
        }
    } catch (e) { showToast('❌ ' + (e.message || 'เกิดข้อผิดพลาดในการบันทึกงานเสร็จ')); }
}

// ── SYSTEM SETTINGS & AI CONFIGURATION ──────────────────────────────────────────

async function loadSettings() {
    try {
        const res = await fetch(`${API_URL}/settings/`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();

        const badgeEl = document.getElementById('active-ai-badge');
        const copilotBadge = document.getElementById('copilot-engine-badge');
        const gInput = document.getElementById('gemini-key-input');
        const oInput = document.getElementById('openai-key-input');
        const lInput = document.getElementById('line-token-input');

        if (gInput && data.gemini_key_preview) gInput.placeholder = `บันทึกแล้ว: ${data.gemini_key_preview}`;
        if (oInput && data.openai_key_preview) oInput.placeholder = `บันทึกแล้ว: ${data.openai_key_preview}`;
        if (lInput && data.line_token_preview) lInput.placeholder = `บันทึกแล้ว: ${data.line_token_preview}`;

        let statusText = '⚡ ROSE Core Intelligence';
        let badgeClass = 'badge-neutral';
        let badgeColor = '#6366f1';
        let drawerText = '⚡ AI Ready';

        if (data.active_ai_provider === 'gemini') {
            statusText = '🟢 Gemini 3.6 Flash Active';
            badgeClass = 'badge-success';
            badgeColor = '#10b981';
            drawerText = '🟢 Gemini Active';
        } else if (data.active_ai_provider === 'openai') {
            statusText = '🟢 OpenAI GPT-4o Active';
            badgeClass = 'badge-success';
            badgeColor = '#10b981';
            drawerText = '🟢 OpenAI Active';
        }

        if (badgeEl) {
            badgeEl.className = `badge-pill ${badgeClass}`;
            badgeEl.textContent = statusText;
        }
        if (copilotBadge) {
            copilotBadge.textContent = drawerText;
            copilotBadge.style.color = badgeColor;
            copilotBadge.style.borderColor = badgeColor;
        }

        // Restore saved sheets webhook
        const savedSheet = localStorage.getItem('sheets_webhook_url');
        const sheetInput = document.getElementById('sheets-url');
        if (savedSheet && sheetInput) sheetInput.value = savedSheet;

        // Restore workshop profile in settings
        loadShopProfileSettings();
        loadBackupStats();

    } catch (e) {
        console.warn('Could not load settings:', e);
    }
}

function loadShopProfileSettings() {
    const shopNameInput = document.getElementById('settings-shop-name');
    const shopPhoneInput = document.getElementById('settings-shop-phone');
    const shopAddressInput = document.getElementById('settings-shop-address');
    if (shopNameInput) shopNameInput.value = localStorage.getItem('shop_name') || 'Zero Garage';
    if (shopPhoneInput) shopPhoneInput.value = localStorage.getItem('shop_phone') || '095-418-5332';
    if (shopAddressInput) shopAddressInput.value = localStorage.getItem('shop_address') || '';
}

function saveShopProfileSettings() {
    const shopName = document.getElementById('settings-shop-name')?.value.trim() || 'Zero Garage';
    const shopPhone = document.getElementById('settings-shop-phone')?.value.trim() || '095-418-5332';
    const shopAddress = document.getElementById('settings-shop-address')?.value.trim() || '';
    localStorage.setItem('shop_name', shopName);
    localStorage.setItem('shop_phone', shopPhone);
    localStorage.setItem('shop_address', shopAddress);
    if (typeof fxSaveShopSettings === 'function') fxSaveShopSettings();
    else showToast('✅ บันทึกข้อมูลหัวกระดาษเรียบร้อย (เบอร์: ' + shopPhone + ')');
}

// ─── Data Backup & Device Transfer ──────────────────────────────────────────
let selectedBackupFile = null;

function goToBackupSettings() {
    switchTab(null, 'settings');
    loadBackupStats();
    setTimeout(() => {
        const sec = document.getElementById('backup-transfer-section');
        if (sec) {
            sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
            sec.style.transition = 'box-shadow 0.4s ease';
            sec.style.boxShadow = '0 0 24px rgba(99, 102, 241, 0.6)';
            setTimeout(() => { sec.style.boxShadow = ''; }, 1600);
        }
    }, 150);
}

async function loadBackupStats() {
    if (typeof fxLoadBackupStatus === "function") fxLoadBackupStatus();
    try {
        const res = await fetch(`${API_URL}/backup/stats`, { headers: HEADERS });
        if (!res.ok) return;
        const data = await res.json();

        const s = data.summary || {};
        const elCust = document.getElementById('backup-stat-customers');
        const elVeh = document.getElementById('backup-stat-vehicles');
        const elTick = document.getElementById('backup-stat-tickets');
        const elStock = document.getElementById('backup-stat-stock');
        const elBills = document.getElementById('backup-stat-bills');
        const elSize = document.getElementById('backup-stat-size');

        if (elCust) elCust.textContent = (s.customers || 0) + ' คน';
        if (elVeh) elVeh.textContent = (s.vehicles || 0) + ' คัน';
        if (elTick) elTick.textContent = (s.tickets || 0) + ' ใบ';
        if (elStock) elStock.textContent = (s.stock_items || 0) + ' รายการ';
        if (elBills) elBills.textContent = (s.bills || 0) + ' บิล';
        if (elSize) elSize.textContent = (data.file_size_kb || 0) + ' KB';

        // Render backups list
        const backups = data.available_backups || [];
        const countEl = document.getElementById('backup-history-count');
        const listEl = document.getElementById('backup-history-list');

        if (countEl) countEl.textContent = `${backups.length} จุด`;

        if (listEl) {
            if (backups.length === 0) {
                listEl.innerHTML = `<div style="color: #94a3b8; font-size: 0.85rem; padding: 8px;">ยังไม่มีจุดสำรองข้อมูลอัตโนมัติ (ระบบจะสร้างให้อัตโนมัติเมื่อมีการนำเข้าข้อมูล)</div>`;
            } else {
                listEl.innerHTML = backups.map(b => {
                    const dt = b.created_at ? new Date(b.created_at).toLocaleString('th-TH') : '-';
                    return `
                        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 8px 12px; font-size: 0.82rem; flex-wrap: wrap; gap: 8px;">
                            <div>
                                <strong style="color: #e2e8f0; display: block;">${b.filename}</strong>
                                <span style="color: #94a3b8;">${dt} • ${b.size_kb} KB</span>
                            </div>
                            <div style="display: flex; gap: 8px;">
                                <button class="btn-outline-sm" style="color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);" onclick="restoreLocalBackup('${b.filename}')" title="กู้คืนจุดนี้">
                                    <i data-lucide="rotate-ccw"></i> กู้คืน
                                </button>
                                <button class="btn-outline-sm" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.4);" onclick="deleteLocalBackup('${b.filename}')" title="ลบไฟล์นี้">
                                    <i data-lucide="trash-2"></i>
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');
                if (window.lucide) lucide.createIcons();
            }
        }
    } catch (e) {
        console.warn('Could not load backup stats:', e);
    }
}

function exportDatabaseFile() {
    showToast('กำลังดาวน์โหลดฐานข้อมูล SQLite (.db)...');
    downloadWithAuth(`${API_URL}/backup/export-db`, 'workshop_backup.db').catch(e => showToast('❌ ' + e.message));
}

function exportJsonFile() {
    showToast('กำลังดาวน์โหลดไฟล์ข้อมูล JSON (.json)...');
    const sName = encodeURIComponent(document.getElementById('settings-shop-name')?.value || localStorage.getItem('shop_name') || 'Zero Garage');
    const sPhone = encodeURIComponent(document.getElementById('settings-shop-phone')?.value || localStorage.getItem('shop_phone') || '');
    const sAddress = encodeURIComponent(document.getElementById('settings-shop-address')?.value || localStorage.getItem('shop_address') || '');
    downloadWithAuth(`${API_URL}/backup/export-json?shop_name=${sName}&shop_phone=${sPhone}&shop_address=${sAddress}`, 'workshop_backup.json')
        .catch(e => showToast('❌ ' + e.message));
}

function handleBackupDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    const dz = document.getElementById('backup-dropzone');
    if (dz) dz.style.borderColor = '#6366f1';
}

function handleBackupDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    const dz = document.getElementById('backup-dropzone');
    if (dz) dz.style.borderColor = 'rgba(99, 102, 241, 0.4)';
}

function handleBackupDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    handleBackupDragLeave(e);
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleBackupFilePicked(e.dataTransfer.files);
    }
}

function handleBackupFilePicked(files) {
    if (!files || files.length === 0) return;
    const file = files[0];
    const name = file.name.toLowerCase();

    const isDb = name.endsWith('.db') || name.endsWith('.sqlite') || name.endsWith('.sqlite3');
    const isJson = name.endsWith('.json');

    if (!isDb && !isJson) {
        showToast('❌ กรุณาเลือกไฟล์ .db หรือ .json เท่านั้น', 'danger');
        return;
    }

    selectedBackupFile = file;

    const previewEl = document.getElementById('backup-file-preview');
    const nameEl = document.getElementById('backup-selected-name');
    const sizeEl = document.getElementById('backup-selected-size');
    const typeEl = document.getElementById('backup-selected-type');
    const jsonOpts = document.getElementById('json-import-options');
    const btnImport = document.getElementById('btn-do-import');

    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `ขนาด: ${(file.size / 1024).toFixed(1)} KB (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;

    if (typeEl) {
        if (isDb) {
            typeEl.textContent = 'SQLite .DB';
            typeEl.className = 'badge-pill badge-primary';
            if (jsonOpts) jsonOpts.style.display = 'none';
        } else {
            typeEl.textContent = 'JSON Data';
            typeEl.className = 'badge-pill badge-success';
            if (jsonOpts) jsonOpts.style.display = 'block';
        }
    }

    if (previewEl) previewEl.style.display = 'block';
    if (btnImport) btnImport.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function confirmAndExecuteImport() {
    if (!selectedBackupFile) {
        showToast('กรุณาเลือกไฟล์ที่ต้องการนำเข้าก่อน', 'warning');
        return;
    }

    const modal = document.getElementById('confirm-restore-modal');
    const detailsEl = document.getElementById('confirm-restore-details');
    const isJson = selectedBackupFile.name.toLowerCase().endsWith('.json');
    const mode = document.querySelector('input[name="json-import-mode"]:checked')?.value || 'replace';

    let modeText = 'แทนที่ฐานข้อมูลเดิมทั้งหมด 100% (Full Restore)';
    if (isJson && mode === 'merge') {
        modeText = 'ผสานข้อมูลเดิม (Merge / Append - ไม่ลบข้อมูลเดิม)';
    }

    if (detailsEl) {
        detailsEl.innerHTML = `
            <div><strong>ชื่อไฟล์:</strong> ${selectedBackupFile.name}</div>
            <div><strong>ขนาดไฟล์:</strong> ${(selectedBackupFile.size / 1024).toFixed(1)} KB</div>
            <div><strong>ประเภทข้อมูล:</strong> ${isJson ? 'ไฟล์ข้อมูล JSON' : 'ไฟล์ฐานข้อมูล SQLite (.db)'}</div>
            <div><strong>รูปแบบการนำเข้า:</strong> <span style="color: #f59e0b;">${modeText}</span></div>
            <div style="margin-top: 8px; color: #10b981;">🛡️ ระบบจะบันทึกจุดสำรองข้อมูลก่อนเริ่มดำเนินการให้อัตโนมัติ</div>
        `;
    }

    if (modal) modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeConfirmRestoreModal() {
    const modal = document.getElementById('confirm-restore-modal');
    if (modal) modal.style.display = 'none';
    const progress = document.getElementById('import-progress-area');
    if (progress) progress.style.display = 'none';
    const btnProceed = document.getElementById('btn-confirm-import-proceed');
    const btnCancel = document.getElementById('btn-confirm-import-cancel');
    if (btnProceed) btnProceed.disabled = false;
    if (btnCancel) btnCancel.disabled = false;
}

async function doExecuteImport() {
    if (!selectedBackupFile) return;

    const btnProceed = document.getElementById('btn-confirm-import-proceed');
    const btnCancel = document.getElementById('btn-confirm-import-cancel');
    const progress = document.getElementById('import-progress-area');

    if (btnProceed) btnProceed.disabled = true;
    if (btnCancel) btnCancel.disabled = true;
    if (progress) progress.style.display = 'block';

    const isJson = selectedBackupFile.name.toLowerCase().endsWith('.json');
    const formData = new FormData();
    formData.append('file', selectedBackupFile);

    const url = isJson ? `${API_URL}/backup/import-json` : `${API_URL}/backup/import-db`;
    if (isJson) {
        const mode = document.querySelector('input[name="json-import-mode"]:checked')?.value || 'replace';
        formData.append('mode', mode);
    }

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY },
            body: formData,
        });

        const data = await res.json();
        if (res.ok && data.ok) {
            showToast('✅ นำเข้าข้อมูลสำเร็จเรียบร้อยแล้ว!');
            if (data.shop_profile) {
                if (data.shop_profile.shop_name) localStorage.setItem('shop_name', data.shop_profile.shop_name);
                if (data.shop_profile.shop_phone) localStorage.setItem('shop_phone', data.shop_profile.shop_phone);
                if (data.shop_profile.shop_address) localStorage.setItem('shop_address', data.shop_profile.shop_address);
                loadShopProfileSettings();
            }

            closeConfirmRestoreModal();

            // Reset preview
            selectedBackupFile = null;
            const previewEl = document.getElementById('backup-file-preview');
            const btnImport = document.getElementById('btn-do-import');
            if (previewEl) previewEl.style.display = 'none';
            if (btnImport) btnImport.style.display = 'none';
            const fInput = document.getElementById('backup-file-input');
            if (fInput) fInput.value = '';

            await loadBackupStats();

            // Refresh app data
            setTimeout(() => {
                showToast('🔄 กำลังรีเฟรชข้อมูลหน้าจอทั้งหมด...');
                setTimeout(() => { location.reload(); }, 1200);
            }, 600);
        } else {
            showToast('❌ นำเข้าข้อมูลไม่สำเร็จ: ' + (data.detail || data.message || 'เกิดข้อผิดพลาด'), 'danger');
            if (btnProceed) btnProceed.disabled = false;
            if (btnCancel) btnCancel.disabled = false;
            if (progress) progress.style.display = 'none';
        }
    } catch (e) {
        showToast('❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้: ' + e.message, 'danger');
        if (btnProceed) btnProceed.disabled = false;
        if (btnCancel) btnCancel.disabled = false;
        if (progress) progress.style.display = 'none';
    }
}

function toggleBackupHistory() {
    const container = document.getElementById('backup-history-container');
    const chevron = document.getElementById('backup-history-chevron');
    if (!container) return;
    const isHidden = container.style.display === 'none';
    container.style.display = isHidden ? 'block' : 'none';
    if (chevron) {
        chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
    }
}

async function restoreLocalBackup(filename) {
    if (!confirm(`คุณต้องการกู้คืนข้อมูลจากจุดสำรอง "${filename}" ใช่หรือไม่?\n(ระบบจะสร้างจุดสำรองข้อมูลปัจจุบันให้อัตโนมัติก่อนกู้คืน)`)) {
        return;
    }

    try {
        showToast(`กำลังกู้คืนข้อมูลจาก ${filename}...`);
        const res = await fetch(`${API_URL}/backup/restore-local`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify({ filename }),
        });
        const data = await res.json();
        if (res.ok && data.ok) {
            showToast('✅ กู้คืนข้อมูลสำเร็จเรียบร้อยแล้ว');
            await loadBackupStats();
            setTimeout(() => { location.reload(); }, 1200);
        } else {
            showToast('❌ กู้คืนไม่สำเร็จ: ' + (data.detail || 'เกิดข้อผิดพลาด'), 'danger');
        }
    } catch (e) {
        showToast('❌ เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'danger');
    }
}

async function deleteLocalBackup(filename) {
    if (!confirm(`ต้องการลบไฟล์สำรองข้อมูล "${filename}" หรือไม่?`)) return;

    try {
        const res = await fetch(`${API_URL}/backup/backups/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            headers: HEADERS,
        });
        const data = await res.json();
        if (res.ok) {
            showToast('🗑️ ลบไฟล์สำรองข้อมูลเรียบร้อย');
            await loadBackupStats();
        } else {
            showToast('❌ ลบไม่สำเร็จ: ' + (data.detail || 'เกิดข้อผิดพลาด'), 'danger');
        }
    } catch (e) {
        showToast('❌ เกิดข้อผิดพลาดในการเชื่อมต่อ', 'danger');
    }
}

function toggleKeyVisibility(inputId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(`eye-${inputId}`);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) icon.setAttribute('data-lucide', 'eye-off');
    } else {
        input.type = 'password';
        if (icon) icon.setAttribute('data-lucide', 'eye');
    }
    if (window.lucide) lucide.createIcons();
}

async function saveAISettings() {
    const geminiKey = document.getElementById('gemini-key-input')?.value.trim();
    const openaiKey = document.getElementById('openai-key-input')?.value.trim();
    const lineToken = document.getElementById('line-token-input')?.value.trim();

    const payload = {};
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (openaiKey) payload.openai_api_key = openaiKey;
    if (lineToken) payload.line_oa_channel_token = lineToken;

    try {
        const res = await fetch(`${API_URL}/settings/`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
            showToast('✅ บันทึกการตั้งค่าระบบเรียบร้อยแล้ว');
            // Clear raw inputs
            if (geminiKey) document.getElementById('gemini-key-input').value = '';
            if (openaiKey) document.getElementById('openai-key-input').value = '';
            if (lineToken) document.getElementById('line-token-input').value = '';
            await loadSettings();
        } else {
            showToast('❌ บันทึกไม่สำเร็จ: ' + (data.detail || 'เกิดข้อผิดพลาด'));
        }
    } catch (e) {
        showToast('❌ ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้');
    }
}

async function testAIConnection(provider) {
    const resultBox = document.getElementById('ai-test-result');
    if (!resultBox) return;

    let key = '';
    if (provider === 'gemini') key = document.getElementById('gemini-key-input')?.value.trim();
    if (provider === 'openai') key = document.getElementById('openai-key-input')?.value.trim();

    resultBox.style.display = 'block';
    resultBox.style.background = 'rgba(30, 41, 59, 0.9)';
    resultBox.style.color = '#94a3b8';
    resultBox.style.border = '1px solid #475569';
    resultBox.innerHTML = `⏳ กำลังทดสอบการเชื่อมต่อ ${provider.toUpperCase()} API...`;

    try {
        const res = await fetch(`${API_URL}/settings/test-ai`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify({ provider: provider, api_key: key || null }),
        });
        const data = await res.json();

        if (res.ok && data.ok) {
            resultBox.style.background = 'rgba(16, 185, 129, 0.15)';
            resultBox.style.color = '#34d399';
            resultBox.style.border = '1px solid rgba(16, 185, 129, 0.4)';
            resultBox.innerHTML = `✅ <strong>${data.message}</strong> (Latency: ${data.latency_ms} ms)`;
            await loadSettings();
        } else {
            resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
            resultBox.style.color = '#f87171';
            resultBox.style.border = '1px solid rgba(239, 68, 68, 0.4)';
            resultBox.innerHTML = `❌ <strong>การเชื่อมต่อไม่สำเร็จ:</strong> ${data.detail || data.message || 'โปรดตรวจสอบความถูกต้องของ API Key'}`;
        }
    } catch (e) {
        resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
        resultBox.style.color = '#f87171';
        resultBox.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        resultBox.innerHTML = `❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์เพื่อทดสอบได้: ${e.message}`;
    }
}

async function testLineConnection() {
    const resultBox = document.getElementById('ai-test-result');
    if (!resultBox) return;

    const token = document.getElementById('line-token-input')?.value.trim();

    resultBox.style.display = 'block';
    resultBox.style.background = 'rgba(30, 41, 59, 0.9)';
    resultBox.style.color = '#94a3b8';
    resultBox.style.border = '1px solid #475569';
    resultBox.innerHTML = `⏳ กำลังตรวจสอบการเชื่อมต่อกับ LINE Messaging API...`;

    try {
        const res = await fetch(`${API_URL}/settings/test-line`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify({ token: token || null }),
        });
        const data = await res.json();

        if (res.ok && data.ok) {
            resultBox.style.background = 'rgba(6, 199, 85, 0.15)';
            resultBox.style.color = '#22c55e';
            resultBox.style.border = '1px solid rgba(6, 199, 85, 0.4)';
            resultBox.innerHTML = `✅ <strong>${data.message}</strong>`;
            await loadSettings();
        } else {
            resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
            resultBox.style.color = '#f87171';
            resultBox.style.border = '1px solid rgba(239, 68, 68, 0.4)';
            resultBox.innerHTML = `❌ <strong>เชื่อมต่อ LINE ไม่สำเร็จ:</strong> ${data.detail || data.message || 'โปรดตรวจสอบ Channel Access Token'}`;
        }
    } catch (e) {
        resultBox.style.background = 'rgba(239, 68, 68, 0.15)';
        resultBox.style.color = '#f87171';
        resultBox.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        resultBox.innerHTML = `❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์เพื่อทดสอบได้: ${e.message}`;
    }
}

function saveSheetUrl() {
    const url = document.getElementById('sheets-url')?.value;
    const status = document.getElementById('sheets-status');
    if (!url) return;
    localStorage.setItem('sheets_webhook_url', url);
    if (status) { status.textContent = '✅ บันทึกเรียบร้อย'; status.style.color = '#34d399'; }
    showToast('✅ บันทึก Google Sheets Webhook เรียบร้อย');
}

// ── AI COPILOT DRAWER & PIPELINE ──────────────────────────────────────────────

function toggleCopilot() {
    const drawer = document.getElementById('ai-copilot-drawer');
    const chevron = document.getElementById('copilot-chevron');
    if (!drawer) return;
    drawer.classList.toggle('collapsed');
    if (chevron) chevron.style.transform = drawer.classList.contains('collapsed') ? 'rotate(0deg)' : 'rotate(180deg)';
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

function renderPipelineTrack(steps) {
    const track = document.getElementById('agent-pipeline-track');
    const meta = document.getElementById('agent-run-meta');
    if (!track) return;

    if (!steps || steps.length === 0) {
        track.innerHTML = '';
        if (meta) meta.textContent = 'Ready';
        return;
    }

    if (meta) meta.textContent = 'Active Execution';
    track.innerHTML = steps.map(s => `
        <div class="pipeline-step ${s.status || 'done'}">
            <span class="step-num">${s.step}</span>
            <span class="step-name">${s.name}</span>
        </div>
    `).join('<i data-lucide="chevron-right" class="step-arrow"></i>');
    if (window.lucide) lucide.createIcons();
}

// ── IMAGE ATTACHMENT & EVENT LISTENERS ──
let attachedChatImage = null; // { dataUrl, filename }

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function handleChatImageSelected(event) {
    const file = event.target && event.target.files && event.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        showToast('กรุณาเลือกไฟล์รูปภาพเท่านั้น');
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        attachedChatImage = {
            dataUrl: e.target.result,
            filename: file.name
        };
        const previewEl = document.getElementById('chat-img-preview-el');
        const filenameEl = document.getElementById('chat-img-filename');
        const wrapEl = document.getElementById('chat-img-preview-wrap');
        if (previewEl) previewEl.src = e.target.result;
        if (filenameEl) filenameEl.textContent = file.name;
        if (wrapEl) wrapEl.style.display = 'flex';
        const input = document.getElementById('chat-input');
        if (input) input.focus();
    };
    reader.readAsDataURL(file);
}

function removeChatAttachedImage() {
    attachedChatImage = null;
    const fileInput = document.getElementById('chat-file-input');
    if (fileInput) fileInput.value = '';
    const previewEl = document.getElementById('chat-img-preview-el');
    if (previewEl) previewEl.src = '';
    const wrapEl = document.getElementById('chat-img-preview-wrap');
    if (wrapEl) wrapEl.style.display = 'none';
}

function initChatImageEvents() {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        // Support paste (Ctrl+V) image directly from clipboard
        chatInput.addEventListener('paste', (e) => {
            const items = e.clipboardData && e.clipboardData.items;
            if (!items) return;
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    const file = items[i].getAsFile();
                    if (file) {
                        const fakeEvent = { target: { files: [file] } };
                        handleChatImageSelected(fakeEvent);
                        e.preventDefault();
                        break;
                    }
                }
            }
        });

        // Press Enter to send (Shift+Enter for newline)
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Drag and drop image files onto copilot drawer
    const dropArea = document.querySelector('.copilot-drawer');
    if (dropArea) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
        dropArea.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                const file = dt.files[0];
                if (file.type.startsWith('image/')) {
                    const fakeEvent = { target: { files: [file] } };
                    handleChatImageSelected(fakeEvent);
                }
            }
        });
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input ? input.value.trim() : '';
    const imgToSend = attachedChatImage;

    // Must have either text or image
    if (!text && !imgToSend) return;

    if (input) input.value = '';
    removeChatAttachedImage();

    const thread = document.getElementById('chat-thread');
    if (!thread) return;

    // Render user message bubble with optional thumbnail
    let userContent = text ? `<div>${escapeHtml(text)}</div>` : '';
    if (imgToSend) {
        userContent += `<div style="margin-top:${text ? '8px' : '0'};">
            <img src="${imgToSend.dataUrl}" class="chat-bubble-img" onclick="viewBillImg(this.src)" title="คลิกเพื่อดูภาพขยาย">
            <span style="font-size:11px;color:#94a3b8;display:block;margin-top:2px;">📎 ${escapeHtml(imgToSend.filename)}</span>
        </div>`;
    }

    thread.innerHTML += `<div class="msg-row user"><div class="bubble user-bubble">${userContent}</div></div>`;
    thread.scrollTop = thread.scrollHeight;

    const botMsgId = `bot-${Date.now()}`;
    thread.innerHTML += `
        <div class="msg-row bot" id="${botMsgId}">
            <div class="avatar-bot"><i data-lucide="cpu"></i></div>
            <div class="bubble bot-bubble">
                <div style="display:flex;align-items:center;gap:8px;color:#94a3b8;">
                    <span class="agent-pulse-dot"></span>
                    <span>${imgToSend ? 'กำลังวิเคราะห์ภาพและประมวลผล R.O.S.E. Copilot...' : 'กำลังเชื่อมต่อฐานข้อมูลและประมวลผล R.O.S.E. Copilot...'}</span>
                </div>
            </div>
        </div>`;
    thread.scrollTop = thread.scrollHeight;
    if (window.lucide) lucide.createIcons();

    // Initial pipeline state
    renderPipelineTrack([
        { step: 1, name: imgToSend ? "Vision Analysis" : "Intent Analysis", status: "active" },
        { step: 2, name: "Live DB Context", status: "pending" },
        { step: 3, name: "ROSE Engine", status: "pending" }
    ]);

    try {
        const payload = {
            message: text || (imgToSend ? "วิเคราะห์รูปภาพนี้เพื่อเปิดใบรับรถหรือบันทึกบิล" : ""),
            image_data: imgToSend ? imgToSend.dataUrl : null,
            image_name: imgToSend ? imgToSend.filename : null
        };

        const res = await fetch(`${API_URL}/chat/`, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        const botMsgEl = document.getElementById(botMsgId);
        if (!res.ok) throw new Error(`API Error ${res.status}`);
        const data = await res.json();

        // Update pipeline visualizer with returned steps
        if (data.pipeline_steps) {
            renderPipelineTrack(data.pipeline_steps);
        } else {
            renderPipelineTrack([
                { step: 1, name: imgToSend ? "Vision Analysis" : "Intent Analysis", status: "done" },
                { step: 2, name: "Live DB Retrieval", status: "done" },
                { step: 3, name: "Response Ready", status: "done" }
            ]);
        }

        // Format markdown response
        let formatted = (data.text || '')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.12);padding:2px 6px;border-radius:4px;color:#a5b4fc;">$1</code>')
            .replace(/\n/g, '<br>');

        // If saved image path returned, show it in bot bubble
        if (data.data && data.data.image_path) {
            formatted += `<div style="margin-top:10px;padding:8px;background:rgba(0,0,0,0.25);border-radius:8px;border:1px solid rgba(255,255,255,0.1);">
                <span style="font-size:11px;color:#94a3b8;display:block;margin-bottom:4px;">📎 ภาพเอกสารที่บันทึกลงระบบ (คลิกดูขยาย):</span>
                <img src="${data.data.image_path}" class="chat-bubble-img" onclick="viewBillImg('${data.data.image_path}')" title="คลิกเพื่อดูภาพขยาย">
            </div>`;
        }

        // Add action shortcuts if applicable
        if (data.type === 'stock') {
            formatted += `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button class="chip" onclick="switchTab('stock')">📦 ไปที่หน้ารายการสต็อก</button>
                <button class="chip" onclick="openAddStockModal()">➕ เพิ่มสินค้าใหม่</button>
            </div>`;
        } else if (data.type === 'ticket') {
            formatted += `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button class="chip" onclick="switchTab('repairs')">📋 ไปที่หน้างานซ่อม (Repairs)</button>
            </div>`;
        } else if (data.type === 'expense') {
            formatted += `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button class="chip" onclick="switchTab('expenses')">💸 ไปที่หน้าค่าใช้จ่าย</button>
            </div>`;
        } else if (data.type === 'appointment') {
            formatted += `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button class="chip" onclick="switchTab('appointments')">📅 ไปที่ปฏิทินนัดหมาย</button>
            </div>`;
        } else if (data.type === 'customer' || data.type === 'vehicle') {
            formatted += `<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button class="chip" onclick="switchTab('customers')">👥 ไปที่หน้าลูกค้า & ข้อมูลรถ</button>
            </div>`;
        }

        botMsgEl.querySelector('.bubble').innerHTML = `<p style="margin:0;line-height:1.6;">${formatted}</p>`;
        thread.scrollTop = thread.scrollHeight;
        if (window.lucide) lucide.createIcons();

        // Refresh underlying datasets dynamically
        if (data.type === 'ticket' && typeof fetchTicketsData === 'function') fetchTicketsData();
        if (data.type === 'stock' && typeof fetchStockData === 'function') fetchStockData();
        if (data.type === 'expense' && typeof loadExpenses === 'function') loadExpenses();
        if ((data.type === 'customer' || data.type === 'vehicle') && typeof fetchCustomersData === 'function') fetchCustomersData();
        if (data.type === 'appointment') {
            if (typeof fetchAppointments === 'function') {
                await fetchAppointments();
            }
            if (typeof renderCalendar === 'function') renderCalendar();
            if (typeof renderDashboardAppointments === 'function') renderDashboardAppointments();
        }
        if (data.type === 'approve_prompt' && data.data?.ticket_id && typeof openApproveModal === 'function') {
            openApproveModal(data.data.ticket_id);
        }

    } catch (err) {
        const botMsgEl = document.getElementById(botMsgId);
        if (botMsgEl) {
            botMsgEl.querySelector('.bubble').innerHTML = `
                <p style="color:#ef4444;margin:0;">
                    ❌ เกิดข้อผิดพลาดในการติดต่อ AI Copilot (${err.message}) กรุณาลองใหม่อีกครั้ง
                </p>`;
        }
        renderPipelineTrack([]);
    }
}

function showToast(msg) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s reverse forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Automatically load settings when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    initCategoryManagement();
});

// ── CATEGORY MANAGEMENT (Expense & Stock) ─────────────────────────────────────
const DEFAULT_EXPENSE_CATS = ['ค่าไฟฟ้า','ค่าน้ำประปา','ค่าเช่า','ค่าอินเทอร์เน็ต','ค่าโทรศัพท์','ค่าน้ำมัน','ค่าอะไหล่','เงินเดือนช่าง','อื่นๆ'];
const DEFAULT_STOCK_CATS   = ['น้ำมันเครื่อง','กรอง','เบรค','ไฟฟ้า','อะไหล่','สารเคมี','ยาง','แบตเตอรี่','อื่นๆ'];

function loadExpenseCats() {
    const saved = localStorage.getItem('expense_categories');
    return saved ? JSON.parse(saved) : [...DEFAULT_EXPENSE_CATS];
}
function saveExpenseCats(cats) {
    localStorage.setItem('expense_categories', JSON.stringify(cats));
}
function loadStockCats() {
    const saved = localStorage.getItem('stock_categories');
    return saved ? JSON.parse(saved) : [...DEFAULT_STOCK_CATS];
}
function saveStockCats(cats) {
    localStorage.setItem('stock_categories', JSON.stringify(cats));
}

function syncDatalist(listId, cats) {
    const dl = document.getElementById(listId);
    if (!dl) return;
    dl.innerHTML = cats.map(c => `<option value="${c}">`).join('');
}

function initCategoryManagement() {
    syncDatalist('expense-cat-list', loadExpenseCats());
    syncDatalist('stock-cat-list', loadStockCats());
    // Pre-fill first value into inputs
    const expCatInput = document.getElementById('expense-cat');
    if (expCatInput && !expCatInput.value) expCatInput.value = '';
    const stoCatInput = document.getElementById('stock-category');
    if (stoCatInput && !stoCatInput.value) stoCatInput.value = '';
}

// ── Manage Expense Categories Modal ──
function openManageExpenseCats() {
    renderExpenseCatsList();
    document.getElementById('manage-expense-cats-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}
function closeManageExpenseCats() {
    document.getElementById('manage-expense-cats-modal').style.display = 'none';
    syncDatalist('expense-cat-list', loadExpenseCats());
}
function renderExpenseCatsList() {
    const cats = loadExpenseCats();
    const container = document.getElementById('expense-cats-list');
    if (!container) return;
    if (!cats.length) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:12px;">ยังไม่มีหมวดหมู่</p>`;
        return;
    }
    container.innerHTML = cats.map((c, i) => `
        <div style="display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:8px 12px;">
            <i data-lucide="tag" style="width:14px;height:14px;color:#a5b4fc;flex-shrink:0;"></i>
            <span style="flex:1;font-size:0.9rem;">${c}</span>
            <button onclick="deleteExpenseCat(${i})" title="ลบ" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#f87171;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:12px;display:flex;align-items:center;gap:3px;"><i data-lucide="trash-2" style="width:12px;height:12px;"></i></button>
        </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
}
function addExpenseCat() {
    const input = document.getElementById('new-expense-cat-input');
    const val = input?.value.trim();
    if (!val) return;
    const cats = loadExpenseCats();
    if (cats.includes(val)) { showToast('⚠️ หมวดหมู่นี้มีอยู่แล้ว'); return; }
    cats.push(val);
    saveExpenseCats(cats);
    input.value = '';
    renderExpenseCatsList();
    showToast(`✅ เพิ่มหมวดหมู่ "${val}" เรียบร้อย`);
}
function deleteExpenseCat(index) {
    const cats = loadExpenseCats();
    const removed = cats.splice(index, 1)[0];
    saveExpenseCats(cats);
    renderExpenseCatsList();
    showToast(`🗑️ ลบหมวดหมู่ "${removed}" แล้ว`);
}

// ── Manage Stock Categories Modal ──
function openManageStockCats() {
    renderStockCatsList();
    document.getElementById('manage-stock-cats-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}
function closeManageStockCats() {
    document.getElementById('manage-stock-cats-modal').style.display = 'none';
    syncDatalist('stock-cat-list', loadStockCats());
}
function renderStockCatsList() {
    const cats = loadStockCats();
    const container = document.getElementById('stock-cats-list');
    if (!container) return;
    if (!cats.length) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:12px;">ยังไม่มีหมวดหมู่</p>`;
        return;
    }
    container.innerHTML = cats.map((c, i) => `
        <div style="display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:8px 12px;">
            <i data-lucide="tag" style="width:14px;height:14px;color:#34d399;flex-shrink:0;"></i>
            <span style="flex:1;font-size:0.9rem;">${c}</span>
            <button onclick="deleteStockCat(${i})" title="ลบ" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#f87171;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:12px;display:flex;align-items:center;gap:3px;"><i data-lucide="trash-2" style="width:12px;height:12px;"></i></button>
        </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
}
function addStockCat() {
    const input = document.getElementById('new-stock-cat-input');
    const val = input?.value.trim();
    if (!val) return;
    const cats = loadStockCats();
    if (cats.includes(val)) { showToast('⚠️ หมวดหมู่นี้มีอยู่แล้ว'); return; }
    cats.push(val);
    saveStockCats(cats);
    input.value = '';
    renderStockCatsList();
    showToast(`✅ เพิ่มหมวดหมู่ "${val}" เรียบร้อย`);
}
function deleteStockCat(index) {
    const cats = loadStockCats();
    const removed = cats.splice(index, 1)[0];
    saveStockCats(cats);
    renderStockCatsList();
    showToast(`🗑️ ลบหมวดหมู่ "${removed}" แล้ว`);
}

// ── PRINT BILL ──────────────────────────────────────────────────────────────────
let _printBillData = null;

function openPrintBill(ticketId) {
    const ticket = allTickets.find(t => t.id === ticketId);
    if (!ticket) { showToast('❌ ไม่พบข้อมูล Ticket'); return; }
    _printBillData = ticket;
    renderPrintBillContent(ticket);
    document.getElementById('print-bill-modal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}
function closePrintBill() {
    document.getElementById('print-bill-modal').style.display = 'none';
    _printBillData = null;
}

function renderPrintBillContent(t) {
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const shopPhone = localStorage.getItem('shop_phone') || '095-418-5332';
    const shopAddress = localStorage.getItem('shop_address') || '';
    const dateStr = t.approved_at
        ? new Date(t.approved_at).toLocaleDateString('th-TH', {year:'numeric',month:'long',day:'numeric'})
        : new Date(t.created_at).toLocaleDateString('th-TH', {year:'numeric',month:'long',day:'numeric'});
    const lineItems = (t.line_items || []);
    const itemsHtml = lineItems.map(item => `
        <tr>
            <td style="padding:7px 10px;border-bottom:1px solid #e5e7eb;">${item.name_th || item.name || '—'}</td>
            <td style="padding:7px 10px;border-bottom:1px solid #e5e7eb;text-align:center;">1</td>
            <td style="padding:7px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">฿${(item.total || item.unit_price || 0).toLocaleString('th-TH')}</td>
        </tr>
    `).join('');
    const labor = t.estimated_labor_cost || 0;
    const total = t.final_cost || t.total_estimated_cost || 0;
    const partsTotal = lineItems.reduce((s, i) => s + (i.total || i.unit_price || 0), 0);

    const content = `
        <div style="text-align:center;margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #111;">
            <div style="font-size:1.5rem;font-weight:800;letter-spacing:0.03em;">${shopName}</div>
            ${shopAddress ? `<div style="font-size:0.85rem;color:#555;margin-top:2px;">${shopAddress}</div>` : ''}
            <div style="font-size:0.85rem;color:#555;">โทร: ${shopPhone}</div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-bottom:16px;font-size:0.88rem;">
            <div>
                <div><strong>ใบแจ้งซ่อม / ใบเสร็จรับเงิน</strong></div>
                <div style="color:#555;">เลขที่: <strong>#${t.id}</strong></div>
            </div>
            <div style="text-align:right;">
                <div>วันที่: <strong>${dateStr}</strong></div>
                <div>สถานะ: <strong>${t.status === 'APPROVED' ? '✅ อนุมัติแล้ว' : t.status}</strong></div>
            </div>
        </div>

        <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:0.87rem;">
            <div style="font-weight:700;margin-bottom:6px;">ข้อมูลรถและลูกค้า</div>
            <div>ทะเบียนรถ: <strong>${t.vehicle_plate || 'ไม่ระบุ'}</strong> &nbsp;|&nbsp; ยี่ห้อ/รุ่น: <strong>${t.car_model || '—'}</strong></div>
            <div>ชื่อลูกค้า: <strong>${t.customer_name || 'ลูกค้าทั่วไป'}</strong></div>
            ${t.mechanic_name ? `<div>ช่าง: <strong>${t.mechanic_name}</strong></div>` : ''}
        </div>

        <table style="width:100%;border-collapse:collapse;font-size:0.87rem;margin-bottom:14px;">
            <thead>
                <tr style="background:#111;color:#fff;">
                    <th style="padding:8px 10px;text-align:left;border-radius:6px 0 0 0;">รายการ</th>
                    <th style="padding:8px 10px;text-align:center;">จำนวน</th>
                    <th style="padding:8px 10px;text-align:right;border-radius:0 6px 0 0;">ราคา</th>
                </tr>
            </thead>
            <tbody>
                ${itemsHtml || '<tr><td colspan="3" style="padding:10px;text-align:center;color:#888;">ไม่มีรายการอะไหล่</td></tr>'}
                ${labor > 0 ? `
                <tr>
                    <td style="padding:7px 10px;border-bottom:1px solid #e5e7eb;">ค่าแรง</td>
                    <td style="padding:7px 10px;text-align:center;border-bottom:1px solid #e5e7eb;">—</td>
                    <td style="padding:7px 10px;text-align:right;border-bottom:1px solid #e5e7eb;">฿${labor.toLocaleString('th-TH')}</td>
                </tr>` : ''}
            </tbody>
        </table>

        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;padding-top:10px;border-top:2px solid #111;font-size:0.9rem;">
            ${partsTotal > 0 ? `<div>ค่าอะไหล่รวม: <strong>฿${partsTotal.toLocaleString('th-TH')}</strong></div>` : ''}
            ${labor > 0 ? `<div>ค่าแรง: <strong>฿${labor.toLocaleString('th-TH')}</strong></div>` : ''}
            <div style="font-size:1.15rem;font-weight:800;border-top:1px solid #ddd;padding-top:6px;margin-top:4px;">
                รวมทั้งสิ้น: ฿${total.toLocaleString('th-TH')}
            </div>
        </div>

        ${t.mechanic_notes ? `<div style="margin-top:14px;padding:10px 14px;background:#fffbeb;border-left:3px solid #f59e0b;border-radius:4px;font-size:0.85rem;"><strong>หมายเหตุช่าง:</strong> ${t.mechanic_notes}</div>` : ''}

        <div style="text-align:center;margin-top:20px;padding-top:14px;border-top:1px solid #e5e7eb;color:#888;font-size:0.78rem;">
            ขอบคุณที่ใช้บริการ — ${shopName}
        </div>
    `;
    document.getElementById('print-bill-content').innerHTML = content;
}

function doPrintBill() {
    const content = document.getElementById('print-bill-content')?.innerHTML;
    if (!content) return;
    const shopName = localStorage.getItem('shop_name') || 'Zero Garage';
    const w = window.open('', '_blank', 'width=720,height=900');
    w.document.write(`<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <title>ใบเสร็จ — ${shopName}</title>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700;800&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Sarabun', Arial, sans-serif; background: #fff; color: #111; padding: 32px; max-width: 680px; margin: 0 auto; }
    @media print {
      body { padding: 10mm 15mm; }
      button { display: none !important; }
    }
  </style>
</head>
<body>
  <div style="position:fixed;top:16px;right:16px;display:flex;gap:8px;">
    <button onclick="window.print()" style="background:#111;color:#fff;border:none;border-radius:6px;padding:8px 18px;cursor:pointer;font-size:14px;font-family:inherit;">🖨️ พิมพ์ / PDF</button>
    <button onclick="window.close()" style="background:#eee;color:#111;border:none;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:14px;font-family:inherit;">✕ ปิด</button>
  </div>
  ${content}
</body>
</html>`);
    w.document.close();
    setTimeout(() => { try { w.focus(); } catch(e){} }, 300);
}

// ── DANGER ZONE: WIPE ALL DATA ──
function openWipeConfirmModal() {
    const input = document.getElementById('wipe-confirm-input');
    if (input) input.value = '';
    const btn = document.getElementById('btn-execute-wipe');
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.4';
        btn.style.cursor = 'not-allowed';
    }
    const spinner = document.getElementById('wipe-progress-spinner');
    if (spinner) spinner.style.display = 'none';

    const modal = document.getElementById('wipe-confirm-modal');
    if (modal) {
        modal.style.display = 'flex';
        if (window.lucide) lucide.createIcons();
        setTimeout(() => input?.focus(), 100);
    }
}

function closeWipeConfirmModal() {
    const modal = document.getElementById('wipe-confirm-modal');
    if (modal) modal.style.display = 'none';
}

function checkWipeConfirmationInput() {
    const val = (document.getElementById('wipe-confirm-input')?.value || '').trim().toUpperCase();
    const btn = document.getElementById('btn-execute-wipe');
    if (!btn) return;
    const isValid = val === 'DELETE' || val === 'ล้างข้อมูล';
    btn.disabled = !isValid;
    btn.style.opacity = isValid ? '1' : '0.4';
    btn.style.cursor = isValid ? 'pointer' : 'not-allowed';
}

async function executeWipeAllData() {
    const input = document.getElementById('wipe-confirm-input');
    const val = (input?.value || '').trim().toUpperCase();
    if (val !== 'DELETE' && val !== 'ล้างข้อมูล') {
        return alert('กรุณาพิมพ์คำว่า DELETE หรือ ล้างข้อมูล เพื่อยืนยัน');
    }

    const btn = document.getElementById('btn-execute-wipe');
    const spinner = document.getElementById('wipe-progress-spinner');
    if (btn) btn.disabled = true;
    if (spinner) spinner.style.display = 'block';

    try {
        const res = await fetch(`${API_URL}/backup/wipe-all-data`, {
            method: 'POST',
            headers: HEADERS
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(_apiErrorText(err, 'เกิดข้อผิดพลาดในการล้างข้อมูล'));
        }

        const data = await res.json();
        closeWipeConfirmModal();

        const backupNote = data.safety_backup ? `\n(สร้างจุดสำรองข้อมูลไว้ที่: ${data.safety_backup})` : '';
        alert(`✅ ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว!${backupNote}`);

        // Reload data across all modules
        await Promise.allSettled([
            fetchTicketsData(),
            fetchStockData(),
            fetchCustomersData(),
            loadSuppliers(),
            fetchAppointments(),
            loadExpenses(),
            loadBackupStats()
        ]);

        if (typeof renderDashboardKPIs === 'function') renderDashboardKPIs();
        showToast('🗑️ ล้างข้อมูลระบบเสร็จสิ้น และอัปเดตหน้าจอเรียบร้อยแล้ว');
    } catch (e) {
        alert(e.message || 'เกิดข้อผิดพลาดในการล้างข้อมูล');
    } finally {
        if (spinner) spinner.style.display = 'none';
        if (btn) btn.disabled = false;
    }
}

// Explicit window bindings to guarantee global accessibility
window.openWipeConfirmModal = openWipeConfirmModal;
window.closeWipeConfirmModal = closeWipeConfirmModal;
window.checkWipeConfirmationInput = checkWipeConfirmationInput;
window.executeWipeAllData = executeWipeAllData;
window.openSupplierDetailModal = openSupplierDetailModal;
window.closeSupplierDetailModal = closeSupplierDetailModal;
window.openAddPurchaseModalForSupplierId = openAddPurchaseModalForSupplierId;
window.deleteSupplier = deleteSupplier;
window.deleteStockItem = deleteStockItem;
window.deleteAppointment = deleteAppointment;
window.quickAdjustStock = quickAdjustStock;
window.handleStockSearchInput = handleStockSearchInput;
window.handleStockSearchKeydown = handleStockSearchKeydown;
window.selectStockItem = selectStockItem;
window.clearStockSearch = clearStockSearch;
window.setStockCategory = setStockCategory;
window.closeStockSearchDropdown = closeStockSearchDropdown;
window.openEditExpenseModal = openEditExpenseModal;
window.closeEditExpenseModal = closeEditExpenseModal;
window.saveEditExpense = saveEditExpense;
window.openEditStockModal = openEditStockModal;
window.closeEditStockModal = closeEditStockModal;
window.saveEditStock = saveEditStock;
window.viewStockCurrentBill = viewStockCurrentBill;
window.openEditSupplierModal = openEditSupplierModal;
window.closeSupplierModal = closeSupplierModal;
window.submitSupplier = submitSupplier;
window.openEditPurchaseModal = openEditPurchaseModal;
window.closeEditPurchaseModal = closeEditPurchaseModal;
window.saveEditPurchase = saveEditPurchase;
window.viewEditPurchaseCurrentBill = viewEditPurchaseCurrentBill;
window.deleteExpense = deleteExpense;
window.deletePurchaseBill = deletePurchaseBill;
window.viewBillImg = viewBillImg;
window.closeBillImg = closeBillImg;
