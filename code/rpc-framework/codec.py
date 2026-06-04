"""codec.py — 序列化/反序列化：自定义二进制协议 (header + JSON body)"""

import json
import struct

# 协议格式 (固定头 + 可变体):
# [4字节: 总长度][1字节: 类型(0=请求/1=响应/2=心跳)][4字节: 消息ID][数据体]
HEADER_SIZE = 9  # 4 + 1 + 4

# 消息类型常量
REQUEST = 0
RESPONSE = 1
HEARTBEAT = 2


class RPCMessage:
    """RPC 消息结构"""
    __slots__ = ('msg_type', 'msg_id', 'body')

    def __init__(self, msg_type=0, msg_id=0, body=None):
        self.msg_type = msg_type  # 0=request, 1=response, 2=heartbeat
        self.msg_id = msg_id
        self.body = body or {}

    def __repr__(self):
        return (f"RPCMessage(type={self.msg_type}, id={self.msg_id}, "
                f"body={self.body})")


def encode(msg_type, msg_id, body):
    """编码 RPC 消息为二进制数据

    Args:
        msg_type: 消息类型 (0=request, 1=response, 2=heartbeat)
        msg_id: 消息 ID
        body: 消息体字典

    Returns:
        bytes: 二进制编码后的完整消息
    """
    body_bytes = json.dumps(body, ensure_ascii=False).encode('utf-8')
    total_len = HEADER_SIZE + len(body_bytes)
    header = struct.pack('!IBI', total_len, msg_type, msg_id)
    return header + body_bytes


def decode(data):
    """解码二进制数据为 RPC 消息

    处理不完整帧：如果数据不足以构成一个完整消息，返回 (None, data)。

    Args:
        data: 二进制数据 (可能包含多个消息，即粘包)

    Returns:
        tuple: (RPCMessage or None, remaining_bytes)
    """
    if len(data) < HEADER_SIZE:
        return None, data

    total_len = struct.unpack('!I', data[:4])[0]
    if total_len < HEADER_SIZE:
        # 无效的长度，跳过这个字节
        return None, data[1:]

    if len(data) < total_len:
        return None, data

    msg_type = data[4]
    msg_id = struct.unpack('!I', data[5:9])[0]
    body_bytes = data[HEADER_SIZE:total_len]
    body = json.loads(body_bytes.decode('utf-8'))

    return RPCMessage(msg_type, msg_id, body), data[total_len:]


def decode_all(data):
    """解码数据中所有完整的消息

    Args:
        data: 二进制数据

    Returns:
        tuple: (messages_list, remaining_bytes)
    """
    messages = []
    remaining = data
    while True:
        msg, remaining = decode(remaining)
        if msg is None:
            break
        messages.append(msg)
    return messages, remaining


# --- 便捷的编码函数 ---

def make_request(msg_id, service, method, args=None, kwargs=None):
    """编码一个 RPC 请求消息"""
    return encode(REQUEST, msg_id, {
        'service': service,
        'method': method,
        'args': args or [],
        'kwargs': kwargs or {},
    })


def make_response(msg_id, result=None, error=None):
    """编码一个 RPC 响应消息"""
    return encode(RESPONSE, msg_id, {
        'result': result,
        'error': error,
    })


def make_heartbeat():
    """编码一个心跳消息"""
    return encode(HEARTBEAT, 0, {})
