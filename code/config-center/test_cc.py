#!/usr/bin/env python3
"""
配置中心测试 - 至少 16 个测试用例
"""
import os
import sys
import time
import json
import shutil
import unittest
import threading

# 确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kvstore import KVStore
from lease import LeaseManager
from protocol import encode_response, decode_request
from server import ConfigServer
from client import ConfigClient


TEST_DATA_DIR = 'test_config_data'


def setUpModule():
    """清理测试数据目录"""
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)


def tearDownModule():
    """清理测试数据目录"""
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)


# ============================================================
# KVStore 测试
# ============================================================

class TestKVStore(unittest.TestCase):
    """KVStore 单元测试"""
    
    def setUp(self):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        self.store = KVStore(path=TEST_DATA_DIR)
    
    def tearDown(self):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
    
    # Test 1: PUT/GET
    def test_put_get(self):
        """PUT 然后 GET"""
        self.store.put('/config/db/host', 'localhost')
        result = self.store.get('/config/db/host')
        self.assertIsNotNone(result)
        self.assertEqual(result['value'], 'localhost')
        self.assertEqual(result['key'], '/config/db/host')
    
    # Test 2: 更新版本递增
    def test_version_increment(self):
        """PUT 更新后版本号递增"""
        self.store.put('/config/test', 'v1')
        v1 = self.store.get('/config/test')
        self.assertEqual(v1['version'], 1)
        
        self.store.put('/config/test', 'v2')
        v2 = self.store.get('/config/test')
        self.assertEqual(v2['version'], 2)
        self.assertEqual(v2['value'], 'v2')
    
    # Test 3: GET 不存在键
    def test_get_nonexistent(self):
        """GET 不存在的键返回 None"""
        result = self.store.get('/nonexistent/key')
        self.assertIsNone(result)
    
    # Test 4: DELETE
    def test_delete(self):
        """DELETE 删除键"""
        self.store.put('/config/to_delete', 'value')
        self.assertIsNotNone(self.store.get('/config/to_delete'))
        
        ok = self.store.delete('/config/to_delete')
        self.assertTrue(ok)
        self.assertIsNone(self.store.get('/config/to_delete'))
    
    # Test 5: 删除不存在键
    def test_delete_nonexistent(self):
        """DELETE 不存在的键返回 False"""
        ok = self.store.delete('/nonexistent')
        self.assertFalse(ok)
    
    # Test 6: 前缀查询 LIST
    def test_list_prefix(self):
        """LIST 前缀查询"""
        self.store.put('/config/db/host', 'localhost')
        self.store.put('/config/db/port', '3306')
        self.store.put('/config/cache/ttl', '3600')
        self.store.put('/other/key', 'val')
        
        db_results = self.store.list_prefix('/config/db/')
        self.assertEqual(len(db_results), 2)
        keys = [r['key'] for r in db_results]
        self.assertIn('/config/db/host', keys)
        self.assertIn('/config/db/port', keys)
        
        config_results = self.store.list_prefix('/config/')
        self.assertEqual(len(config_results), 3)
        
        all_results = self.store.list_prefix('/')
        self.assertEqual(len(all_results), 4)
    
    # Test 7: 持久化保存加载
    def test_persistence(self):
        """持久化 - 保存后重新加载"""
        self.store.put('/persist/key1', 'val1')
        self.store.put('/persist/key2', 'val2')
        
        # 创建新 store（同一数据目录），应自动加载已保存数据
        store2 = KVStore(path=TEST_DATA_DIR)
        r1 = store2.get('/persist/key1')
        self.assertIsNotNone(r1)
        self.assertEqual(r1['value'], 'val1')
        
        r2 = store2.get('/persist/key2')
        self.assertIsNotNone(r2)
        self.assertEqual(r2['value'], 'val2')
    
    # Test 8: WATCH 回调
    def test_watch_callback(self):
        """WATCH 监听回调"""
        events = []
        
        def callback(event):
            events.append(event)
        
        self.store.watch('/watch/key', callback)
        self.store.put('/watch/key', 'watch_value')
        
        time.sleep(0.1)  # 等待回调执行
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['key'], '/watch/key')
        self.assertEqual(events[0]['value'], 'watch_value')
        self.assertEqual(events[0]['type'], 'update')
        
        # delete 也应触发回调
        self.store.delete('/watch/key')
        time.sleep(0.1)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]['type'], 'delete')


