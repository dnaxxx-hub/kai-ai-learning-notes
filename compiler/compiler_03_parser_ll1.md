# 编译原理 第3课：语法分析(上) — CFG/递归下降/LL(1)

> 从 Token 流构建抽象语法树（AST），理解编译器前端最核心的阶段。
> 学完后：能从 Token 流生成 AST，理解 LL(1) 解析表的构建与使用。

---

## 关键概念

### 语法分析（Parsing / Syntax Analysis）

语法分析是编译器的第二阶段——将词法分析器输出的 **Token 流** 转换为 **抽象语法树（AST）**。

```
源代码: "3 + 4 * 5"
         ↓ 词法分析
Token流: [NUM(3), PLUS, NUM(4), STAR, NUM(5)]
         ↓ 语法分析
    AST:     (+)
            /   \
          (3)   (*)
               /   \
             (4)   (5)
```

AST 与解析树（Parse Tree / CST）的区别：
- **解析树**：包含所有中间非终结符节点，信息冗余
- **AST**：只保留对语义分析有意义的结构，去掉括号、分隔符等辅助信息

### 解析策略分类

| 策略 | 方向 | 构建方式 | 代表算法 | 代表 |
|------|------|----------|----------|------|
| **自顶向下** | 从起始符号展开到 Token | 预测/递归 | 递归下降、LL(1) | 手写解析器 |
| **自底向上** | 从 Token 归约到起始符号 | 移进-归约 | LR(1)、LALR(1) | Yacc、Bison |

---

## 1. 上下文无关文法（Context-Free Grammar, CFG）

### 定义

CFG 是一个四元组：**G = (N, Σ, P, S)**

| 符号 | 名称 | 含义 |
|------|------|------|
| N | 非终结符集合 | 可以继续展开的符号（如 `Expr`, `Term`） |
| Σ | 终结符集合 | 不可再展开的符号（即 Token，如 `NUM`, `PLUS`） |
| P | 产生式集合 | 展开规则，形如 `A → α`，其中 A∈N, α∈(N∪Σ)* |
| S | 起始符号 | S∈N，文法的根 |

### 产生式示例

```
E → E + T   # 表达式可以是一个表达式加一个项
E → T       # 表达式也可以只是一个项
T → T * F   # 项可以是一个项乘一个因子
T → F       # 项也可以只是一个因子
F → NUM     # 因子可以是一个数字
F → ( E )   # 因子也可以是一个括号表达式
```

**终结符**：`NUM`, `+`, `*`, `(`, `)`  
**非终结符**：`E`, `T`, `F`  
**起始符号**：`E`

### 推导（Derivation）

从起始符号开始，反复应用产生式，直到没有非终结符：

```
E ⇒ E + T         (E → E + T)
  ⇒ T + T         (E → T)
  ⇒ F + T         (T → F)
  ⇒ NUM + T       (F → NUM)
  ⇒ NUM + T * F   (T → T * F)
  ⇒ NUM + F * F   (T → F)
  ⇒ NUM + NUM * F (F → NUM)
  ⇒ NUM + NUM * NUM (F → NUM)
```

**最左推导**（Leftmost Derivation）：每一步都替换最左边的非终结符。  
**最右推导**（Rightmost Derivation）：每一步都替换最右边的非终结符。

### 二义性（Ambiguity）

如果同一个句子有多棵不同的解析树，文法就是二义的。

```
E → E + E | E * E | NUM
```

对 `3 + 4 * 5`，两棵解析树：

```
    (+)               (*)
   /   \             /   \
 (3)   (*)         (+)   (5)
       /  \       /   \
     (4)  (5)   (3)   (4)
```

左树：`3 + (4 * 5) = 23`  
右树：`(3 + 4) * 5 = 35`

**解决方案**：引入优先级层次结构（将运算符分层）：

```
E → E + T | T     # + 的优先级低
T → T * F | F     # * 的优先级高
F → NUM | ( E )
```

这样 `3 + 4 * 5` 只有一种解析方式。

---

## 2. 递归下降解析（Recursive Descent Parsing）

### 核心思想

**每个非终结符对应一个解析函数**，函数内部根据当前 Token 选择对应的产生式展开。

```
Parser:
  parse_E() -> 根据当前 token 决定用 E → E+T 还是 E → T
  parse_T() -> 根据当前 token 决定用 T → T*F 还是 T → F
  parse_F() -> 根据当前 token 决定用 F → NUM 还是 F → (E)
```

### 优点

