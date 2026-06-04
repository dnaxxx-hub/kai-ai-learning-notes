import re

# Expression-level tokens (used inside {{ }} and {% %})
EXPR_TOKENS = [
    ('COMMENT', r'\{\#.*?\#\}'),
    ('NUMBER', r'\d+\.?\d*'),
    ('STRING', r"'[^']*'|\"[^\"]*\""),
    ('NAME', r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('DOT', r'\.'),
    ('PIPE', r'\|'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('COMMA', r','),
    ('COLON', r':'),
    ('COMP', r'==|!=|<=|>=|<|>'),  # Must come before ASSIGN
    ('ASSIGN', r'='),
    ('OP', r'[+\-*/%]'),
    ('NOT', r'not\b'),
    ('AND', r'and\b'),
    ('OR', r'or\b'),
    ('IN', r'in\b'),
]

# Delimiter patterns
DELIMITERS = re.compile(r'\{\#.*?\#\}|\{\{|\}\}|\{%|%\}')


def _tokenize_expr(text):
    """Tokenize content inside {{ }} or {% %} blocks (without delimiters)."""
    tokens = []
    pos = 0
    while pos < len(text):
        # Skip whitespace inside expressions
        m = re.match(r'\s+', text[pos:])
        if m:
            pos += m.end()
            continue
        matched = False
        for name, pattern in EXPR_TOKENS:
            m = re.match(pattern, text[pos:])
            if m:
                if name == 'COMMENT':
                    pos += m.end()
                    matched = True
                    break
                if name == 'STRING':
                    tokens.append(('STRING', m.group()[1:-1]))
                elif name == 'NUMBER':
                    tokens.append(('NUMBER', m.group()))
                elif name == 'NAME':
                    tokens.append(('NAME', m.group()))
                else:
                    tokens.append((name, m.group()))
                pos += m.end()
                matched = True
                break
        if not matched:
            pos += 1
    return tokens


def tokenize(template):
    tokens = []
    pos = 0
    text_buf = []

    def flush_text():
        if text_buf:
            text = ''.join(text_buf)
            if text:
                tokens.append(('TEXT', text))
            text_buf.clear()

    while pos < len(template):
        # Check for comment
        m = re.match(r'\{\#', template[pos:])
        if m:
            flush_text()
            end = template.find('#}', pos + 2)
            if end == -1:
                end = len(template)
            else:
                end += 2
            tokens.append(('COMMENT', template[pos:end]))
            pos = end
            continue

        # Check for {{
        m = re.match(r'\{\{', template[pos:])
        if m:
            flush_text()
            tokens.append(('VARIABLE_START', '{{'))
            pos += 2
            # Find closing }}
            end = template.find('}}', pos)
            if end == -1:
                end = len(template)
            inner = template[pos:end]
            expr_tokens = _tokenize_expr(inner)
            tokens.extend(expr_tokens)
            tokens.append(('VARIABLE_END', '}}'))
            pos = end + 2 if end != -1 else len(template)
            continue

        # Check for {%
        m = re.match(r'\{%', template[pos:])
        if m:
            flush_text()
            tokens.append(('BLOCK_START', '{%'))
            pos += 2
            # Find closing %}
            end = template.find('%}', pos)
            if end == -1:
                end = len(template)
            inner = template[pos:end]
            expr_tokens = _tokenize_expr(inner)
            tokens.extend(expr_tokens)
            tokens.append(('BLOCK_END', '%}'))
            pos = end + 2 if end != -1 else len(template)
            continue

        # Regular character → accumulate in text buffer
        text_buf.append(template[pos])
        pos += 1

    flush_text()
    return tokens
