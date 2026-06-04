"""Mini Redis 测试 - 至少 16 个测试用例"""
import time
import unittest

from resp import (
    encode_simple, encode_error, encode_integer,
    encode_bulk, encode_array, encode_value,
    decode, decode_request
)
from store import Store
from commands import CommandHandler


# ===== RESP 编码测试 =====

class TestRESPEncode(unittest.TestCase):
    """第 1 组: RESP 编码"""
    
    def test_encode_simple_string(self):
        """测试 1: RESP 编码 Simple String"""
        self.assertEqual(encode_simple('OK'), b'+OK\r\n')
        self.assertEqual(encode_simple('PONG'), b'+PONG\r\n')
    
    def test_encode_error(self):
        """测试 2: RESP 编码 Error"""
        self.assertEqual(encode_error('ERR unknown command'), b'-ERR unknown command\r\n')
        self.assertEqual(encode_error('ERR wrong type'), b'-ERR wrong type\r\n')
    
    def test_encode_integer(self):
        """测试 3: RESP 编码 Integer"""
        self.assertEqual(encode_integer(0), b':0\r\n')
        self.assertEqual(encode_integer(42), b':42\r\n')
        self.assertEqual(encode_integer(-1), b':-1\r\n')
    
    def test_encode_bulk_string(self):
        """测试 4: RESP 编码 Bulk String"""
        self.assertEqual(encode_bulk('hello'), b'$5\r\nhello\r\n')
        self.assertEqual(encode_bulk(''), b'$0\r\n\r\n')
        self.assertEqual(encode_bulk(None), b'$-1\r\n')
        self.assertEqual(encode_bulk('OK'), b'$2\r\nOK\r\n')
    
    def test_encode_array(self):
        """测试 5: RESP 编码 Array"""
        self.assertEqual(encode_array(['foo', 'bar']), b'*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n')
        self.assertEqual(encode_array([]), b'*0\r\n')
        self.assertEqual(encode_array(None), b'*-1\r\n')
        self.assertEqual(encode_array(['a', 'b', 'c']), b'*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n')


class TestRESPDecode(unittest.TestCase):
    """第 2 组: RESP 解码"""
    
    def test_decode_simple_string(self):
        val, rem = decode(b'+OK\r\n')
        self.assertEqual(val, 'OK')
        self.assertEqual(rem, b'')
    
    def test_decode_error(self):
        val, rem = decode(b'-ERR unknown\r\n')
        self.assertIsInstance(val, Exception)
        self.assertEqual(str(val), 'ERR unknown')
        self.assertEqual(rem, b'')
    
    def test_decode_integer(self):
        val, rem = decode(b':42\r\n')
        self.assertEqual(val, 42)
        self.assertEqual(rem, b'')
        
        val, rem = decode(b':-1\r\n')
        self.assertEqual(val, -1)
    
    def test_decode_bulk_string(self):
        val, rem = decode(b'$5\r\nhello\r\n')
        self.assertEqual(val, 'hello')
        self.assertEqual(rem, b'')
        
        val, rem = decode(b'$-1\r\n')
        self.assertIsNone(val)
        self.assertEqual(rem, b'')
        
        val, rem = decode(b'$0\r\n\r\n')
        self.assertEqual(val, '')
    
    def test_decode_array(self):
        """测试 6: RESP 解码完整请求"""
        # 模拟 SET key value
        data = b'*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n'
        val, rem = decode(data)
        self.assertEqual(val, ['SET', 'key', 'value'])
        self.assertEqual(rem, b'')
    
    def test_decode_request(self):
        data = b'*2\r\n$4\r\nPING\r\n$4\r\ntest\r\n'
        result = decode_request(data)
        self.assertEqual(result, ['PING', 'test'])
    
    def test_decode_incomplete(self):
        """不完整帧应该返回 None"""
        val, rem = decode(b'$5\r\nhel')
        self.assertIsNone(val)
        self.assertEqual(rem, b'$5\r\nhel')
    
    def test_decode_then_more(self):
        """粘包测试: 两个请求粘在一起"""
        data = b'*1\r\n$4\r\nPING\r\n*1\r\n$4\r\nPING\r\n'
        val1, rem = decode(data)
        self.assertEqual(val1, ['PING'])
        # 剩余应该包含第二个请求
        val2, _ = decode(rem)
        self.assertEqual(val2, ['PING'])


# ===== 存储引擎测试 =====

