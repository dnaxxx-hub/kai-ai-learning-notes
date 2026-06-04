"""Fix the lexer to handle > and < as single-char operators."""
path = r'C:\Users\Admin\.openclaw\workspace\projects\minilang_vm\compiler.py'
with open(path, 'r') as f:
    content = f.read()

old = "elif ch in '+-*/%=':"
new = "elif ch in '+-*/%=><':"
if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print("Fixed!")
else:
    print(f"Pattern {old!r} not found!")
    for i, line in enumerate(content.split('\n')):
        if "'+-*/%'" in line:
            print(f"Line {i+1}: {line!r}")
