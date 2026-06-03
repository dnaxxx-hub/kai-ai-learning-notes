# Go/Rust 系统语言 #1：Go 语言核心基础与并发模型

> **课程定位：** 全新方向 "Go/Rust 系统语言" 第 1 课
> **目标读者：** 有 C / JS 基础的工程师，从零开始学 Go
> **内容概要：** 设计哲学 → 语法速通 → 接口编程 → 并发模型 → 错误处理 → 工具链生态
> **字数：** ~12KB

---

## 引言：为什么是 Go？

2025 年的后端与基础设施领域，Go 已经稳坐云原生第一语言——Docker、Kubernetes、Prometheus、Terraform、Etcd 全部用 Go 写就。如果你有 C 或 JavaScript 基础，Go 是你进入"系统语言"世界最高效的跳板。

**Go 承诺了三件事：**

1. **编译快**——没有头文件，增量编译快到像脚本语言
2. **运行稳**——GC 自动管理内存，没有 C 的野指针噩梦
3. **并发易**——goroutine 让你用同步的写法写出异步的性能

如果你来自 C 世界，Go 让你从"手动管理一切"中解放；如果你来自 JS 世界，Go 给你静态类型和编译期安全保障，同时保留了回调 + 闭包式的高效表达。

> **这门课的目标：** 一个下午，跑通 Go 的核心脉络。你不需要记住所有语法细节——记住"Go 怎么思考"就够了。

---

## 第一章：Go 设计哲学

Go 由 Ken Thompson（C 语言之父）、Rob Pike（Unix 先驱）、Robert Griesemer（JS引擎开发者）在 2007 年设计。三个人带着对 C++ 和 Java 的痛，想造一门"简单到一周上手，复杂到可以写 OS"的语言。

### 1.1 简洁至上

| 特性 | C / C++ | Java / JS | Go |
|------|---------|-----------|-----|
| 继承 | 有（虚函数表） | 有（class extends） | **没有** |
| 泛型 | 有（模板） | 有 | 1.18 之前没有 |
| 异常 | 无（返回码） | try / catch | **没有**（error 返回值） |
| 类 | 有 | 有 | **没有**（struct + method） |

Go 的哲学是：**少就是多**。没有继承，因为你不需要——用组合就行。没有 try/catch，因为错误就是值，不值得打断控制流。没有面向对象那一套，因为类型 + 方法 + 接口已经够用了。

### 1.2 组合优于继承

```go
// C/JS 的做法：定义一个 Widget 基类，Button 继承它
// Go 的做法：组合
type Clickable struct{ onClick func() }

type Button struct {
    Label    string
    Clickable  // 嵌入——"has-a" 而不是 "is-a"
}
```

Go 嵌入字段（embedding）的本质不是继承，是语法糖——嵌入类型的方法自动"提升"到外层。这是一个**组合**范例，不是**继承**范例。

> **最佳实践：** 优先用 `struct` 组合 + `interface` 抽象，不要试图模拟继承。

### 1.3 约定优于配置

Go 语言级别的约定极多，但每条都是为了**消灭争论**：

- **`go fmt`**——全宇宙统一的代码格式。没有空格 vs Tab 之争
- **首字母大写 = 导出**——`func Foo()` 是 public，`func foo()` 是 private。简单粗暴
- **目录即包名**——`package main` 必然在 `main.go`？不一定是，但约定是
- **文件名不带下划线送测试**——`foo_test.go` 自动识别为测试文件

> **从 JS 来的你：** ESLint + Prettier + 一堆配置终于解决了代码风格问题。Go 告诉你：别配置了，我来定。

### 1.4 并发原语内建

这是 Go 最大的卖点。不像 C 你得用 pthread、JS 你得碰 Event Loop + Worker Thread，Go **在语言层面**内置了并发原语：

```go
go doSomething()       // 启动一个 goroutine，类似于 "async fire and forget"
ch := make(chan int)   // 创建 channel，类似 JS 的可读可写流，但类型安全
```

不是库特性，是**语言关键字**。这意味着编译器知道怎么优化它们。

### 1.5 编译速度

C/C++ 编译慢的罪魁祸首：头文件。每个 `.c` 文件都要 `#include` 一堆东西，预处理器展开后成千上万行。

Go 的解决思路：
- **无头文件**——每个包直接编译，缓存结果
- **显式导入**——`import "fmt"`，编译器一眼就知道依赖关系
- **增量编译**——改了一个文件，只重编译那个包

一个中等规模的 Go 项目（50 万行）可以在 **10-15 秒** 内完成全量编译。同等规模的 C++ 项目需要几分钟。