class TestStore(unittest.TestCase):
    """第 3 组: Store 存储引擎"""
    
    def setUp(self):
        self.store = Store()
    
    def test_set_get(self):
        """测试 7: Store SET/GET"""
        self.store.set('name', 'Alice')
        self.assertEqual(self.store.get('name'), 'Alice')
        self.assertIsNone(self.store.get('nonexistent'))
    
    def test_expire(self):
        """测试 8: Store 过期"""
        # 设置极短过期时间 (1ms)
        self.store.set('temp', 'data', expire_ms=1)
        self.assertEqual(self.store.get('temp'), 'data')
        # 等待过期
        time.sleep(0.05)
        self.assertIsNone(self.store.get('temp'))
    
    def test_delete(self):
        """测试 9: Store DEL"""
        self.store.set('x', '1')
        self.assertTrue(self.store.delete('x'))
        self.assertFalse(self.store.delete('x'))
        self.assertIsNone(self.store.get('x'))
    
    def test_exists(self):
        """测试 10: Store EXISTS"""
        self.store.set('a', '1')
        self.assertTrue(self.store.exists('a'))
        self.assertFalse(self.store.exists('b'))
    
    def test_keys_wildcard(self):
        """测试 11: Store KEYS 通配符"""
        self.store.set('foo', '1')
        self.store.set('bar', '2')
        self.store.set('baz', '3')
        keys = self.store.keys('b*')
        self.assertEqual(sorted(keys), ['bar', 'baz'])
        keys = self.store.keys('*')
        self.assertEqual(sorted(keys), ['bar', 'baz', 'foo'])
        keys = self.store.keys('f??')
        self.assertEqual(keys, ['foo'])
    
    def test_flushall(self):
        """测试 12: Store FLUSHALL"""
        self.store.set('a', '1')
        self.store.set('b', '2')
        self.store.flushall()
        self.assertEqual(self.store.dbsize(), 0)
        self.assertIsNone(self.store.get('a'))
    
    def test_ttl(self):
        self.store.set('persist', 'v')
        self.assertEqual(self.store.ttl('persist'), -1)
        self.assertEqual(self.store.ttl('nonexist'), -2)
        self.store.expire('persist', 100000)
        self.assertGreater(self.store.ttl('persist'), 0)


# ===== 命令处理器测试 =====

class TestCommands(unittest.TestCase):
    """第 4 组: Commands 命令处理器"""
    
    def setUp(self):
        self.store = Store()
        self.handler = CommandHandler(self.store)
    
    def test_ping(self):
        """测试 16: Commands PING"""
        result = self.handler.execute('PING', [])
        self.assertEqual(result, 'PONG')
    
    def test_set_get_del(self):
        """测试 13: Commands SET/GET/DEL"""
        self.assertEqual(self.handler.execute('SET', ['k', 'v']), 'OK')
        self.assertEqual(self.handler.execute('GET', ['k']), 'v')
        self.assertIsNone(self.handler.execute('GET', ['nonexist']))
        self.assertEqual(self.handler.execute('DEL', ['k']), 1)
        self.assertIsNone(self.handler.execute('GET', ['k']))
    
    def test_expire_ttl(self):
        """测试 14: Commands EXPIRE/TTL"""
        self.handler.execute('SET', ['tmp', 'val'])
        self.assertEqual(self.handler.execute('EXPIRE', ['tmp', '100000']), 1)
        self.assertGreater(self.handler.execute('TTL', ['tmp']), 0)
        # 不存在的 key
        self.assertEqual(self.handler.execute('EXPIRE', ['nonexist', '100']), 0)
        self.assertEqual(self.handler.execute('TTL', ['nonexist']), -2)
    
    def test_keys_pattern(self):
        """测试 15: Commands KEYS 模式匹配"""
        self.handler.execute('SET', ['user:1', 'a'])
        self.handler.execute('SET', ['user:2', 'b'])
        self.handler.execute('SET', ['admin:1', 'c'])
        keys = self.handler.execute('KEYS', ['user:*'])
        self.assertEqual(sorted(keys), ['user:1', 'user:2'])
    
    def test_exists(self):
        self.handler.execute('SET', ['e', '1'])
        self.assertEqual(self.handler.execute('EXISTS', ['e']), 1)
        self.assertEqual(self.handler.execute('EXISTS', ['e', 'f']), 1)
        self.assertEqual(self.handler.execute('EXISTS', ['f']), 0)
    
    def test_flushall(self):
        self.handler.execute('SET', ['x', '1'])
        self.assertEqual(self.handler.execute('FLUSHALL', []), 'OK')
        self.assertIsNone(self.handler.execute('GET', ['x']))
    
    def test_dbsize(self):
        self.handler.execute('SET', ['a', '1'])
        self.handler.execute('SET', ['b', '2'])
        self.assertEqual(self.handler.execute('DBSIZE', []), 2)
    
    def test_unknown_command(self):
        with self.assertRaises(ValueError):
            self.handler.execute('NOTACMD', [])
    
    def test_set_with_px(self):
        """SET with PX expiration"""
        self.handler.execute('SET', ['x', 'v', 'PX', '100'])
        self.assertGreater(self.handler.execute('TTL', ['x']), 0)
    
    def test_info(self):
        self.handler.execute('SET', ['a', '1'])
        info = self.handler.execute('INFO', [])
        self.assertIn('keys:', info)
        self.assertIn('expired_keys:', info)


class TestRESPValueEncoder(unittest.TestCase):
    """额外: encode_value 综合测试"""
    
    def test_encode_value_none(self):
        self.assertEqual(encode_value(None), b'$-1\r\n')
    
    def test_encode_value_str(self):
        self.assertEqual(encode_value('hello'), b'$5\r\nhello\r\n')
    
    def test_encode_value_int(self):
        self.assertEqual(encode_value(42), b':42\r\n')
    
    def test_encode_value_list(self):
        self.assertEqual(
            encode_value(['a', 'b']),
            b'*2\r\n$1\r\na\r\n$1\r\nb\r\n'
        )
    
    def test_encode_value_bytes(self):
        self.assertEqual(encode_value(b'data'), b'$4\r\ndata\r\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
