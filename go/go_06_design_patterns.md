# Go 纵深 #6：设计模式

## 选项模式
```go
type Server struct { addr string; timeout time.Duration; logger *log.Logger }
type Option func(*Server)
func WithTimeout(t time.Duration) Option {
    return func(s *Server) { s.timeout = t }
}
func NewServer(addr string, opts ...Option) *Server {
    s := &Server{addr: addr, timeout: 30 * time.Second}
    for _, opt := range opts { opt(s) }
    return s
}
```
优点：零值合理、向后兼容（加新选项不破坏已有代码）

## 接口组合
```go
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
type ReadWriter interface { Reader; Writer } // 组合
```
Go 标准库大量使用接口组合（io.ReadWriter、io.ReadCloser）

## sync.Pool（临时对象池）
```go
var bufPool = sync.Pool{ New: func() any { return make([]byte, 32*1024) } }

func process() {
    buf := bufPool.Get().([]byte)
    defer bufPool.Put(buf)
    // 使用 buf，不用反复分配
}
```
注意：GC 时会清空 Pool，不适合持久化连接池

## 扇出扇入
```go
// 扇出：拆分任务给多个 worker
func fanOut(in <-chan int, n int) []<-chan int {
    chs := make([]<-chan int, n)
    for i := 0; i < n; i++ {
        chs[i] = worker(in)
    }
    return chs
}
// 扇入：合并多路结果
func fanIn(chs ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    for _, c := range chs {
        wg.Add(1); go func(c <-chan int) { defer wg.Done(); for v := range c { out <- v } }(c)
    }
    go func() { wg.Wait(); close(out) }()
    return out
}
```

## Context 传递
```go
ctx = context.WithValue(ctx, "request_id", reqID)
val := ctx.Value("request_id").(string)
```
只传请求级元数据（trace_id、user_id），别当参数替代品
