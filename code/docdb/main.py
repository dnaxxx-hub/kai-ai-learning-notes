#!/usr/bin/env python3
"""DocDB CLI — 类 MongoDB 的命令行接口"""
import sys
import json
from db import Database

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python main.py insert <collection> <json_data>")
        print("  python main.py find <collection> [<json_query>]")
        print("  python main.py find_one <collection> [<json_query>]")
        print("  python main.py update <collection> <json_query> <json_update>")
        print("  python main.py delete <collection> <json_query>")
        print("  python main.py count <collection> [<json_query>]")
        print("  python main.py drop <collection>")
        return

    db = Database()

    cmd = sys.argv[1]

    if cmd == 'insert':
        if len(sys.argv) < 4:
            print("用法: python main.py insert <collection> <json_data>")
            return
        col = db.collection(sys.argv[2])
        data = json.loads(sys.argv[3])
        result = col.insert(data)
        if isinstance(result, list):
            print(f"插入了 {len(result)} 条文档")
        else:
            print(f"插入了文档: {result['_id']}")

    elif cmd == 'find':
        if len(sys.argv) < 3:
            print("用法: python main.py find <collection> [<json_query>]")
            return
        col = db.collection(sys.argv[2])
        query = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        results = col.find(query)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == 'find_one':
        if len(sys.argv) < 3:
            print("用法: python main.py find_one <collection> [<json_query>]")
            return
        col = db.collection(sys.argv[2])
        query = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        result = col.find_one(query)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "未找到")

    elif cmd == 'update':
        if len(sys.argv) < 5:
            print("用法: python main.py update <collection> <json_query> <json_update>")
            return
        col = db.collection(sys.argv[2])
        query = json.loads(sys.argv[3])
        update = json.loads(sys.argv[4])
        count = col.update(query, update)
        print(f"更新了 {count} 条文档")

    elif cmd == 'delete':
        if len(sys.argv) < 4:
            print("用法: python main.py delete <collection> <json_query>")
            return
        col = db.collection(sys.argv[2])
        query = json.loads(sys.argv[3])
        count = col.delete(query)
        print(f"删除了 {count} 条文档")

    elif cmd == 'count':
        if len(sys.argv) < 3:
            print("用法: python main.py count <collection> [<json_query>]")
            return
        col = db.collection(sys.argv[2])
        query = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        count = col.count(query)
        print(f"文档数量: {count}")

    elif cmd == 'drop':
        if len(sys.argv) < 3:
            print("用法: python main.py drop <collection>")
            return
        db.drop(sys.argv[2])
        print(f"已删除集合: {sys.argv[2]}")

    else:
        print(f"未知命令: {cmd}")

if __name__ == '__main__':
    main()
