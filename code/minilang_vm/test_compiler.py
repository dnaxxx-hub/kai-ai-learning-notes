"""Test the compiler."""
from compiler import compile_source

sources = [
    ("print(42)", "print(42);"),
    ("var assign", "a = 10; print(a);"),
    ("arithmetic", "a = 1 + 2 * 3; print(a);"),
]

for name, src in sources:
    print(f"\n=== {name} ===")
    print(f"Source: {src!r}")
    try:
        inst, consts, syms = compile_source(src)
        print(f"Instructions ({len(inst)}):")
        for i, (op, arg) in enumerate(inst):
            print(f"  {i}: op={op}, arg={arg}")
        print(f"Constants: {consts}")
        print(f"Symbols: {syms}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
