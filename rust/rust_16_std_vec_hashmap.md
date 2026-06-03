# Rust #16：深入标准库 — Vec 与 HashMap 源码分析

> 2026-05-25
> 目标：分析 Rust 标准库中 Vec 和 HashMap 的核心实现，与 C++ STL 对比

## 1. Vec<T> — 动态数组

### 1.1 数据结构

```rust
// Rust 标准库中 Vec 的实际定义（简化）
pub struct Vec<T, A: Allocator = Global> {
    buf: RawVec<T, A>,  // 内存管理
    len: usize,         // 当前元素数量
}

// RawVec 的核心
struct RawVec<T, A: Allocator = Global> {
    ptr: Unique<T>,     // 裸指针，指向堆分配的内存
    cap: usize,         // 总容量（元素个数，不是字节数）
    alloc: A,           // 分配器（默认 Global）
}
```

**内存布局**：
```
栈上:                    堆上:
┌─────────────┐          ┌─────┬─────┬─────┬─────┬─────┐
│ ptr         │──────→   │ T0  │ T1  │ T2  │ T3  │ ... │
│ cap = 4     │          └─────┴─────┴─────┴─────┴─────┘
│ len = 3     │          ↑                  ↑
└─────────────┘          |                  └─ capacity
                         └─ len (初始化元素)
```

**与 C++ vector 的对比**：

| 特性 | Rust Vec | C++ std::vector |
|:-----|:---------|:-----------------|
| 栈上大小 | 3 个 usize (24B) | 3 个指针 (24B) |
| 内存管理 | 所有权系统 + Drop | 构造函数/析构函数 |
| 空 vector 优化 | 不分配堆内存 (cap=0, ptr 为非空悬垂指针) | 类似 |
| 零大小类型 | 特化：不分配堆内存 (cap=!0) | 特化：类似 |
| 增长策略 | 翻倍 (x2) | 翻倍 (x2) |

### 1.2 关键方法实现

**创建 (new)**：
```rust
// Vec::new() 不分配堆内存
pub const fn new() -> Vec<T> {
    Vec { buf: RawVec::new(), len: 0 }
}

// RawVec::new(): cap=0, ptr 指向 1 字节对齐的悬垂指针
// 这样 Vec::new() 是 const fn，可在编译期求值
```

**Push — 扩容**：
```rust
pub fn push(&mut self, value: T) {
    if self.len == self.buf.cap {
        self.buf.reserve_for_push(self.len);
    }
    // 注意：这里直接用 ptr::write 写入，不通过 Drop 旧值
    unsafe {
        let end = self.as_mut_ptr().add(self.len);
        ptr::write(end, value);
        self.len += 1;
    }
}

// 扩容策略
fn grow_amortized(&mut self, needed: usize) {
    // 新容量 = max(当前容量 * 2, 需要容量)
    let new_cap = cmp::max(self.cap * 2, needed);
    // ...重新分配内存
}
```

**Pop**：
```rust
pub fn pop(&mut self) -> Option<T> {
    if self.len == 0 { None }
    else {
        self.len -= 1;
        // ptr::read 创建位的拷贝，不运行 Drop
        // 需要调用者保证原位置不再使用
        unsafe { Some(ptr::read(self.as_ptr().add(self.len))) }
    }
}
```

**Drop — 析构**：
```rust
impl<T, A: Allocator> Drop for Vec<T, A> {
    fn drop(&mut self) {
        // 按顺序析构每个元素（逆序）
        // 然后释放堆内存
        unsafe {
            ptr::drop_in_place(ptr::slice_from_raw_parts_mut(
                self.as_mut_ptr(), self.len));
        }
        // RawVec::drop 释放堆内存
    }
}
```

### 1.3 小技巧和小特性

**ZST (Zero Sized Type) 优化**：
```rust
// 对于 () 这样的零大小类型，Vec 根本不分配堆内存
// cap 被设为 usize::MAX
impl<T> RawVec<T, Global> {
    fn new() -> Self {
        let cap = if mem::size_of::<T>() == 0 { !0 } else { 0 };
        RawVec {
            ptr: Unique::dangling(),  // 悬垂指针
            cap,
            alloc: Global,
        }
    }
}
```

**Drain (范围删除)**：
```rust
// drain(..) 返回一个迭代器，元素被"移出"vec
// 但在 drain 被 drop 前，vec 中的"空洞"不会被填充
// drain 被 drop 时会移动剩余元素填补空洞
```

### 1.4 C++ vector 差异

```cpp
// C++ std::vector
std::vector<int> v;
v.push_back(42);
// 分配新内存 → 拷贝构造所有元素 → 销毁旧元素 → 释放旧内存

// Rust Vec
let mut v: Vec<i32> = Vec::new();
v.push(42);
// 分配新内存 → ptr::write（memcpy 级）→ 释放旧内存
// i32 实现了 Copy, 不需要析构
```

