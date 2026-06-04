"""Mini Redis 演示"""
import time
import sys


def demo_resp():
    """演示 RESP 协议编码/解码"""
    print("=" * 50)
    print("RESP 协议演示")
    print("=" * 50)
    
    from resp import (
        encode_simple, encode_error, encode_integer,
        encode_bulk, encode_array, encode_value,
        decode
    )
    
    print("\n1. 编码 Simple String:")
    print(f"   encode_simple('OK') → {encode_simple('OK')!r}")
    
    print("\n2. 编码 Error:")
    print(f"   encode_error('ERR wrong type') → {encode_error('ERR wrong type')!r}")
    
    print("\n3. 编码 Integer:")
    print(f"   encode_integer(42) → {encode_integer(42)!r}")
    
    print("\n4. 编码 Bulk String:")
    print(f"   encode_bulk('hello') → {encode_bulk('hello')!r}")
    print(f"   encode_bulk(None) → {encode_bulk(None)!r}")
    
    print("\n5. 编码 Array:")
    print(f"   encode_array(['SET', 'foo', 'bar']) → {encode_array(['SET', 'foo', 'bar'])!r}")
    
    print("\n6. 编码值自动选择:")
    print(f"   encode_value('hello') → {encode_value('hello')!r}")
    print(f"   encode_value(42) → {encode_value(42)!r}")
    print(f"   encode_value(None) → {encode_value(None)!r}")
    
    print("\n7. 解码:")
    print(f"   decode(b'+OK\\r\\n') → {decode(b'+OK\\r\\n')}")
    print(f"   decode(b':100\\r\\n') → {decode(b':100\\r\\n')}")
    print(f"   decode(b'$5\\r\\nhello\\r\\n') → {decode(b'$5\\r\\nhello\\r\\n')}")
    data = b'*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$5\r\nhello\r\n'
    print(f"   decode({data!r}) → {decode(data)}")


def demo_store():
    """演示存储引擎"""
    print("\n" + "=" * 50)
    print("存储引擎演示")
    print("=" * 50)
    
    from store import Store
    
    store = Store()
    
    print("\n1. SET/GET:")
    store.set('name', 'MiniRedis')
    print(f"   store.set('name', 'MiniRedis') → OK")
    print(f"   store.get('name') → {store.get('name')!r}")
    
    print("\n2. 多个键:")
    store.set('user:1', 'Alice')
    store.set('user:2', 'Bob')
    store.set('admin:1', 'Charlie')
    print(f"   KEYS 'user:*' → {store.keys('user:*')}")
    print(f"   KEYS '*' → {store.keys('*')}")
    
    print("\n3. EXISTS:")
    print(f"   exists 'name' → {store.exists('name')}")
    print(f"   exists 'missing' → {store.exists('missing')}")
    
    print("\n4. DELETE:")
    store.set('temp', '数据')
    print(f"   delete 'temp' → {store.delete('temp')}")
    print(f"   delete 'temp' again → {store.delete('temp')}")
    
    print("\n5. 过期:")
    store.set('expire_soon', '将在 10ms 后过期', expire_ms=10)
    print(f"   刚设置: {store.get('expire_soon')!r}")
    time.sleep(0.05)
    print(f"   50ms 后: {store.get('expire_soon')!r} (应为 None)")
    
    print("\n6. FLUSHALL:")
    store.set('a', '1')
    store.set('b', '2')
    print(f"   DBSIZE 前: {store.dbsize()}")
    store.flushall()
    print(f"   DBSIZE 后: {store.dbsize()}")


def demo_server_client():
    """演示通过 TCP 通信"""
    import threading
    import time
    
    print("\n" + "=" * 50)
    print("TCP 服务器/客户端演示")
    print("=" * 50)
    
    from server import RedisServer
    from client import RedisClient
    
    # 启动服务器线程
    server = RedisServer(port=16379)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.1)
    
    # 客户端连接
    client = RedisClient(port=16379)
    
    try:
        print("\n1. PING:")
        print(f"   → {client.execute('PING')}")
        
        print("\n2. SET/GET:")
        print(f"   SET hello world → {client.execute('SET', 'hello', 'world')}")
        print(f"   GET hello → {client.execute('GET', 'hello')}")
        
        print("\n3. 批量测试:")
        print(f"   SET a 1 → {client.execute('SET', 'a', '1')}")
        print(f"   SET b 2 → {client.execute('SET', 'b', '2')}")
        print(f"   EXISTS a → {client.execute('EXISTS', 'a')}")
        print(f"   KEYS * → {client.execute('KEYS', '*')}")
        print(f"   DBSIZE → {client.execute('DBSIZE')}")
        print(f"   DEL a → {client.execute('DEL', 'a')}")
        print(f"   EXISTS a → {client.execute('EXISTS', 'a')}")
        
        print("\n4. 过期:")
        print(f"   SET temp val PX 50 → {client.execute('SET', 'temp', 'val', 'PX', '50')}")
        print(f"   GET temp → {client.execute('GET', 'temp')!r}")
        time.sleep(0.1)
        print(f"   100ms 后 GET temp → {client.execute('GET', 'temp')!r}")
        
        print("\n✅ 演示完成!")
    finally:
        client.close()


if __name__ == '__main__':
    demo_resp()
    demo_store()
    demo_server_client()
