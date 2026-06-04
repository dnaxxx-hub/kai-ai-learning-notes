# 存储引擎 #3：WAL、恢复与崩溃安全

> 2026-05-17
> 前置：LSM-Tree 原理 #1

## 1. WAL 的定位

WAL（Write-Ahead Log）是持久化的第一道防线，核心原则：

**"写入 MemTable 之前必须先写 WAL"**

```
崩溃场景分析：
1. 写入 WAL ✅ → 写入 MemTable ❌（写入时炸了）
   → 重启时 Replay WAL，重建 MemTable，数据不丢 ✅

2. 写入 WAL ❌（WAL 写入中炸了）
   → 没写完成，不 commit，当作不存在 ✅

3. 写入 WAL ✅ → 写入 MemTable ✅ → Flush 为 SSTable ✅ → 删除 WAL
   → 重启时 WAL 已被删除，但 SSTable 有数据 ✅

重要前提：WAL 本身的写入必须原子且 fsync 到磁盘
```

## 2. WAL 文件格式

### 2.1 块结构

```
WAL 文件 = 多个 32KB 的 Block

Block (32KB):
┌────────────────────────────────┐
│ Record 1 (type=Full)           │ ← 完整的 KV 记录
├────────────────────────────────┤
│ Record 2 (type=First)          │ ← 跨块记录片段
│ Record 3 (type=Middle)         │
│ Record 4 (type=Last)           │
├────────────────────────────────┤
│ padding to 32KB boundary       │ ← 填充到块末尾
└────────────────────────────────┘
```

### 2.2 Record 格式

每个 Record 7 字节头部 + 数据：

```
┌────────┬──────────┬──────────┬────────────┐
│ CRC32  │ Length   │ Type     │ Data       │
│ (4B)   │ (2B)     │ (1B)     │ (Length B) │
├────────┼──────────┼──────────┼────────────┤
│ 0xA1B2 │ 0024     │ 01(Full) │ key=abc    │
│ C3D4   │          │          │ val=123    │
└────────┴──────────┴──────────┴────────────┘
```

Type 值：0=Zero, 1=Full, 2=First, 3=Middle, 4=Last

### 2.3 Group Commit（RocksDB 优化）

多个并发写入的 WAL 合并为一个 fsync（批量刷盘效率高）：

```
没有 Group Commit：
  Write #1: WAL write → fsync → MemTable → OK
  Write #2: WAL write → fsync → MemTable → OK
  Write #3: ...
  每次 fsync 1ms，每秒最多 1000 次写入

有 Group Commit（RocksDB）：
  Writes #1~#3 一起拼到 WAL buffer
  一次 fsync（1ms）搞定 3 次写入
  每秒 3000+ 次写入
```

## 3. WAL 的同步模式

| 模式 | 写入流程 | 持久性 | 延迟 |
|------|---------|--------|------|
| **同步** | WAL fsync → MemTable | ✅ 不丢数据 | 高（每次 fsync） |
| **异步** | WAL write（不 fsync）→ MemTable | ⚠️ 崩溃丢最后几秒 | 低 |
| **关闭** | 只写 MemTable | ❌ 崩溃全丢 | 最低 |

RocksDB 可精细控制每个写入的同步策略。

## 4. 恢复流程

启动时的恢复流程：

```
1. 从 MANIFEST 获取当前 SSTable 列表和元数据
2. 找到最近的 WAL 文件
3. 从 WAL 中读取所有 Record
4. 对每个 Record 应用 Put/Delete 到 MemTable
5. MemTable 满时 Flush 为 SSTable
6. WAL 中的所有记录处理完毕 → 恢复完成
```

### 4.1 增量恢复

用 WAL 的 Sequence Number（seqno）判断哪些操作已经持久化：

```
WAL seqno range: [1000, 5000]
SSTable 已经包含 seqno ≤ 4500 的数据
→ 只需要 Replay seqno 4501~5000 的记录
```

### 4.2 双重 WAL（RocksDB）

RocksDB 支持同时写两个 WAL 文件做冗余：

```cpp
// RocksDB 配置
Options options;
options.wal_dir = "/data/db/wal";
// 启用双 WAL
options.avoid_flush_during_shutdown = true;
options.two_write_queues = true;  // 并行 WAL 写入
```

## 5. 崩溃恢复的可靠性保障

### 5.1 Checksum

每条 WAL Record 有 CRC32 校验：

```cpp
// 写入时计算
uint32_t crc = crc32(data, length);
EncodeFixed32(header + 4, crc);

// 读取时校验
uint32_t stored_crc = DecodeFixed32(header + 4);
uint32_t computed_crc = crc32(data, length);
if (stored_crc != computed_crc) {
    // 损坏的 Record → 截断到此为止
    ReportCorruption("checksum mismatch");
    return;  // 跳过后续，认为已崩溃
}
```

### 5.2 部分写入处理

崩溃可能发生在写入 WAL 的过程中，导致最后一个 Record 不完整：

```cpp
while (remaining > 0) {
    Status s = reader.ReadRecord(&record, &scratch);
    if (s.IsCorruption()) {
        // 检测到损坏，尝试恢复
        if (IsLastRecord()) {
            // 最后一个 Record 不完整 → 截断
            break;
        }
    }
    // 处理完整 Record
    ApplyRecord(record);
}
```

### 5.3 原子写（RocksDB）

RocksDB 支持 POSIX 文件的 `pwrite` + `fdatasync` 保证原子：

```cpp
// 跨平台的原子写
Status WritableFileWriter::Append(const Slice& data) {
    // 在 Linux 上用 pwrite(O_DIRECT)
    // 在 Windows 上用 WriteFile + FlushFileBuffers
    // 保证 4KB 对齐时的原子写
}
```

## 6. 写入性能与持久性的取舍

```
同步 WAL（每次 fsync）
  延迟：500μs - 2ms（取决于磁盘）
  吞吐：1000 ops/s（单线程）
  不丢数据 ✅

批量提交（100 条一次 fsync）
  延迟：1ms 一次，分摊到 100 条 ≈ 10μs/条
  吞吐：100,000 ops/s
  崩溃丢最后最多 100 条 ⚠️

异步 WAL（1秒一次 fsync）
  延迟：近乎 0
  吞吐：500,000 ops/s
  崩溃丢最后 1 秒的数据 ⚠️
```

**最佳实践**：

```
应用场景 → 同步策略

财务交易、支付 → 同步 WAL（安全第一）
消息队列       → 批量提交（性能与持久平衡）
日志收集       → 异步 WAL（性能第一，丢点无所谓）
```

## 7. 工程实现注意

1. **fsync 不是 write** —— write 只写到页缓存，崩溃会丢，fsync 刷到磁盘才安全
2. **WAL 和 SSTable 最好在不同磁盘** —— 总是写 WAL，不抢 SSTable 的 I/O 带宽
3. **WAL 自动清理** —— 当 SSTable 包含比 WAL 更新的数据时，安全删除 WAL
4. **WAL 文件大小上限** —— 达到后自动切换新文件，旧的可清理

## 总结

```
WAL = 所有写入的第一道防线

写入顺序：先 WAL（持久化）→ 后 MemTable（内存）

恢复：Replay WAL → 重建 MemTable

持久化策略：
  同步：安全，慢
  异步：快，丢数据
  批量提交：折中

工程要点：
  CRC32 校验、部分写入截断、fsync vs write、双 WAL 冗余
```
