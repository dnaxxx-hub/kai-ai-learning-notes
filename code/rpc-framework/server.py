"""server.py — RPC 服务器（多线程处理）"""

import socket
import threading
import time
from codec import decode, make_response, make_heartbeat
from registry import ServiceRegistry


class RPCService:
    """服务基类"""
    _methods = {}

    @classmethod
    def method(cls, func):
        cls._methods[func.__name__] = func
        return func


class RPCServer:
    """RPC 服务器

    多线程 TCP 服务器，支持：
    - 多服务注册
    - 自动方法发现
    - 心跳维护
    - 异常处理
    """

    def __init__(self, host='0.0.0.0', port=0, service_name='default',
                 registry=None):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.registry = registry or ServiceRegistry()
        self._services = {}   # {service_name: rpc_service_instance}
        self._running = False
        self._sock = None
        self._threads = []

    def register_service(self, instance, name=None):
        """注册服务实例

        自动发现实例上所有公开方法并注册到注册中心。

        Args:
            instance: 服务实例
            name: 服务名称，默认为类名
        """
        name = name or instance.__class__.__name__
        self._services[name] = instance

        # 注册方法：检查 _rpc_methods（来自元类）或 dir()
        methods = {}
        if hasattr(instance, '_rpc_methods'):
            methods = instance._rpc_methods
        else:
            for method_name in dir(instance):
                if method_name.startswith('_'):
                    continue
                attr = getattr(instance, method_name, None)
                if callable(attr):
                    methods[method_name] = attr

        for method_name, method in methods.items():
            self.registry.register_method(name, method_name, method)

    def start(self):
        """启动服务器"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self.port = self._sock.getsockname()[1]
        self._sock.listen(20)
        self._sock.settimeout(1.0)
        self._running = True

        # 注册到注册中心
        self.registry.register(self.service_name, self.host, self.port)

        # 心跳线程
        hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb_thread.start()

        print(f"🟢 RPC Server {self.service_name} on {self.host}:{self.port}")

        while self._running:
            try:
                conn, addr = self._sock.accept()
                t = threading.Thread(
                    target=self._handle_client, args=(conn, addr), daemon=True
                )
                t.start()
                self._threads.append(t)
            except socket.timeout:
                continue
            except OSError:
                break

    def stop(self):
        """停止服务器"""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def _handle_client(self, conn, addr):
        """处理客户端连接"""
        buffer = b''
        while self._running:
            try:
                data = conn.recv(65536)
                if not data:
                    break
                buffer += data

                while True:
                    msg, buffer = decode(buffer)
                    if msg is None:
                        break

                    if msg.msg_type == 0:      # 请求
                        response = self._process_request(msg)
                        conn.sendall(response)
                    elif msg.msg_type == 2:    # 心跳
                        conn.sendall(make_heartbeat())
            except (OSError, ConnectionError):
                break
        conn.close()

    def _process_request(self, msg):
        """处理 RPC 请求"""
        body = msg.body
        service_name = body.get('service', self.service_name)
        method_name = body.get('method', '')
        args = body.get('args', [])
        kwargs = body.get('kwargs', {})

        try:
            handler = self.registry.get_method(service_name, method_name)
            if handler is None:
                raise ValueError(
                    f"方法 {service_name}.{method_name} 不存在"
                )
            result = handler(*args, **kwargs)
            return make_response(msg.msg_id, result=result)
        except Exception as e:
            return make_response(msg.msg_id, error=str(e))

    def _heartbeat_loop(self):
        """心跳更新循环"""
        while self._running:
            self.registry.heartbeat(self.service_name)
            time.sleep(5)
