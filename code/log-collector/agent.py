import socket
import time
import threading
import os
import json


class LogAgent:
    """日志采集 Agent：文件 tail + TCP 批量发送"""

    def __init__(self, server_host='127.0.0.1', server_port=8800, batch_size=10):
        self.server_host = server_host
        self.server_port = server_port
        self.batch_size = batch_size
        self._running = False

    def watch_file(self, filepath, interval=0.5):
        """监控文件：类似 tail -f"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")

        with open(filepath, 'r') as f:
            f.seek(0, 2)  # 跳到末尾
            batch = []
            while self._running:
                line = f.readline()
                if line:
                    batch.append(line.rstrip())
                    if len(batch) >= self.batch_size:
                        self._send_batch(batch)
                        batch = []
                else:
                    if batch:
                        self._send_batch(batch)
                        batch = []
                    time.sleep(interval)

    def send_line(self, line):
        """发送单行日志"""
        self._send_batch([line])

    def _send_batch(self, lines):
        """批量发送到 TCP 服务器"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.server_host, self.server_port))
            data = json.dumps({'logs': lines}) + '\n'
            sock.sendall(data.encode())
            sock.close()
        except Exception as e:
            print(f"⚠️ 发送失败: {e}")

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
