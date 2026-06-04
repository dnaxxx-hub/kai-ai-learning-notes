#!/usr/bin/env python3
"""
配置中心 - 集成演示
启动服务端，执行一系列操作，展示完整功能。
"""

import time
import threading
from server import ConfigServer
from client import ConfigClient


def start_server():
    server = ConfigServer(host='127.0.0.1', port=8501)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.5)
    return server


def demo():
    # 启动服务器（后台线程）
    server = start_server()
    client = ConfigClient(host='127.0.0.1', port=8501)
    
    print("=" * 60)
    print("🟢 配置中心演示")
    print("=" * 60)
    
    # 1. PUT & GET
    print("\n1️⃣ PUT & GET 键值")
    client.put('/config/db/host', 'localhost')
    client.put('/config/db/port', '3306')
    client.put('/config/db/name', 'mydb')
    client.put('/config/cache/ttl', '3600')
    client.put('/config/cache/maxsize', '1024')
    
    r = client.get('/config/db/host')
    print(f"   GET /config/db/host -> {r}")
    
    # 2. 前缀查询 (类 etcd 目录风格)
    print("\n2️⃣ LIST 前缀查询 /config/db/")
    r = client.list_prefix('/config/db/')
    for item in r.get('data', []):
        print(f"   {item['key']} = {item['value']} (v{item['version']})")
    
    # 3. LIST 全部
    print("\n3️⃣ LIST 全部 /config/")
    r = client.list_prefix('/config/')
    for item in r.get('data', []):
        print(f"   {item['key']} = {item['value']}")
    
    # 4. 版本递增 & UPDATE
    print("\n4️⃣ 版本号自动递增")
    r1 = client.put('/config/db/host', 'db.example.com')
    r = client.get('/config/db/host')
    print(f"   GET /config/db/host -> version={r['data']['version']}, value={r['data']['value']}")
    
    # 5. DELETE
    print("\n5️⃣ DELETE 删除")
    r = client.delete('/config/cache/ttl')
    print(f"   DEL /config/cache/ttl -> {r}")
    r = client.get('/config/cache/ttl')
    print(f"   GET /config/cache/ttl -> {r}")
    
    # 6. GRANT 租约
    print("\n6️⃣ GRANT 租约")
    r = client.grant(30)
    lease_id = r['data']['lease_id']
    print(f"   GRANT 30s -> lease_id={lease_id}")
    
    # 7. ATTACH 键到租约
    print("\n7️⃣ ATTACH 键到租约")
    r = client.attach(lease_id, '/config/cache/maxsize')
    print(f"   ATTACH {lease_id} /config/cache/maxsize -> {r}")
    
    # 8. KEEPALIVE 续约
    print("\n8️⃣ KEEPALIVE 续约")
    r = client.keepalive(lease_id)
    print(f"   KEEPALIVE {lease_id} -> {r}")
    
    # 9. REVOKE 撤销租约（关联键自动删除）
    print("\n9️⃣ REVOKE 撤销租约（关联键自动删除）")
    # 先 attach 另一个键
    client.attach(lease_id, '/config/cache/test_key')
    client.put('/config/cache/test_key', 'temp_value')
    print(f"   撤消前 LIST /config/cache/:")
    r = client.list_prefix('/config/cache/')
    for item in r.get('data', []):
        print(f"     {item['key']}")
    
    client.revoke(lease_id)
    print(f"   撤消后 LIST /config/cache/:")
    r = client.list_prefix('/config/cache/')
    for item in r.get('data', []):
        print(f"     {item['key']}")
    print(f"   关联键已自动清理!")
    
    # 10. STATS
    print("\n🔟 STATS")
    r = client.stats()
    print(f"   keys={r['data']['keys']}, watchers={r['data']['watchers']}")
    
    # 11. 租约自动过期演示
    print("\n1️⃣1️⃣ 租约自动过期演示")
    r = client.grant(2)  # 2 秒租约
    short_lease = r['data']['lease_id']
    client.attach(short_lease, '/config/lease_test')
    client.put('/config/lease_test', 'will_expire')
    print(f"   创建 2s 租约 {short_lease}，关联 /config/lease_test")
    r = client.get('/config/lease_test')
    print(f"   过期前 GET /config/lease_test -> {r['data']['value']}")
    
    print("   等待 3 秒...")
    time.sleep(3)
    
    r = client.get('/config/lease_test')
    print(f"   过期后 GET /config/lease_test -> {r}")
    print(f"   键已自动删除! ✅")
    
    # 清理
    server.lease_mgr.stop()
    print("\n" + "=" * 60)
    print("✅ 演示完成")
    print("=" * 60)


if __name__ == '__main__':
    demo()
