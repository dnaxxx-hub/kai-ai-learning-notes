# 第7课：C/C++实现深度

> 参考 ngtcp2、msquic、lsquic 源码分析

---

## 7.1 ngtcp2 架构分析（核心事件驱动）

### ngtcp2 概述

**ngtcp2** 是最广泛使用的 C 语言 QUIC 实现之一，以事件驱动架构著称。curl、Wireshark（QUIC 解码器）、很多网络工具底层都使用 ngtcp2。

- 仓库：https://github.com/ngtcp2/ngtcp2
- 语言：C（core）+ C++（示例）
- 特性：事件驱动、最小依赖、RFC 9000/9001/9002 完整实现

### ngtcp2 的架构

```
┌─────────────────────────────────────────────┐
│  ngtcp2 用户应用（如 curl、自定义程序）      │
├─────────────────────────────────────────────┤
│  ngtcp2 API 层                              │
│  ┌───────────────────────────────────────┐  │
│  │  ngtcp2_conn (连接对象)              │  │ ← 核心对象
│  │  ngtcp2_cid (Connection ID)          │  │
│  │  ngtcp2_pkt (包处理)                 │  │
│  │  ngtcp2_cc (拥塞控制)               │  │
│  └───────────────────────────────────────┘  │
├─────────────────────────────────────────────┤
│  ngtcp2 内部模块                            │
│  ┌──────────┬──────────┬─────────────────┐  │
│  │ 包解析     │ 握手      │ 流管理         │  │
│  │ (packet) │ (handshake) │ (stream)      │  │
│  ├──────────┼──────────┼─────────────────┤  │
│  │ 恢复/重传 │ 拥塞控制  │ TLS 桥接        │  │
│  │ (recovery)│ (cc)     │ (tls)          │  │
│  └──────────┴──────────┴─────────────────┘  │
├─────────────────────────────────────────────┤
│  UDP (用户提供 send/receive 回调)           │
└─────────────────────────────────────────────┘
```

### ngtcp2 的核心设计模式

ngtcp2 采用**纯回调（callback）设计**——它对 I/O 一无所知，由用户提供回调函数处理各种事件。

