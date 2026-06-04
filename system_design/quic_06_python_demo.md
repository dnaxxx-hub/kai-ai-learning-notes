# 第6课：QUIC实现对比 — 用Python写demo

> 参考 aioquic v1.3.0 文档：https://aioquic.readthedocs.io/

---

## 6.1 aioquic 简介

**aioquic** 是由 Jeremy Lainé 开发的 Python QUIC 和 HTTP/3 实现，是目前 Python 生态中最完整的 QUIC 库。

- 仓库：https://github.com/aiortc/aioquic
- PyPI：`pip install aioquic`
- Python：>= 3.10
- 许可证：BSD-3-Clause

### 安装

```bash
pip install aioquic
```

### aioquic 的架构层次

```
┌─────────────────────────────────────────┐
│  HTTP/3 API                             │
│  ┌───────────────────────────────────┐  │
│  │  H3Connection                    │  │ ← 最上层，处理 HTTP/3 语义
│  │  H3Request, H3Response          │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  QUIC API ("Bring Your Own I/O")       │
│  ┌───────────────────────────────────┐  │
│  │  QuicConnection                  │  │ ← 核心，负责状态机、加密、流控
│  │  QuicStream                      │  │
│  │  QuicEvent                       │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Convenience API (asyncio)              │
│  ┌───────────────────────────────────┐  │
│  │  connect() / serve()             │  │ ← 最方便，封装了 I/O
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 6.2 最小QUIC客户端：连接Google QUIC服务器

```python
"""
最小 QUIC 客户端示例：连接 Google QUIC 服务器

这个示例展示了 QUIC 连接建立的核心流程：
1. 创建 QuicConnection
2. 构建 UDP 数据包
3. 处理握手事件
4. 发送 HTTP/3 请求
5. 接收响应

运行方式：python quic_client_minimal.py
"""

import asyncio
import os
import ssl
from urllib.parse import urlparse

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import (
    QuicEvent,
    HandshakeCompleted,
    ConnectionTerminated,
)
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import (
    H3Event,
    HeadersReceived,
    DataReceived,
)


