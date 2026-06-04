"""test_rpc.py — RPC 框架单元测试（18+ 测试用例）"""

import unittest
import time
import socket
import struct
import threading
import json

from codec import (
    encode, decode, decode_all, make_request, make_response, make_heartbeat,
    RPCMessage, HEADER_SIZE, REQUEST, RESPONSE, HEARTBEAT
)
from registry import ServiceRegistry
from server import RPCServer, RPCService
from client import RPCClient, RemoteServiceProxy


# ============================================================
# 1. 编解码测试
# ============================================================

class TestCodecRequest(unittest.TestCase):
    """测试 1: 请求消息编码/解码"""

    def test_encode_decode_request(self):
        data = make_request(msg_id=42, service='Math', method='add',
                            args=[3, 4])
        msg, remaining = decode(data)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, REQUEST)
        self.assertEqual(msg.msg_id, 42)
        self.assertEqual(msg.body['service'], 'Math')
        self.assertEqual(msg.body['method'], 'add')
        self.assertEqual(msg.body['args'], [3, 4])
        self.assertEqual(msg.body['kwargs'], {})
        self.assertEqual(remaining, b'')


class TestCodecResponse(unittest.TestCase):
    """测试 2: 响应消息编码/解码"""

    def test_encode_decode_response_success(self):
        data = make_response(msg_id=42, result=7)
        msg, remaining = decode(data)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, RESPONSE)
        self.assertEqual(msg.msg_id, 42)
        self.assertEqual(msg.body['result'], 7)
        self.assertIsNone(msg.body.get('error'))

    def test_encode_decode_response_error(self):
        data = make_response(msg_id=1, error="Division by zero")
        msg, remaining = decode(data)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, RESPONSE)
        self.assertEqual(msg.body['error'], "Division by zero")


class TestCodecHeartbeat(unittest.TestCase):
    """测试 3: 心跳消息编码/解码"""

    def test_encode_decode_heartbeat(self):
        data = make_heartbeat()
        msg, remaining = decode(data)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, HEARTBEAT)
        self.assertEqual(msg.msg_id, 0)
        self.assertEqual(msg.body, {})


class TestCodecHeader(unittest.TestCase):
    """测试 4: 协议格式验证 (header size)"""

    def test_header_size(self):
        self.assertEqual(HEADER_SIZE, 9)
        for i in range(10):
            data = make_request(i, 'Svc', 'method')
            self.assertEqual(len(data), HEADER_SIZE + len(
                json.dumps({
                    'service': 'Svc', 'method': 'method',
                    'args': [], 'kwargs': {},
                }).encode('utf-8')
            ))

    def test_header_structure(self):
        data = make_request(msg_id=7, service='Test', method='go')
        total_len = struct.unpack('!I', data[:4])[0]
        self.assertEqual(total_len, len(data), "总长度应对应实际数据总长度")
        self.assertEqual(data[4], REQUEST)
        self.assertEqual(struct.unpack('!I', data[5:9])[0], 7)


class TestCodecIncompleteFrame(unittest.TestCase):
    """测试 5: 不完整帧处理"""

    def test_empty_data(self):
        msg, remaining = decode(b'')
        self.assertIsNone(msg)
        self.assertEqual(remaining, b'')

    def test_partial_header(self):
        msg, remaining = decode(b'\x00\x00')
        self.assertIsNone(msg)
        self.assertEqual(remaining, b'\x00\x00')

    def test_partial_body(self):
        data = make_request(1, 'Svc', 'method')
        # 只发送部分数据
        partial = data[:HEADER_SIZE + 1]
        msg, remaining = decode(partial)
        self.assertIsNone(msg)

    def test_exactly_header(self):
        # 只发送 header 部分（9字节）
        header = struct.pack('!IBI', HEADER_SIZE + 2, REQUEST, 1) + b'{}'
        msg, remaining = decode(header[:HEADER_SIZE])
        self.assertIsNone(msg)


