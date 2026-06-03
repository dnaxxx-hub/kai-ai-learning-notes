# Go 纵深 Roadmap — 11课汇总

| # | 课程 | 核心内容 |
|:-:|------|----------|
| 2 | **并发模型** | GMP调度(hchan/schedule/sysmon), channel底层(发送/接收/select), sync包(Mutex饥饿/RWMutex/WaitGroup/Once/Map/Pool) |
| 3 | **网络编程** | net/http服务端源码(连接管理/Handler/ServeMux), Middleware链, HTTP Client连接池(Transport), TCP底层, 超时配置 |
| 4 | **微服务架构** | gRPC(protobuf/4种通信模式), 接口设计(选项模式/最小接口), 服务发现(etcd/Consul), 配置中心(viper) |
| 5 | **工具链** | go mod(MVS/verify/replace), pprof(cpu/heap/goroutine), testing/fuzz, benchmark |
| 6 | **设计模式** | 选项模式, 接口组合, sync.Pool, 扇出扇入, Pipeline, Context传递 |
| 7 | **数据库** | sql.DB连接池(GORM vs sqlx), 事务, golang-migrate, Prepared Statement |
| 8 | **Web框架** | Gin路由树(Radix Tree), 中间件链, Request Context, 验证,binding, 错误处理 |
| 9 | **内存模型** | happens-before(channel/mutex/atomic/WaitGroup), data race检测, atomic操作, 常见竞争场景 |
| 10 | **反射与代码生成** | reflect包(Type/Value/Call), struct tag解析, JSON模拟, stringer/genny |
| 11 | **性能优化** | 逃逸分析, 内存分配优化, GC调优(GOGC/memory limit), PGO, 常见优化点清单 |
| 12 | **实战项目** | stock-cli: CLI + HTTP API + goroutine定时更新 + RWMutex + 优雅退出 |

**前提：** Go 基础知识（语法/goroutine/channel）在 `go_01_basics.md`
