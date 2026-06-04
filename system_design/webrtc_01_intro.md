# WebRTC 第1课：WebRTC 基础与 P2P 穿越

## 1. 什么是 WebRTC？

WebRTC（Web Real-Time Communication）是一个开源项目，浏览器/应用之间实现实时音视频通信和数据传输。

**关键特点**：
- 浏览器原生支持（Chrome/Firefox/Safari）
- P2P 架构（数据不走服务器中转）
- 加密传输（DTLS-SRTP 强制加密）
- 无需插件，无需安装

## 2. 核心架构

```
[浏览器 A]  ←P2P→  [浏览器 B]
    ↑                    ↑
    |   (信令服务器)      |
    +--------→[Signaling]←--+
              (WebSocket)
```

### 三个核心 API

| API | 功能 | 用途 |
|-----|------|------|
| `MediaStream` | 获取摄像头/麦克风 | getUserMedia() |
| `RTCPeerConnection` | P2P 连接管理 | 音视频传输 |
| `RTCDataChannel` | 数据通道 | 文件/文字/游戏 |

## 3. NAT 穿越 — 为什么 P2P 难？

**问题**：NAT（网络地址转换）让内网设备只有内网 IP，外网设备无法直接连接。

### ICE（Interactive Connectivity Establishment）

```
尝试路径：
1️⃣ 直连（同一内网）→ STUN 获取公网 IP:端口
2️⃣ STUN 打洞（常见 NAT）→ 端口中继穿透  
3️⃣ TURN 中转（对称 NAT 打不通时）→ 服务器接力
```

### STUN（Session Traversal Utilities for NAT）

客户端问 STUN 服务器："我的公网 IP 和端口是什么？"

```
Client (192.168.1.5:12345) → STUN Server (8.8.8.8:3478)
STUN Server (8.8.8.8:3478) → Client: "你的公网是 203.0.113.5:54321"
```

### TURN（Traversal Using Relays around NAT）

当 STUN 失效时，通过中继服务器转发：

```
Client A → TURN Server → Client B
```

TURN 消耗带宽成本高（服务器流量大），是所有方案中最后的选择。

## 4. SDP 信令（Session Description Protocol）

SDP 描述"你要传什么媒体、什么编码、什么参数"：

```
v=0
o=- 123456 2 IN IP4 0.0.0.0
s=-
t=0 0
m=audio 5004 RTP/AVP 96
a=rtpmap:96 OPUS/48000/2
a=fmtp:96 minptime=10;useinbandfec=1
m=video 5006 RTP/AVP 98
a=rtpmap:98 VP8/90000
```

**信令过程**（需要通过你自己的 WebSocket 服务器中转）：

```
Client A                    Signaling Server                  Client B
    |----- SDP Offer ------->|                                    |
    |                         |--------- SDP Offer --------------->|
    |                         |<------- SDP Answer ----------------|
    |<--- SDP Answer --------|                                    |
    |                                                             |
    |----- ICE Candidate --->|                                    |
    |                         |--------- ICE Candidate ---------->|
    |<--- ICE Candidate -----|                                    |
    |                                                             |
    |============ P2P 连接建立 =============>                    |
```

**关键点**：WebRTC 不定义信令协议，信令传输方式是留给开发者的。

## 5. 连接状态机

```
new → checking → connected → completed
     ↘ failed
     → disconnected → (reconnect) → checking
     → closed
```

## 6. 简单流程伪代码

```python
# 伪代码：WebRTC 连接建立
class WebRTCConnection:
    async def connect(self, remote_sdp_url):
        # 1. 创建 PeerConnection
        pc = RTCPeerConnection()
        
        # 2. 获取本地媒体
        stream = await getUserMedia({'audio': True, 'video': True})
        pc.addTrack(stream)
        
        # 3. 创建 Offer（发起方）
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # 4. 通过信令通道发送 offer
        await signaling.send({'type': 'offer', 'sdp': offer.sdp})
        
        # 5. 接收 Answer
        answer = await signaling.receive()
        await pc.setRemoteDescription(answer)
        
        # 6. ICE 打洞完成 → 连接建立
        return pc
```

---

**下一篇**: 媒体处理 — 音视频编解码
