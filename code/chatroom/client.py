"""
client.py — 聊天客户端 (双线程：输入+接收)
"""

import socket
import threading
import json
import struct
import os
import sys

from protocol import pack, parse_stream


class ChatClient:
    def __init__(self, host='127.0.0.1', port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.running = True
        self.lock = threading.Lock()

    def start(self):
        """启动客户端，在连接建立前输入昵称"""
        # 输入昵称
        nick = input("昵称: ").strip()
        if not nick:
            nick = f"User_{os.getpid()}"
        self._send({'msg': nick})

        # 启动接收线程
        recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        recv_thread.start()

        try:
            while self.running:
                try:
                    text = input()
                except (EOFError, KeyboardInterrupt):
                    break
                if not self.running:
                    break
                text = text.strip()
                if text == '/quit':
                    self._send({'type': 'chat', 'msg': '/quit'})
                    self.running = False
                    break
                self._send({'type': 'chat', 'msg': text})
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self._cleanup()

    def _recv_loop(self):
        """后台线程：持续接收服务端消息"""
        buffer = b''
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data
                messages, buffer = parse_stream(buffer)
                for msg in messages:
                    self._display(msg)
            except (OSError, ConnectionError):
                break
            except Exception:
                break
        with self.lock:
            self.running = False

    def _display(self, msg):
        """显示接收到的消息"""
        type_ = msg.get('type', '')
        try:
            if type_ == 'system':
                print(f"[系统] {msg['msg']}")
            elif type_ == 'chat':
                print(f"[{msg['nick']}] {msg['msg']}")
            elif type_ == 'join':
                print(f"🟢 {msg['nick']} 进入聊天室")
            elif type_ == 'leave':
                print(f"🔴 {msg['nick']} 离开聊天室")
        except Exception:
            pass

    def _send(self, msg):
        """发送消息到服务端"""
        try:
            self.sock.sendall(pack(msg))
        except (OSError, ConnectionError):
            with self.lock:
                self.running = False

    def _cleanup(self):
        """清理资源"""
        try:
            self.sock.close()
        except Exception:
            pass
        with self.lock:
            self.running = False


def run_client(host='127.0.0.1', port=9999):
    client = ChatClient(host=host, port=port)
    client.start()
