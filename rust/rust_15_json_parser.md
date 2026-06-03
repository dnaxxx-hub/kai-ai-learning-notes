# Rust #15：从零实现 JSON 解析器

> 2026-05-25
> 目标：不依赖 serde_json，手写完整 JSON parser

## 1. 为什么手写 JSON 解析器？

| 理由 | 说明 |
|:-----|:-----|
| **深入理解协议** | JSON 规范很简单（~6 种类型），手写一遍就透彻了 |
| **学习编译器基础** | JSON 解析 = 一个极简的 parser，包含 lexer + parser 分层 |
| **Rust 模式匹配** | Option、Result、match — 都在这里用得最熟 |
| **错误处理设计** | 实现有位置信息的错误提示 |
| **不依赖外部 crate** | 理解 serde_json 底层在做什么 |

## 2. JSON 语法 — 极简版

```
value    → null | true | false | number | string | array | object
array    → '[' [ value (',' value)* ] ']'
object   → '{' [ string ':' value (',' string ':' value)* ] '}'
string   → '"' { unicode | escape }* '"'
number   → '-'? int ['.' frac] [('e'|'E') ['+'|'-'] digit+]
```

JSON 只有 **6 种值类型**：null, bool, number, string, array, object

## 3. 核心设计：递归下降解析器

```rust
pub struct JsonParser {
    input: Vec<u8>,  // 输入缓冲区
    pos: usize,      // 当前解析位置
}

impl JsonParser {
    pub fn parse(&mut self) -> JsonResult<JsonValue> {
        self.skip_whitespace();
        let val = self.parse_value()?;
        self.skip_whitespace();
        Ok(val)
    }

    fn parse_value(&mut self) -> JsonResult<JsonValue> {
        match self.peek() {
            b'n' => self.parse_null(),
            b't' | b'f' => self.parse_bool(),
            b'"' => self.parse_string().map(JsonValue::String),
            b'[' => self.parse_array(),
            b'{' => self.parse_object(),
            b'-' | b'0'..=b'9' => self.parse_number(),
            c => Err(JsonError::new(
                format!("意外的字符 '{}', 期望 JSON 值", c), self.pos)),
        }
    }
}
```

**递归下降解析器**：每个语法规则对应一个解析函数，它们相互递归调用。

## 4. 数字解析 — 最微妙的部分

```rust
fn parse_number(&mut self) -> JsonResult<JsonValue> {
    let start = self.pos;

    // 1) 可选负号
    if self.input[self.pos] == b'-' { self.pos += 1; }

    // 2) 整数部分：可以是 "0" 或 "1-9" + 数字
    if c == b'0' {
        self.pos += 1;
        // JSON 禁止前导零：01, 00.5 都是非法的
        if next.is_ascii_digit() { return error; }
    } else {
        while self.input[self.pos].is_ascii_digit() { self.pos += 1; }
    }

    // 3) 可选小数部分
    if self.input[self.pos] == b'.' {
        self.pos += 1;
        // 小数点后至少一位数字
        ...
        while self.input[self.pos].is_ascii_digit() { self.pos += 1; }
    }

    // 4) 可选指数部分
    if self.input[self.pos] == b'e' || self.input[self.pos] == b'E' {
        self.pos += 1;
        // 可选 +/-
        ...
        while self.input[self.pos].is_ascii_digit() { self.pos += 1; }
    }

    // 最后用 f64::parse 转换
    let num_str = str::from_utf8(&self.input[start..self.pos])?;
    let value: f64 = num_str.parse()?;
    Ok(JsonValue::Number(value))
}
```

**JSON 数字规范**（与 JavaScript 兼容）：
- 十进制，没有八进制/十六进制
- 可以负数：`-42`
- 可以小数：`3.14`
- 可以科学计数法：`1e10`, `2.5e-3`
- **不能**有前导零：`01`, `00.5` 非法
- **不能**有 NaN/Infinity

## 5. 字符串解析 — 转义序列处理

