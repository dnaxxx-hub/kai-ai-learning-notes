# 编译原理第5课：语义分析与中间代码生成

## 语法指导的翻译

在解析的同时执行语义动作：每个产生式关联一段代码。

### 综合属性（Synthesized）
子节点→父节点传播。在归约时计算。
```
E → E1 + T    { E.val = E1.val + T.val }
```

### 继承属性（Inherited）
父节点→子节点传播。需要更复杂的求值顺序。
```
D → T id      { id.type = T.type }
```

## 符号表管理

```python
class SymbolTable:
    def __init__(self, parent=None):
        self.entries = {}
        self.parent = parent  # 作用域链
    
    def define(self, name, info):
        self.entries[name] = info
    
    def lookup(self, name):
        if name in self.entries:
            return self.entries[name]
        if self.parent:
            return self.parent.lookup(name)
        return None
```

## 类型检查

```python
def type_check(node, st):
    if node.kind == 'IntLit': return 'int'
    if node.kind == 'FloatLit': return 'float'
    if node.kind == 'BinOp':
        l = type_check(node.left, st)
        r = type_check(node.right, st)
        if l != r:
            raise TypeError(f"类型不匹配: {l} vs {r}")
        return l
    if node.kind == 'Id':
        return st.lookup(node.name)['type']
```

## 三地址码（TAC）

中间表示形式：每条指令最多一个运算符 + 三个地址。

```
t1 = a + b      # 二元运算
t2 = t1 * c     # 链式运算
x  = t2         # 赋值
if_false t1 goto L1  # 条件跳转
param x              # 函数参数
call f, 1            # 函数调用
```

### AST → TAC 生成器

```python
class TACGen:
    def __init__(self):
        self.temps = 0
        self.code = []
    
    def new_temp(self):
        self.temps += 1
        return f't{self.temps}'
    
    def gen(self, node):
        if node.kind == 'IntLit':
            return str(node.val)
        if node.kind == 'Id':
            return node.name
        if node.kind == 'BinOp':
            l = self.gen(node.left)
            r = self.gen(node.right)
            t = self.new_temp()
            self.code.append(f'{t} = {l} {node.op} {r}')
            return t
        if node.kind == 'Assign':
            val = self.gen(node.right)
            self.code.append(f'{node.left.name} = {val}')
            return val
```

## SSA（静态单赋值）

每个变量只赋值一次，通过 φ 函数合并控制流。

```
原程序:                      SSA:
  x = 1                       x1 = 1
  if cond:                    if cond:
      x = 2                       x2 = 2
  print(x)                    x3 = φ(x1, x2)
                              print(x3)
```

## 执行示例

```
输入: a = 3 + 4 * 5
AST: Assign(Id('a'), BinOp(+, Id('3'), BinOp(*, Id('4'), Id('5'))))

生成的 TAC:
  t1 = 4 * 5
  t2 = 3 + t1
  a = t2
```

### 完整示例
```python
# 解析 a = 3 + 4 * 5
ast = ASTNode('Assign', 'a', 
    ASTNode('BinOp', '+', 
        ASTNode('IntLit', 3),
        ASTNode('BinOp', '*',
            ASTNode('IntLit', 4),
            ASTNode('IntLit', 5))))

gen = TACGen()
gen.gen(ast)
for inst in gen.code:
    print(inst)
# 输出:
# t1 = 4 * 5
# t2 = 3 + t1
# a = t2
```

## 关键总结
- 语法制导翻译 = 解析 + 语义动作
- 符号表实现作用域链
- TAC 是编译器中间表示的核心
- SSA 简化了优化分析