- ✅ 手写实现，精细控制错误恢复
- ✅ 直观易懂，产生式 → 函数一一对应
- ✅ 可加入任意逻辑（如运算符优先级增强）
- ✅ 绝大多数工业编译器使用（Clang, GCC, Rust, Go, Python）

### 问题：左递归

如果产生式是左递归的，递归下降解析会直接 **无限递归**：

```
E → E + T    # parse_E() 的第一行调用 parse_E()，死循环！
```

```python
def parse_E():
    left = parse_E()      # ← 无限递归！
    token = expect(PLUS)
    right = parse_T()
    return AST('+', left, right)
```

### 解决方案：消除左递归 + 改写文法

---

## 3. 左递归消除（Left Recursion Elimination）

### 直接左递归

形如 `A → A α | β`

通用消除模式（引入一个新非终结符处理**剩余部分**）：

```
消除前:
  A → A α | β

消除后:
  A  → β A'
  A' → α A' | ε
```

### 例子：算术表达式

消除前:
```
E → E + T | T
T → T * F | F
F → NUM | ( E )
```

消除后:
```
E  → T E'
E' → + T E' | ε     # 匹配零个或多个 "+ T"
T  → F T'
T' → * F T' | ε     # 匹配零个或多个 "* F"
F  → NUM | ( E )
```

验证：解析 `3 + 4 * 5`

```
E
→ T E'
→ F T' E'
→ NUM T' E'                   # 匹配 NUM(3)，T' → ε
→ NUM + T E'                  # 匹配 PLUS, 进入 T
→ NUM + F T' E'
→ NUM + NUM T' E'             # 匹配 NUM(4)
→ NUM + NUM * F T' E'         # 匹配 STAR
→ NUM + NUM * NUM T' E'       # 匹配 NUM(5), T' → ε, E' → ε
→ NUM + NUM * NUM             ✅ 成功！
```

### 算法：通用左递归消除

```
对于每个非终结符 A:
  将 A → A α₁ | A α₂ | ... | β₁ | β₂ | ... 改写为:
    A  → β₁ A' | β₂ A' | ...
    A' → α₁ A' | α₂ A' | ... | ε
```

---

## 4. First 集与 Follow 集

### 为什么需要 First/Follow？

递归下降解析需要在每个非终结符函数中，根据**当前 Token** 决定用哪个产生式。
First 和 Follow 集就是用来做这个"决策"的工具。

### First 集：一个符号串可能开头的终结符集合

**定义**：`First(α)` = 所有可以从 α 推导出的句子的**第一个终结符**的集合。

**计算规则（对产生式 X → Y₁ Y₂ ... Yₙ）**：
1. 如果 Y₁ 是终结符 a，则 a ∈ First(X)
2. 如果 Y₁ 是非终结符，则 First(Y₁) 中所有非 ε 元素 ∈ First(X)
3. 如果 Y₁ ⇒* ε（可以推导出空串），则继续看 Y₂
4. 如果所有 Yᵢ ⇒* ε，则 ε ∈ First(X)

**示例**：
```
First(NUM) = { NUM }
First(+)   = { + }
First(E)   = First(T)  因为 E → T E'，所以看 T 的 First
First(T)   = First(F)  因为 T → F T'
First(F)   = { NUM, ( } 因为 F → NUM | ( E )
```

### Follow 集：在推导中紧跟在一个非终结符后面的终结符集合

**定义**：`Follow(A)` = 在某些句型中紧跟在 A 之后的终结符集合。

**计算规则**：
1. `$`（输入结束标记）∈ Follow(S)，其中 S 是起始符号
2. 对产生式 A → α B β：First(β) 中非 ε 元素 ∈ Follow(B)
3. 对产生式 A → α B 或 A → α B β 且 ε ∈ First(β)：Follow(A) ∈ Follow(B)

**示例（对消除左递归后的文法）**：
```
产生式:
E  → T E'
E' → + T E' | ε
T  → F T'
T' → * F T' | ε
F  → NUM | ( E )

计算 Follow:
1. Follow(E) = { $, ) }    # E 是起始符号, F → (E) 中 ) 跟在 E 后
2. Follow(E') = Follow(E) = { $, ) }  # E → T E' 中 E' 产生式内最后
3. Follow(T) = First(E') ∪ Follow(E')  # E' → + T E' 中 E' 之后; E' 可 ε
   = { + } ∪ { $, ) } = { +, $, ) }
4. Follow(T') = Follow(T) = { +, $, ) }  # T → F T'
5. Follow(F) = First(T') ∪ Follow(T)  # T' → * F T' 中 T' 之后; T' 可 ε
   = { * } ∪ { +, $, ) } = { *, +, $, ) }
```

