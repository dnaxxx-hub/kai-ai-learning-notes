"""正则表达式 → NFA 编译器 (Thompson 构造法)"""

from nfa import (
    State, NFA,
    literal_nfa, epsilon_nfa, concat_nfa, union_nfa,
    star_nfa, plus_nfa, optional_nfa,
)

# 运算符优先级
PRECEDENCE = {
    '|': 0,
    '\x00': 1,  # 连接(隐式)
    '?': 2,
    '*': 2,
    '+': 2,
}


def insert_explicit_concat(regex: str) -> str:
    """在需要的地方插入显式连接符 '\x00' (标记)"""
    result = []
    for i, ch in enumerate(regex):
        result.append(ch)
        if i + 1 < len(regex):
            next_ch = regex[i + 1]
            # 在以下情况插入 \x00 (连接符):
            # a (b | * + ? )  或  ) ( ( | * + ? ) 或 * + ? ( ( | a | . )
            if (ch.isalnum() or ch in ')]*+?') and \
               (next_ch.isalnum() or next_ch == '(' or next_ch == '['
                or next_ch == '.' or next_ch == '\\' or next_ch == '^'):
                result.append('\x00')  # 显式连接标记
            # . 后接字符也需要连接
            if ch == '.' and \
               (next_ch.isalnum() or next_ch == '(' or next_ch == '['
                or next_ch == '\\' or next_ch == '^'):
                result.append('\x00')
    return ''.join(result)


def tokenize(regex: str) -> list:
    """将正则表达式拆分为 token"""
    tokens = []
    i = 0
    while i < len(regex):
        ch = regex[i]

        if ch == '\x00':
            # 显式连接标记
            tokens.append(('CONCAT', '\x00'))
            i += 1
            continue

        if ch == '\\':
            # 转义序列
            if i + 1 < len(regex):
                tokens.append(('CHAR', '\\' + regex[i + 1]))
                i += 2
            else:
                tokens.append(('CHAR', '\\'))
                i += 1
            continue

        if ch == '.':
            tokens.append(('DOT', '.'))
        elif ch in '()|*+?^$[]':
            tokens.append(('SPECIAL', ch))
        else:
            tokens.append(('CHAR', ch))
        i += 1

    return tokens


