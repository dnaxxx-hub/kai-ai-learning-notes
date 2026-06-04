from lexer import tokenize


class Expr:
    pass


class Variable(Expr):
    def __init__(self, name):
        self.name = name  # 'user.name' → 'user.name'

    def __repr__(self):
        return f'Var({self.name})'


class Filtered(Expr):
    def __init__(self, expr, filter_name, args=None):
        self.expr = expr
        self.filter_name = filter_name
        self.args = args or []

    def __repr__(self):
        return f'Filter({self.expr}|{self.filter_name})'


class Number(Expr):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Num({self.value})'


class String(Expr):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Str({self.value})'


class BinOp(Expr):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f'({self.left} {self.op} {self.right})'


class Compare(Expr):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f'Cmp({self.left} {self.op} {self.right})'


class Node:
    pass


class TextNode(Node):
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f'Text({self.text!r})'


class VariableNode(Node):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f'VarNode({self.expr})'


class ForNode(Node):
    def __init__(self, var, iter_expr, body, else_body=None):
        self.var = var
        self.iter_expr = iter_expr
        self.body = body
        self.else_body = else_body or []

    def __repr__(self):
        return f'For({self.var} in {self.iter_expr})'


class IfNode(Node):
    def __init__(self, condition, body, elifs=None, else_body=None):
        self.condition = condition
        self.body = body
        self.elifs = elifs or []
        self.else_body = else_body or []

    def __repr__(self):
        return f'If({self.condition})'


class SetNode(Node):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def __repr__(self):
        return f'Set({self.name} = {self.expr})'


class BlockNode(Node):
    def __init__(self, name, body):
        self.name = name
        self.body = body

    def __repr__(self):
        return f'Block({self.name})'


class ExtendsNode(Node):
    def __init__(self, template):
        self.template = template

    def __repr__(self):
        return f'Extends({self.template})'


class Document(Node):
    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return f'Document({self.body})'


def parse(template):
    """入口"""
    tokens = tokenize(template)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    body = _parse_nodes(tokens, pos)
    return Document(body)


def _is_end_block(tokens, pos, keywords):
    """Check if current position starts a block with one of the given keywords (e.g., endif, endfor, else, elif)."""
    if pos >= len(tokens):
        return None
    if tokens[pos][0] != 'BLOCK_START':
        return None
    if pos + 1 >= len(tokens):
        return None
    kw = tokens[pos + 1][1]
    if kw in keywords:
        return kw
    return None


def _skip_block_end(tokens, pos):
    """Consume BLOCK_END at current position if present."""
    if pos[0] < len(tokens) and tokens[pos[0]][0] == 'BLOCK_END':
        pos[0] += 1


def peek_token(tokens, pos):
    return pos[0] < len(tokens)


def _parse_nodes(tokens, pos, end_on=None):
    """Parse nodes. end_on is a set of block keywords that terminate parsing (e.g., {'endif', 'else', 'elif'})."""
    nodes = []
    while pos[0] < len(tokens):
        tok = tokens[pos[0]]

        # Check if we've hit a terminator block
        if end_on:
            kw = _is_end_block(tokens, pos[0], end_on)
            if kw and kw in end_on:
                break

        if tok[0] == 'TEXT':
            nodes.append(TextNode(tok[1]))
            pos[0] += 1

        elif tok[0] == 'VARIABLE_START':
            pos[0] += 1
            expr = _parse_expression(tokens, pos)
            if peek_token(tokens, pos) and tokens[pos[0]][0] == 'VARIABLE_END':
                pos[0] += 1
            nodes.append(VariableNode(expr))

        elif tok[0] == 'BLOCK_START':
            pos[0] += 1
            if pos[0] >= len(tokens):
                continue
            keyword = tokens[pos[0]][1]
            pos[0] += 1

            if keyword == 'for':
                var = None
                if peek_token(tokens, pos) and tokens[pos[0]][0] == 'NAME':
                    var = tokens[pos[0]][1]
                    pos[0] += 1
                if peek_token(tokens, pos) and tokens[pos[0]][1] == 'in':
                    pos[0] += 1
                iter_expr = _parse_expression(tokens, pos) if peek_token(tokens, pos) else None
                _skip_block_end(tokens, pos)

                body = []
                else_body = []
                while pos[0] < len(tokens):
                    kw = _is_end_block(tokens, pos[0], {'endfor', 'else'})
                    if kw == 'endfor':
                        pos[0] += 2  # skip BLOCK_START + NAME
                        _skip_block_end(tokens, pos)
                        break
                    elif kw == 'else':
                        pos[0] += 2
                        _skip_block_end(tokens, pos)
                        else_body = _parse_nodes(tokens, pos, {'endfor'})
                        if _is_end_block(tokens, pos[0], {'endfor'}):
                            pos[0] += 2
                            _skip_block_end(tokens, pos)
                        break
                    else:
                        # Use _parse_nodes to handle nested blocks recursively
                        node = _parse_nodes(tokens, pos, {'endfor', 'else'})
                        if node:
                            body.extend(node)
                        else:
                            pos[0] += 1
                nodes.append(ForNode(var, iter_expr, body, else_body))

            elif keyword == 'if':
                condition = _parse_expression(tokens, pos)
                _skip_block_end(tokens, pos)

                body = _parse_nodes(tokens, pos, {'else', 'elif', 'endif'})
                elifs = []
                else_body = []

                while pos[0] < len(tokens):
                    kw = _is_end_block(tokens, pos[0], {'elif', 'else', 'endif'})
                    if kw == 'elif':
                        pos[0] += 2
                        cond = _parse_expression(tokens, pos)
                        _skip_block_end(tokens, pos)
                        elif_body = _parse_nodes(tokens, pos, {'else', 'elif', 'endif'})
                        elifs.append((cond, elif_body))
                    elif kw == 'else':
                        pos[0] += 2
                        _skip_block_end(tokens, pos)
                        else_body = _parse_nodes(tokens, pos, {'endif'})
                    elif kw == 'endif':
                        pos[0] += 2
                        _skip_block_end(tokens, pos)
                        break
                    else:
                        break

                nodes.append(IfNode(condition, body, elifs, else_body))

            elif keyword == 'set':
                name = None
                if peek_token(tokens, pos) and tokens[pos[0]][0] == 'NAME':
                    name = tokens[pos[0]][1]
                    pos[0] += 1
                if peek_token(tokens, pos) and tokens[pos[0]][1] == '=':
                    pos[0] += 1
                expr = _parse_expression(tokens, pos)
                if peek_token(tokens, pos) and tokens[pos[0]][0] == 'BLOCK_END':
                    pos[0] += 1
                nodes.append(SetNode(name, expr))

            elif keyword == 'block':
                name = None
                if peek_token(tokens, pos) and tokens[pos[0]][0] == 'NAME':
                    name = tokens[pos[0]][1]
                    pos[0] += 1
                _skip_block_end(tokens, pos)
                body = _parse_nodes(tokens, pos, {'endblock'})
                if _is_end_block(tokens, pos[0], {'endblock'}):
                    pos[0] += 2
                    _skip_block_end(tokens, pos)
                nodes.append(BlockNode(name, body))

            elif keyword == 'extends':
                template_name = None
                if peek_token(tokens, pos):
                    if tokens[pos[0]][0] == 'STRING':
                        template_name = tokens[pos[0]][1]
                        pos[0] += 1
                    elif tokens[pos[0]][0] == 'NAME':
                        template_name = tokens[pos[0]][1]
                        pos[0] += 1
                if template_name:
                    nodes.append(ExtendsNode(template_name))
                if peek_token(tokens, pos) and tokens[pos[0]][0] == 'BLOCK_END':
                    pos[0] += 1

        elif tok[0] == 'COMMENT':
            pos[0] += 1

        else:
            pos[0] += 1

    return nodes