```c
/*
 * ngtcp2 核心对象创建
 * 
 * ngtcp2 是一种 "non-blocking, event-driven" API：
 * - 用户调用 ngtcp2_conn_*() 函数推动协议
 * - ngtcp2 通过回调（callbacks）向用户通知事件
 * - 用户不提供 I/O 实现，只提供 UDP 收发回调
 */

#include <ngtcp2/ngtcp2.h>

/* =========================================================
 * 1. 定义回调函数
 * ========================================================= */

/*
 * 接收数据回调（ngtcp2 调用用户提供的方法）
 * 
 * 当 ngtcp2 需要发送数据时，调用此回调。
 * 用户在此回调中调用 sendto() 发送 UDP 数据包。
 */
static int
client_recv_cb(ngtcp2_conn *conn,
               const ngtcp2_cid *dcid,
               const uint8_t *data,
               size_t datalen,
               void *user_data)
{
    /* user_data 指向自定义上下文，如 socket fd */
    struct Context *ctx = (struct Context *)user_data;
    
    int ret = sendto(ctx->fd, data, datalen, 0,
                     (const struct sockaddr *)&ctx->remote_addr,
                     ctx->remote_addrlen);
    if (ret < 0) {
        return NGTCP2_ERR_CALLBACK_FAILURE;
    }
    return 0;
}

/* 握手完成回调 */
static int
handshake_completed_cb(ngtcp2_conn *conn, void *user_data)
{
    struct Context *ctx = (struct Context *)user_data;
    ctx->handshake_done = 1;
    fprintf(stderr, "QUIC 握手完成！\n");
    return 0;
}

/* 流数据接收回调 */
static int
stream_recv_cb(ngtcp2_conn *conn,
               uint32_t flags,
               int64_t stream_id,
               uint64_t offset,
               const uint8_t *data,
               size_t datalen,
               void *user_data,
               void *stream_user_data)
{
    /* 收到流数据：可以传递给 HTTP/3 解析器 */
    struct Context *ctx = (struct Context *)user_data;
    
    /* 保存或处理收到的数据 */
    ctx->stream_data[stream_id] = append_data(
        ctx->stream_data[stream_id],
        data, datalen
    );
    
    return 0;
}

/* =========================================================
 * 2. 初始化 QUIC 客户端连接
 * ========================================================= */

static int
setup_quic_client(struct Context *ctx)
{
    int ret;
    
    /* 配置传输参数 */
    ngtcp2_settings settings;
    ngtcp2_settings_default(&settings);
    
    /* 初始流控窗口: 默认 15360 字节 */
    settings.initial_ts = get_timestamp();
    settings.cc_algo = NGTCP2_CC_ALGO_CUBIC;
    
    /* 配置 TLS（透过 ngtcp2_crypto_* API 与 TLS 栈连接） */
    ngtcp2_crypto_conn_ref ref;
    ngtcp2_crypto_conn_ref_init(&ref, NGTCP2_CRYPTO_REF_TYPE_TLS);
    
    /* 生成客户端 Connection ID */
    ngtcp2_cid scid;
    ngtcp2_cid_init(&scid, my_scid_bytes, sizeof(my_scid_bytes));
    
    /* 设置回调 */
    ngtcp2_callbacks callbacks = {
        .client_initial = client_initial_cb,
        .recv_stream_data = stream_recv_cb,         /* 流数据到达 */
        .handshake_completed = handshake_completed_cb,  /* 握手完成 */
        .send = client_recv_cb,                     /* I/O 发送 */
        /* ... 还有更多回调 ... */
    };
    
    /* 创建连接对象 */
    ret = ngtcp2_conn_client_new(
        &ctx->conn,
        &dcid,           /* 目标 CID（服务器用于路由） */
        &scid,           /* 源 CID（QUIC 连接标识） */
        &callbacks,
        &settings,
        NULL,            /* TLS 连接 */
        ctx              /* user_data */
    );
    if (ret != 0) {
        return -1;
    }
    
    /* 发送 Initial 包开始握手 */
    ngtcp2_conn_handshake(ctx->conn, NULL);
    
    return 0;
}

/* =========================================================
 * 3. 事件循环（简化）
 * ========================================================= */

static void
event_loop(struct Context *ctx)
{
    while (!ctx->done) {
        /* 使用 poll/select/epoll 等待可读事件 */
        struct pollfd pfd = { .fd = ctx->fd, .events = POLLIN };
        int ret = poll(&pfd, 1, 100);  /* 100ms 超时 */
        
        if (ret > 0 && (pfd.revents & POLLIN)) {
            /* 读取 UDP 数据包 */
            uint8_t buf[65535];
            struct sockaddr_storage addr;
            socklen_t addrlen = sizeof(addr);
            
            ssize_t nread = recvfrom(ctx->fd, buf, sizeof(buf),
                                     0, (struct sockaddr *)&addr,
                                     &addrlen);
            if (nread < 0) continue;
            
            /* 将收到的数据送达 ngtcp2 */
            ngtcp2_conn_recv(ctx->conn, buf, nread);
        }
        
        /* 检查是否有数据需要发送 */
        ngtcp2_conn_handle_expiry(ctx->conn, get_timestamp());
        ngtcp2_conn_send(ctx->conn);
    }
}
```

### ngtcp2 的包处理流程（内部）

```
接收 UDP 包 ──→ ngtcp2_pkt_decode()
                 │
                 ├── 解析 Long/Short Header
                 ├── 提取 DCID/SCID
                 ├── 查找匹配的连接
                 │
                 ▼
            ngtcp2_conn_recv()
                 │
                 ├── 解密 Payload（调用 TLS 层）
                 ├── 解析 Frame 列表
                 │     ├── STREAM 帧 → stream_recv_cb
                 │     ├── ACK 帧    → 更新 RTT/丢包检测
                 │     ├── CRYPTO 帧 → 更新 TLS 握手状态
                 │     ├── MAX_DATA → 更新连接级别流控
                 │     └── 其他帧    → 对应处理
                 │
                 ├── 更新拥塞控制状态
                 ├── 更新流控状态
                 └── 产生事件事件
```

