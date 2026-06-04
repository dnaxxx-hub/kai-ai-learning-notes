# C++20 协程深度与异步网络编程

> 从底层机制到实战模式 — 协程是C++20最复杂也最强大的特性

---

## 1. 协程基础概念

C++20 的协程是**无栈协程**（stackless coroutine）：可挂起（suspend）和恢复（resume）的函数。与线程不同，协程在用户态切换，不涉及内核上下文切换。

### 1.1 协程的三个关键对象

```cpp
#include <coroutine>
#include <iostream>
#include <optional>

// 一个协程框架包含三个关键部分：
// 1. promise_type  — 协程的状态管理器
// 2. awaitable     — 可等待体（决定是否挂起）
// 3. coroutine_handle — 底层句柄（恢复/销毁）

// 最小生成器
template<typename T>
struct Generator {
    struct promise_type {
        T current_value;
        
        Generator get_return_object() {
            return Generator{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }
        
        // initial_suspend: 创建时是否立即挂起
        // suspend_always → 需要显式 resume() 才开始
        std::suspend_always initial_suspend() noexcept { return {}; }
        
        // final_suspend: 执行完是否挂起
        std::suspend_always final_suspend() noexcept { return {}; }
        
        void unhandled_exception() { std::terminate(); }
        void return_void() {}
        
        // co_yield 的处理
        std::suspend_always yield_value(T value) noexcept {
            current_value = value;
            return {};
        }
    };
    
    std::coroutine_handle<promise_type> handle_;
    
    explicit Generator(auto h) : handle_(h) {}
    ~Generator() { if (handle_) handle_.destroy(); }
    
    Generator(const Generator&) = delete;
    Generator& operator=(const Generator&) = delete;
    
    // 移动构造（C++20 协程句柄必须是 move-only）
    Generator(Generator&& other) noexcept : handle_(other.handle_) {
        other.handle_ = nullptr;
    }
    
    bool next() {
        if (!handle_) return false;
        handle_.resume();
        return !handle_.done();
    }
    
    T value() { return handle_.promise().current_value; }
};

// 使用
Generator<int> range(int start, int end) {
    for (int i = start; i < end; ++i)
        co_yield i;
}

int main() {
    auto gen = range(0, 5);
    while (gen.next()) {
        std::cout << gen.value() << " ";  // 0 1 2 3 4
    }
}
```

### 1.2 协程的生命周期

```
[创建]
   ↓ initial_suspend()
   ↓     → suspend_always: 挂起，等待 resumen
   ↓     → suspend_never:  立即开始执行
   ↓
[执行体 co_body]
   ↓ co_yield → yield_value() → suspend_always/suspend_never
   ↓ co_await → await_ready() → await_suspend() → await_resume()
   ↓ co_return → return_value()/return_void() → final_suspend()
   ↓
[结束]
   ↓ final_suspend() → suspend_always: 停在终结态 → 手动 destroy()
   ↓                 → suspend_never:  自动析构
   ↓ handle_.destroy()
```

### 1.3 awaitable 接口

任何类型的对象，只要实现了 `await_ready`、`await_suspend`、`await_resume` 三个方法，就可以被 `co_await`。

```cpp
#include <coroutine>
#include <chrono>
#include <thread>
#include <iostream>

// 自定义 awaitable：让协程睡眠指定时间
struct SleepAwaitable {
    std::chrono::milliseconds duration_;
    
    // 是否已经就绪（通常 false 表示需要挂起）
    bool await_ready() const noexcept { return false; }
    
    // 挂起逻辑：返回 void/true/false 或 coroutine_handle
    // void       → 无条件挂起
    // true/false → 是否挂起
    // coroutine_handle → 立即恢复另一个协程
    void await_suspend(std::coroutine_handle<> handle) {
        // 启动一个线程来恢复协程
        std::thread([handle, dur = duration_] {
            std::this_thread::sleep_for(dur);
            handle.resume();  // 恢复协程
        }).detach();
    }
    
    // 恢复后获取结果
    void await_resume() const noexcept {}
};

// 使用
struct Task {
    struct promise_type {
        Task get_return_object() { return {}; }
        std::suspend_never initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
};

Task async_sleep_example() {
    std::cout << "Start sleeping...\n";
    co_await SleepAwaitable{std::chrono::seconds(1)};
    std::cout << "Woke up!\n";
}

int main() {
    async_sleep_example();
    // 注意：这里 main 不会等待协程完成
    // 因为 SleepAwaitable 在线程中恢复协程
    // main 返回后可能协程还没执行完
    std::this_thread::sleep_for(std::chrono::seconds(2));
}
```

