const API_URL = '/api/v1';
const HEADERS = { 'Content-Type': 'application/json' }; // X-API-Key is added by auth.js

const CAT_ICONS = {
  'น้ำมันเครื่อง': { icon: 'droplets', color: '#f59e0b' },
  'กรอง':          { icon: 'filter', color: '#8b5cf6' },
  'เบรค':          { icon: 'disc', color: '#ef4444' },
  'ไฟฟ้า':         { icon: 'zap', color: '#3b82f6' },
  'อะไหล่':        { icon: 'settings', color: '#64748b' },
  'สารเคมี':       { icon: 'flask-conical', color: '#22c55e' },
  'ยาง':           { icon: 'circle', color: '#78716c' },
  'Default':       { icon: 'package', color: '#9ca3af' }
};

let activeCategory = 'All';
let allCategories = [];
let allItems = [];
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    loadCategories();
    loadStock();
    
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            loadStock();
        }, 300);
    });
});

async function loadCategories() {
    try {
        const res = await fetch(`${API_URL}/stock/categories`, { headers: HEADERS });
        if (res.ok) {
            allCategories = await res.json();
            renderCategories();
        }
    } catch (e) {
        console.error('Failed to load categories', e);
    }
}

function renderCategories() {
    const nav = document.getElementById('category-nav');
    let html = `<button class="cat-btn ${activeCategory === 'All' ? 'active' : ''}" onclick="setCategory('All')"><i data-lucide="layers"></i> All Items</button>`;
    
    allCategories.forEach(cat => {
        const iconInfo = CAT_ICONS[cat] || CAT_ICONS['Default'];
        html += `<button class="cat-btn ${activeCategory === cat ? 'active' : ''}" onclick="setCategory('${cat}')">
            <i data-lucide="${iconInfo.icon}" style="color:${iconInfo.color}"></i> ${cat}
        </button>`;
    });
    
    nav.innerHTML = html;
    
    const datalist = document.getElementById('category-list');
    if (datalist) {
        datalist.innerHTML = allCategories.map(c => `<option value="${c}">`).join('');
    }
    lucide.createIcons();
}

function setCategory(cat) {
    activeCategory = cat;
    renderCategories();
    loadStock();
}

async function loadStock() {
    const search = document.getElementById('search-input').value.trim();
    let url = `${API_URL}/stock/?`;
    if (activeCategory !== 'All') url += `category=${encodeURIComponent(activeCategory)}&`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    
    try {
        const res = await fetch(url, { headers: HEADERS });
        if (res.ok) {
            allItems = await res.json();
            renderStock();
            checkLowStock();
        }
    } catch (e) {
        console.error('Failed to load stock', e);
    }
}

function renderStock() {
    const grid = document.getElementById('stock-grid');
    if (allItems.length === 0) {
        grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted)">No items found.</div>';
        return;
    }
    
    grid.innerHTML = allItems.map(item => renderPartCard(item)).join('');
    lucide.createIcons();
}

function renderPartCard(item) {
    const isLow = item.quantity <= item.reorder_level;
    const badgeClass = isLow ? 'low' : '';
    const iconInfo = CAT_ICONS[item.category] || CAT_ICONS['Default'];
    
    const imageHtml = item.image_filename 
        ? `<img src="/static/images/parts/${item.image_filename}" alt="${item.name_th}">`
        : `<i data-lucide="${iconInfo.icon}" class="cat-icon-large" style="color:${iconInfo.color}"></i>`;
        
    return `
        <div class="part-card">
            <div class="part-image">
                <div class="qty-badge ${badgeClass}">${item.quantity} left</div>
                ${imageHtml}
            </div>
            <div class="part-info">
                <div class="part-name-th">${escapeHtml(item.name_th)}</div>
                <div class="part-name-en">${escapeHtml(item.name_en || '')}</div>
                <div class="part-meta">
                    <span class="sku">${escapeHtml(item.sku || 'N/A')}</span>
                    <span style="color:${iconInfo.color}">${escapeHtml(item.category)}</span>
                </div>
                <div class="part-price">
                    <div>
                        <div class="cost-label">Cost</div>
                        ฿${(item.unit_cost||0).toLocaleString()}
                    </div>
                    <div style="text-align:right">
                        <div class="cost-label">Sell</div>
                        ฿${(item.sell_price||0).toLocaleString()}
                    </div>
                </div>
            </div>
            <div class="part-actions">
                ${item.bill_path ? `<button onclick="viewBillLightbox('${item.bill_path}')" title="View Purchase Bill" style="color:#c4b5fd; background:rgba(167,139,250,0.18); border-color:rgba(167,139,250,0.4);"><i data-lucide="receipt"></i></button>` : ''}
                <button onclick="adjustQty(${item.id}, -1)" title="Remove 1"><i data-lucide="minus"></i></button>
                <button class="qty-adjust" onclick="openEditModal(${item.id})" title="Edit Item"><i data-lucide="edit-2"></i></button>
                <button onclick="adjustQty(${item.id}, 1)" title="Add 1"><i data-lucide="plus"></i></button>
            </div>
        </div>
    `;
}

