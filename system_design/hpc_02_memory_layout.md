# 性能优化 #2：内存布局与数据访问模式

> 2026-05-17
> 前置：CPU 管线与缓存 #1

## 1. 局部性的力量

### 1.1 空间局部性 vs 时间局部性

```
空间局部性：访问了一个地址 → 附近的地址也马上会被访问
时间局部性：访问了一个地址 → 这个地址很快会再次被访问
```

对性能影响最大的不是算法复杂度，而是数据结构在内存中的布局。

### 1.2 SoA vs AoS

两种基本的数据组织方式：

```c
// AoS（Array of Structs） → ❌ 对 SIMD / 缓存不友好
struct Particle {
    float x, y, z;    // 位置
    float vx, vy, vz; // 速度
    float mass;       // 质量
};
Particle particles[N];

// AoS 内存布局：
// x0 y0 z0 vx0 vy0 vz0 mass0  x1 y1 z1 vx1 vy1 vz1 mass1  ...
//                            ^ 跨距 7 个 float

// 当只需要 x 坐标时：读 7 个 float 只用了 1 个（浪费 6/7 的缓存带宽）
```

```c
// SoA（Struct of Arrays） → ✅ 缓存/SIMD 友好
struct Particles {
    float x[N], y[N], z[N];
    float vx[N], vy[N], vz[N];
    float mass[N];
};

// SoA 内存布局：
// x0 x1 x2 ...  y0 y1 y2 ...  z0 z1 z2 ...  连续存储同字段
// 当只需要 x 坐标时：连续读 N 个 float，满缓存带宽利用
```

### 1.3 量化引擎中的 SoA

当前策略引擎的 K 线数据应该用 SoA 而非 AoS：

```python
# ❌ AoS（每根 K 线一个 dict/class）
class Bar:
    def __init__(self, o, h, l, c, v):
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.volume = v

bars = [Bar(o,h,l,c,v) for ...]
# 计算 SMA: 每次随机访问 bars[i].close → 缓存不友好

# ✅ SoA（每个字段一个连续数组）
class Bars:
    def __init__(self, n):
        self.open = np.zeros(n)    # 连续内存
        self.high = np.zeros(n)
        self.low = np.zeros(n)
        self.close = np.zeros(n)
        self.volume = np.zeros(n)

# 计算 SMA: bars.close[0:20].mean() → 连续读取 → 缓存友好
```

**NumPy 本身就是 SoA**——每个列（如 close）在底层是一个连续数组。

## 2. 预分配与内存池

### 2.1 动态分配的开销

```c
// ❌ 每次迭代分配新内存
for (int i = 0; i < N; i++) {
    double* temp = malloc(1024 * sizeof(double));
    process(temp);
    free(temp);
}
// malloc/free 每次 ≈ 0.5-2μs → N=100万 时 1-2 秒浪费

// ✅ 预分配 + 复用
double* temp = malloc(1024 * sizeof(double));
for (int i = 0; i < N; i++) {
    process(temp);
}
free(temp);
// 零分配开销
```

Python 中的影响更大——每次 list append、dict 插入都可能触发 resize + 复制。

### 2.2 内存池模式

```python
# 量化引擎中的内存池模式
class SignalBuffer:
    """固定大小的环形缓冲区，预分配不重新分配"""
    def __init__(self, capacity: int):
        self.data = [0.0] * capacity  # 一次分配
        self.head = 0
        self.count = 0

    def push(self, value: float):
        self.data[self.head] = value
        self.head = (self.head + 1) % len(self.data)
        self.count = min(self.count + 1, len(self.data))

    def last_n(self, n: int) -> list:
        # 返回最近 n 个值（连续内存），无分配
        start = (self.head - n) % len(self.data)
        if start + n <= len(self.data):
            return self.data[start:start+n]
        return self.data[start:] + self.data[:self.head]
```

## 3. 数据驱动的设计和分支消除

### 3.1 遍历顺序

```c
// ❌ 优先 C（按行遍历）
// 内存布局: [0,0][0,1]...[0,999][1,0][1,1]...
// 按列读取时跳着走 → 缓存未命中率 100%
for (int j = 0; j < 1000; j++) {
    for (int i = 0; i < 1000; i++) {
        sum += matrix[i][j];  // 行索引在外层，列索引在内层
    }
}

// ✅ 按行（顺序）访问
for (int i = 0; i < 1000; i++) {
    for (int j = 0; j < 1000; j++) {
        sum += matrix[i][j];  // 连续访问 → 缓存命中率 ~100%
    }
}
```

