"""CLI 客户端"""
import socket


class RedisClient:
    def __init__(self, host='127.0.0.1', port=6379):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((host, port))
    
    def execute(self, *args):
        from resp import encode_array, decode
        cmd = encode_array(list(args))
        self.sock.sendall(cmd)
        # 读取响应
        data = b''
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                val, remaining = decode(data)
                if remaining == b'':
                    return val
            except socket.timeout:
                break
            except Exception:
                continue
        return None
    
    def close(self):
        self.sock.close()
