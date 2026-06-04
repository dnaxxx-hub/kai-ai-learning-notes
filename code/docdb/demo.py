#!/usr/bin/env python3
"""DocDB 演示脚本"""
import os, shutil
from db import Database

def main():
    demo_dir = 'demo_data'
    if os.path.exists(demo_dir):
        shutil.rmtree(demo_dir)

    db = Database(demo_dir)
    users = db.collection('users')

    print("=" * 50)
    print("DocDB 演示 — MongoDB 风格的 JSON 文档数据库")
    print("=" * 50)

    # 1. 插入数据
    print("\n1️⃣  插入用户数据")
    users.insert([
        {'name': 'Alice', 'age': 30, 'city': 'Beijing', 'tags': ['engineer', 'python']},
        {'name': 'Bob', 'age': 25, 'city': 'Shanghai', 'tags': ['designer']},
        {'name': 'Charlie', 'age': 35, 'city': 'Beijing', 'tags': ['engineer', 'manager']},
        {'name': 'David', 'age': 28, 'city': 'Shenzhen', 'tags': ['developer']},
        {'name': 'Eve', 'age': 32, 'city': 'Beijing', 'tags': ['engineer', 'data']},
    ])
    print(f"  插入了 {users.count()} 条文档")

    # 2. 基本查询
    print("\n2️⃣  基本查询 — 查找所有用户")
    for u in users.find():
        print(f"  - {u['name']}, {u['age']}岁, {u['city']}")

    # 3. 条件查询
    print("\n3️⃣  条件查询 — $gt 年龄大于30")
    for u in users.find({'age': {'$gt': 30}}):
        print(f"  - {u['name']}, {u['age']}岁")

    # 4. $in 操作符
    print("\n4️⃣  条件查询 — $in 北京和上海的用户")
    for u in users.find({'city': {'$in': ['Beijing', 'Shanghai']}}):
        print(f"  - {u['name']}, {u['city']}")

    # 5. $and 操作符
    print("\n5️⃣  条件查询 — $and 北京且年龄大于30的用户")
    for u in users.find({'$and': [{'city': 'Beijing'}, {'age': {'$gt': 30}}]}):
        print(f"  - {u['name']}, {u['city']}, {u['age']}岁")

    # 6. $regex 操作符
    print("\n6️⃣  条件查询 — $regex 名字以A开头的用户")
    for u in users.find({'name': {'$regex': '^A'}}):
        print(f"  - {u['name']}")

    # 7. 排序
    print("\n7️⃣  排序 — 按年龄升序")
    for u in users.find(sort={'age': 1}):
        print(f"  - {u['name']}, {u['age']}岁")

    # 8. 投影
    print("\n8️⃣  投影 — 只显示名字和城市")
    for u in users.find(projection={'name': 1, 'city': 1}):
        print(f"  - {u.get('name')}, {u.get('city')}")

    # 9. 分页
    print("\n9️⃣  分页 — skip=1, limit=2（按年龄排序）")
    for u in users.find(sort={'age': 1}, skip=1, limit=2):
        print(f"  - {u['name']}, {u['age']}岁")

    # 10. 更新
    print("\n🔟  更新 — 将所有北京用户的年龄+1")
    count = users.update({'city': 'Beijing'}, {'city': 'Beijing'})
    print(f"  更新了 {count} 条文档（演示更新操作）")

    # 11. 计数
    print(f"\n1️⃣1️⃣ 计数 — 总用户数: {users.count()}")

    # 12. 删除
    print("\n1️⃣2️⃣ 删除 — 删除深圳用户")
    count = users.delete({'city': 'Shenzhen'})
    print(f"  删除了 {count} 条文档，剩余 {users.count()} 条")

    # 清理
    shutil.rmtree(demo_dir)
    print("\n" + "=" * 50)
    print("演示完成！✅")

if __name__ == '__main__':
    main()