class Http3Client(QuicConnectionProtocol):
    """
    HTTP/3 客户端协议处理器
    
    继承自 aioquic 的 QuicConnectionProtocol，该基类封装了
    QUIC 连接管理和 I/O 调度。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = None      # H3Connection 实例
        self._done = asyncio.Future()  # 用于标记请求完成
        self._response_data = b""

    def on_http_event(self, event: H3Event) -> None:
        """
        处理 HTTP/3 事件
        
        当 H3Connection 处理完 QUIC 流中的 HTTP/3 帧后，
        会调用此回调函数。
        """
        if isinstance(event, HeadersReceived):
            # 收到响应头
            print(f"响应状态: {[str(h) for h in event.headers]}")
            # event.push_id 如果是 None 则为正常响应，否则是 Server Push

        elif isinstance(event, DataReceived):
            # 收到响应体数据
            self._response_data += event.data
            print(f"收到数据块: {len(event.data)} 字节")

        # 通知 H3Connection 数据已处理完毕
        if event.stream_ended:
            print(f"流 {event.stream_id} 结束")
            if not self._done.done():
                self._done.set_result(self._response_data)

    def on_quic_event(self, event: QuicEvent) -> None:
        """
        处理 QUIC 传输层事件
        
        传输层事件包括握手完成、流打开、数据到达等。
        """
        if isinstance(event, HandshakeCompleted):
            # 握手完成！QUIC 连接已建立
            print(f"QUIC 握手完成，alpn_protocol={event.alpn_protocol}")
            
            # 创建 H3Connection（HTTP/3 层）
            self._http = H3Connection(self._quic)

            # 发送 HTTP GET 请求
            stream_id = self._quic.get_next_available_stream_id()
            self._http.send_headers(
                stream_id=stream_id,
                headers=[
                    (b":method", b"GET"),
                    (b":scheme", b"https"),
                    (b":authority", b"www.google.com"),
                    (b":path", b"/"),
                    (b"user-agent", b"aioquic-demo/1.0"),
                ],
            )
            self._http.send_data(stream_id=stream_id, data=b"", end_stream=True)
            print(f"HTTP/3 GET 请求已发送，stream_id={stream_id}")

        elif isinstance(event, ConnectionTerminated):
            # 连接终止
            print(f"连接终止: 错误码={event.error_code} 原因={event.reason_phrase}")

    def on_quic_event_received(self, event: QuicEvent) -> None:
        """
        回调：从传输层接收到 QUIC 事件
        
        这是 aioquic 的协议钩子，将事件分发给 HTTP 层（如果已建立）。
        """
        self.on_quic_event(event)

        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.on_http_event(http_event)


async def main():
    """
    主函数：建立 QUIC 连接并发送 HTTP/3 请求
    """
    # 配置 QUIC 参数
    configuration = QuicConfiguration(
        alpn_protocols=H3Connection.ALPN_PROTOCOLS,
        is_client=True,
        verify_mode=ssl.CERT_REQUIRED,
    )

    # 加载系统证书（用于验证服务器身份）
    # aioquic 会自动查找系统证书
    configuration.load_default_certificates()

    # 连接目标服务器
    # 注意：connect() 使用 asyncio，会挂起直到连接建立；timeout 控制总超时
    print("正在连接到 www.google.com:443 (QUIC)...")
    async with connect(
        host="www.google.com",
        port=443,
        configuration=configuration,
        create_protocol=Http3Client,
    ) as client:
        # 等待 HTTP 响应（30 秒超时）
        response = await asyncio.wait_for(
            client._done,
            timeout=30.0,
        )
        print(f"收到完整响应: {len(response)} 字节")
        print(response[:500].decode("utf-8", errors="replace"))
        print("... (截断) ...")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6.3 理解连接建立过程和握手

### 握手事件流

```
时间线 (在 aioquic 内部):

1. QuicConnection.send_initial() 
   └─ 组装 Initial 包
      └─ CRYPTO 帧 ← ClientHello
      └─ PADDING 帧 → 满足 1200 字节

2. (网络发送/接收)

3. QuicConnection.receive_datagram()
   └─ 收到 ServerHello (Initial 包)
   └─ 派生 Handshake 密钥
   └─ 收到证书 (Handshake 包)
   └─ 验证证书

4. QuicConnection.send_handshake()
   └─ 发送 Finished (Handshake 包)
   └─ 派生 1-RTT 密钥
   └─ 连接进入 "可发送数据" 状态

5. QuicConnection.send_packet()
   └─ 可以发送加密的 STREAM 帧了！

6. QuicEvent: HandshakeCompleted
   └─ 通知上层：可以开始发送应用数据
```

### 关键代码片段分析

```python
# 1. 配置 QUIC 参数
configuration = QuicConfiguration(
    alpn_protocols=H3Connection.ALPN_PROTOCOLS,
    # ALPN (Application-Layer Protocol Negotiation)：
    # 告诉服务器我们支持 h3 (HTTP/3 over QUIC)
    # 值来自 H3Connection.ALPN_PROTOCOLS = ["h3"]
    
    is_client=True,
    # 声明为客户端模式
    
    verify_mode=ssl.CERT_REQUIRED,
    # 要求验证服务器证书（标准 https 行为）
)

# 2. 创建 QUIC 连接
# QuicConnection 是核心类，它包含了：
# - 连接状态机 (CONNECTING → ESTABLISHED → CLOSING → CLOSED)
# - TLS 握手状态
# - 流状态管理
# - 拥塞控制状态

# 3. 数据包的发送和接收
# aioquic 采用 "Bring Your Own I/O" 模式：
# - send_datagram() 返回要发送的 UDP 数据包（字节串）
# - receive_datagram() 处理收到的 UDP 数据包
# - 实际的 UDP 收发由 asyncio 的 DatagramProtocol 完成

# 4. 事件的产生和处理
# QUIC 层处理完数据包后会产生事件对象：
# - HandshakeCompleted → 握手完成
# - StreamDataReceived → 有流数据到达
# - ConnectionTerminated → 连接终止
# 这些事件被传递给上层的 HTTP/3 处理
```

---

## 6.4 实现HTTP/3 GET请求（带超时和重试）

```python
"""
更完整的 HTTP/3 客户端：支持 GET/POST、超时、错误处理

