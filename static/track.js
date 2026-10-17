let trackLang = localStorage.getItem('track_lang') || 'th';

const TRACK_TEXTS = {
    th: {
        brand_sub: "ระบบเช็คสถานะงานซ่อมรถยนต์ออนไลน์",
        search_title: "ค้นหาสถานะงานซ่อมของคุณ",
        search_desc: "กรอกเลขทะเบียนรถยนต์ (เช่น <code>กข 1234 กรุงเทพ</code>) หรือ หมายเลข Ticket ID",
        search_placeholder: "พิมพ์เลขทะเบียนรถ หรือ เลข Ticket...",
        search_btn: "ค้นหา",
        sample_title: "ตัวอย่างทะเบียนในระบบ:",
        searching: "กำลังค้นหาข้อมูลงานซ่อม...",
        not_found_title: "ไม่พบข้อมูลงานซ่อมสำหรับ",
        not_found_sub: "โปรดตรวจสอบเลขทะเบียนรถยนต์ หรือ หมายเลข Ticket ให้ถูกต้อง",
        error_title: "เกิดข้อผิดพลาดในการเชื่อมต่อ",
        step1: "1. รับรถเข้าศูนย์",
        step2: "2. AI ประเมินอาการ",
        step3: "3. ช่างดำเนินการซ่อม",
        step4: "4. ซ่อมเสร็จพร้อมส่งมอบ",
        status_approved: "อนุมัติซ่อมเรียบร้อย",
        status_pending: "รอช่างอนุมัติประเมินราคา",
        owner_prefix: "เจ้าของรถ:",
        walkin: "ลูกค้าทั่วไป",
        date_prefix: "วันที่รับบริการ:",
        unspec_plate: "ไม่ระบุทะเบียน",
        ai_diag_title: "ผลการวิเคราะห์จากระบบ AI",
        reported_sym: "อาการที่ได้รับแจ้ง:",
        items_title: "รายการเสนอราคาและค่าบริการ",
        labor_cost: "ค่าแรงประเมิน",
        total_cost: "ราคารวมทั้งสิ้น:",
        mech_notes: "บันทึกจากช่างผู้เชี่ยวชาญ:",
        no_parts: "ไม่มีรายการอะไหล่",
        no_issues: "ไม่มีรายการข้อบกพร่องที่ระบุ",
        footer: "© 2026 Zero Garage Command Center — ระบบติดตามสถานะงานซ่อม"
    },
    en: {
        brand_sub: "Real-time Online Vehicle Repair Status Tracker",
        search_title: "Track Your Repair Order",
        search_desc: "Enter license plate number (e.g. <code>กข 1234</code>) or Ticket ID",
        search_placeholder: "Type license plate or Ticket ID...",
        search_btn: "Search",
        sample_title: "Sample plates in system:",
        searching: "Searching for repair order status...",
        not_found_title: "No repair orders found for",
        not_found_sub: "Please verify license plate number or Ticket ID and try again",
        error_title: "Connection Error",
        step1: "1. Vehicle Received",
        step2: "2. AI Diagnosis",
        step3: "3. Repair in Progress",
        step4: "4. Ready for Delivery",
        status_approved: "Approved & In Repair",
        status_pending: "Awaiting Mechanic Approval",
        owner_prefix: "Vehicle Owner:",
        walkin: "General Walk-in",
        date_prefix: "Service Date:",
        unspec_plate: "Unspecified Plate",
        ai_diag_title: "AI Diagnostic Analysis",
        reported_sym: "Reported Complaint:",
        items_title: "Parts & Labor Summary",
        labor_cost: "Estimated Labor",
        total_cost: "Total Amount:",
        mech_notes: "Technician Notes:",
        no_parts: "No parts items",
        no_issues: "No specific defects diagnosed",
        footer: "© 2026 Zero Garage Command Center — Public Repair Tracker"
    }
};

function tt(key) {
    const dict = TRACK_TEXTS[trackLang] || TRACK_TEXTS.th;
    return dict[key] !== undefined ? dict[key] : key;
}

