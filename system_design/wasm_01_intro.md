# WebAssembly 入门笔记：不只是浏览器的高性能代码

> 学习时间：2026-05-17
> Rust Phase 2 — 拓展：WASM 生态
> 前置：Rust 基础 + 编译原理基础

## 1. WASM 的本质定位

### 1.1 它是"编译目标"，不是"编程语言"

WebAssembly（WASM）不是手写的语言，而是**低级二进制指令格式**，作为 C/C++/Rust 的编译目标。

```
源语言 → 编译器 → .wasm 二进制 → 执行环境（浏览器/Wasmtime）
```

### 1.2 为什么需要 WASM？

- JS 性能天花板（动态类型、JIT 不完美）→ 计算密集型任务性能不够
- 大量 C/C++/Rust 库无法在浏览器中用 → WASM 跨语言编译到 Web

### 1.3 关键认知

WASM 不能操作 DOM，不能调 Web API，必须通过 JS glue code 桥接。

> WASM = 计算引擎，JS = 胶水 + UI 逻辑（互补，不是替代）

## 2. WASM vs JS

| 维度 | JS | WASM |
|------|-----|------|
| 类型 | 动态 | 静态（i32/i64/f32/f64）|
| 编译 | JIT | AOT |
| 内存 | GC | 线性内存 + 手动管理 |
| 速度 | 接近原生 | 接近原生，数值运算 10-50x |
| DOM | 原生 | ❌ 需 JS 桥接 |
| 安全 | 浏览器沙箱 | 更强（线性内存隔离） |

**核心注意**：JS↔WASM 边界调用有开销。最佳实践是把大量计算打包为一个 WASM 函数调用。

## 3. 线性内存

WASM 的线性内存是一个连续 ArrayBuffer：JS 和 WASM 共享同一块内存，大块数据零拷贝传递。

```
[全局变量 | 栈 | 堆] ← 连续线性地址空间
                    ← 64KB/页粒度 grow()
```

**安全**：WASM 代码只能访问线性内存范围内的地址，越界被运行时捕获。这让 WASM 成为运行不可信代码的理想沙箱。

## 4. Rust → WASM 工具链

```
rustc → LLVM IR → .wasm
wasm-bindgen → JS glue code (类型桥接 + 内存管理)
wasm-pack → npm 包
```

Rust 是 WASM 的最佳搭档：无 GC / 零成本抽象 / 无运行时 / 体积小。

## 5. 应用场景

- 图像处理（Figma、美图秀秀）— 10x 加速
- 游戏引擎（Unity/UE → WASM）
- 加密/密码学
- 解释器 in browser（Pyodide: CPython→WASM, sql.js, ffmpeg.wasm）
- 压缩/解压缩
- ML 推理（ONNX Runtime Web, Transformers.js）
- Serverless/FaaS — 毫秒级冷启动
- 边缘计算（Cloudflare Workers）

## 6. WASI (WebAssembly System Interface)

让 WASM 脱离浏览器运行的标准系统接口（文件/网络/时钟）。最小权限原则：模块默认无权限，调用者显式授予。

WASI P1（稳定）→ P2（组件模型+异步+HTTP 开发中）

## 7. 服务端 WASM

Wasmtime（Bytecode Alliance）和 Wasmer 是主流运行时。

核心价值：安全沙箱插件系统 + 超快冷启动 FaaS + Docker+WASM 组合。

> WASM 不是替代 Docker，而是补充：WASM 跑无状态业务逻辑，容器跑完整 OS 服务。
