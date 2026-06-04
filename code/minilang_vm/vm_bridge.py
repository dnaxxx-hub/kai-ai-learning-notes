"""
ctypes bridge to MiniLang C VM DLL.

Provides run_bytecode(bytecodes, constants, symbols) that
returns list of output strings.
"""

import ctypes
import os

# Load the DLL
_dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'minilang_vm.dll')
_vm = ctypes.CDLL(_dll_path)

# Define the C function signature
# void run_vm(bytecode, bc_len, const_types, const_data,
#             const_strings, const_str_offsets, num_consts,
#             out_buf, out_count)
_run_vm = _vm.run_vm
_run_vm.argtypes = [
    ctypes.POINTER(ctypes.c_int32),    # bytecode
    ctypes.c_int32,                     # bc_len
    ctypes.POINTER(ctypes.c_int32),    # const_types
    ctypes.POINTER(ctypes.c_int64),    # const_data
    ctypes.c_char_p,                   # const_strings
    ctypes.POINTER(ctypes.c_int32),    # const_str_offsets
    ctypes.c_int32,                    # num_consts
    ctypes.c_char_p,                   # out_buf (flat)
    ctypes.POINTER(ctypes.c_int32),    # out_count
]

MAX_OUTPUT_LINES = 4096
LINE_SIZE = 256


def run_bytecode(instructions, constants, symbols=None):
    """
    Execute MiniLang bytecode via the C VM.

    Args:
        instructions: list of (op, arg) tuples
        constants: list of (type, value) tuples
                   type 0 = int, type 1 = string
        symbols: list of symbol names (optional, currently unused in VM)

    Returns:
        list of output strings
    """
    # Build flat bytecode array: [op1, arg1, op2, arg2, ...]
    n_instr = len(instructions)
    bc_array = (ctypes.c_int32 * (n_instr * 2))()
    for i, (op, arg) in enumerate(instructions):
        bc_array[i * 2] = op
        bc_array[i * 2 + 1] = arg

    # Build constants arrays
    n_consts = len(constants)
    const_types = (ctypes.c_int32 * n_consts)()
    const_data = (ctypes.c_int64 * n_consts)()

    # Build string pool
    string_pool_parts = []
    current_offset = 0
    const_str_offsets = (ctypes.c_int32 * n_consts)()
    for i, (typ, val) in enumerate(constants):
        const_types[i] = typ
        if typ == 0:  # int
            const_data[i] = val
            const_str_offsets[i] = -1
        else:  # string
            const_data[i] = 0
            encoded = str(val).encode('utf-8') + b'\x00'
            const_str_offsets[i] = current_offset
            string_pool_parts.append(encoded)
            current_offset += len(encoded)

    const_strings = b''.join(string_pool_parts)

    # Output buffer (flat)
    out_buf_size = MAX_OUTPUT_LINES * LINE_SIZE
    out_buf = ctypes.create_string_buffer(out_buf_size)
    out_count = ctypes.c_int32(MAX_OUTPUT_LINES)

    # Call C function
    _run_vm(
        bc_array, ctypes.c_int32(n_instr),
        const_types, const_data,
        const_strings if const_strings else b'',
        const_str_offsets,
        ctypes.c_int32(n_consts),
        out_buf,
        ctypes.byref(out_count),
    )

    # Convert output
    n = out_count.value
    results = []
    for i in range(n):
        offset = i * LINE_SIZE
        raw = out_buf[offset:offset + LINE_SIZE]
        # Extract null-terminated string
        null_pos = raw.find(b'\x00')
        if null_pos >= 0:
            raw = raw[:null_pos]
        results.append(raw.decode('utf-8', errors='replace'))

    return results
