"""vm.py — MiniLang Bytecode Virtual Machine

A stack-based VM that executes Bytecode instructions.

Design:
- Fetch → Decode → Execute loop
- Operand stack for expression evaluation
- Call stack (Frames) for function calls
- Frame: ip (instruction pointer), code (Bytecode), stack, locals, closure
- Global environment for top-level variables
- Upvalue management for closures
"""

import math
import random
import json
import time as _time
import urllib.request
import urllib.error
from typing import Any, List, Optional, Dict, Callable as FnType
from bytecode import Bytecode, OPCODE_NAMES, Instruction
from minilang_vm import _NATIVE_PRINT_BUFFER, _to_string, _STDLIB_MODULES
import bytecode as bc


# ====== Runtime Value Types ======
RT_NUMBER = "number"
RT_STRING = "string"
RT_BOOL = "bool"
RT_NIL = "nil"
RT_LIST = "list"
RT_FUNCTION = "function"
RT_NATIVE_FN = "native_fn"


class RuntimeValue:
    __slots__ = ("type", "value")

    def __init__(self, type_name: str, value: Any):
        self.type = type_name
        self.value = value

    def __repr__(self):
        return f"RuntimeValue({self.type}, {self.value!r})"


class Function:
    """A closure: bytecode + captured upvalues."""
    __slots__ = ("bc", "upvalues")

    def __init__(self, bc: Bytecode, upvalues: List):
        self.bc = bc
        self.upvalues = upvalues

    def arity(self) -> int:
        return self.bc.arity

    def __repr__(self):
        return f"<fn {self.bc.name}>"


class Upvalue:
    """A captured variable from an enclosing scope."""
    __slots__ = ("index", "is_local", "closed")

    def __init__(self, index: int, is_local: bool):
        self.index = index
        self.is_local = is_local
        self.closed = None


class Frame:
    """A call frame (activation record)."""
    __slots__ = ("code", "fn", "ip", "stack", "stack_top",
                 "locals", "upvalues")

    def __init__(self, code: Bytecode, fn: Optional[Function], num_locals: int):
        self.code = code
        self.fn = fn
        self.ip = 0
        self.stack = [None] * VM.STACK_MAX
        self.stack_top = 0
        self.locals = [RuntimeValue(RT_NIL, None)] * max(num_locals, 1)
        self.upvalues: List[Upvalue] = []


class MiniLangRuntimeError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"[Runtime Error] Line {line}: {message}" if line else f"[Runtime Error] {message}")


class VMError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"VM Error: {message}")


# ====== Native Functions ======

def _native_print(*args, line: int = 0):
    output = " ".join(_to_string(a) for a in args)
    _NATIVE_PRINT_BUFFER.append(output)
    print(output)
    return RuntimeValue(RT_NIL, None)


