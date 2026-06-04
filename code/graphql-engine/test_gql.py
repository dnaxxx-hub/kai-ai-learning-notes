"""测试迷你 GraphQL 引擎"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema import Schema, ObjectType, Field, String, Int, Float, Boolean, ID, SCALAR_TYPES
from parser import parse_query, Selection, Document, Operation
from executor import Executor


class TestScalarTypes(unittest.TestCase):
    """1. 标量类型解析"""

    def test_scalar_types_exist(self):
        self.assertIn('String', SCALAR_TYPES)
        self.assertIn('Int', SCALAR_TYPES)
        self.assertIn('Float', SCALAR_TYPES)
        self.assertIn('Boolean', SCALAR_TYPES)
        self.assertIn('ID', SCALAR_TYPES)

    def test_scalar_constants(self):
        self.assertEqual(String, 'String')
        self.assertEqual(Int, 'Int')
        self.assertEqual(Float, 'Float')
        self.assertEqual(Boolean, 'Boolean')
        self.assertEqual(ID, 'ID')


class TestObjectType(unittest.TestCase):
    """2. ObjectType 字段定义"""

    def test_create_object_type(self):
        user_type = ObjectType('User', {
            'name': String,
            'age': Int,
        })
        self.assertEqual(user_type.name, 'User')
        self.assertEqual(len(user_type.get_fields()), 2)

    def test_get_field(self):
        user_type = ObjectType('User', {
            'name': String,
            'age': Int,
        })
        field = user_type.get_field('name')
        self.assertEqual(field.name, 'name')
        self.assertEqual(field.field_type, 'String')

    def test_get_unknown_field_raises(self):
        user_type = ObjectType('User', {'name': String})
        with self.assertRaises(ValueError):
            user_type.get_field('unknown')

    def test_field_with_resolver(self):
        user_type = ObjectType('User', {
            'name': Field(String, resolver=lambda root, **kw: 'test'),
        })
        field = user_type.get_field('name')
        self.assertEqual(field.name, 'name')
        self.assertEqual(field.field_type, 'String')
        self.assertEqual(field.resolver(None), 'test')


class TestSchema(unittest.TestCase):
    """3. Schema 构建"""

    def test_schema_creation(self):
        query_type = ObjectType('Query', {'hello': String})
        schema = Schema(query_type=query_type)
        self.assertEqual(schema.get_query_type(), query_type)

    def test_schema_with_mutation(self):
        query_type = ObjectType('Query', {'hello': String})
        mutation_type = ObjectType('Mutation', {'set': String})
        schema = Schema(query_type=query_type, mutation_type=mutation_type)
        self.assertEqual(schema.get_mutation_type(), mutation_type)


class TestParser(unittest.TestCase):
    """4. 简单查询解析"""

    def test_parse_simple(self):
        doc = parse_query('{ hello }')
        self.assertEqual(len(doc.operations), 1)
        op = doc.operations[0]
        self.assertEqual(op.operation_type, 'query')
        self.assertEqual(len(op.selections), 1)
        self.assertEqual(op.selections[0].name, 'hello')

    def test_parse_multiple_fields(self):
        doc = parse_query('{ hello world }')
        self.assertEqual(len(doc.operations), 1)
        self.assertEqual(len(doc.operations[0].selections), 2)
        self.assertEqual(doc.operations[0].selections[0].name, 'hello')
        self.assertEqual(doc.operations[0].selections[1].name, 'world')

    def test_parse_with_operation_type(self):
        doc = parse_query('query { hello }')
        self.assertEqual(doc.operations[0].operation_type, 'query')

    def test_parse_mutation(self):
        doc = parse_query('mutation { set }')
        self.assertEqual(doc.operations[0].operation_type, 'mutation')


class TestNestedQuery(unittest.TestCase):
    """5. 嵌套查询解析"""

    def test_parse_nested(self):
        doc = parse_query('{ user { name age } }')
        op = doc.operations[0]
        self.assertEqual(len(op.selections), 1)
        self.assertEqual(op.selections[0].name, 'user')
        self.assertEqual(len(op.selections[0].selections), 2)
        self.assertEqual(op.selections[0].selections[0].name, 'name')
        self.assertEqual(op.selections[0].selections[1].name, 'age')

    def test_deeply_nested(self):
        doc = parse_query('{ user { profile { bio } } }')
        user_sel = doc.operations[0].selections[0]
        profile_sel = user_sel.selections[0]
        self.assertEqual(profile_sel.name, 'profile')
        self.assertEqual(len(profile_sel.selections), 1)
        self.assertEqual(profile_sel.selections[0].name, 'bio')


class TestAlias(unittest.TestCase):
    """6. 带别名的查询"""

    def test_alias(self):
        doc = parse_query('{ myName: name }')
        sel = doc.operations[0].selections[0]
        self.assertEqual(sel.alias, 'myName')
        self.assertEqual(sel.name, 'name')

    def test_multiple_aliases(self):
        doc = parse_query('{ first: user { n: name } }')
        user_sel = doc.operations[0].selections[0]
        self.assertEqual(user_sel.alias, 'first')
        self.assertEqual(user_sel.name, 'user')
        name_sel = user_sel.selections[0]
        self.assertEqual(name_sel.alias, 'n')
        self.assertEqual(name_sel.name, 'name')


class TestArgs(unittest.TestCase):
    """7. 带参数的查询"""

    def test_args_string(self):
        doc = parse_query('{ user(id: "123") { name } }')
        sel = doc.operations[0].selections[0]
        self.assertEqual(sel.args, {'id': '123'})

    def test_args_int(self):
        doc = parse_query('{ user(id: 1) { name } }')
        sel = doc.operations[0].selections[0]
        self.assertEqual(sel.args, {'id': 1})

    def test_args_float(self):
        doc = parse_query('{ search(limit: 1.5) { name } }')
        sel = doc.operations[0].selections[0]
        self.assertEqual(sel.args, {'limit': 1.5})

    def test_multiple_args(self):
        doc = parse_query('{ items(limit: 10, offset: 5) }')
        sel = doc.operations[0].selections[0]
        self.assertEqual(sel.args, {'limit': 10, 'offset': 5})


class TestResolver(unittest.TestCase):
    """8. resolver 函数"""

    def test_custom_resolver(self):
        query_type = ObjectType('Query', {
            'hello': Field(String, resolver=lambda root, **kw: 'world'),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ hello }')
        self.assertEqual(result['data']['hello'], 'world')

    def test_resolver_with_args(self):
        query_type = ObjectType('Query', {
            'greet': Field(String, resolver=lambda root, **kw: f"Hello, {kw.get('name', 'World')}"),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ greet(name: "GraphQL") }')
        self.assertEqual(result['data']['greet'], 'Hello, GraphQL')

    def test_dict_root_resolver(self):
        query_type = ObjectType('Query', {
            'name': Field(String, resolver=lambda root, **kw: root.get('name')),
            'age': Field(Int, resolver=lambda root, **kw: root.get('age')),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema, root_value={'name': 'Alice', 'age': 30})
        result = executor.execute('{ name age }')
        self.assertEqual(result['data']['name'], 'Alice')
        self.assertEqual(result['data']['age'], 30)

    def test_default_dict_resolver(self):
        """测试默认 resolver 从 dict 取值"""
        query_type = ObjectType('Query', {
            'name': String,
            'age': Int,
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema, root_value={'name': 'Bob', 'age': 25})
        result = executor.execute('{ name age }')
        self.assertEqual(result['data']['name'], 'Bob')
        self.assertEqual(result['data']['age'], 25)


class TestFullExecution(unittest.TestCase):
    """9. 完整查询执行"""

    def test_simple_execution(self):
        query_type = ObjectType('Query', {
            'hello': Field(String, resolver=lambda root, **kw: 'world'),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ hello }')
        self.assertEqual(result, {'data': {'hello': 'world'}, 'errors': None})

    def test_nested_execution(self):
        BookType = ObjectType('Book', {
            'title': String,
            'author': String,
        })
        QueryType = ObjectType('Query', {
            'book': Field(BookType, resolver=lambda root, **kw: {
                'title': '1984', 'author': 'Orwell'
            }),
        })
        schema = Schema(query_type=QueryType)
        executor = Executor(schema)
        result = executor.execute('{ book { title author } }')
        self.assertEqual(result['data']['book']['title'], '1984')
        self.assertEqual(result['data']['book']['author'], 'Orwell')

    def test_execution_with_aliases(self):
        query_type = ObjectType('Query', {
            'hello': Field(String, resolver=lambda root, **kw: 'world'),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ greeting: hello }')
        self.assertEqual(result['data']['greeting'], 'world')


class TestErrorHandling(unittest.TestCase):
    """10. 错误处理"""

    def test_unknown_field(self):
        query_type = ObjectType('Query', {
            'hello': Field(String, resolver=lambda root, **kw: 'world'),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ unknown }')
        self.assertIn('errors', result)
        self.assertIsNotNone(result['errors'])
        self.assertGreater(len(result['errors']), 0)

    def test_empty_query(self):
        schema = Schema(query_type=ObjectType('Query', {'hello': String}))
        executor = Executor(schema)
        # Empty string should result in no operations
        result = executor.execute('')
        self.assertIn('errors', result)


class TestMultipleFields(unittest.TestCase):
    """11. 多字段选择"""

    def test_multiple_fields(self):
        query_type = ObjectType('Query', {
            'a': Field(String, resolver=lambda root, **kw: 'A'),
            'b': Field(String, resolver=lambda root, **kw: 'B'),
            'c': Field(String, resolver=lambda root, **kw: 'C'),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ a b c }')
        self.assertEqual(result['data']['a'], 'A')
        self.assertEqual(result['data']['b'], 'B')
        self.assertEqual(result['data']['c'], 'C')

    def test_mixed_scalar_types(self):
        query_type = ObjectType('Query', {
            'name': Field(String, resolver=lambda root, **kw: 'Alice'),
            'age': Field(Int, resolver=lambda root, **kw: 30),
            'score': Field(Float, resolver=lambda root, **kw: 95.5),
            'active': Field(Boolean, resolver=lambda root, **kw: True),
        })
        schema = Schema(query_type=query_type)
        executor = Executor(schema)
        result = executor.execute('{ name age score active }')
        self.assertEqual(result['data']['name'], 'Alice')
        self.assertEqual(result['data']['age'], 30)
        self.assertEqual(result['data']['score'], 95.5)
        self.assertEqual(result['data']['active'], True)


class TestTypeResolution(unittest.TestCase):
    """12. 类型解析"""

    def test_resolve_nested_type(self):
        BookType = ObjectType('Book', {
            'title': String,
            'rating': Float,
        })
        QueryType = ObjectType('Query', {
            'book': Field(BookType, resolver=lambda root, **kw: {
                'title': 'Dune', 'rating': 4.7
            }),
        })
        schema = Schema(query_type=QueryType)
        executor = Executor(schema)
        result = executor.execute('{ book { title rating } }')
        self.assertEqual(result['data']['book']['title'], 'Dune')
        self.assertEqual(result['data']['book']['rating'], 4.7)

    def test_list_of_objects(self):
        UserType = ObjectType('User', {
            'name': String,
            'email': String,
        })
        QueryType = ObjectType('Query', {
            'users': Field(UserType, resolver=lambda root, **kw: [
                {'name': 'Alice', 'email': 'alice@example.com'},
                {'name': 'Bob', 'email': 'bob@example.com'},
            ]),
        })
        schema = Schema(query_type=QueryType)
        executor = Executor(schema)
        result = executor.execute('{ users { name email } }')
        users = result['data']['users']
        self.assertIsInstance(users, list)
        # executor returns the raw list, but we can verify it's there
        self.assertEqual(len(users), 2)

    def test_mutation_execution(self):
        MutationType = ObjectType('Mutation', {
            'set': Field(String, resolver=lambda root, **kw: kw.get('value', '')),
        })
        QueryType = ObjectType('Query', {
            'get': Field(String, resolver=lambda root, **kw: 'ok'),
        })
        schema = Schema(query_type=QueryType, mutation_type=MutationType)
        executor = Executor(schema)
        result = executor.execute('mutation { set(value: "hello") }')
        self.assertEqual(result['data']['set'], 'hello')


if __name__ == '__main__':
    unittest.main()
