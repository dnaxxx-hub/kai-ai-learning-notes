#!/usr/bin/env python3
"""Test suite for Jinja2-subset template engine."""

import unittest
import os
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import Environment, Template
from lexer import tokenize
from parser import parse
from compiler import Compiler


class TestLexer(unittest.TestCase):
    """词法分析测试"""

    def test_text_only(self):
        """纯文本"""
        tokens = tokenize('Hello World')
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0], ('TEXT', 'Hello World'))

    def test_variable(self):
        """变量标记"""
        tokens = tokenize('{{ name }}')
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0], ('VARIABLE_START', '{{'))
        self.assertEqual(tokens[2], ('VARIABLE_END', '}}'))

    def test_block(self):
        """块标记"""
        tokens = tokenize('{% if x %}')
        self.assertEqual(tokens[0], ('BLOCK_START', '{%'))

    def test_comment(self):
        """注释"""
        tokens = tokenize('before{# comment #}after')
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0], ('TEXT', 'before'))
        self.assertEqual(tokens[1][0], 'COMMENT')
        self.assertEqual(tokens[2], ('TEXT', 'after'))

    def test_string_number(self):
        """字符串和数字"""
        tokens = tokenize("{{ 'hello' }}")
        types = [t[0] for t in tokens]
        self.assertIn('STRING', types)


class TestBasicVariable(unittest.TestCase):
    """Test 1: 简单变量插值"""

    def test_simple_variable(self):
        env = Environment()
        t = env.from_string('Hello {{ name }}')
        result = t.render({'name': 'World'})
        self.assertEqual(result, 'Hello World')

    def test_variable_missing(self):
        env = Environment()
        t = env.from_string('{{ missing }}')
        result = t.render({})
        self.assertEqual(result, '')


class TestDotPath(unittest.TestCase):
    """Test 2: 点号路径"""

    def test_dot_path(self):
        env = Environment()
        t = env.from_string('{{ user.name }}')
        result = t.render({'user': {'name': 'Alice'}})
        self.assertEqual(result, 'Alice')

    def test_nested_dot_path(self):
        env = Environment()
        t = env.from_string('{{ a.b.c }}')
        result = t.render({'a': {'b': {'c': 'deep'}}})
        self.assertEqual(result, 'deep')


class TestFilters(unittest.TestCase):
    """Test 3: 过滤器"""

    def test_upper_filter(self):
        env = Environment()
        t = env.from_string('{{ name | upper }}')
        result = t.render({'name': 'hello'})
        self.assertEqual(result, 'HELLO')

    def test_lower_filter(self):
        env = Environment()
        t = env.from_string('{{ name | lower }}')
        result = t.render({'name': 'HELLO'})
        self.assertEqual(result, 'hello')

    def test_capitalize_filter(self):
        env = Environment()
        t = env.from_string('{{ text | capitalize }}')
        result = t.render({'text': 'hello world'})
        self.assertEqual(result, 'Hello world')

    def test_title_filter(self):
        env = Environment()
        t = env.from_string('{{ text | title }}')
        result = t.render({'text': 'hello world'})
        self.assertEqual(result, 'Hello World')

    def test_trim_filter(self):
        env = Environment()
        t = env.from_string('{{ text | trim }}')
        result = t.render({'text': '  hello  '})
        self.assertEqual(result, 'hello')

    def test_length_filter(self):
        env = Environment()
        t = env.from_string('{{ text | length }}')
        result = t.render({'text': 'hello'})
        self.assertEqual(result, '5')

    def test_default_filter(self):
        env = Environment()
        t = env.from_string('{{ name | default("Guest") }}')
        result = t.render({})
        self.assertEqual(result, 'Guest')

    def test_default_filter_with_value(self):
        env = Environment()
        t = env.from_string('{{ name | default("Guest") }}')
        result = t.render({'name': 'Alice'})
        self.assertEqual(result, 'Alice')

    def test_join_filter(self):
        env = Environment()
        t = env.from_string('{{ items | join(", ") }}')
        result = t.render({'items': ['a', 'b', 'c']})
        self.assertEqual(result, 'a, b, c')