def _native_len(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("len() requires 1 argument", line)
    val = args[0]
    if val.type == RT_STRING:
        return RuntimeValue(RT_NUMBER, len(val.value))
    if val.type == RT_LIST:
        return RuntimeValue(RT_NUMBER, len(val.value))
    raise MiniLangRuntimeError(f"len() not supported for {val.type}", line)


def _native_str(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_STRING, "")
    return RuntimeValue(RT_STRING, _to_string(args[0]))


def _native_int(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_NUMBER, 0)
    val = args[0]
    if val.type == RT_NUMBER:
        return RuntimeValue(RT_NUMBER, int(val.value))
    if val.type == RT_STRING:
        try:
            return RuntimeValue(RT_NUMBER, int(val.value))
        except ValueError:
            raise MiniLangRuntimeError(f"Cannot convert '{val.value}' to int", line)
    raise MiniLangRuntimeError(f"Cannot convert {val.type} to int", line)


def _native_type(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_STRING, "nil")
    return RuntimeValue(RT_STRING, args[0].type)


def _native_input(*args, line: int = 0):
    prompt = ""
    if args:
        prompt = _to_string(args[0])
    try:
        result = input(prompt)
        return RuntimeValue(RT_STRING, result)
    except EOFError:
        return RuntimeValue(RT_STRING, "")


def _native_sqrt(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("sqrt() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"sqrt() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, math.sqrt(val.value))


def _native_abs(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("abs() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"abs() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, abs(val.value))


def _native_rand(*args, line: int = 0):
    if len(args) == 0:
        return RuntimeValue(RT_NUMBER, random.random())
    if len(args) == 1:
        if args[0].type != RT_NUMBER:
            raise MiniLangRuntimeError("rand() requires a number", line)
        return RuntimeValue(RT_NUMBER, random.randint(0, int(args[0].value)))
    if len(args) == 2:
        if args[0].type != RT_NUMBER or args[1].type != RT_NUMBER:
            raise MiniLangRuntimeError("rand() requires numbers", line)
        return RuntimeValue(RT_NUMBER, random.randint(int(args[0].value), int(args[1].value)))
    raise MiniLangRuntimeError("rand() takes 0-2 arguments", line)


# ====== Built-in functions map ======
_BUILTINS = {
    "print": _native_print,
    "len": _native_len,
    "str": _native_str,
    "int": _native_int,
    "type": _native_type,
    "input": _native_input,
    "sqrt": _native_sqrt,
    "abs": _native_abs,
    "rand": _native_rand,
}


# ====== VM ======
class VM:
    """Minimal bytecode virtual machine."""

    STACK_MAX = 1024

    def __init__(self):
        self.globals: Dict[str, RuntimeValue] = {}
        self._init_globals()
        self.frames: List[Frame] = []
        self._open_upvalues: List[Upvalue] = []

    def _init_globals(self):
        """Initialize global built-in functions."""
        # Register stdlib modules as dict-like lists of [key, value] pairs
        for mod_name, mod_fns in _STDLIB_MODULES.items():
            module_dict = []
            for fn_name, fn in mod_fns.items():
                pair = [
                    RuntimeValue(RT_STRING, fn_name),
                    RuntimeValue(RT_NATIVE_FN, fn)
                ]
                module_dict.append(RuntimeValue(RT_LIST, pair))
            self.globals[mod_name] = RuntimeValue(RT_LIST, module_dict)
        # Register builtins last so they take precedence
        for name, fn in _BUILTINS.items():
            self.globals[name] = RuntimeValue(RT_NATIVE_FN, fn)

    def execute(self, code: Bytecode) -> Optional[RuntimeValue]:
        """Execute a Bytecode program. Returns the result value."""
        self.frames.clear()
        self._open_upvalues.clear()

        # Create initial frame for script
        frame = Frame(code, None, code.num_locals)
        self.frames.append(frame)
        self._script_frame = frame

        try:
            while True:
                instr = self._read_instruction()
                result = self._execute_instruction(instr)
                if result == "RETURN":
                    break
        except MiniLangRuntimeError:
            raise
        except VMError as e:
            raise MiniLangRuntimeError(e.message)
        except Exception as e:
            raise MiniLangRuntimeError(f"VM error: {e}")

        if frame.stack:
            return frame.stack[-1]
        return None

    @property
    def _current_frame(self) -> Frame:
        if not self.frames:
            raise VMError("No active frame")
        return self.frames[-1]

    def _read_instruction(self) -> Instruction:
        frame = self._current_frame
        if frame.ip >= len(frame.code.instructions):
            return Instruction(80, 0, 0, 0)  # NOP
        op = frame.code.instructions[frame.ip]
        arg1 = frame.code.instructions[frame.ip + 1]
        arg2 = frame.code.instructions[frame.ip + 2]
        arg3 = frame.code.instructions[frame.ip + 3]
        frame.ip += 4
        return Instruction(op, arg1, arg2, arg3)

    def _push(self, value: RuntimeValue):
        frame = self._current_frame
        if frame.stack_top >= VM.STACK_MAX:
            raise VMError("Stack overflow")
        frame.stack[frame.stack_top] = value
        frame.stack_top += 1

    def _pop(self) -> RuntimeValue:
        frame = self._current_frame
        if frame.stack_top <= 0:
            raise VMError("Stack underflow")
        frame.stack_top -= 1
        return frame.stack[frame.stack_top]

    def _peek(self, depth: int = 0) -> RuntimeValue:
        frame = self._current_frame
        idx = frame.stack_top - 1 - depth
        if idx < 0:
            raise VMError("Stack underflow (peek)")
        return frame.stack[idx]

    def _execute_instruction(self, instr: Instruction) -> Optional[str]:
        """Execute a single instruction. Returns 'RETURN' on script return."""
        op = instr.op

        if op == bc.NOP:
            pass

        elif op == bc.LOAD_CONST:
            idx = instr.arg1 | (instr.arg2 << 8)
            if idx < len(self._current_frame.code.constants):
                # Import from minilang_vm's constants
                const = self._current_frame.code.constants[idx]
                if isinstance(const, RuntimeValue):
                    self._push(const)
                elif isinstance(const, str):
                    self._push(RuntimeValue(RT_STRING, const))
                elif isinstance(const, (int, float)):
                    self._push(RuntimeValue(RT_NUMBER, const))
                elif isinstance(const, bool):
                    self._push(RuntimeValue(RT_BOOL, const))
                elif const is None:
                    self._push(RuntimeValue(RT_NIL, None))
                else:
                    self._push(RuntimeValue(RT_STRING, str(const)))
            else:
                raise VMError(f"Constant index {idx} out of range")

        elif op == bc.LOAD_GLOBAL:
            frame = self._current_frame
            idx = instr.arg1 | (instr.arg2 << 8)
            if idx < len(frame.code.constants):
                name = frame.code.constants[idx]
                if isinstance(name, RuntimeValue):
                    name = name.value
                elif isinstance(name, str):
                    pass
                else:
                    name = str(name)
                if name in self.globals:
                    self._push(self.globals[name])
                else:
                    raise VMError(f"Undefined variable '{name}'")
            else:
                raise VMError(f"Constant index {idx} out of range")

        elif op == bc.STORE_GLOBAL:
            frame = self._current_frame
            idx = instr.arg1 | (instr.arg2 << 8)
            name = frame.code.constants[idx]
            if isinstance(name, RuntimeValue):
                name = name.value
            value = self._pop()
            self.globals[name] = value

        elif op == bc.LOAD_FAST:
            slot = instr.arg1 | (instr.arg2 << 8)
            frame = self._current_frame
            if slot < len(frame.locals):
                self._push(frame.locals[slot])
            else:
                raise VMError(f"Local slot {slot} out of range")

        elif op == bc.STORE_FAST:
            slot = instr.arg1 | (instr.arg2 << 8)
            frame = self._current_frame
            if slot < len(frame.locals):
                frame.locals[slot] = self._pop()
            else:
                raise VMError(f"Local slot {slot} out of range")

        elif op == bc.LOAD_UPVALUE:
            slot = instr.arg1 | (instr.arg2 << 8)
            frame = self._current_frame
            if slot < len(frame.upvalues):
                uv = frame.upvalues[slot]
                if uv.closed is not None:
                    self._push(uv.closed)
                else:
                    # Find the enclosing frame
                    for f in reversed(self.frames[:-1]):
                        if slot < len(f.locals):
                            self._push(f.locals[slot])
                            break
                    else:
                        self._push(RuntimeValue(RT_NIL, None))
            else:
                raise VMError(f"Upvalue slot {slot} out of range")

        elif op == bc.STORE_UPVALUE:
            slot = instr.arg1 | (instr.arg2 << 8)
            frame = self._current_frame
            if slot < len(frame.upvalues):
                uv = frame.upvalues[slot]
                val = self._pop()
                if uv.closed is not None:
                    uv.closed = val
                else:
                    for f in reversed(self.frames[:-1]):
                        if slot < len(f.locals):
                            f.locals[slot] = val
                            break
            else:
                raise VMError(f"Upvalue slot {slot} out of range")

        elif op == bc.ADD:
            b = self._pop()
            a = self._pop()
            if a.type == RT_NUMBER and b.type == RT_NUMBER:
                self._push(RuntimeValue(RT_NUMBER, a.value + b.value))
            elif a.type == RT_STRING and b.type == RT_STRING:
                self._push(RuntimeValue(RT_STRING, a.value + b.value))
            elif a.type == RT_STRING:
                self._push(RuntimeValue(RT_STRING, a.value + _to_string(b)))
            elif b.type == RT_STRING:
                self._push(RuntimeValue(RT_STRING, _to_string(a) + b.value))
            else:
                raise VMError(f"Cannot add {a.type} and {b.type}")

        elif op == bc.SUB:
            b = self._pop()
            a = self._pop()
            self._check_number("subtract", a, b)
            self._push(RuntimeValue(RT_NUMBER, a.value - b.value))

        elif op == bc.MUL:
            b = self._pop()
            a = self._pop()
            if a.type == RT_NUMBER and b.type == RT_NUMBER:
                self._push(RuntimeValue(RT_NUMBER, a.value * b.value))
            elif a.type == RT_STRING and b.type == RT_NUMBER:
                self._push(RuntimeValue(RT_STRING, a.value * b.value))
            else:
                raise VMError(f"Cannot multiply {a.type} and {b.type}")

        elif op == bc.DIV:
            b = self._pop()
            a = self._pop()
            self._check_number("divide", a, b)
            if b.value == 0:
                raise VMError("Division by zero")
            self._push(RuntimeValue(RT_NUMBER, a.value / b.value))

        elif op == bc.MOD:
            b = self._pop()
            a = self._pop()
            self._check_number("modulo", a, b)
            if b.value == 0:
                raise VMError("Division by zero")
            self._push(RuntimeValue(RT_NUMBER, a.value % b.value))

        elif op == bc.NEG:
            a = self._pop()
            if a.type != RT_NUMBER:
                raise VMError(f"Cannot negate {a.type}")
            self._push(RuntimeValue(RT_NUMBER, -a.value))

        elif op == bc.PUSH_TRUE:
            self._push(RuntimeValue(RT_BOOL, True))

        elif op == bc.PUSH_FALSE:
            self._push(RuntimeValue(RT_BOOL, False))

        elif op == bc.PUSH_NIL:
            self._push(RuntimeValue(RT_NIL, None))

        elif op == bc.DUP:
            # Duplicate top of stack
            val = self._peek()
            self._push(val)

        elif op == bc.POP:
            # Discard top of stack
            self._pop()

        elif op == bc.EQ:
            b = self._pop()
            a = self._pop()
            result = self._values_equal(a, b)
            self._push(RuntimeValue(RT_BOOL, result))

        elif op == bc.NE:
            b = self._pop()
            a = self._pop()
            result = not self._values_equal(a, b)
            self._push(RuntimeValue(RT_BOOL, result))

        elif op == bc.GT:
            b = self._pop()
            a = self._pop()
            self._check_number(">", a, b)
            self._push(RuntimeValue(RT_BOOL, a.value > b.value))

        elif op == bc.GE:
            b = self._pop()
            a = self._pop()
            self._check_number(">=", a, b)
            self._push(RuntimeValue(RT_BOOL, a.value >= b.value))

        elif op == bc.LT:
            b = self._pop()
            a = self._pop()
            self._check_number("<", a, b)
            self._push(RuntimeValue(RT_BOOL, a.value < b.value))

        elif op == bc.LE:
            b = self._pop()
            a = self._pop()
            self._check_number("<=", a, b)
            self._push(RuntimeValue(RT_BOOL, a.value <= b.value))

        elif op == bc.JMP:
            offset = (instr.arg1 << 16) | (instr.arg2 << 8) | instr.arg3
            if offset & 0x800000:
                offset -= 0x1000000
            self._current_frame.ip += offset - 4

        elif op == bc.JMP_IF_FALSE:
            cond = self._pop()
            if not self._is_truthy(cond):
                offset = (instr.arg1 << 16) | (instr.arg2 << 8) | instr.arg3
                if offset & 0x800000:
                    offset -= 0x1000000
                self._current_frame.ip += offset - 4

        elif op == bc.JMP_IF_TRUE:
            cond = self._pop()
            if self._is_truthy(cond):
                offset = (instr.arg1 << 16) | (instr.arg2 << 8) | instr.arg3
                if offset & 0x800000:
                    offset -= 0x1000000
                self._current_frame.ip += offset - 4

        elif op == bc.CALL:
            arg_count = instr.arg1
            self._call(arg_count)

        elif op == bc.RET:
            result = self._pop() if self._current_frame.stack_top > 0 else RuntimeValue(RT_NIL, None)
            if len(self.frames) <= 1:
                # Script return - push result back
                self._push(result)
                return "RETURN"
            self.frames.pop()
            # Push return value onto caller's stack
            if self.frames:
                self._push(result)

        elif op == bc.MAKE_FN:
            frame = self._current_frame
            fn_idx = instr.arg1 | (instr.arg2 << 8)
            if fn_idx < len(frame.code.functions):
                fn_bc = frame.code.functions[fn_idx]
                # Create upvalues for this closure
                upvalues = []
                if hasattr(fn_bc, '_upvalue_indices'):
                    for i, idx in enumerate(fn_bc._upvalue_indices):
                        is_local = fn_bc._upvalue_is_local[i]
                        upval = Upvalue(idx, is_local)
                        upvalues.append(upval)
                        if is_local:
                            self._open_upvalues.append(upval)
                fn = Function(fn_bc, upvalues)
                self._push(RuntimeValue(RT_FUNCTION, fn))
            else:
                raise VMError(f"Function index {fn_idx} out of range")

        elif op == bc.CLOSE_UPVALUE:
            # Close an upvalue (move from stack to closed value)
            val = self._pop()
            if self.frames:
                uv = Upvalue(0, True)
                uv.closed = val
                self._open_upvalues.clear()
                # Re-push the value so stack stays consistent
                self._push(val)

        elif op == bc.BUILD_LIST:
            count = instr.arg1
            elements = []
            for _ in range(count):
                elements.insert(0, self._pop())
            self._push(RuntimeValue(RT_LIST, elements))

        elif op == bc.LIST_INDEX:
            idx_val = self._pop()
            obj = self._pop()
            if obj.type != RT_LIST:
                raise VMError("Cannot index non-list value")
            lst = obj.value
            if idx_val.type == RT_NUMBER:
                index = int(idx_val.value)
                if index < 0 or index >= len(lst):
                    raise VMError(f"List index {index} out of range [0, {len(lst)})")
                self._push(lst[index])
            elif idx_val.type == RT_STRING:
                # Dict-like lookup on list of [key, value] pairs
                key = idx_val.value
                found = False
                for item in lst:
                    if item.type == RT_LIST and len(item.value) == 2:
                        k = item.value[0]
                        if k.type == RT_STRING and k.value == key:
                            self._push(item.value[1])
                            found = True
                            break
                if not found:
                    raise VMError(f"Key '{key}' not found in module")
            else:
                raise VMError(f"List index must be a number or string, got {idx_val.type}")

        elif op == bc.PRINT:
            val = self._pop()
            _native_print(val)
            self._push(RuntimeValue(RT_NIL, None))

        else:
            raise VMError(f"Unknown opcode: {op}")

    def _call(self, arg_count: int):
        """Handle a function call."""
        callee = self._peek(arg_count)  # Function is below arguments on stack

        if callee.type == RT_NATIVE_FN:
            # Native function call
            args = []
            for i in range(arg_count):
                args.insert(0, self._pop())
            callee_val = self._pop()
            result = callee_val.value(*args)
            self._push(result)
            return

        if callee.type != RT_FUNCTION:
            raise VMError(f"Cannot call {callee.type}")

        func: Function = callee.value
        if arg_count != func.arity():
            raise VMError(f"Expected {func.arity()} arguments but got {arg_count}")

        # Create new frame
        new_frame = Frame(func.bc, func, func.bc.num_locals)

        # Pop arguments from caller's stack and set as locals
        for i in range(arg_count - 1, -1, -1):
            arg_val = self._pop()
            new_frame.locals[i] = arg_val

        # Pop function itself
        self._pop()

        # Set up upvalues from the closure
        new_frame.upvalues = list(func.upvalues)

        self.frames.append(new_frame)

    def _is_truthy(self, value: RuntimeValue) -> bool:
        if value.type == RT_NIL:
            return False
        if value.type == RT_BOOL:
            return value.value
        if value.type == RT_NUMBER:
            return value.value != 0
        if value.type == RT_STRING:
            return value.value != ""
        if value.type == RT_LIST:
            return len(value.value) > 0
        return True

    def _values_equal(self, a: RuntimeValue, b: RuntimeValue) -> bool:
        if a.type != b.type:
            return False
        if a.type == RT_NIL:
            return True
        if a.type == RT_LIST:
            if len(a.value) != len(b.value):
                return False
            for i in range(len(a.value)):
                if not self._values_equal(a.value[i], b.value[i]):
                    return False
            return True
        return a.value == b.value

    def _check_number(self, op_name: str, a: RuntimeValue, b: RuntimeValue):
        if a.type != RT_NUMBER or b.type != RT_NUMBER:
            raise VMError(f"Cannot {op_name} {a.type} and {b.type}")
