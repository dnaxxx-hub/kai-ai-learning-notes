"""测试 WebSocket 帧编码/解码和握手"""

import unittest
import os
import struct
import json
import base64
import hashlib

from frame import encode_frame, decode_frame, OPCODES
from handshake import parse_handshake, generate_accept_key, WS_MAGIC


class TestFrameEncoding(unittest.TestCase):
    """测试 1: 帧编码/解码正确"""

    def test_encode_decode_basic(self):
        """编码再解码得到相同的数据"""
        payload = b'Hello, WebSocket!'
        encoded = encode_frame(payload, opcode=OPCODES['TEXT'], mask=False)
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(frame['payload'], payload)
        self.assertEqual(frame['opcode'], 0x1)
        self.assertTrue(frame['fin'])
        self.assertEqual(remaining, b'')

    def test_encode_decode_binary(self):
        """二进制帧编码/解码"""
        payload = bytes(range(256))
        encoded = encode_frame(payload, opcode=OPCODES['BINARY'], mask=False)
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(frame['payload'], payload)
        self.assertEqual(frame['opcode'], 0x2)

    def test_continuation_frame(self):
        """延续帧编码/解码"""
        payload = b'continuation'
        encoded = encode_frame(payload, opcode=OPCODES['CONTINUE'], mask=False)
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(frame['opcode'], 0x0)
        self.assertEqual(frame['payload'], payload)


class TestFrameMasking(unittest.TestCase):
    """测试 2: 帧掩码正确"""

    def test_masked_frame(self):
        """带掩码的帧编码/解码"""
        payload = b'Secret Message'
        encoded = encode_frame(payload, opcode=0x1, mask=True)
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(frame['payload'], payload)
        self.assertEqual(frame['opcode'], 0x1)

    def test_masked_roundtrip_compare(self):
        """验证掩码后数据确实被混淆了"""
        payload = b'AAAAAAAA'
        encoded = encode_frame(payload, opcode=0x1, mask=True)
        # 帧头(2) + mask_key(4) + payload(8) = 14
        # 检查 payload 部分 (字节6+) 不等于原始数据
        self.assertNotEqual(encoded[10:], payload,
                            "掩码后的数据不应等于原始数据")
        # 解码后应该恢复
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['payload'], payload)

    def test_mask_bit_in_header(self):
        """确认带 mask 的帧的第2个字节最高位为1"""
        payload = b'X' * 10
        encoded = encode_frame(payload, opcode=0x1, mask=True)
        self.assertTrue(encoded[1] & 0x80, "MASK bit should be set")
        encoded_no_mask = encode_frame(payload, opcode=0x1, mask=False)
        self.assertFalse(encoded_no_mask[1] & 0x80, "MASK bit should not be set")


class TestPayloadSizes(unittest.TestCase):
    """测试 3: 小/中/大 payload 帧"""

    def test_small_payload(self):
        """小 payload (< 126 bytes)"""
        payload = b'A' * 100
        encoded = encode_frame(payload, mask=False)
        self.assertEqual(encoded[1] & 0x7F, 100)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['payload'], payload)

    def test_medium_payload(self):
        """中 payload (126-65535 bytes)"""
        payload = b'B' * 200
        encoded = encode_frame(payload, mask=False)
        # 长度字段应为 126，后面跟 2 字节实际长度
        self.assertEqual(encoded[1] & 0x7F, 126)
        actual_length = struct.unpack('!H', encoded[2:4])[0]
        self.assertEqual(actual_length, 200)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['payload'], payload)

    def test_large_payload(self):
        """大 payload (>= 65536 bytes)"""
        payload = b'C' * 70000
        encoded = encode_frame(payload, mask=False)
        self.assertEqual(encoded[1] & 0x7F, 127)
        actual_length = struct.unpack('!Q', encoded[2:10])[0]
        self.assertEqual(actual_length, 70000)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['payload'], payload)

    def test_empty_payload(self):
        """空 payload"""
        payload = b''
        encoded = encode_frame(payload, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['payload'], b'')

    def test_exact_boundary_125(self):
        """边界: 125 bytes (仍用小长度编码)"""
        payload = b'X' * 125
        encoded = encode_frame(payload, mask=False)
        self.assertEqual(encoded[1] & 0x7F, 125)
        frame, _ = decode_frame(encoded)
        self.assertEqual(len(frame['payload']), 125)

    def test_exact_boundary_126(self):
        """边界: 126 bytes (切换到16位长度)"""
        payload = b'X' * 126
        encoded = encode_frame(payload, mask=False)
        self.assertEqual(encoded[1] & 0x7F, 126)
        frame, _ = decode_frame(encoded)
        self.assertEqual(len(frame['payload']), 126)


