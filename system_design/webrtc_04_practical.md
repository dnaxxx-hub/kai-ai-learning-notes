# WebRTC 第4课：Python 实战 — aiortc 实现

## 1. aiortc 是什么？

aiortc 是 Python 的 WebRTC 实现，支持：
- RTCPeerConnection
- 媒体流（本地摄像头/文件）
- Data Channel
- 与浏览器互操作

```bash
pip install aiortc aiohttp
```

## 2. 简单端到端：Python ↔ 浏览器

### 信令服务器（aiohttp WebSocket）

```python
import asyncio
import aiohttp
from aiohttp import web
from aiortc import RTCPeerConnection, MediaStreamTrack, RTCSessionDescription
import json

# 房间管理
rooms = {}

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    room_id = None
    
    async for msg in ws:
        data = json.loads(msg.data)
        
        if data['type'] == 'join':
            room_id = data['room']
            if room_id not in rooms:
                rooms[room_id] = {'offer': None, 'answer': None}
            rooms[room_id][data['role']] = ws
            
            # 如果双方都在，通知 offer 方开始连接
            if rooms[room_id].get('offer') and rooms[room_id].get('answer'):
                await rooms[room_id]['offer'].send_str(json.dumps({
                    'type': 'peer_ready'
                }))
        
        elif data['type'] == 'offer':
            rooms[room_id]['sdp_offer'] = data
            if rooms[room_id].get('answer'):
                await rooms[room_id]['answer'].send_str(json.dumps(data))
        
        elif data['type'] == 'answer':
            rooms[room_id]['sdp_answer'] = data
            if rooms[room_id].get('offer'):
                await rooms[room_id]['offer'].send_str(json.dumps(data))
        
        elif data['type'] == 'candidate':
            # 转发 ICE Candidate
            other = rooms[room_id].get('offer' if data['role'] == 'answer' else 'answer')
            if other:
                await other.send_str(json.dumps(data))
    
    return ws

app = web.Application()
app.router.add_get('/ws', websocket_handler)
web.run_app(app, port=8765)
```

### Python Offer 端

```python
from aiortc import RTCPeerConnection, RTCSessionDescription
import json

async def create_offer():
    pc = RTCPeerConnection()
    
    # 添加音频/视频轨（可选，如果只需要 Data Channel）
    # 创建 Data Channel
    dc = pc.createDataChannel('chat')
    
    @dc.on('message')
    def on_message(message):
        print(f"Received: {message}")
    
    # 创建 Offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    # 通过 WebSocket 发送
    return {
        'type': 'offer',
        'sdp': pc.localDescription.sdp,
        'role': 'offer'
    }
```

### 浏览器 Answer 端

```javascript
// 浏览器端代码
const pc = new RTCPeerConnection();

let dc = null;

// 收到 offer
async function handleOffer(offer) {
    await pc.setRemoteDescription(offer);
    
    // 创建 answer
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    
    // 发送 answer 给信令服务器
    ws.send(JSON.stringify({
        type: 'answer',
        sdp: answer.sdp,
        role: 'answer'
    }));
}

// Data Channel 事件
pc.ondatachannel = (event) => {
    dc = event.channel;
    dc.onmessage = (e) => console.log(e.data);
    dc.onopen = () => dc.send('Hello from browser!');
};
```

## 3. 纯 Python ↔ Python（无浏览器）

```python
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription
import json

async def run_p2p():
    # 创建两个 PeerConnection
    pc1 = RTCPeerConnection()
    pc2 = RTCPeerConnection()
    
    # PC1 创建 Data Channel
    dc1 = pc1.createDataChannel('test')
    received = []
    
    @dc1.on('open')
    def on_open():
        dc1.send("Hello from PC1!")
    
    # PC2 接收
    @pc2.on('datachannel')
    def on_datachannel(channel):
        @channel.on('message')
        def on_message(msg):
            print(f"PC2 received: {msg}")
            received.append(msg)
    
    # 交换 SDP（本地信号，不需要网络）
    async def do_signaling():
        # 创建 offer
        offer = await pc1.createOffer()
        await pc1.setLocalDescription(offer)
        
        # 设置对方 remote
        await pc2.setRemoteDescription(pc1.localDescription)
        
        # 创建 answer
        answer = await pc2.createAnswer()
        await pc2.setLocalDescription(answer)
        
        # 设置 PC1 的 remote
        await pc1.setRemoteDescription(pc2.localDescription)
    
    await do_signaling()
    await asyncio.sleep(0.1)  # 等 ICE 连接完成
    
    print(f"Connection state: {pc1.connectionState}")
    assert received[0] == "Hello from PC1!"
    print("✅ P2P data channel works!")
    
    await pc1.close()
    await pc2.close()

asyncio.run(run_p2p())
```

## 4. 文件传输实战

```python
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription
import os

CHUNK_SIZE = 16384  # 16KB

async def send_file(pc, filepath):
    dc = pc.createDataChannel('file-transfer')
    
    file_size = os.path.getsize(filepath)
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    @dc.on('open')
    async def on_open():
        # 发元数据
        dc.send(json.dumps({
            'type': 'meta',
            'name': os.path.basename(filepath),
            'size': file_size,
            'chunks': total_chunks
        }))
        
        # 分块发送
        with open(filepath, 'rb') as f:
            for i in range(total_chunks):
                chunk = f.read(CHUNK_SIZE)
                dc.send(chunk)
                # 可以加进度回调
                if (i + 1) % 10 == 0:
                    print(f"Progress: {i+1}/{total_chunks}")
        
        print(f"✅ 文件发送完成: {filepath}")

async def receive_file(pc, output_dir='.'):
    file_buffer = {}
    
    @pc.on('datachannel')
    def on_datachannel(channel):
        
        @channel.on('message')
        def on_message(msg):
            if isinstance(msg, str):
                meta = json.loads(msg)
                if meta['type'] == 'meta':
                    file_buffer['name'] = meta['name']
                    file_buffer['size'] = meta['size']
                    file_buffer['chunks'] = meta['chunks']
                    file_buffer['data'] = bytearray()
                return
            
            # 二进制数据
            file_buffer['data'].extend(msg)
            
            if len(file_buffer['data']) >= file_buffer['size']:
                out = os.path.join(output_dir, file_buffer['name'])
                with open(out, 'wb') as f:
                    f.write(file_buffer['data'])
                print(f"✅ 文件接收完成: {out}")
```

## 5. aiortc 限制与注意事项

1. **不支持 Simulcast** — aiortc 不实现分层编码
2. **Windows 摄像头** — 需要 pyav 或 OpenCV，不能直接用 browser API
3. **TURN 服务器** — 需要额外部署 coturn 等服务
4. **性能** — Python 编解码效率不如浏览器原生实现

## 6. 替代方案

| 工具 | 语言 | 特点 |
|------|------|------|
| aiortc | Python | 灵活，可纯Python P2P |
| pion/webrtc | Go | 高性能，适合做 TURN 服务器 |
| medooze | C++/Node | 媒体服务器级 |
| Janus | C | 通用 WebRTC 服务器 |

---

**下一篇**: WebRTC Roadmap