def _parse_node(tokens, pos):
    """Parse a single node from current position (helper for for-body parsing)."""
    if pos[0] >= len(tokens):
        return None
    tok = tokens[pos[0]]

    if tok[0] == 'TEXT':
        pos[0] += 1
        return TextNode(tok[1])

    if tok[0] == 'VARIABLE_START':
        pos[0] += 1
        expr = _parse_expression(tokens, pos)
        if peek_token(tokens, pos) and tokens[pos[0]][0] == 'VARIABLE_END':
            pos[0] += 1
        return VariableNode(expr)

    if tok[0] == 'BLOCK_START':
        # If it's a closing tag we don't handle here — return None
        if _is_end_block(tokens, pos[0], {'endfor', 'endif', 'endblock', 'else', 'elif'}):
            return None
        # Skip nested blocks in simple mode
        pos[0] += 2  # skip BLOCK_START + NAME
        # Try to skip to BLOCK_END
        _skip_block_end(tokens, pos)
        return None

    if tok[0] == 'COMMENT':
        pos[0] += 1
        return None

    pos[0] += 1
    return None


def _skip_block_end(tokens, pos):
    """Consume BLOCK_END if present."""
    if pos[0] < len(tokens) and tokens[pos[0]][0] == 'BLOCK_END':
        pos[0] += 1


def _parse_expression(tokens, pos):
    """解析表达式（简化版，支持管道链）"""
    # 第一级：字面量/变量
    tok = tokens[pos[0]] if pos[0] < len(tokens) else None
    if tok is None:
        return None

    if tok[0] == 'NUMBER':
        pos[0] += 1
        expr = Number(float(tok[1]) if '.' in tok[1] else int(tok[1]))
    elif tok[0] == 'STRING':
        pos[0] += 1
        expr = String(tok[1].strip("'\""))
    elif tok[0] == 'NAME':
        name = tok[1]
        pos[0] += 1
        # 点号路径
        while pos[0] < len(tokens) and tokens[pos[0]][0] == 'DOT':
            pos[0] += 1
            if pos[0] < len(tokens) and tokens[pos[0]][0] == 'NAME':
                name += '.' + tokens[pos[0]][1]
                pos[0] += 1
        expr = Variable(name)
    else:
        expr = None

    # 第二级：管道过滤器
    while expr is not None and pos[0] < len(tokens) and tokens[pos[0]][0] == 'PIPE':
        pos[0] += 1
        filter_name = tokens[pos[0]][1] if pos[0] < len(tokens) else None
        pos[0] += 1
        args = []
        if pos[0] < len(tokens) and tokens[pos[0]][0] == 'LPAREN':
            pos[0] += 1  # (
            while pos[0] < len(tokens) and tokens[pos[0]][0] != 'RPAREN':
                arg = _parse_expression(tokens, pos)
                if arg:
                    args.append(arg)
                if pos[0] < len(tokens) and tokens[pos[0]][0] == 'COMMA':
                    pos[0] += 1
            if pos[0] < len(tokens) and tokens[pos[0]][0] == 'RPAREN':
                pos[0] += 1
        expr = Filtered(expr, filter_name, args)

    # 比较运算
    if expr is not None and pos[0] < len(tokens) and tokens[pos[0]][0] == 'COMP':
        op = tokens[pos[0]][1]
        pos[0] += 1
        right = _parse_expression(tokens, pos)
        expr = Compare(expr, op, right)

    return expr
