with open('static/chat.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's use node to check syntax if node exists
import subprocess
try:
    res = subprocess.run(['node', '--check', 'static/chat.js'], capture_output=True, text=True)
    print("Node check exit code:", res.returncode)
    print("Node check stdout:", res.stdout)
    print("Node check stderr:", res.stderr)
except Exception as e:
    print("Node not available:", e)
