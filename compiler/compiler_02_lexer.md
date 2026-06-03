# 编译原理 第2课：从正则引擎到完整词法分析器

> 基于第1课的正则引擎（Thompson NFA → DFA），构建一个完整的词法分析器。
> 学完后：能对任意语言的关键字、标识符、数字、字符串、注释等进行 tokenize。

---

## 关键概念

### 什么是词法分析（Lexical Analysis）

词法分析是编译器的第一阶段——将源代码的字符流转换为 **Token 流**（有意义的词法单元）。

```
源代码: "if (x == 42) return y;"
                          ↓ 词法分析
Token流: [IF, LPAREN, ID(x), EQ_EQ, NUM(42), RPAREN, RETURN, ID(y), SEMI]
```

每个 Token 包含：
- **类型**（关键字、标识符、运算符、字面量等）
- **词素**（lexeme，原始文本片段）
- **位置**（行号、列号，用于错误报告）

### 两个设计流派

| 流派 | 代表 | 优点 | 缺点 |
|------|------|------|------|
| **自动机生成** | Lex/Flex → 自动从正则生成DFA | 正确性保证、易维护 | 黑盒、错误信息差 |
| **手写递归下降** | Clang/GCC/Rust | 精细控制、错误恢复好、性能 | 手动编写、易漏边界 |

实际工业编译器大多**混合使用**：正则引擎处理简单 Token，手写处理复杂情况。

### Token 类型设计原则

定义 Token 类型时，遵循 **最长匹配（Longest Match）**和**优先级规则**：
1. 关键字优先于标识符（`if` 不匹配为 ID，而是 IF）
2. 双字符运算符优先于单字符（`==` 优先于两个 `=`）
3. 注释和空白通常被跳过

---

## 架构设计：完整的词法分析器

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  源代码     │───→│  DFA 引擎    │───→│  Token 流   │
│ (字符流)    │    │ (逐字符匹配)  │    │ (有类型)    │
└─────────────┘    └──────────────┘    └─────────────┘
                          ↑
                    ┌─────────────┐
                    │  正则→NFA→DFA│
                    │ (第1课实现)  │
                    └─────────────┘
```

### 多正则合并为单个 DFA

词法分析需要同时匹配多种 Token 类型。关键技巧：

**合并 NFA**：为每个 Token 模式构造独立的 NFA，然后通过一个 ε 起始状态将它们合并。

```
         ┌── NFA_if ──┐
ε-start──┼── NFA_num ─┼──→ 统一运行
         └── NFA_id ──┘
```

**优先级处理**：当多个模式同时匹配时（如表中的 `if` 和标识符），根据优先级选择。方法：
- 在 DFA 的每个接受状态上记录**优先级最高的 Token 类型**
- 或：在词法分析时按优先级顺序尝试（效率低，不推荐）

---

## Python 实现：完整词法分析器

### 第一步：Token 类型定义

```python
from enum import Enum, auto

class TokenType(Enum):
    # 关键字
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    INT = auto()
    FLOAT = auto()
    VOID = auto()
    TRUE = auto()
    FALSE = auto()

    # 标识符和字面量
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT_LIT = auto()
    STRING = auto()

    # 运算符
    PLUS = auto()          # +
    MINUS = auto()         # -
    STAR = auto()          # *
    SLASH = auto()         # /
    EQ = auto()            # =
    EQ_EQ = auto()         # ==
    NOT_EQ = auto()        # !=
    LT = auto()            # <
    GT = auto()            # >
    LE = auto()            # <=
    GE = auto()            # >=
    AND_AND = auto()       # &&
    OR_OR = auto()         # ||

    # 分隔符
    LPAREN = auto()        # (
    RPAREN = auto()        # )
    LBRACE = auto()        # {
    RBRACE = auto()        # }
    SEMI = auto()          # ;
    COMMA = auto()         # ,

    # 特殊
    COMMENT = auto()       # 注释（跳过）
    WS = auto()            # 空白（跳过）
    UNKNOWN = auto()       # 无法识别的字符
    EOF = auto()           # 文件结束