class TestHandshake(unittest.TestCase):
    """测试 4: 握手请求解析"""

    def test_parse_valid_request(self):
        """解析有效的 WebSocket 握手请求"""
        request = (
            'GET /chat HTTP/1.1\r\n'
            'Host: server.example.com\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n'
        )
        result = parse_handshake(request)
        self.assertIsNotNone(result)
        self.assertEqual(result['method'], 'GET')
        self.assertEqual(result['path'], '/chat')
        self.assertEqual(result['key'], 'dGhlIHNhbXBsZSBub25jZQ==')
        self.assertEqual(result['version'], '13')

    def test_parse_missing_key(self):
        """缺少 Sec-WebSocket-Key 应返回 None"""
        request = (
            'GET / HTTP/1.1\r\n'
            'Host: localhost\r\n\r\n'
        )
        result = parse_handshake(request)
        self.assertIsNone(result)

    def test_parse_empty_request(self):
        """空请求应返回 None"""
        result = parse_handshake('')
        self.assertIsNone(result)

    def test_parse_multiple_headers(self):
        """多 header 也能正确解析"""
        request = (
            'GET /test HTTP/1.1\r\n'
            'Host: test.com\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Key: dGVzdCBrZXk=\r\n'
            'Sec-WebSocket-Version: 13\r\n'
            'Origin: http://test.com\r\n'
            'Sec-WebSocket-Protocol: chat\r\n\r\n'
        )
        result = parse_handshake(request)
        self.assertIsNotNone(result)
        self.assertEqual(result['key'], 'dGVzdCBrZXk=')


class TestAcceptKey(unittest.TestCase):
    """测试 5: Accept key 生成"""

    def test_rfc6455_example(self):
        """RFC 6455 Section 4.2.2 — 使用 Sec-WebSocket-Key 值 (base64 字符串本身)"""
        key = 'dGhlIHNhbXBsZSBub25jZQ=='
        # RFC 要求对 key 字符串本身做 SHA1 + base64
        import hashlib
        expected = base64.b64encode(
            hashlib.sha1(key.encode() + WS_MAGIC).digest()
        ).decode()
        result = generate_accept_key(key)
        self.assertEqual(result, expected)

    def test_known_key(self):
        """已知 Key 的预期结果"""
        key = base64.b64encode(b'test key').decode()
        sha1 = hashlib.sha1(key.encode() + WS_MAGIC).digest()
        expected = base64.b64encode(sha1).decode()
        result = generate_accept_key(key)
        self.assertEqual(result, expected)

    def test_random_keys(self):
        """多个随机 Key 验证"""
        for _ in range(5):
            key = base64.b64encode(os.urandom(16)).decode()
            sha1 = hashlib.sha1(key.encode() + WS_MAGIC).digest()
            expected = base64.b64encode(sha1).decode()
            result = generate_accept_key(key)
            self.assertEqual(result, expected)


