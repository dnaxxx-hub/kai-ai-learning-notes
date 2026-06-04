"""路由系统"""
import re
from typing import Callable


class Route:
    def __init__(self, method: str, pattern: str, handler: Callable):
        self.method = method.upper()
        # 将 /users/:id 转换为正则 /users/([^/]+)
        self.pattern = re.sub(r':(\w+)', r'(?P<\1>[^/]+)', pattern)
        self.regex = re.compile(f"^{self.pattern}$")
        self.handler = handler


class Router:
    def __init__(self):
        self.routes: list[Route] = []

    def get(self, pattern: str):
        """GET 路由装饰器"""
        def decorator(handler):
            self.routes.append(Route("GET", pattern, handler))
            return handler
        return decorator

    def post(self, pattern: str):
        """POST 路由装饰器"""
        def decorator(handler):
            self.routes.append(Route("POST", pattern, handler))
            return handler
        return decorator

    def put(self, pattern: str):
        return self._route("PUT", pattern)

    def delete(self, pattern: str):
        return self._route("DELETE", pattern)

    def _route(self, method: str, pattern: str):
        def decorator(handler):
            self.routes.append(Route(method, pattern, handler))
            return handler
        return decorator

    def resolve(self, method: str, path: str) -> tuple:
        """解析请求，返回 (handler, params) 或 None"""
        for route in self.routes:
            if route.method != method.upper():
                continue
            match = route.regex.match(path)
            if match:
                return route.handler, match.groupdict()
        return None, {}