function checkLowStock() {
    const banner = document.getElementById('low-stock-banner');
    const hasLow = allItems.some(item => item.quantity <= item.reorder_level);
    banner.style.display = hasLow ? 'flex' : 'none';
}

async function adjustQty(id, delta) {
    try {
        const res = await fetch(`${API_URL}/stock/${id}/adjust`, {
            method: 'PUT',
            headers: HEADERS,
            body: JSON.stringify({ delta: delta, reason: 'Manual adjustment' })
        });
        if (res.ok) {
            loadStock();
        }
    } catch (e) {
        console.error('Adjust failed', e);
    }
}

function openAddModal() {
    document.getElementById('modal-title').innerHTML = '<i data-lucide="package-plus"></i> Add Part';
    document.getElementById('item-id').value = '';
    document.getElementById('item-form').reset();
    const billPathEl = document.getElementById('item-bill-path');
    const viewBillBtn = document.getElementById('item-view-bill-btn');
    if (billPathEl) billPathEl.value = '';
    if (viewBillBtn) viewBillBtn.style.display = 'none';
    document.getElementById('item-modal').style.display = 'flex';
    lucide.createIcons();
}

function openEditModal(id) {
    const item = allItems.find(i => i.id === id);
    if (!item) return;
    
    document.getElementById('modal-title').innerHTML = '<i data-lucide="edit"></i> Edit Part';
    document.getElementById('item-id').value = item.id;
    document.getElementById('item-name-th').value = item.name_th;
    document.getElementById('item-name-en').value = item.name_en || '';
    document.getElementById('item-sku').value = item.sku || '';
    document.getElementById('item-category').value = item.category;
    document.getElementById('item-quantity').value = item.quantity;
    document.getElementById('item-reorder').value = item.reorder_level;
    document.getElementById('item-cost').value = item.unit_cost;
    document.getElementById('item-price').value = item.sell_price;

    const billPathEl = document.getElementById('item-bill-path');
    const viewBillBtn = document.getElementById('item-view-bill-btn');
    const billInput = document.getElementById('item-bill');
    if (billInput) billInput.value = '';
    if (billPathEl) billPathEl.value = item.bill_path || '';
    if (viewBillBtn) viewBillBtn.style.display = item.bill_path ? 'inline-flex' : 'none';
    
    document.getElementById('item-modal').style.display = 'flex';
    lucide.createIcons();
}

function closeItemModal() {
    document.getElementById('item-modal').style.display = 'none';
}

function viewCurrentPartBill() {
    const path = document.getElementById('item-bill-path')?.value;
    if (path) viewBillLightbox(path);
}

function viewBillLightbox(path) {
    const overlay = document.getElementById('bill-img-overlay');
    const img = document.getElementById('bill-img-el');
    if (overlay && img) {
        img.src = path;
        overlay.style.display = 'flex';
    }
}

function closeBillLightbox() {
    const overlay = document.getElementById('bill-img-overlay');
    if (overlay) overlay.style.display = 'none';
}