### First/Follow 的手感理解

- **First 集**：告诉我"这个非终结符能生成什么开头的东西"
- **Follow 集**：告诉我"当这个非终结符可以生成空串，我要看什么来决定停下"

---

## 5. LL(1) 解析表

### LL(1) 的含义

| 字母 | 含义 |
|------|------|
| L | 从左到右扫描（Left-to-right） |
| L | 最左推导（Leftmost derivation） |
| 1 | 向前看 1 个 Token（1 token lookahead） |

LL(1) 文法：用 1 个 lookahead Token 就能无歧义地选择产生式的文法。

### 构建解析表

解析表是一个二维表：行 = 非终结符，列 = 终结符，值 = 要用的产生式。

构建算法，对每个产生式 `A → α`：
1. 对每个 `a ∈ First(α)`（a ≠ ε）：`Table[A][a] = A → α`
2. 如果 `ε ∈ First(α)`：对每个 `b ∈ Follow(A)`：`Table[A][b] = A → α`

### 示例：构建算术表达式的 LL(1) 解析表

| 非终结符 | NUM | ( | ) | + | * | $ |
|---------|-----|---|---|---|---|---|
| E | E→T E' | E→T E' | | | | |
| E' | | | E'→ε | E'→+TE' | | E'→ε |
| T | T→F T' | T→F T' | | | | |
| T' | | | T'→ε | T'→ε | T'→*FT' | T'→ε |
| F | F→NUM | F→(E) | | | | |

验证步骤：
1. 初始化栈：`[E, $]`（起始符号 + 结束标记）
2. 看当前 Token，查表，弹出非终结符、压入产生式右部
3. 如果栈顶是终结符，与 Token 匹配则弹出并前进

```
栈          输入              动作
[E, $]      NUM + NUM * NUM $  查表: E → T E'
[T, E', $]  NUM + NUM * NUM $  查表: T → F T'
[F, T', E', $]  NUM + ...     查表: F → NUM
[NUM, T', E', $] NUM + ...    匹配 NUM(3), 弹出, 前进Token
[T', E', $]  + NUM * NUM $    查表: T' → ε (因为 + ∈ Follow(T'))
[E', $]      + NUM * NUM $    查表: E' → + T E'
[+, T, E', $] + NUM * NUM $   匹配 PLUS, 弹出, 前进Token
[T, E', $]   NUM * NUM $      查表: T → F T'
[F, T', E', $]  NUM * NUM $   查表: F → NUM
[NUM, T', E', $] NUM * NUM $  匹配 NUM(4), 弹出, 前进Token
[T', E', $]  * NUM $          查表: T' → * F T'
[*, F, T', E', $] * NUM $     匹配 STAR, 弹出, 前进Token
[F, T', E', $]  NUM $         查表: F → NUM
[NUM, T', E', $] NUM $        匹配 NUM(5), 弹出, 前进Token
[T', E', $]  $                查表: T' → ε
[E', $]      $                查表: E' → ε
[$]          $                匹配 $ → ACCEPT ✅
```

---

## 6. Python 实现：递归下降解析器

### 完整代码