function setTrackLanguage(lang) {
    trackLang = lang;
    localStorage.setItem('track_lang', lang);
    document.documentElement.lang = lang;

    const btnTh = document.getElementById('track-lang-th');
    const btnEn = document.getElementById('track-lang-en');
    if (btnTh && btnEn) {
        if (lang === 'th') {
            btnTh.classList.add('active');
            btnTh.style.color = '#fff';
            btnEn.classList.remove('active');
            btnEn.style.color = 'var(--text-muted)';
        } else {
            btnEn.classList.add('active');
            btnEn.style.color = '#fff';
            btnTh.classList.remove('active');
            btnTh.style.color = 'var(--text-muted)';
        }
    }

    // Update static strings
    const brandP = document.querySelector('.brand p');
    if (brandP) brandP.innerText = tt('brand_sub');

    const cardH2 = document.querySelector('.search-card h2');
    if (cardH2) cardH2.innerHTML = `<i data-lucide="search"></i> ${tt('search_title')}`;

    const cardP = document.querySelector('.search-card p');
    if (cardP) cardP.innerHTML = tt('search_desc');

    const input = document.getElementById('track-input');
    if (input) input.placeholder = tt('search_placeholder');

    const btnSearch = document.getElementById('btn-search');
    if (btnSearch) btnSearch.innerHTML = `<i data-lucide="arrow-right"></i> ${tt('search_btn')}`;

    const tagSpan = document.querySelector('.quick-tags span');
    if (tagSpan) tagSpan.innerText = tt('sample_title');

    const footerP = document.querySelector('.track-footer p');
    if (footerP) footerP.innerText = tt('footer');

    if (window.lucide) lucide.createIcons();

    // Re-render if results already displayed
    if (window.lastTrackTickets && window.lastTrackTickets.length > 0) {
        renderTickets(window.lastTrackTickets);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTrackLanguage(trackLang);
    lucide.createIcons();
    
    // Check URL parameters for ?plate=, ?id=, or ?q=
    const urlParams = new URLSearchParams(window.location.search);
    const queryParam = urlParams.get('q') || urlParams.get('plate') || urlParams.get('id');
    if (queryParam) {
        document.getElementById('track-input').value = queryParam;
        performTrack();
    }
    
    // Enter key handler
    document.getElementById('track-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performTrack();
    });
});

function quickSearch(val) {
    document.getElementById('track-input').value = val;
    performTrack();
}

