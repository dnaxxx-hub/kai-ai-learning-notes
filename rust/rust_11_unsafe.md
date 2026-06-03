# Rust #11：unsafe Rust — 裸指针、FFI、Unsafe 最佳实践

> 2026-05-17
> 前置知识：Rust #1~10，特别是 #5 智能指针和 #8 生命周期

## 引言

### 为什么要 unsafe？

Rust 的安全保证都在 Safe Rust 中。但现实世界需要：
1. **FFI** — 调用 C 代码（操作系统 API、现有 C 库）
2. **性能** — 某些场景需要绕过借用检查器（自定义分配器、SIMD）
3. **硬件操作** — 裸机、驱动开发

```rust
// Safe Rust 保证：
// ✓ 不会段错误（无悬垂指针）
// ✓ 不会数据竞争（借用检查器）
// ✓ 不会空指针解引用
// ✓ 不会缓冲区溢出

// Unsafe Rust 额外允许：
// ✗ 解引用裸指针
// ✗ 调用 unsafe 函数（包括 FFI）
// ✗ 访问/修改可变静态变量
// ✗ 实现 unsafe trait
// ✗ 访问 union 字段
```

### 关键原则：unsafe 不是"关掉安全检查"

**unsafe 是告诉编译器"我以人类身份保证这段代码的安全"**。编译器不再帮你检查，但出bug还是你的错。

```rust
// ❌ 错误认知：unsafe = "不要检查了，我知道我在做什么"
// ✅ 正确认知：unsafe = "编译器你看，这人保证这段代码安全"

// unsafe 块内的 Safe Rust 代码仍然受借用检查器约束
unsafe {
    let mut x = 42;
    let r = &x;       // Safe Rust 的不可变借用
    // x = 0;         // ❌ 即使在 unsafe 块内也报错！
}
```

## 1. 裸指针 (`*const T` 和 `*mut T`)

### 与引用和智能指针的对比

```rust
// 引用 &T          : 非空，对齐，不别名
// 可变引用 &mut T  : 非空，对齐，唯一
// 裸指针 *const T  : 可能为空，可能未对齐，可能别名
// 裸指针 *mut T    : 可能为空，可能未对齐，可能别名

// 裸指针可以做什么引用不能做的：
let x = 42;
let r = &x as *const i32;     // Safe！创建裸指针总是安全的

// 1. 无视引用规则（允许别名）
let mut v = vec![1, 2, 3];
let p1 = &mut v[0] as *mut i32;  // 第一元素
let p2 = &mut v[1] as *mut i32;  // 第二元素
unsafe {
    *p1 = 10;
    *p2 = 20;  // 同时可变，Safe Rust 不允许，unsafe 允许
}

// 2. 可以为空
let ptr: *const i32 = std::ptr::null();
unsafe {
    // *ptr  // ⚠️ 解引用空指针是 UB！
}
```

### 创建和操作裸指针

```rust
let x = 42;
// Safe：创建裸指针
let ptr_const: *const i32 = &x;
let mut y = 42;
let ptr_mut: *mut i32 = &mut y;

// 转换引用到指针
let s = String::from("hello");
let len_ptr: *const usize = &s.len;  // 指向 s 的长度字段

// 指针算术
let arr = [1, 2, 3, 4, 5];
let base = arr.as_ptr();  // *const i32
unsafe {
    assert_eq!(*base, 1);
    assert_eq!(*base.add(2), 3);  // 偏移 2 个元素
    assert_eq!(*base.offset(4), 5); // offset 同 add，可以负偏移

    // 获取偏移后的引用
    let slice = std::slice::from_raw_parts(base.add(1), 3);
    assert_eq!(slice, &[2, 3, 4]);
}
```

### 何时使用裸指针

```rust
// 场景 1：FFI 中操作 C 函数返回的指针
extern "C" {
    fn malloc(size: usize) -> *mut std::ffi::c_void;
}

// 场景 2：构建自引用结构（async 状态机本质上就用到了）
struct SelfRef {
    data: String,
    ptr: *const String,  // 指向 self.data
}

impl SelfRef {
    fn new(data: String) -> Self {
        SelfRef {
            ptr: std::ptr::null(),
            data,
        }
    }
    fn init(&mut self) {
        self.ptr = &self.data as *const String;  // 必须 unsafe？不，创建指针 safe
    }
    fn get(&self) -> &str {
        unsafe { &*self.ptr }
    }
}
```