class TestMultiFrameStream(unittest.TestCase):
    """测试 6: 多帧流解析"""

    def test_two_frames_in_stream(self):
        """一个数据流中包含多个帧"""
        payload1 = b'FrameOne'
        payload2 = b'FrameTwo'
        frame1 = encode_frame(payload1, mask=False)
        frame2 = encode_frame(payload2, mask=False)
        stream = frame1 + frame2

        # 解码第一帧
        f1, remaining = decode_frame(stream)
        self.assertIsNotNone(f1)
        self.assertEqual(f1['payload'], payload1)

        # 解码第二帧
        f2, remaining = decode_frame(remaining)
        self.assertIsNotNone(f2)
        self.assertEqual(f2['payload'], payload2)
        self.assertEqual(remaining, b'')

    def test_three_frames_in_stream(self):
        """三个帧在一个流中"""
        frames_data = [b'Alpha', b'Beta', b'Gamma']
        stream = b''.join(encode_frame(p, mask=False) for p in frames_data)

        for expected in frames_data:
            frame, stream = decode_frame(stream)
            self.assertIsNotNone(frame)
            self.assertEqual(frame['payload'], expected)
        self.assertEqual(stream, b'')

    def test_partial_frame(self):
        """不完整的帧应返回 None"""
        payload = b'Complete Payload'
        encoded = encode_frame(payload, mask=False)
        # 只给前3个字节
        partial = encoded[:3]
        frame, remaining = decode_frame(partial)
        self.assertIsNone(frame)
        self.assertEqual(remaining, partial)

    def test_stream_with_masked_frames(self):
        """带掩码的多帧流"""
        payload1 = b'Masked1'
        payload2 = b'Masked2'
        frame1 = encode_frame(payload1, mask=True)
        frame2 = encode_frame(payload2, mask=True)
        stream = frame1 + frame2

        f1, remaining = decode_frame(stream)
        self.assertIsNotNone(f1)
        self.assertEqual(f1['payload'], payload1)

        f2, remaining = decode_frame(remaining)
        self.assertIsNotNone(f2)
        self.assertEqual(f2['payload'], payload2)
        self.assertEqual(remaining, b'')


class TestPingPong(unittest.TestCase):
    """测试 7: PING/PONG 帧"""

    def test_ping_frame(self):
        """PING 帧编码/解码"""
        payload = b'pingdata'
        encoded = encode_frame(payload, opcode=0x9, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0x9)
        self.assertEqual(frame['payload'], payload)
        self.assertTrue(frame['fin'])

    def test_pong_frame(self):
        """PONG 帧编码/解码"""
        payload = b'pongdata'
        encoded = encode_frame(payload, opcode=0xA, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0xA)
        self.assertEqual(frame['payload'], payload)

    def test_ping_followed_by_text(self):
        """PING 帧后跟文本帧"""
        ping_payload = b''
        text_payload = b'Hello'
        ping_frame = encode_frame(ping_payload, opcode=0x9, mask=False)
        text_frame = encode_frame(text_payload, opcode=0x1, mask=False)
        stream = ping_frame + text_frame

        f1, remaining = decode_frame(stream)
        self.assertEqual(f1['opcode'], 0x9)

        f2, remaining = decode_frame(remaining)
        self.assertEqual(f2['opcode'], 0x1)
        self.assertEqual(f2['payload'], text_payload)
        self.assertEqual(remaining, b'')

    def test_pong_with_payload(self):
        """PONG 帧携带 application data"""
        payload = b'application data'
        encoded = encode_frame(payload, opcode=0xA, mask=True)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0xA)
        self.assertEqual(frame['payload'], payload)


class TestCloseFrame(unittest.TestCase):
    """测试 8: Close 帧"""

    def test_close_frame_no_payload(self):
        """Close 帧无 payload"""
        encoded = encode_frame(b'', opcode=0x8, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0x8)
        self.assertEqual(frame['payload'], b'')

    def test_close_frame_with_status_code(self):
        """Close 帧带状态码"""
        # 状态码 1000 (Normal Closure) -> 0x03E8
        payload = struct.pack('!H', 1000)
        encoded = encode_frame(payload, opcode=0x8, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0x8)
        status = struct.unpack('!H', frame['payload'][:2])[0]
        self.assertEqual(status, 1000)

    def test_close_frame_with_reason(self):
        """Close 帧带状态码和原因"""
        reason = b'Normal closure'
        payload = struct.pack('!H', 1000) + reason
        encoded = encode_frame(payload, opcode=0x8, mask=False)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0x8)
        status = struct.unpack('!H', frame['payload'][:2])[0]
        self.assertEqual(status, 1000)
        self.assertEqual(frame['payload'][2:], reason)

    def test_close_mask_roundtrip(self):
        """Close 帧 mask 往返"""
        payload = struct.pack('!H', 1001) + b'Going away'
        encoded = encode_frame(payload, opcode=0x8, mask=True)
        frame, _ = decode_frame(encoded)
        self.assertEqual(frame['opcode'], 0x8)
        self.assertEqual(frame['payload'], payload)