此示例展示了：
1. 完整的请求-响应循环
2. 多个并发流
3. 响应的完整解析
"""

import asyncio
import ssl
from typing import Optional, Dict, List, Tuple

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import (
    QuicEvent,
    HandshakeCompleted,
    ConnectionTerminated,
    StreamDataReceived,
)
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import (
    H3Event,
    HeadersReceived,
    DataReceived,
    HeadersPush,
)
from aioquic.h3.exceptions import NoAvailablePushIDError


class EnhancedHttp3Client(QuicConnectionProtocol):
    """
    增强版 HTTP/3 客户端
    
    支持：
    - 多并发请求
    - 请求超时
    - Server Push 处理（基础）
    - 错误恢复
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http: Optional[H3Connection] = None
        
        # dict: stream_id -> asyncio.Future
        self._requests: Dict[int, asyncio.Future] = {}
        
        # 连接状态
        self.connected = asyncio.Event()
        self.closed = asyncio.Event()
        self.error: Optional[str] = None

    def make_request(
        self,
        method: str,
        authority: str,
        path: str,
        headers: Optional[List[Tuple[bytes, bytes]]] = None,
        data: bytes = b"",
    ) -> asyncio.Future:
        """
        发送一个 HTTP/3 请求
        
        参数:
            method: HTTP 方法 (GET, POST 等)
            authority: 主机名 (如 b"example.com")
            path: URL 路径 (如 b"/api/data")
            headers: 额外的头部字段
            data: 请求体 (POST 时使用)
        
        返回:
            asyncio.Future: 解析为 (headers, body) 元组
        """
        if self._http is None:
            raise RuntimeError("HTTP/3 连接尚未建立")
        
        # 构造完整的头部列表
        request_headers = [
            (b":method", method.encode() if isinstance(method, str) else method),
            (b":scheme", b"https"),
            (b":authority", authority.encode() if isinstance(authority, str) else authority),
            (b":path", path.encode() if isinstance(path, str) else path),
        ]
        if headers:
            request_headers.extend(headers)
        
        # 获取可用的流 ID
        stream_id = self._quic.get_next_available_stream_id()
        
        # 创建 Future 用于获取响应
        future = asyncio.get_event_loop().create_future()
        self._requests[stream_id] = {
            "future": future,
            "headers": [],
            "data": b"",
        }
        
        # 发送请求头和请求体
        self._http.send_headers(stream_id=stream_id, headers=request_headers)
        if data:
            self._http.send_data(stream_id=stream_id, data=data, end_stream=True)
        else:
            self._http.send_data(stream_id=stream_id, data=b"", end_stream=True)
        
        return future

    def on_http_event(self, event: H3Event) -> None:
        """处理 HTTP/3 事件"""
        if isinstance(event, HeadersReceived):
            request = self._requests.get(event.stream_id)
            if request:
                # 保存响应头
                for name, value in event.headers:
                    request["headers"].append((name.decode(), value.decode()))

        elif isinstance(event, DataReceived):
            request = self._requests.get(event.stream_id)
            if request:
                request["data"] += event.data

        elif isinstance(event, HeadersPush):
            # Server Push 处理（简化：直接忽略）
            print(f"收到 Server Push: push_id={event.push_id}")
            if self._http:
                # 拒绝推送（避免浪费带宽）
                self._http.send_cancel_push(push_id=event.push_id)

        # 流结束 → 完成 Future
        if event.stream_ended:
            if event.stream_id in self._requests:
                req = self._requests.pop(event.stream_id)
                if not req["future"].done():
                    req["future"].set_result((req["headers"], req["data"]))

    def on_quic_event(self, event: QuicEvent) -> None:
        """处理 QUIC 传输层事件"""
        if isinstance(event, HandshakeCompleted):
            print(f"[QUIC] 握手完成, ALPN: {event.alpn_protocol}")
            self._http = H3Connection(self._quic)
            self.connected.set()

        elif isinstance(event, ConnectionTerminated):
            print(f"[QUIC] 连接终止: 错误={event.error_code}")
            self.error = event.reason_phrase
            self.closed.set()
            # 通知所有待处理的请求（异常）
            for stream_id, req in list(self._requests.items()):
                if not req["future"].done():
                    req["future"].set_exception(
                        ConnectionError(f"QUIC 连接终止: {event.reason_phrase}")
                    )
            self._requests.clear()