对于非 Copy 类型（如 `String`）：
```rust
let mut v = Vec::new();
let s = String::from("hello");
v.push(s);      // s 被 move 进 vec，所有权转移
// 之后 s 不再有效 — 编译器保证
```

C++ 中对象被 push 后原始对象仍然存在（被拷贝了）。

## 2. HashMap<K, V> — 哈希表

### 2.1 数据结构

Rust 的 HashMap 使用 **Swiss Table** 实现（源于 Google 的 Abseil 库的 `flat_hash_map`）。

```rust
// Rust HashMap 实际定义（简化）
pub struct HashMap<K, V, S = RandomState> {
    base: base::HashMap<K, V, S>,
}

// 底层实现：hashbrown crate
// hashbrown::HashMap 使用 Swiss Table (也叫 Grouped Hash Table)
struct HashMap<K, V, A = Global> {
    table: RawTable<(K, V), A>,
}

struct RawTable<T, A> {
    table: RawTableInner,
    _marker: PhantomData<T>,
}

struct RawTableInner {
    bucket_mask: usize,     // buckets 数量 - 1（总是 2^n - 1）
    ctrl: NonNull<u8>,      // control bytes 数组
    growth_left: usize,     // 还剩多少插入不需要扩容
    items: usize,           // 当前元素数量
}
```

### 2.2 Swiss Table 核心原理

传统哈希表每个 bucket 存一个 `(key, hash, value)`，而 Swiss Table 将 **control bytes** 和 **data** 分开存储：

```
Control Bytes (每个 bucket 1 byte):
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ 0x80│ 0xFF│ 0x82│ 0x7F│ 0x80│ 0x80│ 0x81│ 0x80│
│ 空  │ 已占│ 已占│ 已占│ 空  │ 空  │ 已占│ 空  │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

Data Buckets:
┌──────────┬──────────┬──────────┬──────────┬──────
│ empty    │ (k1, v1) │ (k2, v2) │ (k3, v3) │ ...
└──────────┴──────────┴──────────┴──────────┴──────
```

**Control Byte 编码**：
- 最高位（bit 7）：1 = 空/已删除，0 = 已占用
- 低 7 位：hash 值的 **H2**（前 7 位），用于快速探测

### 2.3 查找过程

```rust
fn find(&self, key: &K) -> Option<&V> {
    let hash = self.hash(key);
    let h2 = h2(hash);          // hash 的低 7 位
    let index = h1(hash);       // hash 的高位 → bucket index

    loop {
        // 关键优化：一次 SIMD 操作检查 16 个 control bytes
        let group = Group::load(self.ctrl(index));
        let matches = group.match_byte(h2);

        for i in matches.iter() {
            let actual_index = (index + i) & self.bucket_mask;
            if self.key_eq(actual_index, key) {
                return Some(&self.data[actual_index].1);
            }
        }

        // 没找到 → 检查是否有空位
        if group.match_empty().any() {
            return None;  // 这个 group 中有空位 → key 不存在
        }

        // 继续探测下一个 group
        index += Group::WIDTH;
    }
}
```

**关键优化**：一次检查 16 个 bucket（使用 SSE2/AVX2/NEON）

```rust
// x86 SSE2 实现
struct Group([u8; 16]);

impl Group {
    fn match_byte(&self, h2: u8) -> BitMask {
        // _mm_set1_epi8(h2)  — 填充 16 个 h2
        // _mm_cmpeq_epi8     — 逐字节比较
        // _mm_movemask_epi8  — 把比较结果打包成一个 16-bit 位掩码
        unsafe {
            let cmp = _mm_cmpeq_epi8(
                _mm_loadu_si128(self.0.as_ptr()),
                _mm_set1_epi8(h2 as i8),
            );
            BitMask(_mm_movemask_epi8(cmp) as u16)
        }
    }
}
```

**这意味着什么？** 每次 probe 检查 16 个 bucket，但只有 1-2 次 SIMD 指令！

### 2.4 插入过程

```rust
fn insert(&mut self, key: K, value: V) -> Option<V> {
    let hash = self.hash(&key);
    let h2 = h2(hash);

    if self.growth_left == 0 {
        self.resize();  // 扩容
    }

    loop {
        let group = Group::load(self.ctrl(index));
        // 1. 先尝试找空位
        if let Some(pos) = group.match_empty_or_deleted().lowest_set() {
            let actual = (index + pos) & self.bucket_mask;
            self.ctrl[actual] = h2;
            self.data[actual] = (key, value);
            self.items += 1;
            self.growth_left -= 1;
            return None;
        }
        // 2. 检查这个 slot 是否匹配相同 key（覆盖）
        for i in group.match_byte(h2).iter() {
            let actual = (index + i) & self.bucket_mask;
            if self.key_eq(actual, &key) {
                let old = std::mem::replace(&mut self.data[actual], (key, value));
                return Some(old.1);
            }
        }
        index += Group::WIDTH;
    }
}
```

### 2.5 扩容 (Resize)

