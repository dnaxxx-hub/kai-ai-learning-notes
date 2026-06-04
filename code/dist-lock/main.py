import sys
import os

# Ensure we can import from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <command> [args...]")
        print("Commands:")
        print("  server          — Start TCP lock server")
        print("  lock <name> [type] [timeout] — Acquire a lock")
        print("  unlock <name> [mode]  — Release a lock")
        print("  rlock <name> [timeout] — Acquire read lock")
        print("  wlock <name> [timeout] — Acquire write lock")
        print("  status [name]   — View lock status")
        print("  list            — List all locks")
        print("  help            — Show help")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'server':
        from server import LockServer
        server = LockServer()
        server.start()
    elif cmd in ('lock', 'unlock', 'rlock', 'wlock', 'status', 'list', 'help'):
        from client import main as client_main
        client_main()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
