#!/usr/bin/env python3
"""
OS 内存管理深度演示

内容：
1. mmap 共享内存示例 (Windows VirtualAlloc + Python mmap)
2. 内存访问模式可视化（按页 vs 按行对比速度）
3. 页面置换算法对比（FIFO vs LRU vs Clock）
4. 4 级页表遍历模拟
5. 伙伴系统模拟
6. 内存碎片分析
"""

import os
import sys
import time
import mmap
import struct
import random
from collections import OrderedDict

# ──────────────────────────────────────────
# Part 1: mmap 共享内存示例
# ──────────────────────────────────────────

def demo_mmap_shared_memory():
    print("=" * 70)
    print("Part 1: mmap 共享内存示例")
    print("=" * 70)

    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
    kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel32.VirtualFree.restype = ctypes.c_bool
    kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
    kernel32.VirtualProtect.restype = ctypes.c_bool
    kernel32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]

    PAGE_READWRITE = 0x04
    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    MEM_RELEASE = 0x8000

    size = 4096
    addr_val = kernel32.VirtualAlloc(None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not addr_val:
        print("  VirtualAlloc failed")
        return
    print(f"  Allocated {size} bytes at {addr_val}")

    # Write data using ctypes
    ctypes.memmove(addr_val, b"Hello from Python mmap demo!", 28)
    buf = (ctypes.c_char * size).from_address(addr_val)
    print(f"  Read back: {buf[:28]}")

    # Change page protection (mprotect analog)
    old_protect = ctypes.c_uint32(0)
    ret = kernel32.VirtualProtect(addr_val, size, PAGE_READWRITE, ctypes.byref(old_protect))
    if ret:
        print(f"  Page protection changed successfully")
    else:
        print(f"  VirtualProtect failed: {ctypes.GetLastError()}")

    # Free
    kernel32.VirtualFree(addr_val, 0, MEM_RELEASE)
    print("  Freed memory\n")

    # --- 1.2 Python mmap 模块 ---
    print("[1.2] Python mmap 模块 (匿名映射)")
    mm = mmap.mmap(-1, 4096, access=mmap.ACCESS_WRITE)
    mm.write(b"mmap test data")
    mm.seek(0)
    print(f"  Read: {mm.read(20)}")
    mm.close()
    print("  mmap closed\n")

    # --- 1.3 系统参数 ---
    print("[1.3] 系统参数")
    kernel32.GetSystemInfo.restype = None
    kernel32.GetSystemInfo.argtypes = [ctypes.c_void_p]
    system_info = ctypes.create_string_buffer(48)
    kernel32.GetSystemInfo(system_info)
    page_size = struct.unpack_from("I", system_info, 8)[0]
    print(f"  System page size: {page_size} bytes ({page_size//1024} KB)")

    allocation_granularity = struct.unpack_from("I", system_info, 20)[0]
    print(f"  Allocation granularity: {allocation_granularity} bytes")
    print()


# ──────────────────────────────────────────
# Part 2: 内存访问模式可视化
# ──────────────────────────────────────────

def demo_memory_access_patterns():
    print("=" * 70)
    print("Part 2: 内存访问模式速度对比")
    print("=" * 70)

    N = 2048
    total_size = N * N * 4
    print(f"\nMatrix size: {N}x{N} (simulated contiguous memory)")
    print(f"Total elements: {N*N:,}")
    print(f"Total memory: ~{total_size // (1024*1024)} MB (as C int array)\n")

    import ctypes
    IntArray = ctypes.c_int * (N * N)
    arr = IntArray()

    for i in range(N * N):
        arr[i] = i % 1000

    print("Access patterns (each repeated 5 times for average):")
    print("-" * 60)

    patterns = []

    # --- 行优先 (Stride = 1) ---
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        s = 0
        for i in range(N):
            row_start = i * N
            for j in range(N):
                s += arr[row_start + j]
        t1 = time.perf_counter()
        times.append(t1 - t0)
    row_time = sum(times) / len(times)
    patterns.append(("Row-major (stride=1)", row_time))
    print(f"  Row-major  (sequential): {row_time*1000:.1f} ms")

    # --- 列优先 (Stride = N) ---
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        s = 0
        for j in range(N):
            for i in range(N):
                s += arr[i * N + j]
        t1 = time.perf_counter()
        times.append(t1 - t0)
    col_time = sum(times) / len(times)
    patterns.append(("Column-major (stride=N)", col_time))
    print(f"  Column-major (stride=N): {col_time*1000:.1f} ms")

    # --- 伪随机访问 ---
    indices = list(range(N * N))
    random.shuffle(indices)
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        s = 0
        for idx in indices:
            s += arr[idx]
        t1 = time.perf_counter()
        times.append(t1 - t0)
    rand_time = sum(times) / len(times)
    patterns.append(("Random access", rand_time))
    print(f"  Random access:          {rand_time*1000:.1f} ms")

    print()
    print("Analysis:")
    print(f"  Sequential is {col_time/row_time:.1f}x faster than column-major")
    print(f"  Sequential is {rand_time/row_time:.1f}x faster than random")
    print()
    print("  Why? CPU 缓存 (cache line = 64 bytes):")
    print("  - Row-major: 访问 arr[i][j] 时，相邻元素在同一 cache line")
    print("  - Column-major: 每次跳过整行，每次访问都 miss cache")
    print("  - Random: 接近 100% cache miss, 等效于内存延迟")
    print()


# ──────────────────────────────────────────
# Part 3: 页面置换算法对比
# ──────────────────────────────────────────

class PageReplacementSim:
    def __init__(self, num_frames, page_sequence):
        self.num_frames = num_frames
        self.pages = page_sequence
        self.page_faults = {}
        self.history = {}

    def run_fifo(self):
        frames = []
        faults = 0
        hist = []
        ptr = 0
        for page in self.pages:
            if page not in frames:
                faults += 1
                if len(frames) < self.num_frames:
                    frames.append(page)
                else:
                    frames[ptr] = page
                    ptr = (ptr + 1) % self.num_frames
            hist.append((page, list(frames)))
        self.page_faults["FIFO"] = faults
        self.history["FIFO"] = hist
        return faults

    def run_lru(self):
        frames = []
        faults = 0
        hist = []
        last_used = {}
        for i, page in enumerate(self.pages):
            last_used[page] = i
            if page not in frames:
                faults += 1
                if len(frames) < self.num_frames:
                    frames.append(page)
                else:
                    lru_page = min(frames, key=lambda p: last_used[p])
                    idx = frames.index(lru_page)
                    frames[idx] = page
            hist.append((page, list(frames)))
        self.page_faults["LRU"] = faults
        self.history["LRU"] = hist
        return faults

    def run_clock(self):
        frames = []
        ref_bits = []
        faults = 0
        hand = 0
        hist = []
        for page in self.pages:
            if page in frames:
                idx = frames.index(page)
                ref_bits[idx] = 1
                hist.append((page, list(frames)))
                continue
            faults += 1
            if len(frames) < self.num_frames:
                frames.append(page)
                ref_bits.append(1)
            else:
                while True:
                    if ref_bits[hand] == 0:
                        frames[hand] = page
                        ref_bits[hand] = 1
                        hand = (hand + 1) % self.num_frames
                        break
                    else:
                        ref_bits[hand] = 0
                        hand = (hand + 1) % self.num_frames
            hist.append((page, list(frames)))
        self.page_faults["Clock"] = faults
        self.history["Clock"] = hist
        return faults

    def run_optimal(self):
        frames = []
        faults = 0
        hist = []
        for i, page in enumerate(self.pages):
            if page not in frames:
                faults += 1
                if len(frames) < self.num_frames:
                    frames.append(page)
                else:
                    future_uses = []
                    for f in frames:
                        try:
                            idx = self.pages[i + 1:].index(f)
                            future_uses.append((f, idx))
                        except ValueError:
                            future_uses.append((f, float('inf')))
                    victim = max(future_uses, key=lambda x: x[1])[0]
                    idx = frames.index(victim)
                    frames[idx] = page
            hist.append((page, list(frames)))
        self.page_faults["OPT"] = faults
        self.history["OPT"] = hist
        return faults

    def run_all(self):
        self.run_fifo()
        self.run_lru()
        self.run_clock()
        self.run_optimal()
        return self.page_faults

    def show_large_access_hist(self):
        for alg in ["FIFO", "LRU", "Clock", "OPT"]:
            if alg not in self.history:
                continue
            print(f"\n  [{alg}] Access sequence (first 40 references):")
            hist = self.history[alg][:40]
            line = "  Ref: "
            for i, (page, _) in enumerate(hist):
                line += f"{page:3d} "
            print(line)
            line = "  Flt: "
            prev_set = set()
            for i, (page, frames) in enumerate(hist):
                curr_set = set(frames)
                if i == 0 or page not in prev_set:
                    line += "  F "
                else:
                    line += "  . "
                prev_set = curr_set
            print(line)
            for f_idx in range(self.num_frames):
                line = f"  F{f_idx}: "
                for _, frames in hist:
                    if f_idx < len(frames):
                        line += f"{frames[f_idx]:3d} "
                    else:
                        line += "  . "
                print(line)
            break


def demo_page_replacement():
    print("=" * 70)
    print("Part 3: 页面置换算法对比")
    print("=" * 70)

    # 场景 A: 顺序循环
    print("\n[Scenario A] Sequential loop (pages 0-9 repeated 4 times)")
    seq = (list(range(10)) * 4)
    sim = PageReplacementSim(4, seq)
    results = sim.run_all()
    for alg, faults in sorted(results.items()):
        print(f"  {alg:8s}: {faults:3d} page faults  (rate: {faults/len(seq)*100:.0f}%)")

    # 场景 B: 局部性
    print("\n[Scenario B] Locality reference pattern")
    random.seed(42)
    locality = []
    for _ in range(10):
        base = random.randint(0, 40)
        locality.extend(random.choices(
            [base, base + 1, base + 2, base + 3, base + random.randint(-5, 5)],
            weights=[50, 25, 15, 10, 0],
            k=20
        ))
    sim = PageReplacementSim(5, locality)
    results = sim.run_all()
    for alg, faults in sorted(results.items()):
        print(f"  {alg:8s}: {faults:3d} page faults  (rate: {faults/len(locality)*100:.0f}%)")

    # 场景 C: 完全随机
    print("\n[Scenario C] Random access (no locality)")
    random.seed(1)
    rand_seq = [random.randint(0, 99) for _ in range(200)]
    sim = PageReplacementSim(10, rand_seq)
    results = sim.run_all()
    for alg, faults in sorted(results.items()):
        print(f"  {alg:8s}: {faults:3d} page faults  (rate: {faults/len(rand_seq)*100:.0f}%)")

    # 场景 D: Belady 异常
    print("\n[Scenario D] Belady's Anomaly (FIFO)")
    anomaly_seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    for frames in [3, 4]:
        sim = PageReplacementSim(frames, anomaly_seq)
        f_fifo = sim.run_fifo()
        f_lru = sim.run_lru()
        anomaly = " *** BELADY ANOMALY: more frames, more faults!" if frames == 4 and f_fifo >= f_lru else ""
        print(f"  FIFO with {frames} frames: {f_fifo} faults (LRU: {f_lru}){anomaly}")

    # 场景 E: 详细 LRU 模拟
    print("\n[Scenario E] LRU page table walk (detail)")
    tiny_seq = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    sim = PageReplacementSim(4, tiny_seq)
    sim.run_lru()
    sim.run_optimal()
    print("  Reference sequence:", tiny_seq)
    for i, (page, frames) in enumerate(sim.history["LRU"]):
        fault_mark = "F" if (i == 0 or page not in sim.history["LRU"][i-1][1]) else "."
        print(f"    [{i:2d}] ref={page:2d}  frames={frames}  [{fault_mark}]")
    print(f"  LRU faults: {sim.page_faults['LRU']}, OPT faults: {sim.page_faults['OPT']}")

    # 汇总
    print("\n[Summary: Algorithm Comparison]")
    print(f"{'Algorithm':<10} {'Complexity':<15} {'Implementation':<30}")
    print("-" * 55)
    print(f"{'FIFO':<10} {'O(N)':<15} {'Queue, O(1) per ref':<30}")
    print(f"{'LRU':<10} {'O(N)':<15} {'Timestamp/stack':<30}")
    print(f"{'Clock':<10} {'O(N)':<15} {'Ref bit + hand':<30}")
    print(f"{'OPT':<10} {'O(N)':<15} {'Future knowledge':<30}")
    print()
    print("  Linux kernel: Active/Inactive list (LRU approximation)")
    print("  kswapd scans pages, moves between lists")
    print("  Decision based on referenced + dirty bits")
    print()


# ──────────────────────────────────────────
# Part 4: 4 级页表遍历
# ──────────────────────────────────────────

def demo_page_table_walk():
    print("=" * 70)
    print("Part 4: 4-Level Page Table Walk (x86-64)")
    print("=" * 70)

    PAGE_BITS = 12
    PT_INDEX_BITS = 9
    PT_ENTRIES = 1 << PT_INDEX_BITS

    print(f"\nConfiguration:")
    print(f"  Page size:     {1 << PAGE_BITS} bytes ({1 << PAGE_BITS >> 10} KB)")
    print(f"  PT level bits: {PT_INDEX_BITS}")
    print(f"  PT entries:    {PT_ENTRIES}")
    print(f"  Virtual addr:  {PAGE_BITS + 4 * PT_INDEX_BITS} bits")
    print()

    test_addrs = [
        0x0000000000400000,
        0x00007f0000000000,
        0x00007ffffffde000,
    ]

    print(f"{'Virtual Address':<22} {'PML4':<8} {'PDPT':<8} {'PD':<8} {'PT':<8} {'Offset':<8}")
    print("-" * 62)

    for vaddr in test_addrs:
        offset = vaddr & ((1 << PAGE_BITS) - 1)
        pt_idx = (vaddr >> PAGE_BITS) & (PT_ENTRIES - 1)
        pd_idx = (vaddr >> (PAGE_BITS + PT_INDEX_BITS)) & (PT_ENTRIES - 1)
        pdpt_idx = (vaddr >> (PAGE_BITS + 2 * PT_INDEX_BITS)) & (PT_ENTRIES - 1)
        pml4_idx = (vaddr >> (PAGE_BITS + 3 * PT_INDEX_BITS)) & (PT_ENTRIES - 1)

        print(f"0x{vaddr:016x}  0x{pml4_idx:03x}  0x{pdpt_idx:03x}  0x{pd_idx:03x}  0x{pt_idx:03x}  0x{offset:03x}")

    print()
    print("Memory needed for page tables:")
    print(f"  PML4:   1 table x 4 KB = 4 KB (per process)")
    print(f"  PDPT:   up to 512 tables x 4 KB = 2 MB")
    print(f"  PD:     up to 256K tables x 4 KB = 1 GB")
    print(f"  PT:     up to 128M tables x 4 KB = 512 GB")
    print()
    print("  With sparse allocation (real process):")
    print("  ~1 PML4 + ~1 PDPT + ~1 PD + ~N PT = few MB typically")
    print()


# ──────────────────────────────────────────
# Part 5: 伙伴系统模拟
# ──────────────────────────────────────────

class BuddySystem:
    def __init__(self, total_size=1024, min_size=32):
        self.total = total_size
        self.min_size = min_size
        self.max_order = self._log2(total_size // min_size)
        self.free_lists = [[] for _ in range(self.max_order + 1)]
        self.free_lists[self.max_order].append({
            'start': 0, 'size': total_size, 'order': self.max_order
        })
        self.allocations = {}

    def _log2(self, x):
        return x.bit_length() - 1

    def alloc(self, size):
        order = self._log2((size + self.min_size - 1) // self.min_size)
        if order > self.max_order:
            return None
        o = order
        while o <= self.max_order and not self.free_lists[o]:
            o += 1
        if o > self.max_order:
            return None
        block = self.free_lists[o].pop(0)
        while o > order:
            o -= 1
            half_size = block['size'] // 2
            buddy = {
                'start': block['start'] + half_size,
                'size': half_size,
                'order': o
            }
            block['size'] = half_size
            block['order'] = o
            self.free_lists[o].append(buddy)
        self.allocations[block['start']] = block
        return block['start']

    def free(self, start):
        if start not in self.allocations:
            raise ValueError(f"Invalid address {start}")
        block = self.allocations.pop(start)
        self._coalesce(block)

    def _coalesce(self, block):
        order = block['order']
        buddy_start = block['start'] ^ block['size']
        buddy_idx = None
        for i, b in enumerate(self.free_lists[order]):
            if b['start'] == buddy_start and b['size'] == block['size']:
                buddy_idx = i
                break
        if buddy_idx is not None and order < self.max_order:
            buddy = self.free_lists[order].pop(buddy_idx)
            merged = {
                'start': min(block['start'], buddy['start']),
                'size': block['size'] * 2,
                'order': order + 1
            }
            self._coalesce(merged)
        else:
            self.free_lists[order].append(block)

    def dump(self):
        print(f"  Buddy state (total={self.total}, min={self.min_size}):")
        for o in range(self.max_order + 1):
            cnt = len(self.free_lists[o])
            if cnt > 0:
                block_size = self.min_size << o
                print(f"    order {o:2d} ({block_size:4d}): {cnt} blocks")

    def total_free(self):
        total = 0
        for o in range(self.max_order + 1):
            for b in self.free_lists[o]:
                total += b['size']
        return total


def demo_buddy_system():
    print("=" * 70)
    print("Part 5: Buddy System 模拟")
    print("=" * 70)

    bs = BuddySystem(1024, 32)
    print("\nInitial state:")
    bs.dump()

    print("\nAllocation trace:")
    a1 = bs.alloc(64)
    print(f"  alloc(64)  -> block at {a1}")
    bs.dump()

    a2 = bs.alloc(128)
    print(f"  alloc(128) -> block at {a2}")
    bs.dump()

    a3 = bs.alloc(32)
    print(f"  alloc(32)  -> block at {a3}")
    bs.dump()

    print(f"\nFree block at {a3}:")
    bs.free(a3)
    bs.dump()

    print(f"\nFree block at {a1} (should coalesce with buddy):")
    bs.free(a1)
    bs.dump()

    print(f"\nFree block at {a2} (should merge fully):")
    bs.free(a2)
    bs.dump()
    print()


# ──────────────────────────────────────────
# Part 6: 碎片分析
# ──────────────────────────────────────────

def demo_fragmentation():
    print("=" * 70)
    print("Part 6: 内存碎片分析")
    print("=" * 70)

    print("\n[6.1] External Fragmentation")
    print("  空闲内存总和很大，但最大连续块很小")
    print()

    bs = BuddySystem(1024, 32)
    a = bs.alloc(128)
    b = bs.alloc(128)
    c = bs.alloc(128)
    bs.free(a)
    bs.free(c)

    print("  Scenario: allocated B in middle, freed A and C:")
    bs.dump()
    free_total = bs.total_free()
    print(f"  Free total: {free_total} bytes")
    d = bs.alloc(256)
    print(f"  alloc(256) -> {d if d else 'FAILED (external fragmentation)'}")
    if not d:
        print("  This is EXTERNAL FRAGMENTATION: 256 bytes free but not contiguous")

    print("\n[6.2] Internal Fragmentation")
    print("  分配块大于请求大小，块内存在浪费")
    print()
    bs2 = BuddySystem(1024, 32)
    x = bs2.alloc(33)
    print(f"  Request: 33 bytes -> allocated block at {x}")
    bs2.dump()
    print(f"  Used: 33 bytes, allocated: 64 bytes")
    waste = 64 - 33
    print(f"  Internal fragmentation: {waste} bytes wasted ({waste/64*100:.0f}%)")

    print("\n[6.3] ptmalloc internal fragmentation (common):")
    sizes_data = [(1, 32), (24, 32), (25, 48), (100, 112), (1000, 1008)]
    for req, actual in sizes_data:
        waste = actual - req
        print(f"  malloc({req:5d}) -> actual {actual:5d}, waste {waste:3d} ({waste/actual*100:.0f}%)")
    print()


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("#" * 60)
    print("#  OS Memory Management Deep Dive")
    print("#  Python Demonstration")
    print("#" * 60)
    print()
    print(f"Platform: {sys.platform}")
    print(f"Python:   {sys.version.split()[0]}")
    print()

    demo_mmap_shared_memory()
    demo_page_table_walk()
    demo_memory_access_patterns()
    demo_page_replacement()
    demo_buddy_system()
    demo_fragmentation()

    print("=" * 70)
    print("All demonstrations completed.")
    print("=" * 70)
