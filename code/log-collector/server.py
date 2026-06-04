import json
import socket
import threading
from indexer import LogIndexer
from aggregator import LogAggregator


class LogServer:
    """中心服务器：接收 TCP 日志 + 索引 + 搜索 API"""

    def __init__(self, host='127.0.0.1', port=8800):
        self.host = host
        self.port = port
        self.indexer = LogIndexer()
        self.aggregator = LogAggregator(self.indexer)
        self._running = False

    def handle_client(self, conn, addr):
        """处理客户端连接"""
        try:
            data = b''
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Process complete lines
                while b'\n' in data:
                    line, data = data.split(b'\n', 1)
                    if line.strip():
                        self._process_message(line.decode(), addr)
        except Exception as e:
            pass
        finally:
            conn.close()

    def _process_message(self, msg, addr):
        """处理接收到的消息"""
        try:
            payload = json.loads(msg)
            logs = payload.get('logs', [])
            for log_line in logs:
                self.indexer.index(log_line)
        except (json.JSONDecodeError, Exception):
            pass

    def start(self):
        """启动 TCP 服务器"""
        self._running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.sock.settimeout(1)

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self.sock.accept()
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    def stop(self):
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass

    def search(self, *args, **kwargs):
        return self.indexer.search(*args, **kwargs)

    def stats(self):
        return self.indexer.stats()
