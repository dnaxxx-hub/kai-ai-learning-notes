# WASM #4：服务端 WASM 与 Wasmtime

> 2026-05-17
> 前置：WASM 编译实战 #2、Rust 并发 #6

## 1. WASI 的定位

WebAssembly System Interface（WASI）是让 WASM 突破浏览器运行的标准系统接口抽象层。

### 1.1 核心设计哲学

**最小权限**：模块默认无任何系统权限，调用者逐个授予。

```
WASI 模块：
  ├── 无：文件系统访问
  ├── 无：网络连接
  ├── 无：环境变量
  ├── 无：时间信息（默认 wall clock）
  └── 所有：计算能力（数学运算、内存分配）
```

### 1.2 与 POSIX 的关系

WASI ≠ POSIX。WASI 是 POSIX 的"安全子集 + WASM 适配"：

| 能力 | POSIX | WASI P1 | WASI P2（组件模型） |
|------|-------|---------|-------------------|
| 文件操作 | ✅ | ✅ | ✅ |
| 网络 | ✅ | ❌ | ✅ (preview 2+) |
| 进程 | fork/exec | ❌ | ❌ |
| 信号 | ✅ | ❌ | ❌ |
| 线程 | pthread | ✅ | ✅ |
| 异步 I/O | epoll/select | ❌ | ✅ (preview 2) |

WASI 不提供进程、信号或 fork——这些对于沙箱来说太重型且不安全。

## 2. Wasmtime 运行时

### 2.1 Rust 集成

```rust
use wasmtime::*;

fn main() -> Result<()> {
    // 1. 创建引擎（所有 WASM 模块共享编译缓存）
    let engine = Engine::default();

    // 2. 编译模块（AOT 编译为本地代码）
    let module = Module::from_file(&engine, "math.wasm")?;

    // 3. 创建 store（每个 store 独立线性内存）
    let mut store = Store::new(&engine, ());

    // 4. 实例化（链接导入 + 分配内存）
    let instance = Instance::new(&mut store, &module, &[])?;

    // 5. 获取导出函数
    let fft = instance.get_typed_func::<(i32, i32), i32>(&mut store, "fft")?;

    // 6. 调用
    let result = fft.call(&mut store, (16, 0))?;
    println!("FFT(16): {result}");

    Ok(())
}
```

### 2.2 模块缓存

WASM 模块编译为本地代码开销不小，可以缓存：

```rust
use wasmtime::{Engine, Module};
use std::fs;

// 编译时
let engine = Engine::default();
let module = Module::new(&engine, &wasm_bytes)?;
let serialized = module.serialize()?; // 编译后的原生代码
fs::write("module.cwasm", serialized)?;

// 加载时（免重编译）
let engine = Engine::default();
let module = unsafe { Module::deserialize(&engine, &fs::read("module.cwasm")?)? };
```

冷启动：首次编译 10-50ms → 缓存加载 1-5ms。

### 2.3 内存限制

```rust
// 默认 WASM 线性内存 1 页（64KB）
// 通过 store 限制内存增长
use wasmtime::MemoryType;

let mut config = Config::new();
config.max_wasm_stack(1024 * 1024); // 最大栈 1MB
let engine = Engine::new(&config)?;
```

每个 WASM 实例独立的线性内存空间，不受宿主内存泄漏影响。

## 3. 插件系统设计

### 3.1 WASM vs DLL/SO

| 维度 | DLL/共享库 | WASM 插件 |
|------|-----------|-----------|
| 安全隔离 | ❌ 完整进程地址空间 | ✅ 线性内存沙箱 |
| 崩溃隔离 | ❌ 宿主一起崩溃 | ✅ 实例级异常捕获 |
| 权限控制 | ❌ 全量系统权限 | ✅ WASI 按需授予 |
| 跨平台 | ❌ ABI 不兼容 | ✅ 二进制通用 |
| 热加载 | 进程级 | 实例级 |
| 调用开销 | 直接函数调用 | 边界 Marshaling |

### 3.2 宿主 ↔ 插件通信

```rust
use wasmtime::*;

// 定义宿主的导出函数（插件可以调用）
fn host_log( caller: Caller<'_, u32>, ptr: i32, len: i32 ) -> Result<()> {
    // 从 WASM 线性内存读取字符串
    let mem = caller.get_export("memory")
        .unwrap()
        .into_memory()
        .unwrap();
    let data = mem.data(&caller)
        [ptr as usize..(ptr + len) as usize]
        .to_vec();
    let msg = String::from_utf8_lossy(&data);
    println!("[Plugin] {msg}");
    Ok(())
}

// 宿主给插件提供的能力
fn create_linker(engine: &Engine) -> Result<Linker<u32>> {
    let mut linker = Linker::new(engine);
    linker.func_wrap("env", "log", host_log)?;
    linker.func_wrap("env", "get_time", || -> i64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64
    })?;
    Ok(linker)
}
```

插件侧（Rust）：

