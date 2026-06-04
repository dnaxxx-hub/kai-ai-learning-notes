#!/usr/bin/env python3
"""fs_demo.py — 文件系统核心机制 Python 演示
模块:
1. inode 索引模拟（直接/间接块寻址）
2. 页缓存 LRU 模拟 + 读写命中率分析
3. 写入模式对比（同步/延迟/写时复制）
4. 碎片分析（空闲块位图碎片率）
5. 日志恢复模拟（redo/undo）
"""

import random
import math
import time

# ============================================================
# 1. inode 索引模拟
# ============================================================
class InodeSim:
    """模拟 EXT4-style inode 索引
    
    数据结构:
    - 12 个直接块指针 (0-11)
    - 1 个一级间接块指针 (12) — 指向一个包含块号的 block
    - 1 个二级间接块指针 (13) — 指向包含一级间接块的 block
    - 1 个三级间接块指针 (14)
    """
    
    BLOCK_SIZE = 4096          # 4KB
    POINTERS_PER_BLOCK = 1024  # 每个 block 可存 1024 个指针 (4字节每个)
    
    def __init__(self):
        self.direct = [None] * 12
        self.indirect1 = None   # 一级间接 [block_no, ...]
        self.indirect2 = None   # 二级间接 [[block_no, ...], ...]
        self.indirect3 = None   # 三级间接
        self.allocated = set()
    
    def _alloc_block(self):
        """分配一个空闲块"""
        b = random.randint(1000, 100000)
        while b in self.allocated:
            b = random.randint(1000, 100000)
        self.allocated.add(b)
        return b
    
    def write_block(self, offset, data_block=None):
        """在逻辑块 offset 处写入数据块
        
        返回: (block_no, index_level)
        - index_level: 0=直接, 1=一级间接, 2=二级间接, 3=三级间接
        """
        if offset < 12:
            n = self._alloc_block()
            self.direct[offset] = n
            return n, 0
        
        off = offset - 12
        if off < self.POINTERS_PER_BLOCK:
            # 一级间接
            if self.indirect1 is None:
                self.indirect1 = []
            while len(self.indirect1) <= off:
                self.indirect1.append(None)
            if self.indirect1[off] is None:
                self.indirect1[off] = self._alloc_block()
            return self.indirect1[off], 1
        
        off -= self.POINTERS_PER_BLOCK
        i2_bucket = off // self.POINTERS_PER_BLOCK
        i2_slot = off % self.POINTERS_PER_BLOCK
        
        if self.indirect2 is None:
            self.indirect2 = []
        while len(self.indirect2) <= i2_bucket:
            self.indirect2.append(None)
        if self.indirect2[i2_bucket] is None:
            self.indirect2[i2_bucket] = []
        bucket = self.indirect2[i2_bucket]
        while len(bucket) <= i2_slot:
            bucket.append(None)
        if bucket[i2_slot] is None:
            bucket[i2_slot] = self._alloc_block()
        return bucket[i2_slot], 2
    
    def max_file_size(self):
        """理论最大文件大小 (字节)"""
        direct = 12
        l1 = self.POINTERS_PER_BLOCK
        l2 = self.POINTERS_PER_BLOCK ** 2
        l3 = self.POINTERS_PER_BLOCK ** 3
        total_blocks = direct + l1 + l2 + l3
        return total_blocks * self.BLOCK_SIZE
    
    def report(self):
        print(f"  inode 索引模拟")
        print(f"  直接块: {sum(1 for x in self.direct if x is not None)}/12")
        l1 = len(self.indirect1) if self.indirect1 else 0
        print(f"  一级间接: {l1}/{self.POINTERS_PER_BLOCK} 指针")
        l2_used = 0
        if self.indirect2:
            for bucket in self.indirect2:
                if bucket:
                    l2_used += len(bucket)
        print(f"  二级间接: {l2_used}/{self.POINTERS_PER_BLOCK**2} 指针")
        print(f"  最大文件: {self.max_file_size()/1024/1024/1024:.1f} GiB")
        print()


