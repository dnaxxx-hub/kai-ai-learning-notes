# Go 纵深 #11：性能优化

## 逃逸分析
```go
go build -gcflags='-m -l' main.go
// 常见逃逸到堆的场景：
1. 返回局部变量指针
2. 值放入 interface{}
3. 闭包捕获外部变量
4. slice/map 容量未知时
5. 大对象（>64KB）
```
栈分配零 GC 压力，堆分配要 GC 追踪。

## 内存分配优化
```go
// ❌ 反复分配
for i := 0; i < n; i++ {
    buf := make([]byte, 4096) // 每次分配
    process(buf)
}

// ✅ 复用
buf := make([]byte, 4096)
for i := 0; i < n; i++ {
    process(buf)
    buf = buf[:cap(buf)] // 重置，不重新分配
}
```

## GC 调优
```go
// GOGC=100 表示堆增长 100% 触发 GC（默认）
debug.SetGCPercent(-1) // 禁止 GC（不推荐）
debug.SetMemoryLimit(1 << 30) // 1GB 软限制（Go 1.19+）
```
- GOGC 越小 GC 越频繁，暂停越短
- GOGC 越大 GC 越少，暂停越长
- `runtime.ReadMemStats(&m)` 查看 GC 统计

## PGO（Profile-Guided Optimization）
```go
go test -bench=. -cpuprofile=cpu.pprof
// 收集性能数据后
go build -pgo=cpu.pprof  // Go 1.21+
```
PGO 可提效 2-14%，主要是内联优化和函数放置。

## 常见优化点
1. 用 strings.Builder 替代字符串 +
2. 预分配 slice 容量：`make([]T, 0, expectedSize)`
3. 用 sync.Pool 复用临时对象
4. 避免 interface{} 装箱（用泛型替代）
5. 用栈变量代替指针字段
6. 减少不必要的锁粒度
