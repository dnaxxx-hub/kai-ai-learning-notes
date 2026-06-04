from dataclasses import dataclass
from typing import List


@dataclass
class Token:
    type: str  # NUMBER, STRING, IDENTIFIER, KEYWORD, OPERATOR, PUNCTUATION, EOF
    value: any
    line: int
    column: int


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    KEYWORDS = {
        'let', 'if', 'else', 'while', 'fn', 'return',
        'true', 'false', 'nil', 'and', 'or', 'not', 'print'
    }

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            # 跳过空白
            if self.source[self.pos] in ' \t\r':
                self._advance()
                continue

            # 换行
            if self.source[self.pos] == '\n':
                self._newline()
                continue

            # 注释 //
            if self.pos + 1 < len(self.source) and self.source[self.pos:self.pos + 2] == '//':
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self._advance()
                continue

            c = self.source[self.pos]

            # 数字
            if c.isdigit() or (c == '.' and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit()):
                self._read_number()
                continue

            # 字符串
            if c == '"':
                self._read_string()
                continue

            # 标识符 / 关键字
            if c.isalpha() or c == '_':
                self._read_identifier()
                continue

            # 运算符和多字符运算符
            if c in '+-*/%=!<>':
                self._read_operator()
                continue

            # 标点
            if c in '(){}[],;':
                self.tokens.append(Token('PUNCTUATION', c, self.line, self.column))
                self._advance()
                continue

            raise SyntaxError(f"Unexpected character '{c}' at line {self.line}, column {self.column}")

        self.tokens.append(Token('EOF', None, self.line, self.column))
        return self.tokens

    def _advance(self):
        self.pos += 1
        self.column += 1

    def _newline(self):
        self.pos += 1
        self.line += 1
        self.column = 1

    def _read_number(self):
        start = self.pos
        is_float = False
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            if self.source[self.pos] == '.':
                if is_float:
                    break  # 第二个小数点
                is_float = True
            self._advance()

        num_str = self.source[start:self.pos]
        value = float(num_str) if is_float else int(num_str)
        self.tokens.append(Token('NUMBER', value, self.line, self.column - len(num_str)))

    def _read_string(self):
        self._advance()  # 跳过开头 "
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] != '"':
            if self.source[self.pos] == '\n':
                raise SyntaxError(f"Unterminated string at line {self.line}")
            self._advance()

        if self.pos >= len(self.source):
            raise SyntaxError(f"Unterminated string starting at line {self.line}")

        value = self.source[start:self.pos]
        self._advance()  # 跳过结尾 "
        self.tokens.append(Token('STRING', value, self.line, self.column - len(value) - 2))

    def _read_identifier(self):
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            self._advance()

        name = self.source[start:self.pos]
        if name in self.KEYWORDS:
            token_type = 'KEYWORD'
        else:
            token_type = 'IDENTIFIER'
        self.tokens.append(Token(token_type, name, self.line, self.column - len(name)))

    def _read_operator(self):
        start = self.pos
        c = self.source[self.pos]
        self._advance()

        # 双字符运算符
        if self.pos < len(self.source):
            next_c = self.source[self.pos]
            two_char = c + next_c
            if two_char in ('==', '!=', '<=', '>='):
                self._advance()
                self.tokens.append(Token('OPERATOR', two_char, self.line, self.column - 2))
                return

        self.tokens.append(Token('OPERATOR', c, self.line, self.column - 1))
