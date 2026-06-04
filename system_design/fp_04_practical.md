# 函数式编程第4课：Python 函数式实战

## 1. 日常数据管线

```python
from functools import reduce, partial
from operator import add, mul, itemgetter
from itertools import chain, groupby

# 复杂数据处理 — 函数式风格
def process_transactions(users, orders):
    """
    场景：统计每个用户的订单总金额，过滤掉零金额，按金额降序
    """
    # 1. 关联用户和订单
    user_orders = chain.from_iterable(
        (user, order) for order in orders 
        if order['user_id'] == user['id']
    )
    
    # 2. 分组求和
    totals = reduce(
        lambda d, u: {**d, u['name']: sum(
            o['amount'] for o in orders 
            if o['user_id'] == u['id']
        )},
        users,
        {}
    )
    
    # 3. 过滤并排序
    return sorted(
        ((name, amt) for name, amt in totals.items() if amt > 0),
        key=itemgetter(1),
        reverse=True
    )
```

## 2. 函数组合（Composition）

```python
from functools import reduce

def compose(*funcs):
    """函数组合：f(g(x)) = (f ∘ g)(x)"""
    return reduce(lambda f, g: lambda x: f(g(x)), funcs)

def pipe(*funcs):
    """管道：x → f(x) → g(f(x))"""
    return reduce(lambda f, g: lambda x: g(f(x)), funcs)

# 使用
add_one = lambda x: x + 1
double = lambda x: x * 2
square = lambda x: x ** 2

# 先 double 再 add_one 再 square
transform = compose(square, add_one, double)
transform(3)  # square(add_one(double(3))) = (6+1)^2 = 49

# pipe 风格（从左到右）
process = pipe(
    lambda data: [x for x in data if x > 0],     # 过滤负数
    lambda data: map(lambda x: x ** 0.5, data),   # 开平方
    lambda data: sorted(data, reverse=True)[:5],  # Top 5
    list
)

process([3, -1, 16, -4, 9, 4, 25, 36])  # [6.0, 5.0, 4.0, 3.0, 2.0]
```

## 3. 惰性求值实战

```python
def lazy_range(n):
    """生成器的惰性特性"""
    i = 0
    while i < n:
        yield i
        i += 1

# 链式惰性操作（不会生成立即计算）
def process_large_dataset(big_data):
    chunked = chunk(big_data, 1000)           # 延迟
    filtered = filter(lambda c: len(c) > 0, chunked)  # 延迟  
    transformed = map(compute_features, filtered)      # 延迟
    result = reduce(merge_results, transformed)        # 按需消费
    return result

# 无限序列 + 惰性求值
def sieve():
    """埃拉托色尼筛法（惰性版）"""
    yield 2
    it = (n for n in range(3, 10**6, 2))
    while True:
        prime = next(it)
        yield prime
        it = filter(lambda x, p=prime: x % p != 0, it)

primes = sieve()
first_10 = [next(primes) for _ in range(10)]
```

## 4. 不可变数据结构：pyrsistent 风格

```python
# 手动实现简单不可变列表
class ImmutableList:
    def __init__(self, *items):
        self._items = tuple(items)
    
    def append(self, item):
        return ImmutableList(*self._items, item)
    
    def remove(self, index):
        return ImmutableList(
            *self._items[:index], *self._items[index+1:]
        )
    
    def __getitem__(self, idx):
        return self._items[idx]
    
    def __repr__(self):
        return f"ImmutableList{self._items}"

lst = ImmutableList(1, 2, 3)
lst2 = lst.append(4)  # 原 lst 不变
lst3 = lst.remove(1)  # 原 lst 不变
# lst = (1,2,3), lst2 = (1,2,3,4), lst3 = (1,3)
```

## 5. Either Monad 错误处理（替代 Exception）

```python
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, Union

T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')

@dataclass
class Left(Generic[E]):
    error: E

@dataclass  
class Right(Generic[T]):
    value: T

Either = Union[Left[E], Right[T]]

def safe_divide(a: float, b: float) -> Either:
    if b == 0:
        return Left("除数不能为零")
    return Right(a / b)

def parse_int(s: str) -> Either:
    try:
        return Right(int(s))
    except ValueError:
        return Left(f"无法解析: {s}")

def bind(m: Either, f: Callable) -> Either:
    match m:
        case Left(e):
            return Left(e)
        case Right(v):
            return f(v)

# 链式：安全解析 → 安全除法
result = bind(
    parse_int("10"),
    lambda x: bind(
        parse_int("2"),
        lambda y: safe_divide(x, y)
    )
)
# Right(5.0)

# 错误传递
error_result = bind(
    parse_int("abc"),
    lambda x: bind(
        parse_int("2"),
        lambda y: safe_divide(x, y)
    )
)
# Left("无法解析: abc")
```

## 6. 工具库推荐

| 库 | 用途 | Python 标准库替代 |
|----|------|-----------------|
| `toolz` | 函数式工具集合 | functools / itertools |
| `fn.py` | Scala 风格 FP | 暂无 |
| `pyrsistent` | 不可变数据结构 | 暂无 |
| `returns` | Monad/函子 类型 | 自定义 Either/Maybe |

```python
# toolz 实战
import toolz as tz

# 管道修饰符
@tz.pipe
def pipeline(data):
    yield from filter(lambda x: x > 0, data)
    yield from map(lambda x: x ** 2, _)
    yield from sorted(_, reverse=True)

pipeline([3, -1, 2, -4, 5])  # [25, 9, 4]

# 记忆化 + 惰性
@tz.memoize
def expensive(x):
    return sum(i ** 2 for i in range(x))

# 分组
result = tz.groupby(lambda x: x % 2, [1, 2, 3, 4, 5])
# {1: [1, 3, 5], 0: [2, 4]}
```

## 7. 什么时候用/不用函数式

**适合**：
- 数据处理管线（map-filter-reduce 链条）
- 并发/并行（不可变状态避免锁）
- 配置/规则引擎（声明式描述）
- 错误处理链（Either/Monad）

**不适合**：
- 高性能数值计算（原地修改更高效）
- I/O 密集型循环（生成器开销可能大于直接操作）
- 团队其他人不熟悉函数式思维

---

**下一篇**: 函数式编程 Roadmap
