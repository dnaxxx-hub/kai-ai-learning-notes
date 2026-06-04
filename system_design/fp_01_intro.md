# 函数式编程第1课：函数式思维入门

## 1. 什么是函数式编程？

**核心原则**：把计算看作数学函数的求值，避免状态变化和可变数据。

### 三大铁律
1. **纯函数（Pure Function）**：相同输入永远返回相同输出，无副作用
2. **不可变（Immutability）**：数据一旦创建，永不修改
3. **声明式（Declarative）**：描述"做什么"而非"怎么做"

### 命令式 vs 函数式

| 场景 | 命令式 | 函数式 |
|------|--------|--------|
| 数组求和 | 循环累加变量 | `reduce(add, arr)` |
| 过滤偶数 | if 判断追加 | `filter(is_even, arr)` |
| 数据变形 | 原地修改 | `map(f, arr)` |

## 2. 核心概念

### 高阶函数（Higher-Order Function）
函数可以当参数传、当返回值给：

```python
from functools import reduce

# map: 变换每个元素
squared = list(map(lambda x: x**2, [1, 2, 3]))  # [1, 4, 9]

# filter: 过滤
evens = list(filter(lambda x: x % 2 == 0, [1, 2, 3, 4]))

# reduce: 归约
total = reduce(lambda a, b: a + b, [1, 2, 3, 4])  # 10
```

### 柯里化（Currying）
多参数函数转成单参数函数链：

```python
# 非柯里化
def add(a, b, c):
    return a + b + c

# 柯里化版
def add(a):
    def with_b(b):
        def with_c(c):
            return a + b + c
        return with_c
    return with_b

add(1)(2)(3)  # 6

# 好处：偏应用
add5 = add(5)
add5(2)(3)  # 10
```

Python 中可以用 `functools.partial` 实现：

```python
from functools import partial

def power(base, exp):
    return base ** exp

square = partial(power, exp=2)
cube = partial(power, exp=3)

square(5)  # 25
cube(5)    # 125
```

## 3. 不可变数据结构

```python
# ❌ 命令式（可变）
items = [1, 2, 3, 4]
items.append(5)  # 修改原列表

# ✅ 函数式（不可变）
items = (1, 2, 3, 4)  # 元组不可变
new_items = items + (5,)  # 返回新元组
```

## 4. Haskell 速览（函数式语言的代表）

```haskell
-- 函数定义
square :: Int -> Int
square x = x * x

-- 高阶函数
map square [1,2,3,4]  -- [1,4,9,16]

-- 惰性求值
fibs = 0 : 1 : zipWith (+) fibs (tail fibs)
take 10 fibs  -- [0,1,1,2,3,5,8,13,21,34]
```

### 惰性求值（Lazy Evaluation）
表达式只在需要时才求值。在 Python 中体现为生成器：

```python
# 惰性
def fibs():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fs = fibs()
first_10 = [next(fs) for _ in range(10)]
```

## 5. Python 中的函数式工具

| 工具 | 用途 |
|------|------|
| `map()` | 变换序列 |
| `filter()` | 过滤序列 |
| `reduce()` | 归约序列（functools） |
| `partial()` | 偏函数 |
| `operator` 模块 | `add/sub/mul` 等操作函数 |
| `itertools` 模块 | `chain/zip_longest/groupby` |
| `functools.lru_cache` | 记忆化/缓存 |
| 推导式 | 更 Pythonic 的 map+filter |

## 6. 实际例子：数据处理管线

```python
from functools import reduce
from operator import add

data = [3, 7, 2, 9, 4, 6, 1, 8]

# 函数式管线：取偶数→平方→求和
result = reduce(
    add,
    map(lambda x: x**2,
        filter(lambda x: x % 2 == 0, data))
)  # 4 + 16 + 36 + 64 = 120

# 用推导式更易读（Pythonic）
result = sum(x**2 for x in data if x % 2 == 0)
```

---

**下一篇**: 类型系统基础 — ADT/多态/Typeclass
