# Go 纵深 #5：工具链

## go mod 深度
- `go mod init` / `go mod tidy` / `go mod graph` / `go mod vendor`
- MVS(最小版本选择)：Go 选择模块所有依赖都认可的最大版本
- `go mod verify`：校验缓存完整性
- `go mod edit -replace`：本地替换，开发调试神器

## pprof 性能分析
```go
import _ "net/http/pprof" // 自动注册 /debug/pprof/

go tool pprof http://localhost:8080/debug/pprof/profile?seconds=30
go tool pprof http://localhost:8080/debug/pprof/heap
go tool pprof http://localhost:8080/debug/pprof/goroutine
```
命令：`top10` / `list FuncName` / `web`（需 graphviz）

## testing / fuzz
```go
// 表格驱动测试
func TestXxx(t *testing.T) { ... }

// Fuzz（Go 1.18+）
func FuzzXxx(f *testing.F) {
    f.Add("seed input")
    f.Fuzz(func(t *testing.T, input string) {
        // 随机测试
    })
}
```

## benchmark / pprof
```go
func BenchmarkXxx(b *testing.B) {
    for i := 0; i < b.N; i++ {
        DoSomething()
    }
}
```
- `go test -bench=. -benchmem -cpuprofile=cpu.out`
- `go tool pprof -http=:8080 cpu.out`（Web界面）
