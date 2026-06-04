# 存储引擎 #6：LevelDB 源码实战分析

> 2026-05-17
> 前置：Compaction 策略 #5

## 1. LevelDB 整体架构

LevelDB 是 Google 开源的嵌入式 KV 存储，核心代码约 1 万行 C++：

```
/leveldb/
├── db/              # 核心
│   ├── db_impl.cc   # DB 主实现（打开/关闭/读写/Getsnapshot）
│   ├── db_iter.cc   # 迭代器（跨 MemTable + SSTable 的多路合并）
│   ├── memtable.cc  # 跳表实现（内存存储）
│   ├── table_cache.cc  # SSTable 文件缓存
│   ├── version_edit.cc, version_set.cc  # Manifest 管理
│   ├── builder.cc   # SSTable 构建器
│   └── compaction.cc    # 合并调度
├── table/           # SSTable 格式
│   ├── block_builder.cc  # Data Block 构建+前缀压缩
│   ├── block.cc          # Data Block 读取+二分查找
│   ├── table_builder.cc  # SSTable 写（Footer/Index/Meta）
│   ├── table.cc          # SSTable 读 + Bloom Filter
│   ├── two_level_iterator.cc  # 双层迭代器（Index→Data）
│   └── format.h      # 常量和类型定义
├── util/            # 工具
│   ├── bloom.cc     # Bloom Filter实现
│   ├── cache.cc     # LRU Cache
│   ├── coding.cc    # Varint + 固定编码
│   ├── crc32c.cc    # CRC32 校验
│   ├── comparator.cc    # BytewiseComparator
│   └── arena.cc     # 内存分配器（简化 malloc/free）
├── include/leveldb/    # 公共头文件
│   ├── db.h
│   ├── options.h
│   ├── write_batch.h
│   └── ...
└── helpers/memenv/     # 内存文件系统（测试用）
```

## 2. 关键数据结构

### 2.1 DBImpl（数据库实例）

```cpp
class DBImpl : public DB {
    MemTable* mem_;                    // 当前活跃 MemTable（可写）
    MemTable* imm_;                    // 冻结 MemTable（等待 flush）
    VersionSet* versions_;             // SSTable 版本管理（含 Manifest）
    Status log_;                       // 当前 WAL 文件写入器
    TableCache* table_cache_;          // SSTable 文件缓存
    std::atomic<bool> shutting_down_;  // 关闭标志
    BackgroundWork scheduled_;         // 后台合并状态
    Mutex mutex_;
};
```

**关键方法调用链**：

```cpp
// Put（写入）
DB::Put(WriteOptions, key, value)
  → DBImpl::Write(write_batch)
    → 写入 WAL（先 fsync）
    → 写入 MemTable（跳表插入）
    → 如果 MemTable 满：提出 imm_ 并新 mem_
    → MaybeScheduleCompaction() 触发合并

// Get（读取）
DB::Get(ReadOptions, key, value)
  → 先查 MemTable（当前）
  → 再查 Immutable MemTable（冻结的）
  → 查 Level 0 所有 SSTable（从最新到最旧）
  → 查 Level 1+（每级至多 1 个 SST，二分查找）
  → 有 Bloom Filter：先检查再读
```

### 2.2 WriteBatch（批写入）

```
WriteBatch 编码格式：
  sequence: 8 bytes       # 批的起始序号
  count: 4 bytes          # 批中的记录数
  records:
    type: 1 byte          # 0=删除 1=写入
    key_length: varint    # key 长度
    key: bytes            # key
    value_length: varint  # value 长度（删除没有）
    value: bytes          # value
```

写入时整个 WriteBatch 作为一个原子操作。

### 2.3 MemTable（跳表）

```cpp
class MemTable {
    explicit MemTable(const InternalKeyComparator& comparator);
    
    void Add(SequenceNumber seq, ValueType type,
             const Slice& key, const Slice& value);
    
    bool Get(const LookupKey& key, std::string* value,
             Status* s);
    
    Arena arena_;                 // 自分配内存（减少 malloc 碎片）
    Table table_;                 // 跳表实现（skiplist.h）
};
```