> **JS 类比：** Go 的增量编译 → Vite 的 HMR。都是"只重编改的部分"。

---

## 第二章：基础语法速通

这一章快速过一遍 Go 基础语法。如果你是 C / JS 开发者，大部分概念你已经知道——我着重讲**Go 的特殊之处**。

### 2.1 变量声明

Go 有三种声明方式：

```go
// 方式一：显式类型声明（类似 C）
var name string = "Alice"

// 方式二：类型推断（类似 JS let）
var name = "Alice"

// 方式三：短声明（只在函数内可用）
name := "Alice"       // 等价于 var name = "Alice"
count := 42           // int，不是 float
pi := 3.14            // float64
ok := true            // bool
```

**零值机制（Zero Value）：** 这是 Go 和 C/JS 的关键区别之一。声明了不赋值？Go 不给 undefined，也不让野指针，而是给一个类型安全的零值：

```go
var i int              // 0
var f float64          // 0.0
var s string           // ""（空字符串）
var b bool             // false
var p *int             // nil（不是 C 里的随机地址）
```

> **从 C 来的你：** 再也不用担心未初始化变量读到的值不确定了。Go 保证零值。
> **从 JS 来的你：** `undefined` 是 JS 的万恶之源之一。Go 直接消灭了它。

**多重赋值：**

```go
a, b := 1, "hello"
a, b = b, a            // 交换值！无需临时变量
```

### 2.2 流程控制

**if 语句：**

```go
// 标准形式（没有括号！）
if x > 0 {
    fmt.Println("positive")
} else if x < 0 {
    fmt.Println("negative")
} else {
    fmt.Println("zero")
}

// Go 特色：if 中可以加"简短语句"
if value := getValue(); value > 10 {
    fmt.Println("big:", value)
} // value 在这里就不可见了——限定作用域
```

**for 循环（没有 while）：**

Go 只有一个循环关键字：`for`。需要 while？用 `for condition {}`：

```go
// 经典 for
for i := 0; i < 10; i++ {
    fmt.Println(i)
}

// while 模式
sum := 1
for sum < 1000 {
    sum += sum
}

// 无限循环
for {
    // 等价于 C 的 while(1) 或 JS 的 while(true)
    break  // 总要有个出口
}

// range 遍历（类似 JS 的 for...of）
nums := []int{1, 2, 3}
for index, value := range nums {
    fmt.Println(index, value)
}
for _, value := range nums {  // 用 _ 忽略索引
    fmt.Println(value)
}
```

**switch（自动 break，不需要 fallthrough 关键字才穿透）：**

```go
// Go 的 switch 每个 case 默认 break
// 想穿透？显式用 fallthrough
switch x {
case 1:
    fmt.Println("one")
case 2:
    fmt.Println("two")
default:
    fmt.Println("other")
}

// switch 可以不带表达式——相当于 if-else 链
score := 85
switch {
case score >= 90:
    fmt.Println("A")
case score >= 80:
    fmt.Println("B")
default:
    fmt.Println("C")
}
```

> **从 C/JS 来的你：** 忘记 `break` 导致 case 穿透是无数 bug 的源头。Go 默认 break，这个设计太舒服了。

### 2.3 函数

Go 函数的核心特征：**多返回值**和**defer**。

```go
// 多返回值——Go 版本的结构化错误处理基础
func div(a, b int) (int, error) {
    if b == 0 {
        return 0, errors.New("division by zero")
    }
    return a / b, nil
}

// 命名返回值（可读性极好）
func div(a, b int) (result int, err error) {
    if b == 0 {
        err = errors.New("division by zero")
        return  // 裸 return，返回 result 和 err 的当前值
    }
    result = a / b
    return
}
```

**defer——Go 版的 RAII / finally：**

```go
func readFile(path string) ([]byte, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer f.Close()  // 函数返回时执行——无论是否出错
    
    return io.ReadAll(f)
}
```

defer 是**声明式资源管理**：
- 你在打开资源的地方**立即声明**关闭它
- 不再需要在每个 return 路径上都写 `f.Close()`
- defer 语句按 **LIFO** 顺序执行（后 defer 的先执行）

> **从 C 来的你：** 再也不怕忘记 free 或者 goto cleanup 了。
> **从 JS 来的你：** 类似 `try { } finally { }`，但更简洁。

**闭包——Go 支持一等函数：**

```go
// adder 返回一个闭包
func adder() func(int) int {
    sum := 0
    return func(x int) int {
        sum += x  // 捕获外部变量 sum
        return sum
    }
}

a := adder()
fmt.Println(a(1))  // 1
fmt.Println(a(2))  // 3
fmt.Println(a(3))  // 6
```

### 2.4 数组与切片