# ============================================================
# Lease 测试
# ============================================================

class TestLease(unittest.TestCase):
    """Lease 单元测试"""
    
    def setUp(self):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        self.store = KVStore(path=TEST_DATA_DIR)
        self.mgr = LeaseManager(self.store)
    
    def tearDown(self):
        self.mgr.stop()
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
    
    # Test 9: GRANT 租约
    def test_grant(self):
        """GRANT 创建租约"""
        lease = self.mgr.grant(60)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.ttl, 60)
        self.assertFalse(lease.expired)
        self.assertIn(lease.id, self.mgr.leases)
    
    # Test 10: KEEPALIVE 续约
    def test_keepalive(self):
        """KEEPALIVE 续约"""
        lease = self.mgr.grant(60)
        old_time = lease.last_keepalive
        
        time.sleep(0.1)
        ok = self.mgr.keepalive(lease.id)
        self.assertTrue(ok)
        self.assertGreater(lease.last_keepalive, old_time)
        self.assertFalse(lease.expired)
    
    # Test 11: 自动过期
    def test_auto_expire(self):
        """租约自动过期"""
        lease = self.mgr.grant(1)  # 1 秒
        self.assertFalse(lease.is_expired())
        
        time.sleep(1.5)
        self.assertTrue(lease.is_expired())
    
    # Test 12: REVOKE 撤销
    def test_revoke(self):
        """REVOKE 撤销租约"""
        lease = self.mgr.grant(60)
        lease_id = lease.id
        lease.keys.add('/revoke/test')
        
        ok = self.mgr.revoke(lease_id)
        self.assertTrue(ok)
        self.assertNotIn(lease_id, self.mgr.leases)
        self.assertTrue(lease.expired)
    
    # Test 13: ATTACH key 到租约
    def test_attach_key(self):
        """ATTACH 键关联到租约"""
        lease = self.mgr.grant(60)
        lease_id = lease.id
        
        ok = self.mgr.attach_key(lease_id, '/lease/attached_key')
        self.assertTrue(ok)
        self.assertIn('/lease/attached_key', lease.keys)
        
        # 过期租约不能 attach
        lease.expired = True
        ok = self.mgr.attach_key(lease_id, '/lease/expired_key')
        self.assertFalse(ok)


# ============================================================
# Protocol 测试
# ============================================================

class TestProtocol(unittest.TestCase):
    """协议编码/解码测试"""
    
    # Test 14: 协议编码/解码
    def test_encode_decode(self):
        """协议编码解码"""
        # 成功响应编码
        resp = encode_response(True, {'key': 'foo', 'version': 1})
        decoded = json.loads(resp.strip())
        self.assertTrue(decoded['ok'])
        self.assertEqual(decoded['data']['key'], 'foo')
        
        # 错误响应编码
        resp = encode_response(False, error='something wrong')
        decoded = json.loads(resp.strip())
        self.assertFalse(decoded['ok'])
        self.assertEqual(decoded['error'], 'something wrong')
        
        # 请求解码: PUT
        cmd, args = decode_request('PUT /config/db/host localhost:3306')
        self.assertEqual(cmd, 'PUT')
        self.assertEqual(args[0], '/config/db/host')
        self.assertEqual(args[1], 'localhost:3306')
        
        # 请求解码: GET
        cmd, args = decode_request('GET /config/key')
        self.assertEqual(cmd, 'GET')
        self.assertEqual(len(args), 1)
        
        # 请求解码: LIST (无参数)
        cmd, args = decode_request('LIST')
        self.assertEqual(cmd, 'LIST')
        self.assertEqual(args, [])
        
        # 请求解码: 空行
        cmd, args = decode_request('')
        self.assertIsNone(cmd)
        self.assertEqual(args, [])


# ============================================================
# 集成测试
# ============================================================