## 2. Unsafe 函数和块

### unsafe fn vs unsafe block

```rust
// unsafe fn：函数本身是不安全的，调用者必须确保条件
unsafe fn dangerous() {
    // 这个函数体可以做各种 unsafe 操作
    // 调用者需要保证安全
}

// unsafe block：在 safe 代码中做 unsafe 操作
fn safe_wrapper() {
    // 在这里保证条件
    unsafe {
        dangerous();
    }
}
```

### 设计模式：安全抽象包装不安全实现

```rust
// 最好的 unsafe 使用模式：封装在安全的 API 后面

// 不安全的底层
unsafe trait Allocator {
    unsafe fn alloc(&self, size: usize) -> *mut u8;
    unsafe fn dealloc(&self, ptr: *mut u8, size: usize);
}

// 安全的上层抽象
struct Vec<T, A: Allocator> {
    ptr: *mut T,
    len: usize,
    cap: usize,
    alloc: A,
}

impl<T, A: Allocator> Vec<T, A> {
    // 安全的 push 方法
    fn push(&mut self, value: T) {
        if self.len == self.cap {
            self.grow();
        }
        unsafe {
            // 在安全方法中做 unsafe 操作
            std::ptr::write(self.ptr.add(self.len), value);
            self.len += 1;
        }
    }
}
// 用户使用 Vec 时完全不需要 unsafe
```

## 3. FFI — 外部函数接口

### 调用 C 代码

```rust
// 声明外部函数
extern "C" {
    fn abs(input: i32) -> i32;
    fn strlen(s: *const std::ffi::c_char) -> usize;
    fn printf(fmt: *const std::ffi::c_char, ...) -> i32;
}

fn main() {
    unsafe {
        println!("abs(-3) = {}", abs(-3));  // 3

        let s = std::ffi::CString::new("hello").unwrap();
        println!("strlen = {}", strlen(s.as_ptr()));  // 5
    }
}
```

### C ABI 调用约定

```rust
mod ffi {
    use std::ffi::{CStr, CString};

    // extern "C" = C ABI — 调用约定与 C 兼容
    // 还有其他约定：
    extern "stdcall" fn stdcall_ffi();    // Windows API
    extern "fastcall" fn fastcall_ffi();
    extern "thiscall" fn thiscall_ffi();  // C++ 成员函数

    // 链接到外部库
    #[link(name = "m")]  // 链接 libm (数学库)
    extern "C" {
        fn sqrt(x: f64) -> f64;
        fn pow(x: f64, y: f64) -> f64;
    }

    pub fn safe_sqrt(x: f64) -> f64 {
        unsafe { sqrt(x) }
    }
}
```

### 在 C 中调用 Rust

```rust
// lib.rs
// #[no_mangle] 保持函数名不被 mangle
// extern "C" 使用 C ABI

#[no_mangle]
pub extern "C" fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[no_mangle]
pub extern "C" fn process_data(data: *mut i32, len: usize) {
    let slice = unsafe { std::slice::from_raw_parts_mut(data, len) };
    for v in slice.iter_mut() {
        *v *= 2;
    }
}

// C 代码调用：
// int add(int a, int b);
// void process_data(int* data, size_t len);
// 
// gcc -o test main.c -lrust_ffi -L. -Wl,-rpath,.
```

### CString 和 CStr

```rust
// Rust → C：需要 CString (末尾有 \0)
let rust_str = "hello";
let c_str = std::ffi::CString::new(rust_str).unwrap();
// c_str.as_ptr() → *const c_char

// C → Rust：从 CStr 解析
unsafe {
    let c_str_ptr: *const std::ffi::c_char = /* 从 C 得到 */;
    let c_str = std::ffi::CStr::from_ptr(c_str_ptr);
    let rust_str = c_str.to_str().unwrap();
}
```

## 4. unsafe trait 实现