class TestFilterChain(unittest.TestCase):
    """Test 4: 过滤器链"""

    def test_filter_chain(self):
        env = Environment()
        t = env.from_string('{{ name | upper | default("X") }}')
        result = t.render({'name': 'hello'})
        self.assertEqual(result, 'HELLO')

    def test_filter_chain_missing(self):
        env = Environment()
        t = env.from_string('{{ name | upper | default("X") }}')
        result = t.render({})
        self.assertEqual(result, 'X')

    def test_multi_filter_chain(self):
        env = Environment()
        t = env.from_string('{{ text | trim | upper }}')
        result = t.render({'text': '  hello  '})
        self.assertEqual(result, 'HELLO')


class TestForLoop(unittest.TestCase):
    """Test 5: for 循环"""

    def test_for_loop(self):
        env = Environment()
        t = env.from_string('{% for x in items %}{{ x }}{% endfor %}')
        result = t.render({'items': ['a', 'b', 'c']})
        self.assertEqual(result, 'abc')

    def test_for_loop_with_separator(self):
        env = Environment()
        t = env.from_string('{% for x in items %}({{ x }}){% endfor %}')
        result = t.render({'items': [1, 2, 3]})
        self.assertEqual(result, '(1)(2)(3)')


class TestForElse(unittest.TestCase):
    """Test 6: 空列表 for else"""

    def test_for_else_empty(self):
        env = Environment()
        t = env.from_string('{% for x in items %}{{ x }}{% else %}empty{% endfor %}')
        result = t.render({'items': []})
        self.assertEqual(result, 'empty')

    def test_for_else_nonempty(self):
        env = Environment()
        t = env.from_string('{% for x in items %}{{ x }}{% else %}empty{% endfor %}')
        result = t.render({'items': ['a']})
        self.assertEqual(result, 'a')


class TestIfCondition(unittest.TestCase):
    """Test 7: if 条件"""

    def test_if_true(self):
        env = Environment()
        t = env.from_string('{% if x %}yes{% endif %}')
        result = t.render({'x': True})
        self.assertEqual(result, 'yes')

    def test_if_false(self):
        env = Environment()
        t = env.from_string('{% if x %}yes{% endif %}')
        result = t.render({'x': False})
        self.assertEqual(result, '')

    def test_if_truthy(self):
        env = Environment()
        t = env.from_string('{% if x %}yes{% endif %}')
        result = t.render({'x': 1})
        self.assertEqual(result, 'yes')

    def test_if_falsy(self):
        env = Environment()
        t = env.from_string('{% if x %}yes{% endif %}')
        result = t.render({'x': 0})
        self.assertEqual(result, '')


class TestIfElifElse(unittest.TestCase):
    """Test 8: if/elif/else"""

    def test_if_elif_else_first(self):
        env = Environment()
        t = env.from_string('{% if x > 5 %}big{% elif x > 0 %}medium{% else %}small{% endif %}')
        result = t.render({'x': 10})
        self.assertEqual(result, 'big')

    def test_if_elif_else_second(self):
        env = Environment()
        t = env.from_string('{% if x > 5 %}big{% elif x > 0 %}medium{% else %}small{% endif %}')
        result = t.render({'x': 3})
        self.assertEqual(result, 'medium')

    def test_if_elif_else_fallback(self):
        env = Environment()
        t = env.from_string('{% if x > 5 %}big{% elif x > 0 %}medium{% else %}small{% endif %}')
        result = t.render({'x': 0})
        self.assertEqual(result, 'small')

    def test_if_else_only(self):
        env = Environment()
        t = env.from_string('{% if x %}yes{% else %}no{% endif %}')
        result = t.render({'x': False})
        self.assertEqual(result, 'no')


class TestComparison(unittest.TestCase):
    """Test 9: 比较条件"""

    def test_greater_than(self):
        env = Environment()
        t = env.from_string('{% if x > 5 %}big{% endif %}')
        self.assertEqual(t.render({'x': 10}), 'big')
        self.assertEqual(t.render({'x': 1}), '')

    def test_less_than(self):
        env = Environment()
        t = env.from_string('{% if x < 5 %}small{% endif %}')
        self.assertEqual(t.render({'x': 1}), 'small')
        self.assertEqual(t.render({'x': 10}), '')

    def test_equal(self):
        env = Environment()
        t = env.from_string('{% if x == 5 %}five{% endif %}')
        self.assertEqual(t.render({'x': 5}), 'five')
        self.assertEqual(t.render({'x': 6}), '')

    def test_not_equal(self):
        env = Environment()
        t = env.from_string('{% if x != 5 %}not five{% endif %}')
        self.assertEqual(t.render({'x': 3}), 'not five')
        self.assertEqual(t.render({'x': 5}), '')


