# 📘 07 - C++20 协程与异步编程

> 协程是 C++20 最重磅的特性之一——零开销抽象的函数级挂起/恢复。
> 核心：`co_return` / `co_yield` / `co_await` + `promise_type` + `awaitable` 协议

---

## 1. 协程是什么

**协程 = 可挂起(suspend) + 可恢复(resume) 的函数**

- 普通函数：调用 → 执行 → 返回 → 结束
- 协程：调用 → 执行 → **挂起** → 恢复 → ... → 最终返回

### 关键能力

| 操作 | 含义 |
|------|------|
| `co_return expr` | 协程结束，返回结果 |
| `co_yield expr` | 挂起并向外产生一个值（generator 模式） |
| `co_await expr` | 挂起直到某个异步操作完成 |

### 谁在背后工作

```
┌─────────────────────────────────────────┐
│ 编译器为协程自动生成的状态机              │
│                                         │
│ 1. 分配协程帧（heap 或 frame allocator） │
│ 2. 所有局部变量保活（跨越 suspend 点）    │
│ 3. 生成 resume/suspend 跳转表           │
│ 4. promise_type 控制生命周期和交互        │
└─────────────────────────────────────────┘
```

---

## 2. co_yield —— Generator\<T\>

最简单的协程：**生产者**模式，每次 yield 返回一个值，外部通过迭代器消费。

### 完整实现 Generator\<T\>

```cpp
#include <coroutine>
#include <exception>
#include <optional>
#include <iostream>

template<typename T>
struct Generator {
    // 每个协程必须的 promise_type
    struct promise_type {
        T current_value_;

        Generator get_return_object() {
            return Generator{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        std::suspend_always initial_suspend() noexcept { return {}; }  // 创建后挂起
        std::suspend_always final_suspend() noexcept { return {}; }    // 结束后挂起（不销毁）
        std::suspend_always yield_value(T value) noexcept {
            current_value_ = std::move(value);
            return {};
        }
        void return_void() noexcept {}
        void unhandled_exception() noexcept { std::terminate(); }
    };

    using handle_type = std::coroutine_handle<promise_type>;

    handle_type coro_;

    explicit Generator(handle_type coro) : coro_(coro) {}
    ~Generator() { if (coro_) coro_.destroy(); }

    // 不可拷贝，可移动
    Generator(const Generator&) = delete;
    Generator& operator=(const Generator&) = delete;
    Generator(Generator&& other) noexcept : coro_(other.coro_) {
        other.coro_ = {};
    }

    // 迭代器——让 Generator 可 for-range
    struct Iter {
        handle_type coro_;
        bool done_ = true;

        void fetch() {
            if (coro_) {
                coro_.resume();
                done_ = coro_.done();
            }
        }
        T operator*() const { return coro_.promise().current_value_; }
        bool operator!=(const Iter&) const { return !done_; }
        Iter& operator++() { fetch(); return *this; }
    };

    Iter begin() {
        Iter it{coro_, true};
        it.fetch();  // 首次 resume
        return it;
    }
    Iter end() { return Iter{{}, true}; }
};

// 使用示例
Generator<int> fibonacci(int max) {
    int a = 0, b = 1;
    while (a <= max) {
        co_yield a;
        auto t = a + b;
        a = b;
        b = t;
    }
}

int main() {
    for (int v : fibonacci(100)) {
        std::cout << v << ' ';  // 0 1 1 2 3 5 8 13 21 34 55 89
    }
}
```

### co_yield 本质

`co_yield expr` 等价于 `co_await promise.yield_value(expr)`

---

## 3. co_await —— awaitable 协议

### awaitable 接口（3个方法）

```cpp
struct MyAwaitable {
    // 1. 是否挂起？true=挂起, false=继续执行
    bool await_ready() noexcept { return false; }

    // 2. 挂起时的回调（通常存 coroutine_handle 以便后续恢复）
    void await_suspend(std::coroutine_handle<> h) noexcept {
        // 保存 h，在异步完成后调用 h.resume()
    }

    // 3. co_await 表达式的结果值
    int await_resume() noexcept { return 42; }
};

Task<int> my_coro() {
    int result = co_await MyAwaitable{};  // result = 42
    co_return result;
}
```