上例中，按行比按列快 10-30x（C 等行优先语言）。

### 3.2 分支消除

```c
// ❌ 条件分支
double result = 0;
for (int i = 0; i < N; i++) {
    if (data[i] > 0) {
        result += data[i];
    }
}
// 每次迭代都可能分支预测错误

// ✅ 无分支版本（分支预测 100%）
double result = 0;
int idx = 0;
double pos_only[N];
for (int i = 0; i < N; i++) {
    pos_only[idx] = data[i];
    idx += (data[i] > 0);       // CMOV 指令而非分支
}
for (int i = 0; i < idx; i++) {
    result += pos_only[i];       // 连续累加，无分支
}

// 或者用三元运算符（编译器可能优化为 CMOV）
for (int i = 0; i < N; i++) {
    result += (data[i] > 0) ? data[i] : 0;
}
```

### 3.3 查找表（LUT）替代计算

```c
// ❌ 实时计算三角函数
double result = 0;
for (int i = 0; i < N; i++) {
    result += sin(angle[i]);  // sin 耗时 ~50-100 周期
}

// ✅ 查找表（精度允许时）
constexpr int TABLE_SIZE = 1024;
double sin_table[TABLE_SIZE];
for (int i = 0; i < TABLE_SIZE; i++) {
    sin_table[i] = sin(2 * M_PI * i / TABLE_SIZE);
}

double result = 0;
for (int i = 0; i < N; i++) {
    int idx = (int)(angle[i] / (2 * M_PI) * TABLE_SIZE) % TABLE_SIZE;
    result += sin_table[idx];  // ~1-2 周期
}
```

## 4. 大小端和内存对齐

### 4.1 对齐

```c
// ❌ 不对齐的结构体
struct __attribute__((packed)) Packet {
    uint8_t type;    // 1 byte
    uint32_t id;     // 4 bytes → 需要 2 次访存才能读（未对齐）
    uint16_t len;    // 2 bytes
};
// sizeof(Packet) = 7 bytes, 但 id 在地址 1, 不是 4 的倍数

// ✅ 对齐的结构体
struct Packet {
    uint8_t type;
    uint8_t padding[3];  // 对齐到 4 字节
    uint32_t id;
    uint16_t len;
};
// sizeof(Packet) = 8 bytes
```

不对齐的代价：x86 上虽不会崩溃但慢 2-3x（需要特殊微码处理），ARM 上直接 SIGBUS。

### 4.2 复合索引

数据库索引的字段顺序很重要（最左前缀）：

```sql
-- 复合索引 (exchange, symbol, timestamp)

-- ✅ 高效（匹配最左前缀）
WHERE exchange = 'SSE' AND symbol = '000009'
-- 先过滤 exchange (1个匹配) → 再过滤 symbol → 局部性

-- ✅ 高效（完整索引）
WHERE exchange = 'SSE' AND symbol = '000009' AND timestamp > '2026-01-01'

-- ❌ 低效（跳过了中间字段）
WHERE exchange = 'SSE' AND timestamp > '2026-01-01'
-- 只能用到 exchange 过滤，无法进一步缩小 timestamp
```

## 5. 内存分配器选择

| 分配器 | 适用 | 特点 |
|--------|------|------|
| glibc malloc | 通用 | 平衡 |
| tcmalloc (Google) | 多线程 | 减少锁竞争 |
| jemalloc (Facebook) | 多线程 + 大内存 | 减少碎片 |
| mimalloc (Microsoft) | 通用 | 快速、低开销 |

```bash
# Python 可以使用 jemalloc 替代系统 malloc
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so python my_script.py
```

## 总结

```
数据布局 > 算法复杂度（对现代 CPU 而言）
SoA > AoS（SIMD 和缓存的亲密朋友）
预分配 > 动态分配（频繁 malloc 的代价）
分支消除 > 分支预测（不可预测分支的代价）
查找表 > 实时计算（精度和速度的权衡）
内存对齐 （不只是对齐，是 I/O 效率）
```