**数组（Array）**——定长，值类型：

```go
var arr [5]int          // [0 0 0 0 0]
arr := [3]int{1, 2, 3}  // [1 2 3]
// 数组长度是类型的一部分！[3]int 和 [5]int 是不同类型
```

**切片（Slice）**——动态数组，引用类型。这是 Go 中最常用的序列类型。

```go
// 创建切片
s := []int{1, 2, 3}         // 字面量创建
s := make([]int, 5)          // len=5, cap=5
s := make([]int, 3, 10)      // len=3, cap=10
s := arr[1:4]                // 从数组切出 slice

// 追加
s = append(s, 4)             // 可能触发扩容
s = append(s, 5, 6, 7)       // 追加多个
s = append(s, other...)      // 展开另一个 slice 追加
```

**Slice 底层结构——理解这个就理解了 Go 一半的内存模型：**

```
slice := make([]int, 3, 5)
// 内存中：
// +--------+--------+--------+
// | ptr    | len(3) | cap(5) |
// +--------+--------+--------+
//   ↓
//   [0, 0, 0, _, _]  ← 底层数组，cap=5
```

- **ptr**：指向底层数组的指针
- **len**：当前元素个数（你实际能看到的部分）
- **cap**：容量（底层数组总长度）

**append 扩容策略：**

```go
s := []int{}
fmt.Println(cap(s))         // 0
s = append(s, 1)
fmt.Println(cap(s))         // 1   → 小于 256 时，翻倍
s = append(s, 2, 3, 4)
fmt.Println(cap(s))         // 4   → 翻倍：1→2→4

// 容量 >= 256 后，扩容因子变为 1.25 倍
// 这种"指数+线性"混合策略兼顾了小切片速度和内存大切片浪费
```

> **性能注意点：** `append` 可能导致底层数组重新分配——当 cap 不够时，Go 新分配一块更大的内存，把旧数据拷贝过来。频繁 append 大数据量的切片，最好用 `make([]T, 0, expectedSize)` 提前分配好容量。

### 2.5 Map

Go 的 map 是**哈希表实现**：

```go
// 创建
m := make(map[string]int)
m := map[string]int{"a": 1, "b": 2}

// CRUD
m["c"] = 3              // 写入
v := m["a"]             // 读取——不存在返回零值
v, ok := m["z"]         // ok=false 表示 key 不存在
delete(m, "a")          // 删除

// 遍历——**无序！**
for k, v := range m {
    fmt.Println(k, v)
}
```

**Go map 的关键特性：**

1. **遍历无序**——每次运行遍历顺序都不同。这是故意的，防止你依赖顺序
2. **并发不安全**——一个 goroutine 写，另一个读了就会 crash（不是数据不一致，是直接 panic）
3. **读取不存在的 key 返回零值**——所以要用 `v, ok := m[key]` 双返回值模式

> **从 C 来的你：** Go map 是内置的哈希表，比你自己写拉链法好一万倍。但注意并发场景需要 `sync.Map` 或 `sync.RWMutex` 保护。
> **从 JS 来的你：** Go 的 `map` ≈ JS 的 `Map` 对象，但更轻量（没有 `.size` 属性直接用 `len()`）。

### 2.6 字符串

Go 字符串是**不可变的 UTF-8 字节序列**：

```go
s := "你好，世界"    // 很安全，UTF-8
fmt.Println(len(s))  // 15（不是 5！len 返回的是字节数）

// 用 rune 遍历真正的字符
for _, r := range s {
    fmt.Printf("%c ", r)  // 你 好 ，世 界
}

// 用字节索引遍历——遇到多字节字符会乱码
for i := 0; i < len(s); i++ {
    fmt.Printf("%x ", s[i])  // 字节值
}
```

**rune = int32 别名：** 用来表示一个 Unicode 码点。Go 用 UTF-8 作为字符串编码，但 `rune` 是解码后的 Unicode 值。

**字符串拼接性能：**

```go
// ❌ 差：字符串不可变，每次 + 都产生新字符串
s := ""
for i := 0; i < 1000; i++ {
    s += "a"  // O(n²) 级别
}

// ✅ 好：用 strings.Builder
var sb strings.Builder
for i := 0; i < 1000; i++ {
    sb.WriteString("a")
}
s := sb.String()  // O(n)
```

> **性能注意点：** `strings.Builder` 内部维护一个 `[]byte`，按需扩容（类似 slice append），避免了字符串不可变导致的反复分配。高频拼接场景必备。

### 2.7 指针

Go 有指针，但**没有指针运算**（no pointer arithmetic）：

