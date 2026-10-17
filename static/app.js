// ─── Constants & Configuration ────────────────────────────────────────────────
const API_URL = '/api/v1';
const API_KEY = ''; // real key is added by auth.js

// Headers helper
const getHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
    };
};

// Global State
let activeTab = 'overview';
let chartInstance = null;
let selectedCustomerId = null;

// ─── Initialization ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initTabs();
    initOverview();
    initTicketsTab();
    initFinanceTab();
    initCustomersTab();
    initMarketingTab();
    
    // Add periodic refresh or listeners
    document.getElementById('btn-trigger-retention').addEventListener('click', runRetentionScan);
});

// ─── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'check-circle';
    if (type === 'warning') icon = 'alert-triangle';
    if (type === 'danger') icon = 'x-circle';
    
    toast.innerHTML = `
        <i data-lucide="${icon}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    lucide.createIcons({attrs: {class: 'toast-icon'}});
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) reverse forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ─── Tab Switching Logic ──────────────────────────────────────────────────────
function initTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            switchTab(targetTab);
            
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function switchTab(tabId) {
    activeTab = tabId;
    
    // Hide all panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    
    // Show active pane
    const targetPane = document.getElementById(`tab-${tabId}`);
    if (targetPane) targetPane.classList.add('active');
    
    // Update headers
    const title = document.getElementById('current-tab-title');
    const subtitle = document.getElementById('current-tab-subtitle');
    
    if (tabId === 'overview') {
        title.innerText = 'Overview Dashboard';
        subtitle.innerText = 'Real-time status of your workshop operations.';
        initOverview();
    } else if (tabId === 'tickets') {
        title.innerText = 'Work Tickets';
        subtitle.innerText = 'Manage vehicle intakes, diagnoses, and mechanic estimates.';
        loadTickets();
        loadOverviewWatchlist();
    } else if (tabId === 'finance') {
        title.innerText = 'Finance & Ledger';
        subtitle.innerText = 'Automated zero-hallucination bookkeeping and monthly P&L insights.';
        loadFinance();
    } else if (tabId === 'customers') {
        title.innerText = 'Customer 360° Profile';
        subtitle.innerText = 'Detailed vehicle health watchlists, and client transaction histories.';
        loadCustomers();
    } else if (tabId === 'marketing') {
        title.innerText = 'LINE Retention Campaigns';
        subtitle.innerText = 'AI-generated retention marketing templates and Line dispatcher.';
        loadMarketing();
    }
}

// ─── Overview Tab Modules ─────────────────────────────────────────────────────
async function initOverview() {
    try {
        // Fetch current month summary for stats
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0'); // e.g. "08"
        
        const res = await fetch(`${API_URL}/finance/summary/${year}/${month}`, { headers: getHeaders() });
        if (res.ok) {
            const data = await res.json();
            document.getElementById('overview-revenue').innerText = `฿${data.summary.total_income.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
            document.getElementById('overview-expenses').innerText = `฿${data.summary.total_expense.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
            document.getElementById('overview-profit').innerText = `฿${data.summary.net_profit.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
        }
        
        // Fetch tickets for pending count
        const ticketRes = await fetch(`${API_URL}/tickets/?limit=200`, { headers: getHeaders() });
        let pendingTickets = 0;
        if (ticketRes.ok) {
            const ticketData = await ticketRes.json();
            pendingTickets = ticketData.items.filter(t => t.status === 'PENDING_MECHANIC_APPROVAL' || t.status === 'DRAFT_ESTIMATE').length;
        }

        // Fetch marketing tasks for pending count
        const marketingRes = await fetch(`${API_URL}/marketing/tasks/`, { headers: getHeaders() });
        let pendingMarketing = 0;
        if (marketingRes.ok) {
            const marketingData = await marketingRes.json();
            pendingMarketing = marketingData.pending || 0;
        }
        
        // Show repair ticket pending count only (not combined — more accurate)
        document.getElementById('overview-pending').innerText = pendingTickets;
        document.getElementById('overview-pending-subtext').innerText = `${pendingTickets} repair ticket${pendingTickets !== 1 ? 's' : ''} awaiting mechanic approval${pendingMarketing > 0 ? ` · ${pendingMarketing} LINE campaign${pendingMarketing !== 1 ? 's' : ''} pending` : ''}`;
        
        // Fetch health watchlist
        loadOverviewWatchlist();
        
    } catch (err) {
        console.error("Overview error", err);
    }
}

