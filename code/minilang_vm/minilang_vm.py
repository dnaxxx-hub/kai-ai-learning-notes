# minilang_vm.py — MiniLang Programming Language Virtual Machine
# Zero external dependencies. Pure Python 3.10+
# 
# Features:
# - Lexer (tokenizer) with full position tracking
# - Recursive-descent Parser with expression/statement separation
# - 30+ AST node types
# - Environment-based runtime with closure support
# - Stack-based VM with bytecode compilation option
# - Built-in runtime library
# - Comprehensive test suite
import sys
import abc
import math
import random
import inspect
import json
import time as _time
import urllib.request
import urllib.error
from typing import Any, List, Optional, Tuple, Union, Dict, Callable

# ====== Token Types ======
class TokenType:
    # Literals
    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"
    # Keywords
    VAR = "VAR"
    FUNC = "FUNC"
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    RETURN = "RETURN"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    PRINT = "PRINT"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NIL = "NIL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    IN = "IN"
    # Delimiters
    LPAREN = "LPAREN"       # (
    RPAREN = "RPAREN"       # )
    LBRACE = "LBRACE"       # {
    RBRACE = "RBRACE"       # }
    LBRACKET = "LBRACKET"   # [
    RBRACKET = "RBRACKET"   # ]
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    # Operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"
    EQUAL = "EQUAL"
    EQUAL_EQUAL = "EQUAL_EQUAL"
    BANG_EQUAL = "BANG_EQUAL"
    GREATER = "GREATER"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS = "LESS"
    LESS_EQUAL = "LESS_EQUAL"
    EOF = "EOF"
    ILLEGAL = "ILLEGAL"

# ====== Token ======
class Token:
    def __init__(self, token_type: str, literal: Any, line: int = 1, column: int = 0):
        self.type = token_type
        self.literal = literal
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type}, {self.literal!r}, L{self.line}:{self.column})"

# ====== Lexer ======
class Lexer:
    """Tokenize MiniLang source code into tokens."""

    _keywords = {
        "var": TokenType.VAR,
        "func": TokenType.FUNC,
        "if": TokenType.IF,
        "else": TokenType.ELSE,
        "while": TokenType.WHILE,
        "for": TokenType.FOR,
        "return": TokenType.RETURN,
        "break": TokenType.BREAK,
        "continue": TokenType.CONTINUE,
        "print": TokenType.PRINT,
        "true": TokenType.TRUE,
        "false": TokenType.FALSE,
        "nil": TokenType.NIL,
        "and": TokenType.AND,
        "or": TokenType.OR,
        "not": TokenType.NOT,
        "in": TokenType.IN,
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 0
        self.tokens: List[Token] = []
        self._errors: List[str] = []
        self._tokenize()

    def _error(self, msg: str):
        self._errors.append(f"[Lexer Error] Line {self.line}: {msg}")

    @property
    def errors(self):
        return self._errors

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 0
        else:
            self.column += 1
        return ch

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return "\0"
        return self.source[idx]

    def _skip_whitespace(self):
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self._advance()
            elif ch == "/" and self._peek(1) == "*":
                self._advance()  # /
                self._advance()  # *
                depth = 1
                while self.pos < len(self.source) and depth > 0:
                    ch = self._advance()
                    if ch == "/" and self._peek() == "*":
                        self._advance()
                        depth += 1
                    elif ch == "*" and self._peek() == "/":
                        self._advance()
                        depth -= 1
            else:
                break

    def _read_number(self) -> Token:
        start_col = self.column
        num_str = ""
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
            num_str += self._advance()
        if num_str.count(".") > 1:
            self._error(f"Invalid number literal: {num_str}")
        if "." in num_str:
            return Token(TokenType.NUMBER, float(num_str), self.line, start_col)
        return Token(TokenType.NUMBER, int(num_str), self.line, start_col)

    def _read_identifier(self) -> Token:
        start_col = self.column
        ident = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            ident += self._advance()
        kw_type = self._keywords.get(ident)
        if kw_type:
            return Token(kw_type, ident, self.line, start_col)
        return Token(TokenType.IDENTIFIER, ident, self.line, start_col)

    def _read_string(self, quote: str) -> Token:
        start_col = self.column
        self._advance()  # consume opening quote
        s = ""
        while self.pos < len(self.source):
            ch = self._advance()
            if ch == "\\":
                next_ch = self._advance() if self.pos < len(self.source) else "\0"
                esc_map = {"n": "\n", "t": "\t", "r": "\r", "\\\\": "\\", '"': '"', "'": "'"}
                s += esc_map.get(next_ch, next_ch)
            elif ch == quote:
                return Token(TokenType.STRING, s, self.line, start_col)
            else:
                s += ch
        self._error("Unterminated string literal")
        return Token(TokenType.STRING, s, self.line, start_col)

    def _tokenize(self):
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]
            col = self.column

            if ch == "(":
                self.tokens.append(Token(TokenType.LPAREN, "(", self.line, col))
                self._advance()
            elif ch == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")", self.line, col))
                self._advance()
            elif ch == "{":
                self.tokens.append(Token(TokenType.LBRACE, "{", self.line, col))
                self._advance()
            elif ch == "}":
                self.tokens.append(Token(TokenType.RBRACE, "}", self.line, col))
                self._advance()
            elif ch == "[":
                self.tokens.append(Token(TokenType.LBRACKET, "[", self.line, col))
                self._advance()
            elif ch == "]":
                self.tokens.append(Token(TokenType.RBRACKET, "]", self.line, col))
                self._advance()
            elif ch == ",":
                self.tokens.append(Token(TokenType.COMMA, ",", self.line, col))
                self._advance()
            elif ch == ";":
                self.tokens.append(Token(TokenType.SEMICOLON, ";", self.line, col))
                self._advance()
            elif ch == "+":
                self.tokens.append(Token(TokenType.PLUS, "+", self.line, col))
                self._advance()
            elif ch == "-":
                self.tokens.append(Token(TokenType.MINUS, "-", self.line, col))
                self._advance()
            elif ch == "*":
                self.tokens.append(Token(TokenType.STAR, "*", self.line, col))
                self._advance()
            elif ch == "/":
                if self._peek(1) in ("/", "*"):
                    continue
                self.tokens.append(Token(TokenType.SLASH, "/", self.line, col))
                self._advance()
            elif ch == "%":
                self.tokens.append(Token(TokenType.PERCENT, "%", self.line, col))
                self._advance()
            elif ch == "=":
                if self._peek(1) == "=":
                    self._advance(); self._advance()
                    self.tokens.append(Token(TokenType.EQUAL_EQUAL, "==", self.line, col))
                else:
                    self._advance()
                    self.tokens.append(Token(TokenType.EQUAL, "=", self.line, col))
            elif ch == "!":
                if self._peek(1) == "=":
                    self._advance(); self._advance()
                    self.tokens.append(Token(TokenType.BANG_EQUAL, "!=", self.line, col))
                else:
                    self._error("Expected '!='")
                    self._advance()
            elif ch == ">":
                if self._peek(1) == "=":
                    self._advance(); self._advance()
                    self.tokens.append(Token(TokenType.GREATER_EQUAL, ">=", self.line, col))
                else:
                    self._advance()
                    self.tokens.append(Token(TokenType.GREATER, ">", self.line, col))
            elif ch == "<":
                if self._peek(1) == "=":
                    self._advance(); self._advance()
                    self.tokens.append(Token(TokenType.LESS_EQUAL, "<=", self.line, col))
                else:
                    self._advance()
                    self.tokens.append(Token(TokenType.LESS, "<", self.line, col))
            elif ch in ('"', "'"):
                self.tokens.append(self._read_string(ch))
            elif ch.isdigit():
                self.tokens.append(self._read_number())
            elif ch.isalpha() or ch == "_":
                self.tokens.append(self._read_identifier())
            else:
                self._error(f"Unexpected character: {ch!r}")
                self._advance()

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))