class TestIntegration(unittest.TestCase):
    """集成测试（启动真实 TCP 服务器）"""
    
    @classmethod
    def setUpClass(cls):
        """启动测试服务器"""
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        
        cls.server = ConfigServer(host='127.0.0.1', port=18500, store_path=TEST_DATA_DIR)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(1)  # 等待服务器就绪
        
        cls.client = ConfigClient(host='127.0.0.1', port=18500)
    
    @classmethod
    def tearDownClass(cls):
        cls.server.lease_mgr.stop()
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
    
    def setUp(self):
        """每个测试前清理所有键"""
        # 获取所有键并删除
        resp = self.client.list_prefix('/')
        if resp.get('ok') and resp.get('data'):
            for item in resp['data']:
                self.client.delete(item['key'])
    
    # Test 15: 集成 PUT+GET+DELETE
    def test_put_get_delete_integration(self):
        """集成: PUT + GET + DELETE"""
        # PUT
        resp = self.client.put('/config/app/name', 'myapp')
        self.assertTrue(resp['ok'])
        self.assertEqual(resp['data']['key'], '/config/app/name')
        
        # GET
        resp = self.client.get('/config/app/name')
        self.assertTrue(resp['ok'])
        self.assertEqual(resp['data']['value'], 'myapp')
        self.assertEqual(resp['data']['version'], 1)
        
        # UPDATE -> 版本递增
        resp = self.client.put('/config/app/name', 'myapp-v2')
        self.assertTrue(resp['ok'])
        
        resp = self.client.get('/config/app/name')
        self.assertEqual(resp['data']['version'], 2)
        self.assertEqual(resp['data']['value'], 'myapp-v2')
        
        # DELETE
        resp = self.client.delete('/config/app/name')
        self.assertTrue(resp['ok'])
        
        # DELETE 后 GET 应返回 None
        resp = self.client.get('/config/app/name')
        self.assertFalse(resp['ok'])
    
    # Test 16: 集成 GRANT+ATTACH+过期清理
    def test_lease_expiry_cleanup(self):
        """集成: GRANT + ATTACH + 过期自动清理"""
        # 先放一个键
        self.client.put('/lease_test/key1', 'will_expire')
        
        # GRANT 1 秒租约
        resp = self.client.grant(1)
        self.assertTrue(resp['ok'])
        lease_id = resp['data']['lease_id']
        
        # ATTACH 键到租约
        resp = self.client.attach(lease_id, '/lease_test/key1')
        self.assertTrue(resp['ok'])
        
        # 确认键存在
        resp = self.client.get('/lease_test/key1')
        self.assertTrue(resp['ok'])
        
        # 等待租约过期 (>1s)
        time.sleep(2)
        
        # 键应被自动删除
        resp = self.client.get('/lease_test/key1')
        self.assertFalse(resp['ok'])
    
    # Test 17: STATS
    def test_stats(self):
        """STATS 统计信息"""
        resp = self.client.stats()
        self.assertTrue(resp['ok'])
        self.assertIn('keys', resp['data'])
        self.assertIn('watchers', resp['data'])
    
    # Test 18: LIST 前缀查询
    def test_list_prefix_integration(self):
        """集成: LIST 前缀查询"""
        self.client.put('/config/db/host', 'localhost')
        self.client.put('/config/db/port', '3306')
        self.client.put('/config/cache/ttl', '3600')
        
        resp = self.client.list_prefix('/config/db/')
        self.assertTrue(resp['ok'])
        self.assertEqual(len(resp['data']), 2)
        
        resp = self.client.list_prefix('/')
        self.assertEqual(len(resp['data']), 3)
    
    # Test 19: REVOKE 清理关联键
    def test_revoke_cleans_keys(self):
        """REVOKE 撤销租约时清理关联键"""
        # PUT key
        self.client.put('/revoke_test/key', 'some_value')
        
        # GRANT
        resp = self.client.grant(600)
        lease_id = resp['data']['lease_id']
        
        # ATTACH
        self.client.attach(lease_id, '/revoke_test/key')
        
        # 确认键存在
        resp = self.client.get('/revoke_test/key')
        self.assertTrue(resp['ok'])
        
        # REVOKE
        resp = self.client.revoke(lease_id)
        self.assertTrue(resp['ok'])
        
        # 键应被清理
        resp = self.client.get('/revoke_test/key')
        self.assertFalse(resp['ok'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
