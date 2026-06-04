# 存储引擎 #5：Compaction 策略深度解析

> 2026-05-17
> 前置：SSTable 格式 #4

## 1. 为什么需要 Compaction

Compaction（合并）其实在解决一个矛盾：

```
LSM-Tree 的写入优势 = MemTable 满了直接 flush（快）
但：
  不合并 → Level 0 无限堆积 → 读放大无限增长
  合并太多 → 写放大飙升 → 写入性能下降
```

**Compaction 的本质是：用写入代价换读取性能。**

## 2. LevelDB 的 Size-Tiered Compaction

### 2.1 层级规则

```
Level 0: 最多 4 个 SSTable（不用合并）
Level 1: 总大小 ≤ 10MB（Level 0 满 4 个→合并到 L1）
Level 2: 总大小 ≤ 100MB
Level 3: 总大小 ≤ 1GB
Level 4: 总大小 ≤ 10GB
Level 5: 总大小 ≤ 100GB
Level 6: 总大小 ≤ 1TB
```

公式：`MaxSize(N) = 10MB × 10^(N-1)`

超过就触发 Compaction。

### 2.2 合并过程

```
Level N → Level N+1 的合并：

输入：
  Level N 的 1 个 SST（选择最大的或 key 范围交叠最多的）
  Level N+1 的 key 范围与输入重叠的所有 SST

合并过程：
  多路归并排序（类似 MergeSort 的 merge 阶段）
  按 key 顺序输出到新的 SSTable

结束后：
  删除输入的 Level N 和 Level N+1 的旧 SSTable
  添加合并后的新 SSTable
```

```
Level 0 (4 files, overlapping):
  [a-g], [c-i], [j-r], [s-z]

Level 1 (3 files, non-overlapping):
  [a-e], [f-l], [m-z]

触发合并 (pick file [c-i] from L0, overlaps L1 [a-e] + [f-l]):
  Input: L0[c-i] + L1[a-e][f-l]
  ↓ 多路归并
  Output: 2 new SSTs covering [a-l] (不重叠地放入 L1)
```

### 2.3 合并触发条件

LevelDB 的触发时机：

```
1. Level 0 file count > kL0_CompactionTrigger (默认 4)
2. Level N 总大小 > MaxSize(N) 
3. 手动触发（CompactRange）
4. Seek 文件被触发（读操作发现某个 SST 读取次数太多）
```

## 3. RocksDB 的 Level Compaction

RocksDB 基于 LevelDB 的合并做了大量优化：

### 3.1 子合并（Subcompaction）

大文件合并可以用多线程并行：

```
一个合并任务可以被拆分为多个子任务：
  SST 1: [a-m]
  SST 2: [n-z]

Subcompaction 1: [a-f] (线程 1)
Subcompaction 2: [g-m] (线程 2)
Subcompaction 3: [n-s] (线程 3)
Subcompaction 4: [t-z] (线程 4)

4 线程并行 → 理论 4x 加速
```

### 3.2 TTL Compaction

对于有时间戳的数据，TTL Compaction 可以丢弃过期数据：

```cpp
// RocksDB 配置
Options options;
options.ttl = 86400;  // 1 天
options.periodic_compaction_seconds = 3600;  // 每小时检查
```

适用：时序数据、日志、缓存的自动清理。

### 3.3 自适应合并（Adaptive Compaction）

RocksDB 动态调整合并策略：

```
写密集时段：
  → 减少合并频率 → 更加顺序写性能
  → 增加临时空间放大

读密集时段：
  → 增加合并频率 → 减少 Level 0 文件
  → 降低读放大

检测方式：
  监控 I/O 延迟和队列深度
```

## 4. RocksDB 的其他合并策略

### 4.1 Universal Compaction

所有 SSTable 都在一个层级，合并时全部排序：

```
Level 0: [SST1], [SST2], [SST3], ..., [SSTn]
         ↓ 触发合并
         全部排序为一个新的 SSTable
```

适用于写入非常多、读取很少的场景（日志）。

### 4.2 FIFO Compaction

