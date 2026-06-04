# λ演算基础：计算的本质

> λ演算（Lambda Calculus）是"计算的数学形式化"——所有编程语言的基础抽象。

## 1. λ演算的语法

只有三样东西：

```
变量：   x, y, z, ...
抽象：   λx.M  — "接受参数x，返回M"
应用：   M N   — "将M应用到N上"
```

这就是全部。图灵完备。

### 语法树示例

```python
# λx.x  (恒等函数)
AST: Lambda(var='x', body=Var('x'))

# λx.λy.x  (第一个参数，K组合子)
AST: Lambda(var='x', body=Lambda(var='y', body=Var('x')))

# (λx.x) y  (将恒等函数应用在y上)
AST: Apply(func=Lambda('x', Var('x')), arg=Var('y'))
```

## 2. Python模拟λ演算

```python
from dataclasses import dataclass
from typing import Union

# AST定义
@dataclass
class Var:
    name: str

@dataclass  
class Lam:
    param: str    # 参数名
    body: 'Term'  # 函数体

@dataclass
class App:
    func: 'Term'  # 函数
    arg: 'Term'   # 参数

Term = Union[Var, Lam, App]

# 辅助函数
def pprint(term):
    """打印λ表达式"""
    match term:
        case Var(name):     return name
        case Lam(p, b):     return f"λ{p}.{pprint(b)}"
        case App(f, a):     return f"({pprint(f)} {pprint(a)})"
```

## 3. 归约规则

### α-等价（Alpha Equivalence）

```
λx.x  ≡  λy.y  — 参数名不重要，只要绑定了正确的变量
```

规则：把绑定的变量名改成另一个未使用的名字。

### β-归约（Beta Reduction）— 核心计算

```
(λx.M) N  →  M[x := N]  — "把M中所有自由出现的x替换成N"
```

```python
def beta_reduce(term: Term) -> Term:
    """β-归约：应用一次"""
    match term:
        case App(Lam(param, body), arg):
            return substitute(body, param, arg)
        case _:
            return term  # 不是redex，无法归约

def substitute(term, var_name, replacement):
    """替换：term中所有自由出现的var_name替换为replacement"""
    match term:
        case Var(name):
            return replacement if name == var_name else term
        case Lam(param, body):
            if param == var_name:
                return term  # 绑定的，不替换
            # 避免变量捕获（α转换）
            if isinstance(replacement, Var) and param == replacement.name:
                new_param = fresh_name(param)
                new_body = substitute(body, param, Var(new_param))
                return Lam(new_param, substitute(new_body, var_name, replacement))
            return Lam(param, substitute(body, var_name, replacement))
        case App(f, a):
            return App(substitute(f, var_name, replacement),
                       substitute(a, var_name, replacement))

# 示例
identity = Lam('x', Var('x'))  # λx.x
applied = App(identity, Var('y'))
# (λx.x) y  →  y
```

### η-变换（Eta Conversion）

```
λx.(M x)  →  M  当x在M中不是自由变量时
```

简化"包装了一层"的函数。

## 4. Church编码：用函数表示数据

### Church布尔

```python
# TRUE = λx.λy.x
TRUE = Lam('x', Lam('y', Var('x')))

# FALSE = λx.λy.y  
FALSE = Lam('x', Lam('y', Var('y')))

# IF = λb.λt.λf.b t f
IF = Lam('b', Lam('t', Lam('f', App(App(Var('b'), Var('t')), Var('f')))))

def church_bool(b):
    """把Church布尔转化为Python布尔"""
    # TRUE(x)(y) = x, FALSE(x)(y) = y
    return b(True)(False)
```

### Church自然数

```
0 = λf.λx.x          — f应用0次
1 = λf.λx.f x        — f应用1次
2 = λf.λx.f (f x)    — f应用2次
n = λf.λx.f^n x      — f应用n次
```

```python
def church_num(n):
    """生成Church数字n"""
    return Lam('f', Lam('x', 
        App.n_times(Var('f'), n, Var('x'))  # f应用n次
    ))

def un_church(n):
    """Church数转Python int"""
    def increment(x): return x + 1
    return n(increment)(0)

# 加法: PLUS = λm.λn.λf.λx.m f (n f x)
PLUS = Lam('m', Lam('n', Lam('f', Lam('x',
    App(App(Var('m'), Var('f')), 
        App(App(Var('n'), Var('f')), Var('x')))
))))
```

## 5. Y组合子——在不支持递归的语言中实现递归

```
Y = λf.(λx.f (x x)) (λx.f (x x))
```

```python
# Y组合子的神奇性质：Y f = f (Y f)
# 这是"不动点定理"的计算机科学版本

def Y(f):
    """Python中的Y组合子"""
    def g(x):
        return f(lambda *args: x(x)(*args))
    return g(g)

# 使用Y组合子实现阶乘（没有def recursion）
fact = Y(lambda f: lambda n: 1 if n == 0 else n * f(n-1))
```

## 6. λ演算的意义

1. **最小的图灵完备语言** — 三行语法规则，涵盖所有可计算函数
2. **函数式语言的数学基础** — Haskell/ML 的原理就是λ演算+类型
3. **编译器的基础** — λ演算的归约策略（Call-by-Name / Call-by-Value）决定语言的语义
4. **Church-Turing Thesis** — λ演算能力等价于图灵机

---

**下一篇**: 简单类型λ演算 — 给λ添加类型
