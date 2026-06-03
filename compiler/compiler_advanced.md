# MiniLang 编译器升级：类型推断与垃圾收集

## 1. 类型系统与类型推断

### 1.1 静态类型检查的两条路径

```
显式类型（C/Java/Rust）：
let x: i32 = 42;        ← 程序员声明类型 → 编译器检查

隐式类型推断（ML/Haskell/Rust）：
let x = 42;              ← 程序员只写值 → 编译器推导类型

HM 类型系统（Hindley-Milner）：
fn map(f, list) { ... }  ← 无需任何类型标注 → 推导最一般类型
```

### 1.2 核心概念

| 概念 | 含义 | 示例 |
|------|------|------|
| **类型变量** | 待定类型 | `α`, `β`, `'a` |
| **类型常量** | 已知类型 | `Int`, `Bool`, `String` |
| **类型构造** | 复合类型 | `List<Int>`, `α → β` |
| **统一（Unify）** | 两个类型相等的约束求解 | `α = Int` |
| **最一般类型** | 推导出最泛化的签名 | `(α → β) → List<α> → List<β>` |

### 1.3 Hindley-Milner 算法（Algorithm W）

算法两个阶段：

**阶段1：约束收集（Constraint Generation）**

遍历 AST，为每个表达式生成类型约束：

```rust
enum Constraint {
    Eq(Type, Type),          // 两个类型必须相等
    Deref(Type, Type),       // *t = T → t: &T
    Call(Type, Type, Type),  // f(x): f: A → B, x: A, res: B
}

fn infer_constraints(expr: &Expr, ctx: &mut Context) -> (Type, Vec<Constraint>) {
    match expr {
        Expr::Lit(n) => (Type::Int, vec![]),
        Expr::Var(name) => (ctx.lookup(name), vec![]),
        Expr::Abs(param, body) => {
            let param_type = Type::Var(ctx.fresh_var());
            ctx.bind(param, param_type.clone());
            let (body_type, constrs) = infer_constraints(body, ctx);
            ctx.unbind(param);
            (Type::Fun(Box::new(param_type), Box::new(body_type)), constrs)
        }
        Expr::App(func, arg) => {
            let (func_type, mut c1) = infer_constraints(func, ctx);
            let (arg_type, c2) = infer_constraints(arg, ctx);
            let result_type = Type::Var(ctx.fresh_var());
            c1.extend(c2);
            c1.push(Constraint::Eq(func_type, Type::Fun(
                Box::new(arg_type),
                Box::new(result_type.clone()),
            )));
            (result_type, c1)
        }
    }
}
```

**阶段2：统一求解（Unification）**

通过 substitution（替换映射）求解所有约束：

```rust
fn unify(eq: &Constraint, subs: &mut Substitution) -> Result<(), Error> {
    match eq {
        Constraint::Eq(t1, t2) => {
            let t1 = apply_subs(subs, t1);
            let t2 = apply_subs(subs, t2);
            if t1 == t2 { return Ok(()); }
            match (&t1, &t2) {
                (Type::Var(v), t) | (t, Type::Var(v)) => {
                    if occurs_check(v, t) {  // 避免 α = α → β
                        return Err("Infinite type".into());
                    }
                    subs.insert(v.clone(), t.clone());
                }
                (Type::Fun(a1, r1), Type::Fun(a2, r2)) => {
                    unify(&Constraint::Eq(*a1, *a2), subs)?;
                    unify(&Constraint::Eq(*r1, *r2), subs)?;
                }
                _ => return Err("Type mismatch".into()),
            }
        }
    }
    Ok(())
}
```

### 1.4 Let 多态性

```rust
let id = fn(x) => x;
// 推断为: α → α (泛化)

let a = id(42);
// 实例化: α := Int, 类型为 Int

let b = id(true);
// 实例化: α := Bool, 类型为 Bool
```

**泛化（Generalization）：** 当 `let` 绑定被处理时，所有不在外层环境中的自由类型变量被量化为**类型参数**。

**实例化（Instantiation）：** 每次使用 let 绑定时，类型参数被替换为**新鲜类型变量**。

### 1.5 在 MiniLang 中实现类型推断

**步骤：**

