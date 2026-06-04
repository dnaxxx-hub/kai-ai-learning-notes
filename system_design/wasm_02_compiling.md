# WASM #2：Rust → WASM 编译实战

> 2026-05-17
> 前置：WASM 入、Rust 基础、编译原理基础

## 1. 编译流程全景

```
Rust 源码
  → rustc (LLVM 后端)
    → .wasm 二进制 (wasm32-unknown-unknown target)
      → wasm-bindgen (生成 JS glue)
        → wasm-pack (打包为 npm 包)
```

## 2. wasm-bindgen 的核心角色

### 2.1 类型桥接

```rust
#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}
```

wasm-bindgen 自动生成：
- Rust 端：将 `&str` 写入线性内存并传递指针+长度
- JS 端：从线性内存读取并构造 JS String

### 2.2 导出规则

| Rust 类型 | WASM 导出 | 备注 |
|-----------|-----------|------|
| `i32`/`u32`/`f64` | 直接值 | 零开销 |
| `&str`/`String` | 指针+长度 | 需内存管理 |
| `Vec<T>` | 指针+长度 | 需 JS 释放 |
| `Result<T, JsValue>` | 异常桥接 | try/catch 转换 |
| `struct` with `#[wasm_bindgen]` | 类 | 含方法+字段 |

### 2.3 JsValue —— 万能类型

`JsValue` 表示任意 JS 值（对象/函数/undefined/null），通过它 WASM 可以和 JS 复杂类型交互。

```rust
#[wasm_bindgen]
pub fn process_js_value(val: JsValue) -> JsValue {
    // 通过 serde_wasm_bindgen 做 JSON 序列化
    let data: serde_json::Value = serde_wasm_bindgen::from_value(val).unwrap();
    // 处理...
    serde_wasm_bindgen::to_value(&result).unwrap()
}
```

## 3. wasm-pack 打包流程

```bash
wasm-pack build --target web    # 生成 ES 模块
wasm-pack build --target bundler  # 生成 webpack/rollup 兼容包
wasm-pack build --target nodejs   # 生成 CommonJS 包
```

### 输出结构（--target web）

```
pkg/
├── project_name_bg.wasm     # 编译后的 WASM 二进制
├── project_name.js          # JS glue code (加载+初始化+类型桥接)
├── project_name.d.ts        # TypeScript 类型声明
└── package.json             # npm 包配置
```

## 4. 内存管理关键

### 4.1 所有权边界

Rust 分配的内存在 WASM 中不会自动释放——GC 只跑在 JS 侧。

核心问题：当 WASM 返回一个 `Vec<u8>` 或 `String`，谁负责 `free`？

wasm-bindgen 的做法：在 JS glue 中自动插入 `__wbindgen_free` 调用。
但前提是 JS glue 能跟踪到所有权——如果直接返回裸指针，必须手动管理。

### 4.2 Box 配合 wasm-bindgen

```rust
#[wasm_bindgen]
pub fn create_large_array() -> Box<[u8]> {
    vec![0u8; 1024 * 1024].into_boxed_slice()
}
// JS 端：wasm-bindgen 自动释放 Box 的内存
```

### 4.3 手动内存管理场景

```rust
#[wasm_bindgen]
pub fn compute_and_get_ptr() -> *mut u8 {
    let data = Box::new(42u8);
    Box::into_raw(data) // 所有权转移给调用者
}

#[wasm_bindgen]
pub fn free_ptr(ptr: *mut u8) {
    unsafe { drop(Box::from_raw(ptr)); }
}
```

## 5. 性能调优

### 5.1 批处理原则

❌ 错误：每个数据点单独调用 WASM
```js
for (const d of hugeArray) {
    result += wasm.process_datum(d);  // 每次调用都有 JS↔WASM 边界开销
}
```

✅ 正确：批量传入
```rust
#[wasm_bindgen]
pub fn process_batch(data: &[f64]) -> Vec<f64> {
    data.iter().map(|x| /* 复杂计算 */).collect()
}
```

