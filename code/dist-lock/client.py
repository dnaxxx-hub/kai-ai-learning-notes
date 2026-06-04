import socket
import sys
import json


class LockClient:
    def __init__(self, host='127.0.0.1', port=8600):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(None)

    def send_command(self, cmd, *args):
        if self.sock is None:
            self.connect()
        line = ' '.join([cmd] + list(args)) + '\n'
        self.sock.sendall(line.encode())
        data = self.sock.recv(65536)
        return json.loads(data.decode('utf-8').strip())

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def lock(self, name='default', lock_type='mutex', timeout=None):
        args = [name, lock_type]
        if timeout is not None:
            args.append(str(timeout))
        return self.send_command('LOCK', *args)

    def rlock(self, name='default', timeout=None):
        args = [name]
        if timeout is not None:
            args.append(str(timeout))
        return self.send_command('RLOCK', *args)

    def wlock(self, name='default', timeout=None):
        args = [name]
        if timeout is not None:
            args.append(str(timeout))
        return self.send_command('WLOCK', *args)

    def unlock(self, name='default', mode=None):
        args = [name]
        if mode:
            args.append(mode)
        return self.send_command('UNLOCK', *args)

    def status(self, name=None):
        args = [name] if name else []
        return self.send_command('STATUS', *args)

    def list_locks(self):
        return self.send_command('LIST')

    def help(self):
        return self.send_command('HELP')


def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <command> [args...]")
        print("Commands: lock, rlock, wlock, unlock, status, list, help")
        sys.exit(1)

    client = LockClient()
    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == 'lock':
            result = client.lock(*args)
        elif cmd == 'rlock':
            result = client.rlock(*args)
        elif cmd == 'wlock':
            result = client.wlock(*args)
        elif cmd == 'unlock':
            result = client.unlock(*args)
        elif cmd == 'status':
            result = client.status(*args)
        elif cmd == 'list':
            result = client.list_locks()
        elif cmd == 'help':
            result = client.help()
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()
