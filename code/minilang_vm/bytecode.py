"""bytecode.py — MiniLang Bytecode Instruction Set

Design:
- Fixed-width instructions (4 bytes each): opcode + 3 operand bytes
- Two sections: constants (data) and code (instructions)
- Each instruction: (op, arg1, arg2, arg3) where args are packed as signed 24-bit

Instruction Format:
  op (uint8) | arg1 (uint8) | arg2 (uint8) | arg3 (uint8)
  For jump offsets that exceed uint8, we encode the offset across 3 bytes.

Addressing:
- Implicit: no operands (PUSH_NIL, ADD, etc.)
- Immediate (arg): PUSH 42 → (PUSH, 0, 0, 42)
- Constant pool index: LOAD_CONST idx
- Stack slot: LOAD_FAST slot, STORE_FAST slot
- Label: JMP offset (relative, signed)
"""

import struct
from typing import List, Tuple, Any, Optional

# ====== Opcodes ======
# Stack operations
PUSH     = 1   # Push constant from pool
PUSH_NIL = 2
PUSH_TRUE = 3
PUSH_FALSE = 4
POP      = 5
DUP      = 6

# Variable operations (local)
LOAD_FAST  = 10  # Load local variable by slot index
STORE_FAST = 11  # Store local variable by slot index

# Variable operations (global)
LOAD_GLOBAL  = 12
STORE_GLOBAL = 13

# Variable operations (closure / upvalue)
LOAD_UPVALUE  = 14
STORE_UPVALUE = 15

# Variable operations (const)
LOAD_CONST = 16

# Arithmetic
ADD = 20
SUB = 21
MUL = 22
DIV = 23
MOD = 24
NEG = 25

# Comparison
EQ = 30
NE = 31
GT = 32
GE = 33
LT = 34
LE = 35

# Logical
NOT = 40

# Jump
JMP            = 50  # Unconditional jump
JMP_IF_FALSE   = 51  # Jump if top-of-stack is falsy
JMP_IF_TRUE    = 52  # Jump if top-of-stack is truthy

# Function
CALL       = 60
RET        = 61
MAKE_FN    = 62  # Create a closure from function index
CLOSE_UPVALUE = 63  # Close an upvalue

# List
BUILD_LIST = 70
LIST_INDEX = 71

# Other
NOP  = 80
PRINT = 81


# ====== Opcode Names ======
OPCODE_NAMES = {
    1: "PUSH",
    2: "PUSH_NIL",
    3: "PUSH_TRUE",
    4: "PUSH_FALSE",
    5: "POP",
    6: "DUP",
    10: "LOAD_FAST",
    11: "STORE_FAST",
    12: "LOAD_GLOBAL",
    13: "STORE_GLOBAL",
    14: "LOAD_UPVALUE",
    15: "STORE_UPVALUE",
    16: "LOAD_CONST",
    20: "ADD",
    21: "SUB",
    22: "MUL",
    23: "DIV",
    24: "MOD",
    25: "NEG",
    30: "EQ",
    31: "NE",
    32: "GT",
    33: "GE",
    34: "LT",
    35: "LE",
    40: "NOT",
    50: "JMP",
    51: "JMP_IF_FALSE",
    52: "JMP_IF_TRUE",
    60: "CALL",
    61: "RET",
    62: "MAKE_FN",
    63: "CLOSE_UPVALUE",
    70: "BUILD_LIST",
    71: "LIST_INDEX",
    80: "NOP",
    81: "PRINT",
}


class Instruction:
    """A single bytecode instruction."""
    __slots__ = ('op', 'arg1', 'arg2', 'arg3')

    def __init__(self, op: int, arg1: int = 0, arg2: int = 0, arg3: int = 0):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3

    def __repr__(self) -> str:
        name = OPCODE_NAMES.get(self.op, f"OP({self.op})")
        if self.arg1 or self.arg2 or self.arg3:
            return f"{name} {self.arg1} {self.arg2} {self.arg3}"
        return name

    def encode(self) -> bytes:
        return bytes([self.op, self.arg1 & 0xFF, self.arg2 & 0xFF, self.arg3 & 0xFF])

    def get_offset(self) -> int:
        """Extract a signed 24-bit offset from arg1..arg3 (big-endian, sign-extended)."""
        val = (self.arg1 << 16) | (self.arg2 << 8) | self.arg3
        if val & 0x800000:
            val -= 0x1000000
        return val

    @classmethod
    def decode(cls, data: bytes, offset: int) -> 'Instruction':
        op = data[offset]
        return cls(op, data[offset + 1], data[offset + 2], data[offset + 3])


