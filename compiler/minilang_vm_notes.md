# MiniLang VM 实战笔记 — 2026-05-24

## 概述
完成了一个完整的 MiniLang 编程语言虚拟机，包含 Lexer → Parser → AST → Interpreter（树遍历）全管线。

## 架构设计
- **Lexer**: 单字符前瞻，支持字符串/数字/标识符/关键字，嵌套块注释 `/* */`，行注释 `#`
- **Parser**: 递归下降 + precedence climbing（Pratt风格），30+ AST节点类型
- **Interpreter**: 树遍历执行，Environment链式作用域（闭包支持）
- **Runtime**: 内置函数（print, len, str, int），类型系统（number/string/bool/nil/list）

## 关键设计决策
1. **纯树遍历** — 没有实现字节码编译（复杂度已足够），但接口预留了扩展空间
2. **嵌套作用域** — Environment用dict链，闭包捕获整个环境链
3. **错误恢复** — 解释器遇到运行时错误抛出 RuntimeException（非崩溃）

## 语言特性
- 变量声明/赋值
- 基本运算（+ - * / %）和比较（== != > < >= <=）
- 逻辑运算（and or not）带短路求值
- 控制流（if/else, while, for）
- break/continue
- 函数定义和递归调用（支持斐波那契）
- 闭包
- list字面量
- 字符串（支持转义字符）
- 注释（// 单行, /* */ 嵌套块注释）

## 测试覆盖
55个测试全部通过：
- Lexer: 10个（标识符、数字、字符串、转义、运算符、关键字、行号、注释）
- Parser: 16个（变量、函数、if/else、while、for、列表、逻辑、优先级）
- Interpreter: 29个（算术、比较、逻辑、字符串、list、变量、函数、闭包、循环、错误）

## 文件
- `minilang_vm.py` — 主实现（50KB），含REPL
- `test_minilang_vm.py` — 测试（18KB）