1. **扩展 AST**：添加 Type 节点和类型标注
2. **添加类型环境**：符号表维护 `(name, Type)` 映射
3. **约束收集**：遍历 AST，收集类型等式约束
4. **统一求解**：运行 HM 算法，得到最一般类型
5. **类型检查/类型化 IR**：将类型信息附加到 IR 节点

```rust
// 类型化的 AST
enum TypedExpr {
    LitInt(i32),
    Var(String, Type),           // 已知类型
    Abs(String, Type, Box<Self>), // 参数+类型
    App(Box<Self>, Box<Self>, Type),
    Let(String, Box<Self>, Box<Self>),
}
```

---

## 2. 垃圾收集（GC）

### 2.1 GC 策略对比

| 策略 | 吞吐 | 暂停 | 实现复杂度 |
|------|------|------|-----------|
| 引用计数 | 中 | 无（即时） | 低 |
| 标记-清除 | 高 | 高（全暂停） | 中 |
| 复制（Cheney） | 中 | 中 | 中 |
| 分代收集 | 高 | 低 | 高 |
| 增量/并发 | 中 | 极低 | 极高 |

### 2.2 标记-清除收集器（Mark-Sweep）

**两阶段分析法：**

```
阶段1（标记）：从 GC Root 出发，遍历可达对象图
阶段2（清除）：扫描整个堆，回收未标记的对象

GC Roots:
├── 栈帧中的局部变量
├── 全局/静态变量
└── 寄存器中的引用
```

#### 对象头设计

```c
typedef struct ObjectHeader {
    uintptr_t mark : 1;        // 标记位
    uintptr_t color : 2;       // 三色标记状态
    uintptr_t size : 29;       // 对象大小
    uintptr_t type_id : 16;    // 类型标识
    // 对于 GC 遍历的对象，第一个字段必须是：
    struct GCField* fields;    // 描述哪些字段是引用
} ObjectHeader;
```

#### 标记阶段

```c
void mark(Object* obj) {
    if (!obj || obj->header.mark) return;
    obj->header.mark = 1;
    // 遍历所有引用字段
    for (int i = 0; i < obj->header.nfields; i++) {
        if (obj->header.is_gc_ref[i]) {
            mark(obj->fields[i]);
        }
    }
}

void mark_all(GC* gc) {
    // 从 GC Root 开始
    for (int i = 0; i < gc->root_count; i++) {
        mark(gc->roots[i]);
    }
}
```

#### 清除阶段

```c
void sweep(GC* gc) {
    Object* obj = gc->heap_start;
    while (obj < gc->heap_end) {
        if (!obj->header.mark) {
            // 未标记：回收
            if (obj->header.finalizer) {
                obj->header.finalizer(obj);  // 调用析构
            }
            add_to_free_list(gc, obj);
        } else {
            // 已标记：清除标记位
            obj->header.mark = 0;
        }
        obj = next_object(obj);
    }
}
```

### 2.3 三色标记（Tri-Color Marking）

用于**增量/并发 GC** 的基础：

```
白色：未访问（可能是垃圾）
灰色：已访问但引用对象未扫描完
黑色：已访问且引用对象已扫描完

初始状态：所有对象白色
标记开始：Root 变灰
循环：从灰色集合取一个对象
      遍历它的引用
      如果引用指向白色对象，将其变为灰色
      当前对象变为黑色
结束：灰色集合为空 → 所有白色是不可达的（可清除）
```

**并发保证（写屏障）：**

```c
// 插入写屏障（Incremental Update）
// 当黑色对象写入指向白色对象的引用时
void write_barrier(Object* black, Object* white) {
    if (is_black(black)) {
        set_gray(white);  // 白色变回灰色
    }
}
```

### 2.4 引用计数（Reference Counting）

#### 基础实现

```c
void ref_inc(RefCounted* obj) {
    obj->refcount.fetch_add(1, relaxed);
}

void ref_dec(RefCounted* obj) {
    if (obj->refcount.fetch_sub(1, acq_rel) == 1) {
        // 递减引用（处理循环引用链）
        for each field in obj->fields:
            if field is RefCounted:
                ref_dec(field);
        free(obj);
    }
}
```