```python
#!/usr/bin/env python3
"""
LL(1) 递归下降解析器，解析算术表达式：
  3 + 4 * 5
生成 AST（抽象语法树）。

文法（消除左递归后）:
  E  → T E'
  E' → + T E' | ε
  T  → F T'
  T' → * F T' | ε
  F  → NUM | ( E )

Token 定义（简化，假设已由词法分析器产出）:
  NUM, PLUS, STAR, LPAREN, RPAREN, END
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional, Union


# ==================== Token 定义 ====================

class TokenType(Enum):
    NUM = auto()
    PLUS = auto()
    STAR = auto()
    LPAREN = auto()
    RPAREN = auto()
    END = auto()         # 输入结束标记 $


@dataclass
class Token:
    type: TokenType
    value: Union[str, int]
    def __repr__(self):
        return f"Token({self.type.name}, {self.value})"


# ==================== 词法分析器（简化版） ====================

class Lexer:
    """简单词法分析器：将字符串转为 Token 流"""
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
    
    def skip_whitespace(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
    
    def next_token(self) -> Token:
        self.skip_whitespace()
        if self.pos >= len(self.text):
            return Token(TokenType.END, '$')
        
        c = self.text[self.pos]
        
        if c.isdigit():
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                self.pos += 1
            return Token(TokenType.NUM, int(self.text[start:self.pos]))
        
        operators = {
            '+': TokenType.PLUS,
            '*': TokenType.STAR,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
        }
        if c in operators:
            self.pos += 1
            return Token(operators[c], c)
        
        raise SyntaxError(f"Unexpected character: {c!r} at position {self.pos}")
    
    def tokenize(self) -> List[Token]:
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.END:
                break
        return tokens


# ==================== AST 节点定义 ====================

class ASTNode:
    """抽象语法树节点基类"""
    pass


@dataclass
class NumNode(ASTNode):
    value: int
    def __repr__(self): return f"Num({self.value})"


@dataclass
class BinOpNode(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode
    def __repr__(self): return f"({self.left} {self.op} {self.right})"


# ==================== 递归下降解析器 ====================

class Parser:
    """
    LL(1) 递归下降解析器
    
    文法:
      E  → T E'
      E' → + T E' | ε
      T  → F T'
      T' → * F T' | ε
      F  → NUM | ( E )
    """
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0      # 当前处理的 Token 索引
    
    def peek(self) -> Token:
        """查看当前 Token（lookahead）"""
        return self.tokens[self.pos]
    
    def consume(self) -> Token:
        """消耗当前 Token，前进到下一个"""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok
    
    def expect(self, *types: TokenType) -> Token:
        """期望当前 Token 是指定类型之一，否则报错"""
        tok = self.peek()
        if tok.type not in types:
            expected = ', '.join(t.name for t in types)
            raise SyntaxError(
                f"Expected {expected}, got {tok.type.name}({tok.value!r}) "
                f"at position {self.pos}"
            )
        return self.consume()
    
    # ---- 产生式对应的解析函数 ----
    
    def parse(self) -> ASTNode:
        """解析入口：E  → T E'"""
        return self.parse_E()
    
    def parse_E(self) -> ASTNode:
        """
        E  → T E'
        
        先解析 T，然后用 E' 处理可能出现的 + T 序列
        """
        left = self.parse_T()
        # 注意：这里的 E' 实际上"吃掉"剩余的 + T 部分并组装成树
        return self.parse_E_prime(left)
    
    def parse_E_prime(self, left: ASTNode) -> ASTNode:
        """
        E' → + T E' | ε
        
        First(E') = { + }
        Follow(E') = { $, ) }
        """
        if self.peek().type == TokenType.PLUS:
            self.consume()                    # 吃掉 '+'
            right = self.parse_T()            # 解析 T
            node = BinOpNode('+', left, right)
            return self.parse_E_prime(node)   # 递归处理后续的 E'
        # ε: 什么也不做，直接返回 left
        return left
    
    def parse_T(self) -> ASTNode:
        """
        T  → F T'
        """
        left = self.parse_F()
        return self.parse_T_prime(left)
    
    def parse_T_prime(self, left: ASTNode) -> ASTNode:
        """
        T' → * F T' | ε
        
        First(T') = { * }
        Follow(T') = { +, $, ) }
        """
        if self.peek().type == TokenType.STAR:
            self.consume()                    # 吃掉 '*'
            right = self.parse_F()            # 解析 F
            node = BinOpNode('*', left, right)
            return self.parse_T_prime(node)   # 递归处理后续的 T'
        # ε
        return left
    
    def parse_F(self) -> ASTNode:
        """
        F  → NUM | ( E )
        
        First(F) = { NUM, ( }
        """
        if self.peek().type == TokenType.NUM:
            tok = self.consume()
            return NumNode(tok.value)
        elif self.peek().type == TokenType.LPAREN:
            self.consume()                    # 吃掉 '('
            node = self.parse_E()             # 递归解析括号内的表达式
            self.expect(TokenType.RPAREN)     # 确保有 ')'
            return node
        else:
            raise SyntaxError(
                f"Expected NUM or '(', got {self.peek().type.name} "
                f"at position {self.pos}"
            )


# ==================== 测试与使用 ====================

def expr_to_ast(text: str) -> ASTNode:
    """从表达式字符串到 AST 的完整流程"""
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    print(f"Token 流: {tokens}")
    parser = Parser(tokens)
    ast = parser.parse()
    return ast


def evaluate(node: ASTNode) -> int:
    """递归计算 AST 的值（用于验证解析正确性）"""
    if isinstance(node, NumNode):
        return node.value
    if isinstance(node, BinOpNode):
        left_val = evaluate(node.left)
        right_val = evaluate(node.right)
        if node.op == '+': return left_val + right_val
        if node.op == '*': return left_val * right_val
    raise ValueError(f"Unknown node: {node}")


def ast_to_str(node: ASTNode, indent: int = 0) -> str:
    """以缩进格式打印 AST"""
    prefix = "  " * indent
    if isinstance(node, NumNode):
        return f"{prefix}Num({node.value})"
    if isinstance(node, BinOpNode):
        return (f"{prefix}BinOp({node.op}):\n"
                f"{ast_to_str(node.left, indent + 1)}\n"
                f"{ast_to_str(node.right, indent + 1)}")
    return f"{prefix}Unknown"


# ==================== 运行测试 ====================

if __name__ == "__main__":
    test_cases = [
        "3 + 4 * 5",
        "3 * 4 + 5",
        "42",
        "1 + 2 + 3",
        "2 * 3 * 4",
        "(1 + 2) * 3",
        "10 + 20 * 30 + 40",
    ]
    
    for expr in test_cases:
        print(f"\n{'='*50}")
        print(f"表达式: {expr}")
        print(f"{'='*50}")
        try:
            ast = expr_to_ast(expr)
            print(f"\nAST 结构:")
            print(ast_to_str(ast))
            print(f"\n求值: {expr} = {evaluate(ast)}")
            print(f"Python eval: {eval(expr)}")  # 交叉验证
        except Exception as e:
            print(f"错误: {e}")
```

