// ── R.O.S.E. Bill Scanner — scan.js ──────────────────────────────────────────
const API_URL = '/api/v1';
const HEADERS = {}; // X-API-Key is added by auth.js
const JSON_HEADERS = { 'Content-Type': 'application/json', ...HEADERS };

// ── State ────────────────────────────────────────────────────────────────────
let billQueue = [];       // array of extracted bill objects
let currentIdx = 0;
let zoomLevel = 1.0;
let isDragging = false;
let dragStart = { x: 0, y: 0 };
let imgOffset = { x: 0, y: 0 };

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    setupDragZoom();
    setupDropZone();
});

// ── File upload ───────────────────────────────────────────────────────────────
async function handleFileUpload(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;
    event.target.value = ''; // allow re-upload of same file
    await processFiles(files);
}

function handleDrop(event) {
    event.preventDefault();
    document.getElementById('drop-zone').classList.remove('dragover');
    const files = Array.from(event.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    if (files.length) processFiles(files);
}

async function processFiles(files) {
    showProcessing(`Reading ${files.length} bill${files.length > 1 ? 's' : ''}...`);

    for (let i = 0; i < files.length; i++) {
        updateProcessingLabel(`AI reading bill ${i + 1} of ${files.length}...`);
        const result = await uploadAndScan(files[i]);
        if (result) billQueue.push(result);
    }

    hideProcessing();

    if (billQueue.length > 0) {
        currentIdx = billQueue.length - files.length; // jump to first new bill
        showSplitView();
        renderBill(currentIdx);
        updateQueueUI();
    }
}

async function uploadAndScan(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_URL}/bills/scan-photo`, {
            method: 'POST',
            headers: HEADERS,
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json();
            showToast(`Failed: ${err.detail || 'Unknown error'}`, 'error');
            return null;
        }
        return await res.json();
    } catch (e) {
        showToast(`Connection error: ${e.message}`, 'error');
        return null;
    }
}

// ── Queue navigation ──────────────────────────────────────────────────────────
function navigateQueue(dir) {
    currentIdx = Math.max(0, Math.min(billQueue.length - 1, currentIdx + dir));
    renderBill(currentIdx);
    updateQueueUI();
}

function updateQueueUI() {
    const qi = document.getElementById('queue-info');
    const ql = document.getElementById('queue-label');
    const prev = document.getElementById('btn-prev');
    const next = document.getElementById('btn-next');

    if (billQueue.length > 1) {
        qi.style.display = 'flex';
        ql.innerText = `Bill ${currentIdx + 1} of ${billQueue.length}`;
        prev.disabled = currentIdx === 0;
        next.disabled = currentIdx === billQueue.length - 1;
    } else {
        qi.style.display = 'none';
    }
}

// ── Render a bill into the review form ───────────────────────────────────────
function renderBill(idx) {
    const bill = billQueue[idx];
    if (!bill) return;

    // Image
    document.getElementById('bill-image').src = bill.image_url;
    document.getElementById('img-label').innerText = bill.image_filename || 'bill.jpg';
    resetZoom();

    // AI badge
    document.getElementById('ai-badge-text').innerText =
        bill.notes?.includes('Demo mode') ? '⚠️ Demo Mode' : '✓ AI Extracted';

    // Customer fields
    setField('r-customer-name', bill.customer_name);
    setField('r-customer-phone', bill.customer_phone);
    setField('r-plate', bill.vehicle_plate);
    setField('r-brand', bill.vehicle_brand);
    setField('r-model', bill.vehicle_model);
    setField('r-submodel', bill.vehicle_submodel);
    setField('r-year', bill.vehicle_year);
    setField('r-color', bill.vehicle_color);
    setField('r-engine', bill.engine_size);
    setSelectField('r-fuel', bill.fuel_type);
    setSelectField('r-transmission', bill.transmission);
    setField('r-mileage', bill.mileage);
    setField('r-date', bill.bill_date);
    setField('r-mechanic', bill.mechanic_name);
    setField('r-labor', bill.labor_cost || 0);
    setField('r-total', bill.total || 0);
    setField('r-notes', bill.notes);

    // Line items
    renderItems(bill.line_items || []);

    // Math banner
    const banner = document.getElementById('math-banner');
    if (!bill.math_ok && bill.total > 0) {
        banner.style.display = 'flex';
        document.getElementById('math-banner-text').innerText =
            `Total mismatch — AI got ฿${bill.total.toLocaleString()} but items sum differently. Please verify.`;
    } else {
        banner.style.display = 'none';
    }

    recalcTotal();
    lucide.createIcons();
}

function setField(id, val) {
    const el = document.getElementById(id);
    if (el && val !== null && val !== undefined) el.value = val;
    else if (el) el.value = '';
}

function setSelectField(id, val) {
    const el = document.getElementById(id);
    if (!el || !val) return;
    for (const opt of el.options) {
        if (opt.value === val) { el.value = val; return; }
    }
}

// ── Line items table ──────────────────────────────────────────────────────────
function renderItems(items) {
    const tbody = document.getElementById('items-tbody');
    tbody.innerHTML = items.map((it, i) => buildItemRow(it, i)).join('');
    lucide.createIcons();
}

function buildItemRow(item, idx) {
    const stockBadge = item.stock_item_id
        ? `<span class="stock-badge matched">in stock</span>`
        : `<span class="stock-badge unmatched">not tracked</span>`;
    return `
        <tr id="row-${idx}" data-stock-id="${item.stock_item_id || ''}">
            <td>
                <input type="text" class="item-name" value="${escHtml(item.name || '')}"
                    oninput="updateRowTotal(${idx})">
                ${stockBadge}
            </td>
            <td><input type="number" class="num-input item-qty" value="${item.qty || 1}"
                min="0" step="0.5" oninput="updateRowTotal(${idx})"></td>
            <td><input type="number" class="num-input item-price" value="${item.unit_price || 0}"
                min="0" step="0.01" oninput="updateRowTotal(${idx})"></td>
            <td><input type="number" class="num-input item-total" value="${item.total || 0}"
                min="0" step="0.01" oninput="recalcTotal()"></td>
            <td><button class="row-delete" onclick="deleteRow(${idx})" title="Remove">
                <i data-lucide="x"></i></button></td>
        </tr>`;
}

function addItemRow() {
    const tbody = document.getElementById('items-tbody');
    const idx = tbody.rows.length;
    const row = document.createElement('tr');
    row.id = `row-${idx}`;
    row.dataset.stockId = '';
    row.innerHTML = buildItemRow({ name: '', qty: 1, unit_price: 0, total: 0 }, idx);
    tbody.appendChild(row);
    lucide.createIcons();
    row.querySelector('.item-name').focus();
}

function deleteRow(idx) {
    const row = document.getElementById(`row-${idx}`);
    if (row) { row.remove(); recalcTotal(); }
}

function updateRowTotal(idx) {
    const row = document.getElementById(`row-${idx}`);
    if (!row) return;
    const qty = parseFloat(row.querySelector('.item-qty')?.value) || 0;
    const price = parseFloat(row.querySelector('.item-price')?.value) || 0;
    const totalInput = row.querySelector('.item-total');
    if (totalInput) totalInput.value = (qty * price).toFixed(2);
    recalcTotal();
}

function recalcTotal() {
    let sum = 0;
    document.querySelectorAll('.item-total').forEach(el => {
        sum += parseFloat(el.value) || 0;
    });
    const labor = parseFloat(document.getElementById('r-labor')?.value) || 0;
    const grand = sum + labor;
    const totalEl = document.getElementById('r-total');
    if (totalEl && !totalEl._manuallyEdited) {
        totalEl.value = grand.toFixed(2);
    }
    document.getElementById('total-auto-note').innerText =
        `Parts: ฿${sum.toLocaleString('th-TH', {maximumFractionDigits:0})} + Labor: ฿${labor.toLocaleString('th-TH', {maximumFractionDigits:0})}`;
}

// Allow manual total edit
document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('r-total');
    if (el) {
        el.addEventListener('input', () => { el._manuallyEdited = true; });
        el.addEventListener('focus', () => { el._manuallyEdited = false; });
    }
});

// ── Collect form data ─────────────────────────────────────────────────────────
function collectFormData() {
    const items = [];
    document.querySelectorAll('#items-tbody tr').forEach(row => {
        const name = row.querySelector('.item-name')?.value?.trim();
        const qty = parseFloat(row.querySelector('.item-qty')?.value) || 1;
        const unit_price = parseFloat(row.querySelector('.item-price')?.value) || 0;
        const total = parseFloat(row.querySelector('.item-total')?.value) || 0;
        const stock_item_id = row.dataset.stockId ? parseInt(row.dataset.stockId) : null;
        if (name) items.push({ name, qty, unit_price, total, stock_item_id });
    });

    const bill = billQueue[currentIdx] || {};

    return {
        image_filename: bill.image_filename || null,
        customer_name: document.getElementById('r-customer-name').value.trim() || null,
        customer_phone: document.getElementById('r-customer-phone').value.trim() || null,
        vehicle_plate: document.getElementById('r-plate').value.trim() || null,
        vehicle_brand: document.getElementById('r-brand').value.trim() || null,
        vehicle_model: document.getElementById('r-model').value.trim() || null,
        vehicle_submodel: document.getElementById('r-submodel').value.trim() || null,
        vehicle_year: parseInt(document.getElementById('r-year').value) || null,
        vehicle_color: document.getElementById('r-color').value.trim() || null,
        engine_size: document.getElementById('r-engine').value.trim() || null,
        fuel_type: document.getElementById('r-fuel').value || null,
        transmission: document.getElementById('r-transmission').value || null,
        mileage: parseInt(document.getElementById('r-mileage').value) || null,
        bill_date: document.getElementById('r-date').value.trim() || null,
        mechanic_name: document.getElementById('r-mechanic').value.trim() || null,
        line_items: items,
        labor_cost: parseFloat(document.getElementById('r-labor').value) || 0,
        total: parseFloat(document.getElementById('r-total').value) || 0,
        notes: document.getElementById('r-notes').value.trim() || null,
    };
}

// ── Confirm bill ──────────────────────────────────────────────────────────────
async function confirmBill() {
    const btn = document.getElementById('btn-confirm');
    btn.disabled = true;
    showProcessing('Saving to all systems...');

    const payload = collectFormData();

    try {
        const res = await fetch(`${API_URL}/bills/confirm`, {
            method: 'POST',
            headers: JSON_HEADERS,
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (res.ok) {
            showToast(
                `✅ Bill confirmed! WorkOrder #${data.work_order_id} — ฿${payload.total.toLocaleString()} saved.` +
                (data.stock_deducted > 0 ? ` Stock updated (${data.stock_deducted} items).` : ''),
                'success'
            );
            // Remove from queue
            billQueue.splice(currentIdx, 1);
            if (billQueue.length === 0) {
                hideSplitView();
            } else {
                currentIdx = Math.min(currentIdx, billQueue.length - 1);
                renderBill(currentIdx);
                updateQueueUI();
            }
        } else {
            showToast(`❌ ${data.detail || 'Failed to save bill'}`, 'error');
        }
    } catch (e) {
        showToast(`❌ Connection error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        hideProcessing();
    }
}

// ── Reject bill ───────────────────────────────────────────────────────────────
function rejectBill() {
    billQueue.splice(currentIdx, 1);
    if (billQueue.length === 0) {
        hideSplitView();
        showToast('Bill rejected', 'info');
    } else {
        currentIdx = Math.min(currentIdx, billQueue.length - 1);
        renderBill(currentIdx);
        updateQueueUI();
        showToast('Bill rejected — next bill loaded', 'info');
    }
}

// ── Show/hide views ───────────────────────────────────────────────────────────
function showSplitView() {
    document.getElementById('drop-zone').style.display = 'none';
    document.getElementById('scan-split').style.display = 'flex';
}
function hideSplitView() {
    document.getElementById('scan-split').style.display = 'none';
    document.getElementById('drop-zone').style.display = 'flex';
    document.getElementById('queue-info').style.display = 'none';
}

// ── Image zoom ────────────────────────────────────────────────────────────────
function setupDragZoom() {
    const viewport = document.getElementById('image-viewport');
    const img = document.getElementById('bill-image');
    if (!viewport || !img) return;

    viewport.addEventListener('wheel', e => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        zoomLevel = Math.max(0.3, Math.min(4, zoomLevel + delta));
        img.style.transform = `scale(${zoomLevel})`;
    }, { passive: false });
}

function zoomIn()   { zoomLevel = Math.min(4, zoomLevel + 0.2); applyZoom(); }
function zoomOut()  { zoomLevel = Math.max(0.3, zoomLevel - 0.2); applyZoom(); }
function resetZoom(){ zoomLevel = 1.0; applyZoom(); }
function applyZoom() {
    const img = document.getElementById('bill-image');
    if (img) img.style.transform = `scale(${zoomLevel})`;
}

// ── Drag-to-scroll image ──────────────────────────────────────────────────────
function setupDropZone() {
    const dz = document.getElementById('drop-zone');
    if (!dz) return;
    dz.addEventListener('dragover', e => {
        e.preventDefault(); dz.classList.add('dragover');
    });
    dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
}

// ── Processing overlay ────────────────────────────────────────────────────────
function showProcessing(label) {
    document.getElementById('processing-label').innerText = label || 'Processing...';
    document.getElementById('processing-overlay').style.display = 'flex';
}
function updateProcessingLabel(label) {
    document.getElementById('processing-label').innerText = label;
}
function hideProcessing() {
    document.getElementById('processing-overlay').style.display = 'none';
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
    const colors = {
        success: 'var(--success)',
        error: 'var(--danger)',
        info: 'var(--accent)',
    };
    const t = document.createElement('div');
    t.style.cssText = `
        background: var(--bg-card); border: 1px solid ${colors[type]};
        color: var(--text-primary); padding: 12px 18px; border-radius: 10px;
        font-size: 13px; font-weight: 500; max-width: 380px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        animation: slideUp 0.3s ease; border-left: 3px solid ${colors[type]};
    `;
    t.innerText = msg;
    document.getElementById('toast-container').appendChild(t);
    setTimeout(() => t.remove(), 4500);
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
