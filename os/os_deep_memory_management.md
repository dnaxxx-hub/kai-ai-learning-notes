# OS 内存管理深度解析 (Deep Dive into OS Memory Management)

> 面向 OS 课程 12 课时重点，兼顾理论深度与工程实践，对标 Linux 内核真实实现。

---

## 目录

1. [虚拟内存与分页机制](#1-虚拟内存与分页机制)
2. [物理内存管理](#2-物理内存管理)
3. [用户态内存分配器](#3-用户态内存分配器)
4. [页面置换算法](#4-页面置换算法)
5. [mmap 与共享内存](#5-mmap-与共享内存)
6. [大页与 CMA](#6-大页与-cma)
7. [实战对照：Linux 内核](#7-实战对照linux-内核)

---

## 1. 虚拟内存与分页机制

### 1.1 为什么需要虚拟内存？

**虚拟内存（Virtual Memory）** 是现代操作系统的基石。它解决三个核心问题：

| 问题 | 解决方案 |
|------|----------|
| **进程隔离**：进程 A 不能访问进程 B 的内存 | 每个进程拥有独立的虚拟地址空间 |
| **碎片化**：物理内存分散无法容纳大连续块 | 分页机制将不连续的物理页映射为连续的虚拟地址 |
| **内存超载**：物理内存不够用 | 页面置换 + 磁盘交换（swap） |

**关键公式**：`虚拟地址 → (MMU + 页表) → 物理地址`

### 1.2 多级页表 (Multi-Level Page Table)

x86-64 架构使用 **4 级页表**，层级为：

```
Virtual Address (48 bits)
┌────────┬────────┬────────┬────────┬────────────┐
│  PML4  │  PDPT  │   PD   │   PT   │   Offset   │
│  (9b)  │  (9b)  │  (9b)  │  (9b)  │   (12b)    │
└────────┴────────┴────────┴────────┴────────────┘
```

- **页大小**：4 KB（12-bit offset → 2^12 = 4096 bytes）
- **每级表**：512 项（9-bit index → 2^9 = 512）
- **每项**：8 bytes → 每张页表 4 KB（恰好一页）

**为什么用多级而不是单级？**
- 单级页表需要 2^48 / 2^12 × 8 = 512 GB 页表空间
- 4 级页表：仅分配实际使用的级，大部分 PML4 项为空，**按需分配**，进程通常只占几 MB 页表

**Linux 内核抽象**：`struct page` 描述每个物理页，`struct mm_struct` 管理进程地址空间。

### 1.3 TLB (Translation Lookaside Buffer)

TLB 是 CPU 内部的 **页表缓存**（硬件），存储最近使用的虚拟-物理地址映射。

- **TLB Miss**：需要遍历页表（硬件遍历或软件装载）
- **TLB Flush**：进程切换（context switch）时，不同进程的虚拟地址空间不同，需要冲刷 TLB
- **大页（Huge Pages）**：使用 2 MB 或 1 GB 大页，同样的 TLB 项数可覆盖更大内存，显著降低 TLB miss

### 1.4 缺页异常 (Page Fault)

当 CPU 访问的虚拟地址在页表中未找到有效映射时触发缺页异常，Linux 缺页异常处理流程：

```
1. CPU 触发 #PF (Page Fault) 异常
2. 保存 faulting address (CR2 寄存器)
3. 检查 vma (Virtual Memory Area) 是否有效
   ├─ 无效 → SIGSEGV (段错误)
   └─ 有效 → 继续
4. 检查页表项是否存在
   ├─ 不存在 → 分配物理页 → 读取磁盘/swap → 更新页表
   └─ 存在但权限不足 → SIGSEGV
5. 返回用户态重新执行指令
```

**关键数据结构**：`struct vm_area_struct` (VMA) 描述进程地址空间中的一个连续区间（如堆、栈、mmap 区域）。

### 1.5 写时复制 (Copy-on-Write, COW)

`fork()` 创建子进程时，并不复制全部物理内存，而是：

1. 父子进程共享所有物理页，页表标记为**只读**
2. 任一进程尝试写入 → 触发写保护缺页
3. 内核复制该物理页，分别映射到父子进程
4. 父子各持一份，均标记为可写

**好处**：`fork()` 后立即 `exec()` 的场景（典型 shell），节省大量拷贝。

---

## 2. 物理内存管理

### 2.1 伙伴系统 (Buddy System)

Linux 物理内存分配的核心算法。它将空闲页按 **2 的幂次** 组织成链表数组。

**核心思想**：

```
order 0: [4K] [4K] [4K] [4K] [4K] ...
order 1: [8K     ] [8K     ] ...
order 2: [16K          ] ...
...
order 10: [4M                      ]
```

- **分配**：请求 order n → 从 free_list[n] 取一个块 → 若为空则从 n+1 分裂为两个（buddy）
- **释放**：释放后检查 buddy 是否也为空闲 → 合并回 order n+1（递归合并）

**优点**：快速合并、外部碎片少（但内部碎片存在，因为只能分配 2^n 大小）
**Linux 实现**：`mm/page_alloc.c` 中的 `__alloc_pages_nodemask()`，每个 NUMA node 维护自己的 buddy system。

### 2.2 slab/slub 分配器

slab 分配器用于管理**内核对象**（如 `task_struct`、`inode`），这些对象通常都是固定大小且频繁分配释放。

**设计三层结构**：
```
cache (例如: kmalloc-256)
  ├── slab (一个或多个物理页)
  │    ├── object (256 bytes)
  │    ├── object (256 bytes)
  │    ├── ...
  │    └── free list 头
  └── slab (满/部分/空闲)
```

- **cache**：管理一类固定大小对象
- **slab**：一组连续物理页，划分为等大小对象
- **着色（coloring）**：不同 slab 的起始偏移略作调整，改善缓存行利用

**Linux 演进**：slab → slob（嵌入式）→ **slub**（默认），slub 简化了 slab 的元数据管理，适合大型系统。

### 2.3 内存碎片 (Memory Fragmentation)

| 类型 | 定义 | 举例 |
|------|------|------|
| **外部碎片** | 空闲内存不连续，无法满足大块连续分配 | 总空闲 100 MB，但最大连续块 10 MB |
| **内部碎片** | 分配块大于实际需要，块内浪费 | 分配 4 KB 页但只用了 100 bytes |

**缓解手段**：
- 伙伴系统 → 合并相邻块，减少外部碎片
- slab → 固定大小对象零内部碎片
- 内存压缩（compaction）→ 移动已用页，制造大块连续区
- THP (Transparent Huge Pages) → 自动将连续 4K 页合并为 2M 大页

---

## 3. 用户态内存分配器

### 3.1 brk/sbrk vs mmap

用户态程序获得内存的两个系统调用：

| 函数 | 行为 | 特点 |
|------|------|------|
| `sbrk(incr)` | 移动 program break（堆顶） | 线性增长，适合小对象 |
| `brk(addr)` | 设置 program break 到指定位置 | 与 sbrk 本质相同 |
| `mmap(NULL, len, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)` | 在 mmap 区域映射匿名页 | 可独立释放，适合大块 |

**典型分配阈值**：`M_MMAP_THRESHOLD`（默认 128 KB）
- 小块（<128 KB）→ 用 brk 扩展堆
- 大块（≥128 KB）→ 用 mmap 分配独立区域

### 3.2 ptmalloc 原理 (glibc 默认)

ptmalloc 基于 dlmalloc，核心结构：

```
arena (每个 arena 一把锁)
  ├── bins (大小分类链表)
  │    ├── fast bins (16-80 bytes, LIFO, 不合并)
  │    ├── small bins (80-512 bytes 间隔 16B)
  │    ├── large bins (>512 bytes，指数间隔)
  │    └── unsorted bin (最近释放的 chunks)
  └── top chunk (堆顶剩余空间)
```

**分配流程**：
```
malloc(n)
  ├─ n < fastbin 上限 → 检查 fast bins
  ├─ n < smallbin 上限 → 检查 small bins
  ├─ n < largebin 上限 → 检查 unsorted → 分裂放入对应 bins
  ├─ 仍未找到 → 检查 large bins
  └─ 都失败 → 扩展堆 (brk/mmap)
```

**释放与合并**：
- `free(p)` → 先放入 fastbin（不合并，更快）
- 非 fastbin 释放 → 检查相邻 chunk，合并空闲块
- 若合并后 chunk 很大 → 可能归还给 OS (`munmap` 或 `brk` 回缩)

### 3.3 jemalloc 与 tcmalloc

| 特性 | ptmalloc | jemalloc | tcmalloc |
|------|----------|----------|----------|
| 并发策略 | 主 arena + 线程缓存 | per-thread cache + per-arena | per-thread cache |
| 碎片控制 | 中等 | 优秀（尤其多线程） | 优秀 |
| 适用场景 | 通用 | 多线程、大内存 | Google 系应用 |
| 核心思想 | 边界标记 | 四层分配（tcache→small→large→huge） | 线程局部缓存 + 页级分配 |

### 3.4 malloc 实现的内存布局

```
堆起始 (start_brk)
┌──────────────┐
│   已分配块    │ ← 每个 chunk 有 header (size + flags)
├──────────────┤
│   空闲块      │
├──────────────┤
│   ...        │
├──────────────┤
│   top chunk  │ ← 堆顶，可扩展
└──────────────┘ ← 当前 brk

chunk 布局:
┌────────┬────────┬──────────────┐
│ prev_size │  size  │   data...     │
│ (8B)    │ (8B:F) │              │
└────────┴────────┴──────────────┘
size 最后 3 bit: A(arena) M(mmap) P(prev_inuse)
```

---

## 4. 页面置换算法

### 4.1 FIFO (First-In, First-Out)

- 最简单的算法，维护一个队列
- 缺页时换出最早调入的页面
- **Belady 异常**：增加物理页帧数反而增加缺页率（FIFO 独有）

### 4.2 LRU (Least Recently Used)

- 换出最长时间未使用的页面
- **最优近似**（OPT 在实际中不可实现，LRU 是最佳可实现的近似）
- 实现方式：硬件维护使用位（usage bit / reference bit），定期扫描

**近似实现**：
- **软件 LRU**（Linux）`struct page->lru` 链表，使用 active_list / inactive_list
- Linux 实际上使用的是 **LRU 近似（双链扫描）**，而非精确 LRU（成本过高）

### 4.3 Clock (二次机会算法 / Second Chance)

Clock 是 LRU 的近似实现，性能接近 LRU 但开销小很多：

```
         ┌─────┐
    ←── │  P0 │ ←──
   │    └─────┘    │
   │    ┌─────┐    │
   └─── │  P1 │ ───┘
        └─────┘
         ↻ (clock hand)
```

**算法**：
1. 指针循环扫描页面
2. 若 reference bit = 1 → 清零，继续扫描
3. 若 reference bit = 0 → 换出该页面

**变种**：Enhanced Second Chance (使用 ref bit + dirty bit，优先换出 "未使用且未修改" 的页面)

### 4.4 Linux 页面回收 (Page Reclaim)

Linux 内核使用一个**双链分析算法**：

```
active_list → 频繁访问的页面
inactive_list → 候选回收的页面
```

- 页面从 inactive 晋升到 active（ref bit 被访问）
- 页面从 active 降级到 inactive（时间老化）
- 缺页时从 inactive_list 尾部回收页面
- **kswapd** 内核线程在内存不足时后台回收

**与理论 LRU 的区别**：Linux 没有精确的访问时间戳，而是通过两个链表模拟 LRU 的 "最近使用" 语义。

---

## 5. mmap 与共享内存

### 5.1 mmap 系统调用

`mmap` 是 Linux 最核心的内存映射机制，统一了**文件 I/O** 和**内存访问**：

```c
void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
```

| 参数 | 含义 |
|------|------|
| `addr` | 建议映射地址（通常传 NULL，让内核决定）|
| `length` | 映射长度 |
| `prot` | PROT_READ / PROT_WRITE / PROT_EXEC |
| `flags` | MAP_SHARED / MAP_PRIVATE / MAP_ANONYMOUS |
| `fd` | 文件描述符（匿名映射传 -1）|
| `offset` | 文件偏移（通常 0）|

**两种模式**：

| 模式 | 写回磁盘？ | 典型的进程间通信？ | fork 行为 |
|------|-----------|-------------------|-----------|
| MAP_SHARED | 是（写穿透） | 是 | 共享同一物理页 |
| MAP_PRIVATE | 否（COW） | 否 | 写时复制 |

### 5.2 文件映射 vs 匿名映射

```
mmap 文件 → 物理页缓存（page cache）
   虚拟地址直接映射到 page cache 的物理页
   读：如同访问内存（免去 read() 的系统调用 + copy_to_user）
   写：延迟写回（由 pdflush/flusher 线程负责）

mmap 匿名 → 匿名页（swap-backed）
   glibc 的 malloc 对大块使用 mmap 匿名映射
   fork 后父子进程共享匿名页（COW）
```

### 5.3 缺页与 mmap

```
mmap 时的行为：
  1. 创建 VMA（记录映射关系），不分配物理页
  2. 首次访问：
     ├─ 匿名 mmap → 分配零填充物理页 (zero-filled-on-demand)
     └─ 文件 mmap → 从文件读取到 page cache
```

**延迟分配（Demand Paging）**：mmap 只创建 VMA，物理页在首次访问时才分配。

---

## 6. 大页与 CMA

### 6.1 HugeTLB (大页)

普通 4 KB 页的问题：TLB 覆盖范围有限（通常只有几十项），遍历大型数据结构时 TLB miss 频繁。

**解决方案**：使用 2 MB 或 1 GB 的大页。

| 页大小 | TLB 覆盖范围 (64 项) |
|--------|---------------------|
| 4 KB   | 256 KB |
| 2 MB   | 128 MB |
| 1 GB   | 64 GB |

**Linux 支持方式**：
- **显式 HugeTLB**：`mmap` 时使用 `MAP_HUGETLB` 标志，或通过 `hugetlbfs` 挂载
- **透明大页 (THP)**：自动将连续的 4K 页合并为 2M 大页，对应用透明

### 6.2 CMA (Contiguous Memory Allocator)

CMA 是 Linux 内核用于分配**大块连续物理内存**的机制，主要给 DMA 和 GPU 使用。

**工作原理**：
1. 系统启动时预留一块 CMA 区域
2. 平时这块内存可用于普通页面分配（movable page）
3. 当驱动需要大块连续内存时，将 CMA 区域中的 movable page 迁移出去
4. 回收后的连续区域分配给驱动

**关键点**：
- CMA 区域是一个内存隔离区（memory zone）的子集
- 只有标记为 `__GFP_MOVABLE` 的页面可以放在 CMA 区域
- 迁移（migration）通过内核的内存压缩（compaction）机制完成

---

## 7. 实战对照：Linux 内核

### 7.1 关键数据结构

| 数据结构 | 所在文件 | 作用 |
|----------|----------|------|
| `struct page` | `include/linux/mm_types.h` | 描述每个物理页 |
| `struct mm_struct` | `include/linux/mm_types.h` | 进程地址空间描述符 |
| `struct vm_area_struct` | `include/linux/mm_types.h` | 虚拟地址区间的描述 |
| `struct zone` | `include/linux/mmzone.h` | 内存管理区（DMA/Normal/HighMem）|
| `struct free_area` | `include/linux/mmzone.h` | buddy system 每个 order 的空闲链表 |
| `struct kmem_cache` | `include/linux/slab.h` | slab/slub 缓存描述 |

### 7.2 关键代码路径

```
malloc → glibc ptmalloc
  └─ brk()/mmap()
      └─ sys_brk / do_mmap
          └─ __alloc_pages_nodemask (buddy)
              └─ rmqueue (从 zone 提取页面)

mmap → do_mmap
  └─ get_unmapped_area (找空闲虚拟地址)
  └─ mmap_region (创建 VMA)
  └─ 首次访问 → __do_page_fault → handle_mm_fault → do_anonymous_page

fork → dup_mmap
  └─ copy_page_range (建立 COW 映射)
```

### 7.3 proc 文件系统查看

```bash
# 内存信息总览
cat /proc/meminfo

# 进程内存映射
cat /proc/<pid>/maps

# buddy system 状态
cat /proc/buddyinfo

# slab 缓存信息
cat /proc/slabinfo

# 缺页统计
cat /proc/<pid>/stat | awk '{print $10" "$12}'
```

### 7.4 性能调优相关 sysctl

```sysctl
# 页面回收倾向（0=积极回收匿名页，100=积极回收文件页）
vm.swappiness = 60

# transparent hugepages 策略：always / madvise / never
/sys/kernel/mm/transparent_hugepage/enabled

# overcommit 策略：0=启发式 1=允许 2=禁止
vm.overcommit_memory = 0
```

---

## 总结

| 层面 | 核心机制 | 关键代码参考 |
|------|---------|-------------|
| **虚拟内存** | 4 级页表 + TLB + 缺页 | `mm/memory.c`, `arch/x86/mm/fault.c` |
| **物理内存** | Buddy System + slab/slub | `mm/page_alloc.c`, `mm/slub.c` |
| **用户态分配** | ptmalloc (brk + mmap) | glibc `malloc/malloc.c` |
| **页面置换** | 双链分析 (active/inactive) | `mm/vmscan.c` |
| **大页** | HugeTLB + THP | `mm/hugetlb.c`, `mm/huge_memory.c` |

> 理解 OS 内存管理，关键在于建立 "三级视角"：
> - **硬件**：MMU + TLB + 多级页表的寻址细节
> - **内核**：VMA + page + zone + buddy/slab 的数据结构设计
> - **用户态**：malloc 分配器的工程实现
>
> 三者协同，构成了现代操作系统高效、安全、可移植的内存管理栈。