```rust
// Send 和 Sync 就是 unsafe trait
unsafe trait Send {}
unsafe trait Sync {}

// 大多数类型自动获得 Send/Sync
// 但当你的类型包含裸指针时，需要手动实现

struct MyBox<T> {
    ptr: *mut T,
}

// Rust 不会自动为含裸指针的类型实现 Send/Sync
// 如果你能保证线程安全，手动实现
unsafe impl<T: Send> Send for MyBox<T> {}
unsafe impl<T: Sync> Sync for MyBox<T> {}

// ⚠️ 错误的实现 = 数据竞争
// 只有确定线程安全时才实现
```

## 5. 可变静态变量

```rust
// 全局可变静态变量 — 在 Safe Rust 中不允许读写
static mut COUNTER: u32 = 0;

fn increment() {
    unsafe {
        COUNTER += 1;
    }
}

// 更好的方案：使用 std::sync::Mutex 或 atomic
use std::sync::atomic::{AtomicU32, Ordering};
static SAFE_COUNTER: AtomicU32 = AtomicU32::new(0);

fn safe_increment() {
    SAFE_COUNTER.fetch_add(1, Ordering::SeqCst);
}
```

## 6. 联合体 (Union)

```rust
// Rust 的 union 类似 C 的 union — 不同字段共享同一块内存
// 访问 union 字段是 unsafe 的

union IntOrFloat {
    i: i32,
    f: f32,
}

fn main() {
    let u = IntOrFloat { i: 42 };
    unsafe {
        println!("{}.{}", u.i, u.f);  // 42 和对应的 f32 解释
    }

    // 实际用途：类型双关 (type punning)
    fn bits_to_float(bits: u32) -> f32 {
        let u = IntOrFloat { i: bits as i32 };
        unsafe { u.f }
    }
}
```

## 7. 实战：安全包装一个 C 库

```rust
// 以我们之前用过的 WinHTTP API 为例（windows-rs 封装了，但了解原理）

mod winhttp_safe {
    use std::ffi::{CStr, CString};
    use std::ptr;

    // 模拟的 C API（实际调用 WinHTTP API）
    extern "system" {
        fn WinHttpOpen(
            pwszUserAgent: *const u16,
            dwAccessType: u32,
            pwszProxyName: *const u16,
            pwszProxyBypass: *const u16,
            dwFlags: u32,
        ) -> *mut std::ffi::c_void;

        fn WinHttpCloseHandle(hInternet: *mut std::ffi::c_void) -> u32;
    }

    // 安全的封装
    pub struct WinHttpHandle {
        handle: *mut std::ffi::c_void,
    }

    impl WinHttpHandle {
        pub fn open(user_agent: &str) -> Result<Self, &'static str> {
            // 将 Rust 字符串转为宽字符串 (UTF-16)
            let agent_wide: Vec<u16> = user_agent
                .encode_utf16()
                .chain(std::iter::once(0))
                .collect();

            unsafe {
                let handle = WinHttpOpen(
                    agent_wide.as_ptr(),
                    0, // WINHTTP_ACCESS_TYPE_DEFAULT_PROXY
                    ptr::null(),
                    ptr::null(),
                    0,
                );

                if handle.is_null() {
                    Err("WinHttpOpen failed")
                } else {
                    Ok(WinHttpHandle { handle })
                }
            }
        }
    }

    // Drop trait：RAII 模式释放资源
    impl Drop for WinHttpHandle {
        fn drop(&mut self) {
            if !self.handle.is_null() {
                unsafe {
                    WinHttpCloseHandle(self.handle);
                }
            }
        }
    }

    // 用户在 safe Rust 中使用
    // let h = WinHttpHandle::open("StockCLI").unwrap();
    // h 离开作用域自动释放
}
```

## 8. Unsafe 的五个"可以"

```rust
// 1. 解引用裸指针
let x = 42;
let ptr = &x as *const i32;
unsafe { println!("{}", *ptr); }

// 2. 调用 unsafe 函数
unsafe fn foo() {}
unsafe { foo(); }

// 3. 访问/修改可变静态变量
static mut COUNTER: i32 = 0;
unsafe { COUNTER += 1; }

// 4. 实现 unsafe trait
unsafe impl Send for MyType {}

// 5. 访问 union 字段
union U { i: i32, f: f32 }
unsafe { u.i; }
```

