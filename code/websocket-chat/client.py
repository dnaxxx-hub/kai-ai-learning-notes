"""WebSocket 聊天客户端 - RFC 6455"""

import socket
import threading
import base64
import os
import struct
import json
import sys

from frame import decode_frame


def encode_frame(payload, opcode=0x1, mask=True):
    """编码 WebSocket 帧 (客户端必须 mask)"""
    frame = bytearray()
    frame.append(0x80 | opcode)

    length = len(payload)
    if length < 126:
        frame.append((0x80 if mask else 0x00) | length)
    elif length < 65536:
        frame.append((0x80 if mask else 0x00) | 126)
        frame.extend(struct.pack('!H', length))
    else:
        frame.append((0x80 if mask else 0x00) | 127)
        frame.extend(struct.pack('!Q', length))

    if mask:
        mask_key = os.urandom(4)
        frame.extend(mask_key)
        frame.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
    else:
        frame.extend(payload)

    return bytes(frame)


class WSClient:
    def __init__(self, host='127.0.0.1', port=8765):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.running = True
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f'GET / HTTP/1.1\r\n'
            f'Host: localhost\r\n'
            f'Upgrade: websocket\r\n'
            f'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\n'
            f'Sec-WebSocket-Version: 13\r\n\r\n'
        )
        self.sock.sendall(request.encode())
        response = self.sock.recv(4096).decode('utf-8', errors='ignore')
        if '101' not in response:
            raise Exception(f"握手失败: {response[:100]}")

    def send(self, text):
        self.sock.sendall(encode_frame(text.encode(), opcode=0x1, mask=True))

    def start(self):
        recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        recv_thread.start()

        try:
            while self.running:
                text = input()
                if text.strip() == '/quit':
                    self.send('/quit')
                    break
                self.send(text)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            self.running = False
            self.sock.close()

    def _recv_loop(self):
        buffer = b''
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data
                while True:
                    frame, remaining = decode_frame(buffer)
                    if frame is None:
                        break
                    buffer = remaining
                    self._handle_frame(frame)
            except Exception:
                break

    def _handle_frame(self, frame):
        if frame['opcode'] == 0x1:  # Text
            try:
                msg = json.loads(frame['payload'].decode('utf-8'))
            except json.JSONDecodeError:
                return
            type_ = msg.get('type', '')
            if type_ == 'system':
                print(f"[系统] {msg['msg']}")
            elif type_ == 'chat':
                print(f"[{msg['nick']}] {msg['msg']}")
