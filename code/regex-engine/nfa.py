"""NFA (非确定性有限自动机) — Thompson 构造所需的数据结构"""


class State:
    """NFA 状态"""
    def __init__(self, is_final: bool = False):
        self.is_final = is_final
        # 转移表: {char: [states], None: [states]} (None = epsilon)
        self.transitions = {}

    def add_transition(self, char, state):
        """添加转移"""
        if char not in self.transitions:
            self.transitions[char] = []
        self.transitions[char].append(state)

    def __repr__(self):
        final = 'F' if self.is_final else ''
        return f'State({id(self):#x}{final})'


class NFA:
    """NFA 片段 — 包含开始状态和接受状态"""
    def __init__(self, start: State, accept: State):
        self.start = start
        self.accept = accept


# 基本 NFA 构造函数

def literal_nfa(char: str) -> NFA:
    """单个字符的 NFA: start --char--> accept"""
    start = State()
    accept = State(is_final=True)
    start.add_transition(char, accept)
    return NFA(start, accept)


def epsilon_nfa() -> NFA:
    """空转移 NFA: start --ε--> accept"""
    start = State()
    accept = State(is_final=True)
    start.add_transition(None, accept)
    return NFA(start, accept)


def concat_nfa(nfa1: NFA, nfa2: NFA) -> NFA:
    """连接: nfa1 后接 nfa2"""
    nfa1.accept.is_final = False
    nfa1.accept.add_transition(None, nfa2.start)
    return NFA(nfa1.start, nfa2.accept)


def union_nfa(nfa1: NFA, nfa2: NFA) -> NFA:
    """选择: nfa1 | nfa2"""
    start = State()
    accept = State(is_final=True)

    start.add_transition(None, nfa1.start)
    start.add_transition(None, nfa2.start)

    nfa1.accept.is_final = False
    nfa1.accept.add_transition(None, accept)
    nfa2.accept.is_final = False
    nfa2.accept.add_transition(None, accept)

    return NFA(start, accept)


def star_nfa(nfa: NFA) -> NFA:
    """Kleene 星号: nfa*"""
    start = State()
    accept = State(is_final=True)

    start.add_transition(None, nfa.start)
    start.add_transition(None, accept)

    nfa.accept.is_final = False
    nfa.accept.add_transition(None, nfa.start)
    nfa.accept.add_transition(None, accept)

    return NFA(start, accept)


def plus_nfa(nfa: NFA) -> NFA:
    """正闭包: nfa+"""
    # a+ = aa*
    return concat_nfa(nfa, star_nfa(nfa))


def optional_nfa(nfa: NFA) -> NFA:
    """可选: nfa?"""
    # a? = a|ε
    return union_nfa(nfa, epsilon_nfa())
