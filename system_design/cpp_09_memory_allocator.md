# 内存分配器实现：从 malloc 替代到定制分配器

## 1. 分配器设计基础

### 1.1 为什么需要自定义分配器

| 场景 | malloc 的缺点 | 定制方案 |
|------|--------------|----------|
| 高频小对象分配 | 大块头管理开销 > 对象本身 | slab/桶分配器 |
| 实时系统 | 不确定延迟 | 固定时间分配器 |
| 游戏引擎 | 每帧大量分配释放 | 栈/池分配器 |
| 嵌入式 | 内存有限+碎片 | 定点分配器 |

### 1.2 分配器的核心接口

```c
typedef struct Allocator {
    void* (*alloc)(struct Allocator* self, size_t size);
    void  (*free)(struct Allocator* self, void* ptr);
    void* (*realloc)(struct Allocator* self, void* ptr, size_t new_size);
} Allocator;
```

### 1.3 内存布局概念

```
Heap:
┌─────┬─────────────────────────────────────┐
│元数据│             可用内存                  │
└─────┴─────────────────────────────────────┘

分配块：
┌──────┬────────────────────┬──────┐
│头部(8-16b)│    用户数据       │尾部(可选)│
└──────┴────────────────────┴──────┘
  └─ size + flags          └─ 对齐填充
```

---

## 2. 分配器类型

### 2.1 线性分配器（Bump Allocator）

最简单的分配器：只维护一个"下一个可用位置"的指针。

```c
typedef struct {
    char* start;
    char* current;
    size_t capacity;
} BumpAllocator;

void* bump_alloc(BumpAllocator* a, size_t size) {
    // 对齐到 16 字节
    size_t aligned = (size + 15) & ~15;
    if (a->current + aligned > a->start + a->capacity)
        return NULL;  // OOM
    void* ptr = a->current;
    a->current += aligned;
    return ptr;
}

void bump_reset(BumpAllocator* a) {
    a->current = a->start;  // 一次性释放全部
}
```

**特点：**
- O(1) 分配，无释放开销
- 适合帧分配器、临时缓冲区
- 不能单独释放个体对象

### 2.2 栈分配器（Stack/Frame Allocator）

维护标记点，支持回滚：

```c
typedef struct {
    char* start;
    char* current;
    size_t capacity;
} StackAllocator;

// 标记当前帧
size_t stack_mark(StackAllocator* s) {
    return (size_t)(s->current - s->start);
}

// 回滚到标记点
void stack_rewind(StackAllocator* s, size_t mark) {
    s->current = s->start + mark;
}
```

### 2.3 池分配器（Pool Allocator）

预分配固定大小元素数组，用空闲链表管理：

```c
typedef struct Node {
    union {
        Node* next;  // 空闲时
        char data[]; // 分配后
    };
} Node;

typedef struct {
    size_t      element_size;
    size_t      element_count;
    Node*       free_list;      // 空闲链表头
    Node*       pool;           // 预分配的块
} PoolAllocator;

void pool_init(PoolAllocator* p, size_t elem_size, size_t count) {
    p->element_size = max(elem_size, sizeof(Node*));  // 至少容纳指针
    p->pool = malloc(p->element_size * count);
    p->free_list = NULL;
    // 初始化空闲链表
    for (size_t i = 0; i < count; i++) {
        Node* node = (Node*)((char*)p->pool + i * p->element_size);
        node->next = p->free_list;
        p->free_list = node;
    }
}

void* pool_alloc(PoolAllocator* p) {
    if (!p->free_list) return NULL;  // 耗尽
    void* ptr = p->free_list;
    p->free_list = p->free_list->next;
    return ptr;
}

void pool_free(PoolAllocator* p, void* ptr) {
    Node* node = (Node*)ptr;
    node->next = p->free_list;
    p->free_list = node;
}
```

**特点：**
- O(1) 分配和释放
- 无碎片（固定大小）
- 适用于：分配相同大小的对象（节点、MUtex、任务等）

### 2.4 Slab 分配器

Linux 内核中的经典设计，支持多种大小：

```
Slab 结构：
┌─────────────┬─────┬─────┬─────┬─────┐
│ Slab 头部     │obj0│obj1│obj2│obj3│...
│(kmem_cache) │     │     │     │     │
└─────────────┴─────┴─────┴─────┴─────┘

管理层级：
kmem_cache → 多个 slab → slab 内固定大小对象
    │
    └─ 部分满 → 全满 → 全空（可回收）
```

