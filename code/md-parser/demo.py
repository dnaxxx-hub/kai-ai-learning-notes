"""演示：Markdown 解析"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_markdown
from renderer import render


def demo():
    print("=" * 60)
    print("📝 Markdown 解析器 · 全功能演示")
    print("=" * 60)

    # 测试用例
    test_cases = [
        ("标题", "# Hello World"),
        ("粗体", "这是 **粗体** 文字"),
        ("斜体", "这是 *斜体* 文字"),
        ("下划线", "这是 _下划线 slash_ 文字"),
        ("嵌套", "**粗体包含 *斜体* 哦**"),
        ("删除线", "这是 ~~删除线~~ 文字"),
        ("行内代码", "运行 `print(1)` 输出 1"),
        ("链接", "访问 [GitHub](https://github.com)"),
        ("图片", "图片: ![Logo](https://example.com/logo.png)"),
        ("段落", "第一段文字。\n\n第二段文字。"),
        ("无序列表", "- 第一项\n- 第二项\n- 第三项"),
        ("有序列表", "1. 第一步\n2. 第二步"),
        ("引用", "> 这是引用\n> 第二行引用"),
        ("水平线", "---"),
        ("代码块", "```python\ndef hello():\n    print('hi')\n```"),
        ("转义", "\\*这不是斜体\\*"),
    ]

    for name, md in test_cases:
        print(f"\n{'━' * 50}")
        print(f"📌 {name}:")
        print(f"  MD:   {md}")
        try:
            ast = parse_markdown(md)
            html = render(ast)
            # 去掉外层 div 标签
            html_content = html.replace('<div class="markdown-body">\n', '').replace('</div>\n', '')
            print(f"  HTML: {html_content.strip()}")
        except Exception as e:
            print(f"  ❌ 错误: {e}")

    # 完整示例
    print(f"\n\n{'=' * 60}")
    print("📄 完整文档示例（sample.md）")
    print("=" * 60)
    sample_path = os.path.join(os.path.dirname(__file__), 'sample.md')
    try:
        with open(sample_path, 'r', encoding='utf-8') as f:
            md = f.read()
        ast = parse_markdown(md)
        html = render(ast)
        print(html)
    except Exception as e:
        print(f"  ❌ 错误: {e}")


if __name__ == '__main__':
    demo()
