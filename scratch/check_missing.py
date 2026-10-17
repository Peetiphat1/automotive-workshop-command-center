import os
import glob
import re
import sys

sys.path.insert(0, '.')
from main import app

backend_routes = {}
for r in app.routes:
    if hasattr(r, 'path'):
        norm = re.sub(r'\{[^}]+\}', '*', r.path)
        methods = list(getattr(r, 'methods', ['GET']))
        backend_routes[norm] = methods

print(f"Total registered backend routes: {len(app.routes)}")

# Find all fetch calls and API URLs in JS files
js_files = glob.glob('static/**/*.js', recursive=True)
html_files = glob.glob('static/**/*.html', recursive=True)

print("\n--- Scanning JS files for API calls ---")
api_url_regex = re.compile(r'(/api/v1/[a-zA-Z0-9_\-\/\$\{\}]+)')
found_apis = []
for jf in js_files + html_files:
    with open(jf, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
        for match in api_url_regex.finditer(text):
            found_apis.append((jf, match.group(1)))

print(f"Found {len(found_apis)} API references in static files.")

# Check for unmatched routes
unmatched = []
for file, path in found_apis:
    # Normalize template literal expressions like ${id} or ${query} or numbers
    clean_path = re.sub(r'\$\{[^}]+\}', '*', path)
    clean_path = re.sub(r'/\d+', '/*', clean_path)
    clean_path = clean_path.rstrip('/')
    
    # Check if matches any route
    matched = False
    for br in backend_routes:
        norm_br = br.rstrip('/')
        pattern = '^' + re.escape(norm_br).replace(r'\*', r'[^/]+') + '$'
        if re.match(pattern, clean_path) or clean_path == norm_br:
            matched = True
            break
        # Also check prefix if query params or trailing subpath
        if norm_br.endswith('/*') and clean_path.startswith(norm_br[:-2]):
            matched = True
            break
    if not matched:
        unmatched.append((file, path, clean_path))

for f, p, cp in set(unmatched):
    print(f"WARNING: No matching route for: {p} (in {f})")

# Check all functions in HTML files that are called in onclick, onchange, onsubmit, etc.
print("\n--- Checking HTML event handlers ---")
inline_event_regex = re.compile(r'\bon[a-z]+\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
call_regex = re.compile(r'([a-zA-Z0-9_$]+)\s*\(')

# Collect all JS definitions across all JS files
js_defs = set()
for jf in js_files:
    with open(jf, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # function name(
        for m in re.finditer(r'\bfunction\s+([a-zA-Z0-9_$]+)\s*\(', content):
            js_defs.add(m.group(1))
        # window.name = or const/let/var name =
        for m in re.finditer(r'\b(?:window\.)?([a-zA-Z0-9_$]+)\s*=\s*(?:function|\([^)]*\)\s*=>|async)', content):
            js_defs.add(m.group(1))
        # class Name
        for m in re.finditer(r'\bclass\s+([a-zA-Z0-9_$]+)', content):
            js_defs.add(m.group(1))

builtin_js = {'alert', 'confirm', 'prompt', 'if', 'event', 'console', 'fetch', 'setTimeout', 'setInterval', 'location', 'history', 'window', 'document', 'open', 'close', 'parseInt', 'parseFloat', 'encodeURIComponent', 'decodeURIComponent'}

for hf in html_files:
    with open(hf, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        for evt in inline_event_regex.finditer(content):
            handler_code = evt.group(1)
            for call in call_regex.finditer(handler_code):
                fn = call.group(1)
                if fn not in js_defs and fn not in builtin_js:
                    print(f"POTENTIAL MISSING JS FUNCTION: '{fn}()' called in {hf} on line: {handler_code.strip()[:60]}")

print("\n--- Scanning for TODO/FIXME/NotImplemented in all python and js files ---")
for root, dirs, files in os.walk('.'):
    if any(ignore in root for ignore in ['.venv', '.git', '__pycache__', 'scratch']):
        continue
    for file in files:
        if file.endswith(('.py', '.js')):
            full_path = os.path.join(root, file)
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                for idx, line in enumerate(f, 1):
                    if any(kw in line for kw in ['TODO', 'FIXME', 'NotImplementedError', 'pass  #', 'raise NotImplemented']):
                        print(f"{full_path}:{idx}: {line.strip()}")
