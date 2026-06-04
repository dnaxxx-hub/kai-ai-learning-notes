"""HTTP Upgrade 握手 - RFC 6455 Section 4"""

import base64
import hashlib

WS_MAGIC = b'258EAFA5-E914-47DA-95CA-5AB9DC91B89B'


def generate_accept_key(key):
    """从 Sec-WebSocket-Key 生成 Sec-WebSocket-Accept"""
    sha1 = hashlib.sha1(key.encode() + WS_MAGIC).digest()
    return base64.b64encode(sha1).decode()


def parse_handshake(request):
    """解析 HTTP Upgrade 请求"""
    lines = request.split('\r\n')
    if not lines:
        return None

    headers = {}
    for line in lines[1:]:
        if ': ' in line:
            k, v = line.split(': ', 1)
            headers[k.lower()] = v

    ws_key = headers.get('sec-websocket-key', '')
    if not ws_key:
        return None

    request_line = lines[0].split()
    if len(request_line) < 2:
        return None

    return {
        'method': request_line[0],
        'path': request_line[1],
        'key': ws_key,
        'version': headers.get('sec-websocket-version', ''),
    }
