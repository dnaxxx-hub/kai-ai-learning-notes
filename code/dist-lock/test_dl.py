"""
Distributed Lock — 完整测试套件 (>= 18 tests)

Tests 1-15: Pure unit tests (no server needed)
Test 16: Server integration tests (run separately via test_server.py)
"""

import unittest
import threading
import time
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lock import Lock, ReentrantLock, ReadWriteLock, FairLock
from lock_manager import LockManager
from protocol import encode_response, decode_request


class MockManager:
    pass


MGR = MockManager()


# ═══════════════════════════════════════════════════════════════
# 1-4. Lock Tests
# ═══════════════════════════════════════════════════════════════

class TestLockBasic(unittest.TestCase):
    """1. Lock: acquire + release"""

    def setUp(self):
        self.lock = Lock('test_lock', MGR)

    def test_acquire_and_release(self):
        r = self.lock.acquire('client1')
        self.assertTrue(r['acquired'])
        self.assertEqual(r['owner'], 'client1')
        self.assertTrue(self.lock.is_locked())

        r2 = self.lock.release('client1')
        self.assertTrue(r2['released'])
        self.assertFalse(self.lock.is_locked())

    def test_release_not_owner(self):
        self.lock.acquire('client1')
        r = self.lock.release('client2')
        self.assertFalse(r['released'])
        self.assertEqual(r['reason'], 'not_owner')
        self.assertTrue(self.lock.is_locked())
        self.lock.release('client1')

    def test_status_method(self):
        self.lock.acquire('client_s')
        s = self.lock.status()
        self.assertEqual(s['name'], 'test_lock')
        self.assertEqual(s['owner'], 'client_s')
        self.assertEqual(s['queue_length'], 0)
        self.lock.release('client_s')


class TestLockBlocking(unittest.TestCase):
    """2. Lock: 已被占有时阻塞"""

    def test_blocking_wait(self):
        lock = Lock('block_lock', MGR)
        lock.acquire('owner')

        results = []

        def waiter():
            r = lock.acquire('waiter1')
            results.append(r['acquired'])
            results.append(r['owner'])

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.1)
        lock.release('owner')
        t.join(timeout=1)

        self.assertTrue(results[0], "Waiter should acquire after release")
        self.assertEqual(results[1], 'waiter1')
        lock.release('waiter1')


class TestLockNonBlocking(unittest.TestCase):
    """3. Lock: 非阻塞 acquire 失败"""

    def test_non_blocking_fail(self):
        lock = Lock('nb_lock', MGR)
        lock.acquire('owner')
        r = lock.acquire('client2', blocking=False)
        self.assertFalse(r['acquired'])
        self.assertEqual(r['reason'], 'locked')
        lock.release('owner')


class TestLockTimeout(unittest.TestCase):
    """4. Lock: 超时 acquire 超时"""

    def test_timeout(self):
        lock = Lock('timeout_lock', MGR)
        lock.acquire('owner')

        start = time.time()
        r = lock.acquire('client2', timeout=0.1)
        elapsed = time.time() - start

        self.assertFalse(r['acquired'])
        self.assertEqual(r['reason'], 'timeout')
        self.assertGreaterEqual(elapsed, 0.08)
        lock.release('owner')


# ═══════════════════════════════════════════════════════════════
# 5-6. ReentrantLock Tests
# ═══════════════════════════════════════════════════════════════

class TestReentrantLock(unittest.TestCase):
    """5-6. ReentrantLock"""

    def test_reentrant_acquire(self):
        lock = ReentrantLock('re_lock', MGR)
        r1 = lock.acquire('client1')
        self.assertTrue(r1['acquired'])

        r2 = lock.acquire('client1')
        self.assertTrue(r2['acquired'])
        self.assertTrue(r2.get('reentrant'))

        lock.release('client1')  # still held (count 1)
        self.assertTrue(lock.is_locked())

        lock.release('client1')  # fully released
        self.assertFalse(lock.is_locked())

    def test_reentrant_match_release_count(self):
        lock = ReentrantLock('re_lock2', MGR)
        lock.acquire('client1')
        lock.acquire('client1')
        lock.acquire('client1')

        self.assertTrue(lock.is_locked())
        lock.release('client1')
        lock.release('client1')
        lock.release('client1')
        self.assertFalse(lock.is_locked())

    def test_reentrant_other_cannot_acquire(self):
        lock = ReentrantLock('re_lock3', MGR)
        lock.acquire('client1')
        r = lock.acquire('client2', blocking=False)
        self.assertFalse(r['acquired'])
        lock.release('client1')
        self.assertFalse(lock.is_locked())

    def test_reentrant_release_excess(self):
        lock = ReentrantLock('re_lock4', MGR)
        lock.acquire('client1')
        # release one more than acquired
        lock.release('client1')  # count 1->0, fully released
        r = lock.release('client1')
        self.assertFalse(r['released'])


