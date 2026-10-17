/**
 * Automotive Workshop Command Center — Internationalization (i18n) Engine
 * Seamless runtime switching between Thai (th) and English (en).
 */

const I18N_DICTIONARY = {
    th: {
        // Brands & Meta
        brand_name: "Zero Garage",
        brand_sub: "Command Center AI",
        nav_main_service: "บริการหลัก (MAIN SERVICE)",
        nav_finance_reports: "การเงิน & รายงาน (FINANCE & REPORTS)",
        
        // Navigation items
        nav_dashboard: "Dashboard",
        nav_repairs: "งานซ่อม",
        nav_pos: "ขายอะไหล่ (POS)",
        nav_appointments: "นัดหมาย",
        nav_customers: "ลูกค้า & รถ",
        nav_stock: "คลัง/สต๊อก",
        nav_purchases: "จัดซื้อ",
        nav_suppliers: "ผู้จำหน่าย",
        nav_reports: "รายงาน",
        nav_expenses: "ค่าใช้จ่าย",
        nav_settings: "ตั้งค่า",
        nav_tracker: "Public Tracker",
        nav_manual: "คู่มือการใช้งาน (Manual)",
        api_status_text: "R.O.S.E. AI Engine Active",

        // Top Header
        search_placeholder: "ค้นหาเลขทะเบียน, ชื่อลูกค้า, เลขที่ Ticket หรือสินค้า...",
        btn_new_ticket: "เปิดใบรับรถใหม่",
        btn_appointment: "นัดหมาย",
        btn_backup_title: "สำรองและย้ายข้อมูล (Backup & Transfer)",
        btn_scan_title: "สแกนบิลและป้ายทะเบียน",
        user_name: "ผู้จัดการอู่ (Admin)",
        user_role: "สาขาหลัก (Bangkok)",

        // KPI Cards
        kpi_revenue_title: "ยอดขายรวมเดือนนี้",
        kpi_revenue_calc: "กำลังคำนวณ...",
        kpi_repairs_title: "งานซ่อมกำลังดำเนินการ",
        kpi_repairs_pending: "รอช่างอนุมัติ {n} คัน",
        kpi_stock_title: "อะไหล่ใกล้หมดคลัง",
        kpi_stock_sub: "ควรสั่งซื้อเพิ่มเพื่อรองรับงานซ่อม",
        kpi_appt_title: "นัดหมายวันนี้",
        kpi_appt_sub: "คลิกดูปฏิทินนัดหมาย ➔",
        unit_cars: "คัน",
        unit_items: "รายการ",
        unit_appts: "นัด",

        // Dashboard sections
        recent_repairs_title: "ตารางงานซ่อมล่าสุด",
        filter_all: "ทั้งหมด",
        filter_pending: "รออนุมัติ",
        filter_approved: "กำลังซ่อม",
        filter_completed: "ซ่อมเสร็จแล้ว",
        upcoming_appts_title: "นัดหมายเร็วๆ นี้ (Upcoming)",
        view_calendar_link: "ดูปฏิทินทั้งหมด",
        watchlist_title: "Watchlist เตือนภัย",
        quick_stock_title: "สต๊อกด่วน",
        view_all_link: "ดูทั้งหมด",

        // Table headers
        th_ticket: "Ticket #",
        th_plate_model: "ทะเบียน / รุ่น",
        th_customer: "ลูกค้า",
        th_symptoms: "อาการ",
        th_items: "รายการ",
        th_price: "ราคา",
        th_status: "สถานะ",
        th_actions: "จัดการ",
        th_date: "วันที่",
        th_phone: "เบอร์โทร",
        th_sku: "รหัส SKU",
        th_part_name: "ชื่ออะไหล่",
        th_category: "หมวดหมู่",
        th_stock_qty: "คงคลัง",
        th_cost: "ราคาทุน",
        th_retail: "ราคาขาย",

        // Status badges
        status_pending: "⏳ รออนุมัติ",
        status_approved: "🟢 กำลังซ่อม",
        status_completed: "✅ เสร็จสิ้น",
        status_cancelled: "❌ ยกเลิก",
        status_confirmed: "ยืนยันแล้ว",
        status_waiting_parts: "รออะไหล่",

        // Action buttons
        btn_approve_work: "✓ อนุมัติเริ่มงาน",
        btn_complete_work: "🏁 แจ้งซ่อมเสร็จ",
        btn_completed_done: "✓ ซ่อมเสร็จแล้ว",
        btn_info: "ข้อมูล",
        btn_work_order: "📋 ใบแจ้งงาน",
        btn_invoice: "🖨️ ใบเสร็จ",
        btn_view_status: "ดูสถานะ",
        btn_close: "ปิด",
        btn_cancel: "ยกเลิก",
        btn_save: "บันทึก",
        btn_confirm: "ยืนยัน",
        btn_search: "ค้นหา",
        btn_print: "พิมพ์ / PDF",

        // Tab: Repairs
        repairs_hub_title: "การจัดการงานซ่อม (Repairs Hub)",
        repairs_search_placeholder: "🔍 ค้นหา (Ticket, ทะเบียน, ลูกค้า, ช่าง)...",

        // Tab: POS
        pos_title: "ประวัติการขายอะไหล่ (POS) & อะไหล่ที่ใช้ในงานซ่อม",
        pos_manual_btn: "+ คนซื้ออะไหล่ (POS)",
        pos_ai_btn: "เพิ่มผ่าน AI",
        pos_filter_all: "ทั้งหมด",
        pos_filter_sale: "🛒 คนซื้ออะไหล่ (POS)",
        pos_filter_repair: "🔧 ใช้ในซ่อม",
        pos_filter_purchase: "📦 จัดซื้อเข้าอู่",

        // Tab: Appointments
        appts_title: "ปฏิทินนัดหมาย & ตารางงานซ่อม",
        btn_add_appt: "เพิ่มนัดหมาย",
        today_btn: "วันนี้",

        // Tab: Customers
        cust_title: "ฐานข้อมูลลูกค้า & ประวัติยานพาหนะ",
        btn_add_cust: "เพิ่มลูกค้าใหม่",
        cust_search_placeholder: "ค้นหาชื่อ, เบอร์โทร, หรือเลขทะเบียน...",

        // Tab: Stock
        stock_title: "จัดการคลังสินค้า & สต๊อกอะไหล่",
        btn_add_part: "เพิ่มอะไหล่ใหม่",
        btn_stock_scanner: "สแกนบิล/บาร์โค้ด",
        btn_stock_cats: "จัดการหมวดหมู่",

        // Tab: Purchases
        purchases_title: "รายการจัดซื้ออะไหล่ & ใบเสร็จ",
        btn_new_purchase: "บันทึกใบสั่งซื้อ",

        // Tab: Suppliers
        suppliers_title: "รายชื่อผู้จำหน่าย & ร้านอะไหล่",
        btn_add_supplier: "เพิ่มผู้จำหน่าย",

        // Tab: Reports
        reports_title: "รายงาน & สถิติศูนย์บริการ",
        rep_tab_sales: "ยอดขายรวม",
        rep_tab_parts: "อะไหล่ขายดี",
        rep_tab_stock: "มูลค่าสต๊อก",
        rep_tab_mechanics: "ผลงานช่าง",
        rep_tab_customers: "ลูกค้าชั้นยอด",
        rep_tab_pnl: "งบกำไร-ขาดทุน",
        rep_tab_tax: "รายงานภาษี (ภ.พ.30)",

        // Tab: Expenses
        expenses_title: "บันทึกค่าใช้จ่าย & เงินสดย่อย",
        btn_add_expense: "บันทึกค่าใช้จ่าย",
        btn_expense_cats: "จัดการหมวดหมู่",

        // Tab: Settings
        settings_title: "การตั้งค่าระบบ (Settings)",

        // General messages
        loading_text: "กำลังโหลด...",
        no_data_repairs: "ไม่พบข้อมูลงานซ่อม",
        no_data_appts: "ไม่มีนัดหมายในวันนี้",
        no_data_watchlist: "ยังไม่มีรถที่ครบกำหนดบำรุงรักษา",
        no_data_stock: "ไม่มีอะไหล่ที่ต้องสั่งซื้อด่วน"
    },

    en: {
        // Brands & Meta
        brand_name: "Zero Garage",
        brand_sub: "Command Center AI",
        nav_main_service: "MAIN SERVICE",
        nav_finance_reports: "FINANCE & REPORTS",
        
        // Navigation items
        nav_dashboard: "Dashboard",
        nav_repairs: "Repairs Hub",
        nav_pos: "Sales / Parts Used",
        nav_appointments: "Appointments",
        nav_customers: "Customers & Cars",
        nav_stock: "Stock / Inventory",
        nav_purchases: "Purchases",
        nav_suppliers: "Suppliers",
        nav_reports: "Reports & Analytics",
        nav_expenses: "Expenses",
        nav_settings: "Settings",
        nav_tracker: "Public Tracker",
        nav_manual: "User Manual",
        api_status_text: "R.O.S.E. AI Engine Active",

        // Top Header
        search_placeholder: "Search license plate, customer name, ticket ID or product...",
        btn_new_ticket: "+ New Intake",
        btn_appointment: "Appointment",
        btn_backup_title: "Backup & Data Transfer",
        btn_scan_title: "Scan Bills & License Plates",
        user_name: "Workshop Manager (Admin)",
        user_role: "Main Branch (Bangkok)",

        // KPI Cards
        kpi_revenue_title: "Total Revenue This Month",
        kpi_revenue_calc: "Calculating...",
        kpi_repairs_title: "Active Repairs",
        kpi_repairs_pending: "{n} awaiting mechanic approval",
        kpi_stock_title: "Low Stock Items",
        kpi_stock_sub: "Reorder recommended to avoid delays",
        kpi_appt_title: "Today's Appointments",
        kpi_appt_sub: "Click to view calendar ➔",
        unit_cars: "vehicles",
        unit_items: "items",
        unit_appts: "appts",

        // Dashboard sections
        recent_repairs_title: "Recent Repairs Board",
        filter_all: "All",
        filter_pending: "Pending",
        filter_approved: "In Progress",
        filter_completed: "Completed",
        upcoming_appts_title: "Upcoming Appointments",
        view_calendar_link: "View Full Calendar",
        watchlist_title: "Maintenance Watchlist",
        quick_stock_title: "Quick Stock",
        view_all_link: "View All",

        // Table headers
        th_ticket: "Ticket #",
        th_plate_model: "Plate / Model",
        th_customer: "Customer",
        th_symptoms: "Symptoms",
        th_items: "Items",
        th_price: "Price",
        th_status: "Status",
        th_actions: "Actions",
        th_date: "Date",
        th_phone: "Phone",
        th_sku: "SKU",
        th_part_name: "Part Name",
        th_category: "Category",
        th_stock_qty: "In Stock",
        th_cost: "Cost Price",
        th_retail: "Retail Price",

        // Status badges
        status_pending: "⏳ Pending",
        status_approved: "🟢 In Progress",
        status_completed: "✅ Completed",
        status_cancelled: "❌ Cancelled",
        status_confirmed: "Confirmed",
        status_waiting_parts: "Waiting Parts",

        // Action buttons
        btn_approve_work: "✓ Approve",
        btn_complete_work: "🏁 Complete",
        btn_completed_done: "✓ Finished",
        btn_info: "Details",
        btn_work_order: "📋 Work Order",
        btn_invoice: "🖨️ Invoice",
        btn_view_status: "Track",
        btn_close: "Close",
        btn_cancel: "Cancel",
        btn_save: "Save",
        btn_confirm: "Confirm",
        btn_search: "Search",
        btn_print: "Print / PDF",

        // Tab: Repairs
        repairs_hub_title: "Repairs Management Hub",
        repairs_search_placeholder: "🔍 Search (Ticket, Plate, Customer, Mechanic)...",

        // Tab: POS
        pos_title: "Parts Sales (POS) & Parts Used in Repairs",
        pos_manual_btn: "+ Sell Parts (POS)",
        pos_ai_btn: "Add via AI",
        pos_filter_all: "All",
        pos_filter_sale: "🛒 Parts Sales (POS)",
        pos_filter_repair: "🔧 Used in Repairs",
        pos_filter_purchase: "📦 Purchases",

        // Tab: Appointments
        appts_title: "Appointments & Schedule Calendar",
        btn_add_appt: "+ Add Appointment",
        today_btn: "Today",

        // Tab: Customers
        cust_title: "Customer Directory & Vehicle Profiles",
        btn_add_cust: "+ Add Customer",
        cust_search_placeholder: "Search by Name, Phone, or License Plate...",

        // Tab: Stock
        stock_title: "Stock & Inventory Management",
        btn_add_part: "+ Add Part",
        btn_stock_scanner: "Scan Bill / Barcode",
        btn_stock_cats: "Manage Categories",

        // Tab: Purchases
        purchases_title: "Parts Purchase Orders & Supplier Bills",
        btn_new_purchase: "+ New PO Bill",

        // Tab: Suppliers
        suppliers_title: "Parts Suppliers & Vendors",
        btn_add_supplier: "+ Add Supplier",

        // Tab: Reports
        reports_title: "Workshop Reports & Business Analytics",
        rep_tab_sales: "Sales Overview",
        rep_tab_parts: "Top Selling Parts",
        rep_tab_stock: "Stock Valuation",
        rep_tab_mechanics: "Mechanic Performance",
        rep_tab_customers: "Top Clients",
        rep_tab_pnl: "Profit & Loss (P&L)",
        rep_tab_tax: "Sales Tax (VAT)",

        // Tab: Expenses
        expenses_title: "Operating Expenses & Overhead Ledger",
        btn_add_expense: "+ Record Expense",
        btn_expense_cats: "Manage Categories",

        // Tab: Settings
        settings_title: "System Settings & Integrations",

        // General messages
        loading_text: "Loading...",
        no_data_repairs: "No repair orders found",
        no_data_appts: "No appointments scheduled for today",
        no_data_watchlist: "No vehicles due for maintenance at this time",
        no_data_stock: "All inventory items are currently well stocked"
    }
};