async function loadOverviewWatchlist() {
    const listContainers = [
        document.getElementById('overview-watchlist'),
        document.getElementById('tickets-watchlist')
    ];
    listContainers.forEach(container => {
        if (container) {
            container.innerHTML = '<p class="loading-placeholder">Loading health alerts...</p>';
        }
    });
    
    try {
        // Fetch a customer's vehicle health watchlist or loop through vehicles
        // For simplicity, we fetch all customers, then look up vehicle health
        const res = await fetch(`${API_URL}/customers/`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to load customer list");
        const customersData = await res.json();
        const customers = customersData.items || [];
        
        let allWatchlistItems = [];
        
        for (let customer of customers) {
            const profileRes = await fetch(`${API_URL}/customers/${customer.id}/profile`, { headers: getHeaders() });
            if (profileRes.ok) {
                const profile = await profileRes.json();
                profile.vehicles.forEach(v => {
                    v.health_watchlist.forEach(w => {
                        if (w.is_overdue) {
                            allWatchlistItems.push({
                                plate: v.plate,
                                brand: v.brand,
                                model: v.model,
                                component: w.component,
                                condition: w.condition,
                                is_overdue: w.is_overdue,
                                notes: w.notes
                            });
                        }
                    });
                });
            }
        }
        
        const listContainers = [
            document.getElementById('overview-watchlist'),
            document.getElementById('tickets-watchlist')
        ];
        
        listContainers.forEach(container => {
            if (!container) return;
            if (allWatchlistItems.length === 0) {
                container.innerHTML = '<p class="loading-placeholder">All vehicles are healthy!</p>';
                return;
            }
            container.innerHTML = '';
            allWatchlistItems.forEach(item => {
                const el = document.createElement('div');
                el.className = `watchlist-item ${item.is_overdue ? 'overdue' : ''}`;
                el.innerHTML = `
                    <div class="watchlist-title-row">
                        <span class="watchlist-plate">${item.brand} ${item.model} (${item.plate})</span>
                        <span class="watchlist-badge">${item.is_overdue ? 'OVERDUE' : 'WARNING'}</span>
                    </div>
                    <div class="watchlist-comp">${item.component} : ${item.condition}</div>
                    <div class="watchlist-notes">${item.notes || ''}</div>
                    <div style="display:flex; justify-content:flex-end; margin-top:8px; gap:8px;">
                        <button class="btn btn-filter btn-accent" style="padding:4px 8px; font-size:11px;" onclick="resolveWatchlistItem('${item.brand}', '${item.model}', '${item.plate}', '${item.component}')">
                            <i data-lucide="wrench" style="width:12px; height:12px; display:inline-block; vertical-align:middle; margin-right:4px;"></i> Resolve Issue
                        </button>
                        <button class="btn btn-filter btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="dismissWatchlistItem('${item.plate}', '${item.component}')">
                            <i data-lucide="check" style="width:12px; height:12px; display:inline-block; vertical-align:middle; margin-right:4px;"></i> Done Elsewhere
                        </button>
                    </div>
                `;
                container.appendChild(el);
            });
        });
        lucide.createIcons();
        
    } catch (err) {
        console.error("Watchlist loading error", err);
        const listContainers = [
            document.getElementById('overview-watchlist'),
            document.getElementById('tickets-watchlist')
        ];
        listContainers.forEach(container => {
            if (container) {
                container.innerHTML = `<p class="loading-placeholder text-danger">Error: ${err.message}</p>`;
            }
        });
    }
}

function resolveWatchlistItem(brand, model, plate, component) {
    switchTab('overview');
    const text = `รถ ${brand} ${model} ทะเบียน ${plate} มาทำการตรวจเช็คและเปลี่ยน ${component} เกินกำหนด`;
    document.getElementById('intake-text').value = text;
    document.getElementById('intake-form').scrollIntoView({ behavior: 'smooth' });
    showToast(`Pre-filled intake parser for ${brand} ${model}!`);
}

async function dismissWatchlistItem(plate, component) {
    if (!confirm(`Mark ${component} for vehicle (${plate}) as serviced elsewhere?`)) return;
    
    try {
        // 1. Fetch current vehicle data
        const getRes = await fetch(`${API_URL}/vehicles/${plate}/health`, { headers: getHeaders() });
        if (!getRes.ok) throw new Error("Failed to load vehicle details");
        const vehicle = await getRes.json();
        
        // 2. Build update payload
        const nowStr = new Date().toISOString();
        const payload = {
            current_mileage: vehicle.current_mileage,
            last_service_date: nowStr
        };
        
        if (component === "น้ำมันเครื่อง") {
            payload.last_oil_change_date = nowStr;
            payload.last_oil_change_mileage = vehicle.current_mileage;
        } else if (component === "แบตเตอรี่") {
            payload.last_battery_date = nowStr;
        } else if (component === "ยางรถยนต์") {
            payload.last_tire_change_mileage = vehicle.current_mileage;
        }
        
        // 3. Update vehicle mileage & log
        const putRes = await fetch(`${API_URL}/vehicles/${plate}/mileage`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });
        
        if (!putRes.ok) {
            const errData = await putRes.json();
            throw new Error(errData.detail || "Failed to update vehicle log");
        }
        
        showToast(`Logged ${component} service elsewhere for ${plate}.`);
        
        // 4. Reload overview stats and watchlist
        initOverview();
        
    } catch (err) {
        console.error("Failed to dismiss alert", err);
        showToast(err.message, "danger");
    }
}

// Intake Ingestion Form Submission
document.getElementById('intake-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = document.getElementById('intake-text').value;
    const resultBox = document.getElementById('ingestion-result');
    const submitBtn = document.getElementById('btn-submit-intake');
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="spinner"></i> Ingesting via LangGraph...';
    resultBox.className = 'ingestion-result-box hidden';
    
    try {
        const res = await fetch(`${API_URL}/tickets/ingest`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ raw_input: text })
        });
        
        const data = await res.json();
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="cpu"></i> Run R.O.S.E. Parser Graph';
        lucide.createIcons();
        
        resultBox.classList.remove('hidden');
        if (res.ok) {
            resultBox.className = 'ingestion-result-box result-success';
            
            // Format details beautifully
            let symptoms = Array.isArray(data.extracted_symptoms) ? data.extracted_symptoms : [];
            let diagnoses = Array.isArray(data.diagnosed_issues) ? data.diagnosed_issues : [];
            let lineItems = Array.isArray(data.line_items) ? data.line_items : [];
            
            resultBox.innerHTML = `
                <h4 style="color:var(--color-success); margin-bottom:8px;"><i data-lucide="check-circle"></i> Service Ticket Created Successfully!</h4>
                <p><strong>Ticket ID:</strong> ${data.id} | <strong>Status:</strong> ${data.status}</p>
                <p><strong>Raw Input:</strong> "${data.raw_input}"</p>
                <div style="margin-top: 10px;">
                    <strong>Extracted Symptoms:</strong> ${symptoms.join(', ') || 'None'}
                </div>
                <div style="margin-top: 10px;">
                    <strong>AI Diagnose:</strong>
                    <ul style="padding-left:20px; margin-top:4px;">
                        ${diagnoses.map(d => `<li><strong>${d.symptom}</strong> → ${d.issue} (Severity: ${d.severity})</li>`).join('')}
                    </ul>
                </div>
                <div style="margin-top: 10px;">
                    <strong>Price Estimate Breakdown:</strong>
                    <ul style="padding-left:20px; margin-top:4px;">
                        ${lineItems.map(item => `<li>${item.name_th} (${item.qty} ${item.type === 'part' ? 'ชิ้น' : 'ชม.'}) - ฿${item.total.toLocaleString()}</li>`).join('')}
                    </ul>
                    <p style="margin-top:8px;"><strong>Total Estimate:</strong> ฿${data.total_estimated_cost.toLocaleString()} (Labor: ฿${data.estimated_labor_cost.toLocaleString()}, Parts: ฿${data.estimated_parts_cost.toLocaleString()})</p>
                </div>
            `;
            showToast("AI Ingestion complete. Service Ticket registered!");
            initOverview();
        } else {
            resultBox.className = 'ingestion-result-box result-error';
            let errorMsg = typeof data.detail === 'object' ? JSON.stringify(data.detail) : (data.detail || 'Internal server error');
            if (Array.isArray(data.detail) && data.detail[0] && data.detail[0].msg) {
                errorMsg = `${data.detail[0].loc.join('.')} - ${data.detail[0].msg}`;
            }
            resultBox.innerHTML = `<h4 style="color:var(--color-danger);"><i data-lucide="alert-triangle"></i> Ingestion Failed</h4><p>${errorMsg}</p>`;
            showToast("Ingestion failed: " + errorMsg, 'danger');
        }
        lucide.createIcons();
    } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="cpu"></i> Run R.O.S.E. Parser Graph';
        lucide.createIcons();
        
        resultBox.classList.remove('hidden');
        resultBox.className = 'ingestion-result-box result-error';
        resultBox.innerHTML = `<h4>Ingestion Error</h4><p>${err.message}</p>`;
        showToast(err.message, 'danger');
    }
});

