"""Markdown Tokenizer — 将源文本拆分为 token 流"""

TOKEN_TYPES = {
    'HEADING': 'heading',       # #
    'BOLD': 'bold',             # **
    'ITALIC': 'italic',         # *
    'STRIKETHROUGH': 'strikethrough',  # ~~
    'CODE_INLINE': 'code_inline',      # `
    'CODE_BLOCK': 'code_block',        # ```
    'LINK_START': 'link_start',        # [
    'LINK_END': 'link_end',            # ](url)
    'IMAGE': 'image',                  # ![
    'LIST_UNORDERED': 'list_unordered', # - * +
    'LIST_ORDERED': 'list_ordered',     # 1.
    'QUOTE': 'quote',                   # >
    'HR': 'hr',                         # --- *** ___
    'TABLE': 'table',                   # |
    'TEXT': 'text',
    'NEWLINE': 'newline',
    'EOF': 'eof',
}


class Token:
    def __init__(self, type_, value='', meta=None):
        self.type = type_
        self.value = value
        self.meta = meta or {}

    def __repr__(self):
        return f'Token({self.type}, {repr(self.value[:30])})'


def tokenize(text: str):
    """字符级扫描产生 token 流"""
    import re
    lines = text.split('\n')
    tokens = []
    in_code_block = False
    code_block_lang = ''
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block detection
        if line.strip().startswith('```'):
            if in_code_block:
                tokens.append(Token('CODE_BLOCK_END'))
                in_code_block = False
                tokens.append(Token('NEWLINE'))
            else:
                lang = line.strip()[3:].strip()
                tokens.append(Token('CODE_BLOCK_START', lang))
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            tokens.append(Token('CODE_BLOCK_LINE', line))
            i += 1
            continue

        # 空行
        stripped = line.strip()
        if stripped == '':
            tokens.append(Token('NEWLINE'))
            i += 1
            continue

        # 水平线
        if stripped in ['---', '***', '___'] and len(stripped) >= 3:
            if all(c == stripped[0] for c in stripped):
                tokens.append(Token('HR'))
                tokens.append(Token('NEWLINE'))
                i += 1
                continue

        # 引用块
        if stripped.startswith('>'):
            text_content = stripped[1:].strip()
            tokens.append(Token('QUOTE'))
            line_tokens = _tokenize_inline(text_content)
            tokens.extend(line_tokens)
            tokens.append(Token('NEWLINE'))
            i += 1
            continue

        # 标题
        heading_match = False
        for hl in range(6, 0, -1):
            if stripped.startswith('#' * hl + ' '):
                content = stripped[hl + 1:].strip()
                tokens.append(Token('HEADING', str(hl)))
                line_tokens = _tokenize_inline(content)
                tokens.extend(line_tokens)
                tokens.append(Token('NEWLINE'))
                heading_match = True
                break

        if heading_match:
            i += 1
            continue

        # 列表（有序 + 无序）
        list_match = False

        # 无序列表
        for marker in ['- ', '* ', '+ ']:
            if line.lstrip().startswith(marker):
                indent = len(line) - len(line.lstrip())
                content = line.lstrip()[2:]
                tokens.append(Token('LIST_UNORDERED', str(indent)))
                line_tokens = _tokenize_inline(content)
                tokens.extend(line_tokens)
                tokens.append(Token('NEWLINE'))
                list_match = True
                break

        if list_match:
            i += 1
            continue

        # 有序列表
        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if ordered_match:
            indent = len(ordered_match.group(1))
            num = ordered_match.group(2)
            content = ordered_match.group(3)
            tokens.append(Token('LIST_ORDERED', num))
            line_tokens = _tokenize_inline(content)
            tokens.extend(line_tokens)
            tokens.append(Token('NEWLINE'))
            i += 1
            continue

        # 表格
        if '|' in stripped:
            tokens.append(Token('TABLE'))

        # 普通行
        line_tokens = _tokenize_inline(stripped)
        tokens.extend(line_tokens)
        tokens.append(Token('NEWLINE'))
        i += 1

    return tokens


def _tokenize_inline(text: str):
    """行内 token 化"""
    tokens = []
    i = 0

    while i < len(text):
        ch = text[i]

        # Escape
        if ch == '\\' and i + 1 < len(text):
            tokens.append(Token('TEXT', text[i+1]))
            i += 2
            continue

        # 图片 ![alt](url)
        if text[i:i+2] == '![':
            end = text.find(']', i)
            if end != -1 and end + 1 < len(text) and text[end+1] == '(':
                alt = text[i+2:end]
                url_end = text.find(')', end+1)
                url = text[end+2:url_end] if url_end != -1 else ''
                tokens.append(Token('IMAGE', alt, {'url': url}))
                i = (url_end + 1) if url_end != -1 else end + 2
                continue

        # 行内代码 `
        if ch == '`':
            end = text.find('`', i + 1)
            if end != -1:
                code = text[i+1:end]
                tokens.append(Token('CODE_INLINE', code))
                i = end + 1
                continue
            else:
                tokens.append(Token('TEXT', ch))
                i += 1
                continue

        # 粗体 ** 或 斜体 *
        if text[i:i+3] == '***':
            tokens.append(Token('ITALIC'))
            tokens.append(Token('BOLD'))
            i += 3
            continue

        if text[i:i+2] == '**':
            tokens.append(Token('BOLD'))
            i += 2
            continue

        if ch == '*':
            tokens.append(Token('ITALIC'))
            i += 1
            continue

        # 删除线 ~~
        if text[i:i+2] == '~~':
            tokens.append(Token('STRIKETHROUGH'))
            i += 2
            continue

        # 下划线 _
        if ch == '_':
            tokens.append(Token('ITALIC'))
            i += 1
            continue

        # 链接 [text](url)
        if ch == '[':
            end = text.find(']', i)
            if end != -1 and end + 1 < len(text) and text[end+1] == '(':
                link_text = text[i+1:end]
                url_end = text.find(')', end+1)
                url = text[end+2:url_end] if url_end != -1 else ''
                tokens.append(Token('LINK_START', link_text, {'url': url}))
                i = (url_end + 1) if url_end != -1 else end + 2
                continue

        # 普通字符
        tokens.append(Token('TEXT', ch))
        i += 1

    return tokens
