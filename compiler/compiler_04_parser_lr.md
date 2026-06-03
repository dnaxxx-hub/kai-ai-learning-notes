# 编译原理第4课：LR(1)/LALR/运算符优先级

## 自顶向下 vs 自底向上

LL(1) 是自顶向下解析，从起始符号开始推导。
LR 是自底向上解析，从 Token 流开始归约到起始符号。

| 特性 | LL(1) | LR(1) |
|------|-------|-------|
| 方向 | 自顶向下（推导） | 自底向上（归约） |
| 表大小 | 小（N×T） | 大（状态×T） |
| 文法类 | LL(1)文法 | LR(1)文法（更大） |
| 实现 | 递归下降（手写友好） | 表驱动（自动生成） |

## LR 解析核心概念

### LR(0) 项
一个 LR(0) 项是带一个点的产生式：`A → α·β`
- 点前 = 已读部分
- 点后 = 待读部分
- `A → α·` 称为归约项（reduce item）

### 状态构建
```
CLOSURE(I):
    重复直到稳定:
        对 I 中每个 `A → α·Bβ`:
            对所有产生式 `B → γ`:
                加 `B → ·γ` 到 I

GOTO(I, X):
    对 I 中每个 `A → α·Xβ`:
        加 `A → αX·β` 到 CLOSURE
```

### 移进-归约冲突
```
状态 s: 
    A → α·      (归约项)
    B → β·aγ    (移进项，下一个是 a)
    
如果 a ∈ Follow(A)，则移进和归约都可选 → 冲突
```

## SLR(1)、LR(1)、LALR(1)

### SLR(1) — 最简版
- 用 Follow(A) 解决归约冲突
- 归约 A → α 只有在下一个 Token ∈ Follow(A) 时才归约
- 表最小，但冲突多

### LR(1) — 完整版
- LR(1) 项 = LR(0)项 + 展望符（lookahead）: `[A → α·β, a]`
- 展望符精确指明何时归约
- 表最大（状态数 ≈ LR(0) × 符号数）

### LALR(1) — 最佳平衡
- 合并 LR(1) 的同心项（core 相同但 lookahead 不同的状态）
- 表大小 ≈ LR(0)，解析能力 ≈ LR(1)
- Yacc/Bison/Gramma 使用的算法

## 运算符优先级解析

### Precedence Climbing（常用手写方案）
```python
def parse_expression(prec=0):
    left = parse_primary()
    while next_op and prec_of(next_op) >= prec:
        op = consume()
        right = parse_expression(prec_of(op) + 1)
        left = ASTNode(op, left, right)
    return left
```

### Shunting Yard（中缀→后缀）
```
数字 → 输出栈
运算符 → 弹出优先级≥它的到输出栈，再入栈
( → 入栈
) → 弹出直到 (
```

## 完整 LR 解析器实现

```python
class LRParser:
    def __init__(self):
        # 文法: E → E + T | T, T → id
        self.action = {
            0: {'id': ('s', 3), 'EOF': None},  # s=shift
            1: {'+': ('s', 4), 'EOF': ('r', 'E→T')},
            2: {'+': ('r', 'T→id'), 'EOF': ('r', 'T→id')},
            3: {'id': ('s', 3), 'EOF': None},
            4: {'id': ('s', 3), 'EOF': None},
            5: {'+': ('s', 4), 'EOF': ('r', 'E→E+T')},
        }
        self.goto = {0: {'E': 1, 'T': 2}, 3: {'E': 5, 'T': 2}}
    
    def parse(self, tokens):
        stack = [0]
        i = 0
        while True:
            state = stack[-1]
            tok = tokens[i] if i < len(tokens) else 'EOF'
            act = self.action[state].get(tok)
            if not act:
                raise SyntaxError(f"在状态{state}遇到{tok}")
            kind, val = act
            if kind == 's':
                stack.append(tok); stack.append(val)
                i += 1
            elif kind == 'r':
                lhs, rhs = val.split('→')
                n = len(rhs.split()) * 2
                for _ in range(n): stack.pop()
                top = stack[-1]
                stack.append(lhs); stack.append(self.goto[top][lhs])
                if lhs == 'E\'': return True
```

## 关键总结
- LR(1) 是工业级解析器的基础
- LALR(1) 是时间-空间的最优平衡
- Precedence Climbing 适合手写表达式解析
- Yacc/Bison = LALR(1) 表生成器
