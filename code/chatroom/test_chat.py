"""
test_chat.py — 聊天室单元测试
覆盖:
  - protocol.py pack/unpack 往返测试
  - 服务端基础功能 (空会话/单用户/多用户)
  - 客户端双线程起停
  - 命令解析
"""

import unittest
import socket
import threading
import struct
import json
import time

# 确保可以导入同级模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import pack, unpack, parse_stream
from server import ChatServer
import client as client_mod


def _recv_all(sock, timeout=1.0):
    """清空socket当前缓冲区中的所有消息，返回消息列表"""
    sock.settimeout(timeout)
    buf = b''
    msgs = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # 先解析已缓冲的数据
        while len(buf) >= 4:
            length = struct.unpack('!I', buf[:4])[0]
            if len(buf) < 4 + length:
                break
            body = buf[4:4 + length]
            buf = buf[4 + length:]
            msgs.append(json.loads(body.decode('utf-8')))
        if msgs:
            break  # 收到消息就返回
        try:
            data = sock.recv(4096)
            if not data:
                break
            buf += data
        except socket.timeout:
            break
    return msgs


class _ServerThread:
    """在后台线程中运行服务器"""

    def __init__(self):
        self.server = ChatServer(host='127.0.0.1', port=0)
        self.thread = threading.Thread(target=self.server.start, daemon=True)
        self.thread.start()
        # 等待服务器就绪
        time.sleep(0.1)
        self.port = self.server.server_sock.getsockname()[1]

    def stop(self):
        self.server._running = False
        self.server.shutdown()
        self.thread.join(timeout=2)


# ============================================================
# Protocol 测试
# ============================================================

class TestProtocol(unittest.TestCase):
    def test_pack_unpack_roundtrip(self):
        """pack/unpack 往返测试: 打包后解包应得到原始消息"""
        msg = {'type': 'chat', 'nick': '张三', 'msg': '你好'}
        data = pack(msg)
        result = unpack(data)
        self.assertEqual(result, msg)

    def test_pack_unpack_ascii(self):
        msg = {'type': 'system', 'msg': 'hello'}
        data = pack(msg)
        result = unpack(data)
        self.assertEqual(result, msg)

    def test_pack_unpack_empty_str(self):
        msg = {'type': 'chat', 'nick': 'a', 'msg': ''}
        data = pack(msg)
        result = unpack(data)
        self.assertEqual(result, msg)

    def test_pack_unpack_numeric(self):
        msg = {'type': 'count', 'value': 42}
        data = pack(msg)
        result = unpack(data)
        self.assertEqual(result, msg)

    def test_pack_unpack_bool(self):
        msg = {'type': 'system', 'ok': True}
        data = pack(msg)
        result = unpack(data)
        self.assertEqual(result, msg)

    def test_pack_length_prefix(self):
        msg = {'a': 'b'}
        data = pack(msg)
        length = struct.unpack('!I', data[:4])[0]
        self.assertEqual(length, len(data) - 4)
        self.assertEqual(len(data), 4 + length)

    def test_unpack_too_short(self):
        with self.assertRaises(ValueError):
            unpack(b'\x00\x00')

    def test_parse_stream_single(self):
        msg = {'msg': 'hello'}
        data = pack(msg)
        messages, remaining = parse_stream(data)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], msg)
        self.assertEqual(remaining, b'')

    def test_parse_stream_multiple(self):
        msgs = [{'msg': 'first'}, {'msg': 'second'}, {'msg': 'third'}]
        stream = b''.join(pack(m) for m in msgs)
        messages, remaining = parse_stream(stream)
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages, msgs)
        self.assertEqual(remaining, b'')

    def test_parse_stream_partial(self):
        msg = {'msg': '完整'}
        data = pack(msg)
        partial = data[:3]
        messages, remaining = parse_stream(partial)
        self.assertEqual(len(messages), 0)
        self.assertEqual(remaining, partial)

    def test_parse_stream_partial_in_middle(self):
        msg1 = {'msg': '完整'}
        msg2 = {'msg': '不完整'}
        data1 = pack(msg1)
        data2 = pack(msg2)
        partial = data2[:-2]
        stream = data1 + partial
        messages, remaining = parse_stream(stream)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], msg1)
        self.assertEqual(remaining, partial)


