// ── Zero Garage — features.js ──
// Payments, customer approval link, warranty, job photos, reorder list, barcode labels,
// shop settings, automatic backup status and the daily-close / job-profit / outstanding reports.
// Loaded before chat.js; uses API_URL, HEADERS, showToast, allTickets, allStock from chat.js at run time.

const FX_METHODS = [['เงินสด', '💵 เงินสด'], ['โอน', '📱 โอน / พร้อมเพย์'], ['บัตร', '💳 บัตร']];
let fxShop = {};  // shop settings shared by every computer

function fxEsc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function fxBaht(n) {
    return '฿' + (Number(n) || 0).toLocaleString('th-TH', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}
async function fxJson(res) {
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof _apiErrorText === 'function' ? _apiErrorText(body) : (body.detail || res.status));
    return body;
}

// Generic modal built on the app's own modal classes
function fxModal(id, title, bodyHtml, width = 620) {
    let el = document.getElementById(id);
    if (!el) {
        el = document.createElement('div');
        el.id = id;
        el.className = 'modal-backdrop';
        el.addEventListener('click', e => { if (e.target === el) el.style.display = 'none'; });
        document.body.appendChild(el);
    }
    el.innerHTML = `<div class="modal-box" style="width:min(${width}px,96vw);max-height:92vh;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px;">
            <h3 style="margin:0;">${title}</h3>
            <button type="button" class="btn-cancel" style="padding:6px 12px;" onclick="document.getElementById('${id}').style.display='none'">✕</button>
        </div>
        ${bodyHtml}
    </div>`;
    el.style.display = 'flex';
    if (window.lucide) lucide.createIcons();
    return el;
}

// ═══ Shop settings ═══════════════════════════════════════════════════════════
async function fxLoadShopSettings() {
    try {
        fxShop = await fxJson(await fetch(`${API_URL}/settings/shop`, { headers: HEADERS }));
        // Keep the old per-browser print header in step with the shared one
        ['shop_name', 'shop_phone', 'shop_address'].forEach(k => {
            if (fxShop[k]) { try { localStorage.setItem(k, fxShop[k]); } catch {} }
        });
    } catch (e) { console.warn('shop settings', e); }
    fxFillSettingsForm();
    return fxShop;
}

function fxFillSettingsForm() {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
    set('fx-tax-id', fxShop.shop_tax_id);
    set('fx-commission', fxShop.commission_pct);
    set('fx-public-url', fxShop.public_base_url);
    set('fx-backup-dir', fxShop.backup_extra_dir);
    const vat = document.getElementById('fx-vat');
    if (vat) vat.checked = fxShop.vat_registered === '1';
}

async function fxSaveShopSettings() {
    const val = id => document.getElementById(id)?.value.trim() ?? '';
    const updates = {
        shop_tax_id: val('fx-tax-id').replace(/-/g, ''),
        vat_registered: document.getElementById('fx-vat')?.checked ? '1' : '0',
        commission_pct: val('fx-commission') || '0',
        public_base_url: val('fx-public-url'),
        backup_extra_dir: val('fx-backup-dir'),
        shop_name: document.getElementById('settings-shop-name')?.value.trim() || fxShop.shop_name,
        shop_phone: document.getElementById('settings-shop-phone')?.value.trim() || '',
        shop_address: document.getElementById('settings-shop-address')?.value.trim() || '',
    };
    try {
        fxShop = await fxJson(await fetch(`${API_URL}/settings/shop`, { method: 'PUT', headers: HEADERS, body: JSON.stringify(updates) }));
        showToast('✅ บันทึกการตั้งค่าร้านเรียบร้อย (ใช้ร่วมกันทุกเครื่อง)');
        fxLoadBackupStatus();
    } catch (e) { showToast('❌ ' + e.message); }
}

// ═══ 1. Payments ══════════════════════════════════════════════════════════════
function fxPaymentBadge(t) {
    if (!t || !['APPROVED', 'IN_PROGRESS', 'COMPLETED'].includes(t.status)) return '';
    const map = {
        paid: ['✓ ชำระครบ', '#34d399', 'rgba(52,211,153,0.12)'],
        partial: [`ค้าง ${fxBaht(t.balance_due)}`, '#fbbf24', 'rgba(251,191,36,0.12)'],
        unpaid: [`ยังไม่ชำระ`, '#f87171', 'rgba(248,113,113,0.12)'],
    };
    const m = map[t.payment_status];
    if (!m) return '';
    return `<div style="margin-top:3px;"><span onclick="fxOpenPayments(${t.id})" style="cursor:pointer;font-size:0.72rem;font-weight:700;color:${m[1]};background:${m[2]};border:1px solid ${m[1]}55;border-radius:999px;padding:1px 8px;white-space:nowrap;" title="คลิกเพื่อรับเงิน / ดูประวัติ">${m[0]}</span></div>`;
}

function fxDecisionBadge(t) {
    if (!t) return '';
    if (t.customer_decision === 'approved') return `<div style="margin-top:3px;font-size:0.72rem;color:#34d399;">📲 ลูกค้าอนุมัติแล้ว</div>`;
    if (t.customer_decision === 'declined') return `<div style="margin-top:3px;font-size:0.72rem;color:#f87171;" title="${fxEsc(t.customer_decision_note || '')}">📲 ลูกค้าไม่อนุมัติ${t.customer_decision_note ? ' — ' + fxEsc(t.customer_decision_note) : ''}</div>`;
    if (t.approval_link_sent && ['PENDING_MECHANIC_APPROVAL', 'DRAFT_ESTIMATE'].includes(t.status)) return `<div style="margin-top:3px;font-size:0.72rem;color:#93c5fd;">📲 รอลูกค้าตอบ</div>`;
    return '';
}

