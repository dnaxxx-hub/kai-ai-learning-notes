"""GraphQL 查询语法解析器"""

import re


class Selection:
    """选择集中的一个字段选择"""

    def __init__(self, name, alias=None, args=None, selections=None):
        self.name = name
        self.alias = alias or name
        self.args = args or {}
        self.selections = selections or []

    def __repr__(self):
        return f"Selection({self.alias}: {self.name}, args={self.args})"


class Document:
    """解析后的 GraphQL 文档"""

    def __init__(self, operations=None):
        self.operations = operations or []

    def __repr__(self):
        return f"Document({self.operations})"


class Operation:
    """操作 (query/mutation)"""

    def __init__(self, operation_type='query', name=None, selections=None, variables=None):
        self.operation_type = operation_type
        self.name = name
        self.selections = selections or []
        self.variables = variables or {}


def parse_query(query_str):
    """解析 GraphQL 查询字符串为 Document"""
    query_str = query_str.strip()
    if not query_str:
        return Document([])

    tokens = _tokenize(query_str)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume(expected=None):
        t = peek()
        if expected and t and t[1] == expected:
            pos[0] += 1
            return t
        elif expected:
            raise SyntaxError(f"期望 {expected}, 得到 {t}")
        pos[0] += 1
        return t

    operations = []

    while peek():
        if peek() and peek()[1] in ('query', 'mutation'):
            op_type = consume()[1]
        else:
            op_type = 'query'

        name = None
        if peek() and peek()[0] == 'NAME':
            name = consume()[1]

        if peek() and peek()[1] == '(':
            _skip_parenthesized_block(tokens, pos)

        selections = _parse_selection_set(tokens, pos)
        operations.append(Operation(op_type, name, selections))

    return Document(operations)


def _skip_parenthesized_block(tokens, pos):
    if pos[0] < len(tokens) and tokens[pos[0]][1] == '(':
        depth = 0
        while pos[0] < len(tokens):
            if tokens[pos[0]][1] == '(':
                depth += 1
            elif tokens[pos[0]][1] == ')':
                depth -= 1
                if depth == 0:
                    pos[0] += 1
                    return
            pos[0] += 1


def _tokenize(query_str):
    tokens = []
    i = 0

    token_patterns = [
        (r'[{}():,!\[\]$@]', lambda m: (m.group(), m.group())),
        (r'"(?:[^"\\]|\\.)*"', lambda m: ('STRING', m.group())),
        (r'[a-zA-Z_][a-zA-Z0-9_]*', lambda m: ('NAME', m.group())),
        (r'-?\d+\.\d+', lambda m: ('FLOAT', float(m.group()))),
        (r'-?\d+', lambda m: ('INT', int(m.group()))),
        (r'\s+|#[^\n]*', None),
    ]

    while i < len(query_str):
        match = None
        for pattern, action in token_patterns:
            m = re.match(pattern, query_str[i:])
            if m:
                if action:
                    token = action(m)
                    tokens.append(token)
                i += m.end()
                match = True
                break
        if not match:
            raise SyntaxError(f"无法解析: {query_str[i:i+20]!r}")

    return tokens


def _is_token(tokens, pos, expected):
    """Check if the token at pos has the given value"""
    return pos[0] < len(tokens) and tokens[pos[0]][1] == expected


def _parse_selection_set(tokens, pos):
    selections = []

    if pos[0] < len(tokens) and tokens[pos[0]][1] == '{':
        pos[0] += 1

    while pos[0] < len(tokens) and tokens[pos[0]][1] != '}':
        if tokens[pos[0]][1] == '{':
            pos[0] += 1
            continue

        token = tokens[pos[0]]
        if token[0] != 'NAME':
            pos[0] += 1
            continue

        name = token[1]
        alias_name = None
        pos[0] += 1

        # 别名: alias: RealField
        if (peek_token(tokens, pos) and tokens[pos[0]][1] == ':'
                and pos[0] + 1 < len(tokens) and tokens[pos[0] + 1][0] == 'NAME'):
            alias_name = name
            pos[0] += 1  # skip ':'
            name = tokens[pos[0]][1]
            pos[0] += 1

        # 参数
        args = _parse_args(tokens, pos)

        # 子选择集
        sub_selections = []
        if peek_token(tokens, pos) and tokens[pos[0]][1] == '{':
            pos[0] += 1
            sub_selections = _parse_selection_set(tokens, pos)

        selections.append(Selection(name, alias_name or name, args, sub_selections))

    if pos[0] < len(tokens) and tokens[pos[0]][1] == '}':
        pos[0] += 1

    return selections


def _parse_args(tokens, pos):
    """解析参数列表"""
    args = {}
    if peek_token(tokens, pos) and tokens[pos[0]][1] == '(':
        pos[0] += 1  # skip (
        while pos[0] < len(tokens) and tokens[pos[0]][1] != ')':
            # Skip commas
            if tokens[pos[0]][1] == ',':
                pos[0] += 1
                continue

            arg_name = tokens[pos[0]][1]
            pos[0] += 1

            # Skip colon
            if pos[0] < len(tokens) and tokens[pos[0]][1] == ':':
                pos[0] += 1

            if pos[0] < len(tokens):
                value_token = tokens[pos[0]]
                pos[0] += 1
                args[arg_name] = _parse_value(value_token)

        if pos[0] < len(tokens) and tokens[pos[0]][1] == ')':
            pos[0] += 1
    return args


def _parse_value(value_token):
    if value_token[0] == 'STRING':
        s = value_token[1]
        return s[1:-1] if s.startswith('"') else s
    elif value_token[0] in ('INT', 'FLOAT'):
        return value_token[1]
    else:
        return value_token[1]


def peek_token(tokens, pos):
    return pos[0] < len(tokens)
