import unittest
import time
import threading

from znode import ZNode
from tree import ZNodeTree
from watcher import WatcherManager
from session import Session, SessionManager


class TestZNode(unittest.TestCase):
    """测试 ZNode 节点模型"""

    def test_znode_creation(self):
        node = ZNode('/test', b'hello')
        self.assertEqual(node.path, '/test')
        self.assertEqual(node.data, b'hello')
        self.assertEqual(node.node_type, ZNode.PERSISTENT)
        self.assertFalse(node.is_ephemeral())
        self.assertFalse(node.is_sequential())
        self.assertEqual(node.version, 0)
        self.assertEqual(node.cversion, 0)

    def test_znode_ephemeral(self):
        node = ZNode('/eph', b'', ZNode.EPHEMERAL, 'sess1')
        self.assertTrue(node.is_ephemeral())
        self.assertFalse(node.is_sequential())
        self.assertEqual(node.owner_session, 'sess1')

    def test_znode_sequential(self):
        node = ZNode('/seq', b'', ZNode.PERSISTENT_SEQUENTIAL)
        self.assertFalse(node.is_ephemeral())
        self.assertTrue(node.is_sequential())

    def test_znode_ephemeral_sequential(self):
        node = ZNode('/ephseq', b'', ZNode.EPHEMERAL_SEQUENTIAL, 'sess2')
        self.assertTrue(node.is_ephemeral())
        self.assertTrue(node.is_sequential())

    def test_znode_update_data(self):
        node = ZNode('/test', b'v1')
        self.assertEqual(node.version, 0)
        node.update_data(b'v2')
        self.assertEqual(node.data, b'v2')
        self.assertEqual(node.version, 1)

    def test_znode_to_dict(self):
        node = ZNode('/test', b'data', ZNode.EPHEMERAL, 'sess1')
        d = node.to_dict()
        self.assertEqual(d['path'], '/test')
        self.assertEqual(d['data'], 'data')
        self.assertEqual(d['node_type'], 'EPHEMERAL')
        self.assertEqual(d['version'], 0)
        self.assertEqual(d['children'], [])