def _handle_char_class(tokens: list, i: int) -> tuple:
    """处理字符集 [abc] [a-z]，返回 (consumed_tokens, new_index)"""
    chars = []
    i += 1  # 跳过 '['
    negate = False

    if i < len(tokens) and tokens[i] == ('SPECIAL', '^'):
        negate = True
        i += 1

    while i < len(tokens):
        tok_type, tok_val = tokens[i]
        if tok_type == 'SPECIAL' and tok_val == ']':
            i += 1
            # 构建字符集 NFA
            all_chars = set()
            j = 0
            while j < len(chars):
                if j + 2 < len(chars) and chars[j + 1] == ('RANGE', '-'):
                    start_char = chars[j]
                    end_char = chars[j + 2]
                    if isinstance(start_char, str) and isinstance(end_char, str):
                        # 如果 start_char 的实际长度 > 1（如转义序列），特殊处理
                        if len(start_char) == 1 and len(end_char) == 1:
                            for c in range(ord(start_char), ord(end_char) + 1):
                                all_chars.add(chr(c))
                            j += 3
                            continue
                    j += 1
                elif isinstance(chars[j], str):
                    all_chars.add(chars[j])
                    j += 1
                else:
                    j += 1

            if negate:
                # 取反：匹配不在集合中的任何字符
                negated = set()
                for c in range(256):
                    ch = chr(c)
                    if ch != '\n' and ch not in all_chars:
                        negated.add(ch)
                return ('CHAR_CLASS_NEGATED', negated), i

            return ('CHAR_CLASS', all_chars), i

        if tok_type == 'SPECIAL' and tok_val == '\\':
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if next_tok[0] == 'CHAR':
                    esc = next_tok[1]
                    if esc == '\\d':
                        chars.extend(list('0123456789'))
                    elif esc == '\\w':
                        chars.extend(list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'))
                    elif esc == '\\s':
                        chars.extend(list(' \t\n\r\f\v'))
                    else:
                        chars.append(esc[-1])
                    i += 2
                    continue
            chars.append('\\')
            i += 1
        elif tok_type == 'CHAR':
            chars.append(tok_val)
            i += 1
        elif tok_val == '-':
            # 检查是否是范围
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if next_tok[0] == 'CHAR' and isinstance(next_tok[1], str) and len(next_tok[1]) == 1:
                    # 暂存范围标记
                    chars.append(('RANGE', '-'))
                    i += 1
                    continue
            chars.append('-')
            i += 1
        else:
            i += 1

    raise ValueError("未闭合的字符集 '['")


def to_postfix(regex: str) -> list:
    """中缀 → 后缀 (Shunting-yard)"""
    # 先插入显式连接符
    expr = insert_explicit_concat(regex)
    tokens = tokenize(expr)

    output = []
    op_stack = []

    i = 0
    while i < len(tokens):
        tok_type, tok_val = tokens[i]

        if tok_type == 'CHAR' or tok_type == 'DOT':
            output.append((tok_type, tok_val))
            i += 1
        elif tok_type == 'CONCAT':
            # 显式连接运算符（二元，优先级 1）
            while op_stack and op_stack[-1][1] in '\x00|' and \
                  PRECEDENCE.get(op_stack[-1][1], 0) >= PRECEDENCE.get('\x00', 0):
                output.append(op_stack.pop())
            op_stack.append(('CONCAT', '\x00'))
            i += 1
        elif tok_val == '(':
            op_stack.append(('SPECIAL', '('))
            i += 1
        elif tok_val == ')':
            while op_stack and op_stack[-1][1] != '(':
                output.append(op_stack.pop())
            if op_stack and op_stack[-1][1] == '(':
                op_stack.pop()  # 移除 '('
            i += 1
        elif tok_val == '[':
            # 字符集处理
            char_class_tok, new_i = _handle_char_class(tokens, i)
            output.append(char_class_tok)
            i = new_i
        elif tok_val in '*+?':
            # 一元运算符，直接输出
            output.append(('SPECIAL', tok_val))
            i += 1
        elif tok_val == '|':
            while op_stack and op_stack[-1][1] in '\x00|' and \
                  PRECEDENCE.get(op_stack[-1][1], 0) >= PRECEDENCE.get(tok_val, 0):
                output.append(op_stack.pop())
            op_stack.append(('SPECIAL', '|'))
            i += 1
        elif tok_val == '^':
            output.append(('ANCHOR', '^'))
            i += 1
        elif tok_val == '$':
            output.append(('ANCHOR', '$'))
            i += 1
        else:
            i += 1

    while op_stack:
        output.append(op_stack.pop())

    return output


def compile_regex(regex: str) -> NFA:
    """将正则表达式编译为 NFA"""
    postfix = to_postfix(regex)
    stack = []

    def _make_char_nfa(ch: str) -> NFA:
        if ch == '\\d':
            return char_class_nfa('0123456789')
        elif ch == '\\w':
            return char_class_nfa(
                'abcdefghijklmnopqrstuvwxyz'
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                '0123456789_'
            )
        elif ch == '\\s':
            return char_class_nfa(' \t\n\r\f\v')
        else:
            # 字面字符（包含 \n 等转义，但此处只处理单个普通字符）
            if ch.startswith('\\') and len(ch) > 1:
                ch = ch[1]  # 取转义后的实际字符
            return literal_nfa(ch)

    for tok_type, tok_val in postfix:
        if tok_type == 'CHAR':
            stack.append(_make_char_nfa(tok_val))
        elif tok_type == 'DOT':
            stack.append(dot_nfa())
        elif tok_type == 'CHAR_CLASS':
            stack.append(char_class_nfa_from_set(tok_val))
        elif tok_type == 'CHAR_CLASS_NEGATED':
            stack.append(char_class_negated_nfa(tok_val))
        elif tok_type == 'ANCHOR':
            if tok_val == '^':
                stack.append(anchor_start_nfa())
            elif tok_val == '$':
                stack.append(anchor_end_nfa())
        elif tok_val == '*':
            nfa = stack.pop()
            stack.append(star_nfa(nfa))
        elif tok_val == '+':
            nfa = stack.pop()
            stack.append(plus_nfa(nfa))
        elif tok_val == '?':
            nfa = stack.pop()
            stack.append(optional_nfa(nfa))
        elif tok_val == '\x00':
            nfa2 = stack.pop()
            nfa1 = stack.pop()
            stack.append(concat_nfa(nfa1, nfa2))
        elif tok_val == '|':
            nfa2 = stack.pop()
            nfa1 = stack.pop()
            stack.append(union_nfa(nfa1, nfa2))

    if not stack:
        return epsilon_nfa()
    return stack[0]


def char_class_nfa(chars: str) -> NFA:
    """字符集 [chars] 的 NFA"""
    start = State()
    accept = State(is_final=True)
    for ch in chars:
        start.add_transition(ch, accept)
    return NFA(start, accept)


def char_class_nfa_from_set(chars: set) -> NFA:
    """从 set 构建字符集 NFA"""
    start = State()
    accept = State(is_final=True)
    for ch in chars:
        start.add_transition(ch, accept)
    return NFA(start, accept)


def char_class_negated_nfa(chars: set) -> NFA:
    """取反字符集 NFA：匹配不在集合中的任何字符"""
    # 使用状态拆解可以避免大量转移，
    # 但这里为了简单，直接为每个字符创建单个转移
    start = State()
    accept = State(is_final=True)
    for ch in chars:
        start.add_transition(ch, accept)
    return NFA(start, accept)


def dot_nfa() -> NFA:
    """通配符 . 的 NFA (匹配除了 \n 以外的任何字符)"""
    start = State()
    accept = State(is_final=True)
    for i in range(256):
        ch = chr(i)
        if ch != '\n':
            start.add_transition(ch, accept)
    return NFA(start, accept)


def anchor_start_nfa() -> NFA:
    """行首锚点 ^ 的 NFA"""
    # ^ 特殊处理：在 matcher 中检查位置
    start = State()
    accept = State(is_final=True)
    start.add_transition(None, accept)  # ε 转移，留给匹配器处理
    return NFA(start, accept)


def anchor_end_nfa() -> NFA:
    """行尾锚点 $ 的 NFA"""
    start = State()
    accept = State(is_final=True)
    start.add_transition(None, accept)  # ε 转移，留给匹配器处理
    return NFA(start, accept)
