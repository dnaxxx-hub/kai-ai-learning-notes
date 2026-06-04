"""入口"""
import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py [server|client]")
        return
    
    mode = sys.argv[1].lower()
    
    if mode == 'server':
        from server import RedisServer
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 6379
        server = RedisServer(port=port)
        server.start()
    
    elif mode == 'client':
        from client import RedisClient
        host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 6379
        client = RedisClient(host, port)
        print(f"🟢 已连接到 {host}:{port}")
        print("输入命令 (空行退出):")
        try:
            while True:
                line = input('> ').strip()
                if not line:
                    break
                args = line.split()
                result = client.execute(*args)
                print(result)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            client.close()
            print("再见!")
    
    else:
        print(f"未知模式: {mode}")


if __name__ == '__main__':
    main()
