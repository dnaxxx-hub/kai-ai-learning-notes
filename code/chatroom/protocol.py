"""
protocol.py — 消息协议定义 (长度前缀+JSON)
4字节长度前缀(NBO) + JSON消息体
"""

import struct
import json


def pack(msg: dict) -> bytes:
    """打包消息 → 4字节长度 + JSON"""
    body = json.dumps(msg, ensure_ascii=False).encode('utf-8')
    return struct.pack('!I', len(body)) + body


def unpack(data: bytes) -> dict:
    """解包消息: 从二进制数据中提取一条完整消息"""
    if len(data) < 4:
        raise ValueError("Message too short")
    length = struct.unpack('!I', data[:4])[0]
    body = data[4:4 + length]
    return json.loads(body.decode('utf-8'))


def parse_stream(buffer: bytes):
    """从流式缓冲区中解析出所有完整消息，返回 (messages, remaining_buffer)"""
    messages = []
    offset = 0
    while len(buffer) - offset >= 4:
        length = struct.unpack('!I', buffer[offset:offset + 4])[0]
        total = 4 + length
        if len(buffer) - offset < total:
            break
        body = buffer[offset + 4:offset + total]
        messages.append(json.loads(body.decode('utf-8')))
        offset += total
    return messages, buffer[offset:]