// ─── Tickets Tab ──────────────────────────────────────────────────────────────
let allTickets = [];
let ticketFilter = 'all';

function initTicketsTab() {
    document.getElementById('ticket-search').addEventListener('input', renderTicketsDeck);
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            ticketFilter = e.target.getAttribute('data-filter');
            renderTicketsDeck();
        });
    });
}

async function loadTickets() {
    const deck = document.getElementById('tickets-deck');
    deck.innerHTML = '<p class="loading-placeholder">Loading tickets...</p>';
    
    try {
        const res = await fetch(`${API_URL}/tickets/`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to fetch tickets");
        const data = await res.json();
        allTickets = data.items || [];
        renderTicketsDeck();
    } catch (err) {
        deck.innerHTML = `<p class="loading-placeholder text-danger">Error: ${err.message}</p>`;
    }
}

function renderTicketsDeck() {
    const deck = document.getElementById('tickets-deck');
    const searchVal = document.getElementById('ticket-search').value.toLowerCase();
    
    // Filter
    let filtered = allTickets;
    if (ticketFilter !== 'all') {
        if (ticketFilter === 'PENDING_MECHANIC_APPROVAL') {
            filtered = filtered.filter(t => t.status === 'PENDING_MECHANIC_APPROVAL' || t.status === 'DRAFT_ESTIMATE');
        } else {
            filtered = filtered.filter(t => t.status === ticketFilter);
        }
    }
    
    // Search
    if (searchVal) {
        filtered = filtered.filter(t => {
            return t.raw_input.toLowerCase().includes(searchVal) || 
                   t.status.toLowerCase().includes(searchVal) ||
                   (t.id + '').includes(searchVal);
        });
    }
    
    if (filtered.length === 0) {
        deck.innerHTML = '<p class="loading-placeholder">No service tickets matching filters found.</p>';
        return;
    }
    
    deck.innerHTML = '';
    filtered.forEach(ticket => {
        const symptoms = Array.isArray(ticket.extracted_symptoms) ? ticket.extracted_symptoms : [];
        const diagnoses = Array.isArray(ticket.diagnosed_issues) ? ticket.diagnosed_issues : [];
        const lineItems = Array.isArray(ticket.line_items) ? ticket.line_items : [];
        
        const card = document.createElement('div');
        card.className = 'ticket-card';
        
        let actionsHtml = '';
        if (ticket.status === 'PENDING_MECHANIC_APPROVAL' || ticket.status === 'DRAFT_ESTIMATE') {
            actionsHtml = `
                <div class="ticket-actions">
                    <button class="btn btn-success btn-sm" onclick="approveTicket(${ticket.id})">
                        <i data-lucide="check"></i> Approve Estimate
                    </button>
                </div>
            `;
        } else {
            actionsHtml = `
                <div class="ticket-actions">
                    <span style="font-size:12px; color:var(--color-success); font-weight:600;"><i data-lucide="check-circle-2" style="display:inline; width:14px; height:14px; margin-right:4px; vertical-align:middle;"></i>Approved by ${ticket.approved_by || 'Mechanic'}</span>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="ticket-header">
                <div class="ticket-meta">
                    <h4>Ticket #${ticket.id}</h4>
                    <span>Created: ${new Date(ticket.created_at).toLocaleDateString()}</span>
                </div>
                <span class="ticket-status-badge ${ticket.status === 'APPROVED' ? 'approved' : 'pending'}">
                    ${ticket.status}
                </span>
            </div>
            
            <div class="ticket-raw-desc">
                "${ticket.raw_input}"
            </div>
            
            <div class="ticket-diagnoses">
                <h5>AI Symptoms & Diagnoses</h5>
                <div class="diagnose-tag-deck">
                    ${diagnoses.map(d => `
                        <div class="diagnose-item-row">
                            <div>
                                <span class="diagnose-symptom">${d.symptom}</span>
                                <span class="diagnose-issue">→ ${d.issue}</span>
                            </div>
                            <span class="diagnose-severity ${d.severity}">${d.severity}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="ticket-items">
                <h5>Extracted Job Lines</h5>
                <ul style="padding-left: 20px; font-size:12px;">
                    ${lineItems.map(item => `
                        <li>${item.name_th} (${item.qty} ${item.type === 'part' ? 'ชิ้น' : 'ชม.'}) - ฿${item.total.toLocaleString()}</li>
                    `).join('')}
                </ul>
            </div>
            
            <div class="ticket-pricing">
                <div>
                    <span style="font-size:11px; color:var(--text-muted);">Est. Job Cost</span>
                    <div class="pricing-total">฿${ticket.total_estimated_cost.toLocaleString()}</div>
                </div>
                <div class="pricing-breakdown">
                    Labor: ฿${ticket.estimated_labor_cost.toLocaleString()}<br>
                    Parts: ฿${ticket.estimated_parts_cost.toLocaleString()}
                </div>
            </div>
            ${actionsHtml}
        `;
        deck.appendChild(card);
    });
    lucide.createIcons();
}

async function approveTicket(ticketId) {
    // Show approval modal
    const modal = document.getElementById('approve-modal');
    document.getElementById('approve-modal-ticket-id').innerText = `#${ticketId}`;
    document.getElementById('approve-mechanic-name').value = '';
    document.getElementById('approve-mechanic-notes').value = '';
    document.getElementById('approve-final-cost').value = '';
    modal.style.display = 'flex';
    
    // Store ticketId for submit
    modal.dataset.ticketId = ticketId;
}

async function submitTicketApproval() {
    const modal = document.getElementById('approve-modal');
    const ticketId = modal.dataset.ticketId;
    const mechanicName = document.getElementById('approve-mechanic-name').value.trim();
    const mechanicNotes = document.getElementById('approve-mechanic-notes').value.trim();
    const finalCostVal = document.getElementById('approve-final-cost').value.trim();
    
    if (!mechanicName) {
        showToast('Please enter your name before approving.', 'warning');
        return;
    }
    
    modal.style.display = 'none';
    
    try {
        const res = await fetch(`${API_URL}/tickets/${ticketId}/approve`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                approved_by: mechanicName,
                mechanic_notes: mechanicNotes || 'ตรวจสอบแล้ว อนุมัติตามรายการประเมิน',
                final_cost: finalCostVal ? parseFloat(finalCostVal) : null
            })
        });
        
        if (res.ok) {
            showToast(`Ticket #${ticketId} approved by ${mechanicName}!`);
            loadTickets();
            initOverview();
        } else {
            const err = await res.json();
            showToast("Failed to approve ticket: " + (err.detail || 'Unknown error'), 'danger');
        }
    } catch (e) {
        showToast("Error: " + e.message, 'danger');
    }
}

// ─── Finance Tab ──────────────────────────────────────────────────────────────
function initFinanceTab() {
    // Dropzone logic
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('bill-file');
    
    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            document.getElementById('selected-file-name').innerText = fileInput.files[0].name;
            showToast("File uploaded successfully into simulation!");
        }
    });

    // Bill Input Tab toggle
    const btnOcr = document.getElementById('btn-bill-tab-ocr');
    const btnText = document.getElementById('btn-bill-tab-text');
    const formUpload = document.getElementById('bill-upload-form');
    const formText = document.getElementById('bill-text-form');

    btnOcr.addEventListener('click', () => {
        btnOcr.classList.add('active');
        btnText.classList.remove('active');
        formUpload.classList.remove('hidden');
        formText.classList.add('hidden');
    });

    btnText.addEventListener('click', () => {
        btnText.classList.add('active');
        btnOcr.classList.remove('active');
        formText.classList.remove('hidden');
        formUpload.classList.add('hidden');
    });

    // Forms handling
    document.getElementById('bill-upload-form').addEventListener('submit', handleBillImageSubmit);
    document.getElementById('bill-text-form').addEventListener('submit', handleBillTextSubmit);
}