### 运行结果（预期）

```
==================================================
表达式: 3 + 4 * 5
==================================================
Token 流: [Token(NUM, 3), Token(PLUS, +), Token(NUM, 4), Token(STAR, *), Token(NUM, 5), Token(END, $)]

AST 结构:
BinOp(+):
  Num(3)
  BinOp(*):
    Num(4)
    Num(5)

求值: 3 + 4 * 5 = 23
Python eval: 23

==================================================
表达式: (1 + 2) * 3
==================================================
Token 流: [Token(LPAREN, (), Token(NUM, 1), Token(PLUS, +), Token(NUM, 2), Token(RPAREN, )), Token(STAR, *), Token(NUM, 3), Token(END, $)]

AST 结构:
BinOp(*):
  BinOp(+):
    Num(1)
    Num(2)
  Num(3)

求值: (1 + 2) * 3 = 9
Python eval: 9
```

---

## 7. LL(1) 文法的约束条件

一个文法要是 LL(1) 的，必须满足：

1. **无二义性**：每个句子只有一种解析方式
2. **无左递归**：不能有 `A → A α` 形式的产生式
3. **无左因子**（Left Factoring）：同一非终结符的多个产生式不能有相同的 First 开端

   ```
   错误: A → a B | a C    # 两个产生式都以 a 开头
   修复: A → a A' | ... 
         A' → B | C
   ```

4. **First 集与 Follow 集不冲突**：
   对每个非终结符 A，如果两个产生式 A → α 和 A → β 都需要 ε 处理：
   First(α) ∩ First(β) = ∅
   且如果 ε ∈ First(α)，那么 First(β) ∩ Follow(A) = ∅

---

## 8. 表驱动的 LL(1) 解析器（与递归下降的对比）

| 方式 | 优点 | 缺点 |
|------|------|------|
| **递归下降**（手写） | 灵活、错误恢复好、可读性高 | 需要手写每个非终结符 |
| **表驱动**（自动生成） | 通用、无需手写代码 | 错误消息差、改文法需重建表 |

实际工程中，**递归下降**是主流（LLVM Clang, GCC, Rust, Go, Swift 都用它）。

---

## 总结

```
文法设计
   ↓ 消除左递归 + 消除左因子
LL(1) 文法
   ↓ 计算 First/Follow 集
解析表 / 递归下降函数
   ↓ 驱动
AST 生成 ✓
```

**关键洞察**：语法分析的本质是**将线性 Token 流恢复为树形结构**。
- 递归下降：用函数调用栈隐式表示树结构
- 表驱动 LL(1)：用显式栈模拟推导过程
- 两者的核心都是：**根据 current token 决定下一步** — 这就是 LL(1) 中 "1" 的含义

**与词法分析器的关系**：词法分析器产出结构化 Token，语法分析器将这些 Token 组装成树。两者之间是**水到渠成**的关系——Token 流就是 CFG 的终结符输入。

---

## 下集预告

第4课：**语法分析(下)：LR(1)/LALR(1)/移进-归约**

- 自底向上解析的核心思想
- LR(1) 项集族和 LR 表
- SLR、LALR(1) 对比
- 运算符优先级解析（Pratt Parsing）
- 实际工程中的解析器选择