每个 cache 管理一种大小（如 32B、64B、128B、256B...），内部维护三个链表：
- **partial**：部分使用的 slab
- **full**：全满的 slab
- **empty**：全空的 slab（可释放回系统）

### 2.5 伙伴系统（Buddy System）

将内存分割为 2 的幂次大小的块。分配时递归分割，释放时合并回兄弟块。

```
Order 3 (32KB):    [               ]
                  /                \
Order 2 (16KB): [       ]       [       ]
               /   \           /   \
Order 1 (8KB): [  ] [  ]     [  ] [  ]
```

**特点：**
- 分配/释放都是 O(log n)
- 外部碎片少（对齐到 2 的幂）
- 内部碎片有（分配 10KB 实际拿到 16KB）

---

## 3. 实现一个完整的通用分配器

### 3.1 核心策略：size-class + freelist

```
分配策略：
- <= 64 字节：pool allocator (32B/64B)
- <= 1KB：slab allocator (128B/256B/512B/1KB)
- > 1KB：buddy system
- > 64KB：直接 mmap

释放策略：
- pool/slab 对象：简单放回空闲链表
- buddy 块：尝试合并兄弟
- mmap：munmap 返回系统
```

### 3.2 线程局部缓存（Tcache）

每个线程维护一个小型对象缓存，减少锁竞争：

```c
typedef struct {
    void* cache[TCACHE_BATCH];  // 线程局部空闲列表
    int   count;
} ThreadCache;

static __thread ThreadCache tcache;

void* tcache_alloc(size_t size) {
    int idx = size_to_idx(size);
    if (idx < TCACHE_CLASSES && tcache[idx].count > 0)
        return tcache[idx].cache[--tcache[idx].count];
    // 缓存未命中，从中心分配器取一批
    return central_alloc_batch(idx, TCACHE_BATCH);
}

void tcache_free(void* ptr, size_t size) {
    int idx = size_to_idx(size);
    if (idx < TCACHE_CLASSES && tcache[idx].count < TCACHE_BATCH)
        tcache[idx].cache[tcache[idx].count++] = ptr;
    else
        central_free(ptr, size);  // 超限则返回中心
}
```

参考实现：
- **glibc malloc**：使用 arena + tcache + fastbins
- **jemalloc**：arenas + tcache + size-classes
- **tcmalloc**：线程缓存 + 页堆

---

## 4. 优化技巧

### 4.1 对齐保证

```c
// 保证所有分配至少 16 字节对齐
#define ALIGNMENT 16
#define ALIGN(size) (((size) + ALIGNMENT - 1) & ~(ALIGNMENT - 1))
```

### 4.2 内联元数据

将大小信息存储在分配指针的前面（glibc/chunk 风格）：

```
[prev_size][size|flags][user data...]
                                    ↑
                                    ptr 返回给用户
```

这样 `free(ptr)` 时只需 `size = *(size_t*)(ptr - 8)`。

### 4.3 延迟合并

释放相邻空闲块时不清除合并，而是放到"回收站"：
- 下次分配查找时再合并
- 减少碎片，避免 O(n) 合并开销

### 4.4 内存预取

在分配/释放时使用 `__builtin_prefetch` 提前加载下一个 free_list 节点到缓存。

---

## 5. 性能对比

| 分配器 | 小对象分配 | 大对象分配 | 多线程 | 碎片控制 |
|--------|-----------|-----------|--------|---------|
| glibc malloc | 好 (tcache) | 好 (mmap) | 好 | 一般 |
| jemalloc | 极好 | 好 | 极好 | 极好 |
| tcmalloc | 极好 | 好 | 极好 | 好 |
| 简单 pool | 极快 O(1) | 不支持 | 差 | 无碎片 |
| 线性分配 | 最快 | 快 | 好 | 无释放 |
| 伙伴系统 | 慢 | 好 | 中等 | 好 |

### 选择题：何时用什么？

| 需求 | 推荐 |
|------|------|
| 每帧分配释放大量临时对象 | 线性/栈分配器 |
| 消息/数据包（固定大小） | 池分配器 |
| 通用服务器 | jemalloc / tcmalloc |
| 实时音频 | 预分配的 ring-buffer |
| KV 存储 | slab + 伙伴系统混合 |
