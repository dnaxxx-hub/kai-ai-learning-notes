import subprocess
import sys
import time


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py server")
        print("  python main.py create <path> [data]")
        print("  python main.py get <path>")
        print("  python main.py set <path> <data>")
        print("  python main.py delete <path>")
        print("  python main.py children <path>")
        print("  python main.py exists <path>")
        print("  python main.py stat <path>")
        print("  python main.py watch <path> [event]")
        print("  python main.py ping")
        return

    cmd = sys.argv[1].lower()

    if cmd == 'server':
        from server import ZKServer

        host = sys.argv[2] if len(sys.argv) > 2 else '0.0.0.0'
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 2181
        server = ZKServer(host, port)
        server.start()

    elif cmd == 'test':
        import unittest
        from test_zk import TestZNode, TestZNodeTree, TestWatcher, TestSession

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for tc in [TestZNode, TestZNodeTree, TestWatcher, TestSession]:
            tests = loader.loadTestsFromTestCase(tc)
            suite.addTests(tests)
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)

    else:
        from client import ZKClient

        host = '127.0.0.1'
        port = 2181
        # Try to parse -h and -p flags
        extra_args = sys.argv[2:]
        path_args = []
        i = 0
        while i < len(extra_args):
            if extra_args[i] == '-h' and i + 1 < len(extra_args):
                host = extra_args[i + 1]
                i += 2
            elif extra_args[i] == '-p' and i + 1 < len(extra_args):
                port = int(extra_args[i + 1])
                i += 2
            else:
                path_args.append(extra_args[i])
                i += 1

        client = ZKClient(host, port)
        try:
            client.connect()

            if cmd == 'create':
                path = path_args[0] if len(path_args) > 0 else '/'
                data = path_args[1] if len(path_args) > 1 else ''
                result = client.create(path, data)
                print(result)

            elif cmd == 'get':
                path = path_args[0] if len(path_args) > 0 else '/'
                result = client.get(path)
                print(result)

            elif cmd == 'set':
                path = path_args[0] if len(path_args) > 0 else '/'
                data = path_args[1] if len(path_args) > 1 else ''
                result = client.set(path, data)
                print(result)

            elif cmd == 'delete':
                path = path_args[0] if len(path_args) > 0 else '/'
                result = client.delete(path)
                print(result)

            elif cmd == 'children':
                path = path_args[0] if len(path_args) > 0 else '/'
                result = client.children(path)
                print(result)

            elif cmd == 'exists':
                path = path_args[0] if len(path_args) > 0 else '/'
                result = client.exists(path)
                print(result)

            elif cmd == 'stat':
                path = path_args[0] if len(path_args) > 0 else '/'
                result = client.stat(path)
                print(result)

            elif cmd == 'watch':
                path = path_args[0] if len(path_args) > 0 else '/'
                event = path_args[1] if len(path_args) > 1 else 'data_changed'
                client.watch(path, event)
                # Keep listening for watch events
                print(f"Watching {path} for {event} events...")
                while True:
                    resp = client._recv()
                    if resp:
                        print(resp)
                    time.sleep(0.1)

            elif cmd == 'ping':
                result = client.ping()
                print(result)

            else:
                print(f"Unknown command: {cmd}")
        finally:
            client.close()


if __name__ == '__main__':
    main()
