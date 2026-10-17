"""
reset_db.py — Wipe all user/demo data from workshop_demo.db
and reset auto-increment counters so the system starts fresh.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "workshop_demo.db")

# Order matters: children before parents (FK constraints)
TABLES_IN_ORDER = [
    "stock_history",
    "work_orders",
    "ledger_entries",
    "finance_bills",
    "expenses",
    "purchase_bills",
    "marketing_tasks",
    "appointments",
    "vehicle_health_watchlist",
    "service_tickets",
    "vehicles",
    "customers",
    "suppliers",
    "parts_catalog",
    "stock_items",
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA foreign_keys = OFF")

print("🗑  Clearing all tables...")
for table in TABLES_IN_ORDER:
    cur.execute(f'DELETE FROM "{table}"')
    print(f"   ✔ {table}")

# Reset auto-increment counters (sqlite_sequence only exists after first INSERT)
try:
    for table in TABLES_IN_ORDER:
        cur.execute(f'DELETE FROM sqlite_sequence WHERE name="{table}"')
except sqlite3.OperationalError:
    pass  # sqlite_sequence doesn't exist yet — nothing to reset

cur.execute("PRAGMA foreign_keys = ON")

# Also clear the seeded flag so _seed() won't skip on next boot
# The seed guard checks if customers table is non-empty,
# so deleting all customers is sufficient — but we also do VACUUM
# to reclaim space and ensure a clean slate.
conn.commit()
conn.execute("VACUUM")
conn.close()

print("\n✅ Database reset complete — all tables empty, IDs reset to 1.")
print("   Restart the server to apply (the seed guard will now re-run if needed).")
print("   Since there are NO demo rows, seeding is skipped and you get a truly blank system.")
