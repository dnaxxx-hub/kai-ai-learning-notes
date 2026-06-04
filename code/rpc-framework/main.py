"""main.py — RPC 框架 CLI 入口"""

import argparse
import sys
import threading
import time

from server import RPCServer, RPCService
from client import RPCClient, RemoteServiceProxy
from registry import ServiceRegistry


def cmd_server(args):
    """启动 RPC 服务器"""
    registry = ServiceRegistry()

    # 动态创建服务类
    class DynamicService(RPCService):
        pass

    server = RPCServer(
        host=args.host,
        port=args.port,
        service_name=args.service,
        registry=registry,
    )
    instance = DynamicService()
    server.register_service(instance, args.service)
    server.start()


def cmd_client(args):
    """RPC 客户端模式"""
    registry = ServiceRegistry()
    # 如果提供了地址，手动注册
    if args.host and args.port:
        registry.register(args.service, args.host, int(args.port))

    client = RPCClient(registry=registry, timeout=args.timeout)
    client.connect(args.service)

    proxy = RemoteServiceProxy(client, args.service)

    if args.method:
        # 调用指定方法
        result = getattr(proxy, args.method)(*args.args)
        print(result)
    else:
        print("已连接，交互模式未实现。请使用 --method 指定方法。")

    client.close()


def cmd_demo(args):
    """运行演示"""
    import demo
    demo.main()


def cmd_test(args):
    """运行测试"""
    import unittest
    from test_rpc import TestCodecRequest, TestCodecResponse
    from test_rpc import TestCodecHeartbeat, TestCodecHeader
    from test_rpc import TestCodecIncompleteFrame, TestCodecStickyPackets
    from test_rpc import TestRegistryRegister, TestRegistryDiscover
    from test_rpc import TestRegistryHeartbeat, TestRegistryHealthCheck
    from test_rpc import TestRPCMethodRegistration, TestRPCClientConnect
    from test_rpc import TestRPCCall, TestRPCError, TestRPCTimeout
    from test_rpc import TestRPCProxy, TestMultiService

    test_cases = [
        TestCodecRequest, TestCodecResponse,
        TestCodecHeartbeat, TestCodecHeader,
        TestCodecIncompleteFrame, TestCodecStickyPackets,
        TestRegistryRegister, TestRegistryDiscover,
        TestRegistryHeartbeat, TestRegistryHealthCheck,
        TestRPCMethodRegistration, TestRPCClientConnect,
        TestRPCCall, TestRPCError, TestRPCTimeout,
        TestRPCProxy, TestMultiService,
    ]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for tc in test_cases:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def main():
    parser = argparse.ArgumentParser(
        description='RPC 框架 - 纯 Python 实现',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py demo              # 运行演示
  python main.py test              # 运行测试
  python main.py server -s Math    # 启动 Math 服务
  python main.py client -s Math    # 连接到 Math 服务
        """,
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # server 子命令
    p_server = subparsers.add_parser('server', help='启动服务器')
    p_server.add_argument('-s', '--service', default='default',
                          help='服务名称')
    p_server.add_argument('--host', default='0.0.0.0', help='监听地址')
    p_server.add_argument('-p', '--port', type=int, default=0,
                          help='监听端口（0=自动分配）')

    # client 子命令
    p_client = subparsers.add_parser('client', help='启动客户端')
    p_client.add_argument('-s', '--service', required=True, help='服务名称')
    p_client.add_argument('--host', default=None, help='服务器地址')
    p_client.add_argument('-p', '--port', default=None, help='服务器端口')
    p_client.add_argument('-t', '--timeout', type=int, default=5,
                          help='超时秒数')
    p_client.add_argument('--method', default=None, help='调用的方法名')
    p_client.add_argument('args', nargs='*', help='方法参数')

    # demo 子命令
    subparsers.add_parser('demo', help='运行演示')

    # test 子命令
    subparsers.add_parser('test', help='运行测试')

    args = parser.parse_args()

    if args.command == 'server':
        cmd_server(args)
    elif args.command == 'client':
        cmd_client(args)
    elif args.command == 'demo':
        cmd_demo(args)
    elif args.command == 'test':
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