关键特性：
- **Arena**：预分配内存块，减少 malloc 开销和碎片
- **跳表**：无锁读（写需要加锁），O(log N) 查询/插入
- InternalKey = `user_key + sequence_number + type`

### 2.4 InternalKey

SSTable 和 MemTable 内部使用的键格式：

```
User Key (可变长) + SeqNo (7 bytes) + Type (1 byte)

示例：
  user key = "mykey"
  seqno    = 42
  type     = kTypeValue (1)
  
  InternalKey = "mykey" + "\x00\x00\x00\x00\x00\x00\x2a" + "\x01"
```

**SeqNo 的作用**：
- 实现 Snapshot（读的时候指定 seqno，只看到 ≤ seqno 的版本）
- Compaction 时判断哪些记录是过时的（被后来覆盖的）

### 2.5 VersionSet & Version

```cpp
class VersionSet {
    Version* current_;           // 当前的版本（活跃的 SSTable 列表）
    std::deque<Version*> versions_;  // 历史版本（被引用的）
};

struct FileMetaData {
    int refs;
    int allowed_seeks;          // 允许的查找次数（触发 seek 合并）
    uint64_t number;            // 文件编号（递增）
    uint64_t file_size;         // 文件大小
    InternalKey smallest;       // 最小 key
    InternalKey largest;        // 最大 key
};
```

每次合并后创建新 `Version` 替换 `current_`，同一个 `Version` 可以被多个迭代器引用（引用计数）。

## 3. 写入流程（代码级）

```cpp
Status DBImpl::Write(const WriteOptions& options, WriteBatch* updates) {
    // 1. 获取写锁（多线程组提交）
    MutexLock l(&mutex_);
    
    // 2. 合并多个并发的 WriteBatch
    writers_.push_back(&updates);
    while (/* 不是队首 */) {
        // 等待前面的批次完成
        cv_.Wait();
    }
    // 合并等待队列中的多个 WriteBatch 为一个
    WriteBatch* merged = BuildBatchGroup(&writers_);
    
    // 3. 增加序列号
    SequenceNumber seq = versions_->LastSequence() + 1;
    merged->SetSequence(seq);
    versions_->SetLastSequence(seq + merged->Count() - 1);
    
    // 4. 写入 WAL
    Status s = log_->AddRecord(merged->Contents());
    if (s.ok() && options.sync) {
        s = log_->Sync();       // fsync（同步模式）
    }
    
    // 5. 写入 MemTable
    s = merged->InsertInto(mem_);
    
    // 6. 检查是否需切换 MemTable
    if (mem_->ApproximateMemoryUsage() > options_.write_buffer_size) {
        mem_->SetReadOnly();       // 当前 mem_ 变 imm_
        imm_ = mem_;
        mem_ = new MemTable(...);  // 新的 mem_
        // 新 mem_ 使用新 WAL
        s = NewWAL(log_number_, ...);
        MaybeScheduleCompaction(); // 触发合并
    }
    
    // 7. 通知等待中的写线程
    while (!writers_.empty() && writers_.front()->done) {
        writers_.pop_front();
        cv_.Signal();
    }
    
    return s;
}
```

## 4. 读取流程（代码级）

```cpp
Status DBImpl::Get(const ReadOptions& options,
                   const Slice& key, std::string* value) {
    // 1. 加入读引用（防止 Version 被合并时回收）
    Version* current = versions_->current();
    current->Ref();
    
    // 2. 计算 Snapshot 的序列号
    SequenceNumber snapshot = options.snapshot
        ? options.snapshot->number_
        : versions_->LastSequence();
    
    // 3. 按优先级查找
    //    ✅ MemTable（最新） → 最快
    //    ✅ Immutable MemTable（次新）
    //    ✅ Level 0 SSTable（最新到最旧）
    //    ✅ Level 1+（每级至多一个）
    Status s;
    LookupKey lkey(key, snapshot);
    
    if (mem_->Get(lkey, value, &s))          // MemTable 命中
        goto done;
    if (imm_ != nullptr && imm_->Get(lkey, value, &s))  // imm 命中
        goto done;
    
    // 从 SSTable 读取
    s = current->Get(options, lkey, value, &stats);
    
done:
    current->Unref();  // 释放 Version 引用
    MaybeScheduleCompaction();  // 读触发的 seek-compaction
    return s;
}
```