# ============================================================
# 2. 页缓存 LRU 模拟
# ============================================================
class PageCacheLRU:
    """页缓存模拟 — LRU 替换策略
    
    模拟读/写操作对页缓存的命中/未命中统计
    """
    
    def __init__(self, capacity=64):
        self.capacity = capacity
        self.cache = {}        # page_id -> access_time
        self.time = 0
        self.hits = 0
        self.misses = 0
        self.read_hits = 0
        self.write_hits = 0
    
    def access(self, page_id, is_write=False):
        self.time += 1
        if page_id in self.cache:
            self.hits += 1
            if is_write:
                self.write_hits += 1
            else:
                self.read_hits += 1
            self.cache[page_id] = self.time
        else:
            self.misses += 1
            if len(self.cache) >= self.capacity:
                lru_page = min(self.cache, key=self.cache.get)
                del self.cache[lru_page]
            self.cache[page_id] = self.time
    
    def hit_rate(self):
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0
    
    def report(self):
        print(f"  页缓存 LRU (容量={self.capacity})")
        print(f"  命中: {self.hits}, 未命中: {self.misses}")
        print(f"  命中率: {self.hit_rate():.1f}%")
        print(f"  读命中: {self.read_hits}, 写命中: {self.write_hits}")
        print()


def simulate_page_cache():
    """模拟不同访问模式的页缓存表现"""
    print("=" * 60)
    print("2. 页缓存 LRU 模拟")
    print("=" * 60)
    
    # 场景 A: 顺序访问 (好的局部性)
    cache_A = PageCacheLRU(64)
    for i in range(200):
        # 顺序访问 0..63 范围，重复 3 次
        page = (i * 17) % 64
        cache_A.access(page, is_write=(i % 5 == 0))
    print("[场景 A] 顺序访问 (好的局部性):")
    cache_A.report()
    
    # 场景 B: 随机访问 (差的局部性)
    cache_B = PageCacheLRU(64)
    for i in range(200):
        page = random.randint(0, 1023)
        cache_B.access(page, is_write=False)
    print("[场景 B] 随机访问 (差的局部性):")
    cache_B.report()
    
    # 场景 C: 工作集大小 > 缓存
    cache_C = PageCacheLRU(32)
    for i in range(200):
        page = (i * 7) % 128
        cache_C.access(page, is_write=False)
    print("[场景 C] 工作集 > 缓存:")
    cache_C.report()
    
    # 场景 D: 混合读写
    cache_D = PageCacheLRU(64)
    for i in range(1000):
        if random.random() < 0.2:  # 20% 写
            cache_D.access(random.randint(0, 127), is_write=True)
        else:
            cache_D.access(random.randint(0, 127), is_write=False)
    print("[场景 D] 混合读写 (工作集128, 20%写):")
    cache_D.report()


# ============================================================
# 3. 写入模式对比
# ============================================================
class WritePatternSim:
    """对比三种写入模式
    
    1. 同步写入 (synchronous) — 每次 write() 都等待磁盘确认
    2. 延迟写入 (delayed / writeback) — 积累后批量写入
    3. 写时复制 (COW, copy-on-write) — Btrfs风格
    """
    
    def simulate(self, n_writes=200, avg_size=8):
        """模拟 n_writes 次写入"""
        
        # 同步写入
        sync_time = n_writes * (5 + random.gauss(0, 1))
        if sync_time < 0:
            sync_time = n_writes * 5
        sync_wasted = 0  # 无浪费空间
        
        # 延迟写入
        batch_size = 16
        batches = math.ceil(n_writes / batch_size)
        delay_time = batches * (5 + avg_size * 0.1)
        delay_wasted = 0  # 小量浪费
        
        # 写时复制 (COW)
        cow_time = 0
        cow_wasted = 0
        for i in range(n_writes):
            # COW 每次写入需要复制原始块
            cow_time += 5 + random.uniform(1, 3)  # 读原块+写新块
            if random.random() < 0.3:  # 30%概率触发实际复制
                cow_wasted += avg_size  # 原块变为垃圾
                cow_time += 2
        
        print(f"  写入次数: {n_writes}, 平均大小: {avg_size}KB")
        print(f"  {'模式':<12} {'总时间(ms)':<14} {'空间浪费(KB)':<14} {'特点'}")
        print(f"  {'-'*56}")
        print(f"  {'同步写入':<12} {sync_time:<14.1f} {sync_wasted:<14} {'一致性强,性能差'}")
        print(f"  {'延迟写入':<12} {delay_time:<14.1f} {delay_wasted:<14} {'性能好,宕机丢数据'}")
        print(f"  {'写时复制':<12} {cow_time:<14.1f} {cow_wasted:<14} {'快照友好,碎片多'}")
        
        # 加入 pwrite 模拟 (定位写入)
        pwrite_time = n_writes * 2  # 无需寻道
        print(f"  {'定位写入':<12} {pwrite_time:<14.1f} {'N/A':<14} {'随机IO友好,无同步'}")
        print()


