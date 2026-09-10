document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    
    // Check URL parameters for ?plate= or ?id=
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
            <p style="margin-top:12px; color: var(--text-secondary);">กำลังค้นหาข้อมูลงานซ่อม...</p>
        </div>
    `;
    lucide.createIcons();

    try {
        const res = await fetch(`/api/v1/tickets/track/${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('Search request failed');
        const tickets = await res.json();

        if (!tickets || tickets.length === 0) {
            resultsArea.innerHTML = `
                <div class="ticket-card" style="text-align:center; padding: 40px;">
                    <i data-lucide="alert-circle" style="width:48px;height:48px;color:#f59e0b;margin-bottom:12px;"></i>
                    <h3>ไม่พบข้อมูลงานซ่อมสำหรับ "${query}"</h3>
                    <p style="color:var(--text-secondary); margin-top:8px;">โปรดตรวจสอบเลขทะเบียนรถยนต์ หรือ หมายเลข Ticket ให้ถูกต้อง</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        renderTickets(tickets);
    } catch (err) {
        resultsArea.innerHTML = `
            <div class="ticket-card" style="text-align:center; padding: 40px;">
                <i data-lucide="x-circle" style="width:48px;height:48px;color:#ef4444;margin-bottom:12px;"></i>
                <h3>เกิดข้อผิดพลาดในการเชื่อมต่อ</h3>
                <p style="color:var(--text-secondary); margin-top:8px;">${err.message}</p>
            </div>
        `;
        lucide.createIcons();
    }
}

function renderTickets(tickets) {
    const resultsArea = document.getElementById('results-area');
    resultsArea.innerHTML = tickets.map(t => {
        const isApproved = t.status === 'APPROVED';
        const isPending = t.status === 'PENDING_MECHANIC_APPROVAL';
        
        let statusBadge = '';
        if (isApproved) {
            statusBadge = `<span class="status-badge approved"><i data-lucide="check-circle-2"></i> อนุมัติซ่อมเรียบร้อย</span>`;
        } else if (isPending) {
            statusBadge = `<span class="status-badge pending"><i data-lucide="clock"></i> รอช่างอนุมัติประเมินราคา</span>`;
        } else {
            statusBadge = `<span class="status-badge pending"><i data-lucide="info"></i> ${t.status}</span>`;
        }

        // Timeline steps status
        const step1Class = 'completed'; // Received
        const step2Class = 'completed'; // Diagnosed
        const step3Class = isApproved ? 'completed' : 'active'; // Approval/Repair
        const step4Class = isApproved ? 'active' : ''; // Completion

        const lineItemsHTML = (t.line_items || []).map(item => `
            <li>
                <span>${item.name_th || item.name}</span>
                <span>฿${(item.total || item.unit_price || 0).toLocaleString()}</span>
            </li>
        `).join('') || '<li><span>ไม่มีรายการอะไหล่</span><span>—</span></li>';

        const diagnosedHTML = (t.diagnosed_issues || []).map(d => `
            <li style="color:#93c5fd">
                <span>• ${d.system || ''}: ${d.issue || ''}</span>
                <small style="color:var(--text-muted)">(${d.severity || 'ปานกลาง'})</small>
            </li>
        `).join('') || '<li style="color:var(--text-muted)">ไม่มีรายการข้อบกพร่องที่ระบุ</li>';

        return `
            <div class="ticket-card">
                <div class="ticket-header">
                    <div>
                        <div class="ticket-id">Ticket #${t.id}</div>
                        <div class="ticket-plate">🚘 ${t.vehicle_plate || 'ไม่ระบุทะเบียน'} — ${t.car_model || ''}</div>
                        <div style="font-size:0.85rem; color:var(--text-muted); margin-top:4px;">เจ้าของรถ: ${t.customer_name || 'ลูกค้าทั่วไป'} | วันที่รับบริการ: ${new Date(t.created_at).toLocaleDateString('th-TH')}</div>
                    </div>
                    <div>${statusBadge}</div>
                </div>

                <!-- Live Timeline -->
                <div class="timeline">
                    <div class="timeline-step ${step1Class}">
                        <div class="step-icon"><i data-lucide="clipboard-check"></i></div>
                        <div class="step-label">1. รับรถเข้าศูนย์</div>
                    </div>
                    <div class="timeline-step ${step2Class}">
                        <div class="step-icon"><i data-lucide="cpu"></i></div>
                        <div class="step-label">2. AI ประเมินอาการ</div>
                    </div>
                    <div class="timeline-step ${step3Class}">
                        <div class="step-icon"><i data-lucide="wrench"></i></div>
                        <div class="step-label">3. ช่างดำเนินการซ่อม</div>
                    </div>
                    <div class="timeline-step ${step4Class}">
                        <div class="step-icon"><i data-lucide="flag"></i></div>
                        <div class="step-label">4. ซ่อมเสร็จพร้อมส่งมอบ</div>
                    </div>
                </div>

                <!-- Detail Blocks -->
                <div class="detail-grid">
                    <div class="detail-block">
                        <h4><i data-lucide="search"></i> ผลการวิเคราะห์จากระบบ AI</h4>
                        <p style="font-size:0.88rem; color:var(--text-secondary); margin-bottom:10px;">
                            <strong>อาการที่ได้รับแจ้ง:</strong> "${t.raw_input}"
                        </p>
                        <ul class="item-list">
                            ${diagnosedHTML}
                        </ul>
                    </div>

                    <div class="detail-block">
                        <h4><i data-lucide="receipt"></i> รายการเสนอราคาและค่าบริการ</h4>
                        <ul class="item-list">
                            ${lineItemsHTML}
                            <li>
                                <span>ค่าแรงประเมิน</span>
                                <span>฿${(t.estimated_labor_cost || 0).toLocaleString()}</span>
                            </li>
                        </ul>
                        <div class="total-cost">
                            ราคารวมทั้งสิ้น: ฿${(t.final_cost || t.total_estimated_cost || 0).toLocaleString()}
                        </div>
                    </div>
                </div>

                ${t.mechanic_notes ? `
                    <div style="margin-top:16px; padding:12px; background:rgba(59, 130, 246, 0.1); border-left:4px solid #3b82f6; border-radius:4px; font-size:0.9rem;">
                        <strong><i data-lucide="user-check"></i> บันทึกจากช่างผู้เชี่ยวชาญ:</strong> ${t.mechanic_notes}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    lucide.createIcons();
}
