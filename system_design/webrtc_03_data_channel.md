# WebRTC 第3课：Data Channel — 数据通道

## 1. 什么是 Data Channel？

Data Channel 让你在 WebRTC 连接上传输任意数据（文本、二进制、文件），与音视频独立。

## 2. 传输层：SCTP over DTLS

```
[应用数据] → SCTP → DTLS → UDP → 网络
```

### SCTP（Stream Control Transmission Protocol）

- **有序/无序**：可以按序或乱序发送
- **多流**：一个连接多个独立流
- **可靠/不可靠**：可选部分可靠
- **部分可靠模式**：最大重传次数 / 最大超时时间

### DTLS（Datagram TLS）

TLS 的 UDP 版本，为 WebRTC 提供：
- **加密**：所有数据加密传输
- **身份验证**：防中间人攻击
- **完整性**：数据未被篡改

## 3. Data Channel 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| ordered | true | 数据是否按序交付 |
| maxRetransmits | null | 最大重传次数（null=无限） |
| maxPacketLifeTime | null | 数据包最大存活时间（ms） |
| protocol | "" | 子协议标识符 |
| negotiated | false | true=预先协商的 id，false=带外协商 |

### 典型配置模式

```javascript
// 可靠有序（文件传输）
{ ordered: true }

// 可靠无序（实时游戏状态）
{ ordered: false }

// 部分可靠（实时视频帧控制信令）
{ ordered: true, maxRetransmits: 3 }

// 不可靠+超时（心跳/位置更新）
{ ordered: false, maxPacketLifeTime: 1000 }
```

## 4. 场景对照

| 场景 | 模式 | 原因 |
|------|------|------|
| 文件传输 | 可靠有序 | 数据完整性优先 |
| 文字聊天 | 可靠有序 | 防止消息顺序错乱 |
| 游戏位置更新 | 不可靠无序 | 最新位置才是重要的，旧位置跳过 |
| 实时协作编辑 | 可靠有序 | 操作日志不能丢 |
| 视频字幕 | 部分可靠(3次) | 偶尔丢一两条字幕可以忍受 |
| 批量传感器数据 | 不可靠+超时 | 旧数据没用，最新数据最值钱 |

## 5. 发送大文件的策略

```javascript
// 数据通道消息大小限制：通常 16KB~64KB
// 大文件需要分块发送

const MAX_CHUNK_SIZE = 16384;  // 16KB

function sendLargeFile(dc, file) {
    const totalChunks = Math.ceil(file.size / MAX_CHUNK_SIZE);
    let offset = 0;
    
    // 1. 先发元数据
    dc.send(JSON.stringify({
        type: 'file-start',
        name: file.name,
        totalChunks: totalChunks
    }));
    
    // 2. 分块发送
    for (let i = 0; i < totalChunks; i++) {
        const chunk = file.slice(offset, offset + MAX_CHUNK_SIZE);
        dc.send(chunk);
        offset += MAX_CHUNK_SIZE;
    }
    
    // 3. 发送完成标记
    dc.send(JSON.stringify({ type: 'file-end' }));
}
```

## 6. 值得注意的局限

1. **消息大小限制**：通常 16KB~64KB（取决于浏览器实现）
2. **不支持直接广播**：Data Channel 是点对点的，多人会议需要单独通道
3. **优先级控制不精细**：SCTP 流优先级不是标准的 Web API
4. **Data Channel 与 WebSocket 对比**

| 特性 | Data Channel | WebSocket |
|------|-------------|-----------|
| 架构 | P2P | C/S |
| 延迟 | 更低（不走服务器） | 略高 |
| 加密 | DTLS（自动） | TLS（手动） |
| 可靠性 | 可配置 | 全可靠有序 |
| 扩展性 | 点对点 | 分布式架构更好 |

---

**下一篇**: Python 实战 — aiortc 实现 P2P 视频通话