async function loadFinance() {
    loadLedger();
    renderFinanceChart();
}

async function loadLedger() {
    const tableBody = document.querySelector('#ledger-table tbody');
    tableBody.innerHTML = '<tr><td colspan="5" class="loading-placeholder">Loading ledger entries...</td></tr>';
    
    try {
        // Fetch last 3 months of ledger data starting June 2026 to August 2026
        // For simplicity, we call get bills and ledger entries
        const res = await fetch(`${API_URL}/finance/bills/`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to load bills");
        const billsData = await res.json();
        
        // We will fetch the monthly summaries to extract ledger entries or request lists
        // Since we want raw ledger entries, let's fetch individual summaries and compile,
        // or just fetch bills that compile ledger. Since backend seeds ledger entries, let's look at bills first.
        // Wait, the API table has ledger entry details. Let's see if we can get ledger list.
        // Wait, is there a GET `/api/v1/finance/ledger` or similar? Let's check `routers/finance.py`.
        // Let's retrieve summaries which returns the counts, or query list bills.
        // Let's check if the API has a ledger endpoint. If not, we can render the bills as ledger records.
        // Let's query `billsData.items` and display them!
        
        const bills = billsData.items || [];
        document.getElementById('ledger-count').innerText = `Total bills: ${bills.length}`;
        
        if (bills.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="loading-placeholder">No ledger records found.</td></tr>';
            return;
        }
        
        tableBody.innerHTML = '';
        bills.forEach(bill => {
            const tr = document.createElement('tr');
            
            // Format line items preview
            const lineItems = Array.isArray(bill.line_items) ? bill.line_items : [];
            const detailsText = lineItems.map(it => `${it.name} x${it.qty}`).join(', ');
            
            // Pending verify indicator
            let confirmActionHtml = '';
            if (bill.status === 'PENDING_CONFIRMATION') {
                confirmActionHtml = `
                    <button class="btn btn-filter btn-success" onclick="confirmBill(${bill.id})">
                        <i data-lucide="check"></i> Verify Math & Post
                    </button>
                `;
            } else if (bill.status === 'MATH_ERROR') {
                confirmActionHtml = `
                    <span class="ledger-type-badge expense" style="background-color:rgba(355,85,55,0.1); border:1px solid hsla(355,85,55,0.2);"><i data-lucide="x-circle" style="vertical-align:middle; width:12px; height:12px; margin-right:4px;"></i>Math Error</span>
                `;
            } else {
                confirmActionHtml = `
                    <span class="ledger-type-badge income" style="background-color:rgba(145,80,45,0.1); border:1px solid hsla(145,80,45,0.2);"><i data-lucide="check" style="vertical-align:middle; width:12px; height:12px; margin-right:4px;"></i>Posted</span>
                `;
            }

            tr.innerHTML = `
                <td>${new Date(bill.bill_date || bill.created_at).toLocaleDateString()}</td>
                <td><span class="ledger-type-badge ${bill.bill_type === 'income' ? 'income' : 'expense'}">${bill.bill_type.toUpperCase()}</span></td>
                <td>${bill.vendor_name || 'General'}</td>
                <td>
                    <div style="font-weight: 500;">${detailsText || bill.raw_input || 'Billing intake'}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">ID: #${bill.id} | Verified: ${bill.math_verified ? 'Yes' : 'No (Discrepancy: ฿' + bill.math_discrepancy + ')'}</div>
                </td>
                <td style="white-space:nowrap; vertical-align:middle;">
                    <div class="ledger-amount ${bill.bill_type === 'income' ? 'income' : 'expense'}" style="display:inline-block; margin-right:12px;">
                        ${bill.bill_type === 'income' ? '+' : '-'} ฿${(bill.calculated_total || bill.extracted_total || 0).toLocaleString()}
                    </div>
                    ${confirmActionHtml}
                </td>
            `;
            tableBody.appendChild(tr);
        });
        lucide.createIcons();
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="5" class="loading-placeholder text-danger">Error: ${err.message}</td></tr>`;
    }
}

async function confirmBill(billId) {
    try {
        const res = await fetch(`${API_URL}/finance/bills/${billId}/confirm`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({
                confirmed_by: 'ผู้จัดการการเงิน',
                notes: 'ตรวจบิลและตัวเลขเรียบร้อย ตรงกัน',
                corrected_items: null,
                corrected_total: null,
                entry_date: null
            })
        });
        
        if (res.ok) {
            showToast(`Bill #${billId} verified and written to ledger!`);
            loadFinance();
            initOverview();
        } else {
            const err = await res.json();
            showToast("Error posting bill: " + (err.detail || 'Unknown error'), 'danger');
        }
    } catch (e) {
        showToast("Error: " + e.message, 'danger');
    }
}