class TestSet(unittest.TestCase):
    """Test 10: set 赋值"""

    def test_set_variable(self):
        env = Environment()
        t = env.from_string('{% set x = 5 %}{{ x }}')
        result = t.render({})
        self.assertEqual(result, '5')

    def test_set_and_use(self):
        env = Environment()
        t = env.from_string('{% set name = "Alice" %}Hello {{ name }}')
        result = t.render({})
        self.assertEqual(result, 'Hello Alice')


class TestBlockExtends(unittest.TestCase):
    """Test 11: block + extends (模板继承)"""

    def test_extends_block(self):
        """基本的模板继承"""
        templates = {}

        def loader(name):
            return templates[name]

        templates['base.html'] = 'HEAD{% block content %}DEFAULT{% endblock %}FOOT'
        templates['child.html'] = (
            '{% extends "base.html" %}'
            '{% block content %}CHILD{% endblock %}'
        )

        env = Environment(loader=loader)
        result = env.render_template('child.html', {})
        # 测试: 继承应合并 blocks
        self.assertIn('HEAD', result)
        self.assertIn('CHILD', result)
        self.assertIn('FOOT', result)
        self.assertNotIn('DEFAULT', result)


class TestNestedLoop(unittest.TestCase):
    """Test 12: 嵌套循环"""

    def test_nested_for(self):
        env = Environment()
        t = env.from_string(
            '{% for row in matrix %}'
            '{% for cell in row %}'
            '{{ cell }}'
            '{% endfor %}'
            '|'
            '{% endfor %}'
        )
        result = t.render({'matrix': [[1, 2], [3, 4]]})
        self.assertEqual(result, '12|34|')

    def test_for_with_if_inside(self):
        env = Environment()
        t = env.from_string(
            '{% for x in items %}'
            '{% if x > 1 %}'
            '{{ x }}'
            '{% endif %}'
            '{% endfor %}'
        )
        result = t.render({'items': [1, 2, 3]})
        self.assertEqual(result, '23')


class TestPlainText(unittest.TestCase):
    """Test 13: 纯文本不变"""

    def test_plain_text(self):
        env = Environment()
        t = env.from_string('Hello World!')
        result = t.render({})
        self.assertEqual(result, 'Hello World!')

    def test_text_with_newlines(self):
        env = Environment()
        t = env.from_string('Line1\nLine2\nLine3')
        result = t.render({})
        self.assertEqual(result, 'Line1\nLine2\nLine3')


class TestComment(unittest.TestCase):
    """Test 14: 注释忽略"""

    def test_comment_removed(self):
        env = Environment()
        t = env.from_string('before{# this is a comment #}after')
        result = t.render({})
        self.assertEqual(result, 'beforeafter')

    def test_comment_with_variable_inside(self):
        env = Environment()
        t = env.from_string('x{# {{ name }} #}y')
        result = t.render({'name': 'leak'})
        self.assertEqual(result, 'xy')


class TestComplexExpressions(unittest.TestCase):
    """Test 15: 复杂表达式"""

    def test_combined_filter_and_variable(self):
        env = Environment()
        t = env.from_string('{{ user.name | upper | default("N/A") }}')
        result = t.render({'user': {'name': 'alice'}})
        self.assertEqual(result, 'ALICE')

    def test_missing_deep_path(self):
        env = Environment()
        t = env.from_string('{{ a.b.c.d | default("missing") }}')
        result = t.render({'a': {}})
        self.assertEqual(result, 'missing')


class TestCustomFilter(unittest.TestCase):
    """Test 16: 自定义过滤器"""

    def test_custom_filter(self):
        env = Environment()
        env.add_filter('reverse', lambda s: str(s)[::-1])
        t = env.from_string('{{ name | reverse }}')
        result = t.render({'name': 'hello'})
        self.assertEqual(result, 'olleh')

    def test_custom_filter_with_args(self):
        env = Environment()
        env.add_filter('surround', lambda s, prefix, suffix: prefix + str(s) + suffix)
        t = env.from_string('{{ name | surround("<", ">") }}')
        result = t.render({'name': 'hello'})
        self.assertEqual(result, '<hello>')

    def test_custom_filter_fallback_default(self):
        env = Environment()
        env.add_filter('surround', lambda s, pre, suf: pre + str(s) + suf)
        t = env.from_string('{{ name | surround("(", ")") }}')
        result = t.render({'name': 'test'})
        self.assertEqual(result, '(test)')


