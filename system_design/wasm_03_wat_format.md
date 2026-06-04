# WASM #3：WAT 格式与模块结构

> 2026-05-17
> 前置：WASM 入 #1、编译原理 #1

## 1. WAT 是什么

WAT（WebAssembly Text Format）是 WASM 二进制格式的文本表示。人是机器不可读了，二进制更难读——WAT 是两者的桥梁。

```
WAT (.wat)            — 人类可读的文本格式
  ↓ wat2wasm
WASM (.wasm)          — 二进制格式，浏览器/运行时执行
  ↓ wasm2wat（逆向）
WAT 回读
```

工具链：https://webassembly.github.io/wabt/demo/wat2wasm/

## 2. 段结构

WASM 模块由若干互不重叠的段（section）组成：

| 段 | 是否可选 | 内容 |
|-----|---------|------|
| Type | 必须 | 函数签名列表 |
| Import | 可选 | 导入的函数/内存/全局变量 |
| Function | 必须 | 函数体代码索引 |
| Table | 可选 | 间接调用表（函数指针） |
| Memory | 可选 | 线性内存定义 |
| Global | 可选 | 全局变量（可导入/导出） |
| Export | 可选 | 导出给外部使用 |
| Start | 可选 | 模块初始化函数 |
| Element | 可选 | Table 初始值 |
| Code | 必须 | 函数体字节码 |
| Data | 可选 | 线性内存初始数据 |
| Custom | 可选 | 调试信息/名称段 |

## 3. WAT 语法基础

### 3.1 模块定义

```wat
(module
  ;; 所有段写在这里面
)
```

### 3.2 函数签名和定义

```wat
(module
  ;; 类型段：定义函数签名
  (type (func (param i32 i32) (result i32)))
  
  ;; 导入段
  (import "js" "log" (func $log (param i32)))
  
  ;; 函数定义：引用类型索引
  (func $add (type 0)
    local.get 0
    local.get 1
    i32.add)
  
  ;; 导出
  (export "add" (func $add))
)
```

### 3.3 指令栈

WASM 是基于栈的虚拟机。每个指令从栈上 pop 操作数，push 结果。

```wat
;; 计算 (1 + 2) * 3
i32.const 1
i32.const 2
i32.add      ;; 栈: [3]
i32.const 3
i32.mul      ;; 栈: [9]
```

vs S 表达式风格（更常见）：

```wat
;; 等价于上面的栈指令
(i32.mul
  (i32.add (i32.const 1) (i32.const 2))
  (i32.const 3))
```

### 3.4 控制流

```wat
;; if-else
(if (result i32)
  (local.get $cond)
  (then (i32.const 1))
  (else (i32.const 0)))

;; block/loop
(block $exit
  (loop $loop
    ;; ...
    br_if $exit  ;; 条件跳出
    br $loop     ;; 继续循环
  )
)
```

WASM 的控制流都是 **结构化**的——没有 goto，只有 block/loop/if。

## 4. 完整 WAT 示例

```wat
(module
  ;; ========== 类型段 ==========
  (type $add_type (func (param i32 i32) (result i32)))
  (type $fact_type (func (param i32) (result i32)))
  
  ;; ========== 内存定义 ==========
  (memory $mem 1)            ;; 初始 1 页（64KB）
  (data (i32.const 0) "Hello, WASM!")  ;; 初始化内存
  
  ;; ========== 全局变量 ==========
  (global $counter (mut i32) (i32.const 0))
  
  ;; ========== 导出 ==========
  (export "add" (func $add))
  (export "factorial" (func $factorial))
  (export "memory" (memory $mem))
  (export "counter" (global $counter))
  
  ;; ========== 函数体 ==========
  (func $add (type $add_type)
    local.get 0
    local.get 1
    i32.add)
  
  (func $factorial (type $fact_type)
    (if (result i32)
      (i32.le_u (local.get 0) (i32.const 1))
      (then (i32.const 1))
      (else
        (i32.mul
          (local.get 0)
          (call $factorial
            (i32.sub (local.get 0) (i32.const 1)))))))
)
```

## 5. 值类型

| WAT 类型 | WASM 类型 | 位数 | 说明 |
|----------|-----------|------|------|
| i32 | i32 | 32 | 整数（默认类型） |
| i64 | i64 | 64 | 大整数 |
| f32 | f32 | 32 | 单精度浮点 |
| f64 | f64 | 64 | 双精度浮点 |
| v128 | v128 | 128 | SIMD 向量（可选） |
| funcref | funcref | - | 函数引用 |
| externref | externref | - | 外部对象引用 |

**WASM 没有字符串类型**——字符串就是线性内存中的一段连续字节。

## 6. 经典指令集

### 算术
```
i32.add/sub/mul/div_s/div_u/rem_s/rem_u
i32.and/or/xor/shl/shr_s/shr_u/rotl/rotr
i32.eq/ne/lt_s/gt_s/le_s/ge_s
f32.add/sub/mul/div/sqrt/abs/neg/ceil/floor
```

### 内存
```
i32.load/store              ;; 4字节
i32.load8_s/u/store8       ;; 1字节
i32.load16_s/u/store16     ;; 2字节
```

### 控制
```
block $label / loop $label / if / else / end
br / br_if / br_table       ;; 分支指令
return / call / call_indirect  ;; 调用
```

## 7. 与 LLVM IR 的关系

```
Rust → rustc → LLVM IR → LLVM wasm backend → .wasm
                     ↑ WAT 位于不同抽象层级

LLVM IR: SSA 形式，无限虚拟寄存器
WASM: 栈机，只有 4+4+1 种值类型

WAT 是「编译后的」表示，不是编译器 IR
```

## 8. 二进制格式速览

WASM 二进制是魔数 + 版本 + 段的序列：

```
0x00 0x61 0x73 0x6d    ;; \0asm — 魔数
0x01 0x00 0x00 0x00    ;; 版本号 1

;; Type 段
0x01                    ;; section id (Type=1)
0x07                    ;; 段长度
  0x01                  ;; 1 个类型
  0x60                  ;; functype
  0x02                  ;; 2 个参数
  0x7f 0x7f            ;; i32, i32
  0x01                  ;; 1 个返回值
  0x7f                  ;; i32
```

每个段的字节用 LEB128 编码（变长整数）。

## 9. 调试技巧

### 在浏览器中

```js
// 实例化并暴露
const instance = await WebAssembly.instantiate(bytes, imports);
const { add, memory } = instance.exports;

// 用 console.wasm 调试（Firefox 支持）
// Chrome: DevTools → "WebAssembly" 面板
```

### 使用 WABT 工具

```bash
wat2wasm demo.wat -o demo.wasm      # WAT → WASM
wasm2wat demo.wasm -o demo.wat      # WASM → WAT（反汇编）
wasm-objdump -x demo.wasm           # 查看段信息
wasm-validate demo.wasm             # 验证二进制
wasm-opt -O3 demo.wasm -o opt.wasm  # 优化
wasm-strip demo.wasm -o stripped.wasm  # 去除调试信息
```

### Rust 调试

```rust
#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = console)]
    fn log(s: &str);
}

// Rust 侧可以直接 console.log
log(&format!("debug: {value}"));
```

## 总结

```
WAT = WASM 的人类可读表示
基于栈的虚拟机 + 结构化控制流 + 线性内存
是理解 WASM 内部机制的最好入口
编译器（Rust/LLVM）生成 WASM，但不生成 WAT
WABT 工具链：wat↔wasm 双向转换 + 分析 + 优化
```
