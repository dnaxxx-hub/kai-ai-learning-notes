"""Fix the lexer to handle '>' and '<' correctly."""
path = r'C:\Users\Admin\.openclaw\workspace\projects\minilang_vm\compiler.py'
with open(path, 'r') as f:
    content = f.read()

# Fix multi-char operator detection (remove stray space)
old = "if ch in '!<>= ' and self.pos"
new = "if ch in '!<>=' and self.pos"
if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Pattern not found!")
    # Debug: find the line
    for i, line in enumerate(content.split('\n')):
        if "!<>= " in line:
            print(f"Line {i+1}: {line!r}")