class Token:
    def __init__(self, type_: TokenType, lexeme: str,
                 line: int, col: int):
        self.type = type_
        self.lexeme = lexeme
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, '{self.lexeme}', {self.line}:{self.col})"
```

### 第二步：复用第1课的正则引擎

从第1课提取核心 NFA/DFA 类：

```python
class NFAState:
    """NFA状态"""
    _id_counter = 0

    def __init__(self, is_accept=False):
        self.id = NFAState._id_counter
        NFAState._id_counter += 1
        self.is_accept = is_accept
        self.transitions = {}    # char → [NFAState]
        self.epsilon = []        # ε → [NFAState]

    def add_transition(self, char, state):
        self.transitions.setdefault(char, []).append(state)

    def add_epsilon(self, state):
        self.epsilon.append(state)


class NFA:
    """NFA = 起始状态 + 接受状态集合"""
    def __init__(self, start, accept):
        self.start = start
        # 接受态可以是多个，用一个set记录
        self.accept_states = set()
        if isinstance(accept, NFAState):
            self.accept_states.add(accept)
        else:
            self.accept_states = set(accept)


def char_nfa(c):
    """字符c的NFA: (State0) --c--> (State1)"""
    s0, s1 = NFAState(), NFAState(is_accept=True)
    s0.add_transition(c, s1)
    return NFA(s0, s1)


def concat_nfa(nfa1, nfa2):
    """连接: 把nfa1的接受态连到nfa2的起始态"""
    for acc in nfa1.accept_states:
        acc.add_epsilon(nfa2.start)
        acc.is_accept = False
    nfa1.accept_states = nfa2.accept_states
    return nfa1


def union_nfa(nfa1, nfa2):
    """选择: 从新起始态ε连到两个NFA的起始态"""
    start = NFAState()
    start.add_epsilon(nfa1.start)
    start.add_epsilon(nfa2.start)
    accept = NFAState(is_accept=True)
    for acc in nfa1.accept_states:
        acc.add_epsilon(accept)
        acc.is_accept = False
    for acc in nfa2.accept_states:
        acc.add_epsilon(accept)
        acc.is_accept = False
    return NFA(start, accept)


def star_nfa(nfa):
    """Kleene星: 从接受态ε回到起始态 + ε跳到新接受态"""
    start = NFAState()
    accept = NFAState(is_accept=True)
    start.add_epsilon(nfa.start)
    start.add_epsilon(accept)
    for acc in nfa.accept_states:
        acc.add_epsilon(nfa.start)
        acc.add_epsilon(accept)
        acc.is_accept = False
    return NFA(start, accept)
```

### 第三步：NFA → DFA（子集构造法）

```python
def epsilon_closure(states, visited=None):
    """计算ε闭包：从states出发能通过ε边到达的所有状态"""
    if visited is None:
        visited = set()
    result = set(states)
    stack = list(states)
    while stack:
        s = stack.pop()
        for eps_s in s.epsilon:
            if eps_s not in visited:
                visited.add(eps_s)
                result.add(eps_s)
                stack.append(eps_s)
    return frozenset(result)


def move(states, char):
    """从states出发走char能到达的状态"""
    result = set()
    for s in states:
        if char in s.transitions:
            result.update(s.transitions[char])
    return result


def nfa_to_dfa(nfa, token_type=None, prioritize=True):
    """
    子集构造法：NFA → DFA
    增强：每个DFA状态记录对应的 Token 类型和优先级
    """
    start_closure = epsilon_closure({nfa.start})
    dfa_states = {start_closure: len(dfa_states) if 'dfa_states' in dir() else 0}
    # ↑ 上面这行纯属演示，实际用 dict 管理

    # 正确实现
    dfa_states = {}          # frozenset(NFA states) → DFA state id
    dfa_trans = {}           # (dfa_id, char) → next_dfa_id
    dfa_accept = {}          # dfa_id → token_type (如果有接受态)
    dfa_queue = []           # BFS队列

    closure = epsilon_closure({nfa.start})
    dfa_states[closure] = 0
    dfa_queue.append(closure)

    # 检查起始闭包是否已经是接受态
    for s in closure:
        if s in nfa.accept_states:
            dfa_accept[0] = token_type

    while dfa_queue:
        current_set = dfa_queue.pop(0)
        current_id = dfa_states[current_set]

        # 收集所有可能的输入字符
        chars = set()
        for s in current_set:
            chars.update(s.transitions.keys())

        for c in chars:
            next_states = move(current_set, c)
            if not next_states:
                continue
            closure = epsilon_closure(next_states)
            if closure not in dfa_states:
                new_id = len(dfa_states)
                dfa_states[closure] = new_id
                dfa_queue.append(closure)
                # 检查接受态
                for s in closure:
                    if s in nfa.accept_states:
                        dfa_accept[new_id] = token_type
                        break
            dfa_trans[(current_id, c)] = dfa_states[closure]

    return dfa_states, dfa_trans, dfa_accept
