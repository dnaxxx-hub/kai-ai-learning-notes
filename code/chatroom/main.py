"""
main.py — CLI 入口 (启动服务端或客户端)
"""

import sys
import argparse
from server import run_server
from client import run_client


def main():
    parser = argparse.ArgumentParser(description='终端聊天室')
    parser.add_argument(
        'mode',
        choices=['server', 'client'],
        help='server: 启动聊天服务器 | client: 启动聊天客户端'
    )
    parser.add_argument(
        '--host',
        default=None,
        help='主机地址 (server默认0.0.0.0, client默认127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=9999,
        help='端口号 (默认9999)'
    )

    args = parser.parse_args()

    if args.mode == 'server':
        host = args.host or '0.0.0.0'
        print(f"启动聊天服务器 {host}:{args.port}")
        run_server(host=host, port=args.port)
    else:
        host = args.host or '127.0.0.1'
        print(f"连接聊天服务器 {host}:{args.port}")
        run_client(host=host, port=args.port)


if __name__ == '__main__':
    main()