function fxTicketExtraButtons(t) {
    let html = '';
    if (['APPROVED', 'IN_PROGRESS', 'COMPLETED'].includes(t.status)) {
        html += `<button class="btn-sm" style="background:rgba(52,211,153,0.12);border:1px solid rgba(52,211,153,0.35);color:#34d399;" onclick="fxOpenPayments(${t.id})" title="รับเงิน / มัดจำ">💵 รับเงิน</button>`;
    }
    if (['PENDING_MECHANIC_APPROVAL', 'DRAFT_ESTIMATE'].includes(t.status)) {
        html += `<button class="btn-sm" style="background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.35);color:#4ade80;" onclick="fxRequestApproval(${t.id})" title="ส่งใบเสนอราคาให้ลูกค้ากดอนุมัติทาง LINE">📲 ส่งลูกค้าอนุมัติ</button>`;
    }
    return html;
}

async function fxOpenPayments(ticketId) {
    let d;
    try { d = await fxJson(await fetch(`${API_URL}/payments/ticket/${ticketId}`, { headers: HEADERS })); }
    catch (e) { return showToast('❌ ' + e.message); }
    const t = (typeof allTickets !== 'undefined' ? allTickets : []).find(x => x.id === ticketId) || {};
    const rows = d.payments.map(p => `
        <tr>
            <td style="font-size:0.8rem;color:var(--text-muted);">${p.paid_at ? new Date(p.paid_at).toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'short' }) : ''}</td>
            <td>${fxEsc(p.method)}</td>
            <td style="font-size:0.8rem;">${fxEsc(p.note || '')}</td>
            <td style="text-align:right;font-weight:700;color:#34d399;">${fxBaht(p.amount)}</td>
            <td style="text-align:right;"><button class="btn-sm" style="color:#f87171;" onclick="fxDeletePayment(${p.id}, ${ticketId})" title="ลบรายการนี้">✕</button></td>
        </tr>`).join('') || `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:12px;">ยังไม่มีการรับเงิน</td></tr>`;
    const statusTxt = { paid: '✅ ชำระครบแล้ว', partial: '🟡 ชำระบางส่วน', unpaid: '🔴 ยังไม่ชำระ', none: '—' }[d.payment_status] || d.payment_status;
    fxModal('fx-pay-modal', `💵 รับเงิน — งานซ่อม #${ticketId} ${t.vehicle_plate ? '(' + fxEsc(t.vehicle_plate) + ')' : ''}`, `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;">
            <div class="report-kpi-card"><div class="report-kpi-label">ยอดที่ต้องชำระ</div><div class="report-kpi-val">${fxBaht(d.amount_due)}</div></div>
            <div class="report-kpi-card"><div class="report-kpi-label">รับแล้ว</div><div class="report-kpi-val green">${fxBaht(d.amount_paid)}</div></div>
            <div class="report-kpi-card"><div class="report-kpi-label">คงค้าง</div><div class="report-kpi-val" style="color:${d.balance_due > 0 ? '#fbbf24' : '#34d399'};">${fxBaht(d.balance_due)}</div></div>
        </div>
        <div style="margin-bottom:10px;font-weight:600;">${statusTxt}</div>
        <div class="table-responsive"><table class="data-table"><thead><tr><th>วันเวลา</th><th>วิธี</th><th>หมายเหตุ</th><th style="text-align:right;">จำนวน</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
        ${d.balance_due > 0 ? `
        <div style="margin-top:14px;padding:12px;border:1px solid rgba(52,211,153,0.3);border-radius:10px;background:rgba(52,211,153,0.06);">
            <div style="font-weight:700;margin-bottom:8px;">รับเงินเพิ่ม</div>
            <div class="form-row-2">
                <div class="form-group"><label>จำนวนเงิน (บาท)</label>
                    <div style="display:flex;gap:6px;"><input type="number" id="fx-pay-amount" class="form-input" min="0" step="0.01" value="${d.balance_due}">
                    <button type="button" class="btn-sm" onclick="document.getElementById('fx-pay-amount').value=${d.balance_due}" title="ใส่ยอดคงค้างทั้งหมด">เต็มจำนวน</button></div></div>
                <div class="form-group"><label>ชำระโดย</label>
                    <select id="fx-pay-method" class="form-input">${FX_METHODS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
            </div>
            <div class="form-group"><label>หมายเหตุ</label><input type="text" id="fx-pay-note" class="form-input" maxlength="300" placeholder="เช่น มัดจำค่าอะไหล่ / ชำระส่วนที่เหลือ"></div>
            <div class="modal-actions"><button class="btn-primary" onclick="fxSubmitPayment(${ticketId})">💾 บันทึกรับเงิน</button></div>
        </div>` : ''}
    `);
}

async function fxSubmitPayment(ticketId) {
    const amount = parseFloat(document.getElementById('fx-pay-amount')?.value);
    if (!(amount > 0)) return showToast('⚠️ กรุณากรอกจำนวนเงิน');
    try {
        await fxJson(await fetch(`${API_URL}/payments/ticket/${ticketId}`, {
            method: 'POST', headers: HEADERS,
            body: JSON.stringify({ amount, method: document.getElementById('fx-pay-method').value, note: document.getElementById('fx-pay-note').value.trim() || null })
        }));
        showToast(`✅ รับเงิน ${fxBaht(amount)} เรียบร้อย`);
        await fetchTicketsData();
        if (typeof renderFullRepairsTable === 'function') renderFullRepairsTable();
        fxOpenPayments(ticketId);
    } catch (e) { showToast('❌ ' + e.message); }
}

async function fxDeletePayment(paymentId, ticketId) {
    if (!confirm('ลบรายการรับเงินนี้ใช่หรือไม่?')) return;
    try {
        await fxJson(await fetch(`${API_URL}/payments/${paymentId}`, { method: 'DELETE', headers: HEADERS }));
        await fetchTicketsData();
        if (typeof renderFullRepairsTable === 'function') renderFullRepairsTable();
        fxOpenPayments(ticketId);
    } catch (e) { showToast('❌ ' + e.message); }
}

// ═══ 8. Customer approval through LINE ═══════════════════════════════════════
async function fxRequestApproval(ticketId) {
    let d;
    try { d = await fxJson(await fetch(`${API_URL}/tickets/${ticketId}/request-approval`, { method: 'POST', headers: HEADERS })); }
    catch (e) { return showToast('❌ ' + e.message); }
    fxModal('fx-approval-modal', `📲 ส่งใบเสนอราคาให้ลูกค้าอนุมัติ — #${ticketId}`, `
        <div style="padding:10px 12px;border-radius:8px;margin-bottom:12px;${d.sent_via_line ? 'background:rgba(52,211,153,0.1);color:#34d399;' : 'background:rgba(251,191,36,0.1);color:#fbbf24;'}">
            ${d.sent_via_line ? '✅ ส่งลิงก์ไปที่ LINE ของลูกค้าแล้ว' : '⚠️ ' + fxEsc(d.note || 'ยังไม่ได้ส่งทาง LINE')}
        </div>
        <label style="font-size:0.85rem;color:var(--text-secondary);">ลิงก์สำหรับลูกค้า (ยอด ${fxBaht(d.amount)})</label>
        <div style="display:flex;gap:6px;margin-top:4px;">
            <input type="text" id="fx-approval-link" class="form-input" readonly value="${fxEsc(d.link)}">
            <button class="btn-primary" onclick="fxCopy(document.getElementById('fx-approval-link').value)">📋 คัดลอก</button>
        </div>
        <div style="font-size:0.78rem;color:var(--text-muted);margin-top:10px;line-height:1.6;">
            ลูกค้าเปิดลิงก์ได้โดยไม่ต้องใช้รหัสผ่าน — เห็นเฉพาะงานนี้ เมื่อลูกค้ากด "อนุมัติ" งานจะเปลี่ยนเป็น "อนุมัติแล้ว" อัตโนมัติ<br>
            ถ้าลูกค้าอยู่นอกร้าน ลิงก์ต้องเปิดจากอินเทอร์เน็ตได้ — ตั้งค่า "ที่อยู่เว็บของร้าน" ใน ตั้งค่า → การเงิน ภาษี & ระบบ
        </div>
    `, 560);
    fetchTicketsData();
}

async function fxCopy(text) {
    try { await navigator.clipboard.writeText(text); showToast('📋 คัดลอกแล้ว'); }
    catch { prompt('คัดลอกข้อความนี้:', text); }
}

// ═══ 9. Warranty ═════════════════════════════════════════════════════════════
async function fxCheckWarranty(plate) {
    const box = document.getElementById('fx-warranty-banner');
    if (!box) return;
    box.style.display = 'none';
    if (!plate || plate.trim().length < 3) return;
    try {
        const list = await fxJson(await fetch(`${API_URL}/tickets/warranty/${encodeURIComponent(plate.trim())}`, { headers: HEADERS }));
        if (!list.length) return;
        box.innerHTML = `<div style="font-weight:700;margin-bottom:4px;">🛡️ รถคันนี้ยังอยู่ในประกัน ${list.length} งาน</div>` + list.map(w =>
            `<div style="font-size:0.82rem;">• งาน #${w.ticket_id} — ${fxEsc(w.warranty_note || (w.items || []).join(', '))} · ถึง ${new Date(w.warranty_until).toLocaleDateString('th-TH')} (อีก ${w.days_left} วัน)</div>`).join('');
        box.style.display = 'block';
    } catch {}
}

// ═══ Job photos (before / after) ═════════════════════════════════════════════
function fxRenderPhotos(ticket) {
    const box = document.getElementById('edit-ticket-photos');
    if (!box) return;
    const photos = ticket?.photos || [];
    const group = kind => photos.filter(p => p.kind === kind).map(p => `
        <div style="position:relative;width:86px;height:86px;border-radius:8px;overflow:hidden;border:1px solid rgba(255,255,255,0.15);">
            <img src="${fxEsc(p.path)}" style="width:100%;height:100%;object-fit:cover;cursor:pointer;" onclick="viewBillImg('${fxEsc(p.path)}')">
            <button type="button" onclick="fxDeletePhoto(${p.id}, ${ticket.id})" style="position:absolute;top:3px;right:3px;background:rgba(0,0,0,0.65);color:#fff;border:none;border-radius:50%;width:22px;height:22px;cursor:pointer;">✕</button>
        </div>`).join('') || '<span style="font-size:0.8rem;color:var(--text-muted);">ยังไม่มีรูป</span>';
    box.innerHTML = ['before', 'after'].map(kind => `
        <div style="margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <strong style="font-size:0.85rem;">${kind === 'before' ? '📷 ก่อนซ่อม' : '✨ หลังซ่อม'}</strong>
                <label class="btn-sm" style="cursor:pointer;">+ เพิ่มรูป<input type="file" accept="image/*" multiple style="display:none;" onchange="fxUploadPhotos(${ticket.id}, '${kind}', this.files)"></label>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">${group(kind)}</div>
        </div>`).join('');
}

async function fxUploadPhotos(ticketId, kind, files) {
    for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        fd.append('kind', kind);
        try { await fxJson(await fetch(`${API_URL}/tickets/${ticketId}/photos`, { method: 'POST', headers: {}, body: fd })); }
        catch (e) { showToast(`❌ ${f.name}: ${e.message}`); }
    }
    await fxRefreshTicketPhotos(ticketId);
}