class TestCombinedScenarios(unittest.TestCase):
    """综合场景测试"""

    def test_server_client_handshake_simulation(self):
        """模拟完整的 WebSocket 握手"""
        # 客户端生成 Key
        client_key = base64.b64encode(os.urandom(16)).decode()

        # 客户端构造请求
        request = (
            f'GET / HTTP/1.1\r\n'
            f'Host: localhost\r\n'
            f'Upgrade: websocket\r\n'
            f'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {client_key}\r\n'
            f'Sec-WebSocket-Version: 13\r\n\r\n'
        )

        # 服务器解析
        parsed = parse_handshake(request)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['key'], client_key)

        # 服务器生成响应
        accept = generate_accept_key(parsed['key'])
        response = (
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
        )
        self.assertIn('101', response)
        self.assertIn(accept, response)

        # 验证 Accept 正确
        sha1 = hashlib.sha1(client_key.encode() + WS_MAGIC).digest()
        expected_accept = base64.b64encode(sha1).decode()
        self.assertEqual(accept, expected_accept)

    def test_masked_text_roundtrip(self):
        """模拟客户端发送 masked text -> 服务器接收"""
        # 客户端发送带 mask 的消息
        original = '{"type":"chat","nick":"Test","msg":"Hello"}'
        payload = original.encode('utf-8')
        encoded = encode_frame(payload, opcode=0x1, mask=True)

        # 服务器接收并解码
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(frame['opcode'], 0x1)
        decoded_payload = frame['payload'].decode('utf-8')
        self.assertEqual(decoded_payload, original)
        self.assertEqual(remaining, b'')

    def test_multiple_messages_server_broadcast(self):
        """模拟服务器广播多条消息"""
        messages = [
            '{"type":"system","msg":"用户1 进入聊天室"}',
            '{"type":"chat","nick":"用户1","msg":"大家好"}',
            '{"type":"system","msg":"用户1 离开聊天室"}',
        ]

        stream = b''
        for msg in messages:
            stream += encode_frame(msg.encode(), opcode=0x1, mask=False)

        for expected in messages:
            frame, stream = decode_frame(stream)
            self.assertIsNotNone(frame)
            self.assertEqual(frame['payload'].decode(), expected)

        self.assertEqual(stream, b'')

    def test_large_masked_payload_with_medium_length(self):
        """带 mask 的中等长度的 payload 往返"""
        payload = b'X' * 500
        encoded = encode_frame(payload, opcode=0x1, mask=True)
        # 检查使用 16 位长度编码
        self.assertEqual(encoded[1] & 0x7F, 126)
        frame, remaining = decode_frame(encoded)
        self.assertIsNotNone(frame)
        self.assertEqual(len(frame['payload']), 500)
        self.assertEqual(frame['payload'], payload)

    def test_opcode_constants(self):
        """验证所有 opcode 常量"""
        self.assertEqual(OPCODES['CONTINUE'], 0x0)
        self.assertEqual(OPCODES['TEXT'], 0x1)
        self.assertEqual(OPCODES['BINARY'], 0x2)
        self.assertEqual(OPCODES['CLOSE'], 0x8)
        self.assertEqual(OPCODES['PING'], 0x9)
        self.assertEqual(OPCODES['PONG'], 0xA)


if __name__ == '__main__':
    unittest.main()