---

## 7.2 msquic（微软API抽象层）

### msquic 概述

**msquic** 是微软开发的跨平台 QUIC 实现，用于 Windows 的 HTTP/3 支持（包括 IIS、.NET）、Linux 和 macOS 也有支持。

- 仓库：https://github.com/microsoft/msquic
- 语言：C（核心）
- API 风格：**面向对象风格**，通过 `QUIC_HANDLE` 和回调查询模式

### msquic 的 API 设计

```c
/*
 * msquic API 示例
 * 
 * msquic 使用 "Registration → Listener → Connection → Stream" 的层次结构
 */

#include <msquic.h>

/* =========================================================
 * 1. 初始化 QUIC 库
 * ========================================================= */

/*
 * 创建 QUIC 注册（Registration）
 * 注册是 msquic 资源管理的顶层容器。
 * 一个进程通常只创建一个注册。
 */
HQUIC Registration;

MsQuicOpen2(&Registration);  /* 打开 msquic 2.0 API */

/* =========================================================
 * 2. 创建连接并设置回调
 * ========================================================= */

/* 
 * msquic 用"回调查询表"来分发事件。
 * 当连接状态变化时，msquic 调用对应的回调函数。
 */
QUIC_CONNECTION_CALLBACK_HANDLER ConnectionCallback;

/* 回调函数 */
_IRQL_requires_max_(DISPATCH_LEVEL)
_Function_class_(QUIC_CONNECTION_CALLBACK)
QUIC_STATUS
QUIC_API
ConnectionCallback(
    _In_ HQUIC Connection,
    _Inout_opt_ void *Context,
    _Inout_ QUIC_CONNECTION_EVENT *Event
    )
{
    switch (Event->Type) {
    
    /* QUIC 连接建立（握手完成） */
    case QUIC_CONNECTION_EVENT_CONNECTED:
        printf("QUIC 连接已建立！\n");
        
        /* 此时可以打开流进行数据传输 */
        {
            HQUIC Stream;
            MsQuic->StreamOpen(
                Connection,
                QUIC_STREAM_OPEN_FLAG_NONE,
                StreamCallback,
                NULL,        /* Context */
                &Stream
            );
            /* 发送 HTTP 请求数据 */
            MsQuic->StreamSend(
                Stream,
                Buffers,     /* QUIC_BUFFER 数组 */
                BufferCount,
                QUIC_SEND_FLAG_START, /* 启动流 */
                NULL
            );
        }
        break;
    
    /* 连接关闭 */
    case QUIC_CONNECTION_EVENT_SHUTDOWN_COMPLETE:
        printf("QUIC 连接已关闭\n");
        break;
    
    /* 收到流数据 */
    case QUIC_CONNECTION_EVENT_STREAM_DATA_AVAILABLE:
        /* 从流中读取数据 */
        MsQuic->StreamReceive(
            Event->STREAM_DATA_AVAILABLE.Stream,
            NULL
        );
        break;
    
    default:
        break;
    }
    
    return QUIC_STATUS_SUCCESS;
}

/* =========================================================
 * 3. 启动客户端连接
 * ========================================================= */

void StartQuicClient(const char *host, uint16_t port)
{
    HQUIC Connection;
    
    /* 创建 QUIC 连接句柄 */
    MsQuic->ConnectionOpen(
        Registration,
        ConnectionCallback,  /* 上一步定义的回调 */
        NULL,                /* Context */
        &Connection
    );
    
    /* 设置 ALPN 为 h3 (HTTP/3) */
    const char *alpn = "h3";
    MsQuic->SetParam(
        Connection,
        QUIC_PARAM_LEVEL_CONNECTION,
        QUIC_PARAM_CONN_REMOTE_ADDRESS,
        sizeof(QUIC_ADDRESS_FAMILY),
        &addr
    );
    
    /* 开始连接 */
    MsQuic->ConnectionStart(
        Connection,
        AF_INET,         /* 地址族 */
        host,            /* 目标主机名 */
        port             /* 端口号 (443) */
    );
}
```

### msquic 的线程模型

