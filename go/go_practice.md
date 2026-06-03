# Go 语言实战学习笔记

> 日期：2026-05-28
> 目标：基于 Go 第 11 课理论学习，动手写两个实用项目

---

## 1. Go 模块和包管理（go.mod）

### 核心概念
- **Module**：Go 的代码组织单元，一个 `go.mod` 文件定义模块路径和依赖
- **Package**：同一目录下 `.go` 文件的集合，包名一般和目录名一致
- 使用 `go mod init <module-path>` 初始化模块

### 实战对比（Python → Go）

| 概念 | Python | Go |
|------|--------|-----|
| 项目元数据 | `pyproject.toml` / `requirements.txt` | `go.mod` |
| 依赖管理 | pip / poetry | 内置 `go mod` |
| 导入方式 | `import requests` | `import "module/pkg"` |
| 内部包引用 | 相对/绝对导入 | 从 module 根路径开始 |

### 注意点
- `go.mod` 要求版本号形如 `v0.0.0` 或 `v1.2.3`
- 同一个目录下所有 `.go` 文件的 `package` 声明必须一致
- `internal` 目录限制外部包导入

## 2. 标准库 os/filepath 文件操作

### 常用 API

```go
// 遍历目录
filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
    // ...
})

// 路径操作
filepath.Join("dir", "sub", "file.txt")  // dir\sub\file.txt (Windows)
filepath.ToSlash(path)                    // 反斜杠 → 正斜杠
filepath.Glob(pattern)                    // 通配符匹配
filepath.Match(pattern, name)             // 单个文件名匹配

// 文件信息
os.Stat(path)               // 获取文件信息
os.IsNotExist(err)          // 判断文件不存在
```

### Windows 兼容
- `filepath.Join` 自动处理路径分隔符（Windows 用 `\`）
- 传入 `filepath.Walk` 的回调路径是 OS 原生格式
- 处理正则/通配符前用 `filepath.ToSlash()` 统一为正斜杠

## 3. goroutine + channel 并发搜索

### 模式：Worker Pool

```
     ┌──────┐  jobs chan   ┌──────────┐
     │ Walk ├─────────────→│ Worker 1 │
     │      │              ├──────────┤
     │      │              │ Worker 2 │  results chan → 收集
     │      │              ├──────────┤
     │      │              │ Worker N │
     └──────┘              └──────────┘
```

### 关键代码模式

```go
// 生产者：遍历目录，将文件路径发送到 jobs channel
go func() {
    defer close(jobs)
    filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
        jobs <- job{path, info}
        return nil
    })
}()

// 消费者：N 个 worker 并发过滤
var wg sync.WaitGroup
for i := 0; i < workerCount; i++ {
    wg.Add(1)
    go func() {
        defer wg.Done()
        for j := range jobs {
            if filter(j.path, j.info) {
                results <- j.path
            }
        }
    }()
}
```

### 对比 Python 感受
- Go 的 goroutine 比 Python 线程轻量得多（栈 KB 级 vs MB 级）
- channel 是 Go 独有的通信原语，Python 需要 `queue.Queue` + Event 协调
- 无 GIL 限制，CPU 密集型（如文件 Hash）也能并行

## 4. flag 包命令行参数解析

### 基础用法

```go
dir := flag.String("dir", ".", "Directory to search")
name := flag.String("name", "", "File name pattern (supports wildcards)")
flag.Parse()
```

### 自定义类型（大小参数）

```go
type sizeFlag int64

func (s *sizeFlag) Set(v string) error {
    // 解析 "1KB", "2MB" 等
    unit := strings.ToUpper(v[len(v)-2:])
    val, _ := strconv.ParseInt(v[:len(v)-2], 10, 64)
    switch unit {
    case "KB": *s = sizeFlag(val * 1024)
    case "MB": *s = sizeFlag(val * 1024 * 1024)
    }
    return nil
}
```

### 对比 Python → Go
- `argparse` 功能更丰富（子命令、自动帮助）；`flag` 更简洁
- Go flag 值类型明确，无字符串到类型的隐式转换
- `flag.Parse()` 必须在所有 `flag.Type()` 调用之后

## 5. net/http 标准库 REST API

### HTTP Server 基础

```go
// 路由注册
http.HandleFunc("GET /api/files", handleListFiles)
http.HandleFunc("GET /api/file/info", handleFileInfo)

// 启动服务器
http.ListenAndServe(":8080", nil)
```

### 路由模式（Go 1.22+ 增强）
Go 1.22 引入了方法匹配的路由：`"GET /api/files"` 只匹配 GET 请求。
之前只能用 `http.HandleFunc("/api/files", ...)` 手动判断 Method。

### JSON 响应

```go
func writeJSON(w http.ResponseWriter, status int, data any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(data)
}
```

### 对比 Python → Go
- Python 用 Flask 的 `@app.route` 装饰器 vs Go 的显式 `HandleFunc`
- Go 没有 Flask 的 `request.args.get()`，需手动从 URL 解析参数
- Go 的类型系统让 JSON 序列化更安全（强类型 struct vs Python dict）
- 标准库就够用，无需第三方框架

## 6. 测试

### Go 测试惯例
- 文件命名 `*_test.go`
- 函数签名 `func TestXxx(t *testing.T)`
- HTTP 测试用 `httptest.NewServer`

### 临时文件测试
```go
func TestFilterByName(t *testing.T) {
    tmpDir := t.TempDir()
    os.WriteFile(filepath.Join(tmpDir, "test.go"), []byte{}, 0644)
    os.WriteFile(filepath.Join(tmpDir, "test.py"), []byte{}, 0644)
    // ...
}
```

## 7. 实战经验总结

### Go vs Python 差异对比

| 维度 | Go | Python |
|------|-----|--------|
| **项目结构** | 模块 + 包，强约定 | 灵活但混乱 |
| **并发** | goroutine + channel 原生支持 | threading / asyncio 库级支持 |
| **标准库** | 内置 HTTP 服务器、JSON、flag | 内置但 HTTP 需框架 |
| **编译** | 静态二进制，无运行时依赖 | 解释执行，需解释器 |
| **错误处理** | `if err != nil` 显式处理 | `try/except` 异常机制 |
| **路径处理** | `filepath` 包原生跨平台 | `os.path` / `pathlib` |
| **JSON 处理** | 强类型映射（struct + tags） | dict 动态类型 |
| **构建速度** | 快（增量编译） | 无需编译 |
| **可执行大小** | ~5-10MB 单文件 | 无 |

### 学习心得

1. **Go 的简洁是双刃剑**：没有泛型（1.18 前）、没有继承，但写起来很直白
2. **错误处理很啰嗦但安全**：每个 `err != nil` 都强迫你思考边界情况
3. **并发是 Go 的灵魂**：goroutine + channel 的组合比 Python 任何并发方案都自然
4. **标准库够用但不够漂亮**：`http.ServerMux` 模式匹配不如 Gin 方便，但零依赖部署很香
5. **Windows 兼容要注意**：路径分隔符、换行符、环境变量都需要额外处理
6. **测试方便但无 mock 框架**：Go 崇尚接口 + 依赖注入，标准库 `testing` 足够
7. **编译部署体验极好**：`go build` 出一个 exe，扔到任意 Windows 机器就能跑