# ============================================================
# Server 测试
# ============================================================

class TestChatServer(unittest.TestCase):
    def setUp(self):
        self.st = _ServerThread()
        self.socks = []

    def tearDown(self):
        for s in self.socks:
            try:
                s.close()
            except Exception:
                pass
        self.st.stop()

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', self.st.port))
        self.socks.append(sock)
        return sock

    def _send(self, sock, msg):
        sock.sendall(pack(msg))

    def test_server_empty(self):
        """空会话：服务器启动无客户端应正常运行"""
        self.assertTrue(self.st.server._running)

    def test_single_client_connect_and_nick(self):
        """单用户连接并设置昵称"""
        sock = self._connect()
        # 先收欢迎消息
        msgs = _recv_all(sock)
        welcome = None
        for m in msgs:
            if m.get('type') == 'system' and '欢迎' in m.get('msg', ''):
                welcome = m
        self.assertIsNotNone(welcome, f"No welcome msg, got: {msgs}")

        # 发送昵称
        self._send(sock, {'msg': '测试用户'})
        time.sleep(0.2)
        msgs = _recv_all(sock)
        # 可能收到 join + system 两条消息, 也可能只收到一条
        entry = None
        for m in msgs:
            msg_text = m.get('msg', '')
            if '已进入' in msg_text:
                entry = m
                break
        self.assertIsNotNone(entry, f"No entry msg, got: {msgs}")

        # 验证服务端记录了昵称
        self.assertIn('测试用户',
                      [c['nick'] for fd, c in self.st.server.clients.items()
                       if c['nick']])

    def test_two_clients_chat(self):
        """双用户：消息应广播"""
        sock_a = self._connect()
        _recv_all(sock_a)
        self._send(sock_a, {'msg': 'Alice'})
        _recv_all(sock_a)

        sock_b = self._connect()
        _recv_all(sock_b)
        self._send(sock_b, {'msg': 'Bob'})
        _recv_all(sock_b)

        # A 收 B 加入
        time.sleep(0.1)
        msgs_a = _recv_all(sock_a)
        join_msg = None
        for m in msgs_a:
            if m.get('type') == 'join':
                join_msg = m
        self.assertIsNotNone(join_msg)
        self.assertEqual(join_msg['nick'], 'Bob')

        # A 发送消息 -> B 收到
        self._send(sock_a, {'type': 'chat', 'msg': 'Hello Bob!'})
        time.sleep(0.1)

        msgs_b = _recv_all(sock_b)
        chat_msg = None
        for m in msgs_b:
            if m.get('type') == 'chat' and m.get('msg') == 'Hello Bob!':
                chat_msg = m
        self.assertIsNotNone(chat_msg)
        self.assertEqual(chat_msg['nick'], 'Alice')

    def test_disconnect_broadcast(self):
        """断线广播 leave"""
        sock_a = self._connect()
        _recv_all(sock_a)
        self._send(sock_a, {'msg': 'Alice'})
        _recv_all(sock_a)

        sock_b = self._connect()
        _recv_all(sock_b)
        self._send(sock_b, {'msg': 'Bob'})
        _recv_all(sock_b)

        # A 收 B 加入
        _recv_all(sock_a)

        # B 断开
        sock_b.close()
        time.sleep(0.5)

        # A 收 leave
        msgs = _recv_all(sock_a)
        leave_msg = None
        for m in msgs:
            if m.get('type') == 'leave':
                leave_msg = m
        self.assertIsNotNone(leave_msg, f"No leave msg, got: {msgs}")
        self.assertEqual(leave_msg['nick'], 'Bob')

    def test_list_command(self):
        """测试 /list"""
        sock_a = self._connect()
        _recv_all(sock_a)
        self._send(sock_a, {'msg': 'Alice'})
        _recv_all(sock_a)

        sock_b = self._connect()
        _recv_all(sock_b)
        self._send(sock_b, {'msg': 'Bob'})
        _recv_all(sock_b)
        _recv_all(sock_a)

        self._send(sock_a, {'type': 'chat', 'msg': '/list'})
        time.sleep(0.1)
        msgs = _recv_all(sock_a)
        list_msg = None
        for m in msgs:
            if m.get('type') == 'system' and '在线' in m.get('msg', ''):
                list_msg = m
        self.assertIsNotNone(list_msg)
        self.assertIn('Alice', list_msg['msg'])
        self.assertIn('Bob', list_msg['msg'])

    def test_nick_command(self):
        """测试 /nick"""
        sock = self._connect()
        _recv_all(sock)
        self._send(sock, {'msg': 'OldName'})
        _recv_all(sock)

        self._send(sock, {'type': 'chat', 'msg': '/nick NewName'})
        time.sleep(0.1)
        msgs = _recv_all(sock)
        nick_msg = None
        for m in msgs:
            if m.get('type') == 'system' and 'OldName' in m.get('msg', ''):
                nick_msg = m
        self.assertIsNotNone(nick_msg)
        self.assertIn('OldName', nick_msg['msg'])
        self.assertIn('NewName', nick_msg['msg'])

    def test_quit_command(self):
        """测试 /quit 触发 leave 广播"""
        sock_a = self._connect()
        _recv_all(sock_a)
        self._send(sock_a, {'msg': 'Alice'})
        _recv_all(sock_a)

        sock_b = self._connect()
        _recv_all(sock_b)
        self._send(sock_b, {'msg': 'Bob'})
        _recv_all(sock_b)
        _recv_all(sock_a)

        self._send(sock_a, {'type': 'chat', 'msg': '/quit'})
        sock_a.close()
        time.sleep(0.5)

        msgs = _recv_all(sock_b)
        leave_msg = None
        for m in msgs:
            if m.get('type') == 'leave':
                leave_msg = m
        self.assertIsNotNone(leave_msg, f"No leave msg, got: {msgs}")
        self.assertEqual(leave_msg['nick'], 'Alice')

    def test_unknown_command(self):
        """测试未知命令"""
        sock = self._connect()
        _recv_all(sock)
        self._send(sock, {'msg': 'Tester'})
        _recv_all(sock)

        self._send(sock, {'type': 'chat', 'msg': '/xyz'})
        time.sleep(0.1)
        msgs = _recv_all(sock)
        sys_msg = None
        for m in msgs:
            if m.get('type') == 'system' and '未知' in m.get('msg', ''):
                sys_msg = m
        self.assertIsNotNone(sys_msg, f"No unknown cmd msg, got: {msgs}")
        self.assertIn('未知', sys_msg['msg'])


# ============================================================
# Client 生命周期测试
# ============================================================

class TestClientLifecycle(unittest.TestCase):
    def test_client_start_stop(self):
        """客户端连接后正常关闭"""
        st = _ServerThread()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', st.port))
        sock.sendall(pack({'msg': 'QuickUser'}))
        time.sleep(0.2)
        sock.sendall(pack({'type': 'chat', 'msg': '/quit'}))
        sock.close()
        time.sleep(0.3)

        st.stop()

    def test_client_threads(self):
        """验证客户端双线程结构"""
        st = _ServerThread()
        cli = client_mod.ChatClient(host='127.0.0.1', port=st.port)

        # 验证接收线程可以创建
        t = threading.Thread(target=cli._recv_loop, daemon=True)
        self.assertIsNotNone(t)

        cli._cleanup()
        st.stop()


if __name__ == '__main__':
    unittest.main(verbosity=2)
