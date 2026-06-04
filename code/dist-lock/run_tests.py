"""Standalone test runner — imports directly from the project dir."""
import sys
import os
import time
import json

# Ensure we can import from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lock import Lock, ReentrantLock, ReadWriteLock, FairLock
from lock_manager import LockManager
from protocol import encode_response, decode_request


class MockManager:
    pass


MGR = MockManager()
passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        import traceback
        traceback.print_exc()
        failed += 1


def assert_eq(a, b, msg=""):
    assert a == b, f"{msg} expected {b!r}, got {a!r}"


def assert_true(v, msg=""):
    assert v, msg


def assert_false(v, msg=""):
    assert not v, msg


# ══════════════════════════════════════════════════════════
# 1-4. Lock
# ══════════════════════════════════════════════════════════

def test_1_acquire_release():
    lock = Lock('t1', MGR)
    r = lock.acquire('c1')
    assert_true(r['acquired'])
    assert_eq(r['owner'], 'c1')
    assert_true(lock.is_locked())

    r2 = lock.release('c1')
    assert_true(r2['released'])
    assert_false(lock.is_locked())


def test_2_blocking_wait():
    lock = Lock('t2', MGR)
    lock.acquire('owner')
    results = []

    def waiter():
        r = lock.acquire('w')
        results.append(r['acquired'])

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)
    lock.release('owner')
    t.join(timeout=1)
    assert_true(results[0], "waiter should get lock")
    lock.release('w')


def test_3_non_blocking():
    lock = Lock('t3', MGR)
    lock.acquire('owner')
    r = lock.acquire('c2', blocking=False)
    assert_false(r['acquired'])
    assert_eq(r['reason'], 'locked')
    lock.release('owner')


def test_4_timeout():
    lock = Lock('t4', MGR)
    lock.acquire('owner')
    start = time.time()
    r = lock.acquire('c2', timeout=0.05)
    elapsed = time.time() - start
    assert_false(r['acquired'])
    assert_eq(r['reason'], 'timeout')
    assert_true(elapsed >= 0.04)
    lock.release('owner')


def test_release_not_owner():
    lock = Lock('t', MGR)
    lock.acquire('c1')
    r = lock.release('c2')
    assert_false(r['released'])
    assert_eq(r['reason'], 'not_owner')
    lock.release('c1')


def test_status():
    lock = Lock('t', MGR)
    lock.acquire('c1')
    s = lock.status()
    assert_eq(s['name'], 't')
    assert_eq(s['owner'], 'c1')
    assert_eq(s['queue_length'], 0)
    lock.release('c1')


# ══════════════════════════════════════════════════════════
# 5-6. ReentrantLock
# ══════════════════════════════════════════════════════════

def test_5_reentrant_acquire():
    lock = ReentrantLock('t5', MGR)
    r1 = lock.acquire('c1')
    assert_true(r1['acquired'])
    r2 = lock.acquire('c1')
    assert_true(r2['acquired'])
    assert_true(r2.get('reentrant'))
    lock.release('c1')
    assert_true(lock.is_locked())
    lock.release('c1')
    assert_false(lock.is_locked())


def test_6_reentrant_count():
    lock = ReentrantLock('t6', MGR)
    lock.acquire('c1')
    lock.acquire('c1')
    lock.acquire('c1')
    assert_true(lock.is_locked())
    lock.release('c1')
    lock.release('c1')
    lock.release('c1')
    assert_false(lock.is_locked())


def test_reentrant_block_other():
    lock = ReentrantLock('t', MGR)
    lock.acquire('c1')
    r = lock.acquire('c2', blocking=False)
    assert_false(r['acquired'])
    lock.release('c1')
    assert_false(lock.is_locked())


# ══════════════════════════════════════════════════════════
# 7-10. ReadWriteLock
# ══════════════════════════════════════════════════════════

def test_7_read_read_share():
    rw = ReadWriteLock('t7', MGR)
    r1 = rw.acquire_read('r1')
    assert_true(r1['acquired'])
    r2 = rw.acquire_read('r2')
    assert_true(r2['acquired'])
    rw.release_read('r1')
    rw.release_read('r2')