```go
x := 42
p := &x        // 取地址
fmt.Println(*p) // 42 —— 解引用
*p = 100        // 通过指针修改
fmt.Println(x)  // 100

// ❌ 不能这样做：
// p++    // 编译错误！Go 禁止指针运算
```

Go 的指针用途是**引用传递**和**共享访问**，不是遍历内存。这使得 GC 的工作简单得多。

> **从 C 来的你：** Go 指针是安全的指针——你知道它指向某个对象，而不是数组中的一个偏移量。再也不用写 `*(p + i * stride)` 了。
> **从 JS 来的你：** 其实 JS 的对象引用就是指针的概念，Go 把它显式化了。

---

## 第三章：面向接口编程

Go 没有类，没有继承，但它有 **interface**。这是 Go 实现多态的方式，也是 Go 最优雅的设计之一。

### 3.1 interface{} 与 any

```go
// 空接口——能"容纳"任何类型
var v interface{}
v = 42         // ok
v = "hello"    // ok
v = true       // ok

// Go 1.18+：any 是 interface{} 的别名
var v any = 42
```

空接口相当于 C 的 `void*` 或 JS 的任意值。**但它不是类型安全的**——你随时可能拿到一个你没想到的类型。所以在实践中，空接口是用来做"不知道类型但先拿着"的场景（比如 JSON 解析的 `map[string]any`）。

### 3.2 鸭子类型：隐式实现

Go 的接口是**隐式的**（implicit satisfaction）。你不需要写 `implements`：

```go
// 定义一个接口
type Writer interface {
    Write([]byte) (int, error)
}

// 定义一个 struct——不需要声明它实现了 Writer
type FileWriter struct {
    path string
}

// 只要实现了接口中的所有方法，就自动"满足"该接口
func (f FileWriter) Write(data []byte) (int, error) {
    return os.WriteFile(f.path, data, 0644)
}

// 使用——任何满足 Writer 接口的类型都能传进来
func saveData(w Writer, data []byte) error {
    _, err := w.Write(data)
    return err
}
```

> **从 C 来的你：** 不需要虚函数表、不需要 `->` 操作符、不需要在头文件声明。Go 的接口是**结构化的类型匹配**——你长这个样，你就是这个类型。
> **从 JS 来的你：** 有点像 TypeScript 的结构类型（structural typing）：`{ write: (data: Uint8Array) => ... }` 就是 Writer。

**这种设计带来了什么好处？**

- **松耦合**——接口定义者和实现者完全解耦。我在包 A 定义 `Writer`，你在包 B 实现它，互不知晓
- **测试友好**——写 mock 只需要实现接口，不需要 mock 框架
- **最小接口原则**——接口尽量小，一个方法最好

### 3.3 类型断言与 Type Switch

当你有一个 `interface{}` 值，想要"取回"背后的具体类型时，需要类型断言：

```go
var v any = "hello world"

// 类型断言——语法类似 Java 的类型转换
s := v.(string)         // 如果 v 不是 string，panic
s, ok := v.(string)     // 安全的断言，ok=false 表示类型不匹配

if s, ok := v.(string); ok {
    fmt.Println("是字符串:", s)
} else {
    fmt.Println("不是字符串")
}
```

**Type Switch —— 优雅的多类型分支：**

```go
func inspect(v any) {
    switch val := v.(type) {
    case int:
        fmt.Println("整数:", val)
    case string:
        fmt.Println("字符串:", val)
    case bool:
        fmt.Println("布尔:", val)
    case []byte:
        fmt.Println("字节数组，长度:", len(val))
    case nil:
        fmt.Println("空值")
    default:
        fmt.Println("未知类型")
    }
}
```

> **最佳实践：** 宁可用 Type Switch 处理多种情况，也不要写一堆 `v.(type1); v.(type2); v.(type3)` 的 if-ok 链。

### 3.4 常见标准接口

Go 标准库大量使用接口。以下是最常用的四个：

**`error` 接口——最核心的接口之一：**

```go
type error interface {
    Error() string
}
```

任何实现了 `Error() string` 方法的类型都可以作为 error 使用。这意味着你可以**创建携带额外信息的错误类型**。

**`Stringer` 接口——类似 Java 的 `toString()`：**

```go
type Stringer interface {
    String() string
}

type Person struct {
    Name string
    Age  int
}

// 实现 Stringer
func (p Person) String() string {
    return fmt.Sprintf("%s (%d岁)", p.Name, p.Age)
}
```