## 9. 常见 Unsafe 陷阱

### 悬垂指针

```rust
fn dangling() -> *const i32 {
    let x = 42;
    &x as *const i32  // 返回指向栈变量的指针
    // x 离开作用域后被释放 —— 悬垂指针！
}
// 在调用者解引用时，内存已被重新使用
```

### 未定义行为 (UB)

```rust
// Rust 中的 UB 包括（不限于）：
// 💀 数据竞争
// 💀 解引用空/悬垂指针
// 💀 读取未初始化的内存
// 💀 违反指针别名规则
// 💀 创建非法的基本类型值
// 💀 使用错误的 ABI 调用函数
// 💀 内存释放后再使用

// UB 的后果：编译器可以认为"这行代码不会被执行"
// 从而导致安全代码中产生意想不到的行为

// 经典例子：
unsafe {
    // 从空指针创建切片
    let slice = std::slice::from_raw_parts(0 as *const i32, 100);
    // UB！空指针 + 非零长度
}
```

### 保持稳定的库 API

```rust
// pub unsafe fn 意味着：调用者必须确保条件
// 改变这个函数为 safe 是"破坏性变更"
// 所以最好一开始就用安全抽象

// 推荐模式：
// ❌ 导出 unsafe API
pub unsafe fn do_dangerous_thing(ptr: *mut i32) { ... }

// ✅ 导出安全 API，内部用 unsafe
pub fn do_safe_thing(data: &mut i32) {
    unsafe { do_dangerous_thing(data); }
}
```

## 10. Miri — 检测 UB 的工具

```rust
// Miri 是 Rust 的 UB 检测器，可以运行时检测大多数 UB
// cargo +nightly miri run
// cargo +nightly miri test

// 什么不能被 Miri 检测：
// ✗ FFI（无法检查外部代码）
// ✗ 平台相关的 UB（内联汇编）
// ✓ 可以检测：指针算术、未初始化内存、别名规则违反
```

## 11. 总结：什么时候用 unsafe

```rust
// ✅ 适合用 unsafe 的场景：
// 1. FFI — 没有其他方式调用 C 库
// 2. 实现零开销抽象（Vec、HashMap、Rc）
// 3. 高性能原始内存操作（自定义分配器）
// 4. SIMD 操作
// 5. 裸机/嵌入式

// ❌ 不适合用 unsafe 的场景：
// 1. 只是因为懒（不想写生命周期标注）
// 2. 加速代码（优化器处理 Safe Rust 和 Unsafe 一样好）
// 3. 绕过借用检查器（"gimme a raw pointer and let me go"）
```

### Rust Unsafe 层次

```
Safe Rust（默认）
├── 借用检查保证安全
├── 无段错误（如果 Safe 代码正确）
└── 编译期检查

Unsafe Rust（可选择加入）
├── 需要开发者保证不变条件
├── 仍然受借用检查（在引用上）
└── 手动验证

FFI 边界
├── 与外部世界通信
├── 必须手动验证类型和生命周期
└── 通常是 UB 的高发区

（越往下，需要的保证越多）
```

## 12. 从 #5 智能指针看 unsafe

```rust
// Box、Rc、Vec 等标准库类型内部都用了 unsafe
// 但它们暴露安全的 API

// 标准库 Vec::push 简化版：
impl<T> Vec<T> {
    pub fn push(&mut self, value: T) {
        if self.len == self.cap { self.grow(); }
        unsafe {
            // write 不会 drop 旧值（内存尚未初始化）
            std::ptr::write(self.ptr.add(self.len), value);
        }
        self.len += 1;
    }
}
// Vec::push 是安全的——它保证：
// 1. 指针不为空
// 2. 偏移不越界
// 3. 内存已经分配

// 用户不需要知道 unsafe，只管 push 就好
```

## 参考

- The Book Ch.19.1: Unsafe Rust
- Rustonomicon: https://doc.rust-lang.org/nomicon/
- Miri: https://github.com/rust-lang/miri
- "Rust Atomics and Locks" Ch.9: The Happens-Before Relationship (unsafe 的并发保证)