### 5.2 线性内存直接共享

```rust
// Rust 端：返回内存视图
#[wasm_bindgen]
pub fn get_buffer() -> JsValue {
    let memory = wasm_bindgen::memory();
    // 返回内存视图的偏移和长度
    JsValue::null()
}
```

JS 端通过 WebAssembly.Memory 直接读写线性内存，绕过 JS↔WASM 边界。

### 5.3 优化技巧清单

- 最小化函数调用次数：打包数据批量传入
- 使用 `wasm-opt` 优化二进制大小（-O3 可减 30-50%）
- 移除 panic 处理：`panic = "abort"` 在 Cargo.toml 中
- 注意 LTO（链接时优化）：`lto = true` 在 release profile
- WASM 的包体积 ≈ 去掉 std 库的 Rust 二进制（std 有很多 WASM 不支持的 OS 特性）

## 6. 服务端场景：WASI

### 6.1 WASM vs WASI

| | WASM | WASI |
|---|------|------|
| 环境 | 浏览器 | 服务端/CLI |
| API | JS glue | 系统接口（文件/网络） |
| 运行时 | 浏览器内置 | Wasmtime/Wasmer |
| 安全 | 浏览器沙箱 | 按需权限 |

### 6.2 Wasmtime 使用

```rust
use wasmtime::*;

fn main() -> Result<()> {
    let engine = Engine::default();
    let module = Module::from_file(&engine, "add.wasm")?;
    let mut store = Store::new(&engine, ());
    let instance = Instance::new(&mut store, &module, &[])?;
    let add = instance.get_typed_func::<(i32, i32), i32>(&mut store, "add")?;
    let result = add.call(&mut store, (1, 2))?;
    println!("1 + 2 = {result}");
    Ok(())
}
```

### 6.3 WASI 权限模型

```rust
let mut linker = Linker::new(&engine);
wasmtime_wasi::add_to_linker(&mut linker, |s| s)?;

// 权限授予：显式打开文件
let wasi_ctx = WasiCtxBuilder::new()
    .inherit_stdout()
    .preopened_dir("/sandbox", "/")? // 只暴露沙箱目录
    .build();
```

对比 Docker：
- Docker：共享内核 → 整个 OS 暴露
- WASM+WASI：无系统调用 → 按文件粒度授权

## 7. 服务端 WASM 应用场景

### 7.1 Cloudflare Workers
- 已支持 WASM 作为 Service Worker 的一部分
- 毫秒级冷启动，适合边缘计算

### 7.2 插件系统
- 用户上传 WASM 作为安全沙箱插件
- 比 Lua/JS 嵌入更安全（线性内存隔离）
- 比进程隔离更轻量（共享地址空间但内存隔离）

### 7.3 FaaS 运行时
- 10ms 冷启动 vs 容器 100ms+
- 包体积 10-100KB vs Docker image 10-100MB
- 无状态计算场景的理想选择

## 8. WASM 局限

| 局限 | 说明 | 缓解 |
|------|------|------|
| 无 GC | 手动管理内存 | Rust 所有权系统 |
| 无异常 | trap 机制简单 | Result 类型 |
| 无标准库 | WASM 只有数字类型 | wasm-bindgen 桥接 |
| 调试困难 | DWARF 支持不完善 | console.log 调试 |
| DOM 桥接开销 | 每次都要过边界 | 批处理 + 批量操作 |
| 多线程有限 | SharedArrayBuffer 需 COOP/COEP | WASM threads proposal |

## 总结

```
Rust + WASM 的最佳实践：
1. 把计算密集逻辑迁入 WASM（图像/加密/编码/ML）
2. 批量传入数据，最小化边界调用
3. 使用 wasm-bindgen 自动处理类型桥接
4. 优先用 Box<T>/Vec<T> 避免手动内存管理
5. 服务端用 WASI + Wasmtime 做沙箱插件
6. WASM ≠ 替代 JS/容器，而是互补方案
```
