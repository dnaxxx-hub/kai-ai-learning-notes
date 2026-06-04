"""Markdown Parser — 将 token 流转换为 AST"""
from tokenizer import Token, tokenize


class Node:
    """AST 节点"""
    def __init__(self, type_, children=None, meta=None):
        self.type = type_
        self.children = children or []
        self.meta = meta or {}

    def __repr__(self):
        return f'Node({self.type}, {len(self.children)} children)'


def parse(tokens):
    """解析 token 流为 AST"""
    root = Node('document')
    i = 0
    current_list = None

    while i < len(tokens):
        tok = tokens[i]

        if tok.type == 'HEADING':
            level = int(tok.value)
            inline = _parse_inline_until_newline(tokens, i + 1)
            heading = Node('heading', inline, {'level': level})
            root.children.append(heading)
            i += len(inline) + 1

        elif tok.type == 'QUOTE':
            inline = _parse_inline_until_newline(tokens, i + 1)
            quote = Node('quote', inline)
            root.children.append(quote)
            i += len(inline) + 1

        elif tok.type == 'LIST_UNORDERED':
            if current_list is None or current_list.type != 'ul':
                current_list = Node('ul')
                root.children.append(current_list)
            indent = int(tok.value)
            text_tokens = _parse_inline_until_newline(tokens, i + 1)
            item = Node('li', text_tokens)
            current_list.children.append(item)
            i += len(text_tokens) + 1

        elif tok.type == 'LIST_ORDERED':
            if current_list is None or current_list.type != 'ol':
                current_list = Node('ol')
                root.children.append(current_list)
            text_tokens = _parse_inline_until_newline(tokens, i + 1)
            item = Node('li', text_tokens)
            current_list.children.append(item)
            i += len(text_tokens) + 1

        elif tok.type == 'HR':
            root.children.append(Node('hr'))
            i += 1

        elif tok.type == 'CODE_BLOCK_START':
            lang = tok.value
            code_lines = []
            i += 1
            while i < len(tokens) and tokens[i].type != 'CODE_BLOCK_END':
                if tokens[i].type == 'CODE_BLOCK_LINE':
                    code_lines.append(tokens[i].value)
                i += 1
            code_block = Node('code_block', [], {'lang': lang, 'code': '\n'.join(code_lines)})
            root.children.append(code_block)
            i += 1  # skip CODE_BLOCK_END

        elif tok.type == 'TABLE':
            table_rows = _parse_table_rows(tokens, i)
            if len(table_rows) >= 2:
                # First row is headers, skip separator row if it matches |---|---| pattern
                rows = []
                for row in table_rows:
                    if any(cell.strip().replace('-', '').strip() == '' for cell in row):
                        # Could be separator row — check if all cells are dashes
                        if all(all(ch in '-:' for ch in cell.strip()) for cell in row):
                            continue
                    rows.append(row)
                if len(rows) >= 2:
                    table = Node('table', [], {'headers': rows[0], 'rows': rows[1:]})
                    root.children.append(table)
                elif len(rows) == 1:
                    table = Node('table', [], {'headers': rows[0], 'rows': []})
                    root.children.append(table)
            # Skip all table tokens
            while i < len(tokens):
                if tokens[i].type == 'NEWLINE':
                    i += 1
                    # Check for double newline (end of table)
                    if i < len(tokens) and tokens[i].type == 'NEWLINE':
                        break
                else:
                    i += 1
            continue

        elif tok.type == 'NEWLINE':
            i += 1

        else:
            # 段落
            inline = _parse_inline_until_newline(tokens, i)
            if inline:
                para = Node('paragraph', inline)
                root.children.append(para)
                i += len(inline)
                if i < len(tokens) and tokens[i].type == 'NEWLINE':
                    i += 1
                current_list = None
            else:
                i += 1

    return root


def _parse_table_rows(tokens, start):
    """解析表格行
    
    每一行由以下 token 序列构成（以 | col1 | col2 | col3 | 为例）：
    - TABLE token（标记行开始）
    - TEXT('|'), TEXT(' '), TEXT('col1'), TEXT(' '), TEXT('|'), ...
    
    我们忽略行首的 TABLE token，以 '|' TEXT 作为列分隔符。
    """
    rows = []
    i = start
    current_row_cells = []
    current_cell = ''
    in_row = False  # whether we're inside a table row (after first |)

    def _flush_row():
        nonlocal current_cell, current_row_cells, in_row
        if current_cell:
            current_row_cells.append(current_cell.strip())
            current_cell = ''
        if current_row_cells:
            # Strip leading empty cell (from leading |)
            while current_row_cells and current_row_cells[0] == '':
                current_row_cells.pop(0)
            # Strip trailing empty cell (from trailing |)
            while current_row_cells and current_row_cells[-1] == '':
                current_row_cells.pop()
            # Filter out rows that are just dashes (separator row)
            if current_row_cells and not _is_separator_row(current_row_cells):
                rows.append(list(current_row_cells))
            current_row_cells = []
        in_row = False

    while i < len(tokens):
        tok = tokens[i]

        if tok.type == 'NEWLINE':
            # End of current row
            _flush_row()
            # Check for double newline or non-table content = end of table
            if i + 1 < len(tokens) and tokens[i+1].type == 'NEWLINE':
                break
            # Check if next non-newline token is something other than TABLE
            j = i + 1
            while j < len(tokens) and tokens[j].type == 'NEWLINE':
                j += 1
            if j < len(tokens) and tokens[j].type != 'TABLE':
                break
            i += 1

        elif tok.type == 'TABLE':
            # Start of a new row (the | at line beginning)
            # If we have an existing row not yet flushed, flush it first
            if in_row or current_row_cells:
                _flush_row()
            in_row = True
            i += 1

        elif tok.type == 'TEXT':
            ch = tok.value
            if ch == '|':
                # Column separator within a row
                current_row_cells.append(current_cell.strip())
                current_cell = ''
            else:
                current_cell += ch
            i += 1

        else:
            # Any other inline tokens inside table cells
            if tok.type == 'IMAGE':
                current_cell += tok.value
            elif tok.type == 'LINK_START':
                current_cell += tok.value
            elif tok.type == 'CODE_INLINE':
                current_cell += tok.value
            else:
                current_cell += tok.value
            i += 1

    # Flush last row
    _flush_row()

    return rows


def _is_separator_row(cells):
    """判断是否为表格分隔行（如 |---|---|）"""
    for cell in cells:
        cell = cell.strip()
        # Pattern: only dashes, colons, and spaces
        if any(c not in '-: ' for c in cell):
            return False
    return True


def _parse_inline_until_newline(tokens, start):
    """从 start 开始收集 inline token 直到遇到 NEWLINE 或 EOF"""
    result = []
    i = start

    while i < len(tokens) and tokens[i].type != 'NEWLINE':
        tok = tokens[i]
        result.append(tok)
        i += 1

    return result


def parse_markdown(text: str):
    """方便入口：文本 → AST"""
    tokens = tokenize(text)
    return parse(tokens)