async function renderFinanceChart() {
    const ctx = document.getElementById('financeChart').getContext('2d');
    
    // Compile P&L summary of past 3 months (June, July, August 2026)
    try {
        // Query June, July, August summaries
        const periods = [
            { y: 2026, m: '06', label: 'June 2026' },
            { y: 2026, m: '07', label: 'July 2026' },
            { y: 2026, m: '08', label: 'August 2026' }
        ];
        
        let revenues = [];
        let expenses = [];
        let profits = [];
        
        for (let p of periods) {
            const res = await fetch(`${API_URL}/finance/summary/${p.y}/${p.m}`, { headers: getHeaders() });
            if (res.ok) {
                const data = await res.json();
                revenues.push(data.summary.total_income);
                expenses.push(data.summary.total_expense);
                profits.push(data.summary.net_profit);
            } else {
                revenues.push(0);
                expenses.push(0);
                profits.push(0);
            }
        }
        
        if (chartInstance) chartInstance.destroy();
        
        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['June 2026', 'July 2026', 'August 2026 (MTD)'],
                datasets: [
                    {
                        label: 'Revenue',
                        data: revenues,
                        backgroundColor: 'rgba(145, 80, 45, 0.7)',
                        borderColor: 'hsl(145, 80, 45)',
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Expenses',
                        data: expenses,
                        backgroundColor: 'rgba(355, 85, 55, 0.7)',
                        borderColor: 'hsl(355, 85, 55)',
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Net Profit',
                        data: profits,
                        backgroundColor: 'rgba(190, 90, 45, 0.7)',
                        borderColor: 'hsl(190, 90, 45)',
                        borderWidth: 1,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#e2e8f0',
                            font: { family: 'Inter' }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: {
                            color: '#94a3b8',
                            font: { family: 'Inter' },
                            callback: function(value) { return '฿' + value.toLocaleString(); }
                        }
                    }
                }
            }
        });
        
    } catch (err) {
        console.error("Error drawing chart", err);
    }
}

