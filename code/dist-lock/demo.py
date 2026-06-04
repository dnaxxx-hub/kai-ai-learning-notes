"""
演示：使用 LockManager 进行各种锁操作
"""

import threading
import time
from lock_manager import LockManager


def demo_mutex():
    print("=" * 60)
    print("1. 互斥锁 (Mutex)")
    mgr = LockManager()
    r1 = mgr.acquire('resource1', 'client_A')
    print(f"  A acquire: {r1}")
    r2 = mgr.acquire('resource1', 'client_B', blocking=False)
    print(f"  B non-blocking acquire (should fail): {r2}")
    r3 = mgr.release('resource1', 'client_A')
    print(f"  A release: {r3}")
    r4 = mgr.acquire('resource1', 'client_B')
    print(f"  B acquire after release: {r4}")
    r5 = mgr.release('resource1', 'client_B')
    print(f"  B release: {r5}")
    print()


def demo_reentrant():
    print("=" * 60)
    print("2. 可重入锁 (Reentrant)")
    mgr = LockManager()
    r1 = mgr.acquire('rlock1', 'client_A', 'reentrant')
    print(f"  A acquire #1: {r1}")
    r2 = mgr.acquire('rlock1', 'client_A', 'reentrant')
    print(f"  A acquire #2 (should re-enter): {r2}")
    r3 = mgr.release('rlock1', 'client_A')
    print(f"  A release #1: {r3}")
    r4 = mgr.release('rlock1', 'client_A')
    print(f"  A release #2: {r4}")
    r5 = mgr.release('rlock1', 'client_A')
    print(f"  A release #3 (full release): {r5}")
    print()


def demo_readwrite():
    print("=" * 60)
    print("3. 读写锁 (ReadWrite)")
    mgr = LockManager()
    # 读读共享
    r1 = mgr.acquire('rw1', 'reader1', 'readwrite')
    print(f"  R1 acquire read: {r1}")
    r2 = mgr.acquire('rw1', 'reader2', 'readwrite')
    print(f"  R2 acquire read (should share): {r2}")
    # 写互斥
    r3 = mgr.acquire_write('rw1', 'writer1', blocking=False)
    print(f"  W1 non-blocking write (should fail): {r3}")
    # 释放读
    mgr.release('rw1', 'reader1')
    mgr.release('rw1', 'reader2')
    print("  Readers released")
    # 写成功
    r4 = mgr.acquire_write('rw1', 'writer1')
    print(f"  W1 write: {r4}")
    r5 = mgr.acquire('rw1', 'reader3', 'readwrite', blocking=False)
    print(f"  R3 non-blocking read (should fail): {r5}")
    mgr.release('rw1', 'writer1', 'write')
    print(f"  W1 released")
    print()


def demo_fair():
    print("=" * 60)
    print("4. 公平锁 (Fair)")
    mgr = LockManager()
    mgr.acquire('fair1', 'client_A', 'fair')
    print(f"  A holds lock")
    results = []

    def try_lock(client_id):
        r = mgr.acquire('fair1', client_id, 'fair')
        results.append((client_id, r))

    threads = []
    for cid in ['client_B', 'client_C', 'client_D']:
        t = threading.Thread(target=try_lock, args=(cid,))
        threads.append(t)
        t.start()
        time.sleep(0.01)  # stagger starts

    time.sleep(0.1)
    print(f"  Status: {mgr.status('fair1')}")
    mgr.release('fair1', 'client_A')
    print(f"  A released — B should get it")

    time.sleep(0.2)
    for cid, r in results:
        print(f"  {cid}: {r}")
    print()


def demo_deadlock_detection():
    print("=" * 60)
    print("5. 锁状态查看")
    mgr = LockManager()
    mgr.acquire('lock_a', 'client_X')
    mgr.acquire('lock_b', 'client_Y')
    print(f"  Status all: {mgr.status()}")
    print(f"  List: {mgr.list_locks()}")
    print()


def demo_timeout():
    print("=" * 60)
    print("6. 超时测试")
    mgr = LockManager()
    mgr.acquire('timer_lock', 'owner')
    r = mgr.acquire('timer_lock', 'waiter', timeout=0.1)
    print(f"  Waiter timeout (should fail): {r}")
    mgr.release('timer_lock', 'owner')
    print()


if __name__ == '__main__':
    demo_mutex()
    demo_reentrant()
    demo_readwrite()
    demo_fair()
    demo_deadlock_detection()
    demo_timeout()