### 常见标准 awaitable

```cpp
// 总是挂起
struct suspend_always {
    bool await_ready() noexcept { return false; }
    void await_suspend(coroutine_handle<>) noexcept {}
    void await_resume() noexcept {}
};

// 从不挂起
struct suspend_never {
    bool await_ready() noexcept { return true; }
    void await_suspend(coroutine_handle<>) noexcept {}
    void await_resume() noexcept {}
};
```

---

## 4. Task\<T\> —— 惰性异步任务

相比 Generator（push 模型），Task 是 **pull + await** 模型：

```cpp
#include <coroutine>
#include <optional>
#include <exception>
#include <variant>

template<typename T>
struct Task {
    struct promise_type {
        std::variant<std::monostate, T, std::exception_ptr> result_;

        auto get_return_object() {
            return Task{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        auto initial_suspend() noexcept { return std::suspend_always{}; }  // 惰性
        auto final_suspend() noexcept { return std::suspend_always{}; }

        void return_value(T value) { result_.template emplace<1>(std::move(value)); }
        void unhandled_exception() { result_.template emplace<2>(std::current_exception()); }
    };

    using handle_type = std::coroutine_handle<promise_type>;
    handle_type coro_;

    explicit Task(handle_type h) : coro_(h) {}
    ~Task() { if (coro_) coro_.destroy(); }

    Task(const Task&) = delete;
    Task(Task&& o) noexcept : coro_(o.coro_) { o.coro_ = {}; }

    // 阻塞等待——简单同步用法
    T blocking_get() {
        coro_.resume();
        auto& result = coro_.promise().result_;
        if (result.index() == 1) return std::get<1>(result);
        else std::rethrow_exception(std::get<2>(result));
    }

    // 让 Task 自身也可被 co_await
    bool await_ready() noexcept { return false; }

    void await_suspend(handle_type awaiting_coro) noexcept {
        // 将当前 handle 挂起到 Task 里，Task 完成后恢复外层的协程
        // 简化版：直接阻塞 resume 这个 Task
        // 生产级需要 scheduler / executor
        // 这里演示原理：立即完成（阻塞当前线程）
        coro_.resume();
        awaiting_coro.resume();
    }

    T await_resume() noexcept {
        auto& result = coro_.promise().result_;
        if (result.index() == 1) return std::get<1>(result);
        else std::rethrow_exception(std::get<2>(result));
    }
};
```

---

## 5. Task 链式调用

```cpp
Task<int> compute_value(int x) {
    co_return x * 2;
}

Task<int> process(int input) {
    // 协程嵌套等待——编译器自动处理
    int v1 = co_await compute_value(input);
    int v2 = co_await compute_value(v1);
    co_return v2;
}

int main() {
    Task<int> t = process(5);
    int result = t.blocking_get();  // 20
    std::cout << result;
}
```

---

## 6. 实战：协程版异步 HTTP 请求器

使用 Windows Winsock 实现协程式异步 TCP 客户端：

