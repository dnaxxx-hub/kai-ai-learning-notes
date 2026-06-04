import socket, json

class ConfigClient:
    """配置中心 TCP 客户端"""
    
    def __init__(self, host='127.0.0.1', port=8500):
        self.host = host
        self.port = port
    
    def _send(self, command):
        """发送命令并返回解析后的响应"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((self.host, self.port))
            sock.sendall((command + '\n').encode('utf-8'))
            data = sock.recv(65536)
            sock.close()
            if not data:
                return {'ok': False, 'error': 'no response'}
            return json.loads(data.decode('utf-8').strip())
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    
    def put(self, key, value):
        return self._send(f'PUT {key} {value}')
    
    def get(self, key):
        return self._send(f'GET {key}')
    
    def delete(self, key):
        return self._send(f'DEL {key}')
    
    def list_prefix(self, prefix='/'):
        return self._send(f'LIST {prefix}')
    
    def grant(self, ttl=60):
        return self._send(f'GRANT {ttl}')
    
    def keepalive(self, lease_id):
        return self._send(f'KEEPALIVE {lease_id}')
    
    def revoke(self, lease_id):
        return self._send(f'REVOKE {lease_id}')
    
    def attach(self, lease_id, key):
        return self._send(f'ATTACH {lease_id} {key}')
    
    def stats(self):
        return self._send('STATS')
