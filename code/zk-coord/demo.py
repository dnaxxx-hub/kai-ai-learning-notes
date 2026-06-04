"""
ZK-Coord 演示脚本
展示核心功能：ZNode CRUD + Watcher + Session + 临时/顺序节点
"""

import time
import threading

from znode import ZNode
from tree import ZNodeTree
from watcher import WatcherManager
from session import SessionManager


def demo_tree():
    print("=" * 60)
    print("🌳 1. ZNode Tree — 树形命名空间")
    print("=" * 60)

    tree = ZNodeTree()

    # 创建永久节点
    n1 = tree.create('/app', b'hello_zk')
    print(f"  创建 /app → {n1.path}")

    # 创建子节点
    n2 = tree.create('/app/config', b'{"port":8080}')
    n3 = tree.create('/app/data', b'some_data')
    print(f"  创建子节点 → /app/config, /app/data")

    # 读取数据
    print(f"  读取 /app → {tree.get_data('/app')}")
    print(f"  读取 /app/config → {tree.get_data('/app/config')}")

    # 修改数据
    tree.set_data('/app', b'hello_zk_v2')
    print(f"  修改 /app → {tree.get_data('/app')} (version={tree.stat('/app')['version']})")

    # 子节点列表
    children = tree.get_children('/app')
    print(f"  子节点: {children}")

    # 节点存在性
    print(f"  exists /app: {tree.exists('/app')}")
    print(f"  exists /nope: {tree.exists('/nope')}")

    # 删除
    tree.delete('/app/config')
    print(f"  删除 /app/config → children: {tree.get_children('/app')}")


def demo_ephemeral_sequential():
    print("\n" + "=" * 60)
    print("🔢 2. 临时节点 + 顺序节点")
    print("=" * 60)

    tree = ZNodeTree()

    # 顺序节点
    s1 = tree.create('/lock', b'', ZNode.PERSISTENT_SEQUENTIAL)
    s2 = tree.create('/lock', b'', ZNode.PERSISTENT_SEQUENTIAL)
    s3 = tree.create('/lock', b'', ZNode.PERSISTENT_SEQUENTIAL)
    print(f"  顺序节点:")
    for n in [s1, s2, s3]:
        print(f"    - {n.path}")

    # 临时节点
    e1 = tree.create('/temp', b'temp_data', ZNode.EPHEMERAL, 'sess1')
    print(f"  临时节点: {e1.path} (ephemeral={e1.is_ephemeral()})")

    # 临时+顺序节点
    es1 = tree.create('/task', b'', ZNode.EPHEMERAL_SEQUENTIAL, 'sess1')
    es2 = tree.create('/task', b'', ZNode.EPHEMERAL_SEQUENTIAL, 'sess1')
    print(f"  临时顺序节点:")
    for n in [es1, es2]:
        print(f"    - {n.path} (eph={n.is_ephemeral()}, seq={n.is_sequential()})")

    # 清理临时节点
    print(f"\n  清理 session=sess1 的临时节点...")
    removed = tree.clean_ephemeral('sess1')
    for r in removed:
        print(f"    已移除: {r}")
    print(f"  exists /temp: {tree.exists('/temp')}")


def demo_watcher():
    print("\n" + "=" * 60)
    print("👀 3. Watcher 通知系统")
    print("=" * 60)

    watcher = WatcherManager()
    tree = ZNodeTree()
    notified = []

    def on_created(evt):
        notified.append(evt)
        print(f"  🟢 CREATED: {evt['path']}")

    def on_deleted(evt):
        notified.append(evt)
        print(f"  🔴 DELETED: {evt['path']}")

    def on_data_changed(evt):
        notified.append(evt)
        print(f"  🟡 DATA_CHANGED: {evt['path']}")

    def on_child_changed(evt):
        notified.append(evt)
        print(f"  🔵 CHILD_CHANGED: {evt['path']}")

    # 注册监听
    watcher.watch('/', 'child_changed', on_child_changed)
    watcher.watch('/app', 'created', on_created)
    watcher.watch('/app', 'data_changed', on_data_changed)
    watcher.watch('/app', 'deleted', on_deleted)

    # 触发事件
    print("  --- 创建 /app ---")
    tree.create('/app', b'hello')
    watcher.notify('/app', 'created')

    print("  --- 修改 /app ---")
    tree.set_data('/app', b'world')
    watcher.notify('/app', 'data_changed')

    print("  --- 创建 /app/child (触发 child_changed) ---")
    tree.create('/app/child')
    watcher.notify('/app/child', 'created')

    print("  --- 删除 /app ---")
    tree.delete('/app')
    watcher.notify('/app', 'deleted')


def demo_session():
    print("\n" + "=" * 60)
    print("🔌 4. Session 管理 (心跳 + 过期清理)")
    print("=" * 60)

    tree = ZNodeTree()
    watcher = WatcherManager()
    sm = SessionManager(tree, watcher)

    # 创建两个 session
    sid1 = sm.create_session(timeout=2)
    sid2 = sm.create_session(timeout=2)
    print(f"  Session 1: {sid1[:8]}...")
    print(f"  Session 2: {sid2[:8]}...")

    # 创建临时节点
    tree.create('/sess1_node', b'', ZNode.EPHEMERAL, sid1)
    tree.create('/sess2_node', b'', ZNode.EPHEMERAL, sid2)
    tree.create('/persistent', b'i_stay')
    print(f"  临时节点: /sess1_node, /sess2_node")
    print(f"  持久节点: /persistent")

    # 保持 sid1 活跃，让 sid2 过期
    print(f"\n  保持 session1 活跃，等待 session2 过期...")
    for i in range(3):
        time.sleep(1)
        sm.keepalive(sid1)
        print(f"  心跳... ({i+1}/3)")

    # sid2 应该过期了
    print(f"  session2 已过期: {sid2 not in sm.sessions}")
    print(f"  /sess2_node 已清理: {not tree.exists('/sess2_node')}")
    print(f"  /sess1_node 还在: {tree.exists('/sess1_node')}")
    print(f"  /persistent 还在: {tree.exists('/persistent')}")

    sm.stop()


def demo_stat():
    print("\n" + "=" * 60)
    print("📊 5. 节点状态 (Stat)")
    print("=" * 60)

    tree = ZNodeTree()

    for i in range(3):
        tree.create(f'/node_{i}', f'data_{i}')

    for name in ['/node_0', '/node_1', '/node_2']:
        st = tree.stat(name)
        print(f"  {name}: version={st['version']}, data='{st['data']}'")


if __name__ == '__main__':
    print("🚀 ZK Coordinator Demo")
    print()

    demo_tree()
    demo_ephemeral_sequential()
    demo_watcher()
    demo_session()
    demo_stat()

    print("\n" + "=" * 60)
    print("✨ Demo Complete!")
    print("=" * 60)