```rust
fn resize(&mut self) {
    let new_capacity = cmp::max(
        self.bucket_mask + 1,
        Group::WIDTH,  // 至少 16
    ) * 2;

    // 创建新表
    let mut new_table = RawTableInner::with_capacity(new_capacity);

    // 重新插入所有元素（因为 bucket_mask 变了）
    for i in 0..self.bucket_mask + 1 {
        if self.is_full(i) {
            let (key, value) = ptr::read(self.data.add(i));
            new_table.insert_no_grow(hash(&key), (key, value));
        }
    }

    // 替换旧表
    *self = new_table;
}
```

**扩容策略**：当 `growth_left == 0` 时翻倍。`growth_left` 初始为 `capacity * (7/8)` — 即 Swiss Table 的负载因子是 **87.5%**（7/8）。

### 2.6 与 C++ 的对比

| 特性 | Rust HashMap (Swiss Table) | C++ unordered_map |
|:-----|:---------------------------|:-------------------|
| 底层算法 | Swiss Table (开放寻址) | 链式哈希 (bucket + 链表) |
| 负载因子 | 87.5% (7/8) | 默认 1.0（可设置） |
| cache miss | 少（连续内存 + 一次 cache line 16 个 slot）| 多（链表遍历） |
| 冲突解决 | 二次探测 (group-level) | 链表 |
| 哈希器 | SipHash-1-3 (默认，DoS 安全) | std::hash (简单) |
| 迭代器顺序 | O(1) 随机（无稳定顺序） | O(buckets) 按 bucket 顺序 |
| 空表堆内存 | 0 (lazy init) | 0 (lazy init) |
| SIMD 优化 | SSE2/AVX2/NEON | 无 |

### 2.7 SipHash — Rust 的默认哈希器

```rust
// HashMap 的默认哈希器是 RandomState (SipHash-1-3)
impl<K, V> HashMap<K, V> {
    pub fn new() -> HashMap<K, V, RandomState> {
        HashMap {
            base: base::HashMap::with_hasher(RandomState::new()),
        }
    }
}
```

**为什么 SipHash？**
- **确定性但不可预测**：每个进程启动时随机生成 key
- **DoS 安全**：攻击者无法构造大量哈希碰撞的 key
- **性能权衡**：比简单 hash 慢 ~3x，但远比 DoS 攻击的风险小

**性能对比**：

| 哈希器 | 速度（相对） | DoS 安全 |
|:-------|:------------|:---------|
| SipHash-1-3 (Rust 默认) | 1x | ✅ |
| FxHash | ~5x | ❌ |
| AHash | ~3x | ✅ |
| std::hash (C++) | ~3x | ❌ (可预测) |

## 3. 源码分析总结

### 3.1 Vec 的关键设计决策

1. **胖指针存储**：ptr + cap + len，栈上 24 字节
2. **永不分配**：`Vec::new()` 是零分配操作
3. **ZST 优化**：零大小类型跳过堆分配
4. **RawVec 分离**：将内存管理从 Vec 逻辑中分离出来
5. **翻倍扩容**：时间复杂度摊还 O(1)

### 3.2 HashMap 的关键设计决策

1. **Swiss Table**：Google 的现代化哈希表实现，内存效率极高
2. **SIMD 加速**：一次检查 16 个 slot 的匹配
3. **高负载因子**：7/8，内存利用率高
4. **SipHash 默认**：安全性优先于极致性能
5. **lazy 分配**：空 HashMap 不占堆内存

### 3.3 Rust vs C++ STL 的设计哲学

| 方面 | Rust | C++ |
|:-----|:-----|:----|
| 内存安全 | 编译器保证（借用检查器 + Drop） | 开发者保证（RAII + 智能指针） |
| 默认安全 | SipHash (防哈希碰撞) | 性能优先 |
| 零成本抽象 | 是（Vec 和手写的 C 数组一样快） | 是 |
| 迭代器 | IntoIter (消耗), Iter (借用), IterMut | 迭代器 + const_iterator |
| 侵入式优化 | SIMD 直接嵌入 | 标准库实现保守 |
| 分配器 | Allocator trait (可替换) | Allocator (C++17+) |

## 4. 阅读源码的方法

```bash
# 查看本地 Rust 标准库源码
rustup component add rust-src

# 在 IDE 中直接跳转到 std::vec::Vec 的实现
# 路径：~/.rustup/toolchains/stable-x86_64-pc-windows-msvc/lib/rustlib/src/rust/library/
#   - alloc/src/vec/mod.rs — Vec 实现
#   - hashbrown/src/map.rs — HashMap 实现
```

**推荐阅读顺序**：
1. `Vec::push` → `Vec::pop` → `Vec::remove` (最常用)
2. `RawVec::grow_amortized` (扩容策略)
3. `HashMap::insert` → `HashMap::find` (核心逻辑)
4. `Group::match_byte` (SIMD 探测)
5. `SipHasher::write` (哈希算法)
