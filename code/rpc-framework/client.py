"""client.py — RPC 客户端（动态代理 + 超时重试）"""

import socket
import threading
import time
from codec import encode, decode, make_request


class RPCClient:
    """RPC 客户端

    支持：
    - 服务发现自动连接
    - 线程安全调用
    - 超时控制
    - 自动重试（连接断开时）
    """

    def __init__(self, registry=None, host='127.0.0.1', port=0,
                 timeout=5, max_retries=0):
        self.registry = registry
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self._sock = None
        self._msg_id = 0
        self._lock = threading.Lock()

    def connect(self, service_name=None):
        """连接到 RPC 服务器

        如果提供 service_name 和 registry，自动进行服务发现。

        Args:
            service_name: 可选的 RPC 服务名，用于服务发现

        Returns:
            self
        """
        if service_name and self.registry:
            svc = self.registry.discover(service_name)
            if svc:
                self.host = svc['host']
                self.port = svc['port']

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        return self

    def reconnect(self):
        """重新连接"""
        self.close()
        return self.connect()

    def call(self, service, method, args=None, kwargs=None, timeout=None):
        """调用远程方法

        Args:
            service: 服务名
            method: 方法名
            args: 位置参数列表
            kwargs: 关键字参数字典
            timeout: 超时秒数，默认使用 self.timeout

        Returns:
            方法返回值

        Raises:
            ConnectionError: 未连接
            RuntimeError: 服务端返回错误
            TimeoutError: 调用超时
        """
        with self._lock:
            self._msg_id += 1
            msg_id = self._msg_id

        data = make_request(msg_id, service, method, args, kwargs)
        last_error = None
        retries = self.max_retries + 1

        for attempt in range(retries):
            try:
                if not self._sock:
                    if attempt > 0:
                        self.reconnect()
                    else:
                        raise ConnectionError("未连接")

                self._sock.sendall(data)

                response = b''
                deadline = time.time() + (timeout or self.timeout)
                while time.time() < deadline:
                    try:
                        chunk = self._sock.recv(4096)
                        if not chunk:
                            break
                        response += chunk

                        msg, remaining = decode(response)
                        if msg is not None:
                            if msg.msg_type == 1:   # 响应
                                if msg.body.get('error'):
                                    raise RuntimeError(msg.body['error'])
                                return msg.body.get('result')
                            elif msg.msg_type == 2:  # 心跳
                                response = remaining
                                continue
                    except socket.timeout:
                        break

                raise TimeoutError("RPC 调用超时")

            except (OSError, ConnectionError) as e:
                last_error = e
                self._sock = None
                if attempt < retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # 递增等待
                    continue
                raise ConnectionError(
                    f"RPC 连接失败 (重试{attempt}次): {e}"
                )
            except Exception:
                self._sock = None
                raise

        raise last_error or ConnectionError("RPC 调用失败")

    def close(self):
        """关闭连接"""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


class RemoteServiceProxy:
    """动态远程服务代理

    通过 __getattr__ 动态创建远程调用方法。

    用法:
        client = RPCClient(...)
        client.connect('MathService')
        math = RemoteServiceProxy(client, 'MathService')
        result = math.add(3, 4)  # 远程调用 MathService.add(3, 4)
    """

    def __init__(self, client, service_name):
        self._client = client
        self._service = service_name

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        def call(*args, **kwargs):
            return self._client.call(self._service, name, args, kwargs)

        return call