```rust
// 插件的 lib.rs
#[link(wasm_import_module = "env")]
extern "C" {
    fn log(ptr: i32, len: i32);
    fn get_time() -> i64;
}

#[no_mangle]
pub extern "C" fn calculate(data_ptr: i32, data_len: i32) -> i32 {
    let msg = "calculating...\0";
    unsafe { log(msg.as_ptr() as i32, msg.len() as i32) }
    // 计算逻辑...
    42
}
```

### 3.3 错误隔离

```rust
// WASM 插件崩溃 ⛔ → 宿主不受影响 ✅
match instance.get_typed_func::<(), i32>(&mut store, "run") {
    Ok(func) => match func.call(&mut store, ()) {
        Ok(result) => println!("Result: {result}"),
        Err(trap) => {
            // trap 只在这个实例范围内
            println!("Plugin crashed: {trap}, restarting...");
            // 重新加载插件的 WASM 模块
            drop(instance);
            let instance = Instance::new(&mut store, &module, &[])?;
        }
    },
    Err(e) => eprintln!("Plugin interface error: {e}"),
}
```

关键：WASM trap 不会传播到宿主的堆栈或内存。

## 4. FaaS 中的应用

### 4.1 冷启动对比

```
Docker 容器：  150-500ms  (拉取镜像 + 启动 OS)
Node.js 函数： 50-150ms   (初始化 V8 + require)
Python 函数：  100-300ms  (CPython 启动 + import)
WASM 函数：    <5ms       (加载二进制 + 内存分配)
```

AWS Lambda SnapStart（预热）+ WASM 的组合可以做到真正的零延迟冷启动。

### 4.2 资源效率

WASM 更轻量的一层抽象：

```
容器     → 30-100MB 基础镜像
Node.js → 15-30MB 运行时
Python  → 10-20MB 运行时
WASM    → 10-100KB 二进制
```

### 4.3 Cloudflare Workers 的实现模型

Workers 使用的 V8 isolates 模型与 WASM 有异曲同工之妙：

- 每个 Worker 一个独立的 V8 isolate（轻量级沙箱）
- 多 Worker 共享同一个 V8 进程
- 冷启动 ≈ 5ms

但这个灵活性依赖于 V8 特有的 isolate 能力——WASM 不依赖于特定运行时。

## 5. 实战案例：量化策略 WASM 沙箱

把用户自定义交易策略编译为 WASM，在沙箱中运行：

```rust
use wasmtime::*;

pub struct StrategySandbox {
    engine: Engine,
    linker: Linker<()>,
}

impl StrategySandbox {
    pub fn new() -> Result<Self> {
        let mut config = Config::new();
        config.max_wasm_stack(256 * 1024); // 限制栈大小
        let engine = Engine::new(&config)?;
        let mut linker = Linker::new(&engine);

        // 宿主提供的安全的 API 子集
        linker.func_wrap("strategy", "get_price", |symbol: i32| -> f64 {
            // 从安全的价格数据库读取（不含账户信息）
            100.0 // demo
        })?;
        linker.func_wrap("strategy", "log_trade", |symbol: i32, qty: f64| {
            // 记录交易建议到审核队列（不直接下单）
        })?;

        Ok(Self { engine, linker })
    }

    pub fn run(&self, wasm_bytes: &[u8], market_data: &[u8]) -> Result<Vec<u8>> {
        let module = Module::new(&self.engine, wasm_bytes)?;
        let mut store = Store::new(&self.engine, ());
        let instance = self.linker.instantiate(&mut store, &module)?;
        let func = instance.get_typed_func::<(), Vec<u8>>(&mut store, "decide")?;
        func.call(&mut store, ())
    }
}
```

安全优势：
- 策略代码拿不到账户/API key
- 无法发起网络请求
- 崩溃不影响交易引擎主进程
- 每次运行在全新实例中（无状态残留）

## 6. 局限与展望

### 当前局限
- WASI Preview 2 在推进中，但网络和异步 I/O 尚不成熟
- 堆栈追踪困难（DWARF 映射不完美）
- 大模块编译时间（>10MB 需要优化）

### 前景方向
- **组件模型**（component model）—— WASM 模块间标准化接口
- **WASI Preview 2/3**—— 原生异步 + HTTP
- **WebAssembly GC**—— 支持 GC 语言的 WASM 编译
- **WASM 作为通用编译目标**—— 从浏览器扩展到边缘计算 → 后端 → IoT

## 总结

```
WASM + Wasmtime 的核心价值：
1. 安全沙箱：线性内存隔离 + 按需权限
2. 超快冷启动：<5ms vs 容器 100ms+
3. 跨平台：一次编译，任意运行时
4. 小体积：10-100KB vs 镜像 MB 级别
5. 错误隔离：崩溃不影响宿主

不适合的场景：
- 大量 OS 调用（WASI 限制）
- 重型 I/O 工作负载（异步 await 不够成熟）
- 依赖特定硬件指令（SIMD 支持有限）
```
