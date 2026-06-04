# 子类型系统：协变/逆变/不变

## 1. 什么是子类型？

S 是 T 的子类型（S <: T），如果**在需要 T 的任何地方，都可以安全地使用 S**。

```
Int <: Float?  — 把int当float用，安全（自动类型提升）
Dog <: Animal? — 把"狗"当"动物"用，安全
```

## 2. Liskov替换原则（LSP）

Barbara Liskov 1987年定义：

> **如果对于每个类型 S 的对象 o₁，都存在一个类型 T 的对象 o₂，
> 使得在所有用 T 编写的程序中，用 o₁ 替换 o₂ 后程序行为不变，
> 则 S 是 T 的子类型。**

**通俗版**：子类应该可以替换父类使用，且不破坏程序正确性。

### LSP 违反的经典例子

```python
class Rectangle:
    def __init__(self, w, h):
        self._width = w
        self._height = h
    
    def set_width(self, w): self._width = w
    def set_height(self, h): self._height = h
    def area(self): return self._width * self._height

class Square(Rectangle):
    def set_width(self, w):
        self._width = w
        self._height = w  # ❌ 改变了契约！
```

问题：`Square.set_width` 修改了 `height`，违反了 Rectangle 的契约（高宽独立）。
这就是"正方形是不是长方形的子类"悖论。

## 3. 函数类型上的子类型

输入逆变，输出协变——这是子类型化最反直觉但也最重要的规则：

```
如果 S₁ <: T₁ 且 T₂ <: S₂
那么 T₁→T₂ <: S₁→S₂
```

### 为什么输入是逆变的？

```python
# 场景：需要一个"接收Animal的吃函数"
def feed(animal: Animal):
    animal.eat()

# 我们有一个"只接收Dog的吃函数"
def feed_dog(dog: Dog):
    dog.bark()
    dog.eat()

# feed_dog 能不能替代 feed？
# ❌ 不能！如果有人传Cat给feed_dog，cat.bark()会报错
# 所以 Dog→Void 不是 Animal→Void 的子类型

# 反过来：如果需要一个"只接收Dog的函数"，
# "接收Animal的函数"可以被替代吗？
# ✅ 可以！接收Animal的函数当然也能处理Dog
# 所以 Animal→Void <: Dog→Void ✓
```

**记忆口诀**：
- 输出（返回值）：和子类型**同向** — 协变（Covariant）
- 输入（参数）：和子类型**反向** — 逆变（Contravariant）

## 4. 泛型中的三种类型变化

```typescript
// TypeScript 示例
interface Producer<T> { produce(): T }      // T 只在输出位 → 协变
interface Consumer<T> { consume(x: T): void }  // T 只在输入位 → 逆变
interface Box<T> { get(): T; set(x: T): void } // T 在输入输出位 → 不变
```

| 变化方向 | 泛型位置 | 例子 |
|---------|---------|------|
| 协变 (Covariant) | 输出（返回值） | List<Dog> <: List<Animal> |
| 逆变 (Contravariant) | 输入（参数） | Comparator<Animal> <: Comparator<Dog> |
| 不变 (Invariant) | 同时输入输出 | Box<Dog> ⊄ Box<Animal> |

### Java示例

```java
// Java 的协变数组（设计错误，历史遗留）
String[] strings = new String[1];
Object[] objects = strings;  // ✅ 编译通过（但运行时会抛错！）
objects[0] = 1;              // ❌ ArrayStoreException

// Java 的泛型是"不变的"
List<String> strs = new ArrayList<>();
List<Object> objs = strs;  // ❌ 编译错误（安全的）
```

## 5. Python渐进类型的子类型

```python
from typing import Union, TypeVar, Generic

T = TypeVar('T', covariant=True)  # 协变
U = TypeVar('U', contravariant=True)  # 逆变

class Animal:
    def sound(self) -> str: return "..."

class Dog(Animal):
    def bark(self) -> str: return "woof"

# mypy 类型检查
def handle_animals(animals: list[Animal]):
    for a in animals:
        a.sound()

# Python中list是"不变"的，但mypy做了特殊处理
dogs = [Dog(), Dog()]  # type: list[Dog]
# handle_animals(dogs)  # 在mypy严格模式下报错
# 但在实践中大多允许（因为Python的鸭子类型）
```

## 6. 结构子类型 vs 名义子类型

| | 名义子类型（Nominal） | 结构子类型（Structural） |
|--|---------------------|----------------------|
| 判断依据 | 显式声明继承关系 | 看结构是否兼容 |
| 语言 | Java, C#, Rust | TypeScript, Go |
| 例子 | `class Dog extends Animal` | `{ name: string }` 兼容任何有name的 |

### Go的结构子类型

```go
// Go没有"implements"关键字
type Writer interface {
    Write([]byte) (int, error)
}

// 只要有Write方法的，就是Writer
type File struct { ... }
func (f *File) Write(p []byte) (n int, err error) { ... }

var w Writer = &File{}  // ✅ 自动满足接口
```

### TypeScript的结构子类型

```typescript
interface Point { x: number; y: number }
interface Point3D { x: number; y: number; z: number }

let p2: Point = { x: 1, y: 2 };
let p3: Point3D = { x: 1, y: 2, z: 3 };

p2 = p3;  // ✅ Point3D <: Point (结构兼容)
p3 = p2;  // ❌ 不兼容（缺少z）
```

## 7. Rust的所有权类型——特殊子类型关系

Rust中的引用有"生命周期"子类型关系：

```
'a : 'b  — 生命周期 'a 不短于 'b

&'a T <: &'b T  — 长生命周期是短生命周期的子类型（协变）
```

所以：
```rust
fn foo<'a>(x: &'a str) -> &'a str { x }

let s = String::from("hello");
let result = foo(&s);  
// 这里 'a 被推断为 s 的生命周期
// &s 的引用比 result 的生命周期长 → 类型安全
```

---

**下一篇**: 类型推断 — Hindley-Milner 算法