class TestZNodeTree(unittest.TestCase):
    """测试树形命名空间"""

    def setUp(self):
        self.tree = ZNodeTree()

    # 1. 创建永久节点
    def test_create_persistent(self):
        node = self.tree.create('/app', b'my_data')
        self.assertIsNotNone(node)
        self.assertEqual(node.path, '/app')
        self.assertEqual(self.tree.get_data('/app'), b'my_data')

    # 2. 读取节点数据
    def test_get_data(self):
        self.tree.create('/app', b'hello')
        data = self.tree.get_data('/app')
        self.assertEqual(data, b'hello')

    # 3. 设置节点数据 + 版本递增
    def test_set_data_version_increment(self):
        self.tree.create('/app', b'v1')
        node = self.tree.set_data('/app', b'v2')
        self.assertIsNotNone(node)
        self.assertEqual(node.version, 1)
        self.assertEqual(self.tree.get_data('/app'), b'v2')

    # 4. 删除节点（无子节点）
    def test_delete_node(self):
        self.tree.create('/app', b'data')
        result = self.tree.delete('/app')
        self.assertTrue(result)
        self.assertFalse(self.tree.exists('/app'))

    # 5. 删除有子节点的节点失败
    def test_delete_node_with_children_fails(self):
        self.tree.create('/app', b'data')
        self.tree.create('/app/sub', b'child')
        result = self.tree.delete('/app')
        self.assertFalse(result)
        self.assertTrue(self.tree.exists('/app'))

    # 6. 节点不存在的 GET 返回 None
    def test_get_nonexistent(self):
        data = self.tree.get_data('/nonexistent')
        self.assertIsNone(data)

    # 7. 获取子节点列表
    def test_get_children(self):
        self.tree.create('/app')
        self.tree.create('/app/a')
        self.tree.create('/app/b')
        children = self.tree.get_children('/app')
        self.assertEqual(children, ['a', 'b'])

    # 8. 节点 EXISTS
    def test_exists(self):
        self.tree.create('/app')
        self.assertTrue(self.tree.exists('/app'))
        self.assertFalse(self.tree.exists('/nonexistent'))

    # 9. 创建临时节点
    def test_create_ephemeral(self):
        node = self.tree.create('/eph', b'eph_data', ZNode.EPHEMERAL, 'sess1')
        self.assertIsNotNone(node)
        self.assertTrue(node.is_ephemeral())
        self.assertEqual(self.tree.get_data('/eph'), b'eph_data')

    # 10. 创建顺序节点（命名递增）
    def test_create_sequential(self):
        n1 = self.tree.create('/seq', b'', ZNode.PERSISTENT_SEQUENTIAL)
        n2 = self.tree.create('/seq', b'', ZNode.PERSISTENT_SEQUENTIAL)
        self.assertIsNotNone(n1)
        self.assertIsNotNone(n2)
        self.assertNotEqual(n1.path, n2.path)
        self.assertLess(n1.path, n2.path)  # seq0000000001 < seq0000000002

    # 11. 创建临时顺序节点
    def test_create_ephemeral_sequential(self):
        node = self.tree.create('/ephseq', b'', ZNode.EPHEMERAL_SEQUENTIAL, 'sess2')
        self.assertIsNotNone(node)
        self.assertTrue(node.is_ephemeral())
        self.assertTrue(node.is_sequential())

    # 12. 路径 NOT_FOUND 返回 None
    def test_path_not_found_returns_none(self):
        result = self.tree.create('/nonexistent/sub', b'data')
        self.assertIsNone(result)

    # 13. 创建已存在节点失败
    def test_create_existing_fails(self):
        self.tree.create('/app', b'data')
        result = self.tree.create('/app', b'data2')
        self.assertIsNone(result)

    # 14. 删除指定版本
    def test_delete_with_version(self):
        self.tree.create('/app', b'v1')
        result = self.tree.delete('/app', version=0)
        self.assertTrue(result)

    def test_delete_with_wrong_version_fails(self):
        self.tree.create('/app', b'v1')
        self.tree.set_data('/app', b'v2')  # now version=1
        result = self.tree.delete('/app', version=0)  # wrong version
        self.assertFalse(result)

    # 15. SET 指定版本
    def test_set_with_version(self):
        self.tree.create('/app', b'v1')
        node = self.tree.set_data('/app', b'v2', version=0)
        self.assertIsNotNone(node)

    def test_set_with_wrong_version_fails(self):
        self.tree.create('/app', b'v1')
        node = self.tree.set_data('/app', b'v2', version=99)
        self.assertIsNone(node)

    # 16. 清理临时节点（session 断开）
    def test_clean_ephemeral(self):
        self.tree.create('/persistent', b'stay')
        self.tree.create('/eph1', b'', ZNode.EPHEMERAL, 'sess1')
        self.tree.create('/eph2', b'', ZNode.EPHEMERAL, 'sess1')
        self.tree.create('/other_eph', b'', ZNode.EPHEMERAL, 'sess2')

        removed = self.tree.clean_ephemeral('sess1')
        self.assertEqual(len(removed), 2)
        self.assertIn('/eph1', removed)
        self.assertIn('/eph2', removed)

        # persistent 还在
        self.assertTrue(self.tree.exists('/persistent'))
        # 其他 session 的临时节点还在
        self.assertTrue(self.tree.exists('/other_eph'))
        # 清理掉的没有了
        self.assertFalse(self.tree.exists('/eph1'))


class TestSession(unittest.TestCase):
    """测试 Session 管理（不使用线程）"""

    def test_session_create(self):
        sess = Session('s1', timeout=10)
        self.assertEqual(sess.session_id, 's1')
        self.assertTrue(sess.active)
        self.assertFalse(sess.is_expired())

    def test_session_keepalive(self):
        sess = Session('s1', timeout=10)
        sess.last_heartbeat = 0  # 模拟过期
        # 先确实过期
        self.assertTrue(sess.is_expired())
        sess.keepalive()
        self.assertFalse(sess.is_expired())

    def test_session_expire(self):
        sess = Session('s1', timeout=0.01)
        time.sleep(0.02)
        self.assertTrue(sess.is_expired())

    def test_session_close(self):
        sess = Session('s1')
        sess.close()
        self.assertFalse(sess.active)


class TestSessionManager(unittest.TestCase):
    """测试 SessionManager（需要 daemon 线程）"""

    def setUp(self):
        self.tree = ZNodeTree()
        self.watcher = WatcherManager()
        self.sm = SessionManager(self.tree, self.watcher)

    def tearDown(self):
        self.sm.stop()

    # 17. Session 创建
    def test_session_create(self):
        sid = self.sm.create_session(timeout=10)
        self.assertIsNotNone(sid)
        self.assertIn(sid, self.sm.sessions)

    # 18. Session keepalive
    def test_keepalive(self):
        sid = self.sm.create_session(timeout=10)
        self.assertTrue(self.sm.keepalive(sid))
        self.assertFalse(self.sm.keepalive('nonexistent'))

    # 19. Session 过期
    def test_session_expiry(self):
        sid = self.sm.create_session(timeout=0.5)
        self.assertIn(sid, self.sm.sessions)
        time.sleep(1.5)
        self.assertNotIn(sid, self.sm.sessions)

    # 20. Session 过期清理临时节点
    def test_session_expiry_cleans_ephemeral(self):
        sid = self.sm.create_session(timeout=0.3)
        self.tree.create('/eph_node', b'', ZNode.EPHEMERAL, sid)
        self.assertTrue(self.tree.exists('/eph_node'))
        time.sleep(1.5)
        self.assertFalse(self.tree.exists('/eph_node'))