```

### 第四步：合并多个 Token 模式为统一 DFA

```python
def build_combined_nfa(patterns):
    """
    将多个 Token 模式合并为一个 NFA
    patterns: [(TokenType, regex_string_or_nfa_func), ...]

    返回一个统一的 NFA，每个接受态标记了所属 Token 类型
    """
    start = NFAState()  # 统一的起始状态

    for token_type, nfa in patterns:
        # 从统一起始态 ε 连接到每个模式的 NFA
        start.add_epsilon(nfa.start)

    return NFA(start, [])  # 接受态分散在各子NFA中


def build_lexer_dfa(patterns):
    """
    为词法分析器构建统一的 DFA。
    patterns: [(TokenType, NFA), ...] 按优先级排序（高优先级在前）

    返回：
    - states: set of frozensets
    - trans: (state_id, char) → state_id
    - accept: state_id → (token_type, priority)
    """
    # Step 1: 合并 NFA（注意优先级顺序）
    start = NFAState()
    for prio, (token_type, nfa) in enumerate(patterns):
        start.add_epsilon(nfa.start)
        # 在子NFA的接受态上标记优先级
        for acc in nfa.accept_states:
            acc._token_type = token_type
            acc._priority = prio

    # Step 2: 子集构造
    dfa_states = {}      # frozenset → id
    dfa_trans = {}       # (id, char) → id
    dfa_accept = {}      # id → (token_type, priority)
    dfa_queue = []

    closure = epsilon_closure({start})
    dfa_states[closure] = 0
    dfa_queue.append(closure)

    while dfa_queue:
        current_set = dfa_queue.pop(0)
        current_id = dfa_states[current_set]

        # 检查接受态（选择优先级最高的）
        best_type, best_prio = None, float('inf')
        for s in current_set:
            if hasattr(s, '_token_type'):
                if s._priority < best_prio:
                    best_type, best_prio = s._token_type, s._priority
                    dfa_accept[current_id] = best_type  # 可能被覆盖

        chars = set()
        for s in current_set:
            chars.update(s.transitions.keys())

        for c in chars:
            next_states = move(current_set, c)
            if not next_states:
                continue
            closure = epsilon_closure(next_states)
            if closure not in dfa_states:
                new_id = len(dfa_states)
                dfa_states[closure] = new_id
                dfa_queue.append(closure)
            dfa_trans[(current_id, c)] = dfa_states[closure]

    return dfa_states, dfa_trans, dfa_accept
```

### 第五步：DFA 驱动的词法分析器（核心！）

这里是整个词法分析器的**引擎**——用 DFA 进行最长匹配：

```python
class Lexer:
    """
    DFA驱动的词法分析器。
    核心算法：在输入字符上运行 DFA，记录最后到达接受态的位置，
    当死路时回退到最后的接受位置。
    """

    def __init__(self, dfa_states, dfa_trans, dfa_accept,
                 skip_types=None):
        """
        dfa_states: frozenset → id
        dfa_trans: (state_id, char) → state_id
        dfa_accept: state_id → TokenType（接受态才能产出Token）
        skip_types: 需要跳过的 TokenType 集合（空白、注释等）
        """
        self.dfa_trans = dfa_trans
        self.dfa_accept = dfa_accept
        self.skip_types = skip_types or {TokenType.WS, TokenType.COMMENT}
        # 预先构建字符索引（字符→所有转换），加速查找
        self.char_map = {}
        for (sid, c), nsid in dfa_trans.items():
            if c not in self.char_map:
                self.char_map[c] = {}
            self.char_map[c][sid] = nsid

    def tokenize(self, source: str):
        """将源代码字符串转换为 Token 列表"""
        tokens = []
        pos = 0
        line, col = 1, 1
        length = len(source)

        while pos < length:
            # 跳过空白（简单实现，实际已在 DFA 中处理）
            # 统一走 DFA 匹配

            # ---- 最长匹配算法 ----
            state = 0  # DFA 起始状态
            last_accept_pos = -1
            last_accept_state = -1
            start_pos = pos

            while pos < length:
                c = source[pos]
                if state in self.char_map and c in self.char_map[state]:
                    state = self.char_map[state][c]
                    pos += 1
                    # 如果能推进，记录最后接受位置
                    if state in self.dfa_accept:
                        last_accept_pos = pos
                        last_accept_state = state
                else:
                    break  # 死路，退出

            # 如果没有找到接受态，尝试单字符 UNKNOWN
            if last_accept_pos == -1:
                if pos == start_pos:  # 死路，连一步都走不了
                    tok_type = TokenType.UNKNOWN
                    lexeme = source[start_pos]
                    pos = start_pos + 1
                else:
                    # 多走了一步还没到接受态
                    tok_type = TokenType.UNKNOWN
                    lexeme = source[start_pos:pos]
            else:
                # 回退到最后接受位置
                pos = last_accept_pos
                tok_type = self.dfa_accept[last_accept_state]
                lexeme = source[start_pos:pos]

            # 更新行列号（分析是否换行等，简化处理）
            newline_count = lexeme.count('\n')
            if newline_count > 0:
                line += newline_count
                col = len(lexeme) - lexeme.rfind('\n')
            else:
                col += len(lexeme)

            # 跳过空白和注释
            if tok_type not in self.skip_types:
                tokens.append(Token(tok_type, lexeme, line, col))

        # 添加 EOF
        tokens.append(Token(TokenType.EOF, '', line, col))
        return tokens
