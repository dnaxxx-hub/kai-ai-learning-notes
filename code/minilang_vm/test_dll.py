"""Quick DLL smoke test."""
import ctypes
import os

dll_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'minilang_vm.dll'))
print(f"DLL path: {dll_path}")
print(f"Exists: {os.path.exists(dll_path)}")

dll = ctypes.CDLL(dll_path)
print("DLL loaded!")

# Test run_vm with a simple program: PUSH_CONST 42, PRINT, HALT
# Instructions: [(1, 0), (19, 0), (0, 0)] where 1=PUSH_CONST, 19=PRINT, 0=HALT
# Constant 0: int value 42

n_instr = 3
bc = (ctypes.c_int32 * (n_instr * 2))()
bc[0] = 1   # PUSH_CONST
bc[1] = 0   # constant index 0
bc[2] = 19  # PRINT
bc[3] = 0
bc[4] = 0   # HALT
bc[5] = 0

n_consts = 1
const_types = (ctypes.c_int32 * n_consts)()
const_types[0] = 0  # int
const_data = (ctypes.c_int64 * n_consts)()
const_data[0] = 42
const_str_offsets = (ctypes.c_int32 * n_consts)()
const_str_offsets[0] = -1
const_strings = b''

LINE_SIZE = 256
MAX_LINES = 4096
out_buf = ctypes.create_string_buffer(MAX_LINES * LINE_SIZE)
out_count = ctypes.c_int32(MAX_LINES)

fn = dll.run_vm
fn.argtypes = [
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.POINTER(ctypes.c_int32),
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_int32),
    ctypes.c_int32,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_int32),
]

print("Calling run_vm...")
fn(bc, ctypes.c_int32(n_instr),
   const_types, const_data,
   const_strings,
   const_str_offsets,
   ctypes.c_int32(n_consts),
   out_buf,
   ctypes.byref(out_count))

n = out_count.value
print(f"Output lines: {n}")
for i in range(n):
    raw = out_buf[i * LINE_SIZE : i * LINE_SIZE + LINE_SIZE]
    null_pos = raw.find(b'\x00')
    if null_pos >= 0:
        raw = raw[:null_pos]
    print(f"  [{i}] {raw.decode('utf-8')}")
