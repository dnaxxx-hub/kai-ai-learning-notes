# Go 纵深 #9：内存模型

## happens-before
- Go 内存模型定义 goroutine 间什么操作保证可见
- 核心规则：
  - 同一 goroutine：程序顺序 = happens-before 关系
  - `ch <- v` happens-before `<-ch`（channel 收发）
  - `mu.Unlock()` happens-before `mu.Lock()`（mutex）
  - `wg.Wait()` 返回 happens-before 所有 `wg.Done()` 的完成
  - `atomic.Store` happens-before `atomic.Load`（同一地址）

## data race 检测
```go
go test -race ./...
// 编译时插桩，运行时检测竞争条件
// 性能开销约 5-10x，只用于测试
```

## atomic 操作
```go
var counter atomic.Int64
counter.Add(1)
val := counter.Load()
counter.Store(100)
swapped := counter.CompareAndSwap(100, 200) // CAS
```
- 原子操作不保证其他 goroutine 立即看到（happens-before 语义才保证）
- 用 `atomic.Load` / `atomic.Store` 建立 happens-before

## 常见竞争场景
1. map 并发读写（直接 panic，不是数据不一致）
2. slice 同时 append（可能丢数据）
3. `io.Reader` / `io.Writer` 不加锁
4. 闭包捕获循环变量
