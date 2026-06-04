#!/usr/bin/env python3
"""Demo script for Jinja2-subset template engine."""

from engine import Environment


def demo_basics():
    print("=" * 60)
    print("1. 基本变量插值")
    print("=" * 60)
    env = Environment()
    t = env.from_string("Hello, {{ name }}!")
    print(f"   Template: Hello, {{{{ name }}}}!")
    print(f"   Result:   {t.render({'name': 'World'})}")
    print()


def demo_filters():
    print("=" * 60)
    print("2. 过滤器")
    print("=" * 60)
    env = Environment()

    t = env.from_string("{{ name | upper }}")
    print(f"   upper:    {t.render({'name': 'hello'})}")

    t = env.from_string("{{ name | lower }}")
    print(f"   lower:    {t.render({'name': 'HELLO'})}")

    t = env.from_string("{{ name | capitalize }}")
    print(f"   capitalize: {t.render({'name': 'hello world'})}")

    t = env.from_string("{{ name | title }}")
    print(f"   title:    {t.render({'name': 'hello world'})}")

    t = env.from_string("{{ name | trim }}")
    print(f"   trim:     '{t.render({'name': '  hello  '})}'")

    t = env.from_string("{{ name | length }}")
    print(f"   length:   {t.render({'name': 'hello'})}")

    t = env.from_string("{{ name | default('Guest') }}")
    print(f"   default:  {t.render({})}")

    t = env.from_string("{{ items | join(', ') }}")
    print(f"   join:     {t.render({'items': ['a', 'b', 'c']})}")
    print()


def demo_filter_chain():
    print("=" * 60)
    print("3. 过滤器链")
    print("=" * 60)
    env = Environment()
    t = env.from_string("{{ name | trim | upper | default('N/A') }}")
    print(f"   Template: {{{{ name | trim | upper | default('N/A') }}}}")
    print(f"   Result:   '{t.render({'name': '  hello  '})}'")
    print(f"   Empty:    '{t.render({})}'")
    print()


def demo_for_loop():
    print("=" * 60)
    print("4. for 循环")
    print("=" * 60)
    env = Environment()

    t = env.from_string(
        "{% for item in items %}"
        "  - {{ item }}\n"
        "{% endfor %}"
    )
    print("Items:")
    print(t.render({'items': ['Apple', 'Banana', 'Cherry']}))

    t = env.from_string(
        "{% for item in items %}"
        "{{ item }}"
        "{% else %}"
        "(empty)"
        "{% endfor %}"
    )
    print(f"Empty list: '{t.render({'items': []})}'")
    print()


def demo_if_elif_else():
    print("=" * 60)
    print("5. if/elif/else 条件")
    print("=" * 60)
    env = Environment()

    t = env.from_string(
        "{% if score >= 90 %}A"
        "{% elif score >= 80 %}B"
        "{% elif score >= 70 %}C"
        "{% elif score >= 60 %}D"
        "{% else %}F"
        "{% endif %}"
    )

    for s in [95, 85, 75, 65, 55]:
        print(f"   Score {s}: Grade {t.render({'score': s})}")
    print()


def demo_set():
    print("=" * 60)
    print("6. set 赋值")
    print("=" * 60)
    env = Environment()
    t = env.from_string(
        "{% set greeting = 'Hello' %}"
        "{% set target = name | default('World') %}"
        "{{ greeting }}, {{ target }}!"
    )
    print(f"   Result: {t.render({'name': 'Alice'})}")
    print()


def demo_template_inheritance():
    print("=" * 60)
    print("7. 模板继承 (block/extends)")
    print("=" * 60)

    templates = {}

    def loader(name):
        return templates[name]

    templates['base.html'] = (
        "<html>\n"
        "<head>\n"
        "  <title>{% block title %}My Site{% endblock %}</title>\n"
        "</head>\n"
        "<body>\n"
        "  <header>{% block header %}Header{% endblock %}</header>\n"
        "  <main>{% block content %}Content{% endblock %}</main>\n"
        "  <footer>{% block footer %}Footer{% endblock %}</footer>\n"
        "</body>\n"
        "</html>"
    )

    templates['page.html'] = (
        '{% extends "base.html" %}'
        '{% block title %}About Us{% endblock %}'
        '{% block content %}This is the about page.{% endblock %}'
        '{% block footer %}© 2026{% endblock %}'
    )

    env = Environment(loader=loader)
    result = env.render_template('page.html', {})
    print(result)
    print()


def demo_custom_filter():
    print("=" * 60)
    print("8. 自定义过滤器")
    print("=" * 60)
    env = Environment()
    env.add_filter('reverse', lambda s: str(s)[::-1])
    t = env.from_string("Hello {{ name | reverse }}")
    print(f"   reverse:  {t.render({'name': 'world'})}")
    print()


def demo_complex():
    print("=" * 60)
    print("9. 复杂模板 — 用户列表")
    print("=" * 60)

    template = (
        "{# User list template #}\n"
        "{% set page_title = 'User Directory' %}\n"
        "<h1>{{ page_title | upper }}</h1>\n"
        "{% if users %}\n"
        "  <table>\n"
        "  {% for user in users %}\n"
        "    <tr>\n"
        "      <td>{{ user.name | default('N/A') }}</td>\n"
        "      <td>{{ user.email | default('no email') | lower }}</td>\n"
        "    </tr>\n"
        "  {% endfor %}\n"
        "  </table>\n"
        "{% else %}\n"
        "  <p>No users found.</p>\n"
        "{% endif %}"
    )

    env = Environment()
    t = env.from_string(template)

    data = {
        'users': [
            {'name': 'Alice', 'email': 'Alice@Example.COM'},
            {'name': 'Bob', 'email': 'Bob@Example.COM'},
            {'name': 'Charlie'},
        ]
    }

    print(t.render(data))
    print()


def main():
    print("\n")
    print("=" * 60)
    print("  Jinja2 子集模板引擎 — 演示")
    print("=" * 60)
    print()

    demo_basics()
    demo_filters()
    demo_filter_chain()
    demo_for_loop()
    demo_if_elif_else()
    demo_set()
    demo_template_inheritance()
    demo_custom_filter()
    demo_complex()

    print("=" * 60)
    print("  演示完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