def test_8_read_write_mutex():
    rw = ReadWriteLock('t8', MGR)
    rw.acquire_read('r1')
    r = rw.acquire_write('w1', timeout=0)
    assert_false(r['acquired'])
    rw.release_read('r1')


def test_9_write_write_mutex():
    rw = ReadWriteLock('t9', MGR)
    rw.acquire_write('w1')
    r = rw.acquire_write('w2', timeout=0)
    assert_false(r['acquired'])
    rw.release_write('w1')


def test_10_release_read_write():
    rw = ReadWriteLock('t10', MGR)
    rw.acquire_read('r1')
    r = rw.release_read('r1')
    assert_true(r['released'])

    rw.acquire_write('w1')
    r = rw.release_write('w1')
    assert_true(r['released'])


def test_rw_release_not_owner():
    rw = ReadWriteLock('t', MGR)
    rw.acquire_read('r1')
    r = rw.release_read('r2')
    assert_false(r['released'])
    rw.release_read('r1')


def test_rw_write_after_read_release():
    rw = ReadWriteLock('t', MGR)
    rw.acquire_read('r1')
    rw.release_read('r1')
    r = rw.acquire_write('w1')
    assert_true(r['acquired'])
    rw.release_write('w1')


def test_rw_status():
    rw = ReadWriteLock('t', MGR)
    rw.acquire_read('r1')
    s = rw.status()
    assert_eq(s['type'], 'readwrite')
    assert_in('r1', s['readers'])
    rw.release_read('r1')


def test_rw_timeout():
    rw = ReadWriteLock('t', MGR)
    rw.acquire_write('w1')
    r = rw.acquire_read('r', timeout=0.05)
    assert_false(r['acquired'])
    rw.release_write('w1')


# ══════════════════════════════════════════════════════════
# 11. FairLock
# ══════════════════════════════════════════════════════════

def test_11_fifo():
    lock = FairLock('t11', MGR)
    lock.acquire('owner')
    results = []

    def w(cid):
        lock.acquire(cid)
        results.append(cid)

    t1 = threading.Thread(target=w, args=('A',))
    t2 = threading.Thread(target=w, args=('B',))
    t3 = threading.Thread(target=w, args=('C',))
    t1.start()
    time.sleep(0.05)
    t2.start()
    time.sleep(0.05)
    t3.start()
    time.sleep(0.1)

    lock.release('owner')
    time.sleep(0.15)
    assert_eq(results[0], 'A', "FIFO: A first")
    lock.release('A')
    time.sleep(0.15)
    assert_eq(results[1], 'B', "FIFO: B second")
    lock.release('B')
    time.sleep(0.15)
    assert_eq(results[2], 'C', "FIFO: C third")
    lock.release('C')
    for t in (t1, t2, t3):
        t.join(timeout=1)


def test_fair_non_blocking():
    lock = FairLock('t', MGR)
    lock.acquire('owner')
    r = lock.acquire('c2', blocking=False)
    assert_false(r['acquired'])
    lock.release('owner')


# ══════════════════════════════════════════════════════════
# 12-14. LockManager
# ══════════════════════════════════════════════════════════

def test_12_multi_lock():
    m = LockManager()
    r1 = m.acquire('a', 'c1')
    assert_true(r1['acquired'])
    r2 = m.acquire('b', 'c2')
    assert_true(r2['acquired'])
    m.release('a', 'c1')
    m.release('b', 'c2')


def test_13_status():
    m = LockManager()
    m.acquire('s', 'c1')
    s = m.status('s')
    assert_eq(s['name'], 's')
    assert_eq(s['owner'], 'c1')
    all_s = m.status()
    assert_in('s', all_s)
    m.release('s', 'c1')


def test_14_lock_types():
    m = LockManager()
    # reentrant
    r1 = m.acquire('re', 'c1', 'reentrant')
    assert_true(r1['acquired'])
    r1b = m.acquire('re', 'c1', 'reentrant')
    assert_true(r1b['reentrant'])
    m.release('re', 'c1')
    m.release('re', 'c1')
    # fair
    r2 = m.acquire('f', 'c2', 'fair')
    assert_true(r2['acquired'])
    m.release('f', 'c2')
    # readwrite
    r3 = m.acquire('rw', 'c3', 'readwrite')
    assert_true(r3['acquired'])
    m.release('rw', 'c3')