---

## 2. 协程的三种 await_suspend 返回值

```cpp
#include <coroutine>
#include <iostream>

struct AwaitableVoid {
    bool await_ready() { return false; }
    
    // 1) 返回 void：总是挂起
    void await_suspend(std::coroutine_handle<>) {
        std::cout << "Suspended (void)\n";
    }
    
    void await_resume() {}
};

struct AwaitableBool {
    bool await_ready() { return false; }
    
    // 2) 返回 bool：true=挂起, false=不挂起（立即继续）
    bool await_suspend(std::coroutine_handle<>) {
        std::cout << "Check condition...\n";
        return true;  // 挂起
    }
    
    void await_resume() {}
};

struct AwaitableHandle {
    bool await_ready() { return false; }
    
    // 3) 返回 coroutine_handle：立即恢复另一个协程
    // 这是实现对称传递（symmetric transfer）的关键
    std::coroutine_handle<> await_suspend(std::coroutine_handle<>) {
        // 返回另一个协程的句柄，将在当前挂起后立即恢复它
        // 相当于 tail call 优化 — 无栈增长！
        return std::noop_coroutine();  // 空操作协程
    }
    
    void await_resume() {}
};
```

**对称传递（Symmetric Transfer）的重要性：**
- 避免递归导致的栈溢出
- 允许协程链式切换而不消耗栈
- 是高效协程调度器的核心机制

---

## 3. co_return 与值返回

```cpp
#include <coroutine>
#include <variant>
#include <exception>

// 可以返回值的协程
template<typename T>
struct ValueTask {
    struct promise_type {
        std::variant<std::monostate, T, std::exception_ptr> result_;
        
        ValueTask get_return_object() {
            return ValueTask{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }
        
        std::suspend_never initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        
        void return_value(T value) {
            result_.template emplace<1>(std::move(value));
        }
        
        void unhandled_exception() {
            result_.template emplace<2>(std::current_exception());
        }
    };
    
    std::coroutine_handle<promise_type> handle_;
    
    explicit ValueTask(auto h) : handle_(h) {}
    ~ValueTask() { if (handle_) handle_.destroy(); }
    
    bool is_ready() const { return handle_.done(); }
    
    T get() {
        if (!is_ready()) handle_.resume();
        if (std::holds_alternative<std::exception_ptr>(handle_.promise().result_))
            std::rethrow_exception(std::get<std::exception_ptr>(handle_.promise().result_));
        return std::get<T>(handle_.promise().result_);
    }
};

ValueTask<int> compute_value() {
    co_return 42;
}

int main() {
    auto task = compute_value();
    std::cout << task.get() << "\n";  // 42
}
```

---

## 4. 协程的实际应用模式

### 4.1 异步事件循环

```cpp
#include <coroutine>
#include <functional>
#include <map>
#include <chrono>

// 简化版异步事件循环框架
class EventLoop {
    // 注册回调 + 暂停协程
    // 事件过后恢复
    // 核心：用协程替代回调嵌套
};
```

### 4.2 生成器模式完整版

