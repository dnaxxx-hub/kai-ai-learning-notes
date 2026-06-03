# 编译器实战 02 — 抽象语法树 (AST)

## 概述
AST 是源代码的树形中间表示，Parser 将 Token 流转换为 AST，后续所有编译阶段都在 AST 上操作。

## 节点设计
所有节点继承自 `ASTNode`，包含 `pos` (源代码位置)。

### 表达式节点
- `NumberLiteral` — 整数/浮点数
- `StringLiteral` — 字符串
- `BoolLiteral` — true/false
- `Identifier` — 变量引用
- `BinaryOp` — 二元运算 (+ - * / == != < > <= >= && ||)
- `UnaryOp` — 一元运算 (! -)
- `Assign` — 赋值
- `Call` — 函数调用

### 语句节点
- `VarDecl` — 变量声明
- `ExprStmt` — 表达式语句
- `If` — if-else
- `While` — while 循环
- `Return` — return 语句
- `Block` — 语句块

### 顶层结构
- `Function` — 函数定义 (参数、返回类型、body)
- `Program` — 程序根节点 (函数列表)

### PrettyPrinter
`ASTPrinter` 将 AST 格式化为可读的树形文本，用于调试。
