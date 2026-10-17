import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

def check_file(filepath):
    print(f"\nChecking {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple scanner that tracks strings, template literals, and comments
    stack = []
    i = 0
    n = len(content)
    line = 1
    col = 1

    while i < n:
        c = content[i]
        
        # Track line & col
        if c == '\n':
            line += 1
            col = 1
            i += 1
            continue

        # Single-line comment
        if c == '/' and i + 1 < n and content[i+1] == '/':
            while i < n and content[i] != '\n':
                i += 1
            continue

        # Multi-line comment
        if c == '/' and i + 1 < n and content[i+1] == '*':
            i += 2
            while i + 1 < n and not (content[i] == '*' and content[i+1] == '/'):
                if content[i] == '\n':
                    line += 1
                i += 1
            i += 2
            continue

        # Single or double quoted string
        if c in ("'", '"'):
            quote = c
            i += 1
            while i < n and content[i] != quote:
                if content[i] == '\\':
                    i += 2
                elif content[i] == '\n':
                    break # multiline error in normal string
                else:
                    i += 1
            i += 1
            continue

        # Template literal
        if c == '`':
            i += 1
            while i < n and content[i] != '`':
                if content[i] == '\\':
                    i += 2
                elif content[i] == '$' and i + 1 < n and content[i+1] == '{':
                    stack.append(('`', line, col))
                    stack.append(('${', line, col))
                    i += 2
                    break
                else:
                    if content[i] == '\n':
                        line += 1
                    i += 1
            else:
                i += 1
            continue

        if c in ('(', '[', '{'):
            stack.append((c, line, col))
        elif c in (')', ']', '}'):
            if not stack:
                print(f"  ❌ Extra closing '{c}' at line {line}, col {col}")
            else:
                top, t_line, t_col = stack.pop()
                expected = {'(': ')', '[': ']', '{': '}'}.get(top)
                if top == '${' and c == '}':
                    # return to template literal
                    continue
                if expected != c:
                    print(f"  ❌ Mismatch: got '{c}' at line {line}:{col}, expected '{expected}' (opened '{top}' at {t_line}:{t_col})")
        
        i += 1
        col += 1

    if stack:
        print(f"  ❌ {len(stack)} unclosed brackets:")
        for item in stack[:10]:
            print(f"     Unclosed {item[0]} from line {item[1]}:{item[2]}")
    else:
        print("  ✅ Brackets and syntax matched perfectly!")

check_file('static/chat.js')
check_file('static/stock.js')
check_file('static/reports.js')
check_file('static/scan.js')
check_file('static/track.js')