```cpp
#include <coroutine>
#include <exception>
#include <functional>

template<typename T>
class Generator {
public:
    struct promise_type;
    using handle_type = std::coroutine_handle<promise_type>;

    struct promise_type {
        T value_;
        std::exception_ptr exception_;
        
        Generator get_return_object() {
            return Generator(handle_type::from_promise(*this));
        }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void unhandled_exception() { exception_ = std::current_exception(); }
        std::suspend_always yield_value(T val) {
            value_ = std::move(val);
            return {};
        }
        void return_void() {}
    };

    handle_type handle_;
    
    Generator(handle_type h) : handle_(h) {}
    ~Generator() { if (handle_) handle_.destroy(); }
    Generator(const Generator&) = delete;
    Generator& operator=(const Generator&) = delete;
    
    Generator(Generator&& other) noexcept : handle_(other.handle_) {
        other.handle_ = nullptr;
    }

    bool next() {
        if (!handle_) return false;
        handle_.resume();
        return !handle_.done();
    }
    
    T value() {
        if (handle_.promise().exception_)
            std::rethrow_exception(handle_.promise().exception_);
        return handle_.promise().value_;
    }
};

// 惰性斐波那契
Generator<long long> fibonacci() {
    long long a = 0, b = 1;
    while (true) {
        co_yield a;
        auto next = a + b;
        a = b;
        b = next;
    }
}

// 惰性筛选素数
Generator<int> sieve(int limit) {
    std::vector<bool> is_prime(limit + 1, true);
    for (int i = 2; i <= limit; ++i) {
        if (is_prime[i]) {
            for (int j = i * i; j <= limit; j += i)
                is_prime[j] = false;
            co_yield i;
        }
    }
}

int main() {
    auto fib = fibonacci();
    for (int i = 0; i < 10; ++i) {
        fib.next();
        std::cout << fib.value() << " ";
    }
    // 0 1 1 2 3 5 8 13 21 34
    
    std::cout << "\nPrimes under 50:\n";
    auto primes = sieve(50);
    while (primes.next()) {
        std::cout << primes.value() << " ";
    }
    // 2 3 5 7 11 13 17 19 23 29 31 37 41 43 47
}
```

---

## 5. 组合多个协程

```cpp
#include <coroutine>
#include <vector>
#include <optional>
#include <iostream>

// 多路生成器：交替从多个来源取数据
template<typename T>
struct MultiGenerator {
    std::vector<Generator<T>> sources_;
    size_t index_ = 0;
    
    std::optional<T> next() {
        if (sources_.empty()) return std::nullopt;
        
        // 轮询所有源
        for (size_t i = 0; i < sources_.size(); ++i) {
            auto& src = sources_[index_];
            index_ = (index_ + 1) % sources_.size();
            
            if (src.next()) {
                return src.value();
            }
        }
        return std::nullopt;
    }
};

// 使用
Generator<int> from_to(int start, int end, int step = 1) {
    for (int i = start; i < end; i += step)
        co_yield i;
}

int main() {
    MultiGenerator<int> multi;
    multi.sources_.push_back(from_to(0, 10, 3));  // 0,3,6,9
    multi.sources_.push_back(from_to(100, 106));   // 100,101,102,103,104,105
    
    while (auto val = multi.next()) {
        std::cout << *val << " ";
    }
    // 0 100 3 101 6 102 9 103 104 105
}
```

---

## 6. 第三方协程库：cppcoro 模式

虽然 C++20 标准只提供了底层原语，社区库 `cppcoro` 提供了可直接使用的协程类型：

| 类型 | 用途 |
|------|------|
| `task<T>` | 返回值的异步任务（lazy 启动） |
| `shared_task<T>` | 多消费者共享的异步结果 |
| `generator<T>` | 同步生成器 |
| `recursive_generator<T>` | 递归生成器 |
| `async_generator<T>` | 异步生成器 |
| `io_service` | 事件循环+协程调度 |

---

## 7. 异步网络编程模式

### 7.1 Promise/Future + 协程

```cpp
#include <coroutine>
#include <future>
#include <iostream>

// 将 std::future 包装为 awaitable
template<typename T>
struct FutureAwaitable {
    std::future<T> future_;
    
    bool await_ready() const noexcept {
        return future_.wait_for(std::chrono::seconds(0)) == std::future_status::ready;
    }
    
    void await_suspend(std::coroutine_handle<> handle) {
        // 在线程池中等待 future 完成
        std::thread([this, handle] {
            future_.wait();
            handle.resume();
        }).detach();
    }
    
    T await_resume() { return future_.get(); }
};

template<typename T>
FutureAwaitable<T> make_awaitable(std::future<T> future) {
    return {std::move(future)};
}

// 使用
struct Task {
    struct promise_type {
        Task get_return_object() { return {}; }
        std::suspend_never initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
};

Task async_workflow() {
    std::cout << "Starting async workflow\n";
    
    // 等待异步操作
    auto result = co_await make_awaitable(
        std::async(std::launch::async, [] {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            return 42;
        })
    );
    
    std::cout << "Got result: " << result << "\n";
}
```

### 7.2 HTTP 请求协程化概念