class TestCodecStickyPackets(unittest.TestCase):
    """测试 6: 粘包处理"""

    def test_two_requests(self):
        data1 = make_request(1, 'Svc', 'method1')
        data2 = make_request(2, 'Svc', 'method2')
        combined = data1 + data2

        msg1, remaining = decode(combined)
        self.assertIsNotNone(msg1)
        self.assertEqual(msg1.msg_id, 1)
        self.assertEqual(msg1.body['method'], 'method1')

        msg2, remaining = decode(remaining)
        self.assertIsNotNone(msg2)
        self.assertEqual(msg2.msg_id, 2)
        self.assertEqual(msg2.body['method'], 'method2')
        self.assertEqual(remaining, b'')

    def test_three_requests(self):
        msgs = [
            make_request(10, 'A', 'foo'),
            make_request(20, 'B', 'bar'),
            make_request(30, 'C', 'baz'),
        ]
        combined = b''.join(msgs)

        messages, remaining = decode_all(combined)
        self.assertEqual(len(messages), 3)
        self.assertEqual([m.msg_id for m in messages], [10, 20, 30])
        self.assertEqual([m.body['method'] for m in messages],
                         ['foo', 'bar', 'baz'])
        self.assertEqual(remaining, b'')

    def test_mixed_request_and_heartbeat(self):
        data = make_request(1, 'Svc', 'method') + make_heartbeat()
        msgs, remaining = decode_all(data)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].msg_type, REQUEST)
        self.assertEqual(msgs[1].msg_type, HEARTBEAT)


# ============================================================
# 2. 注册中心测试
# ============================================================

class TestRegistryRegister(unittest.TestCase):
    """测试 7: 服务注册"""

    def test_register_service(self):
        reg = ServiceRegistry()
        reg.register('MathService', '127.0.0.1', 9091)
        svc = reg.discover('MathService')
        self.assertIsNotNone(svc)
        self.assertEqual(svc['host'], '127.0.0.1')
        self.assertEqual(svc['port'], 9091)
        self.assertEqual(svc['status'], 'active')

    def test_register_duplicate(self):
        reg = ServiceRegistry()
        reg.register('Svc', '0.0.0.0', 1000)
        reg.register('Svc', '0.0.0.0', 2000)  # 覆盖
        svc = reg.discover('Svc')
        self.assertEqual(svc['port'], 2000)


class TestRegistryDiscover(unittest.TestCase):
    """测试 8: 服务发现"""

    def test_discover_existing(self):
        reg = ServiceRegistry()
        reg.register('Svc', '127.0.0.1', 8080)
        svc = reg.discover('Svc')
        self.assertIsNotNone(svc)

    def test_discover_nonexistent(self):
        reg = ServiceRegistry()
        svc = reg.discover('NoSuchService')
        self.assertIsNone(svc)

    def test_discover_after_unregister(self):
        reg = ServiceRegistry()
        reg.register('Svc', '127.0.0.1', 8080)
        reg.unregister('Svc')
        svc = reg.discover('Svc')
        self.assertIsNone(svc)

    def test_list_services(self):
        reg = ServiceRegistry()
        reg.register('A', '0.0.0.0', 1)
        reg.register('B', '0.0.0.0', 2)
        self.assertEqual(len(reg.list_services()), 2)


class TestRegistryHeartbeat(unittest.TestCase):
    """测试 9: 心跳更新"""

    def test_heartbeat_updates_timestamp(self):
        reg = ServiceRegistry()
        reg.register('Svc', '127.0.0.1', 9090)
        old_ts = reg._services['Svc']['last_heartbeat']
        time.sleep(0.01)
        reg.heartbeat('Svc')
        new_ts = reg._services['Svc']['last_heartbeat']
        self.assertGreater(new_ts, old_ts)

    def test_heartbeat_nonexistent(self):
        reg = ServiceRegistry()
        result = reg.heartbeat('NoSuchService')
        self.assertFalse(result)

    def test_heartbeat_restores_active(self):
        reg = ServiceRegistry()
        reg.register('Svc', '127.0.0.1', 9090)
        reg._services['Svc']['status'] = 'inactive'
        reg.heartbeat('Svc')
        self.assertEqual(reg._services['Svc']['status'], 'active')