async function fxDeletePhoto(photoId, ticketId) {
    if (!confirm('ลบรูปนี้?')) return;
    try { await fxJson(await fetch(`${API_URL}/tickets/photos/${photoId}`, { method: 'DELETE', headers: HEADERS })); }
    catch (e) { return showToast('❌ ' + e.message); }
    await fxRefreshTicketPhotos(ticketId);
}

async function fxRefreshTicketPhotos(ticketId) {
    try {
        const t = await fxJson(await fetch(`${API_URL}/tickets/${ticketId}`, { headers: HEADERS }));
        const i = allTickets.findIndex(x => x.id === ticketId);
        if (i >= 0) allTickets[i] = t;
        fxRenderPhotos(t);
    } catch {}
}

// ═══ 7. Reorder list ═════════════════════════════════════════════════════════
let fxReorderData = null;

async function fxOpenReorder() {
    try { fxReorderData = await fxJson(await fetch(`${API_URL}/stock/reorder/suggestions`, { headers: HEADERS })); }
    catch (e) { return showToast('❌ ' + e.message); }
    if (!fxReorderData.count) {
        return fxModal('fx-reorder-modal', '📋 สั่งซื้ออะไหล่ที่ใกล้หมด', '<p style="text-align:center;padding:24px;color:#34d399;">✅ ไม่มีอะไหล่ที่ต่ำกว่าจุดสั่งซื้อ</p>', 520);
    }
    const groups = fxReorderData.groups.map((g, gi) => `
        <div style="margin-bottom:16px;border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
                <div><strong>🏭 ${fxEsc(g.supplier_name)}</strong>
                    <span style="font-size:0.78rem;color:var(--text-muted);">${g.supplier_phone ? '📞 ' + fxEsc(g.supplier_phone) : ''} ${g.supplier_line_id ? ' · LINE ' + fxEsc(g.supplier_line_id) : ''}</span></div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    <button class="btn-sm" onclick="fxCopy(fxReorderText(${gi}))">📋 คัดลอกข้อความสั่งของ</button>
                    <button class="btn-sm" onclick="fxPrintReorder(${gi})">🖨️ พิมพ์ใบสั่งซื้อ</button>
                    <button class="btn-sm" style="color:#34d399;" onclick="fxReorderToPurchase(${gi})" title="เมื่อของมาส่ง บันทึกเป็นบิลจัดซื้อ (สต็อกจะเพิ่มอัตโนมัติ)">📥 ของมาแล้ว → บันทึกบิลซื้อ</button>
                </div>
            </div>
            <div class="table-responsive"><table class="data-table">
                <thead><tr><th style="width:30px;"><input type="checkbox" checked onchange="document.querySelectorAll('.fx-ro-chk-${gi}').forEach(c=>c.checked=this.checked)"></th><th>อะไหล่</th><th style="text-align:center;">คงเหลือ</th><th style="text-align:center;">จองงานซ่อม</th><th style="text-align:center;">จุดสั่งซื้อ</th><th style="text-align:center;width:90px;">สั่ง</th><th style="text-align:right;">ทุน/หน่วย</th></tr></thead>
                <tbody>${g.items.map((it, ii) => `
                    <tr>
                        <td><input type="checkbox" class="fx-ro-chk-${gi}" data-i="${ii}" checked></td>
                        <td><strong>${fxEsc(it.name)}</strong><div style="font-size:0.72rem;color:var(--text-muted);">${fxEsc(it.sku || '')}</div></td>
                        <td style="text-align:center;color:${it.available <= 0 ? '#f87171' : '#fbbf24'};font-weight:700;">${it.quantity}</td>
                        <td style="text-align:center;">${it.reserved || '—'}</td>
                        <td style="text-align:center;">${it.reorder_level}</td>
                        <td><input type="number" class="form-input fx-ro-qty-${gi}" data-i="${ii}" min="1" step="1" value="${it.suggested_qty}" style="padding:4px 6px;text-align:center;"></td>
                        <td style="text-align:right;">${fxBaht(it.unit_cost)}</td>
                    </tr>`).join('')}</tbody>
            </table></div>
        </div>`).join('');
    fxModal('fx-reorder-modal', `📋 สั่งซื้ออะไหล่ที่ใกล้หมด (${fxReorderData.count} รายการ)`, `
        <p style="font-size:0.82rem;color:var(--text-muted);margin:0 0 12px;">จัดกลุ่มตามร้านที่ซื้อครั้งล่าสุด • จำนวนแนะนำ = จุดสั่งซื้อ × 2 − ที่ขายได้ (แก้ได้)</p>
        ${groups}`, 860);
}