async function saveItem() {
    const id = document.getElementById('item-id').value;
    const item = {
        name_th: document.getElementById('item-name-th').value,
        name_en: document.getElementById('item-name-en').value,
        sku: document.getElementById('item-sku').value,
        category: document.getElementById('item-category').value,
        quantity: parseInt(document.getElementById('item-quantity').value) || 0,
        reorder_level: parseInt(document.getElementById('item-reorder').value) || 0,
        unit_cost: parseFloat(document.getElementById('item-cost').value) || 0,
        sell_price: parseFloat(document.getElementById('item-price').value) || 0
    };
    
    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_URL}/stock/${id}` : `${API_URL}/stock/`;
    
    try {
        const res = await fetch(url, {
            method: method,
            headers: HEADERS,
            body: JSON.stringify(item)
        });
        
        if (res.ok) {
            const data = await res.json();
            const itemId = data.id || id;
            
            // Handle image upload
            const fileInput = document.getElementById('item-image');
            if (fileInput && fileInput.files.length > 0) {
                await uploadImage(itemId, fileInput.files[0]);
            }

            // Handle bill upload
            const billInput = document.getElementById('item-bill');
            if (billInput && billInput.files.length > 0) {
                await uploadBill(itemId, billInput.files[0]);
            }
            
            closeItemModal();
            loadCategories();
            loadStock();
        } else {
            const err = await res.json().catch(() => ({}));
            const msg = typeof err.detail === 'string' ? err.detail
                : Array.isArray(err.detail) ? err.detail.map(d => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(' • ')
                : `HTTP ${res.status}`;
            alert('บันทึกไม่สำเร็จ: ' + msg);
        }
    } catch (e) {
        console.error('Save failed', e);
        alert('Failed to save item');
    }
}

async function uploadImage(id, file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        await fetch(`${API_URL}/stock/upload-image/${id}`, {
            method: 'POST',
            headers: {},
            body: formData
        });
    } catch (e) {
        console.error('Image upload failed', e);
    }
}

async function uploadBill(id, file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        await fetch(`${API_URL}/stock/upload-bill/${id}`, {
            method: 'POST',
            headers: {},
            body: formData
        });
    } catch (e) {
        console.error('Bill upload failed', e);
    }
}

function escapeHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('item-modal').addEventListener('click', e => { 
    if (e.target === e.currentTarget) closeItemModal(); 
});

// ── Barcode Scanner Panel ──────────────────────────────────────────────────────
let barcodeTimer = null;
let recentScans  = [];   // [{sku, item}]
let activeIdentifiedData = null;

function openScannerPanel() {
    document.getElementById('scanner-drawer').style.display = 'flex';
    document.getElementById('scanner-backdrop').style.display = 'block';
    // Focus input on next frame so the drawer animation doesn't swallow it
    requestAnimationFrame(() => {
        const inp = document.getElementById('barcode-input');
        if (inp) inp.focus();
    });
    lucide.createIcons();
}

function closeScannerPanel() {
    document.getElementById('scanner-drawer').style.display = 'none';
    document.getElementById('scanner-backdrop').style.display = 'none';
}

// Hardware scanners type very fast then send Enter.
// We also auto-fire after 300 ms of silence so the user doesn't need to hit Enter.
function onBarcodeInput(e) {
    clearTimeout(barcodeTimer);
    barcodeTimer = setTimeout(() => {
        const val = document.getElementById('barcode-input').value.trim();
        if (val.length > 0) doBarcodeLookup();
    }, 300);
}

function onBarcodeKeydown(e) {
    if (e.key === 'Enter') {
        clearTimeout(barcodeTimer);
        e.preventDefault();
        doBarcodeLookup();
    }
}

function clearBarcodeInput() {
    document.getElementById('barcode-input').value = '';
    document.getElementById('scanner-result').style.display = 'none';
    document.getElementById('scanner-not-found').style.display = 'none';
    document.getElementById('barcode-input').focus();
}

async function doBarcodeLookup() {
    const sku = document.getElementById('barcode-input').value.trim();
    if (!sku) return;

    const resultEl  = document.getElementById('scanner-result');
    const nfEl      = document.getElementById('scanner-not-found');

    resultEl.style.display  = 'none';
    nfEl.style.display      = 'none';
    resultEl.innerHTML      = '<div class="scanner-loading"><i data-lucide="loader-2" class="spin"></i> ตรวจสอบสต็อก...</div>';
    resultEl.style.display  = 'block';
    lucide.createIcons();

    try {
        const res = await fetch(`${API_URL}/stock/barcode/${encodeURIComponent(sku)}`, {
            headers: HEADERS
        });

        if (res.status === 404) {
            // Not in local stock — automatically query Sources B & C via AI Identification!
            resultEl.innerHTML = `
                <div class="scanner-loading ai-pulse">
                    <i data-lucide="sparkles" class="spin"></i>
                    <div>
                        <div style="font-weight:600; color:var(--text-primary)">ไม่พบในสต็อก — กำลังสืบค้นด้วย AI</div>
                        <div style="font-size:12px; color:var(--text-muted)">ตรวจฐานข้อมูลสินค้าสากล & แคตตาล็อกยานยนต์ (B & C)...</div>
                    </div>
                </div>`;
            lucide.createIcons();

            try {
                const identRes = await fetch(`${API_URL}/stock/barcode/identify/${encodeURIComponent(sku)}`, {
                    headers: HEADERS
                });

                if (identRes.ok) {
                    const identData = await identRes.json();
                    if (identData.found_in_stock && identData.item) {
                        renderScannerResult(identData.item);
                        addRecentScan(sku, identData.item);
                        return;
                    } else if (identData.identified) {
                        renderIdentifiedResult(identData);
                        return;
                    }
                }
            } catch (identErr) {
                console.warn('AI Identify lookup error:', identErr);
            }

            // Fallback if not recognized
            resultEl.style.display = 'none';
            nfEl.innerHTML = `
                <i data-lucide="package-x"></i>
                <div class="scanner-nf-sku">"${escapeHtml(sku)}"</div>
                <div class="scanner-nf-msg">ไม่พบสินค้านี้ในระบบ — Not found in stock</div>
                <div class="scanner-nf-actions">
                    <a href="https://www.google.com/search?q=${encodeURIComponent(sku + ' อะไหล่ auto part')}" target="_blank" rel="noopener noreferrer" class="btn-google-search-nf">
                        <i data-lucide="search"></i> ค้นหาบาร์โค้ด "${escapeHtml(sku)}" บน Google
                    </a>
                    <button class="btn-add-from-scan" onclick="openAddModalWithSku('${escapeHtml(sku)}')">
                        <i data-lucide="plus-circle"></i> นำเข้า "${escapeHtml(sku)}" เป็นอะไหล่ใหม่
                    </button>
                </div>
            `;
            nfEl.style.display = 'flex';
            lucide.createIcons();
            return;
        }

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const item = await res.json();
        renderScannerResult(item);
        addRecentScan(sku, item);

    } catch (err) {
        resultEl.innerHTML = `<div class="scanner-error"><i data-lucide="alert-circle"></i> Error: ${escapeHtml(err.message)}</div>`;
        lucide.createIcons();
    }
}

function renderScannerResult(item) {
    const resultEl = document.getElementById('scanner-result');
    document.getElementById('scanner-not-found').style.display = 'none';

    const isLow    = item.quantity <= item.reorder_level;
    const isOut    = item.quantity === 0;
    const qtyClass = isOut ? 'scan-qty out' : isLow ? 'scan-qty low' : 'scan-qty ok';
    const qtyLabel = isOut ? '⚠ Out of stock' : isLow ? `⚠ Low: ${item.quantity} left` : `✓ ${item.quantity} in stock`;
    const iconInfo = CAT_ICONS[item.category] || CAT_ICONS['Default'];
    const imageHtml = item.image_filename
        ? `<img src="/static/images/parts/${item.image_filename}" alt="${item.name_th}" class="scan-item-img-large">`
        : `<div class="scan-item-icon-large" style="--cat-color:${iconInfo.color}"><i data-lucide="${iconInfo.icon}"></i></div>`;

    resultEl.innerHTML = `
        <!-- Product identity -->
        <div class="scan-identity">
            <div class="scan-thumb">${imageHtml}</div>
            <div class="scan-identity-body">
                <div class="scan-found-label"><i data-lucide="check-circle-2"></i> Product Found</div>
                <div class="scan-main-name">${escapeHtml(item.name_th)}</div>
                ${item.name_en ? `<div class="scan-main-name-en">${escapeHtml(item.name_en)}</div>` : ''}
                <div class="scan-badges">
                    <span class="sku-badge">${escapeHtml(item.sku || 'N/A')}</span>
                    <span class="cat-badge" style="--cat-color:${iconInfo.color}">${escapeHtml(item.category)}</span>
                </div>
            </div>
        </div>

        <!-- Stock level hero -->
        <div class="scan-stock-hero">
            <div class="scan-stock-number ${isOut ? 'out' : isLow ? 'low' : 'ok'}" id="scan-qty-display-${item.id}">${item.quantity}</div>
            <div class="scan-stock-unit">units in stock</div>
            <div class="${qtyClass} scan-stock-pill">${qtyLabel}</div>
            <div class="scan-reorder-note">Reorder level: ${item.reorder_level}</div>
        </div>

        <!-- Price row -->
        <div class="scan-price-row">
            <div class="scan-price-box">
                <div class="scan-price-label">Cost Price</div>
                <div class="scan-price-val">฿${(item.unit_cost||0).toLocaleString('th-TH')}</div>
            </div>
            <div class="scan-price-divider"></div>
            <div class="scan-price-box">
                <div class="scan-price-label">Sell Price</div>
                <div class="scan-price-val accent">฿${(item.sell_price||0).toLocaleString('th-TH')}</div>
            </div>
            <div class="scan-price-divider"></div>
            <div class="scan-price-box">
                <div class="scan-price-label">Margin</div>
                <div class="scan-price-val ${(item.sell_price - item.unit_cost) >= 0 ? 'green' : 'red'}">
                    ฿${((item.sell_price||0) - (item.unit_cost||0)).toLocaleString('th-TH')}
                </div>
            </div>
        </div>

        <!-- Adjust controls -->
        <div class="scan-adjust-row">
            <button class="scan-btn minus" onclick="scannerAdjust(${item.id}, -1)">
                <i data-lucide="minus-circle"></i><span>Remove 1</span>
            </button>
            <button class="scan-btn plus" onclick="scannerAdjust(${item.id}, +1)">
                <i data-lucide="plus-circle"></i><span>Add 1</span>
            </button>
        </div>
        <div class="scan-links-row">
            <button class="scan-edit-link" onclick="closeScannerPanel(); openEditModal(${item.id})">
                <i data-lucide="edit-2"></i> Open Full Edit
            </button>
            <a href="https://www.google.com/search?q=${encodeURIComponent((item.sku || '') + ' ' + (item.name_th || '') + ' auto part')}" target="_blank" rel="noopener noreferrer" class="scan-google-link">
                <i data-lucide="external-link"></i> Google Search
            </a>
        </div>
    `;
    resultEl.style.display = 'block';
    lucide.createIcons();
}

function renderIdentifiedResult(data) {
    activeIdentifiedData = data;
    const resultEl = document.getElementById('scanner-result');
    document.getElementById('scanner-not-found').style.display = 'none';

    const iconInfo = CAT_ICONS[data.category] || CAT_ICONS['Default'];
    const imageHtml = data.image_url 
        ? `<img src="${data.image_url}" alt="Part image" class="scan-item-img-large">`
        : `<div class="scan-item-icon-large" style="--cat-color:${iconInfo.color}"><i data-lucide="${iconInfo.icon}"></i></div>`;

    resultEl.innerHTML = `
        <div class="scanner-ai-card">
            <div class="scanner-ai-header">
                <div class="scanner-ai-badge">
                    <i data-lucide="sparkles"></i> <span>ตรวจพบจาก AI & แคตตาล็อก</span>
                </div>
                <span class="scanner-source-badge">${escapeHtml(data.source || 'Automotive Catalog')}</span>
            </div>

            <div class="scan-identity" style="margin-bottom: 12px;">
                <div class="scan-thumb">${imageHtml}</div>
                <div class="scan-identity-body">
                    <div class="scan-main-name">${escapeHtml(data.name_th)}</div>
                    ${data.name_en ? `<div class="scan-main-name-en">${escapeHtml(data.name_en)}</div>` : ''}
                    <div class="scan-badges">
                        <span class="sku-badge">${escapeHtml(data.sku)}</span>
                        <span class="cat-badge" style="--cat-color:${iconInfo.color}">${escapeHtml(data.category)}</span>
                        ${data.brand ? `<span class="brand-badge">${escapeHtml(data.brand)}</span>` : ''}
                    </div>
                </div>
            </div>

            ${data.compatible_vehicles ? `
            <div class="scanner-fitment-box">
                <div class="fitment-title"><i data-lucide="car"></i> รุ่นรถยนต์ที่รองรับ (Fitment):</div>
                <div class="fitment-text">${escapeHtml(data.compatible_vehicles)}</div>
            </div>` : ''}

            <div class="scan-price-row" style="margin-top: 14px;">
                <div class="scan-price-box">
                    <div class="scan-price-label">ราคาทุนประเมิน</div>
                    <div class="scan-price-val">฿${(data.unit_cost || 0).toLocaleString('th-TH')}</div>
                </div>
                <div class="scan-price-divider"></div>
                <div class="scan-price-box">
                    <div class="scan-price-label">ราคาขายแนะนำ</div>
                    <div class="scan-price-val accent">฿${(data.sell_price || 0).toLocaleString('th-TH')}</div>
                </div>
            </div>

            <div class="scanner-ai-actions">
                <button class="btn-ai-add-stock" onclick="openAddModalWithIdentified()">
                    <i data-lucide="plus-circle"></i> นำเข้าสต็อกด้วยข้อมูลนี้ (Add to Stock)
                </button>
                <a href="https://www.google.com/search?q=${encodeURIComponent((data.sku || '') + ' ' + (data.name_th || '') + ' auto part')}" target="_blank" rel="noopener noreferrer" class="btn-ai-google-search">
                    <i data-lucide="search"></i> ตรวจสอบข้อมูลบน Google (Check on Google)
                </a>
                <button class="btn-ai-manual-edit" onclick="openAddModalWithSku('${escapeHtml(data.sku)}')">
                    <i data-lucide="edit-3"></i> แก้ไขข้อมูลเอง (Manual)
                </button>
            </div>
        </div>
    `;
    resultEl.style.display = 'block';
    lucide.createIcons();
}

function openAddModalWithIdentified() {
    if (!activeIdentifiedData) return;
    const data = activeIdentifiedData;
    openAddModal();
    if (data.name_th) document.getElementById('item-name-th').value = data.name_th;
    if (data.name_en) document.getElementById('item-name-en').value = data.name_en;
    if (data.sku) document.getElementById('item-sku').value = data.sku;
    if (data.category) document.getElementById('item-category').value = data.category;
    if (data.unit_cost) document.getElementById('item-cost').value = data.unit_cost;
    if (data.sell_price) document.getElementById('item-price').value = data.sell_price;
    
    // Auto-fill note / fitment if field exists
    const notesEl = document.getElementById('item-notes');
    if (notesEl && data.compatible_vehicles) {
        notesEl.value = `รุ่นรถ: ${data.compatible_vehicles}`;
    }

    // Auto-focus quantity input so staff can directly type the incoming stock
    const qtyEl = document.getElementById('item-quantity');
    if (qtyEl) {
        qtyEl.value = '1';
        setTimeout(() => { qtyEl.focus(); qtyEl.select(); }, 150);
    }
    closeScannerPanel();
}

function openAddModalWithSku(sku) {
    // Open the Add Part modal with SKU pre-filled
    openAddModal();
    document.getElementById('item-sku').value = sku;
    // Also close the scanner so the modal is visible
    closeScannerPanel();
}

async function scannerAdjust(id, delta) {
    try {
        const res = await fetch(`${API_URL}/stock/${id}/adjust`, {
            method: 'PUT',
            headers: HEADERS,
            body: JSON.stringify({ delta, reason: delta > 0 ? 'Barcode scan — add stock' : 'Barcode scan — remove stock' })
        });
        if (res.ok) {
            const updated = await res.json();
            // Update display in the result card
            const qtyDisplay = document.getElementById(`scan-qty-display-${id}`);
            if (qtyDisplay) qtyDisplay.innerText = updated.quantity;
            // Refresh background grid too
            loadStock();
            // Re-render the result card to update colours
            renderScannerResult(updated);
        }
    } catch (e) {
        console.error('Adjust failed', e);
    }
}

function addRecentScan(sku, item) {
    // Keep last 8 unique scans
    recentScans = recentScans.filter(s => s.sku !== sku);
    recentScans.unshift({ sku, item });
    if (recentScans.length > 8) recentScans.pop();
    renderRecentScans();
}

function renderRecentScans() {
    const el = document.getElementById('scanner-recent');
    if (recentScans.length === 0) {
        el.innerHTML = '<div class="scanner-recent-empty">No recent scans yet</div>';
        return;
    }
    el.innerHTML = recentScans.map(s => {
        const iconInfo = CAT_ICONS[s.item.category] || CAT_ICONS['Default'];
        const isLow    = s.item.quantity <= s.item.reorder_level;
        return `
            <div class="recent-scan-row" onclick="renderScannerResult(${JSON.stringify(s.item).replace(/"/g, '&quot;')})">
                <span class="recent-scan-sku">${escapeHtml(s.sku)}</span>
                <span class="recent-scan-name">${escapeHtml(s.item.name_th)}</span>
                <span class="recent-scan-qty ${isLow ? 'low' : ''}">${s.item.quantity}</span>
            </div>`;
    }).join('');
}

// Global keyboard shortcut: press F2 anywhere on the stock page to open scanner
document.addEventListener('keydown', e => {
    if (e.key === 'F2') {
        e.preventDefault();
        openScannerPanel();
    }
});