let currentLanguage = localStorage.getItem('workshop_lang') || 'th';

function getAppLanguage() {
    return currentLanguage;
}

function t(key, defaultVal = '') {
    const dict = I18N_DICTIONARY[currentLanguage] || I18N_DICTIONARY.th;
    return dict[key] !== undefined ? dict[key] : (defaultVal || key);
}

function setAppLanguage(lang) {
    if (!['th', 'en'].includes(lang)) lang = 'th';
    currentLanguage = lang;
    localStorage.setItem('workshop_lang', lang);
    document.documentElement.lang = lang;

    // Update toggle button states
    const btnTh = document.getElementById('btn-lang-th');
    const btnEn = document.getElementById('btn-lang-en');
    if (btnTh && btnEn) {
        if (lang === 'th') {
            btnTh.classList.add('active');
            btnEn.classList.remove('active');
        } else {
            btnEn.classList.add('active');
            btnTh.classList.remove('active');
        }
    }

    // Apply translations to all DOM elements with data-i18n attributes
    applyDomTranslations();

    // Notify listeners & trigger re-render of dynamic components
    window.dispatchEvent(new CustomEvent('appLanguageChanged', { detail: { lang } }));

    // Trigger re-rendering of active views if functions exist
    if (typeof renderTicketsTable === 'function') {
        const activeDashPill = document.querySelector('#tab-dashboard .table-filter-pills .pill.active');
        const filterVal = activeDashPill ? (activeDashPill.getAttribute('onclick') || '').match(/'([^']+)'/)?.[1] || 'all' : 'all';
        renderTicketsTable(filterVal);
    }
    if (typeof renderFullRepairsTable === 'function') {
        renderFullRepairsTable();
    }
    if (typeof renderStockTable === 'function') {
        renderStockTable();
    }
    if (typeof renderAppointmentsCalendar === 'function') {
        renderAppointmentsCalendar();
    }
    if (typeof renderWatchlist === 'function') {
        renderWatchlist();
    }
    if (typeof renderExpensesTable === 'function') {
        renderExpensesTable();
    }
    if (typeof renderPurchasesTable === 'function') {
        renderPurchasesTable();
    }
    if (typeof renderSuppliersTable === 'function') {
        renderSuppliersTable();
    }
    if (typeof renderCustomersTable === 'function') {
        renderCustomersTable();
    }
}

