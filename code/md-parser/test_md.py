"""Markdown 解析器测试"""
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from tokenizer import tokenize
from parser import parse_markdown
from renderer import render, _escape_html


class TestTokenizer(unittest.TestCase):
    def test_heading(self):
        tokens = tokenize("# Hello")
        heading_tokens = [t for t in tokens if t.type == 'HEADING']
        self.assertEqual(len(heading_tokens), 1)
        self.assertEqual(heading_tokens[0].value, '1')

    def test_heading_levels(self):
        for level in range(1, 7):
            tokens = tokenize("#" * level + " Test")
            headings = [t for t in tokens if t.type == 'HEADING']
            self.assertEqual(len(headings), 1)
            self.assertEqual(headings[0].value, str(level))

    def test_bold_italic(self):
        tokens = tokenize("**bold** *italic*")
        types = [t.type for t in tokens]
        self.assertIn('BOLD', types)
        self.assertIn('ITALIC', types)

    def test_code_inline(self):
        tokens = tokenize("`code`")
        codes = [t for t in tokens if t.type == 'CODE_INLINE']
        self.assertEqual(len(codes), 1)
        self.assertEqual(codes[0].value, 'code')

    def test_code_block(self):
        tokens = tokenize("```python\nprint('hi')\n```")
        has_start = any(t.type == 'CODE_BLOCK_START' for t in tokens)
        self.assertTrue(has_start)

    def test_strikethrough(self):
        tokens = tokenize("~~strike~~")
        types = [t.type for t in tokens]
        self.assertIn('STRIKETHROUGH', types)

    def test_link(self):
        tokens = tokenize("[text](url)")
        links = [t for t in tokens if t.type == 'LINK_START']
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].value, 'text')
        self.assertEqual(links[0].meta['url'], 'url')

    def test_image(self):
        tokens = tokenize("![alt](img.png)")
        imgs = [t for t in tokens if t.type == 'IMAGE']
        self.assertEqual(len(imgs), 1)
        self.assertEqual(imgs[0].value, 'alt')
        self.assertEqual(imgs[0].meta['url'], 'img.png')

    def test_hr(self):
        for marker in ['---', '***', '___']:
            tokens = tokenize(marker)
            hrs = [t for t in tokens if t.type == 'HR']
            self.assertEqual(len(hrs), 1, f"Failed for {marker}")

    def test_unordered_list_markers(self):
        for marker in ['- ', '* ', '+ ']:
            tokens = tokenize(f"{marker}item")
            lists = [t for t in tokens if t.type == 'LIST_UNORDERED']
            self.assertEqual(len(lists), 1, f"Failed for {marker}")

    def test_ordered_list(self):
        tokens = tokenize("1. first")
        lists = [t for t in tokens if t.type == 'LIST_ORDERED']
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].value, '1')

    def test_quote(self):
        tokens = tokenize("> quoted text")
        quotes = [t for t in tokens if t.type == 'QUOTE']
        self.assertEqual(len(quotes), 1)

    def test_escape(self):
        tokens = tokenize("\\*not italic\\*")
        texts = [t for t in tokens if t.type == 'TEXT']
        text_values = ''.join(t.value for t in tokens if t.type == 'TEXT')
        self.assertIn('*', text_values)


class TestParser(unittest.TestCase):
    def test_parse_heading(self):
        ast = parse_markdown("# Title")
        self.assertEqual(len(ast.children), 1)
        self.assertEqual(ast.children[0].type, 'heading')
        self.assertEqual(ast.children[0].meta['level'], 1)

    def test_parse_unordered_list(self):
        ast = parse_markdown("- item1\n- item2")
        ul = [c for c in ast.children if c.type == 'ul']
        self.assertEqual(len(ul), 1)
        self.assertEqual(len(ul[0].children), 2)

    def test_parse_ordered_list(self):
        ast = parse_markdown("1. first\n2. second")
        ol = [c for c in ast.children if c.type == 'ol']
        self.assertEqual(len(ol), 1)
        self.assertEqual(len(ol[0].children), 2)

    def test_parse_nested_list(self):
        ast = parse_markdown("- a\n  - b\n- c")
        ul = [c for c in ast.children if c.type == 'ul']
        self.assertEqual(len(ul), 1)

    def test_parse_table(self):
        md = "| H1 | H2 |\n|----|----|\n| C1 | C2 |"
        ast = parse_markdown(md)
        tables = [c for c in ast.children if c.type == 'table']
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0].meta['headers']), 2)
        self.assertEqual(len(tables[0].meta['rows']), 1)

    def test_parse_code_block(self):
        ast = parse_markdown("```python\nx=1\n```")
        blocks = [c for c in ast.children if c.type == 'code_block']
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].meta['lang'], 'python')
        self.assertIn('x=1', blocks[0].meta['code'])

    def test_parse_hr(self):
        ast = parse_markdown("---")
        hrs = [c for c in ast.children if c.type == 'hr']
        self.assertEqual(len(hrs), 1)

    def test_parse_quote(self):
        ast = parse_markdown("> quoted")
        quotes = [c for c in ast.children if c.type == 'quote']
        self.assertEqual(len(quotes), 1)