def simulate_write_patterns():
    print("=" * 60)
    print("3. 写入模式对比")
    print("=" * 60)
    sim = WritePatternSim()
    sim.simulate(n_writes=200, avg_size=8)


# ============================================================
# 4. 碎片分析
# ============================================================
class FragmentationAnalyzer:
    """文件系统碎片分析
    
    模拟空闲块位图，计算外部碎片率
    """
    
    def __init__(self, total_blocks=1024):
        self.total = total_blocks
        self.bitmap = [0] * total_blocks  # 0=空闲, 1=已用
    
    def alloc_contiguous(self, n, align=None):
        """分配 n 个连续块"""
        for start in range(self.total - n + 1):
            if align and start % align != 0:
                continue
            if all(self.bitmap[start:start+n] == [0]*n if isinstance(self.bitmap, list) else True for b in self.bitmap[start:start+n]):
                for i in range(start, start+n):
                    self.bitmap[i] = 1
                return start
        return -1
    
    def alloc_random(self, n):
        """随机分配 n 个离散块"""
        count = 0
        while count < n:
            pos = random.randint(0, self.total-1)
            if self.bitmap[pos] == 0:
                self.bitmap[pos] = 1
                count += 1
    
    def free_range(self, start, n):
        """释放连续块"""
        for i in range(start, min(start+n, self.total)):
            self.bitmap[i] = 0
    
    def fragmentation_rate(self):
        """计算外部碎片率
        
        定义: 1 - (最大连续空闲块 / 总空闲块数)
        越接近1表示碎片越严重
        """
        free_blocks = sum(1 for b in self.bitmap if b == 0)
        if free_blocks == 0:
            return 0
        
        max_run = 0
        run = 0
        for b in self.bitmap:
            if b == 0:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        
        return 1 - (max_run / free_blocks)
    
    def report(self, label):
        used = sum(self.bitmap)
        free = self.total - used
        frag = self.fragmentation_rate()
        max_run = 0
        run = 0
        for b in self.bitmap:
            if b == 0: run += 1; max_run = max(max_run, run)
            else: run = 0
        
        print(f"  {label}:")
        print(f"   总块: {self.total}, 已用: {used}, 空闲: {free}")
        print(f"   最大连续空闲: {max_run}, 碎片率: {frag:.3f}")
        print(f"   评估: ", end="")
        if frag < 0.1: print("✅ 低碎片")
        elif frag < 0.3: print("⚠️ 中度碎片")
        elif frag < 0.5: print("❌ 严重碎片")
        else: print("💀 极度碎片 (需要碎片整理)")
        print()


