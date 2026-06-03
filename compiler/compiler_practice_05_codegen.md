# 编译器实战 05 — 代码生成 (AST → C)

## 概述
代码生成将经过语义分析的 AST 转换为 C 源代码。

## 设计

### 类型映射
| MiniLang | C |
|----------|---|
| int      | int |
| float    | double |
| bool     | int (0/1) |
| string   | const char* |

### print 函数
MiniLang 的 `print` 编译为自定义 `ml_print` 函数，根据参数类型调用 `printf`。

### 策略
- 递归遍历 AST，逐节点输出 C 代码字符串
- `visit_xxx` 模式，与语义分析一致
- 表达式节点返回 C 表达式字符串
- 语句节点输出 C 代码行

### fib 示例输出
```c
#include <stdio.h>
#include <stdbool.h>

void ml_print_int(int v) { printf("%d\\n", v); }
void ml_print_float(double v) { printf("%g\\n", v); }
void ml_print_bool(int v) { printf("%s\\n", v ? "true" : "false"); }
void ml_print_string(const char* v) { printf("%s\\n", v); }

int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main() {
    ml_print_int(fib(10));
    return 0;
}
```
