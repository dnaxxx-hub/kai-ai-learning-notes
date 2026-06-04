"""
demo.py — 聊天室演示脚本
自动启动服务器和两个客户端进行交互演示
"""

import socket
import time
import threading
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import ChatServer
from protocol import pack, parse_stream


def _recv_all(sock, timeout=2.0):
    """接收所有可用消息"""
    sock.settimeout(timeout)
    buf = b''
    msgs = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while True:
            if len(buf) >= 4:
                length = int.from_bytes(buf[:4], 'big')
                if len(buf) < 4 + length:
                    break
                body = buf[4:4 + length]
                buf = buf[4 + length:]
                msgs.append(json.loads(body.decode('utf-8')))
                continue
            break
        if msgs:
            break
        try:
            data = sock.recv(4096)
            if not data:
                break
            buf += data
        except socket.timeout:
            break
    return msgs


def demo():
    print("=" * 50)
    print("🖥️  终端聊天室演示")
    print("=" * 50)

    # 启动服务器
    server = ChatServer(host='127.0.0.1', port=0)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    port = server.server_sock.getsockname()[1]
    print(f"\n🟢 服务器启动 -> 127.0.0.1:{port}\n")

    # 创建两个客户端
    sock_a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_a.connect(('127.0.0.1', port))

    sock_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_b.connect(('127.0.0.1', port))

    def show(name, msgs):
        for m in msgs:
            t = m.get('type', '')
            if t == 'system':
                print(f"  [{name}] [系统] {m['msg']}")
            elif t == 'join':
                print(f"  [{name}] 🟢 {m['nick']} 进入聊天室")
            elif t == 'leave':
                print(f"  [{name}] 🔴 {m['nick']} 离开聊天室")
            elif t == 'chat':
                print(f"  [{name}] [{m['nick']}] {m['msg']}")

    # 用户A登录
    print("--- 用户 Alice 连接 ---")
    msgs = _recv_all(sock_a)
    show('A', msgs)
    sock_a.sendall(pack({'msg': 'Alice'}))
    time.sleep(0.1)
    msgs = _recv_all(sock_a)
    show('A', msgs)

    # 用户B登录
    print("\n--- 用户 Bob 连接 ---")
    msgs = _recv_all(sock_b)
    show('B', msgs)
    sock_b.sendall(pack({'msg': 'Bob'}))
    time.sleep(0.2)
    msgs_a = _recv_all(sock_a)
    msgs_b = _recv_all(sock_b)
    show('A', msgs_a)
    show('B', msgs_b)

    # Alice 发送消息
    print("\n--- Alice 发送消息 ---")
    sock_a.sendall(pack({'type': 'chat', 'msg': '大家好！'}))
    time.sleep(0.1)
    msgs_a = _recv_all(sock_a)
    msgs_b = _recv_all(sock_b)
    show('A', msgs_a)
    show('B', msgs_b)

    # Bob 发送消息
    print("\n--- Bob 发送消息 ---")
    sock_b.sendall(pack({'type': 'chat', 'msg': '你好 Alice!'}))
    time.sleep(0.1)
    msgs_a = _recv_all(sock_a)
    msgs_b = _recv_all(sock_b)
    show('A', msgs_a)
    show('B', msgs_b)

    # Alice 查询在线列表
    print("\n--- Alice 查询在线列表 ---")
    sock_a.sendall(pack({'type': 'chat', 'msg': '/list'}))
    time.sleep(0.1)
    msgs = _recv_all(sock_a)
    show('A', msgs)

    # Bob 改昵称
    print("\n--- Bob 改昵称 ---")
    sock_b.sendall(pack({'type': 'chat', 'msg': '/nick Robert'}))
    time.sleep(0.2)
    msgs_a = _recv_all(sock_a)
    msgs_b = _recv_all(sock_b)
    show('A', msgs_a)
    show('B', msgs_b)

    # Bob 退出
    print("\n--- Bob 退出 ---")
    sock_b.sendall(pack({'type': 'chat', 'msg': '/quit'}))
    sock_b.close()
    time.sleep(0.3)
    msgs_a = _recv_all(sock_a)
    show('A', msgs_a)

    # 清理
    sock_a.close()
    server._running = False
    server.shutdown()
    print("\n" + "=" * 50)
    print("✅ 演示结束")
    print("=" * 50)


if __name__ == '__main__':
    demo()
