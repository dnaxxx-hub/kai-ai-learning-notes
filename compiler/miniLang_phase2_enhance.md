# MiniLang VM — Phase 2 Enhancements

## Date: 2026-05-30

## Summary
Successfully enhanced the MiniLang VM with:
- **String support** (literals, concatenation, string * number)
- **List support** (literals, index get/set, len())
- **Boolean operations** (and/or/not with short-circuit evaluation)
- **Import/export cleanup** (clean `__init__.py`)
- **Error handling improvements** (line numbers, type/name error subclasses)
- **ListSet assignment** (`lst[0] = value` syntax)

## Test Results
- **C Bridge path** (compiler.py → C DLL): 12/12 tests passing
- **Tree-walk interpreter** (minilang_vm.py): 27/27 tests passing
- **Total**: 39/39 all green 🟢

## Key Changes

### `minilang_vm.py` (70KB — the full interpreter)
- Added `ListSet` AST node for `lst[idx] = value` assignment
- Updated `_assignment()` parser to handle subscript as assignment target
- Added `_evaluate_list_set()` in interpreter
- Added `MiniLangTypeError` and `MiniLangNameError` as `MiniLangRuntimeError` subclasses
- Enhanced `ParseError` with source context display (line + code snippet)
- Fixed `run_bc()` to properly use C bridge path

### `compiler.py` (29KB — C bridge compiler)
- Added lexer support for `&&`, `||`, `!`, `[`, `]`
- Added `true`, `false`, `and`, `or`, `not` keywords
- Added logical AND/OR with short-circuit evaluation to expression parser
- Added `!` unary operator (compiles to EQ with 0)
- Updated precedence table

### `__init__.py`
- Clean exports: now explicitly lists all public API symbols
- Tested: `from minilang_vm import run_source, Lexer, Parser, etc.`

### `test_minilang_vm.py`
- Expanded from 9 to 39 tests covering both C bridge and tree-walk paths
- Phase 2 features tested: strings, lists, booleans, short-circuit eval

## Architecture Notes
- **Two parallel systems**: C bridge (compiler.py → C DLL) for speed; Tree-walk (minilang_vm.py) for feature completeness
- Strings/lists/booleans work fully in tree-walk; C bridge supports only the `!`/`&&`/`||` operators and basic types
- `run_bc()` now redirects to C bridge path (via vm_bridge.py) instead of calling mismatched API
