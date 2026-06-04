# 存储引擎 #4：SSTable 格式与编码

> 2026-05-17
> 前置：WAL 与恢复 #3

## 1. SSTable 文件结构详解

SSTable (Sorted String Table) 是 LSM-Tree 的磁盘数据结构——有序的、不可变的键值文件。

### 1.1 物理层次

```
┌────────────────────────────────────────────────────┐
│ Footer (48 bytes，固定在文件末尾)                    │
│  - Meta Index Handle      (指向 Meta Index Block)   │
│  - Index Handle           (指向 Index Block)        │
│  - Padding                (8 bytes)                 │
│  - Magic Number           (8 bytes: SHA哈希前8字)   │
├────────────────────────────────────────────────────┤
│ Index Block                                         │
│  - 每个 Data Block 的 last_key + offset + size      │
│  - 按 key 二分查找定位 Data Block                    │
├────────────────────────────────────────────────────┤
│ Meta Index Block                                    │
│  - 指向各个 Meta Block 的句柄                        │
├────────────────────────────────────────────────────┤
│ Meta Block 1: Bloom Filter                          │
│  - 布隆过滤器位图（可选）                             │
├────────────────────────────────────────────────────┤
│ Meta Block 2: Statistics（可选）                      │
│  - key 数量、最大/最小 key 等                        │
├────────────────────────────────────────────────────┤
│ Data Block N                                        │
│  - 键值对，按 key 排序                               │
├────────────────────────────────────────────────────┤
│ ...                                                 │
├────────────────────────────────────────────────────┤
│ Data Block 0                                        │
│  - 键值对 [key0, val0], [key1, val1], ...            │
│  - 重启点 + 前缀压缩                                 │
└────────────────────────────────────────────────────┘
```

### 1.2 Data Block 的内部结构

Data Block 默认 4KB，内部使用**前缀压缩**：

```
Data Block = [Entry * N] + [Restart Points * M] + [Trailer]

Entry 格式（前缀压缩）：
┌────────┬──────────┬────────────┬─────────┐
│ shared │ unshared │ value_len  │ value   │
│ (varint)│ (varint) │ (varint)  │ (bytes) │
├────────┼──────────┼────────────┼─────────┤
│ key:   │          │            │         │
│  "abcdef001" → no compression（shared=0, unshared=9）
│  "abcdef002" → shared=6 ("abcdef"), unshared=3 ("002")
│  "abcdef005" → shared=6 ("abcdef"), unshared=3 ("005")
└────────┴──────────┴────────────┴─────────┘
```

**重启点（Restart Points）**：
每 16 个 Entry 设一个重启点，重启点的 entry **不压缩**（shared=0）。

作用：
- 允许二分查找定位 Entry（不需要从头扫描解压）
- 压缩和查找之间的平衡

### 1.3 Index Block

Index Block 不做前缀压缩（小且需要能力二分查找）：

```
Index Entry 格式（固定）：
  [last_key of data block (length-prefixed)]
  [offset of data block (varint)]
  [size of data block (varint)]

示例:
  Entry 1: "abcdef016" [offset: 0,     size: 4096]
  Entry 2: "abcdef032" [offset: 4096,  size: 4096]
  Entry 3: "ghi000001" [offset: 8192,  size: 4096]
```

## 2. 编码技术

### 2.1 Varint（可变长度整数）

大量整数（如 offset, length）用 varint 编码比固定 4/8 字节省很多：

```python
def encode_varint(n: int) -> bytes:
    """整数 → 可变长字节"""
    buf = bytearray()
    while n >= 0x80:                      # ≥ 128 需要多字节
        buf.append((n & 0x7F) | 0x80)     # 低 7 位 + 最高位标记位
        n >>= 7
    buf.append(n & 0x7F)                  # 最后 7 位，无标记
    return bytes(buf)

def decode_varint(buf: bytes, offset: int) -> tuple[int, int]:
    """从字节中读取一个 varint"""
    result = 0
    shift = 0
    while True:
        byte = buf[offset]
        result |= (byte & 0x7F) << shift
        shift += 7
        offset += 1
        if not (byte & 0x80):             # 最高位为 0 → 最后一个字节
            return result, offset
```