**`io.Reader` 和 `io.Writer`——整个 I/O 世界的基石：**

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}
```

只看这两个接口，你就能猜到：
- 文件、网络连接、压缩流、加密流、内存缓冲——都实现了 Reader/Writer
- 你可以用 `io.Copy(w, r)` 在任意 Reader 和 Writer 之间复制数据
- 你可以用 `io.MultiReader` 把多个 Reader 串起来读

> **性能注意点：** `io.Copy` 会使用 32KB 的缓冲，直接在内核态和用户态之间传输数据。用 `bufio.NewReader` / `bufio.NewWriter` 包裹可以减少系统调用。

### 3.5 依赖注入：interface 作为函数参数

这是 Go 中**高级而优雅**的工程模式。核心思想：函数/方法不直接依赖具体类型，而是依赖接口：

```go
// ❌ 坏：直接依赖具体类型
func SaveUser(user User, db *sql.DB) error { ... }

// ✅ 好：依赖接口
type UserStore interface {
    Save(user User) error
}

func SaveUser(user User, store UserStore) error {
    // 可以传入真实 db，也可以传入 mock，也可以传入缓存层
    return store.Save(user)
}
```

**这有什么用？**
1. **可测试**——传一个 `mockUserStore` 进去就行，不用连真实数据库
2. **可替换**——今天用 MySQL，明天换 PostgreSQL，不用改业务代码
3. **可包装**——用一个加了缓存的 store 包裹底层 store

> **与 C 比较：** C 中做类似的事情需要函数指针 + void* 上下文，类型安全靠自己。Go 的接口在编译期保证类型安全。
> **与 JS 比较：** JS 的"鸭子类型"其实和 Go 一样——你传一个 `{save: fn}` 就行。但 Go 在编译期检查这个对象确实有 `save` 方法。

---

## 第四章：Goroutine 与 Channel（核心章节）

这是 Go 的灵魂。如果你只从这门课带走一个知识点，那就是 **goroutine 和 channel 的思维方式**。

### 4.1 Goroutine 的本质

goroutine 是 Go 的并发执行单元。它**不是操作系统线程**，而是**用户态协程**。

| | OS 线程 | Goroutine |
|--|---------|-----------|
| 创建成本 | ~1MB 栈空间 | ~2KB 栈空间（可伸缩） |
| 切换成本 | 内核态切换（μs 级） | 用户态切换（ns 级） |
| 创建数量 | 几千到极限 | 几百万轻轻松松 |
| 调度器 | OS 内核 | Go 运行时 |

```go
// 启动 goroutine——就这么简单
go func() {
    fmt.Println("我在另一个 goroutine 里执行")
}()

// 或者在一个已存在的函数前加 go
go doWork()
```

对比 C 的 pthread_create 和 JS 的 new Worker：

| C pthread | JS Worker | Go goroutine |
|-----------|-----------|--------------|
| 手动管理线程池 | 消息传递 | 开箱即用 |
| `pthread_create` 约 15-30 行样板代码 | `new Worker('file.js')` 需要单独文件 | `go f()` 两个字符 |
| 共享内存 + mutex | 序列化拷贝 | 共享内存 + channel 任选 |

### 4.2 GMP 调度模型

理解 GMP 是理解 Go 并发性能的关键。

```
Go 运行时调度器
┌──────────────────────────────────────────────────┐
│  G（Goroutine）─→ M（Machine/OS Thread）─→ P（Processor）│
└──────────────────────────────────────────────────┘
```

**三个角色：**
- **G（Goroutine）**——你的代码。G 中存储：栈指针、当前 PC、关联的 M
- **M（Machine）**——操作系统线程。由 OS 调度，M 的数量 ≈ GOMAXPROCS（默认 CPU 核数）
- **P（Processor）**——逻辑处理器。分配 M 执行 G，每个 P 维护一个本地 G 队列

**调度流程（简化版）：**

1. 你用 `go f()` 创建了一个 G，它被放入 P 的本地队列
2. P 关联到一个 M，M 从 P 的队列中取出 G 执行
3. 当 G 遇到阻塞操作（I/O、channel 收发、系统调用）：
   - 阻塞的 G 被移出
   - P 从队列中取下一个 G 给 M 执行
   - 阻塞的 G 恢复后，被重新放入队列
4. 如果某个 P 的队列空了，它可以从其他 P "偷" G（work stealing）

> **性能注意点：** GOMAXPROCS 控制着同时执行用户代码的 OS 线程数。默认 = CPU 核数。I/O 密集场景可以考虑调大，CPU 密集场景保持默认。

**P 的本地队列 vs 全局队列：**
- 每个 P 有自己的本地队列（无锁，高性能）
- 当所有 P 的本地队列都空时，从全局队列取
- 当全局队列也空时，从其他 P "偷"一半（work stealing）

这个模型让 Go 的调度效率接近 O(1) 调度器，只是它是用户态的。

### 4.3 Channel：Goroutine 之间的通信

**"不要通过共享内存来通信，而要通过通信来共享内存。"**——Rob Pike

Channel 是 Go 最重要的并发抽象：一个有类型的、并发安全的管道。

```go
// 创建一个 channel
ch := make(chan int)      // 无缓冲 channel（同步）
ch := make(chan int, 10)  // 有缓冲 channel（异步，容量=10）

