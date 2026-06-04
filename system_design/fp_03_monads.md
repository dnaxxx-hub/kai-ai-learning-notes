# 函数式编程第3课：Monad 深度

> "Monad 不过是自函子范畴上的幺半群" — 对，但这是最没用的解释。

## 1. Functor → Applicative → Monad 的递进

### Functor（可映射容器）

```
fmap :: (a -> b) -> F a -> F b
```

对容器里的值应用函数，容器结构不变。

```haskell
-- Haskell
fmap (+1) (Just 3)  -- Just 4
fmap (+1) Nothing   -- Nothing
fmap (*2) [1,2,3]   -- [2,4,6]
```

```python
# Python 类比
def fmap(func, container):
    if container is None:
        return None
    return func(container)

# 列表做 Functor
class List:
    def fmap(self, func):
        return [func(x) for x in self.items]
```

**Functor 定律**：
1. 恒等：`fmap id = id`
2. 组合：`fmap (f . g) = fmap f . fmap g`

### Applicative（应用函子）

```
pure :: a -> F a          -- 把值装进容器
(<*>) :: F (a -> b) -> F a -> F b  -- 容器中的函数应用到容器中的值
```

当函数也在容器中时：

```haskell
-- 多个参数的 fmap
(+) <$> Just 3 <*> Just 4  -- Just 7

-- 比 fmap 强大：函数也是上下文相关的
[(+1), (*2)] <*> [1, 2, 3]  -- [2,3,4, 2,4,6]
```

### Monad（可编程计算）

```
(>>=) :: M a -> (a -> M b) -> M b
```

核心：**前一步的结果决定后一步做什么**。

```haskell
-- Maybe Monad：如果任一步返回 Nothing，整个链条短路
safe_div :: Double -> Double -> Maybe Double
safe_div x 0 = Nothing
safe_div x y = Just (x / y)

calc :: Maybe Double
calc = do
    a <- safe_div 10 2   -- Just 5
    b <- safe_div a 0    -- Nothing（爆炸，短路）
    return (b * 2)        -- 永远不会执行
```

## 2. 常见 Monad

### Maybe Monad（容错/可空）

```python
class Maybe:
    def bind(self, f):
        if self is Nothing:
            return Nothing
        return f(self.value)

# 链式调用，自动短路
result = (Maybe(10)
    .bind(lambda x: safe_div(x, 2))  # Just 5
    .bind(lambda x: safe_div(x, 0))  # Nothing
    .bind(lambda x: safe_div(x, 3))) # 不会执行
```

### Either Monad（异常替代）

```haskell
data Either e a = Left e | Right a

-- 类似 try-catch 但更纯
safeRead :: String -> Either String Int
safeRead s = case reads s of
    [(n, "")] -> Right n
    _         -> Left "parse error"
```

### List Monad（非确定性计算）

```haskell
-- 所有可能的组合
pairs :: [(Int, Int)]
pairs = do
    x <- [1, 2, 3]
    y <- [4, 5]
    return (x, y)
-- [(1,4),(1,5),(2,4),(2,5),(3,4),(3,5)]
```

### IO Monad（Haskell 处理副作用的方式）

```haskell
-- 纯函数不能有副作用 → IO Monad 隔离副作用
getLine :: IO String
putStrLn :: String -> IO ()

main :: IO ()
main = do
    putStrLn "What's your name?"
    name <- getLine          -- 从 IO 中提取值
    putStrLn ("Hello, " ++ name)
```

IO Monad 的本质：**描述"如何与世界交互"的纯值**。

## 3. Monad 定律

1. **左单位元**: `return x >>= f == f x`
2. **右单位元**: `m >>= return == m`
3. **结合律**: `(m >>= f) >>= g == m >>= (\x -> f x >>= g)`

## 4. Python 实现 Option/Either Monad

```python
from __future__ import annotations
from typing import TypeVar, Callable, Generic, Union

T = TypeVar('T')
U = TypeVar('U')

class Option(Generic[T]):
    """Maybe Monad 的 Python 实现"""
    def __init__(self, value: T = None, is_some: bool = True):
        self._is_some = is_some
        self._value = value
    
    @staticmethod
    def some(x: T) -> Option[T]:
        return Option(x, True)
    
    @staticmethod
    def nothing() -> Option[T]:
        return Option(None, False)
    
    def bind(self, f: Callable[[T], Option[U]]) -> Option[U]:
        if not self._is_some:
            return Option.nothing()
        return f(self._value)
    
    def fmap(self, f: Callable[[T], U]) -> Option[U]:
        if not self._is_some:
            return Option.nothing()
        return Option.some(f(self._value))

# 使用
result = (
    Option.some(10)
    .bind(lambda x: Option.some(x / 2))          # Some(5)
    .fmap(lambda x: x * 3)                       # Some(15)
    .bind(lambda x: Option.nothing())            # Nothing
    .bind(lambda x: Option.some(x + 1))          # 短路
)

if result._is_some:
    print(result._value)
else:
    print("操作失败")
```

## 5. 为什么 Monad 重要？

1. **隔离副作用**（IO Monad）
2. **错误处理**（Maybe/Either Monad）
3. **状态管理**（State Monad）
4. **日志记录**（Writer Monad）
5. **环境读取**（Reader Monad）
6. **组合子模式**（do notation = 领域特定语言）

### 一句话总结

> Functor 让容器可映射，Applicative 让容器中的函数可应用，Monad 让计算序列可编程。

---

**下一篇**: 函数式编程的 Python 实战
