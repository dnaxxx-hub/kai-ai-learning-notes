"""MiniDB 测试"""

import os
import unittest
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from btree import BPlusTree, BPlusTreeNode
from db import MiniDB


class TestBPlusTreeNode(unittest.TestCase):
    """测试 1: B+树节点结构正确"""

    def test_node_creation(self):
        node = BPlusTreeNode(is_leaf=True)
        self.assertTrue(node.is_leaf)
        self.assertEqual(node.keys, [])
        self.assertEqual(node.children, [])
        self.assertIsNone(node.next)
        self.assertIsNone(node.parent)

    def test_internal_node_creation(self):
        node = BPlusTreeNode(is_leaf=False)
        self.assertFalse(node.is_leaf)


class TestBPlusTreeInsertAndSearch(unittest.TestCase):
    """测试 2: 插入数据并精确查找"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_insert_and_search(self):
        self.tree.insert(10, 'ten')
        self.tree.insert(20, 'twenty')
        self.tree.insert(5, 'five')
        self.assertEqual(self.tree.search(10), 'ten')
        self.assertEqual(self.tree.search(20), 'twenty')
        self.assertEqual(self.tree.search(5), 'five')
        self.assertIsNone(self.tree.search(99))

    def test_insert_and_search_many(self):
        for i in range(100):
            self.tree.insert(i, f'val-{i}')
        for i in range(100):
            self.assertEqual(self.tree.search(i), f'val-{i}')
        self.assertIsNone(self.tree.search(200))


class TestBPlusTreeUpdate(unittest.TestCase):
    """测试 3: 更新/覆盖已有键"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_update_value(self):
        self.tree.insert(10, 'ten')
        self.assertEqual(self.tree.search(10), 'ten')
        self.tree.insert(10, 'TEN')
        self.assertEqual(self.tree.search(10), 'TEN')

    def test_multiple_updates(self):
        self.tree.insert(1, 'a')
        self.tree.insert(1, 'b')
        self.tree.insert(1, 'c')
        self.assertEqual(self.tree.search(1), 'c')


class TestBPlusTreeDelete(unittest.TestCase):
    """测试 4: 删除键"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_delete_simple(self):
        self.tree.insert(10, 'ten')
        self.assertEqual(self.tree.search(10), 'ten')
        result = self.tree.delete(10)
        self.assertTrue(result)
        self.assertIsNone(self.tree.search(10))

    def test_delete_nonexistent(self):
        result = self.tree.delete(99)
        self.assertFalse(result)

    def test_delete_from_many(self):
        for i in range(20):
            self.tree.insert(i, f'val-{i}')
        for i in range(10):
            self.tree.delete(i)
        for i in range(10):
            self.assertIsNone(self.tree.search(i))
        for i in range(10, 20):
            self.assertEqual(self.tree.search(i), f'val-{i}')

    def test_delete_all(self):
        for i in range(10):
            self.tree.insert(i, f'val-{i}')
        for i in range(10):
            self.tree.delete(i)
        self.assertIsNone(self.tree.search(0))
        self.assertIsNone(self.tree.search(9))
        self.assertTrue(self.tree.root.is_leaf)


class TestDeleteReturnsNone(unittest.TestCase):
    """测试 8: 删除后查找返回 None"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_delete_then_search(self):
        self.tree.insert(1, 'one')
        self.tree.insert(2, 'two')
        self.tree.insert(3, 'three')
        self.tree.delete(2)
        self.assertIsNone(self.tree.search(2))
        self.assertEqual(self.tree.search(1), 'one')
        self.assertEqual(self.tree.search(3), 'three')

    def test_delete_all_then_search(self):
        for i in range(20):
            self.tree.insert(i, f'val-{i}')
        for i in range(20):
            self.tree.delete(i)
        for i in range(20):
            self.assertIsNone(self.tree.search(i))