async function performTrack() {
    const query = document.getElementById('track-input').value.trim();
    const resultsArea = document.getElementById('results-area');
    if (!query) return;

    resultsArea.style.display = 'block';
    resultsArea.innerHTML = `
        <div class="ticket-card" style="text-align:center; padding: 40px;">
            <div class="spinner"><i data-lucide="loader-2" class="spin"></i></div>
            <p style="margin-top:12px; color: var(--text-secondary);">${tt('searching')}</p>
        </div>
    `;
    lucide.createIcons();

    try {
        const res = await fetch(`/api/v1/tickets/track/${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('Search request failed');
        const tickets = await res.json();

        if (!tickets || tickets.length === 0) {
            window.lastTrackTickets = [];
            resultsArea.innerHTML = `
                <div class="ticket-card" style="text-align:center; padding: 40px;">
                    <i data-lucide="alert-circle" style="width:48px;height:48px;color:#f59e0b;margin-bottom:12px;"></i>
                    <h3>${tt('not_found_title')} "${escapeHtml(query)}"</h3>
                    <p style="color:var(--text-secondary); margin-top:8px;">${tt('not_found_sub')}</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        window.lastTrackTickets = tickets;
        renderTickets(tickets);
    } catch (err) {
        window.lastTrackTickets = [];
        resultsArea.innerHTML = `
            <div class="ticket-card" style="text-align:center; padding: 40px;">
                <i data-lucide="x-circle" style="width:48px;height:48px;color:#ef4444;margin-bottom:12px;"></i>
                <h3>${tt('error_title')}</h3>
                <p style="color:var(--text-secondary); margin-top:8px;">${err.message}</p>
            </div>
        `;
        lucide.createIcons();
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function renderTickets(tickets) {
    const resultsArea = document.getElementById('results-area');
    const isEn = trackLang === 'en';

    resultsArea.innerHTML = tickets.map(t => {
        const isApproved = t.status === 'APPROVED';
        const isPending = t.status === 'PENDING_MECHANIC_APPROVAL';
        
        let statusBadge = '';
        if (isApproved) {
            statusBadge = `<span class="status-badge approved"><i data-lucide="check-circle-2"></i> ${tt('status_approved')}</span>`;
        } else if (isPending) {
            statusBadge = `<span class="status-badge pending"><i data-lucide="clock"></i> ${tt('status_pending')}</span>`;
        } else {
            statusBadge = `<span class="status-badge pending"><i data-lucide="info"></i> ${t.status}</span>`;
        }

        // Timeline steps status
        const step1Class = 'completed'; // Received
        const step2Class = 'completed'; // Diagnosed
        const step3Class = isApproved ? 'completed' : 'active'; // Approval/Repair
        const step4Class = (t.status === 'COMPLETED' || t.status === 'DELIVERED') ? 'completed' : (isApproved ? 'active' : '');

        const lineItemsHTML = (t.line_items || []).map(item => `
            <li>
                <span>${(isEn && item.name) ? item.name : (item.name_th || item.name)}</span>
                <span>฿${(item.total || item.unit_price || 0).toLocaleString()}</span>
            </li>
        `).join('') || `<li><span>${tt('no_parts')}</span><span>—</span></li>`;

        const diagnosedHTML = (t.diagnosed_issues || []).map(d => `
            <li style="color:#93c5fd">
                <span>• ${d.system || ''}: ${d.issue || ''}</span>
                <small style="color:var(--text-muted)">(${d.severity || (isEn ? 'Medium' : 'ปานกลาง')})</small>
            </li>
        `).join('') || `<li style="color:var(--text-muted)">${tt('no_issues')}</li>`;

        const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString(isEn ? 'en-US' : 'th-TH') : '—';

        return `
            <div class="ticket-card">
                <div class="ticket-header">
                    <div>
                        <div class="ticket-id">Ticket #${t.id}</div>
                        <div class="ticket-plate">🚘 ${t.vehicle_plate || tt('unspec_plate')} — ${t.car_model || ''}</div>
                        <div style="font-size:0.85rem; color:var(--text-muted); margin-top:4px;">${tt('owner_prefix')} ${t.customer_name || tt('walkin')} | ${tt('date_prefix')} ${dateStr}</div>
                    </div>
                    <div>${statusBadge}</div>
                </div>

                <!-- Live Timeline -->
                <div class="timeline">
                    <div class="timeline-step ${step1Class}">
                        <div class="step-icon"><i data-lucide="clipboard-check"></i></div>
                        <div class="step-label">${tt('step1')}</div>
                    </div>
                    <div class="timeline-step ${step2Class}">
                        <div class="step-icon"><i data-lucide="cpu"></i></div>
                        <div class="step-label">${tt('step2')}</div>
                    </div>
                    <div class="timeline-step ${step3Class}">
                        <div class="step-icon"><i data-lucide="wrench"></i></div>
                        <div class="step-label">${tt('step3')}</div>
                    </div>
                    <div class="timeline-step ${step4Class}">
                        <div class="step-icon"><i data-lucide="flag"></i></div>
                        <div class="step-label">${tt('step4')}</div>
                    </div>
                </div>

                <!-- Detail Blocks -->
                <div class="detail-grid">
                    <div class="detail-block">
                        <h4><i data-lucide="search"></i> ${tt('ai_diag_title')}</h4>
                        <p style="font-size:0.88rem; color:var(--text-secondary); margin-bottom:10px;">
                            <strong>${tt('reported_sym')}</strong> "${escapeHtml(t.raw_input)}"
                        </p>
                        <ul class="item-list">
                            ${diagnosedHTML}
                        </ul>
                    </div>

                    <div class="detail-block">
                        <h4><i data-lucide="receipt"></i> ${tt('items_title')}</h4>
                        <ul class="item-list">
                            ${lineItemsHTML}
                            <li>
                                <span>${tt('labor_cost')}</span>
                                <span>฿${(t.estimated_labor_cost || 0).toLocaleString()}</span>
                            </li>
                        </ul>
                        <div class="total-cost">
                            ${tt('total_cost')} ฿${(t.final_cost || t.total_estimated_cost || 0).toLocaleString()}
                        </div>
                    </div>
                </div>

                ${t.mechanic_notes ? `
                    <div style="margin-top:16px; padding:12px; background:rgba(59, 130, 246, 0.1); border-left:4px solid #3b82f6; border-radius:4px; font-size:0.9rem;">
                        <strong><i data-lucide="user-check"></i> ${tt('mech_notes')}</strong> ${escapeHtml(t.mechanic_notes)}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    lucide.createIcons();
}