class TestWatcher(unittest.TestCase):
    """测试 Watcher 通知系统"""

    def setUp(self):
        self.wm = WatcherManager()
        self.notified = []

    def _cb(self, evt):
        self.notified.append(evt)

    # 21. Watcher 注册
    def test_watch_register(self):
        self.wm.watch('/test', 'created', self._cb)
        self.wm.notify('/test', 'created')
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['type'], 'created')

    # 22. Watcher 通知
    def test_watch_notify_data_changed(self):
        self.wm.watch('/app', 'data_changed', self._cb)
        self.wm.notify('/app', 'data_changed', {'new_data': 'hello'})
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['type'], 'data_changed')
        self.assertEqual(self.notified[0]['path'], '/app')
        self.assertEqual(self.notified[0]['extra'], {'new_data': 'hello'})

    def test_watch_child_changed(self):
        self.wm.watch('/', 'child_changed', self._cb)
        self.wm.notify('/app', 'created')
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['path'], '/app')

    def test_watch_multiple_callbacks(self):
        results = []

        def cb1(evt):
            results.append('cb1')

        def cb2(evt):
            results.append('cb2')

        self.wm.watch('/test', 'created', cb1)
        self.wm.watch('/test', 'created', cb2)
        self.wm.notify('/test', 'created')
        self.assertEqual(len(results), 2)

    def test_watch_unwatch(self):
        self.wm.watch('/test', 'created', self._cb)
        self.wm.unwatch('/test', 'created', self._cb)
        self.wm.notify('/test', 'created')
        self.assertEqual(len(self.notified), 0)


class TestIntegrationTree(unittest.TestCase):
    """集成测试：ZNodeTree + Session + Watcher 协同"""

    def setUp(self):
        self.tree = ZNodeTree()
        self.watcher = WatcherManager()
        self.sm = SessionManager(self.tree, self.watcher)
        self.notified = []

    def tearDown(self):
        self.sm.stop()

    def _cb(self, evt):
        self.notified.append(evt)

    def test_create_triggers_watcher(self):
        self.watcher.watch('/', 'child_changed', self._cb)
        self.tree.create('/app', b'data')
        self.watcher.notify('/app', 'created')
        # notify triggers: direct 'created' on /app, plus parent '/' gets 'child_changed' callback
        # The callback fires with the original event type 'created'
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['type'], 'created')

    def test_delete_triggers_watcher(self):
        self.tree.create('/app', b'data')
        self.watcher.watch('/app', 'deleted', self._cb)
        self.tree.delete('/app')
        self.watcher.notify('/app', 'deleted')
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['type'], 'deleted')

    def test_set_triggers_watcher(self):
        self.tree.create('/app', b'v1')
        self.watcher.watch('/app', 'data_changed', self._cb)
        self.tree.set_data('/app', b'v2')
        self.watcher.notify('/app', 'data_changed')
        self.assertEqual(len(self.notified), 1)

    def test_session_close_cleans_ephemeral_and_notifies(self):
        sid = self.sm.create_session()
        self.tree.create('/eph', b'', ZNode.EPHEMERAL, sid)
        self.watcher.watch('/eph', 'deleted', self._cb)
        self.sm.close_session(sid)
        self.assertFalse(self.tree.exists('/eph'))
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(self.notified[0]['type'], 'deleted')

    def test_stat(self):
        self.tree.create('/app', b'hello')
        st = self.tree.stat('/app')
        self.assertIsNotNone(st)
        self.assertEqual(st['path'], '/app')
        self.assertEqual(st['data'], 'hello')

    def test_stat_nonexistent(self):
        st = self.tree.stat('/nothing')
        self.assertIsNone(st)

    def test_root_children(self):
        self.tree.create('/a')
        self.tree.create('/b')
        self.tree.create('/c')
        children = self.tree.get_children('/')
        self.assertEqual(children, ['a', 'b', 'c'])

    def test_deep_path(self):
        self.tree.create('/a')
        self.tree.create('/a/b')
        self.tree.create('/a/b/c', b'deep')
        self.assertTrue(self.tree.exists('/a/b/c'))
        self.assertEqual(self.tree.get_data('/a/b/c'), b'deep')

    def test_create_root_fails(self):
        result = self.tree.create('/', b'')
        self.assertIsNone(result)

    def test_delete_root_fails(self):
        result = self.tree.delete('/')
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