// 发送和接收
ch <- 42           // 发送 42 到 channel
value := <-ch      // 从 channel 接收
value, ok := <-ch  // ok=false 表示 channel 已关闭且为空

// 关闭 channel
close(ch)
```

#### 无缓冲 Channel（同步）

```go
ch := make(chan int)

// goroutine A：会阻塞直到有人接收
go func() {
    ch <- 42  // <- 阻塞在这里，直到有人从 ch 接收
}()

// goroutine B（当前 goroutine）
value := <-ch  // <- 阻塞在这里，直到有人发送
fmt.Println(value) // 42
```

**无缓冲 channel 的行为 = 同步通信：**
- 发送方等待接收方准备好
- 接收方等待发送方准备好
- 两者"握手"完成后继续执行

#### 有缓冲 Channel（异步）

```go
ch := make(chan int, 3)  // 缓冲区大小为 3

ch <- 1  // 不阻塞（缓冲区空了，写入 1 个）
ch <- 2  // 不阻塞（还有 1 个空位）
ch <- 3  // 不阻塞（还有一个空位）
ch <- 4  // 阻塞！缓冲区满了，等待有人取走
```

**有缓冲 channel 的行为 = 异步队列：**
- 发送方：缓冲区没满就不阻塞
- 接收方：缓冲区没空就不阻塞
- 本质上就是一个**并发安全的 FIFO 队列**

> **最佳实践：** 默认用无缓冲 channel。只有当你有明确的"生产者-消费者"模式且有速率差异时，才使用有缓冲 channel。
> **性能注意点：** 缓冲大小并非越大越好。太大的缓冲会增加 GC 压力（channel 底层是堆分配）。

### 4.4 select 多路复用

`select` 是 Go 中**最强大的并发原语**。它让你在一个 goroutine 中等待多个 channel 操作：

```go
select {
case msg := <-ch1:
    fmt.Println("从 ch1 收到:", msg)
case msg := <-ch2:
    fmt.Println("从 ch2 收到:", msg)
case ch3 <- 42:
    fmt.Println("成功向 ch3 发送 42")
case <-time.After(1 * time.Second):
    fmt.Println("超时了！")
default:
    fmt.Println("没有一个 channel 准备好")
}
```

**select 的规则：**
1. 同时等待所有 case，哪个准备好了执行哪个
2. 如果多个 case 同时准备好，**随机选择一个**执行（防止饥饿）
3. 如果没有 case 准备好，且没有 default，则**阻塞等待**
4. 如果有 default，且没有 case 准备好，则执行 default（非阻塞）

> **从 JS 来的你：** select ≈ `Promise.race()` + `Promise.any()`。但 select 比 Promise.race 多一个重要功能——**发送也可以等待**。

**超时控制模式：**

```go
ch := make(chan int)
go func() {
    time.Sleep(2 * time.Second)
    ch <- 1
}()

select {
case v := <-ch:
    fmt.Println("收到:", v)
case <-time.After(1 * time.Second):
    fmt.Println("超时！任务没有在 1 秒内完成")
}
```

### 4.5 WaitGroup 与 Once

**sync.WaitGroup——等待一组 goroutine 完成：**

```go
var wg sync.WaitGroup

for i := 0; i < 10; i++ {
    wg.Add(1)  // 计数器 +1
    go func(id int) {
        defer wg.Done()  // 计数器 -1
        doWork(id)
    }(i)
}

wg.Wait()  // 阻塞，直到计数器归零
fmt.Println("所有 goroutine 完成")
```

> **与 C 比较：** C 的 pthread_join 只能等一个线程。WaitGroup 可以等任意数量的 goroutine。
> **与 JS 比较：** wg.Wait() ≈ await Promise.all([...])，但无需收集所有 promise。

**sync.Once——只执行一次的代码：**

```go
var once sync.Once