按文件创建时间丢弃最旧的 SSTable（类似循环缓冲区）：

```
Level 0: [SST1(12:00)], [SST2(12:05)], ..., [SSTn(12:30)]
         ↓ 12:35 写入新 SSTable
         检查 SST1 已经超过设定 TTL（如 1 小时）
         直接删除 SST1
```

适用：缓存、临时数据、消息队列的已消费数据。完全不需要合并——直接过期删除。

### 4.3 策略选择

```
写入工作负载 → Universal Compaction
时序/日志数据 → FIFO + TTL
通用/读写均衡 → Level Compaction（默认）
```

## 5. Compaction 的代价

### 5.1 写放大分析

写一个 key 到 Level 0（1 次写入）→ 被合并到 Level 1（1 次重写）→ 再被合并到 Level 2（1 次重写）…… N 个 level 就写 N 遍。

```
写放大因子 ≈ (Level 总数) / (Level 0 文件数量合并比率)

LevelDB 默认 ≈ 10-40x
RocksDB 优化后 ≈ 3-10x
Universal ≈ 1-2x（但读更慢）
```

### 5.2 I/O 抖动

合并时的 I/O 突发可能影响前台请求：

```
没有合并时：延迟 1ms
合并进行中：延迟 10-50ms（I/O 争抢）
```

RocksDB 的缓解方案：
- **Rate Limiter**：控制合并 I/O 速度

```cpp
// 限制合并 I/O ≤ 100MB/s
options.rate_limiter.reset(NewGenericRateLimiter(100 * 1024 * 1024));
```

- **子合并**：利用多核并行，缩 I/O 突发持续时长
- **预读**：Flush 时预读目标 Level 的相关 SSTable，减少随机 I/O

### 5.3 空间放大 vs 写放大的取舍

```
调大 compaction 触发阈值：
  写放大 ↓（更少合并）→ 空间放大 ↑（更多临时 SST）

调小 compaction 触发阈值：
  写放大 ↑（更多合并）→ 空间放大 ↓（更少临时 SST）
```

最佳配置需要通过实际工作负载测试→监控→调整。

## 6. Compaction 的工程实现细节

**定位输入文件**：
```cpp
// 选择需要合并的 SSTable
void CompactionPicker::PickCompaction() {
    // 1. 找到最大的 Level（Level 0 选文件最多的 level）
    // 2. 在每个 Level 中选择与输入 key 范围重叠的文件
    // 3. 计算总输入大小
    // 4. 如果总大小超过阈值 → 启动合并
    
    int target_level = FindCompactionLevel();
    std::vector<FileMetaData*> input_files = 
        GetOverlappingFiles(target_level, compaction_key_range);
    if (TotalSize(input_files) > compaction_size_threshold) {
        ScheduleCompaction(input_files);
    }
}
```

**多路归并排序**：
```cpp
// 多路归并（多文件 → 排序后 → 写为一个新文件）
class CompactionIterator {
    // 维护所有输入文件的最小堆
    std::priority_queue<Iterator*, std::vector<Iterator*>, IteratorComparator> heap_;
    
    void MergeAndWrite() {
        while (!heap_.empty()) {
            auto* it = heap_.top(); heap_.pop();
            WriteKV(it->key(), it->value());
            it->Next();
            if (it->Valid()) heap_.push(it);
            // 检查是否需要切换到新文件（大小超限）
            if (current_file_size >= target_file_size) {
                FlushCurrentFile();
            }
        }
    }
};
```

## 总结

```
Compaction = 写入性能与读性能的核心权衡

LevelDB 策略：
  层级增长（10x 每级）
  多路归并 → 新文件 → 删除旧文件

RocksDB 扩展：
  子合并（并行）
  TTL Compaction（过期丢弃）
  Universal（全排序，少写放大）
  FIFO（纯时间窗口，零合并）
  Rate Limiter（控制 I/O 暴增）

核心矛盾：
  合并越多 → 读越快 → 写越慢
  合并越少 → 写越快 → 读越慢
  需要针对负载做权衡和微调
```