class Bytecode:
    """Complete bytecode program with constant pool and instruction stream."""

    def __init__(self):
        self.constants: List[Any] = []      # Constant pool
        self.instructions: List[int] = []   # Flat byte array (4-byte aligned)
        self.functions: List['Bytecode'] = []           # Nested function bytecode
        self.name: str = "<script>"
        self.num_locals: int = 0
        self.num_params: int = 0
        self.upvalue_count: int = 0

    @property
    def arity(self) -> int:
        """Number of parameters (convenience alias for num_params)."""
        return self.num_params

    def add_constant(self, value: Any) -> int:
        """Add a value to the constant pool and return its index."""
        # Deduplicate simple constants
        for i, c in enumerate(self.constants):
            if type(c) is type(value) and c == value:
                return i
        self.constants.append(value)
        return len(self.constants) - 1

    def emit(self, op: int, arg1: int = 0, arg2: int = 0, arg3: int = 0):
        """Emit a single instruction."""
        self.instructions.append(op)
        self.instructions.append(arg1 & 0xFF)
        self.instructions.append(arg2 & 0xFF)
        self.instructions.append(arg3 & 0xFF)

    def emit_at(self, idx: int, op: int, arg1: int = 0, arg2: int = 0, arg3: int = 0):
        """Patch an instruction at the given byte index."""
        self.instructions[idx] = op
        self.instructions[idx + 1] = arg1 & 0xFF
        self.instructions[idx + 2] = arg2 & 0xFF
        self.instructions[idx + 3] = arg3 & 0xFF

    def emit_jump(self, op: int) -> int:
        """Emit a jump instruction with placeholder offset. Returns index to patch."""
        idx = len(self.instructions)
        self.emit(op, 0, 0, 0)
        return idx

    def patch_jump(self, jump_idx: int):
        """Patch the jump offset from jump_idx to current position.
        VM does frame.ip += offset - 4 after ip advanced by 4.
        So offset should be target - jump_idx (no -4).
        """
        target = len(self.instructions)
        offset = target - jump_idx
        self._set_offset(jump_idx, offset)

    def _set_offset(self, instr_idx: int, offset: int):
        """Set a signed 24-bit offset at the given instruction index."""
        if offset < 0:
            offset += 0x1000000
        self.instructions[instr_idx + 1] = (offset >> 16) & 0xFF
        self.instructions[instr_idx + 2] = (offset >> 8) & 0xFF
        self.instructions[instr_idx + 3] = offset & 0xFF

    def patch_jump_to_target(self, jump_idx: int, target_idx: int):
        """Patch jump at jump_idx to jump to target_idx."""
        offset = target_idx - jump_idx
        self._set_offset(jump_idx, offset)

    def add_function(self, fn: 'Bytecode') -> int:
        self.functions.append(fn)
        return len(self.functions) - 1

    def get_instruction_at(self, idx: int) -> Instruction:
        return Instruction.decode(self.instructions, idx)

    def __len__(self) -> int:
        return len(self.instructions)

    def encode(self) -> bytes:
        """Serialize to bytes."""
        # Header: num_constants (4) + num_instructions (4) + num_functions (4)
        parts = []
        parts.append(struct.pack('>III', len(self.constants), len(self.instructions), len(self.functions)))
        # Constants: for each, type (1) + data
        for c in self.constants:
            parts.append(self._encode_const(c))
        # Instructions
        parts.append(bytes(self.instructions))
        # Functions
        for fn in self.functions:
            parts.append(fn.encode())
        return b''.join(parts)

    @staticmethod
    def _encode_const(c: Any) -> bytes:
        t = type(c)
        if t is int:
            return struct.pack('>Bq', 0, c)
        elif t is float:
            return struct.pack('>Bd', 1, c)
        elif t is str:
            data = c.encode('utf-8')
            return struct.pack('>BI', 2, len(data)) + data
        elif t is bool:
            return struct.pack('>B?', 3, c)
        elif c is None:
            return struct.pack('>B', 4)
        else:
            raise TypeError(f"Cannot encode constant {type(c)}")

    @staticmethod
    def decode(data: bytes, offset: int = 0) -> 'Bytecode':
        """Deserialize from bytes."""
        import struct
        bc = Bytecode()
        num_constants, num_instructions, num_functions = struct.unpack_from('>III', data, offset)
        pos = offset + 12
        for _ in range(num_constants):
            val, pos = Bytecode._decode_const(data, pos)
            bc.constants.append(val)
        bc.instructions = list(data[pos:pos + num_instructions])
        pos += num_instructions
        for _ in range(num_functions):
            fn, pos = Bytecode.decode(data, pos)
            bc.functions.append(fn)
        return bc

    @staticmethod
    def _decode_const(data: bytes, pos: int) -> Tuple[Any, int]:
        import struct
        t = data[pos]
        pos += 1
        if t == 0:
            val = struct.unpack_from('>q', data, pos)[0]
            pos += 8
            return val, pos
        elif t == 1:
            val = struct.unpack_from('>d', data, pos)[0]
            pos += 8
            return val, pos
        elif t == 2:
            length = struct.unpack_from('>I', data, pos)[0]
            pos += 4
            val = data[pos:pos + length].decode('utf-8')
            pos += length
            return val, pos
        elif t == 3:
            val = bool(data[pos])
            pos += 1
            return val, pos
        elif t == 4:
            return None, pos
        else:
            raise ValueError(f"Unknown constant type {t} at offset {pos - 1}")