for i := 0; i < 10; i++ {
    go func() {
        once.Do(func() {
            fmt.Println("这行只会打印一次")
        })
    }()
}
```

常用于**单例初始化、懒加载**等场景。无论多少个 goroutine 同时调用 `once.Do`，只有第一个会执行。

### 4.6 常见并发模式

#### Worker Pool（工作池）

控制并发数量的经典模式：

```go
func workerPool(jobs <-chan int, results chan<- int, workerCount int) {
    var wg sync.WaitGroup
    
    for i := 0; i < workerCount; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            for job := range jobs {  // jobs 关闭后，range 自动退出
                results <- process(job)
            }
        }(i)
    }
    
    wg.Wait()
    close(results)
}
```

#### Pipeline（管道）

把一个大任务拆成多个阶段，每个阶段是一个 goroutine，通过 channel 连接：

```go
func generate(nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        for _, n := range nums { out <- n }
        close(out)
    }()
    return out
}

func square(in <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        for n := range in { out <- n * n }
        close(out)
    }()
    return out
}

// 使用
for s := range square(generate(2, 3, 4)) {
    fmt.Println(s)  // 4, 9, 16
}
```

#### Fan-in（扇入）

```go
func fanIn(chs ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    for _, ch := range chs {
        wg.Add(1)
        go func(c <-chan int) {
            defer wg.Done()
            for v := range c { out <- v }
        }(ch)
    }
    go func() { wg.Wait(); close(out) }()
    return out
}
```

### 4.7 context 包——超时、取消、值传递

`context` 是 Go 标准库中最重要的包之一。

**1. 超时控制：**

```go
ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
defer cancel()

result, err := doWorkWithContext(ctx)
```

**2. 取消传播：**

```go
ctx, cancel := context.WithCancel(context.Background())

go func() {
    select {
    case <-ctx.Done():
        return  // 收到取消信号，优雅退出
    case result := <-workCh:
        fmt.Println("完成:", result)
    }
}()

cancel()  // 取消——所有派生 context 和 goroutine 都收到通知
```

**3. 值传递：**

```go
ctx := context.WithValue(context.Background(), "request_id", "abc-123")
reqID := ctx.Value("request_id").(string)
```

> **最佳实践：**
> - context 作为函数的**第一个参数**（约定命名 `ctx`）
> - 沿着调用链显式传递，不用全局变量
> - `context.WithValue` 只传请求级元数据（trace_id、user_id），别替代函数参数

---

## 第五章：错误处理与测试

### 5.1 error 接口 vs panic/recover

Go 哲学：**错误是值，不是事件**。普通错误通过返回值传递，不可恢复的异常才用 panic。

```go
// 正常错误——返回 error（最常用模式）
f, err := os.Open("file.txt")
if err != nil {
    return fmt.Errorf("打开文件失败: %w", err)
}
defer f.Close()

// panic——极少使用，通常是程序 bug
if err != nil && unrecoverable {
    panic(fmt.Sprintf("不可能发生的错误: %v", err))
}
```

**panic/recover——类似 try/catch，但在 Go 中极少用：**

```go
defer func() {
    if r := recover(); r != nil {
        fmt.Println("从 panic 恢复了:", r)
    }
}()
panic("出事了")
```

> **最佳实践：** panic = 程序 bug（空指针、越界）。业务逻辑错误永远用 error。

### 5.2 errors.Is / errors.As（Go 1.13+）

```go
var ErrNotFound = errors.New("not found")
err := fmt.Errorf("查询失败: %w", ErrNotFound)

// errors.Is：检查错误链中是否包含目标错误
if errors.Is(err, ErrNotFound) {
    fmt.Println("没找到")
}

// errors.As：取出错误链中特定类型的错误
var pathErr *os.PathError
if errors.As(err, &pathErr) {
    fmt.Println("路径错误:", pathErr.Path)
}
```

> **从 JS 来的你：** `errors.Is` ≈ `instanceof`，`errors.As` ≈ 类型转换 + instanceof。

### 5.3 自定义错误类型

```go
type ValidationError struct {
    Field string
    Value any
    Msg   string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("字段 %s 验证失败: %s", e.Field, e.Msg)
}
```

### 5.4 单元测试

Go 有内建测试框架：

```go
// file: math_test.go
package main
import "testing"

func TestAdd(t *testing.T) {
    result := add(2, 3)
    if result != 5 {
        t.Errorf("add(2,3) = %d; want 5", result)
    }
}
```

**表格驱动测试——Go 的标准测试风格：**

```go
func TestDivide(t *testing.T) {
    tests := []struct {
        name     string
        a, b     int
        want     int
        wantErr  bool
    }{
        {"正常", 10, 2, 5, false},
        {"除零", 10, 0, 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := divide(tt.a, tt.b)
            if (err != nil) != tt.wantErr {
                t.Errorf("错误状态不对")
            }
            if got != tt.want {
                t.Errorf("got %d, want %d", got, tt.want)
            }
        })
    }
}
```

### 5.5 基准测试

```go
func BenchmarkStringConcat(b *testing.B) {
    for i := 0; i < b.N; i++ {
        var s string
        for j := 0; j < 100; j++ { s += "a" }
    }
}