function fxReorderPicked(gi) {
    const g = fxReorderData.groups[gi];
    const qty = {};
    document.querySelectorAll(`.fx-ro-qty-${gi}`).forEach(el => { qty[el.dataset.i] = parseInt(el.value) || 0; });
    const picked = [];
    document.querySelectorAll(`.fx-ro-chk-${gi}`).forEach(el => {
        if (el.checked && qty[el.dataset.i] > 0) picked.push({ ...g.items[el.dataset.i], order_qty: qty[el.dataset.i] });
    });
    return { group: g, items: picked };
}

function fxReorderText(gi) {
    const { group, items } = fxReorderPicked(gi);
    const shop = fxShop.shop_name || localStorage.getItem('shop_name') || 'อู่';
    return `สวัสดีครับ ${group.supplier_name}\n${shop} ขอสั่งอะไหล่ดังนี้:\n` +
        items.map((it, i) => `${i + 1}. ${it.name}${it.sku ? ' (' + it.sku + ')' : ''} × ${it.order_qty}`).join('\n') +
        `\n\nรบกวนแจ้งราคาและวันส่งด้วยครับ 🙏`;
}

function fxPrintReorder(gi) {
    const { group, items } = fxReorderPicked(gi);
    if (!items.length) return showToast('⚠️ ยังไม่ได้เลือกรายการ');
    const shop = fxShop.shop_name || localStorage.getItem('shop_name') || 'Zero Garage';
    const total = items.reduce((s, it) => s + it.order_qty * (it.unit_cost || 0), 0);
    _openPrintWindow(`
        <div style="text-align:center;border-bottom:2px solid #111;padding-bottom:12px;margin-bottom:14px;">
            <div style="font-size:1.4rem;font-weight:800;">${fxEsc(shop)}</div>
            <div style="font-size:1.1rem;font-weight:700;margin-top:6px;">ใบสั่งซื้ออะไหล่ / Purchase Order</div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.9rem;margin-bottom:14px;">
            <div>ถึง: <strong>${fxEsc(group.supplier_name)}</strong>${group.supplier_phone ? '<br>โทร ' + fxEsc(group.supplier_phone) : ''}</div>
            <div>วันที่: <strong>${new Date().toLocaleDateString('th-TH', { dateStyle: 'long' })}</strong></div>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
            <thead><tr style="background:#111;color:#fff;"><th style="padding:8px;text-align:left;">#</th><th style="padding:8px;text-align:left;">รายการ</th><th style="padding:8px;">รหัส</th><th style="padding:8px;text-align:center;">จำนวน</th><th style="padding:8px;text-align:right;">ราคาประมาณ</th></tr></thead>
            <tbody>${items.map((it, i) => `<tr style="border-bottom:1px solid #ddd;"><td style="padding:7px;">${i + 1}</td><td style="padding:7px;">${fxEsc(it.name)}</td><td style="padding:7px;">${fxEsc(it.sku || '')}</td><td style="padding:7px;text-align:center;">${it.order_qty}</td><td style="padding:7px;text-align:right;">${fxBaht(it.order_qty * (it.unit_cost || 0))}</td></tr>`).join('')}</tbody>
        </table>
        <div style="text-align:right;font-weight:800;margin-top:10px;">รวมประมาณ ${fxBaht(total)}</div>
        <div style="margin-top:60px;display:flex;justify-content:flex-end;"><div style="text-align:center;border-top:1px solid #111;padding-top:6px;width:200px;">ผู้สั่งซื้อ</div></div>
    `, `ใบสั่งซื้อ — ${group.supplier_name}`);
}

