# Go 纵深 #3：网络编程深度

## net/http 服务端
- `ListenAndServe` → `net.Listen` + `Accept` 循环，每连接一个 goroutine
- Server 结构体：`ReadTimeout`/`WriteTimeout`/`IdleTimeout` 必须设置！
- 不设超时 → goroutine 泄漏、连接耗尽
- Handler 接口：3种实现方式（函数式/结构体式/闭包式）

## Middleware 模式
```go
type Middleware func(http.Handler) http.Handler
func Chain(h http.Handler, mws ...Middleware) http.Handler {
    for i := len(mws)-1; i >= 0; i-- { h = mws[i](h) }
    return h
}
```
实用中间件：Logger(记录耗时+状态码)、Recoverer(panic恢复)、CORS

## HTTP Client 连接池
```go
tr := &http.Transport{
    MaxIdleConns:        100,
    MaxIdleConnsPerHost: 10,
    IdleConnTimeout:     90 * time.Second,
    DisableCompression:  false,
}
client := &http.Client{Transport: tr, Timeout: 30 * time.Second}
```
经验：MaxIdleConnsPerHost ≤ 2× 期望并发，防 TIME_WAIT 耗尽

## TCP 底层
- `net.Listener.Accept()` 返回 `net.Conn`
- `net.Conn` 是接口：`Read(Buffer)` / `Write(Buffer)` / `Close()` / `LocalAddr()` / `RemoteAddr()`
- TCP keepalive：`conn.(*net.TCPConn).SetKeepAlive(true)`

## WebSocket 简介
- 基于 HTTP Upgrade 握手，然后全双工
- gorilla/websocket 是最流行的库
- 读写需同步（一个 goroutine 读，一个写）
