"""service.py — 服务基类 + 装饰器"""

import inspect


class RPCServiceMeta(type):
    """元类，自动收集服务方法"""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # 收集非私有、可调用的方法
        methods = {}
        for attr_name in dir(cls):
            if attr_name.startswith('_'):
                continue
            attr = getattr(cls, attr_name, None)
            if callable(attr) and not isinstance(attr, type):
                # 如果是绑定的方法（在实例上），取底层函数
                if hasattr(attr, '__func__'):
                    attr = attr.__func__
                methods[attr_name] = attr
        cls._rpc_methods = methods
        return cls


class RPCService(metaclass=RPCServiceMeta):
    """RPC 服务基类

    子类继承后，所有公开方法自动注册为 RPC 方法。
    可以使用 @rpc_method 装饰器为方法添加元数据。
    """
    _rpc_methods = {}

    @classmethod
    def get_rpc_methods(cls):
        """获取所有 RPC 方法"""
        return cls._rpc_methods


def rpc_method(func):
    """RPC 方法装饰器

    可用于显式标记 RPC 方法，并附加元数据。
    """
    func._is_rpc = True
    return func


class EchoService(RPCService):
    """示例：回声服务"""

    def echo(self, message):
        return f"Echo: {message}"

    def reverse(self, message):
        return message[::-1]
