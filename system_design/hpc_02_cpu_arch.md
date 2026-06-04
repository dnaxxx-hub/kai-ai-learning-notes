# HPC Lesson 2: CPU Architecture — 流水线、乱序执行、分支预测与缓存

## 概述

理解 CPU 微架构是写出高性能代码的前提。量化引擎对延迟极度敏感，一个分支预测失败、一次缓存缺失可能意味着错过一个 tick。

## 指令流水线 (Pipeline)

经典 5 级流水线：**IF → ID → EX → MEM → WB**

现代 CPU (如 Intel Golden Cove / AMD Zen 4) 有 **14-19 级** 流水线：
- 更深流水线 → 更高频率 ↔ 但分支预测失败代价更大（>15 cycles）
- 超标量 (Superscalar)：每周期发射多条指令（一般为 4-6 条）

```
周期:  1   2   3   4   5   6   7
Insn1: IF  ID  EX  MEM WB
Insn2:     IF  ID  EX  MEM WB
Insn3:         IF  ID  EX  MEM WB
```

## 乱序执行 (Out-of-Order, OoO)

关键组件：
- **ROB** (Reorder Buffer): 保留站结果暂存，按原始顺序提交
- **RS** (Reservation Station): 等待操作数就绪的指令池
- **Register Renaming**: 消除 WAW/WAR 假依赖

```
程 序 写: R1=load(A) → R2=R1+1 → R1=load(B) → R3=R1+2
物理执行: [R1]=load(A)
           [R2]=[R1]+1
           [R1']=load(B)   ← 寄存器重命名，新物理寄存器
           [R3]=[R1']+2    ← 不等待前两条完成
```

**量化启示**: 核心循环中减少长延迟依赖链（如除法、sqrt），用 FMA 链替代。

## 分支预测 (Branch Prediction)

### 预测器类型
- **BTB** (Branch Target Buffer): 预测跳转目标地址
- **TAGE**: 当前最先进的预测器（基于标签+几何历史）
- **LVP** (Loop Predictor): 循环跳出判定

### 代价
| 事件 | 周期损失 |
|------|---------|
| 正确预测 | 0 |
| 预测失败 | ~15-20 cycles |
| 缓存缺失 | ~100-300 cycles |

### 代码优化

```c
// ❌ 分支密集型 (predictor 容易失败)
for (int i = 0; i < n; i++) {
    if (prices[i] > threshold) count++;
}

// ✅ 分支预测友好: 使用条件移动 (CMOV) 或无分支实现
for (int i = 0; i < n; i++) {
    count += (prices[i] > threshold) ? 1 : 0;
    // 编译器可能生成 cmov
}

// 或更激进的: 用 AVX 比较 + mask 代替分支
__m256 cmp = _mm256_cmp_ps(vprices, vthresh, _CMP_GT_OQ);
int mask = _mm256_movemask_ps(cmp);
count += __builtin_popcount(mask);  // popcount 硬件指令
```

### Likely/Unlikely 提示
```c
// C++20 标准属性
if (likely(check_valid(data))) { ... }
if (unlikely(error_occurred())) { ... }
```

## 缓存层级 (Cache Hierarchy)

以 Intel Golden Cove (13代) 为例：

| 层级 | 大小 | 延迟 | 关联度 |
|------|------|------|--------|
| L1d  | 48 KB | 3-5 cycles | 12-way |
| L1i  | 32 KB | — | 8-way |
| L2   | 2 MB 共享 | ~12 cycles | 16-way |
| L3   | 36 MB 跨核 | ~35-50 cycles | 20-way |
| DRAM | — | ~100-300 cycles | — |

### 关键概念
- **Cache Line**: 64 字节（Intel），一次加载的最小单位
- **Prefetch**: 硬件预取器自动检测模式
- **TLB** (Translation Lookaside Buffer): 页面地址缓存

### 缓存友好代码
```c
// ❌ 跨步访问 (缓存行未充分使用)
for (int j = 0; j < N; j++)
    for (int i = 0; i < N; i++)
        sum += matrix[j * N + i];  // 行优先 → OK
        // sum += matrix[i * N + j];  // ❌ 列优先 → 每步跨 N*4 字节

// ✅ 分块 (Tiling) 提高局部性
for (int ii = 0; ii < N; ii += BLOCK)
    for (int jj = 0; jj < N; jj += BLOCK)
        for (int i = ii; i < ii+BLOCK; i++)
            for (int j = jj; j < jj+BLOCK; j++)
                sum += matrix[i * N + j];
```

## 量化相关性

| CPU 特性 | 量化场景影响 |
|----------|-------------|
| 分支预测失败 | tick 过滤、信号逻辑、if-else 过多的策略 |
| 缓存缺失 | 大内存数据扫描、历史数据回放 |
| 乱序执行 | pipeline 中长延迟指令的隐藏 |
| 超线程 (SMT) | 每核 2 线程共享 L1/L2，吞吐↑但延迟↑ |

## 工具检测

```bash
# Windows
wmic cpu get Name, MaxClockSpeed, L2CacheSize, L3CacheSize

# 或通过代码
cpuid 指令读取 CPUID.04H
```
