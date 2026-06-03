# Go 纵深 #4：微服务架构

## gRPC 基础
- protobuf 定义服务 + 消息，`proto3` 语法
- `protoc --go_out=. --go-grpc_out=. *.proto` 生成代码
- 服务端：注册服务实现，`grpc.NewServer()` + `s.Serve(lis)`
- 客户端：`grpc.Dial(addr, grpc.WithInsecure())`
- 4种通信模式：一元(Unary)、服务端流、客户端流、双向流

## 接口设计
- 选项模式(functional options)：可选参数用 `type Option func(*Config)`
- 接口分离：一个接口 ≤ 3个方法
- 依赖接口，不依赖具体实现（可测试性）

## 服务发现
- etcd / Consul：强一致性，CAP 的 CP
- 心跳注册 + TTL 自动过期
- 客户端缓存 + watch 更新

## 配置中心
- viper 库：支持文件/env/远程配置
- 热更新：`viper.WatchConfig()` + `viper.OnConfigChange(func)`
- 分层：默认值 → 配置文件 → 环境变量 → 命令行参数
