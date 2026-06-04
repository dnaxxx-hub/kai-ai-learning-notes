"""MiniDB — CLI 入口

用法:
    python main.py put <key> <value>
    python main.py get <key>
    python main.py delete <key>
    python main.py range <start> [end]
    python main.py stats
"""

import sys
import os

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import MiniDB


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    db = MiniDB('minidb.dat')

    command = sys.argv[1]

    if command == 'put':
        if len(sys.argv) < 4:
            print("用法: python main.py put <key> <value>")
            return
        key = int(sys.argv[2])
        value = sys.argv[3]
        db.put(key, value)
        db.save()
        print(f"OK: put {key} = {value}")

    elif command == 'get':
        if len(sys.argv) < 3:
            print("用法: python main.py get <key>")
            return
        key = int(sys.argv[2])
        db.load()
        value = db.get(key)
        if value is not None:
            print(value)
        else:
            print(f"None (key {key} 不存在)")

    elif command == 'delete':
        if len(sys.argv) < 3:
            print("用法: python main.py delete <key>")
            return
        key = int(sys.argv[2])
        db.load()
        result = db.delete(key)
        if result:
            db.save()
            print(f"OK: 已删除 key {key}")
        else:
            print(f"key {key} 不存在")

    elif command == 'range':
        if len(sys.argv) < 3:
            print("用法: python main.py range <start> [end]")
            return
        start = int(sys.argv[2])
        end = int(sys.argv[3]) if len(sys.argv) > 3 else None
        db.load()
        results = db.range(start, end)
        if results:
            for k, v in results:
                print(f"{k}: {v}")
        else:
            print("(空)")

    elif command == 'stats':
        db.load()
        s = db.stats()
        print("B+树统计:")
        for k, v in s.items():
            print(f"  {k}: {v}")

    else:
        print(f"未知命令: {command}")
        print(__doc__)

    db.close()


if __name__ == '__main__':
    main()
