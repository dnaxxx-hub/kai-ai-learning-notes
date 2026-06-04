# 前端 WebAssembly — 从 C/C++ 到浏览器

## 一、Emscripten — C/C++ 编译到 wasm

### 编译流程
```
C/C++ 源码 → Emscripten (emcc) → .wasm + .js glue
     ↓
Web 页面 <script src="xxx.js"> → 加载 wasm → 调用 C 函数
```

**Emscripten 核心**:
- **clang 前端**: 将 C/C++ 编译为 LLVM IR
- **Binaryen 后端**: LLVM IR → wasm
- **JS glue**: 内存管理 + API 桥接自动生成

### 编译命令
```bash
emcc calc.c -o calc.js -s WASM=1 -O3
```
- `-s WASM=1`: 输出 wasm 而非 asm.js
- `-O3`: 最高优化等级
- `-s EXPORTED_FUNCTIONS='[_add]'`: 指定导出的函数

**调用方式**:
```js
Module.onRuntimeInitialized = () => {
  const result = Module._add(1, 2) // 同步调用 C 函数
}
```

## 二、wasm vs JS 对比

| 维度 | JavaScript | WebAssembly |
|------|-----------|-------------|
| 类型 | 动态类型，JIT 优化 | 静态类型（i32/f32/i64/f64） |
| 内存 | GC 管理，堆 + 栈 | 线性内存（ArrayBuffer），手动管理 |
| 编译 | JIT → Hot Code 优化 | AOT 编译，接近机器码 |
| 速度 | 一般操作 1x | 密集型计算 **1.2-3x** |
| 适用 | DOM 操作、UI | 计算密集型（编解码/数学/游戏） |

**内存模型**:
```
wasm 线性内存: [0x0000 ... 0xFFFF]（连续、无碎片）
C 的 malloc 管理这块内存
JS 通过 TypedArray 访问: new Int32Array(wasm.memory.buffer)
```

**性能临界**:
- 小函数调用：wasm 有额外调用开销（从 JS 到 wasm 的边界跨越 cost ~5ns）
- 大块数据处理：wasm 优势明显

## 三、AssemblyScript — TypeScript → wasm

```
TypeScript 子集 → AssemblyScript 编译器 → wasm
```

**限制**:
- 不支持 `any`、`union types`
- 需显式类型声明（`i32`, `f64`）
- 无 DOM/BOM API
- 无 GC（手动管理内存）

**示例**:
```ts
export function add(a: i32, b: i32): i32 {
  return a + b
}
```

编译: `npx asc index.ts -o index.wasm`

**定位**: 为 JS 开发者提供低门槛 wasm 入口，性能接近手写 C。

## 四、WASI — 服务端 wasm

**WASI (WebAssembly System Interface)**: 让 wasm 运行在非浏览器环境。

**能力**:
- 文件系统访问
- 网络 Socket
- 时钟/随机数
- 环境变量

**运行时**: Wasmtime / WasmEdge / wasmer

**应用场景**: Serverless (CloudFlare Workers / Fastly Compute@Edge)、IoT、插件系统。

**WASI vs 浏览器 wasm**:
- 浏览器 wasm 依赖 JS API 访问外部
- WASI 可以直接调用系统服务

## 五、WebAssembly 实战应用

### 1. WebGL / 3D 渲染
- Unity/Unreal 游戏引擎 Web 导出（3D 游戏）
- **原理**: wasm 执行物理计算/骨骼动画，WebGL 负责渲染
- 性能较 JS 纯计算提升 2-3x

### 2. 音频处理
- **Web Audio API + wasm**: 音频编解码（MP3/AAC/Opus）
- **DAW 应用**: 音频效果器（混响/压缩/均衡器）
- 延迟降低 50%+

### 3. 图像处理
- **Canvas + wasm**: 大图缩放、滤镜（模糊/锐化/色彩矩阵）
- **格式编解码**: JPEG-XL/WEBP/AVIF 解码器
- 批量处理速度比纯 JS 快 3-5x

## 六、SIMD in wasm

**SIMD (Single Instruction Multiple Data)**: 一条指令同时处理多个数据。

**wasm SIMD 128-bit**: `v128` 类型 + 约 250 条 SIMD 指令

**应用**:
- 矩阵计算（4x4 float 同时处理）
- 像素处理（RGBA 4 通道并行）
- 音频（4 个样本同时计算）

**性能**: 比标量 wasm 再快 **2-4x**

**浏览器支持**: Chrome 91+ / Firefox 89+ / Safari 16.4+