async function fxReorderToPurchase(gi) {
    const { group, items } = fxReorderPicked(gi);
    if (!items.length) return showToast('⚠️ ยังไม่ได้เลือกรายการ');
    document.getElementById('fx-reorder-modal').style.display = 'none';
    await openAddPurchaseModal(group.supplier_id ? group.supplier_name : '');
    const container = document.getElementById('pb-items-container');
    if (container) container.innerHTML = '';
    items.forEach(it => addPurchaseItemRow(it.name, it.order_qty, it.unit_cost || 0));
    if (typeof recalcPurchaseTotals === 'function') recalcPurchaseTotals();
    showToast('📥 ตรวจจำนวน/ราคาตามบิลจริง แล้วกดบันทึก');
}

// ═══ Barcode labels ══════════════════════════════════════════════════════════
async function fxPrintLabels(ids) {
    const items = (allStock || []).filter(s => ids.includes(s.id));
    if (!items.length) return showToast('⚠️ ไม่มีรายการให้พิมพ์');
    if (typeof JsBarcode !== 'function') return showToast('❌ โหลดตัวสร้างบาร์โค้ดไม่สำเร็จ');

    // Parts without a code get one (ZG-00012) so the scanner can find them
    const noSku = items.filter(s => !s.code);
    if (noSku.length && !confirm(`${noSku.length} รายการยังไม่มีรหัส SKU — ให้ระบบสร้างรหัสให้อัตโนมัติ (เช่น ZG-${String(noSku[0].id).padStart(5, '0')}) แล้วพิมพ์เลยหรือไม่?`)) return;
    for (const s of noSku) {
        const sku = `ZG-${String(s.id).padStart(5, '0')}`;
        try {
            await fxJson(await fetch(`${API_URL}/stock/${s.id}`, {
                method: 'PUT', headers: HEADERS,
                body: JSON.stringify({ name_th: s.name_th || s.name, name_en: s.name_en, sku, category: s.category, quantity: s.quantity, unit_cost: s.unit_cost || 0, sell_price: s.sell_price || 0, reorder_level: s.reorder_level ?? 5, notes: s.notes, bill_path: s.bill_path })
            }));
            s.code = sku;
        } catch (e) { return showToast(`❌ ${s.name}: ${e.message}`); }
    }
    if (noSku.length) fetchStockData();

    const copies = Math.max(1, parseInt(prompt('พิมพ์รายการละกี่ดวง?', '1')) || 1);
    const labels = [];
    for (const s of items) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        try { JsBarcode(svg, s.code, { format: 'CODE128', height: 38, width: 1.6, fontSize: 12, margin: 0, displayValue: true }); }
        catch { showToast(`⚠️ รหัส "${s.code}" สร้างบาร์โค้ดไม่ได้`); continue; }
        for (let i = 0; i < copies; i++) labels.push(`
            <div class="lbl"><div class="nm">${fxEsc(s.name)}</div>${svg.outerHTML}<div class="pr">${fxBaht(s.price)}</div></div>`);
    }
    _openPrintWindow(`
        <style>
            .sheet { display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; }
            .lbl { border:1px dashed #999; border-radius:4px; padding:6px; text-align:center; page-break-inside:avoid; }
            .lbl svg { max-width:100%; height:auto; }
            .nm { font-size:11px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .pr { font-size:13px; font-weight:800; }
            body { max-width: 780px !important; }
        </style>
        <div class="sheet">${labels.join('')}</div>`, 'ฉลากบาร์โค้ดอะไหล่');
}

