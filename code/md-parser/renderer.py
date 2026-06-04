"""HTML Renderer — AST → HTML"""
from parser import Node


def render(ast: Node) -> str:
    """渲染 AST 为 HTML 字符串"""
    # Check if the document is standalone (no wrapper needed)
    html = '<div class="markdown-body">\n'
    for child in ast.children:
        html += _render_node(child, 1)
    html += '</div>\n'
    return html


def render_standalone(ast: Node, title: str = "Markdown") -> str:
    """渲染为完整的独立 HTML 文档"""
    body = ''
    for child in ast.children:
        body += _render_node(child, 0)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape_html(title)}</title>
<style>
.markdown-body {{
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #333;
}}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
}}
.markdown-body h1 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
.markdown-body h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
.markdown-body h3 {{ font-size: 1.25em; }}
.markdown-body pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; }}
.markdown-body code {{ background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }}
.markdown-body pre code {{ background: none; padding: 0; }}
.markdown-body blockquote {{ border-left: 4px solid #dfe2e5; padding: 0 1em; color: #6a737d; margin: 0; }}
.markdown-body table {{ border-collapse: collapse; width: 100%; }}
.markdown-body th, .markdown-body td {{ border: 1px solid #dfe2e5; padding: 6px 13px; text-align: left; }}
.markdown-body th {{ background: #f6f8fa; font-weight: 600; }}
.markdown-body img {{ max-width: 100%; }}
.markdown-body hr {{ border: 0; border-top: 2px solid #eee; }}
</style>
</head>
<body>
<div class="markdown-body">
{body}
</div>
</body>
</html>
'''
    return html


def _render_node(node: Node, indent: int = 0) -> str:
    """渲染单个节点"""
    prefix = '  ' * indent
    html = ''

    if node.type == 'heading':
        level = node.meta.get('level', 1)
        content = _render_inline(node.children)
        html += f'{prefix}<h{level}>{content}</h{level}>\n'

    elif node.type == 'paragraph':
        content = _render_inline(node.children)
        html += f'{prefix}<p>{content}</p>\n'

    elif node.type == 'ul':
        html += f'{prefix}<ul>\n'
        for child in node.children:
            html += _render_node(child, indent + 1)
        html += f'{prefix}</ul>\n'

    elif node.type == 'ol':
        html += f'{prefix}<ol>\n'
        for child in node.children:
            html += _render_node(child, indent + 1)
        html += f'{prefix}</ol>\n'

    elif node.type == 'li':
        content = _render_inline(node.children)
        html += f'{prefix}<li>{content}</li>\n'

    elif node.type == 'quote':
        content = _render_inline(node.children)
        html += f'{prefix}<blockquote><p>{content}</p></blockquote>\n'

    elif node.type == 'hr':
        html += f'{prefix}<hr>\n'

    elif node.type == 'code_block':
        lang = node.meta.get('lang', '')
        code = node.meta.get('code', '')
        lang_attr = f' class="language-{lang}"' if lang else ''
        html += f'{prefix}<pre><code{lang_attr}>{_escape_html(code)}</code></pre>\n'

    elif node.type == 'table':
        html += f'{prefix}<table>\n'
        # 表头
        if node.meta.get('headers'):
            html += f'{prefix}  <thead>\n{prefix}    <tr>\n'
            for h in node.meta['headers']:
                html += f'{prefix}      <th>{_escape_html(h)}</th>\n'
            html += f'{prefix}    </tr>\n{prefix}  </thead>\n'
        # 表体
        if node.meta.get('rows'):
            html += f'{prefix}  <tbody>\n'
            for row in node.meta['rows']:
                html += f'{prefix}    <tr>\n'
                for cell in row:
                    html += f'{prefix}      <td>{_escape_html(cell)}</td>\n'
                html += f'{prefix}    </tr>\n'
            html += f'{prefix}  </tbody>\n'
        html += f'{prefix}</table>\n'

    return html


def _render_inline(tokens) -> str:
    """渲染 inline token 列表为 HTML"""
    result = []
    i = 0
    bold_open = False
    italic_open = False
    strike_open = False

    while i < len(tokens):
        tok = tokens[i]

        if tok.type == 'TEXT':
            result.append(_escape_html(tok.value))

        elif tok.type == 'BOLD':
            if bold_open:
                result.append('</strong>')
                bold_open = False
            else:
                result.append('<strong>')
                bold_open = True

        elif tok.type == 'ITALIC':
            if italic_open:
                result.append('</em>')
                italic_open = False
            else:
                result.append('<em>')
                italic_open = True

        elif tok.type == 'STRIKETHROUGH':
            if strike_open:
                result.append('</del>')
                strike_open = False
            else:
                result.append('<del>')
                strike_open = True

        elif tok.type == 'CODE_INLINE':
            result.append(f'<code>{_escape_html(tok.value)}</code>')

        elif tok.type == 'LINK_START':
            url = tok.meta.get('url', '')
            text = tok.value
            result.append(f'<a href="{_escape_html(url)}">{_escape_html(text)}</a>')

        elif tok.type == 'IMAGE':
            alt = tok.value
            url = tok.meta.get('url', '')
            result.append(f'<img src="{_escape_html(url)}" alt="{_escape_html(alt)}">')

        i += 1

    return ''.join(result)


def _escape_html(text: str) -> str:
    """HTML 转义"""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