class TestRegistryHealthCheck(unittest.TestCase):
    """测试 10: 健康检查过期"""

    def test_health_check_expired(self):
        reg = ServiceRegistry()
        reg.register('Svc1', '0.0.0.0', 1)
        reg.register('Svc2', '0.0.0.0', 2)
        # 强制让 Svc1 过期
        reg._services['Svc1']['last_heartbeat'] = time.time() - 100
        expired = reg.check_health(timeout=10)
        self.assertIn('Svc1', expired)
        self.assertNotIn('Svc2', expired)
        self.assertEqual(reg._services['Svc1']['status'], 'inactive')
        self.assertEqual(reg._services['Svc2']['status'], 'active')

    def test_health_check_no_expired(self):
        reg = ServiceRegistry()
        reg.register('Svc', '0.0.0.0', 1)
        expired = reg.check_health(timeout=100)
        self.assertEqual(expired, [])

    def test_discover_inactive(self):
        reg = ServiceRegistry()
        reg.register('Svc', '0.0.0.0', 1)
        reg._services['Svc']['status'] = 'inactive'
        svc = reg.discover('Svc')
        self.assertIsNone(svc)


# ============================================================
# 3. RPC 服务器 & 客户端测试
# ============================================================

class TestRPCMethodRegistration(unittest.TestCase):
    """测试 11: RPC Server 方法注册"""

    def test_method_registration(self):
        reg = ServiceRegistry()
        server = RPCServer(host='127.0.0.1', port=0, registry=reg)

        class TestService(RPCService):
            def foo(self):
                return 'foo'

            def bar(self, x):
                return x * 2

        server.register_service(TestService(), 'TestService')

        handler = reg.get_method('TestService', 'foo')
        self.assertIsNotNone(handler)
        self.assertEqual(handler(), 'foo')

        handler = reg.get_method('TestService', 'bar')
        self.assertEqual(handler(5), 10)

    def test_method_registration_nonexistent(self):
        reg = ServiceRegistry()
        handler = reg.get_method('NoSvc', 'noMethod')
        self.assertIsNone(handler)


class TestRPCClientConnect(unittest.TestCase):
    """测试 12: RPC Client 连接"""

    def test_client_connect(self):
        reg = ServiceRegistry()
        server_port = [0]

        class SimpleService(RPCService):
            def ping(self):
                return 'pong'

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Simple', registry=reg
            )
            server.register_service(SimpleService(), 'Simple')
            server_port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(
            registry=reg, host='127.0.0.1',
            port=server_port[0]
        )
        client.connect('Simple')
        self.assertIsNotNone(client._sock)
        client.close()


class TestRPCCall(unittest.TestCase):
    """测试 13: RPC 调用 (加法)"""

    def test_add_call(self):
        reg = ServiceRegistry()
        port = [0]

        class CalcService(RPCService):
            def add(self, a, b):
                return a + b

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Calc', registry=reg
            )
            server.register_service(CalcService(), 'Calc')
            port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(registry=reg, host='127.0.0.1', port=port[0])
        client.connect('Calc')
        result = client.call('Calc', 'add', [3, 4])
        self.assertEqual(result, 7)
        result = client.call('Calc', 'add', [100, 200])
        self.assertEqual(result, 300)
        client.close()

    def test_multiply_call(self):
        reg = ServiceRegistry()
        port = [0]

        class CalcService(RPCService):
            def multiply(self, a, b):
                return a * b

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Calc', registry=reg
            )
            server.register_service(CalcService(), 'Calc')
            port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(registry=reg, host='127.0.0.1', port=port[0])
        client.connect('Calc')
        self.assertEqual(client.call('Calc', 'multiply', [5, 6]), 30)
        self.assertEqual(client.call('Calc', 'multiply', [0, 100]), 0)
        self.assertEqual(client.call('Calc', 'multiply', [-2, 3]), -6)
        client.close()


