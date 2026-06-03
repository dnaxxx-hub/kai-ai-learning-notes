# Go 纵深 #7：数据库

## sql.DB 连接池
```go
db, _ := sql.Open("mysql", dsn)
db.SetMaxOpenConns(25)      // 最大打开连接数
db.SetMaxIdleConns(10)      // 最大空闲连接数
db.SetConnMaxLifetime(5 * time.Minute) // 连接最大存活时间
db.SetConnMaxIdleTime(1 * time.Minute) // 空闲超时
```
注意：`sql.Open` 不建实际连接，`db.Ping()` 才连通

## GORM vs sqlx

| 特性 | GORM | sqlx |
|------|------|------|
| ORM | ✅ 全功能 | ❌ 只做映射 |
| 自动迁移 | ✅ | ❌ |
| 链式查询 | ✅ | ❌ (手写 SQL) |
| 性能 | 慢（反射多） | 快（更接近原生） |
| 复杂查询 | 难 | 容易 |

## 事务
```go
tx, _ := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
defer tx.Rollback() // 成功 Commit 后 Rollback 无效果
tx.ExecContext(ctx, "UPDATE ...")
tx.Commit() // 成功后 Rollback no-op
```

## migration
- golang-migrate：`migrate create -ext sql -dir migrations create_users`
- up.sql 和 down.sql 成对出现
- 嵌入 binary：`embed` 包静态编译

## Prepared Statement
```go
stmt, _ := db.PrepareContext(ctx, "SELECT * FROM users WHERE id = ?")
defer stmt.Close()
stmt.QueryRowContext(ctx, 1) // 每次只需传参数，避免 SQL 注入
```