#### 循环引用问题

```
A → B → C
↑         ↓
└─────────┘  (A 引用 C)

refcount: A(2) B(1) C(2)
都不为 0 → 永远不会释放
```

**解决：**
1. 弱引用（`WeakPtr`）：不计数，检测到循环时手动清理
2. 跟踪+引用计数混合：偶尔扫描收集循环
3. Rust 的做法：用所有权模型在编译期消除循环引用

#### 优点
- 对象释放即时（适合实时系统）
- GC 开销分散，无"全停顿"
- 实现简单

### 2.5 复制收集器（Cheney's Algorithm）

**"半区复制"**：将堆分为两部分 From 和 To。

```
分配只在 From 区进行（bump pointer）
From 满时：
  1. 交换 From 和 To 角色
  2. 遍历 From 区的所有可达对象
  3. 将它们复制到 To 区（紧凑排列）
  4. 清除 From 区

优点：无碎片，分配 O(1)
缺点：只使用一半内存
```

---

## 3. 在 MiniLang 中集成 GC

### 3.1 架构设计

```
┌────────┐   ┌──────────┐   ┌───────────┐   ┌────────┐
│ Source │ → │ Type Inf  │ → │ IR 生成    │ → │ GC 插入│
└────────┘   └──────────┘   └───────────┘   └────┬───┘
                                                  │
              ┌───────────────────────────────────┘
              ↓
       ┌──────────────┐
       │  运行时 + GC   │
       │  (标记-清除)    │
       └──────────────┘
```

### 3.2 GC 插入阶段

在 IR 生成后，编译器需要：

1. **识别分配点**：哪些 IR 指令分配内存
2. **插入 GC 安全点**：在函数调用、loop back-edge 处
3. **生成栈映射**：标记哪些栈位置包含 GC 引用
4. **对象布局信息**：为每个类型生成字段描述

```rust
// 分配指令在 IR 中被替换为
call @gc_alloc(i32 %size, i32 %type_id)
// GC 安全点
call @gc_safepoint()

// 栈映射在函数入口
define @foo() gc "statepoint-example" {
    ; GC 引用的位置记录在元数据中
    %ptr = call @gc_alloc(...) ["gc-live" = (%ptr)]
}
```

### 3.3 GC Root 扫描

```c
void scan_roots(GC* gc, struct StackFrame* frame) {
    // 扫描寄存器
    for (int i = 0; i < frame->gc_ref_count; i++) {
        void* ptr = frame->gc_refs[i];
        mark(gc, ptr);
    }
    // 扫描上层的栈帧
    if (frame->prev) scan_roots(gc, frame->prev);
}
```

### 3.4 性能考量

```
对象分配开销对比：
  malloc:        ~80ns (通用分配器)
  bump alloc:    ~3ns  (仅指针增量)
  refcount inc:  ~5ns  (原子操作)
  refcount dec:  ~5ns  (原子操作 + 条件分支)

GC 暂停时间（标记-清除，10MB 堆）：
  标记：~5ms
  清除：~1ms
  总计：~6ms

GC 暂停时间（增量式）：
  每步：~0.1ms
  总 GC 时间相同但分散
```

---

## 4. MiniLang 升级方案总结

### 类型系统升级

| 功能 | 状态 | 实现 |
|------|------|------|
| 基本类型（Int, Bool） | ✅ | 已支持 |
| 显式类型标注 | ➕ | 扩展 AST |
| HM 类型推断 | ➕ | 约束生成+统一求解 |
| Let 多态 | ➕ | 泛化/实例化 |
| 代数数据类型 | 💭 | sum type + pattern matching |
| 类型类/Trait | 💭 | 类似 Rust 的 trait bounds |

### GC 升级

| 功能 | 状态 | 实现 |
|------|------|------|
| 栈上变量（自动生命周期） | ✅ | 已支持 |
| 堆分配（box/gcnew） | ➕ | 运行时 alloc |
| 标记-清除 GC | ➕ | 实现两阶段算法 |
| 写屏障 | ➕ | 增量式 GC 需要 |
| 分代收集 | 💭 | 世代 + Remembered Set |

注：✅ 已实现  ➕ 本轮新增  💭 未来规划
