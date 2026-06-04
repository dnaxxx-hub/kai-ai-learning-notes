"""迷你 GraphQL 引擎演示"""

from schema import Schema, ObjectType, Field, String, Int, Float
from executor import Executor


def main():
    print("=" * 50)
    print("迷你 GraphQL 引擎演示")
    print("=" * 50)

    # 定义 Book 类型
    BookType = ObjectType('Book', {
        'title': String,
        'author': String,
        'year': Int,
        'rating': Float,
    })

    # 定义 Author 类型
    AuthorType = ObjectType('Author', {
        'name': String,
        'age': Int,
    })

    # 定义 Query 类型
    QueryType = ObjectType('Query', {
        'hello': Field(String, resolver=lambda root, **kw: "World!"),
        'books': Field(BookType, resolver=lambda root, **kw: [
            {'title': '1984', 'author': 'George Orwell', 'year': 1949, 'rating': 4.8},
            {'title': 'Brave New World', 'author': 'Aldous Huxley', 'year': 1932, 'rating': 4.5},
            {'title': 'Fahrenheit 451', 'author': 'Ray Bradbury', 'year': 1953, 'rating': 4.3},
        ]),
        'author': Field(AuthorType, resolver=lambda root, **kw: {
            'name': kw.get('name', 'Unknown'),
            'age': kw.get('age', 0),
        }),
    })

    # 构建 Schema
    schema = Schema(query_type=QueryType)
    executor = Executor(schema)

    # 演示 1: 简单查询
    print("\n--- 演示 1: 简单查询 ---")
    result = executor.execute('{ hello }')
    print(f"查询: {{ hello }}")
    print(f"结果: {result}")

    # 演示 2: 嵌套查询
    print("\n--- 演示 2: 嵌套查询 ---")
    result = executor.execute('{ books { title author } }')
    print(f"查询: {{ books {{ title author }} }}")
    print(f"结果: {result}")

    # 演示 3: 带别名的查询
    print("\n--- 演示 3: 带别名的查询 ---")
    result = executor.execute('{ greeting: hello }')
    print(f"查询: {{ greeting: hello }}")
    print(f"结果: {result}")

    # 演示 4: 带参数的查询
    print("\n--- 演示 4: 带参数的查询 ---")
    result = executor.execute('{ author(name: "Alice", age: 30) { name age } }')
    print(f"查询: {{ author(name: \"Alice\", age: 30) {{ name age }} }}")
    print(f"结果: {result}")

    # 演示 5: 多字段查询
    print("\n--- 演示 5: 多字段查询 ---")
    result = executor.execute('{ books { title year rating } }')
    print(f"查询: {{ books {{ title year rating }} }}")
    print(f"结果: {result}")

    # 演示 6: 混合查询
    print("\n--- 演示 6: 混合查询 ---")
    result = executor.execute('{ hello author(name: "Bob", age: 25) { name age } }')
    print(f"查询: {{ hello author(name: \"Bob\", age: 25) {{ name age }} }}")
    print(f"结果: {result}")

    print("\n" + "=" * 50)
    print("演示完成!")
    print("=" * 50)


if __name__ == '__main__':
    main()