def test_mgr_release_no_lock():
    m = LockManager()
    r = m.release('no', 'c')
    assert_false(r['released'])


def test_mgr_list():
    m = LockManager()
    m.acquire('l1', 'c1')
    m.acquire('l2', 'c1')
    locks = m.list_locks()
    assert_in('l1', locks)
    assert_in('l2', locks)
    m.release('l1', 'c1')
    m.release('l2', 'c1')


def test_mgr_acquire_write():
    m = LockManager()
    r = m.acquire_write('rw', 'w1')
    assert_true(r['acquired'])
    m.release('rw', 'w1', 'write')


# ══════════════════════════════════════════════════════════
# 15. Protocol
# ══════════════════════════════════════════════════════════

def test_15_encode_decode():
    s = encode_response(True, {'k': 'v'})
    obj = json.loads(s.strip())
    assert_true(obj['ok'])
    assert_eq(obj['data']['k'], 'v')
    assert_true(s.endswith('\n'))

    s2 = encode_response(False, error='err')
    obj2 = json.loads(s2.strip())
    assert_false(obj2['ok'])
    assert_eq(obj2['error'], 'err')

    cmd, args = decode_request('LOCK a b')
    assert_eq(cmd, 'LOCK')
    assert_eq(args, ['a', 'b'])

    cmd2, args2 = decode_request('')
    assert_eq(cmd2, '')

    cmd3, args3 = decode_request('LIST')
    assert_eq(cmd3, 'LIST')
    assert_eq(args3, [])

    s4 = encode_response(True)
    obj4 = json.loads(s4.strip())
    assert_true(obj4['ok'])
    assert_not_in('data', obj4)


# helpers
def assert_in(item, container):
    assert item in container, f"{item!r} not in {container!r}"


def assert_not_in(item, container):
    assert item not in container, f"{item!r} found in {container!r}"


# ══════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    import threading

    print("=== Distributed Lock Tests ===\n")

    tests = [
        # 1-4: Lock basic
        ("1. Lock: acquire + release", test_1_acquire_release),
        ("2. Lock: blocking wait", test_2_blocking_wait),
        ("3. Lock: non-blocking fail", test_3_non_blocking),
        ("4. Lock: timeout", test_4_timeout),
        ("   Lock: release not owner", test_release_not_owner),
        ("   Lock: status", test_status),
        # 5-6: ReentrantLock
        ("5. ReentrantLock: re-enter", test_5_reentrant_acquire),
        ("6. ReentrantLock: count match", test_6_reentrant_count),
        ("   ReentrantLock: block other", test_reentrant_block_other),
        # 7-10: ReadWriteLock
        ("7. ReadWriteLock: read-read share", test_7_read_read_share),
        ("8. ReadWriteLock: read-write mutex", test_8_read_write_mutex),
        ("9. ReadWriteLock: write-write mutex", test_9_write_write_mutex),
        ("10. ReadWriteLock: release", test_10_release_read_write),
        ("    ReadWriteLock: release not owner", test_rw_release_not_owner),
        ("    ReadWriteLock: write after read release", test_rw_write_after_read_release),
        ("    ReadWriteLock: status", test_rw_status),
        ("    ReadWriteLock: timeout", test_rw_timeout),
        # 11: FairLock
        ("11. FairLock: FIFO order", test_11_fifo),
        ("    FairLock: non-blocking", test_fair_non_blocking),
        # 12-14: LockManager
        ("12. LockManager: multi lock", test_12_multi_lock),
        ("13. LockManager: status", test_13_status),
        ("14. LockManager: lock types", test_14_lock_types),
        ("    LockManager: release no lock", test_mgr_release_no_lock),
        ("    LockManager: list locks", test_mgr_list),
        ("    LockManager: acquire_write", test_mgr_acquire_write),
        # 15: Protocol
        ("15. Protocol: encode/decode", test_15_encode_decode),
    ]

    print(f"Total test methods: {len(tests)}\n")

    for name, fn in tests:
        test(name, fn)

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    if failed > 0:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