class TestLiterals(unittest.TestCase):
    """Test 17: 数字和字符串字面量"""

    def test_number_literal(self):
        env = Environment()
        t = env.from_string('{{ 42 }}')
        result = t.render({})
        self.assertEqual(result, '42')

    def test_string_literal(self):
        env = Environment()
        t = env.from_string("{{ 'hello' }}")
        result = t.render({})
        self.assertEqual(result, 'hello')

    def test_double_quote_string(self):
        env = Environment()
        t = env.from_string('{{ "world" }}')
        result = t.render({})
        self.assertEqual(result, 'world')

    def test_float_literal(self):
        env = Environment()
        t = env.from_string('{{ 3.14 }}')
        result = t.render({})
        self.assertEqual(result, '3.14')


class TestEmptyContext(unittest.TestCase):
    """Test 18: 空上下文"""

    def test_empty_context(self):
        env = Environment()
        t = env.from_string('Hello {{ name }}')
        result = t.render({})
        self.assertEqual(result, 'Hello ')

    def test_no_context(self):
        env = Environment()
        t = env.from_string('static text')
        result = t.render()
        self.assertEqual(result, 'static text')


class TestSafeFilter(unittest.TestCase):
    """Test safe filter"""

    def test_safe_filter(self):
        env = Environment()
        t = env.from_string('{{ content | safe }}')
        result = t.render({'content': '<b>bold</b>'})
        self.assertEqual(result, '<b>bold</b>')


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_complex_template(self):
        """真实世界的模板"""
        template_str = (
            '{# This is a comment #}\n'
            '{% set title = "Users" %}\n'
            '<h1>{{ title | upper }}</h1>\n'
            '{% if users %}\n'
            '<ul>\n'
            '{% for user in users %}\n'
            '<li>{{ user.name | default("Unknown") }}</li>\n'
            '{% endfor %}\n'
            '</ul>\n'
            '{% else %}\n'
            '<p>No users found.</p>\n'
            '{% endif %}'
        )

        env = Environment()
        t = env.from_string(template_str)
        result = t.render({'users': [{'name': 'Alice'}, {'name': 'Bob'}]})

        self.assertIn('<h1>USERS</h1>', result)
        self.assertIn('<li>Alice</li>', result)
        self.assertIn('<li>Bob</li>', result)
        self.assertNotIn('No users', result)

    def test_template_without_users(self):
        template_str = (
            '{% if users %}\n'
            'have users\n'
            '{% else %}\n'
            'No users found.\n'
            '{% endif %}'
        )
        env = Environment()
        t = env.from_string(template_str)
        result = t.render({'users': []})
        self.assertIn('No users', result)


class TestInheritance(unittest.TestCase):
    """模板继承测试"""

    def test_single_block_override(self):
        templates = {}

        def loader(name):
            return templates[name]

        templates['base.txt'] = 'START{% block body %}BASE{% endblock %}END'
        templates['child.txt'] = (
            '{% extends "base.txt" %}'
            '{% block body %}CHILD{% endblock %}'
        )

        env = Environment(loader=loader)
        result = env.render_template('child.txt', {})
        self.assertEqual(result, 'STARTCHILDEND')

    def test_multiple_blocks(self):
        templates = {}

        def loader(name):
            return templates[name]

        templates['layout.html'] = (
            '<html>'
            '<head><title>{% block title %}Default{% endblock %}</title></head>'
            '<body>{% block content %}Body{% endblock %}</body>'
            '</html>'
        )
        templates['page.html'] = (
            '{% extends "layout.html" %}'
            '{% block title %}My Page{% endblock %}'
            '{% block content %}Hello World{% endblock %}'
        )

        env = Environment(loader=loader)
        result = env.render_template('page.html', {})
        self.assertIn('<title>My Page</title>', result)
        self.assertIn('Hello World</body>', result)
        self.assertNotIn('Default', result)


if __name__ == '__main__':
    unittest.main()