class TestRangeQuery(unittest.TestCase):
    """测试 5: 范围查询"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_range_query(self):
        for i in range(0, 100, 10):
            self.tree.insert(i, f'val-{i}')
        results = self.tree.range_query(20, 60)
        self.assertEqual(len(results), 4)
        expected = [(20, 'val-20'), (30, 'val-30'), (40, 'val-40'), (50, 'val-50')]
        self.assertEqual(results, expected)

    def test_range_query_all(self):
        for i in range(10):
            self.tree.insert(i, f'val-{i}')
        results = self.tree.range_query(0)
        self.assertEqual(len(results), 10)

    def test_range_query_empty(self):
        results = self.tree.range_query(0, 100)
        self.assertEqual(results, [])

    def test_range_query_single(self):
        self.tree.insert(50, 'fifty')
        results = self.tree.range_query(50, 51)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], (50, 'fifty'))


class TestBulkInsert(unittest.TestCase):
    """测试 7: 大量插入 (1000 条) 保持正确"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def test_bulk_insert(self):
        for i in range(1000):
            self.tree.insert(i, f'val-{i}')
        self.assertEqual(self.tree.search(0), 'val-0')
        self.assertEqual(self.tree.search(500), 'val-500')
        self.assertEqual(self.tree.search(999), 'val-999')
        self.assertIsNone(self.tree.search(1000))

    def test_bulk_insert_reverse(self):
        for i in range(999, -1, -1):
            self.tree.insert(i, f'val-{i}')
        for i in range(1000):
            self.assertEqual(self.tree.search(i), f'val-{i}')

    def test_bulk_range(self):
        for i in range(1000):
            self.tree.insert(i, f'val-{i}')
        results = self.tree.range_query(100, 200)
        self.assertEqual(len(results), 100)
        self.assertEqual(results[0][0], 100)
        self.assertEqual(results[-1][0], 199)


class TestBalance(unittest.TestCase):
    """额外: B+树插入删除保持平衡"""

    def setUp(self):
        self.tree = BPlusTree(order=4)

    def check_invariant(self, node=None):
        """检查 B+树不变式"""
        if node is None:
            node = self.tree.root
        # 非根节点：键数在 [min_keys, max_keys] 范围内
        if node is not self.tree.root:
            self.assertGreaterEqual(len(node.keys), self.tree.min_keys,
                                    f"非根节点 {node} 键数 {len(node.keys)} < min {self.tree.min_keys}")
        # 所有节点键数不超过 max_keys
        self.assertLessEqual(len(node.keys), self.tree.max_keys,
                             f"节点 {node} 键数 {len(node.keys)} > max {self.tree.max_keys}")
        # 内部节点: children = keys + 1
        if not node.is_leaf:
            self.assertEqual(len(node.children), len(node.keys) + 1,
                             f"内部节点 children({len(node.children)}) != keys({len(node.keys)})+1")
            for child in node.children:
                self.check_invariant(child)

    def verify_leaf_keys(self):
        """验证所有叶子节点中的不重复键总数等于插入的键数"""
        if self.tree.root.is_leaf:
            return
        # Find first leaf
        leaf = self.tree.root
        while not leaf.is_leaf:
            leaf = leaf.children[0]

        total = 0
        seen = set()
        while leaf:
            for k in leaf.keys:
                self.assertNotIn(k, seen, f"重复键 {k}")
                seen.add(k)
                total += 1
            leaf = leaf.next
        return total

    def test_balance_after_inserts(self):
        for i in range(100):
            self.tree.insert(i, f'val-{i}')
        self.check_invariant(self.tree.root)

    def test_balance_after_delete(self):
        for i in range(20):
            self.tree.insert(i, f'val-{i}')
        for i in range(5, 15):
            self.tree.delete(i)
        self.check_invariant(self.tree.root)

    def test_insert_delete_cycle(self):
        for i in range(50):
            self.tree.insert(i, f'val-{i}')
        for i in range(25):
            self.tree.delete(i)
        self.check_invariant(self.tree.root)


