# 🔧 Automotive Workshop Command Center
### ระบบหลังบ้านอัจฉริยะสำหรับอู่ซ่อมรถ — R.O.S.E. Framework

Production-ready MVP backend built with **FastAPI + LangGraph + Pydantic + SQLite**.

---

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
uvicorn main:app --reload --port 8000

# 4. Open Swagger UI
start http://localhost:8000/docs
```

> **No API keys required.** All LLM/AI calls are deterministic mocks — runs 100% offline.

---

## Architecture — R.O.S.E.

```
┌─────────────────────────────────────────────────────────┐
│  R — Router & Intake         (agents/router_graph.py)   │
│  Intent classification + Entity extraction               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  O — Orchestrator            (agents/*_agent.py)        │
│  DiagnosisGraph · BillGraph · MarketingGraph            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  S — Shared State & Hub      (SQLite / models/)         │
│  Customers · Vehicles · Tickets · Bills · Ledger        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  E — Execution & Guardrails  (services/ + routers/)     │
│  Pydantic validation · Math check · HITL gates          │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
backend for car repair shop/
├── main.py                    # FastAPI app + seed data
├── requirements.txt
├── .env.example
├── core/
│   ├── config.py              # Settings & thresholds
│   ├── database.py            # SQLAlchemy engine
│   └── dependencies.py        # DI: DB session, API key
├── models/
│   ├── db_models.py           # SQLAlchemy ORM models
│   └── schemas.py             # Pydantic v2 schemas
├── agents/
│   ├── router_graph.py        # LangGraph: RouterGraph
│   ├── diagnosis_agent.py     # LangGraph: DiagnosisGraph
│   ├── bill_agent.py          # LangGraph: BillGraph + mock OCR
│   └── marketing_agent.py     # LangGraph: MarketingGraph + mock LINE
├── routers/
│   ├── tickets.py             # Module 1 endpoints
│   ├── finance.py             # Module 2 endpoints
│   ├── customers.py           # Module 3 endpoints
│   └── marketing.py           # Module 4 endpoints
└── services/
    ├── ticket_service.py      # Module 1 business logic
    ├── finance_service.py     # Module 2 business logic
    ├── customer_service.py    # Module 3 business logic
    └── marketing_service.py   # Module 4 business logic
```

---

## API Endpoints

### Module 1 — Tickets & Repair Intake
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tickets/ingest` | Ingest Thai text → RouterGraph → DiagnosisGraph |
| `GET`  | `/api/v1/tickets/` | List all tickets (filterable by status) |
| `GET`  | `/api/v1/tickets/{id}` | Get ticket detail |
| `POST` | `/api/v1/tickets/{id}/approve` | **HITL**: Mechanic approves/adjusts |

### Module 2 — Finance & Billing
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/finance/expenses/parse-text` | Parse Thai bill text → BillGraph → math check |
| `POST` | `/api/v1/finance/bills/upload` | Upload PNG/JPG → mock OCR → BillGraph |
| `GET`  | `/api/v1/finance/bills/` | List all bills |
| `GET`  | `/api/v1/finance/bills/{id}` | Get bill detail |
| `PUT`  | `/api/v1/finance/bills/{id}/confirm` | **HITL**: Staff confirms → writes to ledger |
| `GET`  | `/api/v1/finance/summary/{year}/{month}` | Monthly P&L + AI insights |

### Module 3 — Customer & Vehicle 360°
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/customers/` | Create customer |
| `GET`  | `/api/v1/customers/` | List customers |
| `GET`  | `/api/v1/customers/{id}` | Get customer |
| `PUT`  | `/api/v1/customers/{id}` | Update customer |
| `GET`  | `/api/v1/customers/{id}/profile` | **360° Profile** (vehicles + history + segment) |
| `POST` | `/api/v1/customers/{id}/vehicles` | Add vehicle |
| `PUT`  | `/api/v1/vehicles/{plate}/mileage` | Update mileage & service dates |
| `GET`  | `/api/v1/vehicles/{plate}/health` | Get health watchlist |

### Module 4 — Marketing & Retention
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/marketing/triggers/run-cron` | Scan vehicles → generate LINE messages |
| `GET`  | `/api/v1/marketing/tasks/` | List marketing tasks |
| `GET`  | `/api/v1/marketing/tasks/{id}` | Get task |
| `POST` | `/api/v1/marketing/tasks/{id}/approve` | **HITL**: Admin approves → mock LINE dispatch |
| `POST` | `/api/v1/marketing/tasks/{id}/reject` | Reject task |

---

## HITL Guardrail Rules

| Trigger | Action |
|---------|--------|
| Ticket cost > 3,000 THB | Status → `PENDING_MECHANIC_APPROVAL` |
| Ticket involves heavy repair (engine/gear) | Status → `PENDING_MECHANIC_APPROVAL` |
| Bill math error (sum ≠ total, tolerance > 1 THB) | Status → `MATH_ERROR` (blocks ledger write) |
| Marketing task generated | Status → `PENDING_ADMIN_APPROVAL` |

---

## Seed Data (ready for Swagger testing)

| Entity | Count | Details |
|--------|-------|---------|
| Customers | 3 | สมชาย, นภาพร, วิชัย |
| Vehicles | 4 | Toyota Camry, Honda PCX 150, Isuzu D-Max, Mazda 2 |
| Parts Catalog | 15 | Engine oil, brake pads, battery, tires, etc. |
| Service Tickets | 2 | 1 approved, 1 pending mechanic approval |
| Finance Bills | 2 | 1 expense (confirmed), 1 income (confirmed) |
| Ledger Entries | 15 | June–August 2026 P&L data |
| Health Watchlist | 5 | Pre-seeded overdue items triggering marketing engine |

---

## Production Upgrade Path

| Component | Demo (MVP) | Production |
|-----------|------------|------------|
| Database | SQLite file | PostgreSQL |
| LLM | Deterministic mock | GPT-4o / Claude / Gemini |
| OCR | `mock_ocr_image()` | Google Cloud Vision / AWS Textract |
| LINE Dispatch | `mock_line_dispatch()` | LINE Messaging API |
| Auth | `X-API-Key` header | OAuth2 / JWT |
| Background jobs | Manual `POST /run-cron` | Celery + Redis / APScheduler |

---

## Environment Variables

Copy `.env.example` to `.env` and adjust:

```env
DATABASE_URL=sqlite:///./workshop_demo.db
QUOTE_APPROVAL_THRESHOLD_THB=3000.0
OIL_CHANGE_KM=10000
OIL_CHANGE_MONTHS=6
BATTERY_CHANGE_YEARS=2
TIRE_CHANGE_KM=40000
CUSTOMER_INACTIVE_MONTHS=6
MOCK_API_KEY=workshop-secret-2026
```