def simulate_fragmentation():
    print("=" * 60)
    print("4. 碎片分析")
    print("=" * 60)
    
    random.seed(42)
    
    # 场景 A: 顺序分配后释放 (低碎片)
    fa = FragmentationAnalyzer(200)
    for _ in range(10):
        fa.alloc_contiguous(10)
    # 释放交替块
    for i in range(0, 100, 20):
        fa.free_range(i, 5)
    fa.report("[A] 顺序分配+交替释放")
    
    # 场景 B: 随机分配 (高碎片)
    fb = FragmentationAnalyzer(200)
    for _ in range(20):
        n = random.randint(2, 5)
        if sum(fb.bitmap) < 180:
            fb.alloc_random(n)
    fb.report("[B] 连续随机分配")
    
    # 场景 C: 长时间运行 (碎片累积)
    fc = FragmentationAnalyzer(1024)
    for _ in range(80):
        n = random.randint(1, 15)
        start = fc.alloc_contiguous(n)
        if start >= 0 and random.random() < 0.4 and n > 3:
            fc.free_range(start + n//2, n//2)
    fc.report("[C] 长时间运行")
    
    # EXT4 碎片整理模拟
    print("  [EXT4 碎片整理模拟]")
    # 在线整理: 将离散块移动为连续
    frag_before = fc.fragmentation_rate()
    # 简单整理: 压缩空闲块到尾部
    blocks = list(fc.bitmap)
    used_blocks = [i for i, b in enumerate(blocks) if b == 1]
    for i, idx in enumerate(used_blocks):
        fc.bitmap[i] = 1
    for i in range(len(used_blocks), fc.total):
        fc.bitmap[i] = 0
    frag_after = fc.fragmentation_rate()
    print(f"   整理前碎片率: {frag_before:.3f}")
    print(f"   整理后碎片率: {frag_after:.3f}")
    print(f"   改善: {(frag_before - frag_after) * 100:.1f}%")
    print()


# ============================================================
# 5. 日志恢复模拟
# ============================================================
class JournalSim:
    """文件系统日志恢复模拟
    
    模拟 redo 日志 (EXT4 JBD2风格):
    1. 事务开始 → 写入日志 → 日志提交 → check point
    2. crash 恢复: 扫描日志 → redo 未检查点事务
    
    模拟 undo 日志 (数据库风格):
    1. 写数据前先写 undo 日志
    2. crash 恢复: 扫描日志 → undo 未完成事务
    """
    
    def __init__(self):
        self.journal = []
        self.active_txns = {}  # txn_id -> [operations]
        self.committed = set()
        self.checkpointed = set()
        self.current_txn = 0
    
    def begin_txn(self):
        self.current_txn += 1
        self.active_txns[self.current_txn] = []
        return self.current_txn
    
    def log_write(self, txn_id, block_id, old_data, new_data):
        """记录写入操作 (redo + undo 信息)"""
        entry = {
            'txn_id': txn_id,
            'block': block_id,
            'old': old_data,
            'new': new_data,
        }
        self.journal.append(entry)
        self.active_txns[txn_id].append(entry)
    
    def commit_txn(self, txn_id):
        self.committed.add(txn_id)
        del self.active_txns[txn_id]
    
    def checkpoint(self):
        """检查点: 将提交的事务写入到数据区域后, 标记为已检查点"""
        for txn_id in list(self.committed):
            self.checkpointed.add(txn_id)
    
    def crash_recovery(self):
        """Crash 恢复: redo 已提交的事务, undo 未提交的"""
        redo_list = []
        undo_list = []
        
        for entry in self.journal:
            if entry['txn_id'] in self.checkpointed:
                continue  # 已检查点, 不需要恢复
            if entry['txn_id'] in self.committed:
                redo_list.append(entry)
            else:
                undo_list.append(entry)
        
        return {'redo': redo_list, 'undo': undo_list}
    
    def simulate_crash(self):
        print("  [Crash 恢复模拟]")
        
        # 正常操作
        t1 = self.begin_txn()
        self.log_write(t1, 100, "旧数据_A", "新数据_A")
        self.log_write(t1, 101, "旧数据_B", "新数据_B")
        self.commit_txn(t1)
        
        self.checkpoint()  # 已检查点
        
        t2 = self.begin_txn()
        self.log_write(t2, 200, "旧数据_C", "新数据_C")
        self.log_write(t2, 201, "旧数据_D", "新数据_D")
        self.commit_txn(t2)
        
        t3 = self.begin_txn()
        self.log_write(t3, 300, "旧数据_E", "新数据_E")
        # t3 未提交 -> crash
        
        # Crash 恢复
        result = self.crash_recovery()
        print(f"   日志条目总数: {len(self.journal)}")
        print(f"   Redo (需要重做): {len(result['redo'])} 条")
        for e in result['redo']:
            print(f"     block {e['block']}: {e['old']} -> {e['new']} (txn={e['txn_id']})")
        
        print(f"   Undo (需要回滚): {len(result['undo'])} 条")
        for e in result['undo']:
            print(f"     block {e['block']}: {e['old']} <- {e['new']} (txn={e['txn_id']}, 未提交)")
        print()


def simulate_journal():
    print("=" * 60)
    print("5. 日志恢复模拟 (JBD2+Undo)")
    print("=" * 60)
    js = JournalSim()
    js.simulate_crash()


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("文件系统核心机制演示")
    print("=" * 60)
    print()
    
    # 1. inode 索引
    print("=" * 60)
    print("1. inode 索引模拟")
    print("=" * 60)
    inode = InodeSim()
    for offset in [0, 5, 11, 12, 13, 14, 15, 100, 200, 500]:
        bn, level = inode.write_block(offset)
        print(f"  逻辑块 {offset:>4} → 物理块 {bn:>6} (索引层级={level})")
    inode.report()
    
    # 2. 页缓存
    simulate_page_cache()
    
    # 3. 写入模式
    simulate_write_patterns()
    
    # 4. 碎片分析
    simulate_fragmentation()
    
    # 5. 日志恢复
    simulate_journal()
    
    print("✅ fs_demo.py 全部完成")


if __name__ == "__main__":
    main()