func BenchmarkStringBuilder(b *testing.B) {
    for i := 0; i < b.N; i++ {
        var sb strings.Builder
        for j := 0; j < 100; j++ { sb.WriteString("a") }
        _ = sb.String()
    }
}
```

运行：`go test -bench . -benchmem`

```
BenchmarkStringConcat     1000000    1234 ns/op   5200 B/op   99 allocs/op
BenchmarkStringBuilder    5000000     240 ns/op    896 B/op    1 allocs/op
```

`strings.Builder` 快 5 倍，内存分配少 98 次。

---

## 第六章：Go 工具链与生态

### 6.1 go mod——模块管理

```bash
go mod init github.com/yourname/project   # 初始化
go get github.com/gin-gonic/gin           # 添加依赖
go mod tidy                                # 整理依赖
go mod graph                               # 查看依赖图
go mod edit -replace old=new               # 本地替换（开发神器）
```

**go.mod 文件：**

```
module github.com/yourname/project
go 1.22

require (
    github.com/gin-gonic/gin v1.9.1
)
```

> **从 JS 来的你：** go.mod ≈ package.json + lockfile。go.sum 是完整性校验。
> **从 C 来的你：** 终于不用手动下载库、配置包含路径了。

### 6.2 go build / run / test / fmt / vet

```bash
go build               # 编译
go run main.go         # 编译并运行
go test ./...          # 运行所有测试
go fmt ./...           # 格式化——这是标准，不是选项
go vet ./...           # 静态分析
```

**go vet 发现的问题举例：** Printf 格式串不匹配、Lock/Unlock 错误用法、context 未传递。

> Go 编译结果是**静态链接**的单个二进制。不需要运行时和依赖。

### 6.3 常用标准库

| 包 | 用途 |
|----|------|
| `net/http` | HTTP 客户端 + 服务端 |
| `encoding/json` | JSON 序列化/反序列化 |
| `sync` | Mutex、RWMutex、Map、Pool |
| `io` | Reader/Writer 抽象 |
| `os` | 系统操作 |
| `time` | 时间与定时器 |

**5 行代码的 HTTP Server：**

```go
package main
import ("fmt"; "net/http")
func main() {
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        fmt.Fprintf(w, "Hello, %s!", r.URL.Path[1:])
    })
    http.ListenAndServe(":8080", nil)
}
```

### 6.4 编译优化：内联与逃逸分析

**内联（Inlining）：** 短小函数自动展开，消除调用开销。

```bash
go build -gcflags=-m main.go
# ./main.go:10:6: can inline add
# ./main.go:15:11: inlining call to add
```

**逃逸分析（Escape Analysis）：** 编译器判断变量放栈还是堆。

```bash
go build -gcflags='-m -l' main.go
# ./main.go:5:2: moved to heap: x    ← 逃逸到堆
```

> **性能注意点：** 栈分配零 GC 压力。常见逃逸原因：返回局部变量指针、值放入 interface{}、闭包捕获外部变量。

---

## 结论：Go 的思维方式

1. **简洁至上**——不做你不需要的事
2. **组合 > 继承**——struct + interface = 强大的类型系统
3. **并发是语言的一部分**——goroutine + channel + select
4. **错误是值，不是事件**——检查它、返回它、包装它
5. **代码风格是强制的**——go fmt 消灭了代码风格争论

**下一课预告：** Go 运行时——GC 原理、内存模型、cgo、进阶性能调优。然后进入 Rust，与 Go 做对比。

---

## 练习题目

### 练习 1：并发素数判断器

用 Worker Pool 模式判断一批数字是否为素数：
- 输入：`[]int{11, 15, 17, 21, 23, 29, 30, 31, 37}`
- 4 个 worker goroutine 并发处理
- 输出每个数字的素数判断结果

**涉及知识点：** goroutine、channel、WaitGroup

### 练习 2：并发爬虫模拟

模拟爬取 10 个 URL：
- `time.Sleep` 随机延迟（300-800ms）
- 最多 3 个并发
- `context.WithTimeout` 设置 3 秒超时
- 输出每个 URL 的响应时间和总耗时

**涉及知识点：** context 超时、WaitGroup、select

### 练习 3：HTTP Server + JSON API

HTTP Server 监听 `:8080`：
- `POST /tasks` — 提交任务，返回任务 ID
- `GET /tasks/:id` — 查询任务状态（pending / processing / done）
- 内部 goroutine 池处理任务
- `sync.RWMutex` 保护状态 map

**涉及知识点：** net/http、encoding/json、sync.RWMutex、goroutine
