# Rust FFI：C 绑定与 WebAssembly

## 1. Rust FFI 基础

### 1.1 声明外部函数

```rust
#[link(name = "snappy")]
unsafe extern "C" {
    fn snappy_max_compressed_length(source_length: size_t) -> size_t;
    fn snappy_compress(
        input: *const u8, input_length: size_t,
        compressed: *mut u8, compressed_length: *mut size_t,
    ) -> c_int;
}
```

**关键点：**
- `#[link(name = "lib_name")]` 告诉链接器链接什么库
- `extern "C"` 指定 C ABI 调用约定
- 所有 FFI 调用必须放在 `unsafe {}` 块中

### 1.2 构建脚本（build.rs）

```toml
[package]
build = "build.rs"
```

```rust
// build.rs
fn main() {
    println!("cargo:rustc-link-lib=static=snappy");
    println!("cargo:rustc-link-search=/path/to/snappy/lib");
    // 生成绑定用
    println!("cargo:rerun-if-changed=wrapper.h");
}
```

### 1.3 类型映射

| C 类型 | Rust 类型（libc crate） |
|--------|----------------------|
| `int` | `c_int` |
| `char` | `c_char` |
| `size_t` | `size_t` |
| `void*` | `*mut c_void` |
| `int*` 输出参数 | `*mut c_int` |
| `const char*` | `*const c_char`（CString） |

---

## 2. 安全接口封装模式

### 2.1 基本模式：输入/输出缓冲

```rust
// 输入：从 &[u8] 安全转换
pub fn validate_compressed_buffer(src: &[u8]) -> bool {
    unsafe {
        snappy_validate_compressed_buffer(src.as_ptr(), src.len() as size_t) == 0
    }
}

// 输出：分配 Vec 并传递给 C
pub fn compress(src: &[u8]) -> Vec<u8> {
    unsafe {
        let srclen = src.len() as size_t;
        let psrc = src.as_ptr();
        let mut dstlen = snappy_max_compressed_length(srclen);
        let mut dst = Vec::with_capacity(dstlen as usize);
        snappy_compress(psrc, srclen, dst.as_mut_ptr(), &mut dstlen);
        dst.set_len(dstlen as usize);
        dst
    }
}
```

### 2.2 所有权与析构

**规则：** 谁分配谁释放。如果 C 库返回了内存，要用 Rust 的 `Drop` 封装：

```rust
struct CBuffer(*mut c_void);

impl Drop for CBuffer {
    fn drop(&mut self) {
        unsafe { c_free(self.0); }
    }
}
```

### 2.3 不透明类型（Opaque Type）

```rust
#[repr(C)]
pub struct Foo {
    _data: (),
    _marker: PhantomData<(*mut u8, PhantomPinned)>,
}
```

这种类型无法在安全代码中构造，只能作为指针传递，实现了类型安全的 C 句柄。

### 2.4 可空指针优化

利用 Rust 的"空指针优化"：

```rust
// Option<&T> 在运行时是 *const T（None = null）
// Option<Box<T>> 同理
// 对应 C 的 int (*)(int) 类型
type CCallback = Option<extern "C" fn(c_int) -> c_int>;
```

无需 `transmute`！

---

## 3. 回调模式

### 3.1 简单回调

```rust
unsafe extern "C" fn callback(a: i32) {
    println!("I'm called from C with value {0}", a);
}

// 注册到 C
#[link(name = "extlib")]
unsafe extern "C" {
    fn register_callback(cb: extern fn(i32)) -> i32;
    fn trigger_callback();
}
```

### 3.2 带目标对象的回调

```rust
struct RustObject { a: i32 }

unsafe extern "C" fn callback(target: *mut RustObject, a: i32) {
    unsafe { (*target).a = a; }
}

// 传递 raw pointer
register_callback(&mut *rust_object as *mut RustObject, callback);
```

### 3.3 异步回调（跨线程）

关键挑战：C 库可能在**任意线程**调用回调。

```rust
// 推荐方案：使用 channel 将回调转发到 Rust 线程
use std::sync::mpsc;

let (tx, rx) = mpsc::channel();
let callback = move |data| {
    tx.send(data).unwrap();  // 转发到 Rust 线程
};
```

---

## 4. Rust 调用 C 的完整流程

### 4.1 C 库编译

```makefile
# 编译 C 库为静态库
gcc -c -o snappy.o snappy.c
ar rcs libsnappy.a snappy.o
```

### 4.2 Rust 构建

