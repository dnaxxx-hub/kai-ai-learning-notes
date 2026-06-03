# Go 纵深 #12：实战项目 — 股票查询 CLI + HTTP API

## 项目结构
```
stock-cli/
├── main.go          # CLI 入口
├── server.go        # HTTP API
├── client.go        # 数据采集（模拟）
├── store.go         # 内存存储
├── go.mod
└── go.sum
```

## CLI 模式
```go
// 用 flag 包或 cobra
func main() {
    symbol := flag.String("symbol", "AAPL", "股票代码")
    flag.Parse()
    quote := fetchQuote(*symbol)
    fmt.Printf("%s: $%.2f (%.2f%%)\n", quote.Symbol, quote.Price, quote.ChangePct)
}
// go run . --symbol=GOOG
```

## HTTP API
```go
type StockHandler struct{ store *Store }
func (h *StockHandler) GetQuote(c *gin.Context) {
    symbol := c.Param("symbol")
    quote, ok := h.store.Get(symbol)
    if !ok { c.JSON(404, gin.H{"error": "not found"}); return }
    c.JSON(200, quote)
}
// GET /api/quote/AAPL
```

## 数据采集 goroutine
```go
func (s *Store) StartUpdater(ctx context.Context, interval time.Duration) {
    ticker := time.NewTicker(interval)
    go func() {
        for { select {
        case <-ticker.C: s.updateAll()
        case <-ctx.Done(): ticker.Stop(); return
    } }()
}()
```

## 整合功能
1. CLI 单次查询 — 用 flag 传 symbol
2. HTTP server 持续运行 — gin 路由
3. 定时更新 — goroutine + ticker
4. 并发安全 — sync.RWMutex 保护 store
5. context 关闭 — signal.NotifyContext 优雅退出
