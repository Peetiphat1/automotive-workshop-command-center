# 📖 Automotive Workshop Command Center — User Manual
*(Complete User & Administrator Manual)*

Welcome to the **Automotive Workshop Command Center & R.O.S.E. AI Copilot** user manual — an all-in-one automotive repair shop and service center management platform.

---

## 📑 Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Getting Started (Launch & Stop)](#2-getting-started-launch--stop)
3. [Important URLs](#3-important-urls)
4. [Module-by-Module User Guide](#4-module-by-module-user-guide)
   - [4.1 Command Center Dashboard](#41-command-center-dashboard)
   - [4.2 Service Tickets & Intake System](#42-service-tickets--intake-system)
   - [4.3 Appointments & Calendar](#43-appointments--calendar)
   - [4.4 Customer 360° Profile & Vehicles](#44-customer-360-profile--vehicles)
   - [4.5 Stock & Inventory Management](#45-stock--inventory-management)
   - [4.6 Purchases & Parts Suppliers](#46-purchases--parts-suppliers)
   - [4.7 Finance & Expense Tracking](#47-finance--expense-tracking)
   - [4.8 Reports & Business Analytics (7 Standard Reports)](#48-reports--business-analytics-7-standard-reports)
   - [4.9 OCR Scanner (Bills & License Plates)](#49-ocr-scanner-bills--license-plates)
   - [4.10 Public Repair Tracker for Customers](#410-public-repair-tracker-for-customers)
   - [4.11 AI & LINE Official Account Integrations](#411-ai--line-official-account-integrations)
5. [Troubleshooting, Backup & Data Migration](#5-troubleshooting-backup--data-migration)

---

## 1. System Overview & Architecture

The Automotive Workshop Command Center is built with modern, production-grade technologies:
- **Backend:** FastAPI (Python 3.12) high-performance framework supporting asynchronous requests.
- **Database:** SQLite ORM via SQLAlchemy (`workshop_demo.db`) — zero-configuration, single-file, highly reliable database.
- **AI Engine:** R.O.S.E. Copilot Framework integrating LangGraph & Google Gemini API for intelligent symptom extraction, diagnostic estimates, and OCR receipt processing.
- **Frontend:** Glassmorphism UI crafted with HTML5, responsive CSS3, Vanilla JS, Lucide Icons, and Chart.js.
- **Language Support:** Bilingual interface (Thai 🇹🇭 and English 🇬🇧) with instant runtime toggle.

---

## 2. Getting Started (Launch & Stop)

### How to Launch
You can start the application using any of the following 3 methods:
1. **Via Desktop Shortcut:** Double-click the **`Automotive Workshop Command Center`** icon on your Desktop.
2. **Via Direct Launcher:** Double-click **`START Automotive Workshop.bat`** on your Desktop.
3. **Via Project Folder:** Double-click `START.bat` located inside the root project directory.

> ✨ When launched, the console window initializes dependencies and automatically opens your default browser at `http://localhost:8000/dashboard`.

### How to Stop
- Close the command console window (Command Prompt), or press `Ctrl + C` inside the console terminal.

---

## 3. Important URLs

| Screen | URL | Description |
|---|---|---|
| 🏠 **Main Dashboard** | [http://localhost:8000/dashboard](http://localhost:8000/dashboard) | Main command center for workshop managers and technicians. |
| 📦 **Stock & Inventory** | [http://localhost:8000/stock](http://localhost:8000/stock) | Inventory control, stock adjustments, barcode scanning & history. |
| 📷 **OCR Scanner** | [http://localhost:8000/scan](http://localhost:8000/scan) | Scan parts purchase invoices & vehicle license plates via camera or file upload. |
| 🔍 **Public Repair Tracker** | [http://localhost:8000/track](http://localhost:8000/track) | Public portal for customers to check real-time repair progress. |
| 📖 **User Manual (Thai / English)** | [http://localhost:8000/manual](http://localhost:8000/manual) | Interactive, searchable documentation with TH/EN language switcher. |
| ⚡ **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI API documentation for developers. |

---

## 4. Module-by-Module User Guide

### 4.1 Command Center Dashboard
- **Top 4 KPI Metric Cards:**
  1. *Total Monthly Revenue:* Real-time summation of labor and spare parts from all approved/completed invoices.
  2. *Active Repairs:* Current count of vehicles undergoing inspection or repair.
  3. *Low Stock Warning:* Alerts when inventory items fall below minimum reorder thresholds.
  4. *Today's Appointments:* Count of scheduled client arrivals for the current date. Click to navigate directly to the Appointments calendar.
- **Recent Repairs Table:** Displays latest tickets with quick filter pills: `All`, `Pending Approval`, `In Progress`, `Completed`.
- **Upcoming Appointments Card:** Quick view of the next scheduled vehicles.
- **Maintenance Watchlist:** Automated recommendations for vehicles due for routine engine oil, battery, brake, or tire services.
- **R.O.S.E. AI Copilot (Right Sidebar Dock):** Conversational AI assistant — query vehicle status, inventory levels, or ask diagnostic recommendations in natural language.

### 4.2 Service Tickets & Intake System (Repairs Hub)
1. Click the **"+ New Intake"** button (top header or Repairs tab).
2. Input vehicle details:
   - License Plate (e.g., `กข 1234 กรุงเทพ` or `1AB 1234`)
   - Customer Name and Phone Number
   - Reported Symptoms or Customer Complaints (e.g., *"Squeaking noise when braking, brake pedal vibrating"*)
3. The AI Copilot automatically extracts structured symptoms, matches required replacement parts from catalog, and computes estimated parts cost and labor fees.
4. Lead technician reviews the estimate and clicks **"Approve"** to transition the ticket into the active repair workflow.
5. Once physical work concludes, click **"Complete Repair"** to finalize invoice and record ledger entries.

### 4.3 Appointments & Calendar
- Monthly visual calendar view of client appointments.
- Click any calendar date to view the day's scheduled bookings.
- Click **"+ Add Appointment"** to register a new slot:
  - Select customer and vehicle.
  - Choose date, time slot, and target service (e.g., 10,000 km periodic maintenance, brake pad replacement, tire change).
  - Track status: `Confirmed`, `Pending`, or `Completed`.

### 4.4 Customer 360° Profile & Vehicles
- Search customers by Name, Phone Number, or Vehicle License Plate.
- Click **"Customer 360° View"** to inspect:
  - All vehicles registered under the customer along with current mileage.
  - Lifetime total spending and visit frequency.
  - Complete historical log of past repair orders, work tickets, and invoices.

### 4.5 Stock & Inventory Management
- Access via the **"Stock"** sidebar tab or visit `/stock`.
- **Add New Part:** Specify Part Name (TH/EN), SKU / Barcode, Category, In-Stock Quantity, Cost Price, Retail Price, and Reorder Level.
- **Adjust Stock Levels:** Fast (+) receive stock or (-) withdraw parts with mandatory reason notes.
- **Stock Movement History:** Complete audit trail tracking date, user, quantity delta, and associated repair ticket ID.

### 4.6 Purchases & Parts Suppliers
- Maintain supplier contacts, vendor terms, and phone numbers.
- Generate Purchase Orders (PO) for bulk spare parts.
- Monitor payment status (`Paid` vs `Pending Payment`) and delivery fulfillment.

### 4.7 Finance & Expense Tracking
- Record daily operational garage expenditures: Rent, Utilities (Electricity & Water), Equipment & Tools, Shop Consumables, and Mechanic Payroll.
- Categorized expense records are automatically consolidated into the Profit & Loss statement.

### 4.8 Reports & Business Analytics (7 Standard Reports)
The system includes 7 industry-standard management reports:
1. **Sales Report:** Daily and monthly revenue breakdown by labor vs. parts.
2. **Top Parts:** Top 10 most frequently used and sold spare parts.
3. **Stock Valuation:** Total inventory balance evaluated at Cost vs. Retail value.
4. **Mechanic Performance:** Labor hours, tickets completed, and technician commission metrics.
5. **Customer Spending:** Top VIP clients ranked by lifetime spending.
6. **Profit & Loss (P&L):** Net profit calculated from Gross Revenue minus Cost of Goods Sold and Operating Expenses.
7. **Sales Tax Report:** VAT breakdown report for tax filing.

### 4.9 OCR Scanner (Bills & License Plates)
- Access via the **"Scan"** top button or navigate to `/scan`.
- **License Plate OCR:** Upload or snap a vehicle front picture to automatically extract license number and province.
- **Purchase Invoice OCR:** Snap parts receipt images; OCR automatically parses line items, unit costs, total amounts, and maps items to inventory.

### 4.10 Public Repair Tracker for Customers
- Accessible at: [http://localhost:8000/track](http://localhost:8000/track)
- Customers enter their license plate (e.g., `กข 1234`) or Ticket ID.
- Real-time milestone tracker visualizes vehicle progress:
  *Vehicle Received ➔ Diagnosis & Disassembly ➔ Repair in Progress ➔ Quality Inspection ➔ Ready for Pickup*

### 4.11 AI & LINE Official Account Integrations
- **AI Settings:** Configure Google Gemini or OpenAI API keys to power smart diagnostics and receipt OCR.
- **LINE Official Account:** Connect Channel Access Token and Channel Secret to dispatch automatic repair status alerts and notifications to customers' LINE app.

---

## 5. Troubleshooting, Backup & Data Migration

### Frequently Asked Questions (FAQs)

#### 1. Port 8000 Already in Use
If another process has locked port 8000:
1. Open Command Prompt (`cmd.exe`).
2. Run: `netstat -ano | findstr :8000`
3. Terminate the blocking process: `taskkill /PID <PID_NUMBER> /F` and relaunch `START.bat`.

#### 2. Browser Does Not Open Automatically
- Open Google Chrome, Microsoft Edge, or Firefox manually and navigate to: `http://localhost:8000/dashboard`

---

### Data Backup & Device Migration

The Command Center includes built-in **Data Export** and **Data Import** capabilities under the top database icon `💾` or via **Settings ➔ Backup & Data Migration**:

#### 📤 How to Export Data from Current Computer:
1. Click the database icon `💾` in the top header, or go to **Settings ➔ Backup & Data Migration**.
2. Select your preferred export format:
   - **Download SQLite Database (.db):** *(Recommended)* 100% complete snapshot of all customers, vehicles, inventory, tickets, expenses, and invoices. Ideal for instant migration to another computer.
   - **Download JSON Export (.json):** Human-readable export suitable for Excel analysis or selective merging.
3. Save the file to a USB Flash Drive, cloud storage (Google Drive / OneDrive), or send via email.

#### 📥 How to Import Data on New Computer:
1. Launch the application on your new computer and navigate to **Settings ➔ Backup & Data Migration**.
2. Drag and drop your `.db` or `.json` file into the upload box (or click to browse).
3. Review the preview metrics and click **"Confirm & Import Now"**.
4. The system **automatically generates a Safety Backup point** before modifying data, ensuring complete safety. The new machine is now fully synced and ready for business!

---
*Note: You can review and restore historical safety backups at any time from the "Safety Backup History" panel.*