```rust
fn parse_string(&mut self) -> JsonResult<String> {
    self.expect_char(b'"')?;
    loop {
        match self.input[self.pos] {
            b'"' => return Ok(result),        // 结束
            b'\\' => {                        // 转义序列
                match esc {
                    b'"' => result.push('"'),
                    b'n' => result.push('\n'),
                    b'u' => {
                        // \uXXXX: 4位十六进制 Unicode
                        let hex_str = self.read_exact(4)?;
                        let code = u32::from_str_radix(hex_str, 16)?;
                        let ch = char::from_u32(code)?;
                        result.push(ch);
                    }
                    ...
                }
            }
            0x00..=0x1F => error("控制字符不允许"),
            _ => result.push(c as char),
        }
    }
}
```

**字符串转义支持**：
- 标准转义：`\"`, `\\`, `\/`, `\n`, `\r`, `\t`, `\b`, `\f`
- Unicode 转义：`\uXXXX`（例如 `\u4e16` → '世'）
- 控制字符必须转义，不能直接出现在字符串中

## 6. 值类型设计

```rust
pub enum JsonValue {
    Null,
    Bool(bool),
    Number(f64),        // JSON 只有一种数字类型
    String(String),
    Array(Vec<JsonValue>),
    Object(HashMap<String, JsonValue>),
}
```

**为什么 Number 用 f64？**
- JSON 规范要求：number 是 IEEE 754 double
- JavaScript 的 Number 也是 f64
- 整数精度限制：f64 可以精确表示 2^53 以内的整数

**为什么 Object 用 HashMap？**
- 键值对集合，适合哈希表
- 理论上 Object 中的 key 是无序的（尽管 JSON 序列化时一般按插入顺序）

## 7. 便捷访问方法

```rust
impl JsonValue {
    pub fn as_str(&self) -> Option<&str> { ... }
    pub fn as_f64(&self) -> Option<f64> { ... }
    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Number(n) if n.fract() == 0.0 && n.is_finite() => Some(*n as i64),
            _ => None,
        }
    }
    pub fn get(&self, path: &str) -> Option<&JsonValue> {
        // 点路径访问: val.get("user.name")
        for part in path.split('.') {
            current = current.as_object()?.get(part)?;
        }
        Some(current)
    }
}
```

## 8. 自定义错误类型

```rust
pub struct JsonError {
    pub message: String,
    pub position: usize,    // 错误发生的位置（字节偏移）
}
```

错误信息示例：
```
位置 42: 期望 ',', 发现 '}'
位置 10: 数字中意外的字符 'x'
位置 15: 无效的转义序列: \q
```

## 9. 测试结果

```
running 10 tests
test test_null     ... ok
test test_bool     ... ok
test test_number   ... ok
test test_string   ... ok
test test_array    ... ok
test test_object   ... ok
test test_nested   ... ok
test test_whitespace ... ok
test test_errors   ... ok
test test_display  ... ok
```

## 10. 关键技术点

| 概念 | 实现方式 |
|:-----|:---------|
| 解析策略 | 递归下降 (recursive descent) |
| 字符处理 | 直接用 `&[u8]` 字节，避免 UTF-8 开销 |
| 数字转换 | `str::parse::<f64>()` |
| 错误追踪 | 记录 `pos` 位置信息 |
| 前导零检测 | JSON 规范要求，特殊检查 `0` 后的数字 |
| Unicode 转义 | `u32::from_str_radix` → `char::from_u32` |

## 11. 与 serde_json 的对比

| 功能 | 本实现 | serde_json |
|:-----|:-------|:-----------|
| 代码量 | ~500 行 | ~20k 行 |
| 性能 | 基准 | ~5x 更快 |
| API 风格 | 返回 JsonValue enum | Deserialize trait + 零拷贝 |
| 类型映射 | 手动 match | 自动派生 |
| 正确性 | 常见场景 OK | RFC 8259 完全实现 |
| 特性 | 6 种类型 | 全 JSON 扩展 |

**核心差异**：serde_json 的 `deserialize` 是基于 trait 的，可以在解析时直接构造目标类型，避免中间 `JsonValue` 的分配。我们的实现在解析后还需要手动 match。

## 12. 可改进的方向

- ❌ 大数精度（目前 f64 会丢失精度）
- ❌ 性能优化（字节匹配 vs 字符串哈希）
- ❌ 原始字符串解析中的 \uXXXX surrogates
- ❌ 自定义 UTF-8 解码（目前依赖标准库）