```toml
# Cargo.toml
[build-dependencies]
# 可选：自动生成绑定
bindgen = "0.70"
```

```rust
// build.rs — 使用 bindgen
fn main() {
    let bindings = bindgen::Builder::default()
        .header("wrapper.h")
        .generate()
        .expect("Unable to generate bindings");
    bindings.write_to_file("src/bindings.rs").unwrap();
}
```

### 4.3 ABI 兼容规则

- `#[repr(C)]` 对 struct/enum — 保证内存布局与 C 一致
- `Box<T>` ❌ 不可用于 FFI（可能被换成 null）
- `String` ❌ 不是 C 字符串（无 null 终止符）
- `&T`/`&mut T` — 假设非空、对齐正确
- `*const T`/`*mut T` — 原始指针是最安全的 FFI 类型

---

## 5. WebAssembly（wasm-bindgen）

### 5.1 核心概念

```
Rust source → LLVM IR → wasm bytecode (.wasm)
wasm-bindgen 生成 JS 胶水层

数据传递方式：
- 基本类型（i32/f64）：直接传递
- 字符串/数组：复制到 wasm 线性内存 + 传递指针
- DOM/JS 对象：通过 externref（引用计数）
```

### 5.2 wasm-bindgen 声明

```rust
use wasm_bindgen::prelude::*;

// 导出给 JS 调用
#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

// 导入 JS 函数
#[wasm_bindgen]
extern "C" {
    fn alert(s: &str);
    #[wasm_bindgen(js_namespace = console)]
    fn log(s: &str);
}
```

### 5.3 JS 对象交互

```rust
#[wasm_bindgen]
pub struct Canvas {
    ctx: web_sys::CanvasRenderingContext2d,
}

#[wasm_bindgen]
impl Canvas {
    pub fn new(canvas_id: &str) -> Self {
        let document = web_sys::window().unwrap().document().unwrap();
        let canvas = document.get_element_by_id(canvas_id).unwrap();
        let ctx = canvas
            .dyn_into::<web_sys::HtmlCanvasElement>()
            .unwrap()
            .get_context("2d")
            .unwrap()
            .unwrap();
        Canvas { ctx }
    }

    pub fn draw_rect(&self, x: f64, y: f64, w: f64, h: f64) {
        self.ctx.fill_rect(x, y, w, h);
    }
}
```

### 5.4 内存模型

```
WASM Memory Layout:
┌─────────────────┐
│     Stack       │ ← local variables
├─────────────────┤
│     Heap        │ ← Box, Vec, String
│  (linear memory) │
├─────────────────┤
│  Stack Pointer  │ ← __heap_base
└─────────────────┘

JS/Rust 边界值传递：
- 小类型：Copy（i32, f64, bool）
- 字符串：编码为 UTF-8，复制到 wasm 堆，传递 (ptr, len)
- 大对象：传递引用编号（externref table index）
```

---

## 6. 深度对比：C FFI vs WASM

| 维度 | C FFI | WASM |
|------|-------|------|
| 调用开销 | 几乎 0（链接后直接调用） | ~10-100ns（通过 runtime） |
| 数据传递 | 指针直接共享 | 需复制或引用表间接访问 |
| 语言支持 | 任何 C ABI 语言 | 任何编译为 wasm 的语言 |
| 浏览器支持 | ❌ | ✅ |
| 安全性 | unsafe（裸指针） | 内存安全（线性内存边界检查） |
| 部署 | 二进制发行 | .wasm 文件，无需编译 |

---

## 7. 高级话题

### 7.1 unwinding 与异常

```rust
// C-unwind ABI — 允许 panic 跨越 C 边界
unsafe extern "C-unwind" fn example() {
    panic!("Unwinding across C frames");
}

// catch_unwind 翻译为错误码
pub extern "C" fn safe_function() -> i32 {
    match std::panic::catch_unwind(|| {
        // 可能 panic 的代码
    }) {
        Ok(_) => 0,
        Err(_) => 1,
    }
}
```

### 7.2 线程安全

C 库通常不保证线程安全。Rust 侧要：

1. 用 `Mutex` 包装所有 C 库调用
2. 实现 `Send + Sync`（unsafe 标记，需手动保证）
3. 不要跨线程解引用 C 返回的指针

### 7.3 性能优化

- **避免频繁跨 FFI 边界**：批量处理数据
- **使用静态链接**：减少运行时的库搜索开销
- **WASM 启用优化**：`wasm-pack build --release` + `wasm-opt -Oz`
- **线性内存预分配**：减少 wasm 内存增长次数
