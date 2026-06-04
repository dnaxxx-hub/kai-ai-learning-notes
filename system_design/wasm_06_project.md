# WASM #6：wasm_math 实战项目复盘

> 2026-05-17
> 前置：WASM 编译实战 #2、WAT #3

## 项目概况

一个纯 Rust WASM 数学库，导出 3 个计算密集函数：FFT、矩阵乘法、线性回归。

**源码结构**：
```
wasm_math/
├── Cargo.toml     — wasm32-unknown-unknown + cdylib
├── src/lib.rs     — 导出函数（FFT/MatMul/LinearFit）
└── pkg/           — 构建产物（JS glue + TS types + WASM）
```

## 构建流程复盘

### 最佳选型

```
Cargo.toml:
  [lib]
  crate-type = ["cdylib"]   ← 关键：WASM 动态库

  [profile.release]
  lto = true                ← 链接时优化（减少体积）
  opt-level = "z"            ← 优化体积（比 "s" 更激进）
  strip = true               ← 去除符号
  panic = "abort"            ← 不用 unwind（WASM 不支持）
```

### 构建命令

```bash
wasm-pack build --target web --release
```

等效手动三步：
1. `cargo build --target wasm32-unknown-unknown --release`
2. `wasm-bindgen target/.../wasm_math.wasm --out-dir pkg --target web`
3. wasm-pack 自动处理了 pkg/package.json

### 产物体积

```
wasm_math_bg.wasm   — 22.4 KB（包含 FFT + MatMul + LinearFit）
wasm_math.js        — 7.0 KB（JS glue + 类型桥接）
wasm_math.d.ts      — 1.9 KB（TypeScript 声明）
```

对比方案：
| 方案 | 体积 | 说明 |
|------|------|------|
| 纯 JS 实现 | ~8 KB | 慢 10-50x（数值计算） |
| Rust WASM (opt-level=z) | 22 KB | 原生性能 + 零运行时 |
| Rust WASM (opt-level=3) | ~35 KB | 更快但更胖 |
| Pyodide (CPython→WASM) | ~12 MB | 带完整运行时 |

opt-level=z 在 22KB 内实现 FFT + 矩阵乘 + 线性拟合，很划算。

## 导出函数设计

### 1. FFT

```rust
#[wasm_bindgen]
pub fn fft(real: &[f64], imag: &[f64]) -> Vec<f64>
```

**算法**：Cooley-Tukey 基-2 FFT，位反转重排 + 蝶形运算。

复杂度：O(n log n)，输入必须是 2 的幂。

**WASM 特有的设计考虑**：
- 传入 `&[f64]` → wasm-bindgen 自动从 JS typed array 复制到线性内存
- 返回 `Vec<f64>` → wasm-bindgen 在 JS glue 中自动释放内存
- 交错输出 `[re0, im0, re1, im1, ...]` → 减少一次 WASM→JS 边界调用

### 2. 矩阵乘法

```rust
#[wasm_bindgen]
pub fn matmul(a: &[f64], b: &[f64], m: usize, k: usize, n: usize) -> Vec<f64>
```

**设计**：i-k-j 循环顺序，利用 locality。

对于 100×100 矩阵：纯 Rust 约 2ms，JS 三重 for 循环约 15ms→ 7x 加速。

### 3. 最小二乘线性拟合

```rust
#[wasm_bindgen]
pub fn linear_fit(x: &[f64], y: &[f64]) -> Vec<f64>
```

返回 `[斜率, 截距]`。经典公式直接实现，计算量很小（O(n)），但演示了完整 WASM 工作流。

## JS 侧使用

```html
<script type="module">
import init, { fft, matmul, linear_fit } from './pkg/wasm_math.js';

async function main() {
    await init();  // 加载 WASM 二进制并初始化

    // FFT: 8 点信号
    const real = new Float64Array([1, 0, -1, 0, 1, 0, -1, 0]);
    const imag = new Float64Array([0, 0, 0, 0, 0, 0, 0, 0]);
    const result = fft(real, imag);
    console.log('FFT:', result);  // [re0, im0, re1, im1, ...]

    // 矩阵乘法: 2×3 × 3×2
    const a = new Float64Array([1, 2, 3, 4, 5, 6]);
    const b = new Float64Array([7, 8, 9, 10, 11, 12]);
    const c = matmul(a, b, 2, 3, 2);
    console.log('MatMul:', c);

    // 线性拟合
    const x = new Float64Array([1, 2, 3, 4, 5]);
    const y = new Float64Array([2.1, 4.0, 6.2, 7.9, 10.1]);
    const [slope, intercept] = linear_fit(x, y);
    console.log(`y = ${slope}x + ${intercept}`);
}
main();
</script>
```

## WASM 边界开销测试

JS↔WASM 调用开销（空函数）：

| 调用方式 | 每次开销 |
|---------|---------|
| 空函数 | ~50ns |
| 传 2 个 f64 | ~60ns |
| 传 1024 f64 slice | ~500ns（复制） |
| 返回 Vec\<f64\> (1024) | ~600ns（分配+复制） |

关键结论：WASM 边界的实际开销 < 1μs，只有真正的计算密集型 workload 才有显著加速。

## 与纯 JS 的对比场景

| 场景 | Rust WASM | 纯 JS | 加速比 |
|------|-----------|-------|--------|
| FFT 1024 | ~50μs | ~2ms | ~40x |
| MatMul 100×100 | ~2ms | ~15ms | ~7.5x |
| 线性拟合 1万点 | ~100μs | ~1ms | ~10x |

Upside：数值计算 WASM 有不可替代的性能优势。
Limit：DOM 操作、简单逻辑、频繁小调用 → WASM 不适合。

## 可扩展方向

1. **SIMD（wasm_simd128 或 portable-simd）**：FFT 和 MatMul 进一步加速 2-4x
2. **多线程**：wasm_threads proposal + SharedArrayBuffer
3. **配合 WebGL/WebGPU**：在 GPU 上跑大矩阵乘法
4. **集成到量化策略**：作为策略沙箱编译目标

## 总结

```
wasm_math 验证了 Rust → WASM 全链路：
1. 编译：wasm32 target + cdylib + release profile
2. 桥接：wasm-bindgen 自动类型转换 + 内存管理
3. 输出：22KB 二进制，含 3 个实用数学函数
4. 调用：JS Import + await init() + 直接调用

WASM 的真正价值：计算密集 + 安全沙箱 + 毫秒冷启动
在量化系统中可以落地为策略沙箱编译目标
```
