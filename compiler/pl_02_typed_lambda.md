# 简单类型λ演算（STLC）

> 给λ演算加上类型系统的第一个尝试。

## 1. STLC 语法

### 类型

```
τ := τ₁ → τ₂  |  Base
```

没有多态。每个函数都有一个输入类型和一个输出类型。

### 项

```
t := x                   — 变量
   | λx:τ.t              — 带类型标注的函数定义
   | t₁ t₂               — 函数应用
```

### 类型规则（Typing Rules）

```
x:τ ∈ Γ
───────── (Var)          — 变量查找
Γ ⊢ x:τ

Γ, x:τ₁ ⊢ t:τ₂
───────────────── (→I)  — 函数引入（抽象）
Γ ⊢ (λx:τ₁.t): τ₁→τ₂

Γ ⊢ t₁: τ₁→τ₂    Γ ⊢ t₂: τ₁
──────────────────────────── (→E) — 函数消去（应用）
Γ ⊢ t₁ t₂: τ₂
```

## 2. Python类型检查器

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Union

# 类型定义
@dataclass
class BaseType:
    name: str  # e.g., 'Int', 'Bool', 'Nat'

@dataclass
class FuncType:
    from_type: 'Type'
    to_type: 'Type'

Type = Union[BaseType, FuncType]

# 类型环境：变量名 → 类型
TypeEnv = Dict[str, Type]

# λ项定义
@dataclass
class Var:
    name: str

@dataclass
class Abs:
    param: str
    param_type: Type
    body: 'Term'

@dataclass  
class App:
    func: 'Term'
    arg: 'Term'

Term = Union[Var, Abs, App]

def type_check(env: TypeEnv, term: Term) -> Optional[Type]:
    """
    STLC类型检查算法。
    返回：类型（如果通过）或 None（类型错误）
    
    规则参考上面的推导公式
    """
    match term:
        case Var(name):
            # 规则(Var)
            if name in env:
                return env[name]
            return None  # 未定义变量
        
        case Abs(param, param_type, body):
            # 规则(→I)
            new_env = {**env, param: param_type}
            body_type = type_check(new_env, body)
            if body_type:
                return FuncType(from_type=param_type, to_type=body_type)
            return None
        
        case App(func, arg):
            # 规则(→E)
            func_type = type_check(env, func)
            arg_type = type_check(env, arg)
            
            if isinstance(func_type, FuncType) and func_type.from_type == arg_type:
                return func_type.to_type
            return None

# 测试
env = {'x': BaseType('Int'), 'f': FuncType(BaseType('Int'), BaseType('Bool'))}

# λx:Int. x 的类型：Int → Int
identity_type = type_check(env, Abs('x', BaseType('Int'), Var('x')))
print(identity_type)  # FuncType(from=Int, to=Int)

# f x 的类型：Bool（f: Int→Bool, x: Int, so f x: Bool）
app_type = type_check(env, App(Var('f'), Var('x')))
print(app_type)  # BaseType('Bool')

# f f 的类型检查：报错（f在期待一个Int，但给了它一个函数）
error_type = type_check(env, App(Var('f'), Var('f')))
print(error_type)  # None
```

## 3. Curry-Howard同构

**程序 = 证明，类型 = 命题**

| 编程语言 | 逻辑 |
|---------|------|
| 类型 | 命题 |
| 类型检查 = 证明检查 |
| 可运行的程序 | 正确的证明 |
| 函数类型 A→B | 蕴含 A ⇒ B |
| 积类型 A×B | 合取 A ∧ B |
| 和类型 A+B | 析取 A ∨ B |
| 空类型 Void | 假 ⊥ |
| 单位类型 Unit | 真 ⊤ |

**例子**：存在函数 `f: A→A` 意味着命题 A⇒A 是恒真的

## 4. STLC 的性质

1. **类型安全性**（Progress + Preservation）：
   - Progress：有类型的项要么是值，要么可以继续归约
   - Preservation：归约后类型不变
   
2. **强归一化**：所有类型正确的程序都会终止（不能实现无限循环）
   - 这意味着：STLC不是图灵完备的
   - 原因：没有递归/不动点组合子

3. **唯一类型**：每个项至多只有一个类型

## 5. STLC 与 MiniLang 的关系

MiniLang 的 `fun (x: Int) => x + 1` 就是 STLC 的 `λx:Int. x + 1`：

```
MiniLang:        STLC:
fun (x: Int) =>  λx:Int.
    x + 1          (+ x 1)
```

类型检查算法也是一脉相承的。

## 6. STLC的局限

1. **没有多态**：`λx.x` 只能写成 `λx:Int.x` 或 `λx:Bool.x`，不能一个函数通吃
2. **没有子类型**：不能把 `Int` 当作 `Float` 用（即使它们有包含关系）
3. **没有变体/记录**：只有函数类型和基本类型
4. **没有递归**：不能定义 `let rec` 或循环

这些局限推动了**System F（多态λ演算）**、**F-下界（F-sub，子类型化）**、**HM类型推理**等的发展。

---

**下一篇**: 子类型系统 — 协变/逆变/不变
