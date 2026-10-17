import sqlite3

conn = sqlite3.connect('workshop_demo.db')
cur = conn.cursor()
cur.execute("SELECT sku, name_th, quantity, unit_cost FROM stock_items WHERE sku LIKE '1006045%' OR sku LIKE 'D2-%' OR sku LIKE 'A2-%'")
rows = cur.fetchall()
print(f"Found {len(rows)} existing matching items:")
for r in rows:
    print(r)

cur.execute("SELECT id, bill_number, supplier_id, total_amount FROM purchase_bills")
print("Purchase bills:", cur.fetchall())

conn.close()