class TestRPCError(unittest.TestCase):
    """测试 14: RPC 调用异常"""

    def test_call_nonexistent_method(self):
        reg = ServiceRegistry()
        port = [0]

        class SimpleService(RPCService):
            def ok(self):
                return True

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Simple', registry=reg
            )
            server.register_service(SimpleService(), 'Simple')
            port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(registry=reg, host='127.0.0.1', port=port[0])
        client.connect('Simple')
        with self.assertRaises(RuntimeError):
            client.call('Simple', 'nonexistent')
        client.close()

    def test_call_method_raises_exception(self):
        reg = ServiceRegistry()
        port = [0]

        class ErrorService(RPCService):
            def crash(self):
                raise ValueError("故意错误")

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Error', registry=reg
            )
            server.register_service(ErrorService(), 'Error')
            port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(registry=reg, host='127.0.0.1', port=port[0])
        client.connect('Error')
        with self.assertRaises(RuntimeError) as ctx:
            client.call('Error', 'crash')
        self.assertIn("故意错误", str(ctx.exception))
        client.close()


class TestRPCTimeout(unittest.TestCase):
    """测试 15: 超时处理"""

    def test_call_timeout(self):
        port = get_free_port()

        class SlowService(RPCService):
            def slow(self):
                time.sleep(5)
                return 'done'

        def run():
            server = RPCServer(
                host='127.0.0.1', port=port,
                service_name='SlowService'
            )
            server.register_service(SlowService(), 'SlowService')
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        # 设置极短超时
        client = RPCClient(host='127.0.0.1', port=port, timeout=1)
        client.connect()
        with self.assertRaises((TimeoutError, ConnectionError)):
            client.call('SlowService', 'slow')
        client.close()

    def test_connect_timeout(self):
        # 连接不存在的地址，应该很快失败
        client = RPCClient(host='127.0.0.1', port=19999, timeout=1)
        with self.assertRaises((socket.timeout, ConnectionRefusedError,
                                ConnectionError, OSError)):
            client.connect()


class TestRPCProxy(unittest.TestCase):
    """测试 16: 代理模式调用"""

    def test_proxy_call(self):
        reg = ServiceRegistry()
        port = [0]

        class GreetService(RPCService):
            def hello(self, name):
                return f"Hello, {name}!"

            def add(self, a, b, c):
                return a + b + c

        def run():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='Greet', registry=reg
            )
            server.register_service(GreetService(), 'Greet')
            port[0] = server.port
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)

        client = RPCClient(registry=reg, host='127.0.0.1', port=port[0])
        client.connect('Greet')

        proxy = RemoteServiceProxy(client, 'Greet')
        self.assertEqual(proxy.hello('World'), 'Hello, World!')
        self.assertEqual(proxy.add(1, 2, 3), 6)

        client.close()