编码效果：
- 小整数（0-127）：1 字节（vs 4 字节 int32）
- 中等（128-16383）：2 字节
- 整数存为 4 字节的情况很少（多数 offset 都小）

### 2.2 数据压缩

SSTable 可选压缩 Data Block：

| 压缩算法 | 速度 | 压缩比 | 适用 |
|---------|------|--------|------|
| Snappy | ✅ 极快 | 1.5-2x | 通用默认 |
| LZ4 | ✅✅ 最快 | ~2x | 需要低延迟 |
| Zlib | ❌ 慢 | 3-4x | 存储紧张 |
| ZSTD | ✅ 快 | 3-5x | 压缩比+速度均衡 |

**RocksDB 默认用 Snappy**（解压速度是最关键的，读路径每次都要解压）。

**压缩选择指南**：
- 热数据 → Snappy/LZ4（读命中率高，需要快去解压）
- 冷数据 → ZSTD（读少，更重要是省空间）

## 3. 布隆过滤器在 SSTable 中的实现

Bloom Filter 存在每个 SSTable 的 Meta Block 中：

```
SSTable N: [Data Blocks] [Bloom Filter (meta)] [Index] [Footer]

查找过程：
1. 检查 MemTable 和 Immutable MemTable
2. 检查 Level 0 的所有 SSTable：
   a. 读取 Bloom Filter（检查 key 是否可能在其中）
   b. Bloom 说不存在 → 跳过 ✅
   c. Bloom 说可能存在 → 二分 Index Block 找 Data Block
3. 检查 Level 1+：
   a. 二分找哪个 SSTable 可能含这个 key
   b. Bloom 过滤后再读内容
```

Bloom Filter 参数：
- 每个 key 约 10 bits → 1% 假阳率
- 每个 SSTable 独立的 Bloom（不跨文件）
- RocksDB 还支持 Full-Filter（全量）和 Partitioned-Filter（分片）

## 4. SSTable 的生命周期

```
创建：MemTable Flush → 直接写为一个 SSTable (Level 0)
存活：Serve reads + 等待被合并
合并：Compaction 读取多个 SSTable → 合并 → 写入新 SSTable
删除：合并后老 SSTable 不再被引用 → 删除

关键约束：
  SSTable 一旦创建，永远不修改（immutable）
  Compaction 只创建新的 SSTable，删除旧的
  任何时候读写都要假设 SSTable 可能正在被合并中
```

## 5. Manifest

Manifest 记录所有 SSTable 的 Level 分配和 key 范围：

```
Current (已持久化的版本)：
  Level 0: 4 SSTables
    [file1: keys a-z, size 10MB]
    [file2: keys a-b, size 1MB]   ← 重叠（L0 特性）
    [file3: keys c-e, size 2MB]
    [file4: keys f-z, size 8MB]
  Level 1: 3 SSTables
    [file5: keys a-e, size 5MB]   ← 不重叠
    [file6: keys f-k, size 4MB]
    [file7: keys l-z, size 6MB]
  Level 2: 5 SSTables
    ...
```

Manifest 也是 append-only 的日志文件，每次版本变更追加一条 Edit 记录。

## 总结

```
SSTable = 不可变、有序的键值文件

内部结构：
  Data Block  ← 前缀压缩 + 重启点二分
  Index Block ← 快速定位 Data Block
  Meta Block  ← Bloom Filter / 统计信息

编码优化：
  Varint 编码整数（省空间）
  前缀压缩相邻 key（省空间）
  Snappy/LZ4 压缩 Data Block（省 I/O）

生命周期：
  Flush 创建 → Compaction 重写 → 不再引用则删除
  永远不原地修改
```
