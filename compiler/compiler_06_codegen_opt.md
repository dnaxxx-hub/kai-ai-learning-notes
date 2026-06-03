# 编译原理第6课：代码生成与优化

## 编译器后端概览

```
TAC → 指令选择 → 寄存器分配 → 指令调度 → 目标代码
```

## 指令选择

### 树覆盖（Tree Tiling）
将 IR 节点树用目标指令的模式瓦片覆盖。

```
TAC: t = a + b
x86: MOV eax, [a]     # 载入 a
     ADD eax, [b]     # 加 b
     MOV [t], eax     # 存回 t
```

## 寄存器分配

### 图着色（Graph Coloring）
1. 构建活跃变量干涉图（节点=变量，边=同时活跃的变量）
2. 用 K 种颜色着色（K=物理寄存器数）
3. 着不上色的变量→溢出到内存

```python
class RegAlloc:
    def __init__(self, colors=4):
        self.colors = colors
        self.interference = {}  # var → set of vars
    
    def add_edge(self, a, b):
        self.interference.setdefault(a, set()).add(b)
        self.interference.setdefault(b, set()).add(a)
    
    def color(self):
        result = {}
        stack = []
        # 简化：依次移除度数<colors的节点
        g = {v: set(n) for v, n in self.interference.items()}
        while g:
            # 找度数<colors的节点
            candidates = [v for v, n in g.items() if len(n) < self.colors]
            if not candidates:
                v = max(g, key=lambda x: len(g[x]))  # 溢出候选
            else:
                v = candidates[0]
            stack.append(v)
            del g[v]
            for n in g.values():
                n.discard(v)
        # 反向着色
        colors = ['r', 'g', 'b', 'c']
        while stack:
            v = stack.pop()
            used = {result[n] for n in self.interference[v] if n in result}
            for c in colors[:self.colors]:
                if c not in used:
                    result[v] = c
                    break
            if v not in result:
                result[v] = 'spill'  # 溢出
        return result
```

### 线性扫描
更快的在线算法，一次线性扫描活跃区间。

```
按变量活跃区间起点排序
遍历区间:
    释放已结束区间的寄存器
    分配一个空闲寄存器（或溢出一个冲突的）
```

## 基本优化

### 窥孔优化（Peephole）
滑动窗口（通常2-3条指令）匹配局部模式。

| 模式 | 替换 |
|------|------|
| `MOV r, r` | 删除 |
| `JMP L; L:` | 删除跳转 |
| `ADD 0` | 删除 |
| `MUL 2` | `SHL 1` |
| `PUSH arg; POP dst` | `MOV dst, arg` |

### 常量折叠
```
3 + 5 → 8
2 * 10 → 20
```

### 常量传播
```
x = 5; y = x + 3 → y = 8
```

### 死代码消除
删除赋值后未被读取的变量。

### 公共子表达式消除（CSE）
```python
# 前                    # 后
a = b * c               t = b * c
d = b * c               a = t
                        d = t
```

## TAC → 伪汇编 完整示例

```python
class CodeGen:
    def __init__(self):
        self.asm = []
    
    def gen(self, tac):
        if tac.op == '=':
            r = self.gen_expr(tac.right)
            self.asm.append(f'  MOV [{tac.left}], {r}')
    
    def gen_expr(self, expr):
        if expr.is_const:
            return f'#{expr.val}'  # 立即数
        if expr.is_var:
            return f'[{expr.name}]'  # 内存
        if expr.is_binop:
            r1 = self.gen_expr(expr.left)
            r2 = self.gen_expr(expr.right)
            op_map = {'+': 'ADD', '-': 'SUB', '*': 'MUL'}
            self.asm.append(f'  MOV R0, {r1}')
            self.asm.append(f'  {op_map[expr.op]} R0, {r2}')
            return 'R0'
```

## 编译器流水线回顾

```
源码
  ↓ 词法分析
Token 流
  ↓ 语法分析 (LL/LR)
AST
  ↓ 语义分析
带类型 AST + 符号表
  ↓ IR 生成
TAC / SSA
  ↓ 优化 (CF/CP/DCE/CSE/Peephole)
优化 IR
  ↓ 指令选择
汇编指令流
  ↓ 寄存器分配 + 指令调度
目标代码
```

## 关键总结
- 指令选择：tree tiling 模式匹配
- 寄存器分配：图着色或线性扫描
- 窥孔优化：窗口模式匹配，简单但有效
- 常量折叠+传播：最基础的编译时求值
- 死代码消除：清理无用赋值
- CSE：避免重复计算
