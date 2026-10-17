import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = [
    'routers/stock.py',
    'routers/suppliers.py',
    'routers/expenses.py',
    'routers/backup.py',
    'services/backup_service.py',
    'static/stock.js',
]

for f in files:
    print(f"\n=================== DIFF: {f} ===================")
    res = subprocess.run(['git', 'diff', f], capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(res.stdout[:2000])