```

### 第六步：构建语言 Token 模式

用第1课的正则引擎构造具体语言的 Token：

```python
def build_minic_patterns():
    """
    为 MiniC 语言构造 Token 模式
    优先级从高到低：
    1. 关键字（在标识符之前）
    2. 多字符运算符
    3. 单字符运算符/分隔符
    4. 字面量
    5. 标识符
    """
    patterns = []

    # --- 关键字（用精确字符串匹配） ---
    keywords = {
        'if': TokenType.IF, 'else': TokenType.ELSE,
        'while': TokenType.WHILE, 'for': TokenType.FOR,
        'return': TokenType.RETURN,
        'int': TokenType.INT, 'float': TokenType.FLOAT,
        'void': TokenType.VOID,
        'true': TokenType.TRUE, 'false': TokenType.FALSE,
    }
    # 为每个关键字构造精确字符串NFA
    for kw, tt in keywords.items():
        # 构造字符串NFA: 逐个字符连接
        nfa = None
        for c in kw:
            cnfa = char_nfa(c)
            if nfa is None:
                nfa = cnfa
            else:
                nfa = concat_nfa(nfa, cnfa)
        patterns.append((tt, nfa))

    # --- 多字符运算符 ---
    multi_ops = {
        '==': TokenType.EQ_EQ, '!=': TokenType.NOT_EQ,
        '<=': TokenType.LE, '>=': TokenType.GE,
        '&&': TokenType.AND_AND, '||': TokenType.OR_OR,
    }
    for op, tt in multi_ops.items():
        nfa = None
        for c in op:
            cnfa = char_nfa(c)
            if nfa is None:
                nfa = cnfa
            else:
                nfa = concat_nfa(nfa, cnfa)
        patterns.append((tt, nfa))

    # --- 标识符: [a-zA-Z_][a-zA-Z0-9_]* ---
    # 注意：关键字必须在标识符之前，因为标识符也匹配 "if"
    id_nfa = _build_identifier_nfa()
    patterns.append((TokenType.IDENTIFIER, id_nfa))

    # --- 整数: [0-9]+ ---
    int_nfa = _build_digit_nfa()
    patterns.append((TokenType.INTEGER, int_nfa))

    # --- 浮点数: [0-9]+"."[0-9]* ---
    float_nfa = _build_float_nfa()
    patterns.append((TokenType.FLOAT_LIT, float_nfa))

    # --- 单字符运算符/分隔符 ---
    single_chars = {
        '+': TokenType.PLUS, '-': TokenType.MINUS,
        '*': TokenType.STAR, '/': TokenType.SLASH,
        '=': TokenType.EQ, '<': TokenType.LT, '>': TokenType.GT,
        '(': TokenType.LPAREN, ')': TokenType.RPAREN,
        '{': TokenType.LBRACE, '}': TokenType.RBRACE,
        ';': TokenType.SEMI, ',': TokenType.COMMA,
    }
    for ch, tt in single_chars.items():
        patterns.append((tt, char_nfa(ch)))

    # --- 空白: [ \t\n\r]+ ---
    ws_nfa = _build_whitespace_nfa()
    patterns.append((TokenType.WS, ws_nfa))

    return patterns


