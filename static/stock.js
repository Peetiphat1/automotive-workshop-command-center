const API_URL = 'http://127.0.0.1:8000/api/v1';
const HEADERS = { 'Content-Type': 'application/json', 'X-API-Key': 'workshop-secret-2026' };

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
    
    document.getElementById('item-modal').style.display = 'flex';
    lucide.createIcons();
}

function closeItemModal() {
    document.getElementById('item-modal').style.display = 'none';
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
            
            // Handle image upload
            const fileInput = document.getElementById('item-image');
            if (fileInput.files.length > 0) {
                await uploadImage(data.id, fileInput.files[0]);
            }
            
            closeItemModal();
            loadCategories();
            loadStock();
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
            headers: { 'X-API-Key': 'workshop-secret-2026' },
            body: formData
        });
    } catch (e) {
        console.error('Image upload failed', e);
    }
}

function escapeHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('item-modal').addEventListener('click', e => { 
    if (e.target === e.currentTarget) closeItemModal(); 
});