# ═══════════════════════════════════════════════════════════════
# 7-10. ReadWriteLock Tests
# ═══════════════════════════════════════════════════════════════

class TestReadWriteLock(unittest.TestCase):
    """7-10. ReadWriteLock"""

    def setUp(self):
        self.rw = ReadWriteLock('rw_test', MGR)

    def test_read_read_share(self):
        """7. 读读共享"""
        r1 = self.rw.acquire_read('reader1')
        self.assertTrue(r1['acquired'])
        r2 = self.rw.acquire_read('reader2')
        self.assertTrue(r2['acquired'])
        self.rw.release_read('reader1')
        self.rw.release_read('reader2')

    def test_read_write_mutex(self):
        """8. 读写互斥"""
        self.rw.acquire_read('reader1')
        r = self.rw.acquire_write('writer1', timeout=0)
        self.assertFalse(r['acquired'])
        self.rw.release_read('reader1')

    def test_write_write_mutex(self):
        """9. 写写互斥"""
        self.rw.acquire_write('writer1')
        r = self.rw.acquire_write('writer2', timeout=0)
        self.assertFalse(r['acquired'])
        self.rw.release_write('writer1')

    def test_release_read_write(self):
        """10. release_read / release_write"""
        self.rw.acquire_read('r1')
        r = self.rw.release_read('r1')
        self.assertTrue(r['released'])

        self.rw.acquire_write('w1')
        r = self.rw.release_write('w1')
        self.assertTrue(r['released'])

    def test_release_not_reader(self):
        self.rw.acquire_read('r1')
        r = self.rw.release_read('r2')
        self.assertFalse(r['released'])
        self.rw.release_read('r1')

    def test_release_not_writer(self):
        self.rw.acquire_write('w1')
        r = self.rw.release_write('w2')
        self.assertFalse(r['released'])
        self.rw.release_write('w1')

    def test_read_after_write_release(self):
        self.rw.acquire_write('w1')
        self.rw.release_write('w1')
        r = self.rw.acquire_read('r1')
        self.assertTrue(r['acquired'])
        self.rw.release_read('r1')

    def test_rw_timeout(self):
        self.rw.acquire_write('w1')
        r = self.rw.acquire_read('r_timeout', timeout=0.05)
        self.assertFalse(r['acquired'])
        self.rw.release_write('w1')

    def test_write_after_read_release(self):
        self.rw.acquire_read('r1')
        self.rw.acquire_read('r2')
        self.rw.release_read('r1')
        self.rw.release_read('r2')
        r = self.rw.acquire_write('w1')
        self.assertTrue(r['acquired'])
        self.rw.release_write('w1')

    def test_rw_status(self):
        self.rw.acquire_read('r1')
        self.rw.acquire_read('r2')
        s = self.rw.status()
        self.assertEqual(s['type'], 'readwrite')
        self.assertIn('r1', s['readers'])
        self.assertIn('r2', s['readers'])
        self.assertIsNone(s['writer'])
        self.rw.release_read('r1')
        self.rw.release_read('r2')


# ═══════════════════════════════════════════════════════════════
# 11. FairLock Tests
# ═══════════════════════════════════════════════════════════════

class TestFairLock(unittest.TestCase):
    """11. FairLock: FIFO 顺序"""

    def test_fifo_order(self):
        lock = FairLock('fair_test', MGR)
        lock.acquire('owner')

        results = []

        def waiter(cid):
            r = lock.acquire(cid)
            results.append(cid)

        t1 = threading.Thread(target=waiter, args=('A',))
        t2 = threading.Thread(target=waiter, args=('B',))
        t3 = threading.Thread(target=waiter, args=('C',))

        t1.start()
        time.sleep(0.05)
        t2.start()
        time.sleep(0.05)
        t3.start()

        time.sleep(0.1)

        # Release one at a time
        lock.release('owner')
        time.sleep(0.15)
        self.assertEqual(results[0], 'A')

        lock.release('A')
        time.sleep(0.15)
        self.assertEqual(results[1], 'B')

        lock.release('B')
        time.sleep(0.15)
        self.assertEqual(results[2], 'C')

        lock.release('C')
        for t in (t1, t2, t3):
            t.join(timeout=1)

    def test_fair_non_blocking(self):
        lock = FairLock('fair_nb', MGR)
        lock.acquire('owner')
        r = lock.acquire('client2', blocking=False)
        self.assertFalse(r['acquired'])
        lock.release('owner')

    def test_fair_timeout(self):
        lock = FairLock('fair_to', MGR)
        lock.acquire('owner')
        r = lock.acquire('client2', timeout=0.05)
        self.assertFalse(r['acquired'])
        lock.release('owner')


# ═══════════════════════════════════════════════════════════════
# 12-14. LockManager Tests
# ═══════════════════════════════════════════════════════════════

