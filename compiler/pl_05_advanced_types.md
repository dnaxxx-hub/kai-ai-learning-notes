# 高级类型系统：存在类型/依赖类型/线性类型

## 1. 存在类型（Existential Types）

"存在某个类型 T，使得..."
- 泛型：`∀T. F<T>` — "对所有类型 T，F<T> 成立"
- 存在：`∃T. F<T>` — "存在某个类型 T，F<T> 成立"

```haskell
-- 存在类型的经典用法：类型擦除的容器
data AnyShow = forall a. Show a => MkAnyShow a

-- 这个容器装着"某个"实现了Show的类型
-- 你可以对它调用show，但不能知道具体是什么类型
```

### Python 中的存在类型

```python
from typing import Any, Protocol

class Hashable(Protocol):
    def __hash__(self) -> int: ...

# "存在某个实现了Hashable的类型"
def store_in_dict(key: Hashable, value: Any):
    return {key: value}
```

## 2. 依赖类型（Dependent Types）

类型可以**依赖值**——"类型是值的一个函数"。

```haskell
-- 伪代码：依赖类型
-- 向量的大小是类型的一部分
append :: Vec n a -> Vec m a -> Vec (n + m) a
-- n和m是值，但它们在类型签名中出现了！
```

### 实际语言：Idris/Agda

```idris
-- Idris 的依赖类型
data Vect : Nat -> Type -> Type where
    Nil  : Vect 0 a
    (::) : a -> Vect n a -> Vect (n+1) a

-- 类型系统保证两个向量长度相同才能相加
zipVect : Vect n a -> Vect n b -> Vect n (a, b)
zipVect [] [] = []
zipVect (x::xs) (y::ys) = (x, y) :: zipVect xs ys
-- 编译器保证：如果长度不同，代码不编译
```

### Python 的逼近

```python
# Python不能做真正的依赖类型，但可以用类型提示模拟
from typing import Tuple, Literal

# Literal类型：参数是具体值
def three_plus(x: Literal[3]) -> int:
    return x + 3

# 无法表达"数组长度为3"的类型约束
```

## 3. 线性类型（Linear Types）

每个值必须被**恰好使用一次**。

```haskell
-- Haskell的线性类型扩展
-- 文件句柄——打开后必须关闭
openFile :: FilePath &> IO FileHandle
closeFile :: FileHandle &> IO ()

-- 如果忘记closeFile，编译不通过
```

### Rust的所有权系统——最成功的线性类型应用

```rust
// Rust不是经典线性类型（允许drop），但核心思想一致
fn consume(s: String) { 
    // s被消费了
}

fn main() {
    let s = String::from("hello");
    consume(s);
    // println!("{}", s);  // ❌ 编译错误：s已经被移动了
}
```

Rust的借用检查 = 线性类型 + 借用语义：

| 概念 | 线性类型 | Rust |
|------|---------|------|
| 使用次数 | 恰好1次 | 1次（move）或N次只读（borrow） |
| 资源管理 | 自动释放 | drop trait |
| 共享 | 不允许 | 引用计数 Rc/Arc |

## 4. 交集类型（Intersection Types）& 并集类型（Union Types）

### 交集类型 `A & B`

值同时满足 A 和 B 两个类型：

```typescript
// TypeScript的交集类型
type Named = { name: string };
type Aged = { age: number };

type Person = Named & Aged;
// Person一定同时有 name 和 age
```

### 并集类型 `A | B`

值满足 A **或** B 中的一个：

```typescript
// TypeScript的并集类型
type Result = Success | Failure;

function handle(result: Result) {
    if (result.type === 'success') {
        // 这里类型自动缩小为Success
        return result.data;
    }
    // 这里类型自动缩小为Failure
    return result.error;
}
```

### 与代数数据类型的对比

```
Haskell: data Option a = Some a | None
         — 必须case/pattern match才能访问

TypeScript: type Option<T> = T | null;  
            — 可以用typeof/null检查来缩小
```

## 5. Haskell的GADT（广义代数数据类型）

让构造函数可以"选择"返回什么类型：

```haskell
-- 普通ADT
data Expr = IVal Int | BVal Bool | Add Expr Expr

eval :: Expr -> ???
-- 问题：返回类型不确定（IVal返回Int，BVal返回Bool，Add返回Int）

-- GADT——类型信息跟随构造函数
{-# LANGUAGE GADTs #-}
data Expr a where
    IVal :: Int -> Expr Int
    BVal :: Bool -> Expr Bool
    Add  :: Expr Int -> Expr Int -> Expr Int

eval :: Expr a -> a
eval (IVal n) = n
eval (BVal b) = b
eval (Add x y) = eval x + eval y  -- 类型安全！
```

## 6. TypeFamilies（类型族）— 类型级别的函数

```haskell
{-# LANGUAGE TypeFamilies #-}
-- 类型族：类型到类型的映射
type family Element (c :: * -> *) :: *
type instance Element [] = Int
type instance Element Maybe = Bool

-- 关联类型族（OCaml/Traits风格）
class Collection c where
    type Item c
    first :: c -> Maybe (Item c)
    rest :: c -> c
```

## 7. 各种类型系统的表达能力分级

| 等级 | 类型系统 | 语言 | 表达力 |
|------|---------|------|-------|
| 0 | 无类型 | 汇编, B | 最小 |
| 1 | 简单类型 λ演算 | STLC | 不能表达递归 |
| 2 | HM | Haskell 99% | 类型推断 |
| 3 | System F | 多态λ演算 | 泛型 |
| 4 | F-下界 | Java/Scala | 子类型+泛型 |
| 5 | 依赖类型 | Idris/Agda | 类型检查=执行 |
| 6 | 线性+依赖 | 理论 | 完美资源管理 |

---

**附**: PL理论 Roadmap
