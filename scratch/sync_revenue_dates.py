import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from core.database import SessionLocal
from models.db_models import ServiceTicket, LedgerEntry, get_local_now

db = SessionLocal()
now_local = get_local_now()
print('Current local time:', now_local)

active_ids = [16, 17, 18, 19]
for t in db.query(ServiceTicket).filter(ServiceTicket.id.in_(active_ids)).all():
    print(f'Ticket #{t.id} ({t.status}): before created_at={t.created_at}, updated_at={t.updated_at}')
    t.created_at = now_local
    t.updated_at = now_local
    if t.status == 'APPROVED':
        t.approved_at = now_local

for l in db.query(LedgerEntry).filter(LedgerEntry.description.like('%Ticket%')).all():
    print(f'Ledger #{l.id} ({l.amount}฿): before entry_date={l.entry_date} - {l.description}')
    l.entry_date = now_local

db.commit()
print('Successfully synchronized tickets and ledger entries to current date!')