class TestLockManager(unittest.TestCase):
    """12-14. LockManager"""

    def setUp(self):
        self.mgr = LockManager()

    def test_multi_lock_independent(self):
        """12. 多锁独立"""
        r1 = self.mgr.acquire('lock_a', 'client1')
        self.assertTrue(r1['acquired'])
        r2 = self.mgr.acquire('lock_b', 'client2')
        self.assertTrue(r2['acquired'])
        self.mgr.release('lock_a', 'client1')
        self.mgr.release('lock_b', 'client2')

    def test_status(self):
        """13. 锁的 STATUS"""
        self.mgr.acquire('stat_lock', 'clientX')
        s = self.mgr.status('stat_lock')
        self.assertEqual(s['name'], 'stat_lock')
        self.assertEqual(s['owner'], 'clientX')

        all_s = self.mgr.status()
        self.assertIn('stat_lock', all_s)
        self.mgr.release('stat_lock', 'clientX')

    def test_status_not_found(self):
        s = self.mgr.status('nonexistent')
        self.assertIn('error', s)

    def test_list_locks(self):
        self.mgr.acquire('lst1', 'c1')
        self.mgr.acquire('lst2', 'c2')
        locks = self.mgr.list_locks()
        self.assertIn('lst1', locks)
        self.assertIn('lst2', locks)
        self.mgr.release('lst1', 'c1')
        self.mgr.release('lst2', 'c2')

    def test_release_no_lock(self):
        r = self.mgr.release('no_such_lock', 'client')
        self.assertFalse(r['released'])
        self.assertEqual(r['reason'], 'no_such_lock')

    def test_lock_types(self):
        """14. 不同类型的锁"""
        r1 = self.mgr.acquire('re_lock', 'c1', 'reentrant')
        self.assertTrue(r1['acquired'])
        r1b = self.mgr.acquire('re_lock', 'c1', 'reentrant')
        self.assertTrue(r1b['reentrant'])
        self.mgr.release('re_lock', 'c1')
        self.mgr.release('re_lock', 'c1')

        r2 = self.mgr.acquire('fair_lock', 'c2', 'fair')
        self.assertTrue(r2['acquired'])
        self.mgr.release('fair_lock', 'c2')

        r3 = self.mgr.acquire('rw_lock', 'c3', 'readwrite')
        self.assertTrue(r3['acquired'])
        self.mgr.release('rw_lock', 'c3')

    def test_acquire_write_method(self):
        r = self.mgr.acquire_write('rw_method', 'w1')
        self.assertTrue(r['acquired'])
        self.assertEqual(r['mode'], 'write')
        self.mgr.release('rw_method', 'w1', 'write')

    def test_release_with_mode_rw(self):
        self.mgr.acquire('mode_rw', 'c1', 'readwrite')
        r = self.mgr.release('mode_rw', 'c1', 'read')
        self.assertTrue(r['released'])

    def test_release_not_owned_by_different_client(self):
        self.mgr.acquire('owner_lock', 'owner1')
        r = self.mgr.release('owner_lock', 'owner2')
        self.assertFalse(r['released'])


# ═══════════════════════════════════════════════════════════════
# 15. Protocol Tests
# ═══════════════════════════════════════════════════════════════

class TestProtocol(unittest.TestCase):
    """15. 协议编码/解码"""

    def test_encode_response_success(self):
        s = encode_response(True, {'hello': 'world'})
        obj = json.loads(s.strip())
        self.assertTrue(obj['ok'])
        self.assertEqual(obj['data']['hello'], 'world')
        self.assertTrue(s.endswith('\n'))

    def test_encode_response_error(self):
        s = encode_response(False, error='something wrong')
        obj = json.loads(s.strip())
        self.assertFalse(obj['ok'])
        self.assertEqual(obj['error'], 'something wrong')

    def test_decode_request(self):
        cmd, args = decode_request('LOCK res1 mutex')
        self.assertEqual(cmd, 'LOCK')
        self.assertEqual(args, ['res1', 'mutex'])

    def test_decode_request_empty(self):
        cmd, args = decode_request('')
        self.assertEqual(cmd, '')
        self.assertEqual(args, [])

    def test_decode_request_no_args(self):
        cmd, args = decode_request('LIST')
        self.assertEqual(cmd, 'LIST')
        self.assertEqual(args, [])

    def test_decode_request_extra_spaces(self):
        cmd, args = decode_request('  HELP   ')
        self.assertEqual(cmd, 'HELP')
        self.assertEqual(args, [])

    def test_encode_response_none_data(self):
        s = encode_response(True)
        obj = json.loads(s.strip())
        self.assertTrue(obj['ok'])
        self.assertNotIn('data', obj)


# ═══════════════════════════════════════════════════════════════
# Count tests
# ═══════════════════════════════════════════════════════════════

def count_tests():
    """Count all test methods"""
    import inspect
    total = 0
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj.__module__ == __name__:
            for m in dir(obj):
                if m.startswith('test_'):
                    total += 1
    return total


if __name__ == '__main__':
    print(f"Total test methods: {count_tests()}")
    unittest.main(verbosity=2)