// Ingest Bill upload simulator
async function handleBillImageSubmit(e) {
    e.preventDefault();
    const mockScenario = document.getElementById('ocr-mock-type').value;
    const resultBox = document.getElementById('bill-result');
    const submitBtn = document.getElementById('btn-submit-bill');
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="spinner"></i> OCR Parsing & Verifying math...';
    resultBox.className = 'bill-result-box hidden';
    
    try {
        // Prepare mock values to simulate OCR based on selected scenario
        let formData = new FormData();
        // Append a mock empty image file
        const blob = new Blob(["mock_img"], { type: "image/png" });
        formData.append("file", blob, "receipt.png");
        
        // We will pass the scenario as custom header or path in mock OCR?
        // Wait, the API endpoint is `/api/v1/finance/bills/upload`
        // Let's check how the endpoint works. It processes a file upload.
        // Wait, since we want to trigger specific mock results, let's see how upload works.
        // Let's check `routers/finance.py` for `/bills/upload`.
        
        const uploadRes = await fetch(`${API_URL}/finance/bills/upload?scenario=${mockScenario}`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY
            },
            body: formData
        });
        
        const data = await uploadRes.json();
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="file-digit"></i> Ingest & Verify Bill';
        lucide.createIcons();
        
        resultBox.classList.remove('hidden');
        if (uploadRes.ok) {
            if (data.status === 'MATH_ERROR') {
                resultBox.className = 'bill-result-box result-error';
                resultBox.innerHTML = `
                    <h4 style="color:var(--color-danger); margin-bottom:8px;"><i data-lucide="alert-triangle"></i> Zero-Hallucination Guardrail Triggered!</h4>
                    <p><strong>Status:</strong> ${data.status} | <strong>Math Verified:</strong> ${data.math_verified ? 'Yes' : 'No'}</p>
                    <p><strong>Discrepancy:</strong> ฿${data.math_discrepancy.toLocaleString()}</p>
                    <p style="color:var(--text-muted); margin-top:8px;">${data.math_check_detail || 'Math discrepancy detected: Extracted sum of items does not match the invoice total total.'}</p>
                    <p style="margin-top:4px; font-weight:600; color:var(--color-danger);">⚠️ Booking is locked. Manual audit required.</p>
                `;
                showToast("Math error detected! Booking locked for auditing.", "warning");
            } else {
                resultBox.className = 'bill-result-box result-success';
                resultBox.innerHTML = `
                    <h4 style="color:var(--color-success); margin-bottom:8px;"><i data-lucide="check-circle"></i> Invoice Extracted & Math Verified</h4>
                    <p><strong>Bill ID:</strong> ${data.id} | <strong>Vendor:</strong> ${data.vendor_name}</p>
                    <p><strong>Calculated Total:</strong> ฿${data.calculated_total.toLocaleString()} | <strong>Math Verified:</strong> Yes</p>
                    <p style="margin-top:6px; font-weight:600;">Status: Pending final verification before posting to ledger.</p>
                `;
                showToast("Invoice processed and math verified.");
            }
            loadFinance();
            initOverview();
        } else {
            resultBox.className = 'bill-result-box result-error';
            resultBox.innerHTML = `<h4>Verification Failed</h4><p>${data.detail || 'Internal server error'}</p>`;
        }
        lucide.createIcons();
    } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="file-digit"></i> Ingest & Verify Bill';
        lucide.createIcons();
        resultBox.classList.remove('hidden');
        resultBox.className = 'bill-result-box result-error';
        resultBox.innerHTML = `<h4>Error</h4><p>${err.message}</p>`;
        showToast(err.message, 'danger');
    }
}

// Ingest Bill text form
async function handleBillTextSubmit(e) {
    e.preventDefault();
    const rawText = document.getElementById('bill-text').value;
    const resultBox = document.getElementById('bill-result');
    const submitBtn = document.getElementById('btn-submit-bill-text');
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="spinner"></i> Ingesting bill text...';
    resultBox.className = 'bill-result-box hidden';
    
    try {
        const res = await fetch(`${API_URL}/finance/expenses/parse-text`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                raw_text: rawText,
                bill_type: 'expense'
            })
        });
        
        const data = await res.json();
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="cpu"></i> Run Bill Parser Graph';
        lucide.createIcons();
        
        resultBox.classList.remove('hidden');
        if (res.ok) {
            resultBox.className = 'bill-result-box result-success';
            resultBox.innerHTML = `
                <h4 style="color:var(--color-success); margin-bottom:8px;"><i data-lucide="check-circle"></i> Bill Text Parsed Successfully!</h4>
                <p><strong>Bill ID:</strong> ${data.id} | <strong>Status:</strong> ${data.status}</p>
                <p><strong>Vendor Name:</strong> ${data.vendor_name || 'Not detected'}</p>
                <p><strong>Math Verified:</strong> ${data.math_verified ? 'Yes' : 'No'} (Discrepancy: ฿${data.math_discrepancy})</p>
                <p><strong>Total calculated:</strong> ฿${data.calculated_total.toLocaleString()}</p>
            `;
            showToast("Bill text ingested successfully.");
            loadFinance();
            initOverview();
        } else {
            resultBox.className = 'bill-result-box result-error';
            resultBox.innerHTML = `<h4>Parser Failed</h4><p>${data.detail || 'Internal server error'}</p>`;
        }
        lucide.createIcons();
    } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i data-lucide="cpu"></i> Run Bill Parser Graph';
        lucide.createIcons();
        resultBox.classList.remove('hidden');
        resultBox.className = 'bill-result-box result-error';
        resultBox.innerHTML = `<h4>Error</h4><p>${err.message}</p>`;
        showToast(err.message, 'danger');
    }
}

// ─── Customers Tab ────────────────────────────────────────────────────────────
let allCustomers = [];

function initCustomersTab() {
    document.getElementById('customer-search').addEventListener('input', renderCustomerListDeck);
}

