# HPC Lesson 3: Memory Optimization — 缓存友好、NUMA、伪共享、内存对齐

## 概述

现代 CPU 的计算能力远超内存带宽。"Memory wall" 是 HPC 的头号瓶颈。对于量化引擎，关键问题不是 CPU 不够快，而是数据喂不进去。

## 缓存友好 (Cache-Friendly)

### 空间局部性 (Spatial Locality)
一次加载 64 字节 cache line，尽量用完每一个字节。

```c
// AoS vs SoA — 最重要的数据布局决策

// ❌ AoS (Array of Structs) — 遍历字段时浪费带宽
struct Tick { float price; float volume; int flags; };
struct Tick ticks[1000000];
for (int i = 0; i < N; i++)
    sum += ticks[i].volume;  // 加载64B只用了4B

// ✅ SoA (Struct of Arrays) — 同类数据连续存放
struct Ticks {
    float *price;
    float *volume;
    int   *flags;
};
for (int i = 0; i < N; i++)
    sum += volume[i];  // 连续访问，预取器友好
```

### 时间局部性 (Temporal Locality)
重复访问的数据尽量小，避免被逐出 L1。

```c
// ❌ 频繁回扫大数组，颠簸缓存
for (int iter = 0; iter < 100; iter++)
    for (int i = 0; i < 1000000; i++)
        data[i] = process(data[i]);  // 每次都从内存加载

// ✅ 分块处理
for (int b = 0; b < N; b += BLOCK) {
    int end = min(b + BLOCK, N);
    for (int iter = 0; iter < 100; iter++)
        for (int i = b; i < end; i++)
            data[i] = process(data[i]);
}
```

## NUMA (Non-Uniform Memory Access)

多路服务器中，每个 socket 有自己的内存控制器。

```mermaid
Socket 0          Socket 1
┌────────┐       ┌────────┐
│ Core0-7│ ←→    │ Core8-15│
│ L3 16MB│       │ L3 16MB│
└───┬────┘       └───┬────┘
    │ DDR4            │ DDR4
```

- 访问本地内存: ~100ns
- 访问远端内存: ~150ns (跨 QPI/UPI 链路)

**量化建议**: 多线程量化系统绑定数据到线程所在 socket。
```c
// Windows: 设置线程亲和性 + NUMA 节点绑定
SetThreadAffinityMask(thread, 1ULL << core_id);
// 或直接用 NUMA API分配内存：
// VirtualAllocExNuma
```

Windows 11 通常单 socket（用户桌面场景），NUMA 影响较小但了解即可。

## 伪共享 (False Sharing)

多个线程修改同一 cache line 上的不同变量 → 硬件缓存一致性协议强制同步。

```c
// ❌ 伪共享：两个值为同一个 cache line
struct alignas(64) CounterPair {
    int64_t a;  // 线程1更新
    int64_t b;  // 线程2更新
    // 总16B，仍在64B cache line内
};
// 每次 a 更新 → 线程2的 b 所在 cache line 无效化 → 性能暴跌

// ✅ 使用 cache line padding
struct CounterPair {
    int64_t a;
    char pad[56];  // 填充到64B
    int64_t b;
    char pad2[56];
};
// 或 C++17 方法：
struct alignas(64) Counter { int64_t val; };
Counter counters[2];  // 每个 counter 独占 cache line
```

### Windows/MSVC 等效写法
```cpp
__declspec(align(64)) struct Counter { int64_t val; };
// 或 C++11:
struct alignas(64) Counter { int64_t val; };
```

## 内存对齐 (Alignment)

### 为什么对齐？

- **SSE 需要 16B** 对齐 (`_mm_load_ps`)
- **AVX 需要 32B** 对齐 (`_mm256_load_ps`) — _mm256_loadu_ps 不做要求
- **Cache Line 64B** 对齐可避免跨行加载

```c
// 栈对齐
alignas(32) float buffer[1024];

// 堆对齐 (C++17)
float *buf = new (std::align_val_t(32)) float[1024];
delete[] buf;

// 堆对齐 (C)
float *buf = _aligned_malloc(1024 * sizeof(float), 32);
_aligned_free(buf);

// 或 posix_memalign (Linux)
```

### Struct 布局与 padding

```c
// 编译器自动填充
struct Bad {
    char c;   // 1B
    int i;    // 4B → padding 3B
    short s;  // 2B → padding 2B 对齐到 8B
};  // 总 12B → 实际 sizeof = 12

// 按大小降序排列减少 padding
struct Good {
    int i;    // 4B
    short s;  // 2B
    char c;   // 1B
    char _pad; // 1B
};  // sizeof = 8，节省 33%
```

## 量化场景汇总

| 技术 | 应用 |
|------|------|
| SoA 布局 | OHLCV 多个数组替代 struct 数组 |
| Cache line padding | 多线程统计计数器、订单簿 level |
| 对齐分配 | SIMD 处理的价格序列 |
| 分块处理 | 日度数据回放、因子计算 |
| 预取指令 | `_mm_prefetch` (软件预取) |