function fxPrintLabelsForTable() {
    const ids = [...document.querySelectorAll('#stock-tbody tr[id^="stock-row-"]')].map(tr => parseInt(tr.id.replace('stock-row-', '')));
    if (!ids.length) return showToast('⚠️ ไม่มีรายการในตาราง');
    if (ids.length > 60 && !confirm(`จะพิมพ์ฉลาก ${ids.length} รายการ ใช่หรือไม่? (ค้นหาก่อนเพื่อเลือกเฉพาะที่ต้องการ)`)) return;
    fxPrintLabels(ids);
}

// ═══ 5. Automatic backup status ══════════════════════════════════════════════
async function fxLoadBackupStatus() {
    const box = document.getElementById('fx-backup-status');
    if (!box) return;
    try {
        const s = await fxJson(await fetch(`${API_URL}/backup/daily-status`, { headers: HEADERS }));
        const extraOk = s.extra_dir && s.copied_to && !s.error;
        box.innerHTML = `
            <div>📅 สำรองล่าสุด: <strong>${fxEsc(s.newest || 'ยังไม่มี')}</strong> · เก็บไว้ ${s.daily_files}/${s.keep_days} วัน (โฟลเดอร์ backups ในเครื่องนี้)</div>
            <div style="margin-top:4px;">💽 สำเนาเพิ่มเติม: ${s.extra_dir
                ? (extraOk ? `<span style="color:#34d399;">✅ ${fxEsc(s.copied_to)}</span>` : `<span style="color:#fbbf24;">⚠️ ${fxEsc(s.error || 'ยังไม่ได้คัดลอกวันนี้')}</span>`)
                : '<span style="color:#fbbf24;">⚠️ ยังไม่ได้ตั้งค่า — ถ้าคอมพิวเตอร์เสีย ข้อมูลจะหายทั้งหมด แนะนำให้ใส่โฟลเดอร์ USB หรือ Google Drive/OneDrive</span>'}</div>`;
    } catch (e) { box.textContent = '❌ ' + e.message; }
}

async function fxRunBackupNow() {
    try {
        await fxSaveShopSettings();
        const r = await fxJson(await fetch(`${API_URL}/backup/run-daily`, { method: 'POST', headers: HEADERS }));
        showToast(r.error ? '⚠️ ' + r.error : `✅ สำรองข้อมูลแล้ว: ${r.last_file}`);
    } catch (e) { showToast('❌ ' + e.message); }
    fxLoadBackupStatus();
}

