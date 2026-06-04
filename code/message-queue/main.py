"""Message Queue - 入口"""
import sys
import os

# 确保导入路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import MQServer
from client import MQClient


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python main.py server")
        print("  python main.py declare-queue <name> [--durable]")
        print("  python main.py declare-exchange <name> [--type direct|topic|fanout|headers]")
        print("  python main.py bind <queue> <exchange> [routing_key]")
        print("  python main.py publish <json_args>")
        print("  python main.py status")
        return

    cmd = sys.argv[1]

    if cmd == 'server':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5672
        server = MQServer(port=port)
        server.start()

    else:
        client = MQClient()
        client.connect()
        try:
            if cmd == 'declare-queue':
                name = sys.argv[2]
                durable = '--durable' in sys.argv
                res = client.declare_queue(name, durable)
                print(res)

            elif cmd == 'declare-exchange':
                name = sys.argv[2]
                etype = 'direct'
                if len(sys.argv) > 3:
                    etype = sys.argv[3]
                if etype.startswith('--type='):
                    etype = etype.split('=', 1)[1]
                elif len(sys.argv) > 4 and sys.argv[3] == '--type':
                    etype = sys.argv[4]
                res = client.declare_exchange(name, etype)
                print(res)

            elif cmd == 'bind':
                queue = sys.argv[2]
                exchange = sys.argv[3]
                routing_key = sys.argv[4] if len(sys.argv) > 4 else ''
                res = client.bind(queue, exchange, routing_key)
                print(res)

            elif cmd == 'publish':
                import json as _json
                args = _json.loads(' '.join(sys.argv[2:]))
                body = args.get('body', '')
                exchange = args.get('exchange', '')
                routing_key = args.get('routing_key', '')
                persistent = args.get('persistent', False)
                res = client.publish(body, exchange, routing_key,
                                     persistent=persistent)
                print(res)

            elif cmd == 'status':
                res = client.status()
                print(json.dumps(res, indent=2, ensure_ascii=False))

            else:
                print(f"未知命令: {cmd}")

        finally:
            client.close()


if __name__ == '__main__':
    main()