async def http3_get(
    url: str,
    timeout: float = 10.0,
) -> Tuple[List[Tuple[str, str]], bytes]:
    """
    便捷函数：发送 HTTP/3 GET 请求
    
    用法:
        headers, body = await http3_get("https://www.example.com/")
        print(f"状态: {headers[0]}")
        print(f"响应体: {body[:200]}")
    
    参数:
        url: 完整 URL
        timeout: 超时时间（秒）
    
    返回:
        (响应头列表, 响应体)
    """
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    
    configuration = QuicConfiguration(
        alpn_protocols=H3Connection.ALPN_PROTOCOLS,
        is_client=True,
    )
    configuration.load_default_certificates()
    
    async with connect(
        host=host,
        port=port,
        configuration=configuration,
        create_protocol=EnhancedHttp3Client,
    ) as client:
        # 等待 QUIC 握手完成
        await asyncio.wait_for(client.connected.wait(), timeout=timeout)
        
        # 发送请求
        future = client.make_request(method="GET", authority=host, path=path)
        
        # 等待响应
        headers, body = await asyncio.wait_for(future, timeout=timeout)
        
        return headers, body


async def main():
    """演示：并发请求多个 URL"""
    urls = [
        "https://cloudflare.com/",
        "https://www.google.com/",
    ]
    
    tasks = [http3_get(url) for url in urls]
    
    print("并发发送 HTTP/3 请求...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            print(f"{url}: 错误 → {result}")
        else:
            headers, body = result
            status = dict(headers).get(":status", "???")
            print(f"{url}: 状态={status}, 响应体={len(body)} 字节")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6.5 QUIC UDP 层详解

### 从原始 UDP 到 QUIC 的映射

```
UDP 包 (以太网 ≈ 1500 字节 MTU):
┌───────────────────────────────────────────────────┐
│ UDP 头部 (8 字节)                                 │
│ ┌──────────────┬──────────────┬────────────────┐  │
│ │ 源端口 (2B)  │ 目标端口(2B) │ 长度(2B)       │  │
│ │ checksum (2B)│              │                │  │
│ └──────────────┴──────────────┴────────────────┘  │
├───────────────────────────────────────────────────┤
│ QUIC 数据包 (与 UDP 负载边界对齐)                  │
│ ┌─────────────────────────────────────────────┐   │
│ │ Header (Long/Short) + CID + PN + Payload   │   │
│ └─────────────────────────────────────────────┘   │
├───────────────────────────────────────────────────┤
│ 可能的下一个 QUIC 包（连接合并 coalescing）       │
│ ┌─────────────────────────────────────────────┐   │
│ │ Initial + Handshake 合并在一个 UDP 包中     │   │
│ └─────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┘
```

### aioquic 的 UDP 处理流程（简化）

```python
class QuicProtocol(asyncio.DatagramProtocol):
    """
    asyncio UDP 协议封装 aioquic
    
    这是 aioquic 内部的连接适配器。理解它对理解 QUIC 包处理流程很有帮助。
    """

    def __init__(self, quic_connection: QuicConnection):
        self._quic = quic_connection

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """
        收到 UDP 数据包时的回调
        
        参数:
            data: UDP 负载（一个或多个 QUIC 数据包）
            addr: (IP, 端口)
        """
        # 1. aioquic 尝试解密
        # 2. 如果成功 → 更新连接状态
        # 3. 产生 QuicEvent
        
        for event in self._quic.receive_datagram(data, host=addr[0], port=addr[1]):
            # 处理事件（HandshakeCompleted, StreamDataReceived 等）
            self._on_quic_event(event)

    def send_pending(self):
        """
        发送待发送的 QUIC 数据包
        
        每次调用 process_events() 后，检查发送缓冲区
        """
        for data, addr in self._quic.send_datagrams():
            self.transport.sendto(data, addr)
```

---

## 6.6 抓包分析（Wireshark看QUIC）

### 使用 Wireshark 抓取 QUIC 流量

```
1. 启动 Wireshark，选择网络接口
2. 设置抓包过滤：udp port 443
3. 访问一个支持 QUIC 的网站
4. 在抓包中找到 QUIC 数据包

Wireshark 中 QUIC 包的典型视图：

No.    Time         Source          Destination    Protocol  Length  Info
  1    0.000000     192.168.1.5     142.250.80.4   QUIC     1352    Initial, DCID=...
  2    0.045000     142.250.80.4    192.168.1.5    QUIC     1200    Initial, DCID=...
  3    0.045100     142.250.80.4    192.168.1.5    QUIC     1350    Handshake, DCID=...
  4    0.050000     192.168.1.5     142.250.80.4    QUIC     78      Handshake, DCID=...
  5    0.050200     192.168.1.5     142.250.80.4    QUIC     1350    1-RTT, PN=0, STREAM
  6    0.085000     142.250.80.4    192.168.1.5     QUIC     1350    1-RTT, PN=1, STREAM
```

### 使用 Wireshark 分析要点

```
Initial 包分析：
  QUIC Initial
      Header Form: Long Header (1)
      Version: 1 (0x00000001)
      Destination Connection ID: ...
      Source Connection ID: ...
      Packet Number: 0
      └─ CRYPTP Frame [0x06]
           └─ TLSv1.3 Record: Handshake
                └─ ClientHello

1-RTT 包分析：
  QUIC 1-RTT Protected
      Header Form: Short Header (0)
      Destination Connection ID: ...
      Packet Number: 3
      Protected Payload: ...
      └─ (解密后) STREAM Frame [0x16]
           Stream ID: 4
           Offset: 0
           Length: 128
           FIN: True
           └─ HTTP/3
                └─ HEADERS Frame [0x01]
                └─ DATA Frame [0x00]
```

### QUIC 流量分析技巧

```python
"""
伪代码：程序化解析 QUIC 抓包文件（pcap）

实际可用 scapy 或 pyshark 库分析 QUIC 数据包
"""

# 使用 pyshark 分析 QUIC 流量
"""
import pyshark

cap = pyshark.FileCapture("quic_traffic.pcap")

for packet in cap:
    if 'QUIC' in packet:
        quic = packet.quic
        
        # 查看包类型
        if hasattr(quic, 'packet_type'):
            print(f"QUIC 包类型: {quic.packet_type}")
        
        # 查看 Connection ID
        if hasattr(quic, 'dcid'):
            print(f"DCID: {quic.dcid}")
        
        # 查看帧类型
        if hasattr(quic, 'quic_frame_type'):
            print(f"帧类型: {quic.quic_frame_type}")
        
        # 如果有 CRYPTO 帧，查看 TLS 握手内容
        if hasattr(quic, 'crypto'):
            print(f"CRYPTO 数据长度: {len(bytes(quic.crypto.payload))}")
"""

# 抓包建议：
# 1. 在本地启动一个 QUIC 服务器（如 Caddy）
# 2. 用浏览器访问，Wireshark 抓 localhost 的 UDP 包
# 3. 观察 Initial → Handshake → 1-RTT 的完整握手
# 4. 对比 TCP+TLS 与 QUIC 的握手 RTT 数
```

---

## 6.7 QUIC 实现对比

| 实现 | 语言 | 维护方 | 特性 |
|------|------|--------|------|
| **aioquic** | Python | Jeremy Lainé | 纯 Python, 适合学习和原型验证, 性能一般 |
| **ngtcp2** | C | ngtcp2 团队 | 事件驱动, 高性能, 被 curl 使用 |
| **msquic** | C | Microsoft | Windows 原生, API 设计上层友好, QUIC in .NET |
| **lsquic** | C | LiteSpeed | 生产级, CHROMIUM 早期版本使用 |
| **quiche** | Rust | Cloudflare | 安全优先, 被 curl/nginx 支持 |
| **Chromium QUIC** | C++ | Google | 浏览器事实标准, 最成熟 |
| **quic-go** | Go | Lucas Clemente | Go 生态最佳, 被许多项目使用 |

### aioquic 的定位

```
aioquic 适合：
  ✓ 学习 QUIC 协议细节
  ✓ 快速原型验证
  ✓ Python 项目的 QUIC 支持
  ✓ 测试和集成测试

aioquic 不适合：
  ✗ 高并发生产环境
  ✗ 极致性能场景
  ✗ 移动端或嵌入式环境
```

---

## 一句话总结

aioquic 是 Python 最成熟的 QUIC 库，采用 "Bring Your Own I/O" 架构设计，通过 QuicConnection 处理传输层事件并产生事件通知上层的 H3Connection，完整演示了 QUIC 握手→HTTP/3 请求→响应的全过程。