class TestMultiService(unittest.TestCase):
    """测试 17: 多服务注册"""

    def test_multi_service_discovery(self):
        reg = ServiceRegistry()
        port1, port2 = [0], [0]

        class ServiceA(RPCService):
            def get_name(self):
                return 'ServiceA'

        class ServiceB(RPCService):
            def get_name(self):
                return 'ServiceB'

        def run_a():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='ServiceA', registry=reg
            )
            server.register_service(ServiceA(), 'ServiceA')
            port1[0] = server.port
            server.start()

        def run_b():
            server = RPCServer(
                host='127.0.0.1', port=0,
                service_name='ServiceB', registry=reg
            )
            server.register_service(ServiceB(), 'ServiceB')
            port2[0] = server.port
            server.start()

        ta = threading.Thread(target=run_a, daemon=True)
        tb = threading.Thread(target=run_b, daemon=True)
        ta.start()
        tb.start()
        time.sleep(0.5)

        services = reg.list_services()
        self.assertIn('ServiceA', services)
        self.assertIn('ServiceB', services)
        self.assertEqual(len(services), 2)

        # 分别连接两个服务
        client_a = RPCClient(registry=reg, host='127.0.0.1', port=port1[0])
        client_a.connect('ServiceA')
        self.assertEqual(client_a.call('ServiceA', 'get_name'), 'ServiceA')

        client_b = RPCClient(registry=reg, host='127.0.0.1', port=port2[0])
        client_b.connect('ServiceB')
        self.assertEqual(client_b.call('ServiceB', 'get_name'), 'ServiceB')

        client_a.close()
        client_b.close()


# ============================================================
# 额外测试: 更全面的边界覆盖
# ============================================================

class TestCodecEdgeCases(unittest.TestCase):
    """额外测试 18: 编解码边界情况"""

    def test_complex_body(self):
        """嵌套复杂数据结构"""
        data = make_request(1, 'Svc', 'process', kwargs={
            'users': [{'name': 'Alice', 'age': 30},
                      {'name': 'Bob', 'age': 25}],
            'active': True,
            'count': 42,
            'tags': ['a', 'b', 'c'],
        })
        msg, remaining = decode(data)
        self.assertEqual(len(msg.body['kwargs']['users']), 2)
        self.assertTrue(msg.body['kwargs']['active'])

    def test_empty_body(self):
        """空请求体"""
        data = make_request(0, '', '')
        msg, remaining = decode(data)
        self.assertEqual(msg.body['service'], '')
        self.assertEqual(msg.body['args'], [])

    def test_none_result(self):
        """None 返回值"""
        data = make_response(1, result=None)
        msg, remaining = decode(data)
        self.assertIsNone(msg.body.get('result'))

    def test_unicode_body(self):
        """Unicode 字符串"""
        data = make_request(1, 'Svc', 'echo', ['你好，世界！ 🌍'])
        msg, remaining = decode(data)
        self.assertEqual(msg.body['args'][0], '你好，世界！ 🌍')


class TestRegistryEdgeCases(unittest.TestCase):
    """额外测试 19: 注册中心边界"""

    def test_unregister_nonexistent(self):
        reg = ServiceRegistry()
        reg.unregister('NoSuchService')  # 不应抛异常

    def test_register_and_unregister_multiple(self):
        reg = ServiceRegistry()
        for i in range(10):
            reg.register(f'Svc{i}', '0.0.0.0', i)
        self.assertEqual(len(reg.list_services()), 10)
        for i in range(5):
            reg.unregister(f'Svc{i}')
        self.assertEqual(len(reg.list_services()), 5)

    def test_discover_after_heartbeat_timeout(self):
        reg = ServiceRegistry()
        reg.register('Svc', '0.0.0.0', 1)
        reg._services['Svc']['last_heartbeat'] = time.time() - 60
        reg.check_health(timeout=10)
        svc = reg.discover('Svc')
        self.assertIsNone(svc)


class TestServerStop(unittest.TestCase):
    """额外测试 20: 服务器停止"""

    def test_server_start_stop(self):
        reg = ServiceRegistry()
        server = RPCServer(
            host='127.0.0.1', port=0,
            service_name='StopTest', registry=reg
        )

        def run():
            server.start()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.2)

        self.assertTrue(server._running)
        server.stop()
        time.sleep(0.1)
        self.assertFalse(server._running)


# ============================================================
# 辅助函数
# ============================================================

def get_free_port():
    """获取一个可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ============================================================
# 运行
# ============================================================

if __name__ == '__main__':
    unittest.main(verbosity=2)
