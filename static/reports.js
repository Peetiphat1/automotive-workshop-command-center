/**
 * REPORTS CONTROLLER (ศูนย์รวมรายงาน)
 * Handles Hub view, 7 Sub-report views, date range queries,
 * interactive tables with live search, CSV export, and chart rendering.
 */

(function () {
    // ── State ────────────────────────────────────────────────────────────────
    let currentReport = 'hub';
    const reportDataCache = {};
    const tableManagers = {};

    // ── Date Helpers ─────────────────────────────────────────────────────────
    function getMonthDateRange() {
        const now = new Date();
        const y = now.getFullYear();
        const m = now.getMonth();
        const first = new Date(y, m, 1);
        const toYYYYMMDD = (d) => {
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            return `${d.getFullYear()}-${mm}-${dd}`;
        };
        return {
            start: toYYYYMMDD(first),
            end: toYYYYMMDD(now),
        };
    }

    function formatThaiDateRange(startStr, endStr) {
        if (!startStr || !endStr) return '';
        const fmt = (s) => {
            const parts = s.split('-');
            if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
            return s;
        };
        return `(${fmt(startStr)} - ${fmt(endStr)})`;
    }

    function formatNumber(val, decimals = 2) {
        const num = parseFloat(val) || 0;
        return num.toLocaleString('th-TH', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    // ── CSV Export Utility (UTF-8 BOM for Thai support in Excel) ─────────────
    function exportToCSV(filename, tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        let csv = '\uFEFF'; // UTF-8 BOM
        const rows = table.querySelectorAll('tr');

        rows.forEach((row) => {
            // Ignore empty state rows
            if (row.querySelector('.empty-report-msg')) return;

            const cols = row.querySelectorAll('th, td');
            const rowData = [];
            cols.forEach((col) => {
                let text = col.innerText.replace(/[\n\r]+/g, ' ').replace(/"/g, '""').trim();
                rowData.push(`"${text}"`);
            });
            if (rowData.length > 0) {
                csv += rowData.join(',') + '\r\n';
            }
        });

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.setAttribute('download', `${filename}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // ── Generic Table Manager with Search, Sort, and Pagination ─────────────
    class TableManager {
        constructor(opts) {
            this.tableId = opts.tableId;
            this.tbodyId = opts.tbodyId;
            this.searchId = opts.searchId;
            this.selectId = opts.selectId;
            this.paginationId = opts.paginationId;
            this.renderRow = opts.renderRow;
            this.emptyCols = opts.emptyCols || 5;
            this.allRows = [];
            this.filteredRows = [];
            this.currentPage = 1;
            this.pageSize = 25;

            this.initListeners();
        }

        initListeners() {
            if (this.searchId) {
                const sEl = document.getElementById(this.searchId);
                if (sEl) {
                    sEl.addEventListener('input', (e) => {
                        this.filter(e.target.value);
                    });
                }
            }
            if (this.selectId) {
                const pEl = document.getElementById(this.selectId);
                if (pEl) {
                    pEl.addEventListener('change', (e) => {
                        this.pageSize = parseInt(e.target.value, 10) || 25;
                        this.currentPage = 1;
                        this.render();
                    });
                }
            }
        }

        setData(rows) {
            this.allRows = rows || [];
            this.filter(document.getElementById(this.searchId)?.value || '');
        }

        filter(query) {
            const q = (query || '').toLowerCase().trim();
            if (!q) {
                this.filteredRows = [...this.allRows];
            } else {
                this.filteredRows = this.allRows.filter((r) => {
                    return Object.values(r).some((v) =>
                        String(v).toLowerCase().includes(q)
                    );
                });
            }
            this.currentPage = 1;
            this.render();
        }

        render() {
            const tbody = document.getElementById(this.tbodyId);
            if (!tbody) return;

            if (this.filteredRows.length === 0) {
                tbody.innerHTML = `<tr><td colspan="${this.emptyCols}" class="empty-report-msg">ไม่มีข้อมูลในช่วงเวลานี้</td></tr>`;
                this.renderPagination(0);
                return;
            }

            const total = this.filteredRows.length;
            const startIdx = (this.currentPage - 1) * this.pageSize;
            const endIdx = Math.min(startIdx + this.pageSize, total);
            const pageRows = this.filteredRows.slice(startIdx, endIdx);

            tbody.innerHTML = pageRows.map((r, i) => this.renderRow(r, startIdx + i + 1)).join('');

            this.renderPagination(total, startIdx + 1, endIdx);
            if (window.lucide) lucide.createIcons();
        }

        renderPagination(total, start = 0, end = 0) {
            const pEl = document.getElementById(this.paginationId);
            if (!pEl) return;

            if (total === 0) {
                pEl.innerHTML = `<span>แสดง 0 รายการ</span>`;
                return;
            }

            const totalPages = Math.ceil(total / this.pageSize) || 1;
            let btnsHtml = `
                <button class="report-page-btn" ${this.currentPage <= 1 ? 'disabled' : ''} onclick="window.reportsApp.changePage('${this.tableId}', ${this.currentPage - 1})">ก่อนหน้า</button>
            `;
            for (let p = 1; p <= totalPages; p++) {
                if (totalPages > 7 && Math.abs(p - this.currentPage) > 2 && p !== 1 && p !== totalPages) {
                    if (p === 2 || p === totalPages - 1) btnsHtml += `<span style="padding:4px 6px;color:#64748b;">...</span>`;
                    continue;
                }
                btnsHtml += `
                    <button class="report-page-btn ${p === this.currentPage ? 'active' : ''}" onclick="window.reportsApp.changePage('${this.tableId}', ${p})">${p}</button>
                `;
            }
            btnsHtml += `
                <button class="report-page-btn" ${this.currentPage >= totalPages ? 'disabled' : ''} onclick="window.reportsApp.changePage('${this.tableId}', ${this.currentPage + 1})">ถัดไป</button>
            `;

            pEl.innerHTML = `
                <span>แสดง ${start}-${end} จาก ${total} รายการ</span>
                <div class="report-pagination-btns">${btnsHtml}</div>
            `;
        }

        setPage(page) {
            this.currentPage = page;
            this.render();
        }
    }

    // ── Daily Sales Chart Renderer ──────────────────────────────────────────
    let salesChartInstance = null;

    function drawDailySalesChart(canvasId, dailyData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Use Chart.js if available (with tooltips, hover effects, and animations)
        if (window.Chart) {
            const labels = (dailyData || []).map((d) => d.day_label || d.date);
            const posData = (dailyData || []).map((d) => d.pos_sales || 0);
            const repairData = (dailyData || []).map((d) => d.repair_sales || 0);
            const totalData = (dailyData || []).map((d) => d.total || 0);
            const maxVal = Math.max(...totalData, 0);

            // Update existing chart instance if canvas matches
            if (salesChartInstance && salesChartInstance.ctx && salesChartInstance.ctx.canvas === canvas) {
                salesChartInstance.data.labels = labels;
                salesChartInstance.data.datasets[0].data = posData;
                salesChartInstance.data.datasets[1].data = repairData;
                if (salesChartInstance.options.scales && salesChartInstance.options.scales.y) {
                    salesChartInstance.options.scales.y.suggestedMax = maxVal > 0 ? undefined : 1.0;
                }
                salesChartInstance.update();
                return;
            }

            if (salesChartInstance) {
                salesChartInstance.destroy();
                salesChartInstance = null;
            }

            const ctx = canvas.getContext('2d');
            salesChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'ยอดขายอะไหล่ (POS)',
                            data: posData,
                            backgroundColor: 'rgba(56, 189, 248, 0.85)',
                            hoverBackgroundColor: 'rgba(56, 189, 248, 1)',
                            borderColor: '#38bdf8',
                            borderWidth: 1,
                            borderRadius: 4,
                            stack: 'salesStack',
                        },
                        {
                            label: 'ยอดงานซ่อม',
                            data: repairData,
                            backgroundColor: 'rgba(52, 211, 153, 0.85)',
                            hoverBackgroundColor: 'rgba(52, 211, 153, 1)',
                            borderColor: '#34d399',
                            borderWidth: 1,
                            borderRadius: 4,
                            stack: 'salesStack',
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 650,
                        easing: 'easeOutQuart'
                    },
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            align: 'end',
                            labels: {
                                color: '#94a3b8',
                                font: { family: 'Kanit, sans-serif', size: 12 },
                                boxWidth: 12,
                                boxHeight: 12,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                padding: 16,
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#f8fafc',
                            titleFont: { family: 'Kanit, sans-serif', size: 13, weight: '600' },
                            bodyColor: '#cbd5e1',
                            bodyFont: { family: 'Kanit, sans-serif', size: 12 },
                            borderColor: 'rgba(255, 255, 255, 0.15)',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 4,
                            usePointStyle: true,
                            callbacks: {
                                label: function(context) {
                                    const val = Number(context.raw || 0);
                                    return ` ${context.dataset.label}: ${val.toLocaleString('th-TH', {minimumFractionDigits: 2})} ฿`;
                                },
                                footer: function(tooltipItems) {
                                    let sum = 0;
                                    tooltipItems.forEach(item => { sum += (Number(item.raw) || 0); });
                                    return `รวมทั้งสิ้น: ${sum.toLocaleString('th-TH', {minimumFractionDigits: 2})} ฿`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            stacked: true,
                            grid: {
                                display: false,
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: { family: 'Kanit, sans-serif', size: 11 },
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 15,
                            }
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            suggestedMax: maxVal > 0 ? undefined : 1.0,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.06)',
                                borderDash: [4, 4],
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: { family: 'Kanit, sans-serif', size: 11 },
                                callback: function(value) {
                                    return value.toLocaleString('th-TH') + ' ฿';
                                }
                            }
                        }
                    }
                }
            });
            return;
        }

        // Fallback to pure 2D Canvas if Chart.js is not loaded
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        if (!dailyData || dailyData.length === 0) {
            ctx.fillStyle = '#64748b';
            ctx.font = '14px Kanit, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('ไม่มีข้อมูลยอดขายรายวัน', w / 2, h / 2);
            return;
        }

        const padLeft = 55;
        const padBottom = 35;
        const padTop = 20;
        const padRight = 20;
        const plotW = w - padLeft - padRight;
        const plotH = h - padTop - padBottom;

        const maxVal = Math.max(...dailyData.map((d) => d.total || 0), 100);

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.07)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#94a3b8';
        ctx.font = '11px Kanit, sans-serif';
        ctx.textAlign = 'right';

        const steps = 4;
        for (let s = 0; s <= steps; s++) {
            const y = padTop + plotH - (s / steps) * plotH;
            const val = Math.round((s / steps) * maxVal);
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(w - padRight, y);
            ctx.stroke();
            ctx.fillText(val.toLocaleString('th-TH'), padLeft - 8, y + 4);
        }

        const barGroupW = plotW / dailyData.length;
        const barW = Math.max(6, Math.min(barGroupW * 0.65, 36));

        dailyData.forEach((d, idx) => {
            const x = padLeft + idx * barGroupW + (barGroupW - barW) / 2;
            const barH = ((d.total || 0) / maxVal) * plotH;
            const y = padTop + plotH - barH;

            const grad = ctx.createLinearGradient(0, y, 0, padTop + plotH);
            grad.addColorStop(0, '#38bdf8');
            grad.addColorStop(1, '#0284c7');
            ctx.fillStyle = grad;

            ctx.beginPath();
            ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0]);
            ctx.fill();

            const step = dailyData.length > 20 ? 3 : (dailyData.length > 10 ? 2 : 1);
            if (idx % step === 0 || idx === dailyData.length - 1) {
                ctx.fillStyle = '#94a3b8';
                ctx.textAlign = 'center';
                ctx.fillText(d.day_label || '', x + barW / 2, h - 12);
            }
        });
    }

    // ── Navigation Functions ────────────────────────────────────────────────
    function showReportHub(updateHash = true) {
        currentReport = 'hub';
        document.querySelectorAll('.subreport-view').forEach((el) => el.classList.remove('active'));
        const hub = document.getElementById('report-hub-view');
        if (hub) hub.classList.add('active');

        const title = document.getElementById('report-page-title');
        if (title) title.innerHTML = `<i data-lucide="layout-grid"></i> ศูนย์รวมรายงาน`;
        if (window.lucide) lucide.createIcons();

        if (updateHash) {
            try {
                localStorage.setItem('activeTab', 'reports');
                localStorage.removeItem('activeSubReport');
                if (window.location.hash !== '#reports') {
                    history.replaceState(null, '', '#reports');
                }
            } catch (_) {}
        }
    }

    function openReport(reportKey, updateHash = true) {
        currentReport = reportKey;
        document.querySelectorAll('.subreport-view').forEach((el) => el.classList.remove('active'));

        const target = document.getElementById(`report-${reportKey}-view`);
        if (target) target.classList.add('active');

        const titles = {
            sales: 'รายงานยอดขาย',
            topParts: 'อะไหล่ขายดี',
            stock: 'รายงานสต็อก',
            mechanics: 'รายงานช่าง',
            customers: 'รายงานลูกค้า',
            profit: 'รายงานกำไร-ขาดทุน',
            tax: 'รายงานภาษีขาย',
            dailyClose: 'ปิดยอดประจำวัน',
            jobProfit: 'กำไรรายงาน',
            outstanding: 'ลูกค้าค้างชำระ',
        };

        const title = document.getElementById('report-page-title');
        if (title) title.innerHTML = `<i data-lucide="menu"></i> ${titles[reportKey] || 'รายงาน'}`;

        if (updateHash) {
            try {
                localStorage.setItem('activeTab', 'reports');
                localStorage.setItem('activeSubReport', reportKey);
                if (window.location.hash !== `#reports/${reportKey}`) {
                    history.replaceState(null, '', `#reports/${reportKey}`);
                }
            } catch (_) {}
        }

        // Initialize default dates if empty
        const startInput = document.getElementById(`${reportKey}-start-date`);
        const endInput = document.getElementById(`${reportKey}-end-date`);
        const range = getMonthDateRange();
        if (startInput && !startInput.value) startInput.value = range.start;
        if (endInput && !endInput.value) endInput.value = range.end;

        // Auto-refresh when user changes either start or end date
        let autoFilterTimeout = null;
        const onDateChange = () => {
            if (autoFilterTimeout) clearTimeout(autoFilterTimeout);
            autoFilterTimeout = setTimeout(() => {
                loadReportData(reportKey);
            }, 200);
        };
        if (startInput && !startInput.dataset.listenerAttached) {
            startInput.dataset.listenerAttached = 'true';
            startInput.addEventListener('change', onDateChange);
            startInput.addEventListener('input', onDateChange);
        }
        if (endInput && !endInput.dataset.listenerAttached) {
            endInput.dataset.listenerAttached = 'true';
            endInput.addEventListener('change', onDateChange);
            endInput.addEventListener('input', onDateChange);
        }

        // Fetch & load
        loadReportData(reportKey);
        if (window.lucide) lucide.createIcons();
    }

    // ── API Fetch & Loaders ─────────────────────────────────────────────────
    async function loadReportData(key) {
        const startInput = document.getElementById(`${key}-start-date`);
        const endInput = document.getElementById(`${key}-end-date`);
        const s = startInput ? startInput.value : '';
        const e = endInput ? endInput.value : '';

        const activeView = document.getElementById(`report-${key}-view`);
        const filterBtn = activeView ? activeView.querySelector('.btn-report-filter') : null;
        if (filterBtn) {
            filterBtn.classList.add('loading');
            filterBtn.innerHTML = '<span class="report-spinner"></span> แสดงรายงาน';
        }

        // Safety timeout to ensure button never stays in loading state
        setTimeout(() => {
            if (filterBtn && filterBtn.classList.contains('loading')) {
                filterBtn.classList.remove('loading');
                filterBtn.disabled = false;
                filterBtn.innerHTML = 'แสดงรายงาน';
                filterBtn.style.opacity = '1';
            }
        }, 2500);

        try {
            switch (key) {
                case 'sales':
                    await fetchSalesReport(s, e);
                    break;
                case 'topParts':
                    await fetchTopPartsReport(s, e);
                    break;
                case 'stock':
                    await fetchStockReport();
                    break;
                case 'mechanics':
                    await fetchMechanicsReport(s, e);
                    break;
                case 'customers':
                    await fetchCustomersReport(s, e);
                    break;
                case 'profit':
                    await fetchProfitReport(s, e);
                    break;
                case 'tax':
                    await fetchTaxReport(s, e);
                    break;
                case 'dailyClose':
                    await fxReports.dailyClose();
                    break;
                case 'jobProfit':
                    await fxReports.jobProfit(s, e);
                    break;
                case 'outstanding':
                    await fxReports.outstanding();
                    break;
            }
        } catch (err) {
            console.error(`Error loading report ${key}:`, err);
        } finally {
            if (filterBtn) {
                filterBtn.classList.remove('loading');
                filterBtn.disabled = false;
                filterBtn.innerHTML = 'แสดงรายงาน';
                filterBtn.style.opacity = '1';
            }
        }
    }

    // 1. Sales Report
    async function fetchSalesReport(start, end) {
        const url = `/api/v1/reports/sales?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        // Update KPI cards
        const partsEl = document.getElementById('sales-kpi-parts');
        const repairEl = document.getElementById('sales-kpi-repair');
        const grandEl = document.getElementById('sales-kpi-grand');
        if (partsEl) partsEl.innerText = formatNumber(data.pos_parts_total);
        if (repairEl) repairEl.innerText = formatNumber(data.repair_total);
        if (grandEl) grandEl.innerText = formatNumber(data.grand_total);

        // Render Chart
        drawDailySalesChart('sales-daily-chart', data.daily_sales);

        // Setup table
        if (!tableManagers['sales-table']) {
            tableManagers['sales-table'] = new TableManager({
                tableId: 'sales-table',
                tbodyId: 'sales-tbody',
                searchId: 'sales-search-input',
                selectId: 'sales-entries-select',
                paginationId: 'sales-pagination',
                emptyCols: 6,
                renderRow: (r) => `
                    <tr>
                        <td>${r.date}</td>
                        <td><strong>${r.doc_no}</strong></td>
                        <td>${r.customer}</td>
                        <td>${r.vehicle}</td>
                        <td><span class="status-badge" style="background:rgba(56,189,248,0.15);color:#38bdf8;padding:2px 8px;border-radius:4px;">${r.type}</span></td>
                        <td class="text-right font-mono" style="font-weight:600;color:#f8fafc;">${formatNumber(r.amount)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['sales-table'].setData(data.items || []);
    }

    // 2. Top Parts Report
    async function fetchTopPartsReport(start, end) {
        const url = `/api/v1/reports/top-parts?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const titleEl = document.getElementById('topparts-card-title');
        if (titleEl) {
            titleEl.innerText = `อะไหล่ขายดี ${formatThaiDateRange(start, end)}`;
        }

        if (!tableManagers['topparts-table']) {
            tableManagers['topparts-table'] = new TableManager({
                tableId: 'topparts-table',
                tbodyId: 'topparts-tbody',
                searchId: 'topparts-search-input',
                selectId: 'topparts-entries-select',
                paginationId: 'topparts-pagination',
                emptyCols: 5,
                renderRow: (r, idx) => `
                    <tr>
                        <td class="text-center font-bold" style="color:${idx <= 3 ? '#fbbf24' : '#94a3b8'};">${idx}</td>
                        <td><code>${r.sku || '-'}</code></td>
                        <td><strong>${r.name}</strong></td>
                        <td class="text-center">${r.quantity_sold}</td>
                        <td class="text-right font-mono" style="font-weight:600;color:#38bdf8;">${formatNumber(r.total_revenue)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['topparts-table'].setData(data.items || []);
    }

    // 3. Stock Report
    async function fetchStockReport() {
        const url = `/api/v1/reports/stock`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const kpiEl = document.getElementById('stock-total-cost-val');
        const footerEl = document.getElementById('stock-footer-total');
        const formatted = `${formatNumber(data.total_cost_valuation)} ฿`;
        if (kpiEl) kpiEl.innerText = formatted;
        if (footerEl) footerEl.innerText = formatNumber(data.total_cost_valuation);

        if (!tableManagers['stock-report-table']) {
            tableManagers['stock-report-table'] = new TableManager({
                tableId: 'stock-report-table',
                tbodyId: 'stock-report-tbody',
                searchId: 'stock-report-search',
                selectId: 'stock-report-entries-select',
                paginationId: 'stock-report-pagination',
                emptyCols: 6,
                renderRow: (r) => `
                    <tr>
                        <td><code>${r.sku}</code></td>
                        <td><strong>${r.name}</strong></td>
                        <td><span style="color:#94a3b8;font-size:0.83rem;">${r.category}</span></td>
                        <td class="text-center font-bold" style="color:${r.quantity <= 5 ? '#f87171' : '#f8fafc'};">${r.quantity}</td>
                        <td class="text-right font-mono">${formatNumber(r.unit_cost)}</td>
                        <td class="text-right font-mono" style="font-weight:600;color:#f8fafc;">${formatNumber(r.total_value)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['stock-report-table'].setData(data.items || []);
    }

    // 4. Mechanics Report
    async function fetchMechanicsReport(start, end) {
        const pctEl = document.getElementById('mechanics-commission');
        const pct = pctEl && pctEl.value !== '' ? `&commission_pct=${encodeURIComponent(pctEl.value)}` : '';
        const url = `/api/v1/reports/mechanics?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}${pct}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (pctEl && pctEl.value === '') pctEl.placeholder = `${data.commission_rate}`;

        const titleEl = document.getElementById('mechanics-card-title');
        if (titleEl) {
            titleEl.innerText = `ผลงานช่าง ${formatThaiDateRange(start, end)}`;
        }

        if (!tableManagers['mechanics-table']) {
            tableManagers['mechanics-table'] = new TableManager({
                tableId: 'mechanics-table',
                tbodyId: 'mechanics-tbody',
                searchId: 'mechanics-search-input',
                selectId: 'mechanics-entries-select',
                paginationId: 'mechanics-pagination',
                emptyCols: 8,
                renderRow: (r) => `
                    <tr>
                        <td><strong>${r.mechanic_name}</strong></td>
                        <td class="text-center">${r.jobs_count}</td>
                        <td class="text-center">${r.completed_count ?? ''}</td>
                        <td class="text-center" style="color:${r.open_jobs ? '#fbbf24' : 'inherit'};">${r.open_jobs ?? ''}</td>
                        <td class="text-right font-mono">${formatNumber(r.total_revenue || 0)}</td>
                        <td class="text-right font-mono">${formatNumber(r.total_labor)}</td>
                        <td class="text-center">${r.commission_rate}%</td>
                        <td class="text-right font-mono" style="font-weight:600;color:#34d399;">${formatNumber(r.commission_amount)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['mechanics-table'].setData(data.items || []);
    }

    // 5. Top Customers Report
    async function fetchCustomersReport(start, end) {
        const url = `/api/v1/reports/customers?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const titleEl = document.getElementById('customers-card-title');
        if (titleEl) {
            titleEl.innerText = `ลูกค้าที่ใช้จ่ายสูงสุด ${formatThaiDateRange(start, end)}`;
        }

        if (!tableManagers['customers-table']) {
            tableManagers['customers-table'] = new TableManager({
                tableId: 'customers-table',
                tbodyId: 'report-customers-tbody',
                searchId: 'customers-search-input',
                selectId: 'customers-entries-select',
                paginationId: 'customers-pagination',
                emptyCols: 6,
                renderRow: (r, idx) => `
                    <tr>
                        <td class="text-center font-bold" style="color:${idx <= 3 ? '#fbbf24' : '#94a3b8'};">${idx}</td>
                        <td><strong>${r.name}</strong></td>
                        <td>${r.phone}</td>
                        <td class="text-center">${r.visits_count}</td>
                        <td class="text-center" style="color:#fbbf24;">${r.points}</td>
                        <td class="text-right font-mono" style="font-weight:600;color:#38bdf8;">${formatNumber(r.total_spent)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['customers-table'].setData(data.items || []);
    }

    // 6. Profit & Loss Report
    async function fetchProfitReport(start, end) {
        const url = `/api/v1/reports/profit?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const titleEl = document.getElementById('profit-card-title');
        if (titleEl) {
            titleEl.innerText = `งบกำไร-ขาดทุน ${formatThaiDateRange(start, end)}`;
        }

        const setVal = (id, val, prefix = '') => {
            const el = document.getElementById(id);
            if (el) el.innerText = `${prefix}${formatNumber(val)}`;
        };

        setVal('pnl-parts-rev', data.parts_revenue);
        setVal('pnl-repair-rev', data.repair_revenue);
        setVal('pnl-other-rev', data.other_revenue || 0);
        const notes = document.getElementById('pnl-notes');
        if (notes) {
            notes.innerHTML = `ℹ️ ต้นทุนนับเฉพาะอะไหล่ที่ขาย/ใช้ในงานจริง (${data.jobs_count} งาน) — การซื้ออะไหล่เข้าสต็อกช่วงนี้ ${formatNumber(data.stock_purchases || 0)} บาท ไม่นับเป็นต้นทุนจนกว่าจะขายออก`
                + (data.jobs_missing_cost ? `<br>⚠️ ${data.jobs_missing_cost} งานมีอะไหล่ที่พิมพ์เอง (ไม่ได้เลือกจากคลัง) จึงไม่รู้ทุน — กำไรอาจสูงกว่าความจริง` : '');
        }
        setVal('pnl-total-rev', data.total_revenue);
        setVal('pnl-cogs', data.cogs, data.cogs > 0 ? '-' : '-');
        setVal('pnl-gross', data.gross_profit);
        setVal('pnl-opex', data.operating_expenses, data.operating_expenses > 0 ? '-' : '-');

        const netEl = document.getElementById('pnl-net-profit');
        if (netEl) {
            netEl.innerText = formatNumber(data.net_profit);
            netEl.className = `pnl-val ${data.net_profit >= 0 ? 'val-green' : 'val-red'}`;
        }
    }

    // 7. Sales Tax Report (ภ.พ.30)
    async function fetchTaxReport(start, end) {
        const url = `/api/v1/reports/tax?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const titleEl = document.getElementById('tax-card-title');
        if (titleEl) {
            titleEl.innerText = `ภาษีขาย สำหรับยื่น ภพ.30 ${formatThaiDateRange(start, end)}`;
        }

        const preTaxEl = document.getElementById('tax-kpi-pretax');
        const vatEl = document.getElementById('tax-kpi-vat');
        const grandEl = document.getElementById('tax-kpi-grand');
        if (preTaxEl) preTaxEl.innerText = formatNumber(data.pre_tax_total);
        if (vatEl) vatEl.innerText = formatNumber(data.vat_total);
        if (grandEl) grandEl.innerText = formatNumber(data.grand_total);

        const footPre = document.getElementById('tax-footer-pretax');
        const footVat = document.getElementById('tax-footer-vat');
        if (footPre) footPre.innerText = formatNumber(data.pre_tax_total);
        if (footVat) footVat.innerText = formatNumber(data.vat_total);

        if (!tableManagers['tax-table']) {
            tableManagers['tax-table'] = new TableManager({
                tableId: 'tax-table',
                tbodyId: 'tax-tbody',
                searchId: 'tax-search-input',
                selectId: 'tax-entries-select',
                paginationId: 'tax-pagination',
                emptyCols: 4,
                renderRow: (r) => `
                    <tr>
                        <td><strong>${r.doc_no}</strong></td>
                        <td>${r.date}</td>
                        <td class="text-right font-mono">${formatNumber(r.pre_tax)}</td>
                        <td class="text-right font-mono" style="font-weight:600;color:#38bdf8;">${formatNumber(r.vat)}</td>
                    </tr>
                `,
            });
        }
        tableManagers['tax-table'].setData(data.items || []);
    }

    // ── Export API to Global Scope ───────────────────────────────────────────
    window.reportsApp = {
        showReportHub,
        openReport,
        loadReportData,
        exportToCSV,
        changePage: (tableId, page) => {
            if (tableManagers[tableId]) {
                tableManagers[tableId].setPage(page);
            }
        },
    };

    // Auto-resize chart on window resize
    window.addEventListener('resize', () => {
        if (currentReport === 'sales') {
            const startInput = document.getElementById('sales-start-date');
            const endInput = document.getElementById('sales-end-date');
            if (startInput && endInput) fetchSalesReport(startInput.value, endInput.value);
        }
    });

    // Initialize Report view (preserve active subreport if reloading)
    function onDOMReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    onDOMReady(() => {
        let sub = null;
        const hash = window.location.hash.replace(/^#\/?/, '');
        if (hash.startsWith('reports/')) {
            sub = hash.split('/')[1];
        } else {
            const savedTab = localStorage.getItem('activeTab');
            if (savedTab === 'reports') {
                sub = localStorage.getItem('activeSubReport');
            }
        }

        if (sub) {
            openReport(sub, false);
        } else {
            showReportHub(false);
        }
    });
})();