async function loadCustomers() {
    const listDeck = document.getElementById('customer-list-deck');
    listDeck.innerHTML = '<p class="loading-placeholder">Loading customer records...</p>';
    
    try {
        const res = await fetch(`${API_URL}/customers/`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to load customers list");
        const data = await res.json();
        allCustomers = data.items || [];
        renderCustomerListDeck();
    } catch (err) {
        listDeck.innerHTML = `<p class="loading-placeholder text-danger">Error: ${err.message}</p>`;
    }
}

function renderCustomerListDeck() {
    const listDeck = document.getElementById('customer-list-deck');
    const searchVal = document.getElementById('customer-search').value.toLowerCase();
    
    let filtered = allCustomers;
    if (searchVal) {
        filtered = filtered.filter(c => {
            return c.name.toLowerCase().includes(searchVal) || c.phone.includes(searchVal);
        });
    }
    
    if (filtered.length === 0) {
        listDeck.innerHTML = '<p class="loading-placeholder">No customers found.</p>';
        return;
    }
    
    listDeck.innerHTML = '';
    filtered.forEach(customer => {
        const btn = document.createElement('button');
        btn.className = `customer-item-card ${selectedCustomerId === customer.id ? 'active' : ''}`;
        btn.innerHTML = `
            <h4>${customer.name}</h4>
            <p><i data-lucide="phone" style="display:inline; width:12px; height:12px; margin-right:4px; vertical-align:middle;"></i>${customer.phone}</p>
        `;
        btn.addEventListener('click', () => {
            selectedCustomerId = customer.id;
            renderCustomerListDeck(); // Update active selection class
            loadCustomerProfile360(customer.id);
        });
        listDeck.appendChild(btn);
    });
    lucide.createIcons();
}

async function loadCustomerProfile360(customerId) {
    const panel = document.getElementById('customer-profile-panel');
    panel.innerHTML = '<p class="loading-placeholder">Compiling customer 360° profile...</p>';
    
    try {
        const res = await fetch(`${API_URL}/customers/${customerId}/profile`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to load customer profile details");
        const profile = await res.json();
        
        let segmentClass = 'VIP';
        if (profile.customer_segment === 'At Risk') segmentClass = 'At Risk';
        if (profile.customer_segment === 'Churned') segmentClass = 'Churned';
        
        panel.innerHTML = `
            <div class="profile-header-block">
                <div class="profile-meta">
                    <h3>${profile.customer.name}</h3>
                    <div class="profile-contact">
                        <span><i data-lucide="phone"></i> ${profile.customer.phone}</span>
                        <span><i data-lucide="message-circle"></i> LINE: ${profile.customer.line_id || '-'}</span>
                        <span><i data-lucide="mail"></i> ${profile.customer.email || '-'}</span>
                    </div>
                </div>
                <span class="profile-segment-pill">${profile.customer_segment}</span>
            </div>
            
            <div class="section-divider">Associated Vehicles</div>
            <div class="vehicles-deck">
                ${profile.vehicles.map(v => {
                    return `
                        <div class="vehicle-card">
                            <div class="vehicle-header-row">
                                <span class="vehicle-model">${v.brand} ${v.model}</span>
                                <span class="vehicle-plate">${v.plate}</span>
                            </div>
                            <div class="vehicle-stats">
                                <div>Year: <strong>${v.year || 'N/A'}</strong></div>
                                <div>Color: <strong>${v.color || 'N/A'}</strong></div>
                                <div>Mileage: <strong>${v.current_mileage.toLocaleString()} km</strong></div>
                                <div>Last Service: <strong>${v.last_service_date ? new Date(v.last_service_date).toLocaleDateString() : 'N/A'}</strong></div>
                            </div>
                            <div class="vehicle-health-summary">
                                <span style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">Health Watchlist:</span>
                                <div style="margin-top: 6px;">
                                    ${v.health_watchlist.length === 0 ? '<span style="color:var(--color-success); font-size:12px;"><i data-lucide="check-circle" style="display:inline; width:12px; height:12px; margin-right:4px; vertical-align:middle;"></i>All systems nominal</span>' : 
                                    v.health_watchlist.map(w => `
                                        <div style="font-size:12px; margin-bottom:4px; color:${w.is_overdue ? 'var(--color-danger)' : 'var(--color-warning)'}">
                                            <i data-lucide="${w.is_overdue ? 'alert-triangle' : 'alert-circle'}" style="display:inline; width:12px; height:12px; margin-right:4px; vertical-align:middle;"></i>
                                            <strong>${w.component}</strong>: ${w.condition}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>

            <div class="section-divider">Service Ticket History</div>
            <div class="table-responsive">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Ticket ID</th>
                            <th>Description</th>
                            <th>Symptoms</th>
                            <th>Status</th>
                            <th>Final Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${profile.ticket_history.length === 0 ? '<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:16px;">No service visits on file.</td></tr>' : 
                        profile.ticket_history.map(t => {
                            const symptoms = Array.isArray(t.extracted_symptoms) ? t.extracted_symptoms : [];
                            return `
                                <tr>
                                    <td>#${t.id}</td>
                                    <td>"${t.raw_input.substring(0, 50)}..."</td>
                                    <td>${symptoms.join(', ') || '-'}</td>
                                    <td><span class="ticket-status-badge ${t.status === 'APPROVED' ? 'approved' : 'pending'}">${t.status}</span></td>
                                    <td style="font-weight:600;">฿${(t.final_cost || t.total_estimated_cost || 0).toLocaleString()}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>

            <div class="section-divider" style="margin-top:32px;">Intake Summary & Metrics</div>
            <div class="stats-grid" style="margin-bottom:0;">
                <div class="stat-card" style="padding:16px;">
                    <div class="stat-info">
                        <h3>Total Spend</h3>
                        <p class="stat-value" style="font-size:18px;">฿${profile.total_spent.toLocaleString()}</p>
                    </div>
                </div>
                <div class="stat-card" style="padding:16px;">
                    <div class="stat-info">
                        <h3>Total Visits</h3>
                        <p class="stat-value" style="font-size:18px;">${profile.total_visits} times</p>
                    </div>
                </div>
                <div class="stat-card" style="padding:16px;">
                    <div class="stat-info">
                        <h3>Last Visit Date</h3>
                        <p class="stat-value" style="font-size:16px; font-family:var(--font-body); font-weight:600;">${profile.last_visit_date ? new Date(profile.last_visit_date).toLocaleDateString() : 'N/A'}</p>
                    </div>
                </div>
            </div>
        `;
        lucide.createIcons();
    } catch (err) {
        panel.innerHTML = `<p class="loading-placeholder text-danger">Error: ${err.message}</p>`;
    }
}

// ─── LINE Marketing Retention Tab ─────────────────────────────────────────────
let allMarketingTasks = [];

function initMarketingTab() {
    document.getElementById('btn-marketing-scan').addEventListener('click', runRetentionScan);
}

async function loadMarketing() {
    const list = document.getElementById('marketing-tasks-list');
    list.innerHTML = '<p class="loading-placeholder">Loading marketing retention campaigns...</p>';
    
    try {
        const res = await fetch(`${API_URL}/marketing/tasks/`, { headers: getHeaders() });
        if (!res.ok) throw new Error("Failed to load marketing tasks queue");
        const data = await res.json();
        allMarketingTasks = data.items || [];
        renderMarketingTasks();
    } catch (err) {
        list.innerHTML = `<p class="loading-placeholder text-danger">Error: ${err.message}</p>`;
    }
}

function renderMarketingTasks() {
    const list = document.getElementById('marketing-tasks-list');
    if (allMarketingTasks.length === 0) {
        list.innerHTML = '<p class="loading-placeholder">No campaign messages generated yet. Run a retention scan to fetch candidates!</p>';
        return;
    }
    
    list.innerHTML = '';
    allMarketingTasks.forEach(task => {
        const card = document.createElement('div');
        card.className = 'marketing-task-card';
        
        let actionsHtml = '';
        if (task.status === 'PENDING_ADMIN_APPROVAL') {
            actionsHtml = `
                <div class="ticket-actions" style="margin-top:10px;">
                    <button class="btn btn-danger btn-sm" onclick="rejectMarketingTask(${task.id})">
                        <i data-lucide="x"></i> Dismiss
                    </button>
                    <button class="btn btn-success btn-sm" onclick="approveMarketingTask(${task.id})">
                        <i data-lucide="check"></i> Dispatch to LINE OA
                    </button>
                </div>
            `;
        } else {
            actionsHtml = `
                <div class="ticket-actions" style="margin-top:10px;">
                    <span style="font-size:12px; color:var(--color-success); font-weight:600;"><i data-lucide="check-circle" style="display:inline; width:14px; height:14px; margin-right:4px; vertical-align:middle;"></i>Dispatched to LINE</span>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="task-header-row">
                <div class="task-meta">
                    <h4>${task.customer_name} (${task.vehicle_plate || 'General'})</h4>
                    <p>Trigger logic: <strong>${task.trigger_type}</strong> | Generated: ${new Date(task.created_at).toLocaleDateString()}</p>
                </div>
                <span class="task-badge ${task.status === 'DISPATCHED' ? 'approved' : ''}">${task.status}</span>
            </div>
            
            <div class="task-msg-body">
                ${task.draft_message}
            </div>
            
            <div class="task-voucher-row">
                <div>Voucher: <strong>${task.voucher_code || 'None'}</strong></div>
                <div>Discount Amount: <strong>฿${(task.discount_amount || 0).toLocaleString()}</strong></div>
            </div>
            ${actionsHtml}
        `;
        list.appendChild(card);
    });
    lucide.createIcons();
}

async function runRetentionScan() {
    const btn = document.getElementById('btn-marketing-scan');
    const headerBtn = document.getElementById('btn-trigger-retention');
    
    const setBtnsLoading = (loading) => {
        if (loading) {
            btn.disabled = headerBtn.disabled = true;
            btn.innerHTML = headerBtn.innerHTML = '<i class="spinner"></i> Running database scan...';
        } else {
            btn.disabled = headerBtn.disabled = false;
            btn.innerHTML = '<i data-lucide="scan"></i> Execute Retention Scan Now';
            headerBtn.innerHTML = '<i data-lucide="refresh-cw"></i> Scan Retention';
        }
        lucide.createIcons();
    };
    
    setBtnsLoading(true);
    try {
        const res = await fetch(`${API_URL}/marketing/triggers/run-cron`, {
            method: 'POST',
            headers: getHeaders()
        });
        
        setBtnsLoading(false);
        if (res.ok) {
            const data = await res.json();
            showToast(`Scan complete. Flagged ${data.total_flagged} targets. Generated ${data.tasks_generated} approvals!`);
            
            // Reload whatever tab is active
            if (activeTab === 'overview') {
                initOverview();
            } else if (activeTab === 'marketing') {
                loadMarketing();
            }
        } else {
            showToast("Failed to run retention scan", "danger");
        }
    } catch (e) {
        setBtnsLoading(false);
        showToast("Error scanning: " + e.message, "danger");
    }
}

async function approveMarketingTask(taskId) {
    try {
        // Fetch target task content to simulate dispatch preview
        const task = allMarketingTasks.find(t => t.id === taskId);
        
        const res = await fetch(`${API_URL}/marketing/tasks/${taskId}/approve`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                approved_by: 'ผู้จัดการสาขา',
                edited_message: null
            })
        });
        
        if (res.ok) {
            showToast(`LINE Retention Message #${taskId} approved and dispatched!`);
            loadMarketing();
            initOverview();
            
            // Update LINE Phone Mockup Simulator
            if (task) {
                simulateLineMessage(task.draft_message);
            }
        } else {
            const err = await res.json();
            showToast("Failed to dispatch campaign: " + (err.detail || 'Unknown error'), 'danger');
        }
    } catch (e) {
        showToast("Error: " + e.message, 'danger');
    }
}

async function rejectMarketingTask(taskId) {
    try {
        const res = await fetch(`${API_URL}/marketing/tasks/${taskId}/reject`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                rejected_by: 'ผู้จัดการสาขา',
                reason: 'ยกเลิกแคมเปญชั่วคราว ลูกค้าโทรเข้ามาสอบถามข้อมูลแล้ว'
            })
        });
        
        if (res.ok) {
            showToast(`LINE message #${taskId} dismissed.`);
            loadMarketing();
            initOverview();
        } else {
            const err = await res.json();
            showToast("Error dismissing task: " + (err.detail || 'Unknown error'), 'danger');
        }
    } catch (e) {
        showToast("Error: " + e.message, 'danger');
    }
}

function simulateLineMessage(messageText) {
    const chatContainer = document.getElementById('simulated-chat-messages');
    chatContainer.innerHTML = ''; // Clear empty state system logs
    
    const bubble = document.createElement('div');
    bubble.className = 'simulated-bubble';
    bubble.innerText = messageText;
    chatContainer.appendChild(bubble);
}
