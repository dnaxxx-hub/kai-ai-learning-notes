# 编译器实战 06 — 完整演示

## 示例：Fibonacci
```minilang
func fib(n: int) -> int {
    if n <= 1 {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

print(fib(10));  // 输出 55
```

## 管道流程
```
源代码 → Lexer(Token流) → Parser(AST) → SemanticAnalyzer → CodeGen(C代码) → gcc → 可执行文件
```

## 扩展思路
1. **数组支持** — 添加 `[]` 语法
2. **结构体/类** — 编译为 C struct
3. **模块系统** — 多文件编译
4. **优化pass** — 常量折叠、死代码消除
5. **自举** — 用 MiniLang 写 MiniLang 编译器