class TestPersistence(unittest.TestCase):
    """测试 6: 持久化保存再加载后数据一致性"""

    def setUp(self):
        self.db_file = 'test_persist.dat'
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        try:
            if os.path.exists(self.db_file):
                os.remove(self.db_file)
        except PermissionError:
            pass

    def test_save_and_load(self):
        db = MiniDB(self.db_file, order=4)
        db.put(10, 'ten')
        db.put(20, 'twenty')
        db.put(30, 'thirty')
        db.save()
        db.close()

        db2 = MiniDB(self.db_file, order=4)
        loaded = db2.load()
        self.assertTrue(loaded)
        self.assertEqual(db2.get(10), 'ten')
        self.assertEqual(db2.get(20), 'twenty')
        self.assertEqual(db2.get(30), 'thirty')
        self.assertIsNone(db2.get(99))
        db2.close()

    def test_save_load_many(self):
        db = MiniDB(self.db_file, order=4)
        for i in range(50):
            db.put(i, f'value-{i}')
        db.save()
        db.close()

        db2 = MiniDB(self.db_file, order=4)
        db2.load()
        for i in range(50):
            self.assertEqual(db2.get(i), f'value-{i}')
        db2.close()

    def test_save_load_update(self):
        db = MiniDB(self.db_file, order=4)
        db.put(1, 'one')
        db.put(2, 'two')
        db.save()
        db.close()

        db2 = MiniDB(self.db_file, order=4)
        db2.load()
        db2.put(2, 'TWO')
        db2.put(3, 'three')
        db2.save()
        db2.close()

        db3 = MiniDB(self.db_file, order=4)
        db3.load()
        self.assertEqual(db3.get(1), 'one')
        self.assertEqual(db3.get(2), 'TWO')
        self.assertEqual(db3.get(3), 'three')
        db3.close()

    def test_delete_persistence(self):
        db = MiniDB(self.db_file, order=4)
        for i in range(10):
            db.put(i, f'val-{i}')
        db.save()
        db.close()

        db2 = MiniDB(self.db_file, order=4)
        db2.load()
        db2.delete(5)
        db2.save()
        db2.close()

        db3 = MiniDB(self.db_file, order=4)
        db3.load()
        self.assertIsNone(db3.get(5))
        self.assertEqual(db3.get(4), 'val-4')
        self.assertEqual(db3.get(6), 'val-6')
        db3.close()


class TestMiniDBAPI(unittest.TestCase):
    """MiniDB API 集成测试"""

    def setUp(self):
        self.db_file = 'test_minidb_api.dat'
        try:
            if os.path.exists(self.db_file):
                os.remove(self.db_file)
        except PermissionError:
            pass

    def tearDown(self):
        try:
            if os.path.exists(self.db_file):
                os.remove(self.db_file)
        except PermissionError:
            pass

    def test_put_get(self):
        db = MiniDB(self.db_file)
        db.put(1, 'hello')
        self.assertEqual(db.get(1), 'hello')
        db.close()

    def test_put_get_delete(self):
        db = MiniDB(self.db_file)
        db.put(1, 'hello')
        db.put(2, 'world')
        self.assertEqual(db.get(1), 'hello')
        self.assertTrue(db.delete(1))
        self.assertIsNone(db.get(1))
        self.assertEqual(db.get(2), 'world')
        db.close()

    def test_range_persistence(self):
        db = MiniDB(self.db_file)
        for i in range(0, 50, 5):
            db.put(i, f'val-{i}')
        db.save()
        db.close()

        db2 = MiniDB(self.db_file)
        db2.load()
        results = db2.range(10, 30)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0], (10, 'val-10'))
        self.assertEqual(results[-1], (25, 'val-25'))
        db2.close()

    def test_stats(self):
        db = MiniDB(self.db_file)
        for i in range(100):
            db.put(i, f'val-{i}')
        s = db.stats()
        self.assertIn('order', s)
        self.assertIn('height', s)
        self.assertIn('total_nodes', s)
        self.assertIn('total_keys', s)
        # total_keys counts ALL keys in the tree (internal + leaf)
        # It should be >= 100
        self.assertGreaterEqual(s['total_keys'], 100)
        self.assertEqual(s['order'], 4)
        db.close()


if __name__ == '__main__':
    unittest.main()