def _build_identifier_nfa():
    """[a-zA-Z_][a-zA-Z0-9_]*"""
    # 第一个字符
    first = NFAState()
    accept = NFAState(is_accept=True)
    for c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_':
        first.add_transition(c, accept)

    # 后续字符（重复星）
    rest = NFAState(is_accept=True)
    for c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_':
        accept.add_transition(c, rest)
        rest.add_transition(c, rest)  # 自循环

    return NFA(first, {accept, rest})


def _build_digit_nfa():
    """[0-9]+"""
    s0 = NFAState()
    s1 = NFAState(is_accept=True)
    for c in '0123456789':
        s0.add_transition(c, s1)
        s1.add_transition(c, s1)  # 自循环
    return NFA(s0, s1)


def _build_float_nfa():
    """[0-9]+"."[0-9]*"""
    # 整数部分
    int_part = NFAState()
    dot_state = NFAState()
    frac_state = NFAState(is_accept=True)
    for c in '0123456789':
        int_part.add_transition(c, dot_state)
        dot_state.add_transition(c, dot_state)  # 多位数

    # 小数点
    dot_state.add_transition('.', frac_state)
    for c in '0123456789':
        frac_state.add_transition(c, frac_state)
        frac_state.add_transition(c, NFAState(is_accept=True))

    return NFA(int_part, frac_state)


def _build_whitespace_nfa():
    """[ \t\n\r]+"""
    s0 = NFAState()
    s1 = NFAState(is_accept=True)
    for c in ' \t\n\r':
        s0.add_transition(c, s1)
        s1.add_transition(c, s1)
    return NFA(s0, s1)
```

### 第七步：完整使用示例

```python
def main():
    # Step 1: 构建语言模式
    patterns = build_minic_patterns()

    # Step 2: 构建合并 DFA
    print("Building lexer DFA...")
    states, trans, accept = build_lexer_dfa(patterns)
    print(f"DFA: {len(states)} states, {len(trans)} transitions")

    # Step 3: 创建词法分析器
    lexer = Lexer(states, trans, accept)

    # Step 4: 测试
    source_code = """
    int main() {
        float x = 3.14;
        if (x == 3.14 && true) {
            return 42;
        }
    }
    """

    print("\n=== Source ===")
    print(source_code)
    print("\n=== Tokens ===")
    tokens = lexer.tokenize(source_code)
    for tok in tokens:
        print(tok)


if __name__ == '__main__':
    main()
```

---

## 完整运行流程示意

以输入 `if(x==42)` 为例：

```
源字符: i  f  (  x  =  =  4  2  )

步骤1: 走 DFA 匹配 'if'
  pos=0: state=0, 读 'i' → state=X (标识符路径)
  pos=1: 读 'f' → state=Y (接受态: TokenType.IF)
  pos=2: 读 '(' → 死路，回退到 pos=2
  输出: Token(IF, 'if', 1:1)

步骤2: 走 DFA 匹配 '('
  pos=2: state=0, 读 '(' → state=Z (接受态: LPAREN)
  输出: Token(LPAREN, '(', 1:3)

步骤3: 走 DFA 匹配 'x'
  pos=3: state=0, 读 'x' → ID路径
  pos=4: 读 '=' → 死路，回退
  输出: Token(IDENTIFIER, 'x', 1:4)

...

最终 Token 流:
  IF, LPAREN, ID(x), EQ_EQ, INTEGER(42), RPAREN, EOF
