# 性能优化 #1：CPU 管线与缓存层次

> 2026-05-17
> 前置：计算机组成（基础，已有）

## 1. CPU 的真相

### 1.1 CPU 实际比看起来慢很多

```
理想：3GHz CPU = 0.33ns 一条指令
现实：大部分时间 CPU 在 等数据
  L1 命中     → 1ns（4 个周期）
  L2 命中     → 4ns（12-16 个周期）
  L3 命中     → 15ns（40-50 个周期）
  RAM 命中    → 50-100ns（150-300 个周期）
  SSD 读取    → 10-100μs
  网络延迟    → 1-100ms

结论：一条 RAM 随机访问 ≈ 300 条指令的等待时间
      优化内存访问模式 ≈ 优化性能的核心
```

### 1.2 缓存层次

```
CPU Core 0          CPU Core 1
┌──────────┐        ┌──────────┐
│  L1d (32KB)       │  L1d (32KB)
│  L1i (32KB)       │  L1i (32KB)
│  L2  (256KB)      │  L2  (256KB)
└──────┬───┘        └──────┬───┘
       │                    │
       └────────┬───────────┘
                │
          L3 (8-32MB) ← 所有核心共享
                │
          ┌─────┴─────┐
          │   RAM      │
          └───────────┘
```

- L1: 32KB 指令 + 32KB 数据，每核私有
- L2: 256KB-512KB，每核私有
- L3: 8-32MB，所有核心共享

## 2. 缓存行（Cache Line）

### 2.1 对齐

缓存以 64 字节的缓存行（Cache Line）为单位载入：

```c
// ❌ 缓存行颠簸
struct Bad {
    int a;          // 4 bytes
    // padding
    int b;          // 4 bytes (可能和其他数据共享一个缓存行)
};

// 两个不相关的数据在同一缓存行 → 多核写时会互相 invalidate

// ✅ 缓存行对齐
struct alignas(64) Good {
    int a;          // 第一个缓存行
    int padding[15]; // 填满 64 字节
    int b;          // 第二个缓存行
};
```

多核场景下**防止假共享（False Sharing）**：两个核心各自写互不相干的变量，但这俩变量恰好在一个缓存行里——每次写都会 invalidate 对方。

### 2.2 预取

CPU 会自动预取顺序访问的数据：

```c
// ✅ 顺序访问 → 硬件预取命中
for (int i = 0; i < N; i++) sum += arr[i];  // 预测模式：连续地址

// ❌ 随机访问 → 预取无效
for (int i = 0; i < N; i++) sum += arr[rand() % N];  // 无法预测
```

可以手动预取（但现代硬件预取已经非常强，手动很少需要）：

```c
// 手动预取（极少真正需要）
for (int i = 0; i < N; i++) {
    __builtin_prefetch(&arr[i + 16], 0, 3);  // 预取 arr[i+16]
    sum += arr[i];
}
```

## 3. 指令级并行（ILP）

### 3.1 超标量执行

现代 CPU 一个时钟周期可以发射 3-6 条指令（流水线深度 14-20 级）：

```
一条指令的流水线：
取指 → 译码 → 寄存器重命名 → 发射 → 执行 → 写回

多指令同时执行：
      Cycle 1  2  3  4  5  6  7  8
Inst1: |F| |D| |R| |E| |W|          ADD r1, r2, r3
Inst2:     |F| |D| |R| |E| |W|      SUB r4, r5, r6
Inst3:         |F| |D| |R| |E| |W|  XOR r7, r8, r9
```

**关键限制**——依赖链：指令 2 如果依赖指令 1 的结果，就不能并行发射。

### 3.2 消除依赖链延迟

```c
// ❌ 长依赖链
double sum = 0;
for (int i = 0; i < N; i++) {
    sum += arr[i];  // 每次迭代需要上次的 sum（串行）
}

// ✅ 展开循环 + 独立累加器
double sum0 = 0, sum1 = 0, sum2 = 0, sum3 = 0;
for (int i = 0; i < N; i += 4) {
    sum0 += arr[i];
    sum1 += arr[i+1];
    sum2 += arr[i+2];
    sum3 += arr[i+3];
}
double sum = sum0 + sum1 + sum2 + sum3;
```

