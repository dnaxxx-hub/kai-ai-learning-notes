"""TCP 服务器 - selectors 多路复用"""
import socket
import selectors

from resp import decode_request, encode_value, encode_error
from store import Store
from commands import CommandHandler


class RedisServer:
    def __init__(self, host='0.0.0.0', port=6379):
        self.host = host
        self.port = port
        self.store = Store()
        self.handler = CommandHandler(self.store)
        self.selector = selectors.DefaultSelector()
        self.buffers = {}  # {fd: bytes}
    
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(100)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"\U0001f7e2 Mini Redis on {self.host}:{self.port}")
        self._run()
    
    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.selector.register(conn, selectors.EVENT_READ, self._read)
        print(f"  \U0001f500 连接: {addr}")
    
    def _read(self, conn, mask):
        try:
            data = conn.recv(65536)
            if not data:
                self._disconnect(conn)
                return
        except Exception:
            self._disconnect(conn)
            return
        
        buf = self.buffers.get(conn.fileno(), b'')
        buf += data
        self.buffers[conn.fileno()] = buf
        
        # 尝试解析所有完整的请求
        while True:
            # 保存当前缓冲区长度，用于检测是否推进
            orig_buf = buf
            
            cmd = decode_request(buf)
            if cmd is None:
                break  # 没有完整请求
            
            # 计算这个请求消耗了多少字节
            # 方法是：重新解析并追踪剩余
            from resp import decode as resp_decode
            _, remaining = resp_decode(buf)
            
            consumed = len(buf) - len(remaining)
            buf = remaining
            self.buffers[conn.fileno()] = buf
            
            if consumed == 0:
                break  # 异常保护
            
            try:
                cmd_name = cmd[0].upper() if isinstance(cmd[0], str) else cmd[0]
                result = self.handler.execute(cmd_name, cmd[1:])
                conn.sendall(encode_value(result))
            except ValueError as e:
                conn.sendall(encode_error(str(e)))
            except Exception as e:
                conn.sendall(encode_error(str(e)))
    
    def _disconnect(self, conn):
        fd = conn.fileno()
        if fd in self.buffers:
            del self.buffers[fd]
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass
    
    def _run(self):
        try:
            while True:
                events = self.selector.select()
                for key, _mask in events:
                    callback = key.data
                    callback(key.fileobj, _mask)
        except KeyboardInterrupt:
            print("\n\U0001f6d1 服务器关闭")
        finally:
            self.selector.close()
