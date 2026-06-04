"""demo.py — RPC 框架演示"""

from server import RPCServer, RPCService
from client import RPCClient, RemoteServiceProxy
from registry import ServiceRegistry
import threading
import time


# 定义数学服务
class MathService(RPCService):
    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

    def subtract(self, a, b):
        return a - b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("除数不能为 0")
        return a / b

    def power(self, a, b):
        return a ** b

    def echo(self, msg):
        return f"Echo: {msg}"


# 定义字符串服务
class StringService(RPCService):
    def concat(self, a, b):
        return a + b

    def upper(self, s):
        return s.upper()

    def length(self, s):
        return len(s)


def main():
    print("=" * 50)
    print("RPC 框架演示")
    print("=" * 50)

    registry = ServiceRegistry()

    # 启动 MathService 服务器
    def run_math_server():
        server = RPCServer(
            host='127.0.0.1', port=9091,
            service_name='MathService', registry=registry
        )
        server.register_service(MathService(), 'MathService')
        server.start()

    t = threading.Thread(target=run_math_server, daemon=True)
    t.start()
    time.sleep(0.3)

    # 启动 StringService 服务器
    def run_string_server():
        server = RPCServer(
            host='127.0.0.1', port=9092,
            service_name='StringService', registry=registry
        )
        server.register_service(StringService(), 'StringService')
        server.start()

    t2 = threading.Thread(target=run_string_server, daemon=True)
    t2.start()
    time.sleep(0.3)

    # --- MathService 客户端 ---
    print("\n📐 MathService 调用:")
    client1 = RPCClient(registry=registry, host='127.0.0.1', port=9091)
    client1.connect('MathService')

    # 直接调用
    r1 = client1.call('MathService', 'add', [3, 4])
    print(f"  3 + 4 = {r1}")

    r2 = client1.call('MathService', 'multiply', [5, 6])
    print(f"  5 × 6 = {r2}")

    # 代理模式
    math = RemoteServiceProxy(client1, 'MathService')
    print(f"  10 - 3 = {math.subtract(10, 3)}")
    print(f"  20 / 4 = {math.divide(20, 4)}")
    print(f"  2 ^ 10 = {math.power(2, 10)}")
    print(f"  {math.echo('Hello RPC!')}")

    # 错误处理
    try:
        math.divide(1, 0)
    except RuntimeError as e:
        print(f"  错误捕获: {e}")

    client1.close()

    # --- StringService 客户端 ---
    print("\n🔤 StringService 调用:")
    client2 = RPCClient(registry=registry, host='127.0.0.1', port=9092)
    client2.connect('StringService')

    str_svc = RemoteServiceProxy(client2, 'StringService')
    print(f"  Hello + World = {str_svc.concat('Hello', ' World')}")
    print(f"  hello.upper() = {str_svc.upper('hello')}")
    print(f"  'RPC'.length = {str_svc.length('RPC')}")

    client2.close()

    # --- 注册中心状态 ---
    print("\n📋 注册中心状态:")
    services = registry.list_services()
    for name, info in services.items():
        print(f"  {name}: {info['host']}:{info['port']} (active)")

    print("\n✅ 演示完成!")


if __name__ == '__main__':
    main()