```
msquic 内部的线程模型：

┌──────────────────────┐
│   应用主线程          │
│     │                 │
│     │ MsQuic->Xxx()  │ ← 用户线程调用 msquic API
│     ▼                 │
├──────────────────────┤
│   msquic Worker       │ ← msquic 内部线程池
│   ┌────────────────┐  │
│   │   UDP Socket   │  │ ← 接收/发送数据包
│   ├────────────────┤  │
│   │ 连接状态机     │  │ ← 管理连接状态转移
│   ├────────────────┤  │
│   │ 拥塞控制       │  │ ← 速率控制
│   ├────────────────┤  │
│   │ 丢包检测       │  │ ← 定时器驱动
│   └────────────────┘  │
├──────────────────────┤
│   用户回调            │ ← 在 msquic 线程中执行
│ (不可长时间阻塞)      │   需快速返回，不可 sleep
└──────────────────────┘
```

---

## 7.3 LSQUIC（LiteSpeed生产级）

### LSQUIC 概述

**lsquic** 是 LiteSpeed Technologies 开发的 QUIC 实现，长期在 LiteSpeed Web Server 生产环境运行。

- 仓库：https://github.com/litespeedtech/lsquic
- 特点：支持 QUIC v1/v2、HTTP/3、服务器推送、Ticket 恢复
- 被 Nginx QUIC 实现参考

### lsquic 引擎架构

```c
/*
 * lsquic 核心：Engine（引擎）
 * 
 * lsquic 使用 "Engine" 概念管理所有 QUIC 连接。
 */

#include <lsquic.h>

/*
 * 创建 lsquic 引擎
 * 
 * lsquic_engine 管理：
 * - 多个 QUIC 连接
 * - 定时器
 * - 配置参数
 * - 内部内存池
 */
lsquic_engine_t *
create_lsquic_engine(struct lsquic_engine_api *api)
{
    struct lsquic_engine_settings settings;
    lsquic_engine_init_settings(&settings,
                                0);  /* 0 = 使用默认设置 */
    
    /* 自定义配置 */
    settings.es_versions = LSQUIC_DF_VERSIONS;  /* 支持的 QUIC 版本 */
    settings.es_max_cwnd = 15000000;  /* 最大拥塞窗口 */
    
    /* 创建引擎 */
    lsquic_engine_t *engine = lsquic_engine_new(
        LSENG_HTTP,           /* 引擎模式：HTTP 或全双工 */
        &settings             /* 配置参数 */
    );
    
    return engine;
}

/*
 * lsquic 的事件驱动模式
 * 
 * lsquic 的典型事件循环：
 */
void
event_loop(lsquic_engine_t *engine, int sock_fd)
{
    while (!shutdown) {
        /* 第1步：处理网络 I/O */
        if (has_incoming_packets(sock_fd)) {
            struct sockaddr_storage peer_addr;
            socklen_t addrlen = sizeof(peer_addr);
            unsigned char buf[QUIC_MAX_PKT_SZ];
            
            ssize_t n = recvfrom(sock_fd, buf, sizeof(buf),
                                 0, (struct sockaddr *)&peer_addr,
                                 &addrlen);
            
            /* 将数据包喂给 lsquic 引擎 */
            lsquic_engine_packet_in(
                engine,
                buf,          /* 接收到的 UDP 载荷 */
                n,            /* 实际接收字节数 */
                sock_fd,      /* 套接字描述符 */
                &peer_addr,   /* 对端地址 */
                &local_addr,  /* 本端地址 */
                0             /* ECN 标记 */
            );
        }
        
        /* 第2步：处理引擎内部事件/超时 */
        lsquic_engine_process_connections(engine);
        
        /* 第3步：检查是否有数据要发送 */
        {
            lsquic_engine_out_event_s *event = lsquic_engine_get_event(engine, 0);
            if (event && event->type == LSENG_EVENT_PACKET_OUT) {
                /* 获取要发送的数据 */
                const struct iovec *vecs = event->packet_out->vecs;
                int nvecs = event->packet_out->nvecs;
                
                /* 发送到对端 */
                sendmsg(sock_fd, construct_msghdr(...), 0);
            }
        }
        
        /* 第4步：获取下一个超时 */
        int timeout_ms = lsquic_engine_next_tick(engine);
        if (timeout_ms > 0) {
            /* 等待直到超时或新数据到达 */
            wait_for_io(sock_fd, timeout_ms);
        }
    }
}
```

