# WASM #5：WASM 组件模型与生态

> 2026-05-17
> 前置：WASM 运行时 #4

## 1. 组件模型是什么

WASM 组件模型是 WASM 模块之上的**标准化接口层**，解决模块间的互通问题。

### 1.1 问题

```
传统 WASM 模块：
  WASM A 导出 add(i32, i32) → i32
  WASM B 导出 compute(String) → String

  ❌ A 和 B 不能直接互调（接口格式不统一）
  ❌ 宿主代码需要对每个模块写特定的适配
  ❌ 模块间传递复杂类型（字符串/结构体）需要手动 marshal
```

### 1.2 组件模型的解法

```
WASM 组件：
  模块 A 声明接口 (interface "math")  { add: func(x: s32, y: s32) → s32 }
  模块 B 声明接口 (interface "compute") { compute_string: func(s: string) → string }

  标准 WIT (WebAssembly Interface Types) 描述语言
  自动生成类型桥接代码 —— 无需手动 marshal
```

**核心抽象**：WIT（Wasm Interface Types）

```wit
// math.wit — 接口定义文件
package math:examples;

interface math-ops {
    add: func(x: s32, y: s32) -> s32;
    multiply: func(x: s32, y: s32) -> s32;
}

world math-world {
    export math-ops;
}
```

## 2. WIT 语言速览

### 2.1 内建类型

```wit
// 基本值类型
bool, s8, u8, s16, u16, s32, u32, s64, u64
float32, float64
char, string

// 复合类型
tuple<T, U>, list<T>, option<T>, result<T, E>
```

### 2.2 自定义类型

```wit
// 标志（Flags）
flags permissions {
    READ,
    WRITE,
    EXECUTE,
}

// 枚举
enum color {
    RED,
    GREEN,
    BLUE,
}

// 变体（Variant）
variant tree-node {
    leaf(s32),
    branch(list<tree-node>),
}

// 记录
record trade-signal {
    price: float64,
    volume: s32,
    action: string,
    timestamp: float64,
}
```

### 2.3 完整示例

一个量化策略的 WIT 接口：

```wit
package quant:strategy@1.0.0;

interface market-data {
    record bar {
        open: float64,
        high: float64,
        low: float64,
        close: float64,
        volume: s32,
        timestamp: s64,
    }
    
    get-bars: func(symbol: string, count: s32) -> list<bar>;
}

interface trading {
    record order {
        symbol: string,
        side: string,     // "buy" | "sell"
        price: float64,
        quantity: float64,
    }
    
    submit-order: func(order: order) -> result<u64, string>;
    cancel-order: func(order-id: u64) -> result<bool, string>;
}

world strategy-host {
    import market-data;
    import trading;
    
    export on-bar: func(bars: list<bar>);
}
```

## 3. 组件模型的工作流

```
WASM 模块二进制
    ↓ wasm-tools component new
WASM 组件（含 WIT 元数据）
    ↓ 组件间 1:1 类型匹配自动桥接
组合运行或单独运行
```

```bash
# 将模块打包为组件
wasm-tools component new math.wasm -o math.component.wasm

# 组件间链接
wasm-tools compose component_a.component.wasm component_b.component.wasm -o combined.component.wasm
```

## 4. WASM 生态全景

### 4.1 运行时对比

| 运行时 | 语言 | 关键特性 | 适用场景 |
|--------|------|----------|---------|
| Wasmtime | Rust | WASI P1/P2, 组件模型 | 服务端/FaaS |
| Wasmer | Rust | 多语言（JS/Python/Ruby 嵌入） | 插件系统 |
| WAMR | C | 极轻量（~100KB） | IoT/嵌入式 |
| WasmEdge | C++ | AI 推理扩展 + 网络 | 边缘 ML |
| wasm3 | C | 解释器（无 JIT） | 受限设备 |
| Node.js | C++ | 内建 WASM | Web 生态 |

### 4.2 工具链

```
wabt  — WAT ↔ WASM 转换 + 验证
wasm-tools — 组件模型操作 + WIT 处理
wasm-opt — Binaryen 优化器（-O3 减 30-50%）
wasm-pack — Rust → npm 包打包
wasmtime — WASI 运行时 + CLI
wasm2c — WASM → C 源码转换
```

### 4.3 WASM 在各语言的编译支持

| 语言 | 编译到 WASM | 状态 |
|------|-------------|------|
| Rust | ✅ wasm32-unknown-unknown | 一等公民 |
| C/C++ | ✅ EMScripten / clang | 成熟 |
| Go | ✅ 内建 js/wasm 目标 | 功能型 |
| Zig | ✅ 原生支持 | 不错 |
| Python | ⚠️ Pyodide 方案（CPython 编译为 WASM） | 通用场景 |
| Java | ⚠️ TeaVM / CheerpJ | 非主流 |
| C# | ⚠️ Blazor 方案 | .NET 生态 |

非 Rust/C/C++ 语言的 WASM 方案通常需要携带运行时（如 Pyodide 加载完整的 CPython 到 WASM），体积大且性能差。

## 5. WASM 在量子策略系统中的定位

结合当前量化交易引擎的设计：

```
用户策略（Rust/wasm-pack）
    ↓ 编译为 WASM 组件
WASM 沙箱（Wasmtime 实例）
    ↓ WIT 接口调用
量化引擎主板（strategy_v4.py）  
    ↓
行情 → 信号 → 执行
```

每个用户策略在一个独立的 WASM 实例中运行：
- **隔离**：策略之间不互相影响
- **安全**：策略只能访问宿主授权的数据
- **灵活**：策略热更新 — 替换 WASM 文件即换策略
- **公平**：策略统一通过 WIT 接口获取行和下单

## 总结

```
WASM 组件模型 = 标准化 WASM 模块交互协议
WIT = Interface Types，让模块间传递复杂类型

在生态中的定位：
- 浏览器：做计算密集的备选
- 服务端：做安全沙箱插件系统
- 边缘：做 FaaS 冷启动优化
- 我的系统：做量化策略沙箱

工具链最成熟的语言：Rust 和 C/C++
```