**Version::Get** 中的 SSTable 搜索：

```cpp
bool Version::Get(const ReadOptions& options,
                  const LookupKey& key, std::string* value) {
    // Level 0：检查所有文件（可能有重叠）
    for (int i = 0; i < files_[0].size(); i++) {
        if (f->largest < key || f->smallest > key) continue;  // 范围过滤
        if (f->allowed_seeks <= 0) {
            // 这个文件被读取太多次了 → 触发合并
            ScheduleCompaction(f);
            continue;
        }
        if (table_cache_->Get(options, f->number, ...)) {
            f->allowed_seeks--;
            return true;  // 找到了
        }
    }
    
    // Level 1+：二分查找（范围不重叠）
    for (int level = 1; level < config::kNumLevels; level++) {
        const std::vector<FileMetaData*>& files = files_[level];
        if (files.empty()) continue;
        
        // 二分查找包含目标 key 的文件
        uint32_t idx = FindFile(vset_->icmp_, files, key.Encode());
        if (idx < files.size()) {
            FileMetaData* f = files[idx];
            if (f->largest >= key && f->smallest <= key) {
                if (table_cache_->Get(options, f->number, ...)) {
                    return true;
                }
            }
        }
    }
    
    return false;  // 没找到
}
```

## 5. Compaction 调度

```cpp
void DBImpl::BackgroundCompaction() {
    // 1. Imm 还没 flush → 先 flush
    if (imm_ != nullptr) {
        CompactMemTable();
        return;
    }
    
    // 2. 选择需要合并的文件
    Compaction* c = versions_->PickCompaction();
    if (c == nullptr) return;
    
    // 3. 执行合并
    if (c->IsTrivialMove()) {
        // 单个文件可以直接下移（不重叠时）
        versions_->Edit(c->inputs()[0], c->level() + 1);
    } else {
        // 多路归并
        DoCompactionWork(c);
    }
    
    // 4. 更新 Version
    versions_->LogAndApply(c->edit(), &mutex_);
    
    // 5. 清理过期文件 + 计算下一次合并
    DeleteObsoleteFiles();
    MaybeScheduleCompaction();
}
```

**TrivialMove 优化**：如果 Level N 的 SSTable 与 Level N+1 完全不重叠，不做实际合并——直接下移 Level 元数据（省一个完整合并）。

## 6. 从中吸取的工程经验

### 6.1 代码质量

LevelDB 的品质决定了它的晚辈掌握存储引擎的精髓：

1. **极简**：~1 万行，实现完整 LSM-Tree，每个类单职责
2. **零依赖**：纯 C++11，无第三方库
3. **充分覆盖的测试**：table_test, db_test, corruption_test
4. **抽象精准**：Iterator 模式贯穿读取、合并、压缩全部

### 6.2 可以借鉴的设计

- **Arena 分配器**：特殊的内存分配，减少碎片和 free 开销
- **引用计数 Version**：快照持续引用旧版本，合并创建新版本
- **WriteBatch 批量提交**：合并多个并发写入做一次 fsync 和跳表插入
- **State Machine 的 VersionSet**：每次 Change 都是 append-log

### 6.3 与 RocksDB 的不同

RocksDB 在 LevelDB 之上增加了：
- 多线程合并（LevelDB 单线程后台）
- 多种压缩算法和缓存分片
- 列族（Column Family）
- Merge Operator
- 事务支持
- PinnableSlice（避免复制大 value）

## 总结

```
LevelDB 源码 ≈ 1 万行 C++ 实现完整 LSM-Tree

写入路径：
  WriteBatch → WAL(fsync) → MemTable(跳表)
  MemTable 满 → flush 为 SSTable(Immutable→File)

读取路径：
  MemTable → Immutable → Level 0(逐个看) → Level 1+(二分看)

合并路径：
  Level N 超限 → 选文件 → 多路归并 → 新 Version

工程精华：
  Arena 分配器、跳表、Iterator 模式、
  引用计数 Version、WriteBatch 组提交
```
