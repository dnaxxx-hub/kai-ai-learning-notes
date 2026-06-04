"""NFA 模拟器 — 使用 epsilon-closure 算法"""

from nfa import State, NFA
from compiler import compile_regex


def epsilon_closure(states: set) -> set:
    """计算一组状态的 ε-闭包"""
    closure = set(states)
    stack = list(states)

    while stack:
        state = stack.pop()
        for next_state in state.transitions.get(None, []):
            if next_state not in closure:
                closure.add(next_state)
                stack.append(next_state)

    return closure


def move(states: set, char: str) -> set:
    """在给定字符上从一组状态转移"""
    result = set()
    for state in states:
        for next_state in state.transitions.get(char, []):
            result.add(next_state)
    return result


def match(nfa: NFA, text: str) -> bool:
    """检查正则是否完全匹配文本"""
    current = epsilon_closure({nfa.start})

    for ch in text:
        current = epsilon_closure(move(current, ch))
        if not current:
            return False

    return any(s.is_final for s in current)


def _search_at(nfa: NFA, text: str, start_pos: int) -> str or None:
    """从指定位置开始搜索匹配 (最长匹配)"""
    current = epsilon_closure({nfa.start})
    best = None
    best_len = -1

    for j in range(start_pos, len(text)):
        current = epsilon_closure(move(current, text[j]))
        if any(s.is_final for s in current):
            length = j - start_pos + 1
            if length > best_len:
                best = text[start_pos:j + 1]
                best_len = length
        if not current:
            break

    return best


def search(nfa: NFA, text: str) -> str or None:
    """在文本中搜索匹配的子串 (最长匹配)"""
    best = None
    best_len = -1

    for i in range(len(text)):
        current = epsilon_closure({nfa.start})

        for j in range(i, len(text)):
            current = epsilon_closure(move(current, text[j]))
            if any(s.is_final for s in current):
                length = j - i + 1
                if length > best_len:
                    best = text[i:j + 1]
                    best_len = length
            if not current:
                break

    return best


def findall(nfa: NFA, text: str) -> list:
    """查找所有匹配"""
    results = []
    i = 0
    while i < len(text):
        match_str = _search_at(nfa, text, i)
        if match_str:
            results.append(match_str)
            i += len(match_str)
        else:
            i += 1
    return results


# 方便使用的高层 API

class Regex:
    """正则表达式对象"""
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.nfa = compile_regex(pattern)

    def match(self, text: str) -> bool:
        """完整匹配"""
        return match(self.nfa, text)

    def search(self, text: str) -> str or None:
        """搜索子串"""
        return search(self.nfa, text)

    def findall(self, text: str) -> list:
        """查找所有"""
        return findall(self.nfa, text)

    def __repr__(self):
        return f'Regex({self.pattern!r})'