class TestRenderer(unittest.TestCase):
    def test_render_heading(self):
        ast = parse_markdown("# Hello")
        html = render(ast)
        self.assertIn('<h1>', html)
        self.assertIn('Hello', html)
        self.assertIn('</h1>', html)

    def test_render_paragraph(self):
        ast = parse_markdown("Hello World")
        html = render(ast)
        self.assertIn('<p>', html)
        self.assertIn('Hello World', html)

    def test_render_bold(self):
        ast = parse_markdown("**bold**")
        html = render(ast)
        self.assertIn('<strong>bold</strong>', html)

    def test_render_italic(self):
        ast = parse_markdown("*italic*")
        html = render(ast)
        self.assertIn('<em>italic</em>', html)

    def test_render_strikethrough(self):
        ast = parse_markdown("~~strike~~")
        html = render(ast)
        self.assertIn('<del>strike</del>', html)

    def test_render_code_inline(self):
        ast = parse_markdown("`code`")
        html = render(ast)
        self.assertIn('<code>code</code>', html)

    def test_render_link(self):
        ast = parse_markdown("[GitHub](https://github.com)")
        html = render(ast)
        self.assertIn('<a href="https://github.com">GitHub</a>', html)

    def test_render_image(self):
        ast = parse_markdown("![Alt](https://example.com/img.png)")
        html = render(ast)
        self.assertIn('<img src="https://example.com/img.png" alt="Alt">', html)

    def test_render_unordered_list(self):
        ast = parse_markdown("- a\n- b")
        html = render(ast)
        self.assertIn('<ul>', html)
        self.assertIn('<li>', html)

    def test_render_ordered_list(self):
        ast = parse_markdown("1. first\n2. second")
        html = render(ast)
        self.assertIn('<ol>', html)
        self.assertIn('<li>first</li>', html)

    def test_render_hr(self):
        ast = parse_markdown("---")
        html = render(ast)
        self.assertIn('<hr>', html)

    def test_render_code_block(self):
        ast = parse_markdown("```python\nx=1\n```")
        html = render(ast)
        self.assertIn('<pre><code class="language-python">', html)
        self.assertIn('x=1', html)

    def test_render_blockquote(self):
        ast = parse_markdown("> quote")
        html = render(ast)
        self.assertIn('<blockquote>', html)

    def test_html_escape(self):
        self.assertEqual(_escape_html('<div>'), '&lt;div&gt;')
        self.assertEqual(_escape_html('a&b'), 'a&amp;b')
        self.assertEqual(_escape_html('"quote"'), '&quot;quote&quot;')
        self.assertEqual(_escape_html('a<b>c&d'), 'a&lt;b&gt;c&amp;d')

    def test_render_nested_formatting(self):
        ast = parse_markdown("**bold *and italic***")
        html = render(ast)
        self.assertIn('<strong>', html)
        self.assertIn('<em>', html)
        self.assertIn('</strong>', html)
        self.assertIn('</em>', html)

    def test_sample_file(self):
        """加载 sample.md 并验证基本结构"""
        sample_path = os.path.join(os.path.dirname(__file__), 'sample.md')
        with open(sample_path, 'r', encoding='utf-8') as f:
            md = f.read()
        ast = parse_markdown(md)
        html = render(ast)
        # Should have various elements
        self.assertIn('<h1>', html)
        self.assertIn('<h2>', html)
        self.assertIn('<h3>', html)
        self.assertIn('<p>', html)
        self.assertIn('<strong>', html)
        self.assertIn('<em>', html)
        self.assertIn('<del>', html)
        self.assertIn('<code>', html)
        self.assertIn('<a href', html)
        self.assertIn('<pre><code class="language-python">', html)
        self.assertIn('<ul>', html)
        self.assertIn('<ol>', html)
        self.assertIn('<blockquote>', html)
        self.assertIn('<hr>', html)
        self.assertIn('<table>', html)


if __name__ == '__main__':
    unittest.main()
