# 类型推断：Hindley-Milner 算法

> 让程序员不需要显式写类型，编译器"猜"出来。

## 1. HM类型系统的核心特性

Hindley-Milner（又名 Algorithm W/Damas-Milner）：
- **类型推断**：无需显式类型标注
- **Let多态**：`let x = ...` 在上下文中可以有多种类型
- **强类型**：类型安全，无隐式转换
- **主流应用**：ML / Haskell / Rust（前向声明）

## 2. 类型推断的直觉

```haskell
-- 不需要写类型
f x y = x + y  -- Haskell自动推断出 f :: Num a => a -> a -> a
```

推理过程：
```
1. + 的类型是 Num a => a -> a -> a
2. x 作为 + 的第一个参数 → x :: a
3. y 作为 + 的第二个参数 → y :: a  
4. 结果类型 → a
5. 化简 → f :: Num a => a -> a -> a
```

## 3. 核心算法步骤

HM算法 = **约束生成 + 合一（Unification）**：

### 算法W（流程）

```
输入：λ表达式 + 类型环境
输出：最通用类型 + 约束集合

1. 为每个子表达式生成"类型变量"
2. 生成约束（类型必须相等）
3. 用合一算法解约束
4. 返回解出的类型
```

## 4. Python实现简化版HM

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# --- 类型表达式 ---
@dataclass
class TVar:
    name: str

@dataclass  
class TFun:
    arg: 'TypeExpr'
    ret: 'TypeExpr'

@dataclass
class TBase:
    name: str

TypeExpr = TVar | TFun | TBase

# --- λ项 ---
class Term: pass

@dataclass
class Var(Term):
    name: str

@dataclass
class Let(Term):
    name: str
    bind: Term
    body: Term

@dataclass
class Abs(Term):
    param: str
    body: Term

@dataclass
class App(Term):
    func: Term
    arg: Term

# --- 合一算法 ---
class UnificationError(Exception):
    pass

class Unifier:
    def __init__(self):
        self.id_counter = 0
        self.substitutions = {}  # TVar -> TypeExpr
    
    def fresh_var(self, prefix='t'):
        """生成新的类型变量"""
        self.id_counter += 1
        return TVar(f"{prefix}{self.id_counter}")
    
    def unify(self, t1: TypeExpr, t2: TypeExpr):
        """合一两个类型"""
        t1 = self.apply(t1)
        t2 = self.apply(t2)
        
        if isinstance(t1, TVar):
            if isinstance(t2, TVar) and t1.name == t2.name:
                return
            # t1 = t2 检查出现（Occurs Check）— 防止 x = x -> x
            if self.occurs(t1.name, t2):
                raise UnificationError(f"递归类型: {t1} in {t2}")
            self.substitutions[t1.name] = t2
        elif isinstance(t2, TVar):
            self.unify(t2, t1)  # 交换
        elif isinstance(t1, TFun) and isinstance(t2, TFun):
            self.unify(t1.arg, t2.arg)
            self.unify(t1.ret, t2.ret)
        elif isinstance(t1, TBase) and isinstance(t2, TBase):
            if t1.name != t2.name:
                raise UnificationError(f"类型不匹配: {t1} vs {t2}")
        else:
            raise UnificationError(f"不能合一: {t1} vs {t2}")
    
    def occurs(self, name: str, t: TypeExpr) -> bool:
        """Occurs Check — t中是否引用了name？"""
        t = self.apply(t)
        if isinstance(t, TVar):
            return t.name == name
        elif isinstance(t, TFun):
            return self.occurs(name, t.arg) or self.occurs(name, t.ret)
        return False
    
    def apply(self, t: TypeExpr) -> TypeExpr:
        """应用所有已知替换"""
        if isinstance(t, TVar):
            while t.name in self.substitutions:
                t = self.substitutions[t.name]
            return t
        elif isinstance(t, TFun):
            return TFun(self.apply(t.arg), self.apply(t.ret))
        return t

# --- 类型推断 ---
class TypeInferer:
    def __init__(self):
        self.unifier = Unifier()
        self.env = {}  # 类型环境
    
    def infer(self, term: Term) -> TypeExpr:
        """推断类型（Algorithm W简化版）"""
        match term:
            case Var(name):
                if name in self.env:
                    return self.env[name]
                raise Exception(f"未定义变量: {name}")
            
            case Abs(param, body):
                # λx.e — 生成新类型变量
                param_type = self.unifier.fresh_var()
                self.env[param] = param_type
                body_type = self.infer(body)
                return TFun(param_type, body_type)
            
            case App(func, arg):
                # e1 e2 — 生成约束
                func_type = self.infer(func)
                arg_type = self.infer(arg)
                result_type = self.unifier.fresh_var()
                
                # 添加约束：func_type = arg_type -> result_type
                self.unifier.unify(func_type, TFun(arg_type, result_type))
                
                return result_type
            
            case Let(name, bind, body):
                # let x = e1 in e2 — Let多态
                bind_type = self.infer(bind)
                # 对于let多态，应该对bind_type做泛化
                # 简化版：直接添加
                self.env[name] = bind_type
                return self.infer(body)

# --- 测试 ---
inferer = TypeInferer()

# let id = λx.x in id 42
term = Let(
    'id',
    Abs('x', Var('x')),  # λx.x
    App(Var('id'), 42)   # id(42)
)

# 简化环境（实际数字类型需要预先定义）
inferer.env['42'] = TBase('Int')

result = inferer.infer(term)
print(f"结果类型: {inferer.unifier.apply(result)}")
# 应该输出 Int
```

## 5. Let多态

Let多态的关键：`let x = e1 in e2` 时，对 e1 的类型做**泛化**（Gneralization）：

```haskell
-- 没有let多态，只能推理为单一类型
\x -> if x then 1 else 0  -- Bool -> Int

-- 有了let多态
let id x = x   -- 泛化为 ∀a. a -> a
in (id True, id 1)  -- 可以同时用在Bool和Int上
```

算法：
1. 推断 e1 的类型 τ
2. 找出 τ 中没有被环境绑定的自由类型变量 → 变成类型参数
3. 在 e2 中，每次使用 id 时都生成"新鲜的实例"

## 6. HM算法的局限

1. **不允许 `let rec` 递归**（虽然扩展了允许）
2. **不支持高阶多态**（Rank-2+ 类型的推断是未解问题）
3. **不直接支持子类型**（HM本质上是生成等式约束≠子类型约束）
4. **错误信息差**（"类型不匹配"在复杂场景中难以调试）

## 7. mypy 的渐进式类型

mypy不是HM，但它实现了Python的渐进类型系统：

```python
# 完全的静态类型 → HM风格
def add(x: int, y: int) -> int: ...

# 逐步添加类型 → mypy允许忽略部分
def add(x, y):
    return x + y  # mypy可以推断出int || float
```

---

**下一篇**: 高级类型系统
