"""WebSocket 聊天 CLI 入口"""

import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py [server|client]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == 'server':
        from server import WSChatServer
        server = WSChatServer()
        server.start()
    elif mode == 'client':
        from client import WSClient
        client = WSClient()
        print("🟢 已连接，输入消息发送，输入 /quit 退出，输入 /nick <昵称> 改名")
        client.start()
    else:
        print(f"未知模式: {mode}")
        print("用法: python main.py [server|client]")
        sys.exit(1)


if __name__ == '__main__':
    main()