```cpp
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <coroutine>
#include <string>
#include <iostream>
#include <functional>
#pragma comment(lib, "ws2_32.lib")

// ---- 简单的 Socket Awaitable ----
struct SocketReadAwaitable {
    SOCKET sock_;
    char* buf_;
    int len_;
    int bytes_read_ = 0;

    bool await_ready() noexcept { return false; }

    void await_suspend(std::coroutine_handle<> h) noexcept {
        // 在 Windows 中，使用非阻塞 socket + select/WSAEventSelect
        // 简化版：直接阻塞读取（真实场景应使用 IOCP/WSAEventSelect + 线程池恢复）
        // 这里为了演示协程原理，在单独的线程中执行阻塞 IO
        std::thread([this, h]() {
            bytes_read_ = recv(sock_, buf_, len_, 0);
            h.resume();  // IO 完成后恢复协程
        }).detach();
    }

    int await_resume() noexcept { return bytes_read_; }
};

// ---- 协程版 HTTP GET ----
struct HttpResult {
    int status_code;
    std::string body;
};

Task<HttpResult> async_http_get(const std::string& host, const std::string& path) {
    // 1. 创建 socket
    SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == INVALID_SOCKET) co_return HttpResult{0, "socket failed"};

    // 2. 连接
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(80);
    // 简化：使用 gethostbyname
    auto* he = gethostbyname(host.c_str());
    if (!he) { closesocket(sock); co_return HttpResult{0, "dns failed"}; }
    memcpy(&addr.sin_addr, he->h_addr, he->h_length);

    if (connect(sock, (sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
        closesocket(sock);
        co_return HttpResult{0, "connect failed"};
    }

    // 3. 发送 HTTP 请求
    std::string request = "GET " + path + " HTTP/1.1\r\n"
                          "Host: " + host + "\r\n"
                          "Connection: close\r\n\r\n";
    send(sock, request.c_str(), (int)request.size(), 0);

    // 4. 协程式读取响应
    std::string response;
    char buf[4096];
    while (true) {
        int n = co_await SocketReadAwaitable{sock, buf, sizeof(buf) - 1};
        if (n <= 0) break;
        buf[n] = '\0';
        response += buf;
    }

    closesocket(sock);

    // 5. 解析状态码
    int code = 0;
    if (response.size() > 9 && response.substr(0, 4) == "HTTP") {
        code = std::stoi(response.substr(9, 3));
    }

    // 找到 body（跳过 header）
    auto body_pos = response.find("\r\n\r\n");
    std::string body = (body_pos != std::string::npos)
        ? response.substr(body_pos + 4) : response;

    co_return HttpResult{code, body};
}

// 使用
Task<void> demo() {
    auto result = co_await async_http_get("example.com", "/");
    std::cout << "Status: " << result.status_code << "\n";
    std::cout << "Body size: " << result.body.size() << "\n";
}
```

---

## 7. 协程 vs 线程池 vs 回调

| 维度 | 协程 (C++20) | 线程池 | 回调 (async) |
|------|-------------|--------|-------------|
| 代码可读性 | ⭐⭐⭐⭐⭐ 顺序书写 | ⭐⭐⭐ 需管理任务 | ⭐⭐ 回调地狱 |
| 内存开销 | ≈1-2KB/协程帧 | 栈 ≈1-8MB/线程 | 闭包 ≈数百B |
| 上下文切换 | 用户态函数间切换 (ns级) | 内核态调度 (us级) | 函数指针调用 |
| 错误处理 | try/catch 正常 | 需传递异常 | 错误回调嵌套 |
| 条件分支 | if/for/while 正常 | 需条件变量/future | 回调中判断 |
| 资源管理 | RAII 正常 | RAII 正常 | 闭包捕获需谨慎 |

### 何时选择

- **协程**：大量并发 IO（数千个）、需要顺序书写异步逻辑、微服务/网关
- **线程池**：CPU 密集型任务、已有线程安全库、简单并行
- **回调**：事件流处理（虽有更好选择）、旧代码兼容、简单单次通知

---

## 8. 性能要点

```
协程框架分配 ≈ 1 次 heap alloc（协程帧）
每次 suspend/resume ≈ 3-5 条指令
比线程切换快 50-100x

⚠️ 注意：
- 编译器优化不佳时可能多次分配（使用局部分配器优化）
- 协程帧大小由所有跨 suspend 点的变量决定
- 不要在大循环中 co_await（慢于函数调用）
```

---

## 总结

| 概念 | 一句话 |
|------|--------|
| `co_yield` | 挂起并产出一个值（Generator 模式） |
| `co_await` | 挂起等待异步操作完成 |
| `co_return` | 协程结束并返回值 |
| `promise_type` | 协程的行为控制器（值、异常、生命周期） |
| `awaitable` | `await_ready` / `await_suspend` / `await_resume` 三件套 |
| `coroutine_handle` | 协程帧的句柄，可 resume / destroy |
