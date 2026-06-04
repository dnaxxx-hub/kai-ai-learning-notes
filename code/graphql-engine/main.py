"""GraphQL 引擎 CLI 入口"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema import Schema, ObjectType, Field, String, Int, Float, Boolean
from executor import Executor


def create_default_schema():
    """创建一个默认的 Schema 用于演示"""
    QueryType = ObjectType('Query', {
        'hello': Field(String, resolver=lambda root, **kw: "World!"),
        'echo': Field(String, resolver=lambda root, **kw: kw.get('msg', '')),
        'ping': Field(String, resolver=lambda root, **kw: 'pong'),
        'answer': Field(Int, resolver=lambda root, **kw: 42),
        'pi': Field(Float, resolver=lambda root, **kw: 3.14159),
        'is_graphql_cool': Field(Boolean, resolver=lambda root, **kw: True),
    })
    return Schema(query_type=QueryType)


def main():
    query_str = None

    # 从命令行参数读取
    if len(sys.argv) > 1:
        query_str = ' '.join(sys.argv[1:])

    # 从 stdin 读取
    if query_str is None and not sys.stdin.isatty():
        query_str = sys.stdin.read().strip()

    # 交互模式
    if query_str is None:
        print("迷你 GraphQL 引擎 CLI")
        print("输入 GraphQL 查询 (输入 'quit' 退出)")
        print("示例: { hello }\n")
        schema = create_default_schema()
        executor = Executor(schema)

        while True:
            try:
                line = input("> ").strip()
                if line.lower() in ('quit', 'exit', 'q'):
                    break
                if not line:
                    continue

                result = executor.execute(line)
                import json
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print()
            except KeyboardInterrupt:
                print("\n再见!")
                break
            except Exception as e:
                print(f"错误: {e}\n")
        return

    # 单次执行模式
    schema = create_default_schema()
    executor = Executor(schema)

    try:
        result = executor.execute(query_str)
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
