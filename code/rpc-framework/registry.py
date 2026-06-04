"""registry.py — 服务注册中心（本地 + 心跳健康检查）"""

import time
import threading


class ServiceRegistry:
    """服务注册中心

    维护服务实例的注册信息，支持：
    - 服务注册/注销
    - 服务发现
    - 心跳更新
    - 健康检查（过期服务标记为 inactive）
    - 方法注册/查找
    """

    def __init__(self):
        self._services = {}   # {service_name: ServiceInfo}
        self._methods = {}    # {service_name: {method_name: handler}}
        self._lock = threading.Lock()

    def register(self, name, host='0.0.0.0', port=0):
        """注册服务"""
        with self._lock:
            self._services[name] = {
                'host': host,
                'port': port,
                'last_heartbeat': time.time(),
                'status': 'active',
            }
            if name not in self._methods:
                self._methods[name] = {}

    def unregister(self, name):
        """注销服务"""
        with self._lock:
            self._services.pop(name, None)
            self._methods.pop(name, None)

    def heartbeat(self, name):
        """更新服务心跳时间戳

        Returns:
            bool: 服务存在并更新成功返回 True，否则 False
        """
        with self._lock:
            if name in self._services:
                self._services[name]['last_heartbeat'] = time.time()
                self._services[name]['status'] = 'active'
                return True
            return False

    def discover(self, name):
        """服务发现

        返回 active 状态的服务信息，或 None（服务不存在或 inactive）。
        """
        with self._lock:
            svc = self._services.get(name)
            if svc and svc['status'] == 'active':
                return dict(svc)
            return None

    def list_services(self):
        """列出所有 active 的服务"""
        with self._lock:
            return {k: dict(v) for k, v in self._services.items()
                    if v['status'] == 'active'}

    def register_method(self, service_name, method_name, handler):
        """注册服务方法"""
        with self._lock:
            if service_name not in self._methods:
                self._methods[service_name] = {}
            self._methods[service_name][method_name] = handler

    def get_method(self, service_name, method_name):
        """获取服务方法处理器"""
        with self._lock:
            svc = self._methods.get(service_name, {})
            return svc.get(method_name)

    def check_health(self, timeout=15):
        """检查过期服务，将超时未心跳的服务标记为 inactive

        Args:
            timeout: 超时阈值（秒），默认 15 秒

        Returns:
            list: 被标记为 inactive 的服务名列表
        """
        now = time.time()
        with self._lock:
            expired = [
                name
                for name, svc in self._services.items()
                if now - svc['last_heartbeat'] > timeout
            ]
            for name in expired:
                self._services[name]['status'] = 'inactive'
            return expired
