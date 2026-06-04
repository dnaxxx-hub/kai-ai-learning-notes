"""WebSocket 聊天演示脚本"""

import threading
import time
import sys

from server import WSChatServer
from client import WSClient


def run_demo():
    """启动服务器和一个客户端进行演示"""
    # 启动服务器
    server = WSChatServer(port=9876)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # 启动客户端
    client = WSClient(port=9876)
    # 发送演示消息
    time.sleep(0.5)
    client.send("大家好！我是演示客户端")
    time.sleep(0.5)
    client.send("/nick 演示君")
    time.sleep(0.5)
    client.send("改名成功！")
    time.sleep(0.5)
    client.send("WebSocket 聊天室演示 🎉")
    time.sleep(0.5)
    client.send("发送 /list 查看在线用户")
    time.sleep(0.5)
    client.running = False
    client.sock.close()
    print("✅ 演示完成")


if __name__ == '__main__':
    print("=" * 50)
    print("WebSocket 聊天室演示")
    print("=" * 50)
    run_demo()