---

## 7.4 代码层面理解包处理流程

### QUIC 包收发的完整路径

```
============================
发送路径（Send Path）
============================

应用层:
  HTTP/3 发送数据 ──→ 传递给 QUIC 层
                        │
QUIC 流层:
  Stream 管理 ─────────→ STREAM 帧组装
  (流的创建、缓冲、    (根据流 ID、偏移、长度)
   优先级排队)
                        │
QUIC 帧层:
  帧组装 ─────────────→ CRYPTO/PING/PATH_CHALLENGE 等
  各种帧类型编码          非 STREAM 帧
                        │
QUIC 包层:
  包编号分配 ──────────→ 包编号空间: Initial/Handshake/1-RTT
  单调递增 PN
                        │
加密层:
  加密 ────────────────→ 使用对应阶段的密钥加密
     Header Protection     (Initial/Handshake/1-RTT key)
     Payload Encryption
                        │
QUIC 包编码:
  头编码 ──────────────→ Long/Short Header
  CID 添加                 加上实际的 DCID
  版本字段(Inital包)
                        │
协议栈选择:
  发送 ────────────────→ sendto(fd, quic_packet, len)
                          经由 UDP 发送
```

```
============================
接收路径（Receive Path）
============================

UDP 接收:
  recvfrom(fd, buf) ──→ 获取 UDP 载荷
                          含一个或多个 QUIC 包（coalescing）
                        │
QUIC 包解码:
  头部解析 ───────────→ 检测 Long/Short Header
  CID 匹配                提取 DCID 找到对应连接
                        │
解密:
  尝试解密 ────────────→ 根据 Header 类型
                          使用对应密钥
                          失败则丢弃
                        │
包编号处理:
  去重 ────────────────→ 包编号检测（防止重放）
  确认                      生成 ACK 帧（待发送）
                        │
帧解谜:
  处理帧 ──────────────→ STREAM → 流数据处理
                          CRYPTO → TLS 握手推进
                          ACK → RTT 更新 + 丢包检测
                          MAX_DATA/MAX_STREAM_DATA → 流控更新
                          PATH_CHALLENGE → 验证回复
                          CONNECTION_CLOSE → 连接关闭
                        │
上层事件:
  应用数据 ────────────→ 通知应用层有新数据
                          通过回调或事件队列
```

### 关键数据结构

```c
/*
 * QUIC 实现中核心数据结构的伪代码
 * （与 ngtcp2/msquic/lsquic 类似）
 */

/* =========================================================
 * 连接对象（核心）
 * ========================================================= */
struct quic_connection {
    /* 标识 */
    ngtcp2_cid src_cid;        /* 源 Connection ID */
    ngtcp2_cid dst_cid;        /* 目标 Connection ID */
    
    /* 状态机：
     * CONNECTING (握手) → ESTABLISHED (数据传输) → CLOSING → CLOSED
     */
    enum quic_conn_state state;
    
    /* 流管理 */
    struct rb_tree streams;      /* 按 stream ID 索引 */
    uint64_t max_streams_bidi;   /* 最大并发双向流数 */
    uint64_t max_streams_uni;    /* 最大并发单向流数 */
    
    /* 流量控制 */
    uint64_t max_data;           /* 连接级别最大数据量 */
    uint64_t bytes_received;     /* 已接收总字节数 */
    
    /* 拥塞控制 */
    struct congestion_controller *cc;
    uint64_t cwnd;               /* 拥塞窗口 */
    uint64_t ssthresh;           /* 慢启动门限 */
    uint64_t bytes_in_flight;    /* 在途字节数 */
    
    /* 恢复状态 */
    struct rtt_stats rtt;
    uint64_t loss_detection_timer;
    
    /* 加密 */
    struct tls_context tls;
    uint8_t *initial_key;
    uint8_t *handshake_key;
    uint8_t *app_key;
    int key_phase;
};

/* =========================================================
 * 流对象
 * ========================================================= */
struct quic_stream {
    int64_t stream_id;           /* Stream ID（0, 4, 8...） */
    uint32_t flags;              /* 标志: SEND/RCV 等 */
    
    /* 发送缓冲区 */
    struct linked_list send_buffer;  /* 待发送数据 */
    uint64_t send_offset;            /* 已发送的字节偏移 */
    
    /* 接收状态 */
    struct hole_queue recv_holes;   /* 接收到的数据洞（乱序到达） */
    uint64_t recv_offset;           /* 连续已接收的字节偏移 */
    
    /* 流级别流量控制 */
    uint64_t max_stream_data;       /* 该流最大数据量 */
    
    /* 流用户数据（HTTP/3 上下文） */
    void *user_data;
};

/* =========================================================
 * 包对象
 * ========================================================= */
struct quic_packet {
    /* 包类型 */
    enum {
        QUIC_PKT_INITIAL,
        QUIC_PKT_HANDSHAKE,
        QUIC_PKT_RETRY,
        QUIC_PKT_1RTT,
        QUIC_PKT_VERSION_NEGOTIATION,
    } type;
    
    /* 包编号 */
    int64_t packet_number;
    enum pn_space pn_space;      /* Initial/Handshake/1-RTT */
    
    /* 发送时间（用于 RTT 计算） */
    uint64_t send_time;
    
    /* 帧列表 */
    struct frame *frames;
    int num_frames;
    
    /* 已发送次数 */
    int send_count;
    
    /* 原始数据 */
    uint8_t *raw_data;
    size_t raw_len;
};
```