# ====== AST Nodes ======
class ASTNode(abc.ABC):
    pass

class Number(ASTNode):
    def __init__(self, value: Union[int, float], line: int = 0):
        self.value = value
        self.line = line

class Str(ASTNode):
    def __init__(self, value: str, line: int = 0):
        self.value = value
        self.line = line

class Bool(ASTNode):
    def __init__(self, value: bool, line: int = 0):
        self.value = value
        self.line = line

class Nil(ASTNode):
    def __init__(self, line: int = 0):
        self.line = line

class ListLiteral(ASTNode):
    def __init__(self, elements: List[ASTNode], line: int = 0):
        self.elements = elements
        self.line = line

class Identifier(ASTNode):
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line

class Unary(ASTNode):
    def __init__(self, op: str, right: ASTNode, line: int = 0):
        self.op = op
        self.right = right
        self.line = line

class Binary(ASTNode):
    def __init__(self, left: ASTNode, op: str, right: ASTNode, line: int = 0):
        self.left = left
        self.op = op
        self.right = right
        self.line = line

class Logical(ASTNode):
    def __init__(self, left: ASTNode, op: str, right: ASTNode, line: int = 0):
        self.left = left
        self.op = op
        self.right = right
        self.line = line

class Grouping(ASTNode):
    def __init__(self, expr: ASTNode, line: int = 0):
        self.expr = expr
        self.line = line

class Call(ASTNode):
    def __init__(self, callee: ASTNode, arguments: List[ASTNode], line: int = 0):
        self.callee = callee
        self.arguments = arguments
        self.line = line

class Assign(ASTNode):
    def __init__(self, name: str, value: ASTNode, line: int = 0):
        self.name = name
        self.value = value
        self.line = line

class Subscript(ASTNode):
    def __init__(self, obj: ASTNode, index: ASTNode, line: int = 0):
        self.obj = obj
        self.index = index
        self.line = line

class Stmt(ASTNode):
    pass

class VarDecl(Stmt):
    def __init__(self, name: str, initializer: Optional[ASTNode], line: int = 0):
        self.name = name
        self.initializer = initializer
        self.line = line

class FuncDecl(Stmt):
    def __init__(self, name: str, params: List[str], body: 'Block', line: int = 0):
        self.name = name
        self.params = params
        self.body = body
        self.line = line

class Block(Stmt):
    def __init__(self, statements: List[Stmt], line: int = 0):
        self.statements = statements
        self.line = line

class If(Stmt):
    def __init__(self, condition: ASTNode, then_branch: Stmt, else_branch: Optional[Stmt], line: int = 0):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
        self.line = line

class While(Stmt):
    def __init__(self, condition: ASTNode, body: Stmt, line: int = 0):
        self.condition = condition
        self.body = body
        self.line = line

class For(Stmt):
    def __init__(self, initializer: Optional[Stmt], condition: Optional[ASTNode],
                 increment: Optional[ASTNode], body: Stmt, line: int = 0):
        self.initializer = initializer
        self.condition = condition
        self.increment = increment
        self.body = body
        self.line = line

class Return(Stmt):
    def __init__(self, value: Optional[ASTNode], line: int = 0):
        self.value = value
        self.line = line

class Break(Stmt):
    def __init__(self, line: int = 0):
        self.line = line

class Continue(Stmt):
    def __init__(self, line: int = 0):
        self.line = line

class Print(Stmt):
    def __init__(self, expr: ASTNode, line: int = 0):
        self.expr = expr
        self.line = line

class ExprStmt(Stmt):
    def __init__(self, expr: ASTNode, line: int = 0):
        self.expr = expr
        self.line = line


# ====== Parser Exception ======
class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"[Parse Error] Line {line}: {message}")


