# Go 纵深 #8：Web 框架 — Gin 源码级

## 路由树（基数树 Radix Tree）
```go
// gin 的路由树就是压缩前缀树
// GET /users → 节点 /users
// GET /users/:id → 节点 /users → 子节点 /:id
// POST /users → 需要方法区分，gin 对每种方法独立建树
tree := &methodTree{method: "GET", root: &node{
    path: "/",
    children: []*node{
        {path: "users", handlers: handlers},
        {path: "users/:id", handlers: handlers},
    },
}}
```
- 优点：匹配 O(n)，n=路径段数，优于正则匹配
- 路径参数用 `:` 前缀节点，`:id` 匹配任意一级

## 中间件链
```go
func Logger() gin.HandlerFunc {
    return func(c *gin.Context) {
        t := time.Now()
        c.Next() // 调用后续中间件和 handler
        log.Printf("%s %s %d %s", c.Request.Method, c.Request.URL.Path, c.Writer.Status(), time.Since(t))
    }
}
r.Use(gin.Logger(), gin.Recovery())
```

## Request Context
- `c.Query("key")` — URL 查询参数
- `c.Param("id")` — 路径参数
- `c.GetHeader("Authorization")` — 请求头
- `c.ShouldBindJSON(&obj)` — JSON 绑定 + 验证
- `c.JSON(200, obj)` — JSON 响应

## 验证
- `binding:"required,min=1,max=100"` — struct tag 验证
- 自定义验证器：`binding.Validator.RegisterValidation("xxx", ...)`

## 错误处理
- `c.AbortWithStatusJSON(400, gin.H{"error": "bad request"})`
- 全局 `Recovery()` 中间件捕获 panic
