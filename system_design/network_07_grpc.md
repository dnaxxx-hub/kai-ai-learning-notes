# gRPC — 高性能 RPC 框架

## 什么是 gRPC？

**gRPC** = Google 开源的高性能远程过程调用(RPC)框架。

- 基于 **HTTP/2** 传输
- 使用 **Protocol Buffers** (protobuf) 序列化
- 支持四种调用模式
- 多语言互操作

## 1. Protocol Buffers (protobuf)

### 定义服务接口 (.proto 文件)

```protobuf
// hello.proto
syntax = "proto3";

package hello;

// 定义服务
service Greeter {
  // 一元 RPC
  rpc SayHello (HelloRequest) returns (HelloReply);
  
  // 服务端流式
  rpc SayHelloServerStream (HelloRequest) returns (stream HelloReply);
  
  // 客户端流式
  rpc SayHelloClientStream (stream HelloRequest) returns (HelloReply);
  
  // 双向流式
  rpc SayHelloBidirectional (stream HelloRequest) returns (stream HelloReply);
}

// 定义消息类型
message HelloRequest {
  string name = 1;    // 字段编号(唯一标识)
  int32 age = 2;
  repeated string tags = 3;  // 数组
}

message HelloReply {
  string message = 1;
}
```

### 标量类型

| .proto Type | Go Type | C++ Type | Java/Kotlin Type | Python Type |
|-------------|---------|----------|------------------|-------------|
| double | float64 | double | double | float |
| float | float32 | float | float | float |
| int32 | int32 | int32 | int | int |
| int64 | int64 | int64 | long | int/long |
| uint32 | uint32 | uint32 | int | int/long |
| uint64 | uint64 | uint64 | long | int/long |
| bool | bool | bool | boolean | bool |
| string | string | string | String | str/unicode |
| bytes | []byte | string | ByteString | bytes |

### 编译 protobuf

```bash
# 安装 protoc
# macOS: brew install protobuf
# Linux: apt install protobuf-compiler

# 安装 Go 插件
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# 编译
protoc --go_out=. --go-grpc_out=. hello.proto
```

## 2. gRPC 四种调用模式

### 一元 RPC (Unary RPC)

```go
// 客户端代码
func main() {
    conn, _ := grpc.Dial("localhost:50051", grpc.WithInsecure())
    defer conn.Close()
    
    client := pb.NewGreeterClient(conn)
    
    // 普通请求-响应
    resp, err := client.SayHello(context.Background(), &pb.HelloRequest{
        Name: "Alice",
        Age:  30,
    })
    
    log.Printf("Response: %s", resp.Message)
}
```

### 服务端流式 (Server Streaming)

```go
// 客户端: 不断从流中读取
stream, _ := client.SayHelloServerStream(ctx, &pb.HelloRequest{Name: "Bob"})
for {
    reply, err := stream.Recv()
    if err == io.EOF {
        break
    }
    log.Printf("Received: %s", reply.Message)
}
```

### 客户端流式 (Client Streaming)

```go
// 客户端: 批量发送数据
stream, _ := client.SayHelloClientStream(ctx)
names := []string{"Alice", "Bob", "Charlie"}
for _, name := range names {
    stream.Send(&pb.HelloRequest{Name: name})
}
resp, _ := stream.CloseAndRecv()
log.Printf("Final response: %s", resp.Message)
```

### 双向流式 (Bidirectional Streaming)

```go
// 同时收发
stream, _ := client.SayHelloBidirectional(ctx)

// 接收 goroutine
go func() {
    for {
        reply, err := stream.Recv()
        if err == io.EOF { break }
        log.Printf("Got: %s", reply.Message)
    }
}()

// 发送
for _, name := range names {
    stream.Send(&pb.HelloRequest{Name: name})
}
stream.CloseSend()
```

## 3. gRPC vs REST API 对比

| 特性 | gRPC | REST |
|------|------|------|
| 协议 | HTTP/2 | HTTP/1.1 (或HTTP/2) |
| 序列化 | protobuf (二进制, 紧凑) | JSON/XML (文本, 冗余) |
| 接口定义 | 强制 .proto 定义 | 文档化(OpenAPI等) |
| 流式支持 | 原生支持(4种模式) | SSE/WebSocket(不原生) |
| 浏览器支持 | 需grpc-web(gateway) | 原生支持 |
| 代码生成 | 自动生成客户端/服务端 | 通常手动/工具生成 |
| 性能 | 高 | 较低 |
| 网络负载 | 轻量 | 较重 |
| 可读性 | 难(二进制的) | 易(文本的) |
| 调试 | 需grpcurl等工具 | curl直接调试 |

### 性能对比数据

```
场景: 1000次请求, 小型payload

REST (JSON):            ~150ms,  ~1.2 KB/req
gRPC (protobuf):        ~30ms,  ~200 B/req

场景: 10万条数据流式传输

REST (分页查询):        ~12s,  大量重复请求
gRPC (服务端流式):      ~1.5s, 单次流连接
```

## 4. gRPC 高级特性

### 拦截器 (Interceptor)

```go
// 服务端拦截器: 记录请求日志
func loggingInterceptor(ctx context.Context, req interface{},
    info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    
    log.Printf("收到请求: %s", info.FullMethod)
    start := time.Now()
    
    resp, err := handler(ctx, req)
    
    log.Printf("处理完成: %s, 耗时: %v", info.FullMethod, time.Since(start))
    return resp, err
}

// 应用拦截器
s := grpc.NewServer(grpc.UnaryInterceptor(loggingInterceptor))
```

### 认证 (TLS/mTLS)

```go
// 服务端启用TLS
creds, _ := credentials.NewServerTLSFromFile("server.crt", "server.key")
s := grpc.NewServer(grpc.Creds(creds))

// 客户端使用TLS
creds, _ := credentials.NewClientTLSFromFile("ca.crt", "")
conn, _ := grpc.Dial("localhost:50051", grpc.WithTransportCredentials(creds))
```

### deadline/超时

```go
// 客户端设置3秒超时
ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
defer cancel()

resp, err := client.SayHello(ctx, &pb.HelloRequest{Name: "test"})
```

## 5. 常用工具

```bash
# 启动gRPC服务
go run server/main.go

# gRPC客户端
go run client/main.go

# grpcurl — curl的gRPC版(调试用)
grpcurl -plaintext localhost:50051 list                     # 列出服务
grpcurl -plaintext localhost:50051 describe hello.Greeter   # 查看服务定义
grpcurl -plaintext -d '{"name": "test"}' localhost:50051 hello.Greeter/SayHello

# golang 服务端启动模板
go run <<< '
package main
import (
    "log"
    "net"
    "google.golang.org/grpc"
    pb "path/to/protobuf"
)

type server struct { pb.UnimplementedGreeterServer }

func (s *server) SayHello(ctx context.Context, req *pb.HelloRequest) (*pb.HelloReply, error) {
    return &pb.HelloReply{Message: "Hello " + req.Name}, nil
}

func main() {
    lis, _ := net.Listen("tcp", ":50051")
    s := grpc.NewServer()
    pb.RegisterGreeterServer(s, &server{})
    log.Println("gRPC server listening on :50051")
    s.Serve(lis)
}
'
```