# ====== Parser ======
class Parser:
    """Recursive-descent parser using precedence climbing for expressions."""

    PRECEDENCE = {
        TokenType.OR: 1,
        TokenType.AND: 2,
        TokenType.EQUAL_EQUAL: 3,
        TokenType.BANG_EQUAL: 3,
        TokenType.GREATER: 4,
        TokenType.GREATER_EQUAL: 4,
        TokenType.LESS: 4,
        TokenType.LESS_EQUAL: 4,
        TokenType.PLUS: 5,
        TokenType.MINUS: 5,
        TokenType.STAR: 6,
        TokenType.SLASH: 6,
        TokenType.PERCENT: 6,
        TokenType.LBRACKET: 7,
        TokenType.LPAREN: 7,
    }

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self._errors: List[str] = []

    @property
    def errors(self):
        return self._errors

    def _peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "")

    def _previous(self) -> Token:
        if self.pos > 0:
            return self.tokens[self.pos - 1]
        return Token(TokenType.EOF, "")

    def _advance(self) -> Token:
        tok = self._peek()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def _check(self, *types: str) -> bool:
        return self._peek().type in types

    def _match(self, *types: str) -> Optional[Token]:
        if self._check(*types):
            return self._advance()
        return None

    def _consume(self, token_type: str, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        tok = self._peek()
        raise ParseError(message, tok.line)

    def _sync(self):
        while not self._check(TokenType.EOF):
            if self._previous().type == TokenType.SEMICOLON:
                return
            if self._check(TokenType.VAR, TokenType.FUNC, TokenType.IF,
                           TokenType.WHILE, TokenType.FOR, TokenType.RETURN,
                           TokenType.PRINT, TokenType.BREAK, TokenType.CONTINUE,
                           TokenType.LBRACE, TokenType.RBRACE):
                return
            self._advance()

    def parse(self) -> List[Stmt]:
        statements = []
        while not self._check(TokenType.EOF):
            try:
                stmt = self._statement()
                if stmt is not None:
                    statements.append(stmt)
            except ParseError as e:
                self._errors.append(str(e))
                self._sync()
        return statements

    def _statement(self) -> Optional[Stmt]:
        if self._check(TokenType.VAR):
            return self._var_declaration()
        if self._check(TokenType.FUNC):
            return self._func_declaration()
        if self._check(TokenType.IF):
            return self._if_statement()
        if self._check(TokenType.WHILE):
            return self._while_statement()
        if self._check(TokenType.FOR):
            return self._for_statement()
        if self._check(TokenType.RETURN):
            return self._return_statement()
        if self._check(TokenType.BREAK):
            return self._break_statement()
        if self._check(TokenType.CONTINUE):
            return self._continue_statement()
        if self._check(TokenType.PRINT):
            return self._print_statement()
        if self._check(TokenType.LBRACE):
            return self._block()
        return self._expression_statement()

    def _var_declaration(self) -> VarDecl:
        tok = self._advance()
        name = self._consume(TokenType.IDENTIFIER, "Expected variable name after 'var'.")
        initializer = None
        if self._match(TokenType.EQUAL):
            initializer = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after variable declaration.")
        return VarDecl(name.literal, initializer, tok.line)

    def _func_declaration(self) -> FuncDecl:
        tok = self._advance()
        name = self._consume(TokenType.IDENTIFIER, "Expected function name after 'func'.")
        self._consume(TokenType.LPAREN, "Expected '(' after function name.")
        params = []
        if not self._check(TokenType.RPAREN):
            params.append(self._consume(TokenType.IDENTIFIER, "Expected parameter name.").literal)
            while self._match(TokenType.COMMA):
                params.append(self._consume(TokenType.IDENTIFIER, "Expected parameter name.").literal)
        self._consume(TokenType.RPAREN, "Expected ')' after parameters.")
        body = self._block()
        return FuncDecl(name.literal, params, body, tok.line)

    def _if_statement(self) -> If:
        tok = self._advance()
        self._consume(TokenType.LPAREN, "Expected '(' after 'if'.")
        condition = self._expression()
        self._consume(TokenType.RPAREN, "Expected ')' after if condition.")
        then_branch = self._statement()
        else_branch = None
        if self._match(TokenType.ELSE):
            else_branch = self._statement()
        return If(condition, then_branch, else_branch, tok.line)

    def _while_statement(self) -> While:
        tok = self._advance()
        self._consume(TokenType.LPAREN, "Expected '(' after 'while'.")
        condition = self._expression()
        self._consume(TokenType.RPAREN, "Expected ')' after while condition.")
        body = self._statement()
        return While(condition, body, tok.line)

    def _for_statement(self) -> For:
        tok = self._advance()
        self._consume(TokenType.LPAREN, "Expected '(' after 'for'.")
        initializer = None
        if self._match(TokenType.SEMICOLON):
            pass
        elif self._check(TokenType.VAR):
            initializer = self._var_declaration()
        else:
            initializer = self._expression_statement()
        condition = None
        if not self._check(TokenType.SEMICOLON):
            condition = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after for condition.")
        increment = None
        if not self._check(TokenType.RPAREN):
            increment = self._expression()
        self._consume(TokenType.RPAREN, "Expected ')' after for clauses.")
        body = self._statement()
        return For(initializer, condition, increment, body, tok.line)

    def _return_statement(self) -> Return:
        tok = self._advance()
        value = None
        if not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after 'return'.")
        return Return(value, tok.line)

    def _break_statement(self) -> Break:
        tok = self._advance()
        self._consume(TokenType.SEMICOLON, "Expected ';' after 'break'.")
        return Break(tok.line)

    def _continue_statement(self) -> Continue:
        tok = self._advance()
        self._consume(TokenType.SEMICOLON, "Expected ';' after 'continue'.")
        return Continue(tok.line)

    def _print_statement(self) -> Print:
        tok = self._advance()
        expr = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after print expression.")
        return Print(expr, tok.line)

    def _block(self) -> Block:
        tok = self._consume(TokenType.LBRACE, "Expected '{' to begin block.")
        statements = []
        while not self._check(TokenType.RBRACE) and not self._check(TokenType.EOF):
            stmt = self._statement()
            if stmt is not None:
                statements.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' to end block.")
        return Block(statements, tok.line)

    def _expression_statement(self) -> ExprStmt:
        tok = self._peek()
        expr = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after expression.")
        return ExprStmt(expr, tok.line)

    def _expression(self) -> ASTNode:
        return self._assignment()

    def _assignment(self) -> ASTNode:
        expr = self._or()
        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if isinstance(expr, Identifier):
                return Assign(expr.name, value, equals.line)
            raise ParseError("Invalid assignment target.", equals.line)
        return expr

    def _or(self) -> ASTNode:
        expr = self._and()
        while self._match(TokenType.OR):
            op = self._previous()
            right = self._and()
            expr = Logical(expr, op.literal, right, op.line)
        return expr

    def _and(self) -> ASTNode:
        expr = self._equality()
        while self._match(TokenType.AND):
            op = self._previous()
            right = self._equality()
            expr = Logical(expr, op.literal, right, op.line)
        return expr

    def _equality(self) -> ASTNode:
        expr = self._comparison()
        while self._match(TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            op = self._previous()
            right = self._comparison()
            expr = Binary(expr, op.literal, right, op.line)
        return expr

    def _comparison(self) -> ASTNode:
        expr = self._term()
        while self._match(TokenType.GREATER, TokenType.GREATER_EQUAL,
                          TokenType.LESS, TokenType.LESS_EQUAL):
            op = self._previous()
            right = self._term()
            expr = Binary(expr, op.literal, right, op.line)
        return expr

    def _term(self) -> ASTNode:
        expr = self._factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self._previous()
            right = self._factor()
            expr = Binary(expr, op.literal, right, op.line)
        return expr

    def _factor(self) -> ASTNode:
        expr = self._unary()
        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._previous()
            right = self._unary()
            expr = Binary(expr, op.literal, right, op.line)
        return expr

    def _unary(self) -> ASTNode:
        if self._match(TokenType.MINUS, TokenType.NOT, TokenType.PLUS):
            op = self._previous()
            right = self._unary()
            return Unary(op.literal, right, op.line)
        return self._call()

    def _call(self) -> ASTNode:
        expr = self._primary()
        while True:
            if self._match(TokenType.LPAREN):
                line = self._previous().line
                args = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        args.append(self._expression())
                self._consume(TokenType.RPAREN, "Expected ')' after arguments.")
                expr = Call(expr, args, line)
            elif self._match(TokenType.LBRACKET):
                line = self._previous().line
                index = self._expression()
                self._consume(TokenType.RBRACKET, "Expected ']' after subscript.")
                expr = Subscript(expr, index, line)
            else:
                break
        return expr

    def _primary(self) -> ASTNode:
        if self._match(TokenType.NUMBER):
            tok = self._previous()
            return Number(tok.literal, tok.line)
        if self._match(TokenType.STRING):
            tok = self._previous()
            return Str(tok.literal, tok.line)
        if self._match(TokenType.TRUE):
            return Bool(True, self._previous().line)
        if self._match(TokenType.FALSE):
            return Bool(False, self._previous().line)
        if self._match(TokenType.NIL):
            return Nil(self._previous().line)
        if self._match(TokenType.IDENTIFIER):
            return Identifier(self._previous().literal, self._previous().line)
        if self._match(TokenType.LPAREN):
            tok = self._previous()
            expr = self._expression()
            self._consume(TokenType.RPAREN, "Expected ')' after expression.")
            return Grouping(expr, tok.line)
        if self._match(TokenType.LBRACKET):
            tok = self._previous()
            elements = []
            if not self._check(TokenType.RBRACKET):
                elements.append(self._expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._expression())
            self._consume(TokenType.RBRACKET, "Expected ']' after list literal.")
            return ListLiteral(elements, tok.line)
        tok = self._peek()
        raise ParseError(f"Unexpected token: {tok.literal!r}", tok.line)



# ====== Runtime Value Types ======
RT_NUMBER = "number"
RT_STRING = "string"
RT_BOOL = "bool"
RT_NIL = "nil"
RT_LIST = "list"
RT_FUNCTION = "function"
RT_NATIVE_FN = "native_fn"


class RuntimeValue:
    def __init__(self, type_name: str, value: Any):
        self.type = type_name
        self.value = value

    def __repr__(self):
        return f"RuntimeValue({self.type}, {self.value!r})"


# ====== Function ======
class Function:
    def __init__(self, decl: FuncDecl, closure: 'Environment', is_initializer: bool = False):
        self.decl = decl
        self.closure = closure
        self.is_initializer = is_initializer

    def arity(self) -> int:
        return len(self.decl.params)

    def __repr__(self):
        return f"<fn {self.decl.name}>"


# ====== Environment ======
class Environment:
    def __init__(self, enclosing: Optional['Environment'] = None):
        self.values: Dict[str, RuntimeValue] = {}
        self.enclosing = enclosing

    def define(self, name: str, value: RuntimeValue):
        self.values[name] = value

    def get(self, name: str, line: int = 0) -> RuntimeValue:
        if name in self.values:
            return self.values[name]
        if self.enclosing is not None:
            return self.enclosing.get(name, line)
        raise MiniLangRuntimeError(f"Undefined variable '{name}'", line)

    def assign(self, name: str, value: RuntimeValue, line: int = 0):
        if name in self.values:
            self.values[name] = value
            return
        if self.enclosing is not None:
            self.enclosing.assign(name, value, line)
            return
        raise MiniLangRuntimeError(f"Undefined variable '{name}'", line)

    def get_at(self, depth: int, name: str) -> Optional[RuntimeValue]:
        env = self
        for _ in range(depth):
            if env is None:
                return None
            env = env.enclosing
        if env is not None and name in env.values:
            return env.values[name]
        return None

    def assign_at(self, depth: int, name: str, value: RuntimeValue):
        env = self
        for _ in range(depth):
            if env is None:
                return
            env = env.enclosing
        if env is not None:
            env.values[name] = value


# ====== Runtime Error ======
class MiniLangRuntimeError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"[Runtime Error] Line {line}: {message}" if line else f"[Runtime Error] {message}")


# ====== Return Value ======
class ReturnValue(Exception):
    def __init__(self, value: Optional[RuntimeValue]):
        self.value = value


# ====== Loop Control ======
class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass



# ====== Interpreter ======
class Interpreter:
    def __init__(self):
        self.globals = Environment()
        self.environment = self.globals
        self._locals: Dict[ASTNode, int] = {}
        self._define_builtins()

    def _define_builtins(self):
        builtins = {
            "print": _native_print,
            "len": _native_len,
            "str": _native_str,
            "int": _native_int,
            "type": _native_type,
            "input": _native_input,
            "sqrt": _native_sqrt,
            "abs": _native_abs,
            "rand": _native_rand,
        }

        # Register stdlib modules as nested objects (list of [key, value] pairs)
        for mod_name, mod_fns in _STDLIB_MODULES.items():
            module_dict = []
            for fn_name, fn in mod_fns.items():
                pair = [
                    RuntimeValue(RT_STRING, fn_name),
                    RuntimeValue(RT_NATIVE_FN, fn)
                ]
                module_dict.append(RuntimeValue(RT_LIST, pair))
            self.globals.define(mod_name, RuntimeValue(RT_LIST, module_dict))

        # Register builtins AFTER stdlib so they take precedence
        for name, fn in builtins.items():
            self.globals.define(name, RuntimeValue(RT_NATIVE_FN, fn))

    def resolve(self, expr: ASTNode, depth: int):
        self._locals[expr] = depth

    def _lookup_variable(self, name: str, expr: ASTNode, line: int) -> RuntimeValue:
        # Search through the full environment chain
        env = self.environment
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.enclosing
        raise MiniLangRuntimeError(f"Undefined variable '{name}'", line)

    def interpret(self, statements: List[Stmt]) -> Optional[RuntimeValue]:
        result = None
        try:
            for stmt in statements:
                result = self._execute(stmt)
            return result
        except MiniLangRuntimeError:
            raise

    def _execute(self, stmt: Stmt) -> Optional[RuntimeValue]:
        if isinstance(stmt, ExprStmt):
            return self._evaluate(stmt.expr)
        elif isinstance(stmt, Print):
            value = self._evaluate(stmt.expr)
            _native_print(value)
            return value
        elif isinstance(stmt, VarDecl):
            value = RuntimeValue(RT_NIL, None)
            if stmt.initializer is not None:
                value = self._evaluate(stmt.initializer)
            self.environment.define(stmt.name, value)
            return value
        elif isinstance(stmt, FuncDecl):
            func = Function(stmt, self.environment)
            self.environment.define(stmt.name, RuntimeValue(RT_FUNCTION, func))
            return RuntimeValue(RT_FUNCTION, func)
        elif isinstance(stmt, Block):
            return self._execute_block(stmt.statements, Environment(self.environment))
        elif isinstance(stmt, If):
            cond = self._evaluate(stmt.condition)
            if self._is_truthy(cond):
                return self._execute(stmt.then_branch)
            elif stmt.else_branch is not None:
                return self._execute(stmt.else_branch)
            return None
        elif isinstance(stmt, While):
            return self._execute_while(stmt)
        elif isinstance(stmt, For):
            return self._execute_for(stmt)
        elif isinstance(stmt, Return):
            value = None
            if stmt.value is not None:
                value = self._evaluate(stmt.value)
            raise ReturnValue(value)
        elif isinstance(stmt, Break):
            raise BreakException()
        elif isinstance(stmt, Continue):
            raise ContinueException()
        return None

    def _execute_while(self, stmt: While) -> Optional[RuntimeValue]:
        result = None
        while True:
            cond = self._evaluate(stmt.condition)
            if not self._is_truthy(cond):
                break
            try:
                result = self._execute(stmt.body)
            except BreakException:
                break
            except ContinueException:
                continue
        return result

    def _execute_for(self, stmt: For) -> Optional[RuntimeValue]:
        loop_env = Environment(self.environment) if stmt.initializer else self.environment
        if stmt.initializer:
            prev = self.environment
            self.environment = loop_env
        else:
            prev = self.environment
            self.environment = loop_env

        try:
            if stmt.initializer is not None:
                self._execute(stmt.initializer)

            while True:
                if stmt.condition is not None:
                    cond = self._evaluate(stmt.condition)
                    if not self._is_truthy(cond):
                        break
                try:
                    self._execute(stmt.body)
                except BreakException:
                    break
                except ContinueException:
                    pass

                if stmt.increment is not None:
                    self._evaluate(stmt.increment)
        finally:
            self.environment = prev
        return None

    def _execute_block(self, statements: List[Stmt], env: Environment) -> Optional[RuntimeValue]:
        previous = self.environment
        self.environment = env
        try:
            result = None
            for stmt in statements:
                result = self._execute(stmt)
            return result
        finally:
            self.environment = previous

    def _evaluate(self, expr: ASTNode) -> RuntimeValue:
        if isinstance(expr, Number):
            return RuntimeValue(RT_NUMBER, expr.value)
        elif isinstance(expr, Str):
            return RuntimeValue(RT_STRING, expr.value)
        elif isinstance(expr, Bool):
            return RuntimeValue(RT_BOOL, expr.value)
        elif isinstance(expr, Nil):
            return RuntimeValue(RT_NIL, None)
        elif isinstance(expr, ListLiteral):
            elements = [self._evaluate(e) for e in expr.elements]
            return RuntimeValue(RT_LIST, elements)
        elif isinstance(expr, Identifier):
            return self._lookup_variable(expr.name, expr, expr.line)
        elif isinstance(expr, Grouping):
            return self._evaluate(expr.expr)
        elif isinstance(expr, Unary):
            return self._evaluate_unary(expr)
        elif isinstance(expr, Binary):
            return self._evaluate_binary(expr)
        elif isinstance(expr, Logical):
            return self._evaluate_logical(expr)
        elif isinstance(expr, Call):
            return self._evaluate_call(expr)
        elif isinstance(expr, Assign):
            return self._evaluate_assign(expr)
        elif isinstance(expr, Subscript):
            return self._evaluate_subscript(expr)
        raise MiniLangRuntimeError(f"Unknown expression type: {type(expr).__name__}", getattr(expr, 'line', 0))

    def _evaluate_unary(self, expr: Unary) -> RuntimeValue:
        right = self._evaluate(expr.right)
        if expr.op == "-":
            if right.type != RT_NUMBER:
                raise MiniLangRuntimeError(f"Cannot negate {right.type}", expr.line)
            return RuntimeValue(RT_NUMBER, -right.value)
        elif expr.op == "+":
            if right.type != RT_NUMBER:
                raise MiniLangRuntimeError(f"Cannot apply unary + to {right.type}", expr.line)
            return RuntimeValue(RT_NUMBER, right.value)
        elif expr.op == "not":
            return RuntimeValue(RT_BOOL, not self._is_truthy(right))
        raise MiniLangRuntimeError(f"Unknown unary operator: {expr.op}", expr.line)

    def _evaluate_binary(self, expr: Binary) -> RuntimeValue:
        left = self._evaluate(expr.left)
        right = self._evaluate(expr.right)

        if expr.op == "+":
            if left.type == RT_NUMBER and right.type == RT_NUMBER:
                return RuntimeValue(RT_NUMBER, left.value + right.value)
            if left.type == RT_STRING and right.type == RT_STRING:
                return RuntimeValue(RT_STRING, left.value + right.value)
            if left.type == RT_STRING:
                return RuntimeValue(RT_STRING, left.value + _to_string(right))
            if right.type == RT_STRING:
                return RuntimeValue(RT_STRING, _to_string(left) + right.value)
            raise MiniLangRuntimeError(f"Cannot add {left.type} and {right.type}", expr.line)

        if expr.op == "-":
            self._check_number_operands(expr.op, left, right, expr.line)
            return RuntimeValue(RT_NUMBER, left.value - right.value)
        if expr.op == "*":
            if left.type == RT_NUMBER and right.type == RT_NUMBER:
                return RuntimeValue(RT_NUMBER, left.value * right.value)
            if left.type == RT_STRING and right.type == RT_NUMBER:
                return RuntimeValue(RT_STRING, left.value * right.value)
            raise MiniLangRuntimeError(f"Cannot multiply {left.type} and {right.type}", expr.line)
        if expr.op == "/":
            self._check_number_operands(expr.op, left, right, expr.line)
            if right.value == 0:
                raise MiniLangRuntimeError("Division by zero", expr.line)
            return RuntimeValue(RT_NUMBER, left.value / right.value)
        if expr.op == "%":
            self._check_number_operands(expr.op, left, right, expr.line)
            if right.value == 0:
                raise MiniLangRuntimeError("Division by zero", expr.line)
            # Use Python's % which handles negatives like C
            result = left.value % right.value
            return RuntimeValue(RT_NUMBER, result)

        if expr.op == "==":
            return RuntimeValue(RT_BOOL, _values_equal(left, right))
        if expr.op == "!=":
            return RuntimeValue(RT_BOOL, not _values_equal(left, right))

        self._check_number_operands(expr.op, left, right, expr.line)
        if expr.op == ">":
            return RuntimeValue(RT_BOOL, left.value > right.value)
        if expr.op == ">=":
            return RuntimeValue(RT_BOOL, left.value >= right.value)
        if expr.op == "<":
            return RuntimeValue(RT_BOOL, left.value < right.value)
        if expr.op == "<=":
            return RuntimeValue(RT_BOOL, left.value <= right.value)

        raise MiniLangRuntimeError(f"Unknown binary operator: {expr.op}", expr.line)

    def _evaluate_logical(self, expr: Logical) -> RuntimeValue:
        left = self._evaluate(expr.left)
        if expr.op == "or":
            if self._is_truthy(left):
                return left
            return self._evaluate(expr.right)
        elif expr.op == "and":
            if not self._is_truthy(left):
                return left
            return self._evaluate(expr.right)
        raise MiniLangRuntimeError(f"Unknown logical operator: {expr.op}", expr.line)

    def _evaluate_call(self, expr: Call) -> RuntimeValue:
        callee = self._evaluate(expr.callee)

        if callee.type == RT_NATIVE_FN:
            args = [self._evaluate(a) for a in expr.arguments]
            return callee.value(*args, line=expr.line)

        if callee.type != RT_FUNCTION:
            raise MiniLangRuntimeError(f"Cannot call {callee.type}", expr.line)

        func: Function = callee.value
        if len(expr.arguments) != func.arity():
            raise MiniLangRuntimeError(
                f"Expected {func.arity()} arguments but got {len(expr.arguments)}",
                expr.line
            )

        env = Environment(func.closure)
        for i, param in enumerate(func.decl.params):
            arg_value = self._evaluate(expr.arguments[i])
            env.define(param, arg_value)

        try:
            self._execute_block(func.decl.body.statements, env)
        except ReturnValue as ret:
            return ret.value if ret.value is not None else RuntimeValue(RT_NIL, None)
        return RuntimeValue(RT_NIL, None)

    def _evaluate_assign(self, expr: Assign) -> RuntimeValue:
        value = self._evaluate(expr.value)
        # Search through environment chain
        env = self.environment
        while env is not None:
            if expr.name in env.values:
                env.values[expr.name] = value
                return value
            env = env.enclosing
        raise MiniLangRuntimeError(f"Undefined variable '{expr.name}'", expr.line)

    def _evaluate_subscript(self, expr: Subscript) -> RuntimeValue:
        obj = self._evaluate(expr.obj)
        idx = self._evaluate(expr.index)
        if obj.type != RT_LIST:
            raise MiniLangRuntimeError("Cannot index non-list value", expr.line)
        lst = obj.value
        if idx.type == RT_NUMBER:
            index = int(idx.value)
            if index < 0 or index >= len(lst):
                raise MiniLangRuntimeError(f"List index {index} out of range [0, {len(lst)})", expr.line)
            return lst[index]
        elif idx.type == RT_STRING:
            key = idx.value
            for item in lst:
                if item.type == RT_LIST and len(item.value) >= 2:
                    k = item.value[0]
                    if k.type == RT_STRING and k.value == key:
                        return item.value[1]
            raise MiniLangRuntimeError(f"Key '{key}' not found in module", expr.line)
        else:
            raise MiniLangRuntimeError(f"List index must be a number or string, got {idx.type}", expr.line)

    def _check_number_operands(self, op: str, left: RuntimeValue, right: RuntimeValue, line: int):
        if left.type != RT_NUMBER or right.type != RT_NUMBER:
            raise MiniLangRuntimeError(f"Cannot apply '{op}' to {left.type} and {right.type}", line)

    def _is_truthy(self, value: RuntimeValue) -> bool:
        if value.type == RT_NIL:
            return False
        if value.type == RT_BOOL:
            return value.value
        if value.type == RT_NUMBER:
            return value.value != 0
        if value.type == RT_STRING:
            return value.value != ""
        if value.type == RT_LIST:
            return len(value.value) > 0
        return True



# ====== Helper Functions ======
def _to_string(value: RuntimeValue) -> str:
    if value.type == RT_NIL:
        return "nil"
    if value.type == RT_BOOL:
        return "true" if value.value else "false"
    if value.type == RT_NUMBER:
        if isinstance(value.value, float) and value.value == int(value.value):
            return str(int(value.value))
        return str(value.value)
    if value.type == RT_STRING:
        return value.value
    if value.type == RT_LIST:
        elements = ", ".join(_to_string(e) for e in value.value)
        return "[" + elements + "]"
    if value.type == RT_FUNCTION:
        return f"<fn {value.value.decl.name}>"
    if value.type == RT_NATIVE_FN:
        return f"<native fn {value.value.__name__}>"
    return str(value.value)


def _values_equal(a: RuntimeValue, b: RuntimeValue) -> bool:
    if a.type != b.type:
        return False
    if a.type == RT_NIL:
        return True
    if a.type == RT_LIST:
        if len(a.value) != len(b.value):
            return False
        for i in range(len(a.value)):
            if not _values_equal(a.value[i], b.value[i]):
                return False
        return True
    return a.value == b.value


# ====== Native Functions ======
_NATIVE_PRINT_BUFFER = []


def _native_print(*args, line: int = 0):
    output = " ".join(_to_string(a) for a in args)
    _NATIVE_PRINT_BUFFER.append(output)
    print(output)
    return RuntimeValue(RT_NIL, None)


def _native_len(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("len() requires 1 argument", line)
    val = args[0]
    if val.type == RT_STRING:
        return RuntimeValue(RT_NUMBER, len(val.value))
    if val.type == RT_LIST:
        return RuntimeValue(RT_NUMBER, len(val.value))
    raise MiniLangRuntimeError(f"len() not supported for {val.type}", line)


def _native_str(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_STRING, "")
    return RuntimeValue(RT_STRING, _to_string(args[0]))


def _native_int(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_NUMBER, 0)
    val = args[0]
    if val.type == RT_NUMBER:
        return RuntimeValue(RT_NUMBER, int(val.value))
    if val.type == RT_STRING:
        try:
            return RuntimeValue(RT_NUMBER, int(val.value))
        except ValueError:
            raise MiniLangRuntimeError(f"Cannot convert '{val.value}' to int", line)
    raise MiniLangRuntimeError(f"Cannot convert {val.type} to int", line)


def _native_type(*args, line: int = 0):
    if not args:
        return RuntimeValue(RT_STRING, "nil")
    return RuntimeValue(RT_STRING, args[0].type)


def _native_input(*args, line: int = 0):
    prompt = ""
    if args:
        prompt = _to_string(args[0])
    try:
        result = input(prompt)
        return RuntimeValue(RT_STRING, result)
    except EOFError:
        return RuntimeValue(RT_STRING, "")


def _native_sqrt(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("sqrt() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"sqrt() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, math.sqrt(val.value))


def _native_abs(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("abs() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"abs() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, abs(val.value))


def _native_rand(*args, line: int = 0):
    if len(args) == 0:
        return RuntimeValue(RT_NUMBER, random.random())
    if len(args) == 1:
        if args[0].type != RT_NUMBER:
            raise MiniLangRuntimeError("rand() requires a number", line)
        return RuntimeValue(RT_NUMBER, random.randint(0, int(args[0].value)))
    if len(args) == 2:
        if args[0].type != RT_NUMBER or args[1].type != RT_NUMBER:
            raise MiniLangRuntimeError("rand() requires numbers", line)
        return RuntimeValue(RT_NUMBER, random.randint(int(args[0].value), int(args[1].value)))
    raise MiniLangRuntimeError("rand() takes 0-2 arguments", line)


# ====== Stdlib: JSON ======
def _stdlib_json_loads(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("json.loads() requires 1 argument", line)
    s = args[0]
    if s.type != RT_STRING:
        raise MiniLangRuntimeError(f"json.loads() requires a string, got {s.type}", line)
    try:
        parsed = json.loads(s.value)
    except json.JSONDecodeError as e:
        raise MiniLangRuntimeError(f"json.loads() error: {e}", line)
    return _py_to_runtime(parsed, line)


def _py_to_runtime(val, line: int = 0) -> RuntimeValue:
    """Convert a Python value to a MiniLang RuntimeValue."""
    if val is None:
        return RuntimeValue(RT_NIL, None)
    if isinstance(val, bool):
        return RuntimeValue(RT_BOOL, val)
    if isinstance(val, (int, float)):
        return RuntimeValue(RT_NUMBER, val)
    if isinstance(val, str):
        return RuntimeValue(RT_STRING, val)
    if isinstance(val, (list, tuple)):
        return RuntimeValue(RT_LIST, [_py_to_runtime(v, line) for v in val])
    if isinstance(val, dict):
        # Represent dicts as lists of [key, value] pairs for simplicity
        result = []
        for k, v in val.items():
            pair = [
                RuntimeValue(RT_STRING, str(k)),
                _py_to_runtime(v, line)
            ]
            result.append(RuntimeValue(RT_LIST, pair))
        return RuntimeValue(RT_LIST, result)
    raise MiniLangRuntimeError(f"Cannot convert {type(val).__name__} to MiniLang value", line)


# ====== Stdlib: File IO ======
def _stdlib_file_read(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("file.read() requires 1 argument", line)
    path = args[0]
    if path.type != RT_STRING:
        raise MiniLangRuntimeError(f"file.read() requires a string path, got {path.type}", line)
    try:
        with open(path.value, "r", encoding="utf-8") as f:
            content = f.read()
        return RuntimeValue(RT_STRING, content)
    except Exception as e:
        raise MiniLangRuntimeError(f"file.read() error: {e}", line)


def _stdlib_file_write(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("file.write() requires 2 arguments (path, content)", line)
    path = args[0]
    content = args[1]
    if path.type != RT_STRING:
        raise MiniLangRuntimeError(f"file.write() path must be a string, got {path.type}", line)
    try:
        with open(path.value, "w", encoding="utf-8") as f:
            f.write(_to_string(content))
        return RuntimeValue(RT_NIL, None)
    except Exception as e:
        raise MiniLangRuntimeError(f"file.write() error: {e}", line)


def _stdlib_file_append(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("file.append() requires 2 arguments (path, content)", line)
    path = args[0]
    content = args[1]
    if path.type != RT_STRING:
        raise MiniLangRuntimeError(f"file.append() path must be a string, got {path.type}", line)
    try:
        with open(path.value, "a", encoding="utf-8") as f:
            f.write(_to_string(content))
        return RuntimeValue(RT_NIL, None)
    except Exception as e:
        raise MiniLangRuntimeError(f"file.append() error: {e}", line)


# ====== Stdlib: HTTP ======
def _stdlib_http_get(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("http.get() requires 1 argument (url)", line)
    url = args[0]
    if url.type != RT_STRING:
        raise MiniLangRuntimeError(f"http.get() url must be a string, got {url.type}", line)
    try:
        with urllib.request.urlopen(url.value, timeout=10) as response:
            data = response.read().decode("utf-8")
        return RuntimeValue(RT_STRING, data)
    except Exception as e:
        raise MiniLangRuntimeError(f"http.get() error: {e}", line)


# ====== Stdlib: Time ======
def _stdlib_time_now(*args, line: int = 0):
    return RuntimeValue(RT_NUMBER, _time.time())


def _stdlib_time_sleep(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("time.sleep() requires 1 argument (ms)", line)
    ms = args[0]
    if ms.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"time.sleep() requires a number, got {ms.type}", line)
    _time.sleep(ms.value / 1000.0)
    return RuntimeValue(RT_NIL, None)


# ====== Stdlib: Array Operations ======
def _stdlib_arr_push(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("arr.push() requires 2 arguments (list, value)", line)
    lst = args[0]
    if lst.type != RT_LIST:
        raise MiniLangRuntimeError(f"arr.push() requires a list, got {lst.type}", line)
    lst.value.append(args[1])
    return RuntimeValue(RT_NUMBER, len(lst.value))


def _stdlib_arr_pop(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("arr.pop() requires 1 argument (list)", line)
    lst = args[0]
    if lst.type != RT_LIST:
        raise MiniLangRuntimeError(f"arr.pop() requires a list, got {lst.type}", line)
    if not lst.value:
        raise MiniLangRuntimeError("arr.pop() on empty list", line)
    return lst.value.pop()


def _stdlib_arr_len(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("arr.len() requires 1 argument (list)", line)
    lst = args[0]
    if lst.type != RT_LIST:
        raise MiniLangRuntimeError(f"arr.len() requires a list, got {lst.type}", line)
    return RuntimeValue(RT_NUMBER, len(lst.value))


def _stdlib_arr_sort(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("arr.sort() requires 1 argument (list)", line)
    lst = args[0]
    if lst.type != RT_LIST:
        raise MiniLangRuntimeError(f"arr.sort() requires a list, got {lst.type}", line)
    # Sort based on numeric value if all are numbers, else string representation
    try:
        lst.value.sort(key=lambda v: v.value if hasattr(v, 'value') else str(v))
    except Exception as e:
        raise MiniLangRuntimeError(f"arr.sort() error: {e}", line)
    return RuntimeValue(RT_NIL, None)


# ====== Stdlib: String Operations ======
def _stdlib_str_len(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("str.len() requires 1 argument (string)", line)
    s = args[0]
    if s.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.len() requires a string, got {s.type}", line)
    return RuntimeValue(RT_NUMBER, len(s.value))


def _stdlib_str_upper(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("str.upper() requires 1 argument (string)", line)
    s = args[0]
    if s.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.upper() requires a string, got {s.type}", line)
    return RuntimeValue(RT_STRING, s.value.upper())


def _stdlib_str_lower(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("str.lower() requires 1 argument (string)", line)
    s = args[0]
    if s.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.lower() requires a string, got {s.type}", line)
    return RuntimeValue(RT_STRING, s.value.lower())


def _stdlib_str_split(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("str.split() requires 2 arguments (string, separator)", line)
    s = args[0]
    sep = args[1]
    if s.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.split() first argument must be a string, got {s.type}", line)
    if sep.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.split() separator must be a string, got {sep.type}", line)
    parts = s.value.split(sep.value)
    return RuntimeValue(RT_LIST, [RuntimeValue(RT_STRING, p) for p in parts])


def _stdlib_str_join(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("str.join() requires 2 arguments (separator, list)", line)
    sep = args[0]
    lst = args[1]
    if sep.type != RT_STRING:
        raise MiniLangRuntimeError(f"str.join() separator must be a string, got {sep.type}", line)
    if lst.type != RT_LIST:
        raise MiniLangRuntimeError(f"str.join() second argument must be a list, got {lst.type}", line)
    parts = [_to_string(v) for v in lst.value]
    return RuntimeValue(RT_STRING, sep.value.join(parts))


# ====== Stdlib: Math ======
def _stdlib_math_abs(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("math.abs() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.abs() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, abs(val.value))


def _stdlib_math_round(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("math.round() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.round() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, round(val.value))


def _stdlib_math_floor(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("math.floor() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.floor() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, math.floor(val.value))


def _stdlib_math_ceil(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("math.ceil() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.ceil() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, math.ceil(val.value))


def _stdlib_math_sqrt(*args, line: int = 0):
    if not args:
        raise MiniLangRuntimeError("math.sqrt() requires 1 argument", line)
    val = args[0]
    if val.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.sqrt() requires a number, got {val.type}", line)
    return RuntimeValue(RT_NUMBER, math.sqrt(val.value))


def _stdlib_math_pow(*args, line: int = 0):
    if len(args) < 2:
        raise MiniLangRuntimeError("math.pow() requires 2 arguments (base, exponent)", line)
    a = args[0]
    b = args[1]
    if a.type != RT_NUMBER or b.type != RT_NUMBER:
        raise MiniLangRuntimeError(f"math.pow() requires numbers, got {a.type}, {b.type}", line)
    return RuntimeValue(RT_NUMBER, math.pow(a.value, b.value))


# ====== Stdlib: System ======
def _stdlib_sys_argv(*args, line: int = 0):
    items = [RuntimeValue(RT_STRING, s) for s in sys.argv]
    return RuntimeValue(RT_LIST, items)


def _stdlib_sys_exit(*args, line: int = 0):
    code = 0
    if args:
        val = args[0]
        if val.type == RT_NUMBER:
            code = int(val.value)
    sys.exit(code)


# ====== Stdlib registration ======
_STDLIB_MODULES = {
    "json": {
        "loads": _stdlib_json_loads,
    },
    "file": {
        "read": _stdlib_file_read,
        "write": _stdlib_file_write,
        "append": _stdlib_file_append,
    },
    "http": {
        "get": _stdlib_http_get,
    },
    "time": {
        "now": _stdlib_time_now,
        "sleep": _stdlib_time_sleep,
    },
    "arr": {
        "push": _stdlib_arr_push,
        "pop": _stdlib_arr_pop,
        "len": _stdlib_arr_len,
        "sort": _stdlib_arr_sort,
    },
    "str": {
        "len": _stdlib_str_len,
        "upper": _stdlib_str_upper,
        "lower": _stdlib_str_lower,
        "split": _stdlib_str_split,
        "join": _stdlib_str_join,
    },
    "math": {
        "abs": _stdlib_math_abs,
        "round": _stdlib_math_round,
        "floor": _stdlib_math_floor,
        "ceil": _stdlib_math_ceil,
        "sqrt": _stdlib_math_sqrt,
        "pow": _stdlib_math_pow,
    },
    "sys": {
        "argv": _stdlib_sys_argv,
        "exit": _stdlib_sys_exit,
    },
}


# ====== Run Functions ======
def run_source(source: str) -> Tuple[Optional[RuntimeValue], List[str], List[str]]:
    """Run MiniLang source code. Returns (result, lex_errors, parse_errors)."""
    lexer = Lexer(source)
    if lexer.errors:
        return None, lexer.errors, []

    parser = Parser(lexer.tokens)
    statements = parser.parse()

    if parser.errors:
        return None, [], parser.errors

    interpreter = Interpreter()
    try:
        result = interpreter.interpret(statements)
        return result, [], []
    except MiniLangRuntimeError as e:
        return None, [], [str(e)]


def run_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    result, lex_errors, parse_errors = run_source(source)
    if lex_errors:
        for e in lex_errors:
            print(e, file=sys.stderr)
        return False
    if parse_errors:
        for e in parse_errors:
            print(e, file=sys.stderr)
        return False
    return True


def repl():
    """Simple REPL for MiniLang."""
    interpreter = Interpreter()
    print("MiniLang REPL (type 'exit()' to quit)")
    while True:
        try:
            line = input(">>> ")
            if line.strip() in ("exit()", "quit()"):
                break
            lexer = Lexer(line)
            if lexer.errors:
                for e in lexer.errors:
                    print(e)
                continue
            parser = Parser(lexer.tokens)
            statements = parser.parse()
            if parser.errors:
                for e in parser.errors:
                    print(e)
                continue
            result = interpreter.interpret(statements)
            if result is not None and result.type != RT_NIL:
                print(_to_string(result))
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


# ====== Bytecode Compiler & VM Integration ======

def run_bc(code, name="<script>"):
    """Run MiniLang source via Bytecode Compiler + VM instead of tree-walk.
    
    Returns (result RuntimeValue, lex_errors, compile/vm_errors).
    """
    from compiler import Compiler
    from vm import VM
    
    _NATIVE_PRINT_BUFFER.clear()
    
    lexer = Lexer(code)
    if lexer.errors:
        return None, lexer.errors, []
    
    parser = Parser(lexer.tokens)
    statements = parser.parse()
    if parser.errors:
        return None, [], parser.errors
    
    compiler = Compiler()
    bytecode = compiler.compile(statements, name)
    if bytecode is None:
        return None, [], compiler.errors
    
    try:
        vm = VM()
        result = vm.execute(bytecode)
        return result, [], []
    except MiniLangRuntimeError as e:
        return None, [], [str(e)]
    except Exception as e:
        return None, [], [str(e)]


def run(code):
    """Run MiniLang source using the Bytecode VM (default)."""
    return run_bc(code)


def run_tree(code):
    """Run MiniLang source using the original tree-walk interpreter (preserved)."""
    return run_source(code)


def dump_bytecode(bytecode, indent=0):
    """Dump a Bytecode program as human-readable instructions.
    
    Args:
        bytecode: A Bytecode object
        indent: Indentation level (for nested functions)
    
    Returns:
        A string with the disassembly
    """
    from bytecode import OPCODE_NAMES
    prefix = "  " * indent
    lines = []
    
    lines.append(f"{prefix}== {bytecode.name} ==")
    lines.append(f"{prefix}  constants ({len(bytecode.constants)}):")
    for i, c in enumerate(bytecode.constants):
        lines.append(f"{prefix}    [{i}] {c!r}")
    
    lines.append(f"{prefix}  instructions ({len(bytecode.instructions) // 4}):")
    i = 0
    while i < len(bytecode.instructions):
        op = bytecode.instructions[i]
        name = OPCODE_NAMES.get(op, f"OP({op})")
        arg1 = bytecode.instructions[i + 1]
        arg2 = bytecode.instructions[i + 2]
        arg3 = bytecode.instructions[i + 3]
        
        # Format args nicely
        args_str = ""
        if op in (50, 51, 52):  # JMP/JMP_IF_FALSE/JMP_IF_TRUE
            offset = (arg1 << 16) | (arg2 << 8) | arg3
            if offset & 0x800000:
                offset -= 0x1000000
            target = i + 4 + offset
            args_str = f" -> {target}"
        elif op == 16:  # LOAD_CONST
            idx = arg1 | (arg2 << 8)
            if idx < len(bytecode.constants):
                args_str = f" [{idx}] {bytecode.constants[idx]!r}"
            else:
                args_str = f" [{idx}] (out of range)"
        elif op == 62:  # MAKE_FN
            idx = arg1 | (arg2 << 8)
            if idx < len(bytecode.functions):
                args_str = f" [{idx}] {bytecode.functions[idx].name}"
            else:
                args_str = f" [{idx}] (out of range)"
        elif op == 12 or op == 13:  # LOAD_GLOBAL/STORE_GLOBAL
            idx = arg1 | (arg2 << 8)
            if idx < len(bytecode.constants):
                args_str = f" '{bytecode.constants[idx]}'"
            else:
                args_str = f" [{idx}]"
        elif op == 60:  # CALL
            args_str = f" {arg1} args"
        elif arg1 or arg2 or arg3:
            args_str = f" {arg1} {arg2} {arg3}"
        
        lines.append(f"{prefix}    [{i:4d}] {name:12s}{args_str}")
        i += 4
    
    # Dump nested functions
    if bytecode.functions:
        lines.append(f"{prefix}  functions ({len(bytecode.functions)}):")
        for fn_bc in bytecode.functions:
            lines.append("")
            lines.append(dump_bytecode(fn_bc, indent + 1))
    
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        source = open(sys.argv[1], "r", encoding="utf-8").read()
        result, lex_errors, errors = run_bc(source)
        if lex_errors:
            for e in lex_errors:
                print(e, file=sys.stderr)
            sys.exit(1)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            sys.exit(1)
    else:
        repl()