// ═══ Reports: daily close, job profit, outstanding ═══════════════════════════
const fxReports = {
    async dailyClose() {
        const dateEl = document.getElementById('dailyClose-date');
        if (dateEl && !dateEl.value) dateEl.value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
        const box = document.getElementById('fx-daily-close-body');
        let d;
        try { d = await fxJson(await fetch(`${API_URL}/reports/daily-close?date=${dateEl.value}`, { headers: HEADERS })); }
        catch (e) { box.innerHTML = `<p style="color:#f87171;">${fxEsc(e.message)}</p>`; return; }
        fxReports._lastClose = d;
        const kpi = (label, val, color = '') => `<div class="report-kpi-card"><div class="report-kpi-label">${label}</div><div class="report-kpi-val ${color}">${val}</div></div>`;
        const methods = Object.entries(d.received_by_method);
        box.innerHTML = `
            <div class="report-kpi-row">
                ${kpi('💰 รับเงินทั้งหมดวันนี้', fxBaht(d.total_received), 'green')}
                ${methods.map(([m, v]) => kpi(m, fxBaht(v), 'blue')).join('') || kpi('ตามวิธีชำระ', '—')}
                ${kpi('💸 รายจ่ายวันนี้', fxBaht(d.total_expenses))}
                ${kpi('💵 เงินสดสุทธิ (เงินสดรับ − รายจ่าย)', fxBaht(d.cash_net), d.cash_net >= 0 ? 'green' : '')}
            </div>
            <div class="report-kpi-row">
                ${kpi('🔧 เปิดงานใหม่', d.tickets_opened)}
                ${kpi('🏁 ซ่อมเสร็จ', d.tickets_completed.length)}
                ${kpi('🛒 บิลขายหน้าร้าน', `${d.pos_sales_count} บิล · ${fxBaht(d.pos_sales_total)}`)}
                ${kpi('📈 กำไรจากงานวันนี้ (หลังหักทุนอะไหล่)', fxBaht(d.profit_on_jobs), 'green')}
                ${kpi('⏳ ลูกค้าค้างชำระ (ทั้งหมด)', `${d.outstanding_count} งาน · ${fxBaht(d.outstanding_total)}`)}
            </div>
            ${fxTable('รายการรับเงิน', ['เวลา', 'รายการ', 'วิธี', 'หมายเหตุ', 'จำนวน'], d.payments.map(p => [p.time, fxEsc(p.ref), fxEsc(p.method), fxEsc(p.note || ''), fxBaht(p.amount)]))}
            ${fxTable('งานที่ซ่อมเสร็จวันนี้', ['งาน', 'ทะเบียน', 'ลูกค้า', 'ช่าง', 'ยอด', 'รับแล้ว', 'ค้าง'], d.tickets_completed.map(t => [`#${t.ticket_id}`, fxEsc(t.plate || ''), fxEsc(t.customer || ''), fxEsc(t.mechanic || ''), fxBaht(t.amount_due), fxBaht(t.amount_paid), t.balance_due > 0 ? `<span style="color:#fbbf24;font-weight:700;">${fxBaht(t.balance_due)}</span>` : '✓']))}
            ${fxTable('รายจ่ายวันนี้', ['หมวด', 'รายละเอียด', 'จำนวน'], d.expenses.map(e => [fxEsc(e.category), fxEsc(e.description || ''), fxBaht(e.amount)]))}
            ${fxTable('อะไหล่ที่ออกจากสต็อกวันนี้', ['อะไหล่', 'รหัส', 'จำนวนที่ใช้/ขาย', 'คงเหลือ'], d.parts_used.map(u => [fxEsc(u.name), fxEsc(u.sku || ''), u.qty, u.left ?? '']))}
        `;
    },

    printDailyClose() {
        const d = fxReports._lastClose;
        if (!d) return;
        const shop = fxShop.shop_name || localStorage.getItem('shop_name') || 'Zero Garage';
        const rows = (list, cols) => list.map(r => `<tr>${cols.map(c => `<td style="padding:5px 8px;border-bottom:1px solid #ddd;">${c(r)}</td>`).join('')}</tr>`).join('');
        _openPrintWindow(`
            <div style="text-align:center;border-bottom:2px solid #111;padding-bottom:10px;margin-bottom:14px;">
                <div style="font-size:1.4rem;font-weight:800;">${fxEsc(shop)}</div>
                <div style="font-size:1.1rem;font-weight:700;">สรุปปิดยอดประจำวัน ${d.date_th}</div>
            </div>
            <table style="width:100%;font-size:0.95rem;margin-bottom:14px;">
                <tr><td>รับเงินทั้งหมด</td><td style="text-align:right;font-weight:800;">${fxBaht(d.total_received)}</td></tr>
                ${Object.entries(d.received_by_method).map(([m, v]) => `<tr><td>&nbsp;&nbsp;• ${fxEsc(m)}</td><td style="text-align:right;">${fxBaht(v)}</td></tr>`).join('')}
                <tr><td>รายจ่ายวันนี้</td><td style="text-align:right;">${fxBaht(d.total_expenses)}</td></tr>
                <tr><td><strong>เงินสดสุทธิ (ควรมีในลิ้นชัก)</strong></td><td style="text-align:right;font-weight:800;">${fxBaht(d.cash_net)}</td></tr>
                <tr><td>งานเปิดใหม่ / ซ่อมเสร็จ / บิลขาย</td><td style="text-align:right;">${d.tickets_opened} / ${d.tickets_completed.length} / ${d.pos_sales_count}</td></tr>
                <tr><td>ลูกค้าค้างชำระทั้งหมด</td><td style="text-align:right;">${d.outstanding_count} งาน · ${fxBaht(d.outstanding_total)}</td></tr>
            </table>
            <div style="font-weight:700;margin:10px 0 4px;">รายการรับเงิน</div>
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">${rows(d.payments, [p => p.time, p => fxEsc(p.ref), p => fxEsc(p.method), p => fxBaht(p.amount)]) || '<tr><td>—</td></tr>'}</table>
            <div style="font-weight:700;margin:10px 0 4px;">อะไหล่ที่ใช้/ขาย</div>
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">${rows(d.parts_used, [u => fxEsc(u.name), u => u.qty, u => 'เหลือ ' + (u.left ?? '')]) || '<tr><td>—</td></tr>'}</table>
            <div style="margin-top:50px;display:flex;justify-content:space-between;">
                <div style="text-align:center;border-top:1px solid #111;padding-top:6px;width:180px;">ผู้ปิดยอด</div>
                <div style="text-align:center;border-top:1px solid #111;padding-top:6px;width:180px;">ผู้ตรวจสอบ</div>
            </div>`, `ปิดยอด ${d.date_th}`);
    },

    async jobProfit(start, end) {
        const box = document.getElementById('fx-job-profit-body');
        let d;
        try { d = await fxJson(await fetch(`${API_URL}/reports/job-profit?start_date=${start}&end_date=${end}`, { headers: HEADERS })); }
        catch (e) { box.innerHTML = `<p style="color:#f87171;">${fxEsc(e.message)}</p>`; return; }
        fxReports._lastJobs = d;
        box.innerHTML = `
            <div class="report-kpi-row">
                <div class="report-kpi-card"><div class="report-kpi-label">ยอดขาย</div><div class="report-kpi-val">${fxBaht(d.total_revenue)}</div></div>
                <div class="report-kpi-card"><div class="report-kpi-label">ต้นทุนอะไหล่</div><div class="report-kpi-val">${fxBaht(d.total_parts_cost)}</div></div>
                <div class="report-kpi-card"><div class="report-kpi-label">กำไร (${d.margin_pct}%)</div><div class="report-kpi-val green">${fxBaht(d.total_profit)}</div></div>
            </div>
            ${d.jobs_missing_cost ? `<div style="margin-bottom:10px;padding:8px 12px;border-radius:8px;background:rgba(251,191,36,0.1);color:#fbbf24;font-size:0.82rem;">⚠️ ${d.jobs_missing_cost} งานมีอะไหล่ที่พิมพ์เอง (ไม่ได้เลือกจากคลัง) จึงไม่รู้ต้นทุน — กำไรของงานเหล่านี้จะสูงกว่าความจริง ให้เลือกอะไหล่จากคลังตอนเปิดงาน</div>` : ''}
            ${fxTable('', ['วันที่', 'เอกสาร', 'ประเภท', 'ลูกค้า / ทะเบียน', 'ช่าง', 'ยอดขาย', 'ทุนอะไหล่', 'กำไร', '%'], d.items.map(j => [
                j.date, j.ref, j.kind_th, fxEsc((j.customer || '') + (j.plate ? ' · ' + j.plate : '')), fxEsc(j.mechanic || '—'),
                fxBaht(j.revenue), fxBaht(j.parts_cost) + (j.missing_cost ? ' <span title="มีอะไหล่ที่ไม่รู้ต้นทุน" style="color:#fbbf24;">⚠️</span>' : ''),
                `<strong style="color:${j.profit >= 0 ? '#34d399' : '#f87171'};">${fxBaht(j.profit)}</strong>`, j.margin_pct + '%',
            ]), 'fx-job-profit-table')}`;
    },

    async outstanding() {
        const box = document.getElementById('fx-outstanding-body');
        let d;
        try { d = await fxJson(await fetch(`${API_URL}/payments/outstanding`, { headers: HEADERS })); }
        catch (e) { box.innerHTML = `<p style="color:#f87171;">${fxEsc(e.message)}</p>`; return; }
        box.innerHTML = `
            <div class="report-kpi-row">
                <div class="report-kpi-card"><div class="report-kpi-label">งานที่ยังค้างชำระ</div><div class="report-kpi-val">${d.count}</div></div>
                <div class="report-kpi-card"><div class="report-kpi-label">ยอดค้างรวม</div><div class="report-kpi-val" style="color:#fbbf24;">${fxBaht(d.total_outstanding)}</div></div>
            </div>
            ${fxTable('', ['งาน', 'วันที่', 'ทะเบียน', 'ลูกค้า', 'โทร', 'ยอด', 'รับแล้ว', 'ค้าง', ''], d.items.map(i => [
                `#${i.ticket_id}`, i.date ? new Date(i.date).toLocaleDateString('th-TH') : '', fxEsc(i.plate || ''), fxEsc(i.customer_name || ''),
                i.customer_phone ? `<a href="tel:${fxEsc(i.customer_phone)}" style="color:#93c5fd;">${fxEsc(i.customer_phone)}</a>` : '',
                fxBaht(i.amount_due), fxBaht(i.amount_paid), `<strong style="color:#fbbf24;">${fxBaht(i.balance_due)}</strong>`,
                `<button class="btn-sm" style="color:#34d399;" onclick="fxOpenPayments(${i.ticket_id})">💵 รับเงิน</button>`,
            ]), 'fx-outstanding-table')}`;
    },
};

function fxTable(title, headers, rows, id = '') {
    return `<div class="report-content-card">
        ${title ? `<div class="report-card-heading">${title}</div>` : ''}
        <div class="report-table-wrapper"><table class="report-data-table" ${id ? `id="${id}"` : ''}>
            <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
            <tbody>${rows.length ? rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')
                : `<tr><td colspan="${headers.length}" class="empty-report-msg">ไม่มีข้อมูล</td></tr>`}</tbody>
        </table></div></div>`;
}

// ═══ Tax invoice helpers (used by printInvoiceFromTicket) ═════════════════════
function fxVatBlock(total) {
    if (fxShop.vat_registered !== '1') return '';
    const rate = parseFloat(fxShop.vat_rate) || 7;
    const base = total / (1 + rate / 100);
    const vat = total - base;
    return `<div>มูลค่าก่อนภาษี: <strong>${fxBaht(base.toFixed(2))}</strong></div>
            <div>ภาษีมูลค่าเพิ่ม ${rate}%: <strong>${fxBaht(vat.toFixed(2))}</strong></div>`;
}

document.addEventListener('DOMContentLoaded', () => {
    fxLoadShopSettings();
    fxLoadBackupStatus();
});
