"""MiniDB 演示 — 插入100条记录，范围查询，删除，持久化"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MiniDB


def main():
    db_filename = 'demo.dat'

    # 清理旧的演示文件
    if os.path.exists(db_filename):
        os.remove(db_filename)

    db = MiniDB(db_filename, order=4)

    print("=" * 50)
    print("MiniDB 演示")
    print("=" * 50)

    # 1. 插入 100 条记录
    print("\n📝 插入 100 条记录 (key=0..99, value=f'value-{key}')...")
    for i in range(100):
        db.put(i, f'value-{i}')
    print(f"   已插入 100 条记录")

    # 统计信息
    s = db.stats()
    print(f"\n📊 B+树统计:")
    for k, v in s.items():
        print(f"   {k}: {v}")

    # 2. 精确查找
    print("\n🔍 精确查找:")
    for k in [0, 50, 99]:
        v = db.get(k)
        print(f"   get({k}) = {v}")
    print(f"   get(100) = {db.get(100)}")

    # 3. 范围查询
    print("\n📋 范围查询 [10, 30):")
    results = db.range(10, 30)
    for k, v in results:
        print(f"   {k}: {v}")
    print(f"   共 {len(results)} 条")

    # 4. 更新
    print("\n✏️ 更新 key=50 为 'updated-50':")
    db.put(50, 'updated-50')
    print(f"   get(50) = {db.get(50)}")

    # 5. 删除
    print("\n🗑️ 删除 key=0:")
    db.delete(0)
    print(f"   get(0) = {db.get(0)}")
    print(f"   删除 key=99:")
    db.delete(99)
    print(f"   get(99) = {db.get(99)}")

    # 6. 持久化
    print("\n💾 保存到文件...")
    db.save()
    db.close()

    # 7. 重新加载
    print("\n🔄 从文件重新加载...")
    db2 = MiniDB(db_filename, order=4)
    db2.load()

    print(f"   get(1) = {db2.get(1)}")
    print(f"   get(50) = {db2.get(50)}")
    print(f"   get(98) = {db2.get(98)}")

    # 验证一致性
    print("\n✅ 验证数据一致性:")
    ok = True
    for i in range(1, 99):
        expected = 'updated-50' if i == 50 else f'value-{i}'
        actual = db2.get(i)
        if actual != expected:
            print(f"   错误: key={i}, 期望={expected}, 实际={actual}")
            ok = False
    if ok:
        print(f"   所有 98 条记录正确！")

    s2 = db2.stats()
    print(f"\n📊 重新加载后的统计:")
    for k, v in s2.items():
        print(f"   {k}: {v}")

    db2.close()

    # 清理
    if os.path.exists(db_filename):
        os.remove(db_filename)

    print("\n" + "=" * 50)
    print("🎉 演示完成！")


if __name__ == '__main__':
    main()