4 个独立累加器 → CPU 可以同时执行 4 条加法（无依赖阻塞）。

### 3.3 分支预测

```c
// ❌ 不可预测的分支
for (int i = 0; i < N; i++) {
    if (data[i] > threshold) {   // threshold 导致 50% 概率
        sum += data[i];          // 分支预测错误 50%
    }
}

// ✅ 可预测的分支
for (int i = 0; i < N; i++) {
    if (i > N/2) {               // 单调模式：前 N/2 不成立，后 N/2 成立
        sum += data[i];          // 分支预测正确率 ~100%
    }
}

// 分支预测错误代价：清空流水线（~15-20 个周期）
// 无分支优化：
for (int i = 0; i < N; i++) {
    sum += (data[i] > threshold) ? data[i] : 0;  // 编译器可能用 CMOV
}
```

## 4. 向量化指令

### 4.1 什么是 SIMD

```
标量（SISD）：一条指令处理一个数据
  ADD r1, r2        # r1 = r1 + r2

向量（SIMD）：一条指令处理多个数据（SSE/AVX）
  ADDPS xmm0, xmm1  # xmm0[0..3] += xmm1[0..3] (4个float)
  VADDPD ymm0,ymm1  # ymm0[0..3] += ymm1[0..3] (4个double, AVX)
  VMULPS zmm0,zmm1  # zmm0[0..15] += zmm1[0..15] (16个float, AVX-512)
```

### 4.2 自动向量化

编译器在 O2/O3 下自动尝试：

```c
// 编译器可以向量化
void add_arrays(const float* a, const float* b, float* out, int n) {
    for (int i = 0; i < n; i++) {
        out[i] = a[i] + b[i];  // 连续内存 → 自动 SIMD
    }
}

// 编译器不能向量化
void add_wrong(float** a, float** b, float* out, int n) {
    for (int i = 0; i < n; i++) {
        out[i] = (*a)[i] + (*b)[i];  // 指针别名（可能重叠）
    }
}
```

`__restrict__` 关键字告诉编译器指针不重叠：

```c
void add_restrict(float* __restrict__ a, float* __restrict__ b,
                  float* __restrict__ out, int n) {
    for (int i = 0; i < n; i++) {
        out[i] = a[i] + b[i];  // 无别名，编译器放心向量化
    }
}
```

### 4.3 手动 SIMD（Rust）

```rust
use std::simd::*;

fn add_simd(a: &[f64], b: &[f64]) -> Vec<f64> {
    let n = a.len();
    let mut out = Vec::with_capacity(n);
    let chunks = n / f64x4::LEN;
    
    for i in 0..chunks {
        let offset = i * f64x4::LEN;
        // 一次加载 4 个 double
        let va = f64x4::from_slice(&a[offset..]);
        let vb = f64x4::from_slice(&b[offset..]);
        // 一次完成 4 个加法
        let vc = va + vb;
        // 一次存储 4 个结果
        out.extend_from_slice(&vc.to_array());
    }
    // 处理剩余的
    for i in (chunks * f64x4::LEN)..n {
        out.push(a[i] + b[i]);
    }
    out
}
```

## 5. 核心量化场景的 CPU 瓶颈

在我们的量化系统中可预见的瓶颈：

```
计算模式          CPU 瓶颈              优化方向
────────────────────────────────────────
K 线计算         内存带宽（数据量大）    数据局部性、AOS→SOA
策略评分         分支预测（条件多）      无分支编程、查询表
回测 10 年行情   流水线吞吐量            循环展开、SIMD
RL 训练         向量运算（GPU 更好）     GPU/Intel MKL
布林带计算       浮点吞吐量              自动向量化、restrict

瓶颈主要集中在 内存访问模式 和 分支预测
```

## 总结

```
CPU 快的假象→ 真正瓶颈是数据到达速度
缓存层次  → L1(1ns) < L2(4ns) < L3(15ns) << RAM(100ns)
缓存行     → 64 字节对齐，防假共享
ILP        → 减少依赖链，多累加器展开
分支预测   → 可预测模式 > 不可预测模式
SIMD       → 自动向量化（编译器）+ 手动（Rust std::simd）
```
