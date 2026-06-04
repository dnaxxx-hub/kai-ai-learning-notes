# 函数式编程第2课：类型系统与代数数据类型

## 1. 类型系统的作用

类型系统 = 编译器/解释器能在运行前检查出的"一类错误的集合"。

```
运行时错误 → 编译时错误（越早发现越好）
```

### 静态 vs 动态类型

| | 静态（Haskell/Rust） | 动态（Python/JS） |
|--|-------------------|-----------------|
| 检查时机 | 编译时 | 运行时 |
| 安全性 | 类型错误不编译 | 运行时才炸 |
| 灵活性 | 低 | 高 |
| 工具支持 | IDE 补全强 | 一般 |

## 2. 代数数据类型（ADT）

ADT = 通过"和"与"积"组合类型。

### 积类型（Product Type）— "且"

```haskell
-- 一个 Person 包含 name, age, email "全部"
data Person = Person String Int String
```

### 和类型（Sum Type）— "或"

```haskell
-- Bool 是 True 或 False
data Bool = True | False

-- Maybe 是有值或没有
data Maybe a = Just a | Nothing

-- Either：结果或错误
data Either a b = Left a | Right b
```

### Python 中的 ADT 模拟

```python
from dataclasses import dataclass
from typing import Union, Optional

# 积类型
@dataclass
class Person:
    name: str
    age: int
    email: str

# 和类型（Union）
Shape = Union['Circle', 'Rectangle', 'Triangle']  # 要么圆，要么矩形，要么三角形

@dataclass
class Circle:
    radius: float

@dataclass
class Rectangle:
    width: float
    height: float

# 用 Union 做模式匹配
def area(shape: Shape) -> float:
    match shape:
        case Circle(r):    return 3.14 * r * r
        case Rectangle(w, h): return w * h
```

## 3. 模式匹配（Pattern Matching）

Haskell：

```haskell
factorial :: Int -> Int
factorial 0 = 1                    -- 模式1：0
factorial n = n * factorial (n-1)  -- 模式2：任意数

-- Maybe 匹配
describeMaybe :: Maybe a -> String
describeMaybe (Just x) = "存在值"
describeMaybe Nothing  = "空值"
```

Python 3.10+ 的 match：

```python
def handle_result(result: Optional[int]) -> str:
    match result:
        case None:
            return "没有结果"
        case 0:
            return "结果是零"
        case n if n < 0:
            return f"负数: {n}"
        case n:
            return f"正数: {n}"
```

## 4. 多态

### 参数多态（Parametric Polymorphism）

函数对"任何类型"都生效：

```haskell
-- Haskell
length :: [a] -> Int        -- a 可以是任何类型
length []     = 0
length (x:xs) = 1 + length xs
```

### 特设多态（Ad-hoc Polymorphism）

对"有某种能力的类型"生效 — 通过 Typeclass 实现：

```haskell
-- 类型类约束：任何可以判相等的类型
elem :: Eq a => a -> [a] -> Bool
elem x []     = False
elem x (y:ys) = if x == y then True else elem x ys
```

## 5. Haskell 的 Typeclass 层级

```
                    Eq
                   /  \
                 Ord   Show
                 |     |
               Num  Read
               /|\
              / | \
            Int Float Double
            
Functor → Applicative → Monad
```

关键 Typeclass：

| Typeclass | 功能 | 关键方法 |
|-----------|------|---------|
| Eq | 判等 | ==, /= |
| Ord | 排序 | <, >, <=, compare |
| Show | 转字符串 | show |
| Read | 解析字符串 | read |
| Num | 数值运算 | +, -, *, fromInteger |
| Functor | 可映射 | fmap / <$> |
| Applicative | 可应用 | pure, <*> |
| Monad | 可绑定 | >>=, return |

## 6. Python 的类型注解——静态类型接近

```python
from typing import TypeVar, Generic, Optional, List

T = TypeVar('T')

class Maybe(Generic[T]):
    """Haskell 的 Maybe 在 Python 的模拟"""
    def __init__(self, value: Optional[T] = None):
        self._value = value
    
    def bind(self, func):
        """>>= 操作符"""
        if self._value is None:
            return Maybe[T]()
        return func(self._value)
    
    def map(self, func):
        """fmap / <$>"""
        if self._value is None:
            return Maybe[T]()
        return Maybe(func(self._value))

# 使用
def safe_div(x: float, y: float) -> Maybe[float]:
    if y == 0:
        return Maybe()
    return Maybe(x / y)

result = Maybe(10).bind(lambda x: safe_div(x, 2))
```

---

**下一篇**: Monad 深度 — 从 Functor 到 Monad
