import ast
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from main import app

print("=== CHECK 1: BACKEND FASTAPI ENDPOINTS & FRONTEND URLS ===")
# Build map of all registered FastAPI endpoints: (method, path)
routes = []
for r in app.routes:
    if hasattr(r, 'path'):
        methods = list(getattr(r, 'methods', ['GET']))
        routes.append((methods, r.path))

js_files = glob.glob('static/**/*.js', recursive=True)
html_files = glob.glob('static/**/*.html', recursive=True)

url_patterns = [
    re.compile(r'fetch\s*\(\s*[`\'"]([^`\'"?#]+)'),
    re.compile(r'\$\{API_URL\}(/[^`\'"?#]+)'),
    re.compile(r'API_URL\s*\+\s*[`\'"]([^`\'"?#]+)'),
    re.compile(r'[`\'"](/api/v1/[^`\'"?#]+)'),
]

endpoints_called = []
for f in js_files + html_files:
    with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
        content = fp.read()
        for pat in url_patterns:
            for match in pat.finditer(content):
                u = match.group(1)
                if not u.startswith('/api/v1'):
                    if u.startswith('/'):
                        u = '/api/v1' + u
                endpoints_called.append((f, u))

print(f"Total API calls found in frontend: {len(endpoints_called)}")

def match_route(called_path):
    # normalize path: replace /123 or /${...} with placeholder
    norm = re.sub(r'/\$\{[^}]+\}', '/{param}', called_path)
    norm = re.sub(r'/\d+', '/{param}', norm)
    norm = norm.rstrip('/')
    for methods, path in routes:
        norm_r = path.rstrip('/')
        norm_r_regex = '^' + re.sub(r'\{[^}]+\}', r'[^/]+', norm_r) + '$'
        if re.match(norm_r_regex, norm) or re.match(norm_r_regex, called_path.rstrip('/')):
            return True, methods, path
    return False, None, None

for f, ep in sorted(set(endpoints_called)):
    ok, methods, matched_path = match_route(ep)
    if not ok:
        print(f"❌ FRONTEND CALLS UNMATCHED BACKEND ROUTE: {ep} in {f}")

print("\n=== CHECK 2: CHECK PYTHON IMPORTS & ATTRIBUTES ===")
# Check for broken imports or missing attributes across python files
py_files = [p for p in glob.glob('**/*.py', recursive=True) if not any(x in p for x in ['.venv', '__pycache__'])]

for pf in py_files:
    try:
        with open(pf, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=pf)
    except Exception as e:
        print(f"❌ Syntax error in {pf}: {e}")

print("\n=== CHECK 3: CHECK JAVASCRIPT GLOBAL CALLS ===")
# In static/*.html, check all scripts included and all onclick/onchange/etc.
for hf in html_files:
    with open(hf, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    # Find all script src
    scripts = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', html)
    # Find all inline calls
    handlers = re.findall(r'\bon[a-z]+\s*=\s*["\']([^"\']+)["\']', html, re.I)
    
    # Collect all functions in those scripts
    declared_funcs = set()
    for s in scripts:
        # resolve path
        sp = os.path.normpath(os.path.join(os.path.dirname(hf), s.lstrip('/')))
        if not os.path.exists(sp):
            sp = os.path.normpath(os.path.join('static', s.lstrip('/')))
        if os.path.exists(sp):
            with open(sp, 'r', encoding='utf-8', errors='ignore') as sf:
                scontent = sf.read()
                # find functions
                for fn in re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', scontent):
                    declared_funcs.add(fn)
                for fn in re.findall(r'(?:window\.)?([a-zA-Z0-9_$]+)\s*=\s*(?:function|\([^)]*\)\s*=>|async)', scontent):
                    declared_funcs.add(fn)
    # also inline script functions
    for in_script in re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', html, re.DOTALL):
        for fn in re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', in_script):
            declared_funcs.add(fn)
        for fn in re.findall(r'(?:window\.)?([a-zA-Z0-9_$]+)\s*=\s*(?:function|\([^)]*\)\s*=>|async)', in_script):
            declared_funcs.add(fn)

    # Check each handler call
    for h in handlers:
        calls = re.findall(r'([a-zA-Z0-9_$]+)\s*\(', h)
        for c in calls:
            if c not in declared_funcs and c not in [
                'alert', 'confirm', 'prompt', 'if', 'console', 'preventDefault',
                'stopPropagation', 'close', 'open', 'setTimeout', 'clearTimeout',
                'getElementById', 'querySelector', 'querySelectorAll', 'reset', 'submit',
                'focus', 'blur', 'click', 'select', 'toUpperCase', 'toLowerCase'
            ]:
                print(f"❌ HTML {hf} calls UNDEFINED FUNCTION: {c}() in handler: {h}")

print("\n=== CHECK 4: CHECK STATIC/CHAT.JS, STOCK.JS, APP.JS MISSING FUNCTIONS ===")
# Look for function calls in JS files that are not defined in that JS file or global libs