```cpp
// 伪代码：假设有异步 HTTP 库
/*
task<HttpResponse> http_get(std::string url) {
    auto socket = co_await tcp_connect(url, 443);
    co_await socket.send("GET / HTTP/1.1\r\n...");
    auto response = co_await socket.recv();
    co_return response;
}

task<void> parallel_fetch() {
    auto r1 = http_get("https://api1.example.com");
    auto r2 = http_get("https://api2.example.com");
    // 同时发起
    auto result1 = co_await r1;
    auto result2 = co_await r2;
    // 用法像同步代码，实际是异步并发
}
*/
```

---

## 8. 在 libkds/KVStore 中的实战建议

### 8.1 异步 I/O 读写

KVStore 的 append-log 写入可以用协程实现异步化：

```cpp
// 伪代码
task<WriteResult> async_append(KVStore& store, std::string_view key, 
                                std::span<const std::byte> value) {
    // 异步写入日志
    auto offset = co_await store.async_write_log(value);
    // 更新内存索引
    store.update_index(key, offset);
    co_return WriteResult{offset};
}
```

### 8.2 惰性数据生成

```cpp
Generator<Bar> read_kline_stream(const char* filename) {
    FILE* fp = fopen(filename, "rb");
    if (!fp) co_return;
    
    Bar bar;
    while (fread(&bar, sizeof(Bar), 1, fp) == 1) {
        co_yield bar;
    }
    fclose(fp);
}

// 使用
auto stream = read_kline_stream("data.bin");
while (stream.next()) {
    auto& bar = stream.value();
    process_bar(bar);
}
```

### 8.3 多协程协作的数据库查询

```cpp
// 伪代码：多个协程共同构建查询结果
template<typename Coro>
Generator<KVPair> merge_sort(Generator<KVPair>& a, Generator<KVPair>& b) {
    auto has_a = a.next(), has_b = b.next();
    
    while (has_a && has_b) {
        if (a.value().key <= b.value().key) {
            co_yield a.value();
            has_a = a.next();
        } else {
            co_yield b.value();
            has_b = b.next();
        }
    }
    
    while (has_a) { co_yield a.value(); has_a = a.next(); }
    while (has_b) { co_yield b.value(); has_b = b.next(); }
}
```

---

## 9. 协程的陷阱与最佳实践

### 9.1 常见陷阱

```cpp
// ❌ 1. 协程句柄的生命周期
Generator<int> bad_generator() {
    co_yield 1;
    co_yield 2;
}
// 如果 handle 被提前 destroy()，访问 value() 是 UB

// ❌ 2. 协程中抛出异常必须捕获
struct BadPromise {
    // 如果未实现 unhandled_exception，协程会 std::terminate()
    void unhandled_exception() { /* 必须实现！*/ }
};

// ❌ 3. 非 final_suspend 时的句柄销毁顺序
// 如果 final_suspend 返回 suspend_never，协程帧在 co_return 后自动销毁
// 此后任何 handle_.resume() 都是 UB

// ✅ 4. 正确的销毁
struct GoodPromise {
    std::suspend_always final_suspend() noexcept { return {}; }
    // 这样协程帧保持在终结态，需要手动 destroy()
    // 使用者必须记得调用 handle_.destroy()
};
```

### 9.2 最佳实践

1. **永远让 final_suspend 返回 suspend_always** — 避免自动销毁后的悬垂句柄
2. **协程句柄必须是 move-only** — 禁止复制
3. **co_yield/co_await 不在 constexpr 函数中** — 协程不能 constexpr
4. **注意协程帧的分配** — 默认在堆上，可以用 promise_type::operator new 自定义分配器
5. **对称传递替代递归** — 避免栈溢出

### 9.3 协程 vs 线程对比

| 特性 | 协程 | 线程 |
|------|------|------|
| 创建开销 | ~几十ns（堆分配一次） | ~μs级（内核栈创建） |
| 切换开销 | 无（只改变控制流） | ~μs级（上下文切换） |
| 并行性 | 并发不并行 | 可并行（多核） |
| 栈 | 无栈（复用调用者栈） | 独立栈（MB级） |
| 取消 | 协作式（co_await 检查点） | 强制式（需要信号/回调） |
| 适用场景 | I/O 密集型 | CPU 密集型/真正并行 |