function applyDomTranslations() {
    // 1. Text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translated = t(key);
        if (translated) {
            // If the element has child icons, only replace text node or preserve icons
            const icon = el.querySelector('i');
            const badge = el.querySelector('.badge');
            if (icon && badge) {
                // e.g. <i data-lucide="wrench"></i> <span>งานซ่อม</span> <span class="badge">0</span>
                const span = el.querySelector('span:not(.badge)');
                if (span) span.innerText = translated;
            } else if (icon) {
                el.childNodes.forEach(node => {
                    if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                        node.textContent = ' ' + translated;
                    }
                });
            } else {
                el.innerText = translated;
            }
        }
    });

    // 2. Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translated = t(key);
        if (translated) el.setAttribute('placeholder', translated);
    });

    // 3. Titles / tooltips
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        const translated = t(key);
        if (translated) el.setAttribute('title', translated);
    });

    // 4. HTML content
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
        const key = el.getAttribute('data-i18n-html');
        const translated = t(key);
        if (translated) el.innerHTML = translated;
    });

    // Re-initialize Lucide icons if any were re-rendered
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

// Auto-run on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    setAppLanguage(currentLanguage);
});

// Expose globally
window.t = t;
window.getAppLanguage = getAppLanguage;
window.setAppLanguage = setAppLanguage;
