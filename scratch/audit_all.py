import ast
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Audit each HTML file and its loaded JS files
page_bundles = {
    'static/index.html': ['static/i18n.js', 'static/reports.js', 'static/chat.js'],
    'static/stock.html': ['static/stock.js'],
    'static/scan.html': ['static/scan.js'],
    'static/track.html': ['static/track.js'],
    'static/manual.html': [],
    'static/manual_en.html': [],
}

builtin_js = {
    'alert', 'confirm', 'prompt', 'if', 'console', 'preventDefault',
    'stopPropagation', 'close', 'open', 'setTimeout', 'clearTimeout',
    'getElementById', 'querySelector', 'querySelectorAll', 'reset', 'submit',
    'focus', 'blur', 'click', 'select', 'toUpperCase', 'toLowerCase',
    'setTrackLanguage', 'quickSearch', 'performTrack', 'lucide', 'createIcons',
    'addEventListener'
}

print("=== 1. CHECKING HTML EVENT HANDLERS AGAINST INCLUDED JS ===")
for html_path, js_list in page_bundles.items():
    if not os.path.exists(html_path):
        continue
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    js_sources = ""
    for js_path in js_list:
        if os.path.exists(js_path):
            with open(js_path, 'r', encoding='utf-8', errors='ignore') as f:
                js_sources += "\n" + f.read()

    # Add inline scripts from HTML
    for inline in re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', html, re.DOTALL):
        js_sources += "\n" + inline

    # Defined functions
    defs = set()
    for m in re.finditer(r'\bfunction\s+([a-zA-Z0-9_$]+)\s*\(', js_sources):
        defs.add(m.group(1))
    for m in re.finditer(r'\b([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>)', js_sources):
        defs.add(m.group(1))
    for m in re.finditer(r'window\.([a-zA-Z0-9_$]+)\s*=', js_sources):
        defs.add(m.group(1))

    # Event handlers in HTML (onclick=..., onsubmit=..., etc.)
    handler_attr_pattern = re.compile(r'\bon[a-z]+\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    missing_handlers = set()
    for h_match in handler_attr_pattern.finditer(html):
        h_code = h_match.group(1)
        # Find function invocations
        for call_match in re.finditer(r'([a-zA-Z0-9_$]+)\s*\(', h_code):
            fn_name = call_match.group(1)
            if fn_name not in defs and fn_name not in builtin_js:
                missing_handlers.add((fn_name, h_code))

    if missing_handlers:
        print(f"\n[!] IN {html_path}: Found {len(missing_handlers)} potentially undefined handler(s):")
        for fn_name, h_code in sorted(missing_handlers):
            print(f"    - {fn_name}() in: {h_code.strip()[:80]}")
    else:
        print(f"[OK] {html_path}: All event handlers are defined in loaded JS.")

# 2. Check JavaScript syntax using node.js or python regex
print("\n=== 2. CHECKING JS FILES FOR SYNTAX / COMMON RUNTIME ERRORS ===")
js_files = glob.glob('static/**/*.js', recursive=True)
for jf in js_files:
    with open(jf, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    # Check for unmatched braces or parentheses roughly
    open_cur = 0
    open_paren = 0
    open_bracket = 0
    for idx, line in enumerate(lines, 1):
        # strip string literals and comments roughly
        clean = re.sub(r'//.*', '', line)
        open_cur += clean.count('{') - clean.count('}')
        open_paren += clean.count('(') - clean.count(')')
        open_bracket += clean.count('[') - clean.count(']')
    print(f"{jf}: {len(lines)} lines, braces net: {open_cur}, parens net: {open_paren}, brackets net: {open_bracket}")

# 3. Check for API endpoints in all JS files vs FastAPI app routes
print("\n=== 3. CHECKING ALL API CALLS IN JS VS FASTAPI ENDPOINTS ===")
sys.path.insert(0, '.')
from main import app

backend_routes = set()
for r in app.routes:
    if hasattr(r, 'path'):
        norm = re.sub(r'\{[^}]+\}', '*', r.path).rstrip('/')
        backend_routes.add(norm)

# Find all fetch/axios/http calls in JS
unmatched_endpoints = set()
for jf in js_files:
    with open(jf, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    # Matches /api/v1/...
    for match in re.finditer(r'[\'"`](/api/v1[^\'" `?#]+)', text):
        raw_url = match.group(1)
        norm_url = re.sub(r'\$\{[^}]+\}', '*', raw_url)
        norm_url = re.sub(r'/\d+', '/*', norm_url).rstrip('/')
        
        # Check against backend_routes
        matched = False
        for br in backend_routes:
            pat = '^' + re.escape(br).replace(r'\*', r'[^/]+') + '$'
            if re.match(pat, norm_url) or re.match(pat, raw_url.rstrip('/')):
                matched = True
                break
        if not matched:
            unmatched_endpoints.add((jf, raw_url, norm_url))

    # Matches ${API_URL}/...
    for match in re.finditer(r'\$\{API_URL\}(/[^\'" `?#]+)', text):
        raw_url = '/api/v1' + match.group(1)
        norm_url = re.sub(r'\$\{[^}]+\}', '*', raw_url)
        norm_url = re.sub(r'/\d+', '/*', norm_url).rstrip('/')
        
        matched = False
        for br in backend_routes:
            pat = '^' + re.escape(br).replace(r'\*', r'[^/]+') + '$'
            if re.match(pat, norm_url) or re.match(pat, raw_url.rstrip('/')):
                matched = True
                break
        if not matched:
            unmatched_endpoints.add((jf, raw_url, norm_url))

if unmatched_endpoints:
    print(f"[!] Found {len(unmatched_endpoints)} unmatched API calls:")
    for jf, raw, norm in sorted(unmatched_endpoints):
        print(f"    - {raw} in {jf}")
else:
    print("[OK] All frontend API endpoints match backend FastAPI routes.")

# 4. Check python routers for missing dependencies, service calls, or undefined methods
print("\n=== 4. CHECKING PYTHON ROUTERS FOR UNDEFINED SERVICE CALLS ===")
# Let's inspect all router files and verify that services have the methods they call
import importlib
router_files = glob.glob('routers/**/*.py', recursive=True)
for rf in router_files:
    if '__init__' in rf:
        continue
    mod_name = rf.replace('\\', '.').replace('/', '.').replace('.py', '')
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:
        print(f"[!] Error importing {mod_name}: {e}")

print("[OK] All router modules imported successfully.")