```

---

## 手写 Lexer 替代方案（纯手写，无 DFA）

虽然上面用 DFA 展示了自动机原理，但现实中**大多数编译器用手写词法分析器**。
以下是等价的纯手写版本——更简洁、性能更好、错误恢复更可控：

```python
class HandWrittenLexer:
    """
    手写词法分析器：逐个字符分析，switch-case 风格
    不存在状态爆炸，线性性能，错误信息精确
    """

    # 关键字集合
    keywords = {
        'if', 'else', 'while', 'for', 'return',
        'int', 'float', 'void', 'true', 'false',
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)

    def peek(self, offset=0):
        """偷看下一个字符"""
        idx = self.pos + offset
        return self.source[idx] if idx < self.length else '\0'

    def advance(self):
        """消费一个字符，更新行列"""
        c = self.source[self.pos]
        self.pos += 1
        if c == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c

    def skip_whitespace(self):
        """跳过空白"""
        while self.pos < self.length and self.peek() in ' \t\n\r':
            self.advance()

    def read_identifier(self):
        """读取标识符或关键字"""
        start = self.pos
        while self.pos < self.length and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        word = self.source[start:self.pos]
        # 关键字 vs 标识符
        if word in self.keywords:
            return Token(TokenType[word.upper()], word, self.line, self.col - len(word))
        return Token(TokenType.IDENTIFIER, word, self.line, self.col - len(word))

    def read_number(self):
        """读取数字（整数或浮点数）"""
        start = self.pos
        is_float = False
        while self.pos < self.length and self.peek().isdigit():
            self.advance()
        if self.peek() == '.' and self.pos + 1 < self.length and self.source[self.pos + 1].isdigit():
            is_float = True
            self.advance()  # 吃 '.'
            while self.pos < self.length and self.peek().isdigit():
                self.advance()
        lexeme = self.source[start:self.pos]
        tok_type = TokenType.FLOAT_LIT if is_float else TokenType.INTEGER
        return Token(tok_type, lexeme, self.line, self.col - len(lexeme))

    def tokenize(self):
        """主循环"""
        tokens = []
        while self.pos < self.length:
            self.skip_whitespace()
            if self.pos >= self.length:
                break

            c = self.peek()
            line, col = self.line, self.col

            # 标识符
            if c.isalpha() or c == '_':
                tokens.append(self.read_identifier())
                continue

            # 数字
            if c.isdigit():
                tokens.append(self.read_number())
                continue

            # 多字符运算符
            two_char = self.source[self.pos:self.pos + 2]
            op_map = {
                '==': TokenType.EQ_EQ, '!=': TokenType.NOT_EQ,
                '<=': TokenType.LE, '>=': TokenType.GE,
                '&&': TokenType.AND_AND, '||': TokenType.OR_OR,
            }
            if two_char in op_map:
                self.advance()
                self.advance()
                tokens.append(Token(op_map[two_char], two_char, line, col))
                continue

            # 单字符
            single_map = {
                '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.STAR, '/': TokenType.SLASH,
                '=': TokenType.EQ, '<': TokenType.LT, '>': TokenType.GT,
                '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '{': TokenType.LBRACE, '}': TokenType.RBRACE,
                ';': TokenType.SEMI, ',': TokenType.COMMA,
            }
            if c in single_map:
                self.advance()
                tokens.append(Token(single_map[c], c, line, col))
                continue

            # 无法识别
            self.advance()
            tokens.append(Token(TokenType.UNKNOWN, c, line, col))

        tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return tokens
```

---

## 工程实战要点

### 1. 错误恢复策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| Panic Mode | 遇到错误Token，跳过到行尾或分号 | 简单语言、玩具编译器 |
| 字符级别恢复 | 跳过非法字符后继续 | 真实工程（Clang/GCC用） |
| 上下文恢复 | 根据预期Token类型尝试补救 | 高级、IDE场景 |

**推荐**：先用 Panic Mode，成熟后加入字符级恢复。

### 2. 性能优化

- **按字符查找**：预构建 `char → [(state, next_state)]` 索引（已在 Lexer 中实现）
- **提前建表**：对大语言常见字符（字母、数字）建立快速跳转表
- **批量处理**：一次性跳过连续的空白/注释
- **无锁缓冲**：使用 `bytearray` 或 `memoryview` 避免字符串拷贝

### 3. Token 位置追踪的精度

```python
# 精简版位置追踪：只记行号
# 开发用版：精确到列号
# 生产用版：还要记录token长度（用于高亮和自动完成）
```

---

## 与第1课的关系总结

| 第1课（正则引擎） | 第2课（词法分析器） |
|---|---|
| 单个正则 → NFA → DFA | 多正则合并 → 统一 DFA |
| 接受/不接受二元结果 | Token 类型多分类 |
| 匹配一个模式 | 最长匹配 + 优先级 |
| 纯匹配引擎 | 字符流 → Token 流驱动 |
| 没有位置信息 | 记录行列号 |

## 下一步

完成词法分析后，下一步是**语法分析（Parsing）**：
- 我们需要一个 CFG（上下文无关文法）来描述语言结构
- 从 Token 流构建 AST（抽象语法树）
- 手写递归下降 Parser 或 自动构造 LL/LR Parser

这正是第3课的内容。
