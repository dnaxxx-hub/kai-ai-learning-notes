"""
Test suite for MiniLang VM (C backend + Python bytecode compiler).
"""

from compiler import compile_source
from vm_bridge import run_bytecode


def run_test(name, source, expected):
    """Compile source, run VM, compare output."""
    instructions, constants, symbols = compile_source(source)
    output = run_bytecode(instructions, constants, symbols)
    output_str = ' '.join(output)
    expected_str = ' '.join(str(e) for e in (expected if isinstance(expected, (list, tuple)) else [expected]))
    
    passed = (output_str == expected_str)
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status} | {name}")
    if not passed:
        print(f"         Expected: {expected_str!r}")
        print(f"         Got:      {output_str!r}")
        print(f"         Output lines: {output}")
        print(f"         Bytecode ({len(instructions)} instructions):")
        for i, (op, arg) in enumerate(instructions[:30]):
            print(f"           {i:4d}: op={op:2d}, arg={arg:6d}")
        if len(instructions) > 30:
            print(f"           ... ({len(instructions)} total)")
    return passed


def main():
    tests = [
        ("1. Constant expression", "print(42);", [42]),
        ("2. Variable assignment", "a = 10; print(a);", [10]),
        ("3. Arithmetic", "a = 1 + 2 * 3; print(a);", [7]),
        ("4. Condition (true)", "if (5 > 3) { print(1); } else { print(0); }", [1]),
        ("5. Loop", """
i = 0;
while (i < 5) {
    print(i);
    i = i + 1;
}
""", [0, 1, 2, 3, 4]),
        ("6. Function call", """
def add(a, b) {
    return a + b;
}
print(add(3, 4));
""", [7]),
        ("7. Nested function call", """
def add(a, b) {
    return a + b;
}
print(add(add(1, 2), 3));
""", [6]),
        ("8. Recursive factorial", """
def fact(n) {
    if (n <= 1) {
        return 1;
    }
    return n * fact(n - 1);
}
print(fact(5));
""", [120]),
        ("9. Multiple functions", """
def sq(x) {
    return x * x;
}
def sum_sq(a, b) {
    return sq(a) + sq(b);
}
print(sum_sq(3, 4));
""", [25]),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("MiniLang VM Test Suite")
    print("=" * 60)

    for name, source, expected in tests:
        if run_test(name, source, expected):
            passed += 1
        else:
            failed += 1
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed / {len(tests)} total")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