### 关键算法：丢包检测（RFC 9002 实现逻辑）

```c
/*
 * QUIC 丢包检测核心算法伪代码
 * 参考 RFC 9002 §6
 */

/* 检测包是否丢失 */
static int
detect_lost_packets(struct quic_connection *conn,
                    uint64_t largest_acked,
                    uint64_t now)
{
    int lost_count = 0;
    
    /*
     * 遍历所有未确认的包（在包的发送时间顺序上）
     * 找出满足以下条件的包标记为丢失：
     * 
     * 条件 A: 包编号 < largest_acked 且未被该 ACK 确认
     * 条件 B: 超过丢包检测超时时间
     */
    
    struct sent_packet *pkt = conn->sent_packets.head;
    
    while (pkt && pkt->packet_number <= largest_acked) {
        int is_lost = 0;
        
        /* 条件 A: 包阈值法
         * 如果已确认的包编号中最大的减去当前包编号 >= 3
         * 且当前包未被确认，判定为丢失
         */
        if (pkt->packet_number + 3 <= largest_acked) {
            is_lost = 1;
        }
        
        /* 条件 B: 时间阈值法
         * 如果包发送后经过的时间超过阈值
         */
        if (!is_lost) {
            uint64_t threshold = compute_loss_delay(conn);
            if (now - pkt->send_time >= threshold) {
                is_lost = 1;
            }
        }
        
        if (is_lost) {
            /* 标记为丢失 */
            pkt->lost = 1;
            lost_count++;
            
            /* 通知拥塞控制器 */
            conn->cc->on_loss(conn, pkt);
        }
        
        pkt = pkt->next;
    }
    
    return lost_count;
}

/* 计算丢包检测延迟阈值 */
static uint64_t
compute_loss_delay(struct quic_connection *conn)
{
    /*
     * RFC 9002: 丢包检测延迟 = max(1.125 * srtt, kGranularity) 
     *                          + max(4 * rttvar, kGranularity)
     *                          + ack_delay
     */
    uint64_t delay = max(conn->rtt.smoothed_rtt * 9 / 8,
                         1000);  /* kGranularity = 1ms */
    delay += max(conn->rtt.rttvar * 4, 1000);
    delay += conn->rtt.latest_ack_delay;
    
    return delay;
}
```

---

## 一句话总结

ngtcp2 采用纯 C 回调驱动的架构实现最高性能，msquic 提供面向对象的 API 抽象层和线程安全设计，lsquic 在生产环境中经过验证，三者都遵循 QUIC 包处理的三阶段（接收→解密→帧处理）事件驱动模型。
