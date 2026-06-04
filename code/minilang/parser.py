from lexer import Token
from nodes import *
from typing import List


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, type: str, value=None):
        if self.peek().type != type or (value is not None and self.peek().value != value):
            expected = f"{type} '{value}'" if value else type
            got = f"{self.peek().type} '{self.peek().value}'"
            raise SyntaxError(f"Expected {expected}, got {got} at line {self.peek().line}")
        return self.advance()

    def parse(self) -> Program:
        statements = []
        while self.peek().type != 'EOF':
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return Program(statements)

    def parse_statement(self):
        if self.peek().type == 'KEYWORD':
            kw = self.peek().value
            if kw == 'let':
                return self.parse_var_decl()
            if kw == 'if':
                return self.parse_if()
            if kw == 'while':
                return self.parse_while()
            if kw == 'fn':
                return self.parse_function()
            if kw == 'return':
                return self.parse_return()
            if kw == 'print':
                return self.parse_print()

        # 表达式语句
        expr = self.parse_expression()
        self.expect('PUNCTUATION', ';')
        return expr

    def parse_var_decl(self):
        self.expect('KEYWORD', 'let')
        name = self.expect('IDENTIFIER').value
        initializer = None
        if self.peek().value == '=':
            self.advance()
            initializer = self.parse_expression()
        self.expect('PUNCTUATION', ';')
        return VarDecl(name, initializer)

    def parse_if(self):
        self.expect('KEYWORD', 'if')
        self.expect('PUNCTUATION', '(')
        condition = self.parse_expression()
        self.expect('PUNCTUATION', ')')
        then_branch = self.parse_block()
        else_branch = None
        if self.peek().type == 'KEYWORD' and self.peek().value == 'else':
            self.advance()
            else_branch = self.parse_block()
        return If(condition, then_branch, else_branch)

    def parse_while(self):
        self.expect('KEYWORD', 'while')
        self.expect('PUNCTUATION', '(')
        condition = self.parse_expression()
        self.expect('PUNCTUATION', ')')
        body = self.parse_block()
        return While(condition, body)

    def parse_function(self):
        self.expect('KEYWORD', 'fn')
        name = self.expect('IDENTIFIER').value
        self.expect('PUNCTUATION', '(')
        params = []
        while self.peek().value != ')':
            params.append(self.expect('IDENTIFIER').value)
            if self.peek().value == ',':
                self.advance()
        self.expect('PUNCTUATION', ')')
        body = self.parse_block()
        return FunctionDef(name, params, body)

    def parse_return(self):
        self.expect('KEYWORD', 'return')
        value = None
        if self.peek().value != ';':
            value = self.parse_expression()
        self.expect('PUNCTUATION', ';')
        return Return(value)

    def parse_print(self):
        self.expect('KEYWORD', 'print')
        self.expect('PUNCTUATION', '(')
        expr = self.parse_expression()
        self.expect('PUNCTUATION', ')')
        self.expect('PUNCTUATION', ';')
        return Print(expr)

    def parse_block(self):
        self.expect('PUNCTUATION', '{')
        statements = []
        while self.peek().value != '}':
            statements.append(self.parse_statement())
        self.expect('PUNCTUATION', '}')
        return Block(statements)

    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        expr = self.parse_or()
        if self.peek().type == 'OPERATOR' and self.peek().value == '=':
            self.advance()
            if not isinstance(expr, Identifier):
                raise SyntaxError("Left side of assignment must be identifier")
            value = self.parse_assignment()
            return Assign(expr.name, value)
        return expr

    def parse_or(self):
        left = self.parse_and()
        while self.peek().type == 'KEYWORD' and self.peek().value == 'or':
            self.advance()
            right = self.parse_and()
            left = BinaryOp('or', left, right)
        return left

    def parse_and(self):
        left = self.parse_comparison()
        while self.peek().type == 'KEYWORD' and self.peek().value == 'and':
            self.advance()
            right = self.parse_comparison()
            left = BinaryOp('and', left, right)
        return left

    def parse_comparison(self):
        left = self.parse_addition()
        while self.peek().type == 'OPERATOR' and self.peek().value in ('==', '!=', '<', '>', '<=', '>='):
            op = self.advance().value
            right = self.parse_addition()
            left = BinaryOp(op, left, right)
        return left

    def parse_addition(self):
        left = self.parse_multiplication()
        while self.peek().type == 'OPERATOR' and self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinaryOp(op, left, right)
        return left

    def parse_multiplication(self):
        left = self.parse_unary()
        while self.peek().type == 'OPERATOR' and self.peek().value in ('*', '/', '%'):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(op, left, right)
        return left

    def parse_unary(self):
        if self.peek().type == 'OPERATOR' and self.peek().value == '-':
            self.advance()
            operand = self.parse_unary()
            return UnaryOp('-', operand)
        if self.peek().type == 'KEYWORD' and self.peek().value == 'not':
            self.advance()
            operand = self.parse_unary()
            return UnaryOp('not', operand)
        return self.parse_call_or_primary()

    def parse_call_or_primary(self):
        expr = self.parse_primary()
        while True:
            if self.peek().value == '(':
                # 函数调用
                self.advance()
                args = []
                while self.peek().value != ')':
                    args.append(self.parse_expression())
                    if self.peek().value == ',':
                        self.advance()
                self.expect('PUNCTUATION', ')')
                expr = Call(expr, args)
            elif self.peek().value == '[':
                # 索引访问
                self.advance()
                index = self.parse_expression()
                self.expect('PUNCTUATION', ']')
                expr = Index(expr, index)
            else:
                break
        return expr

    def parse_primary(self):
        token = self.peek()

        if token.type == 'NUMBER':
            self.advance()
            return Number(token.value)

        if token.type == 'STRING':
            self.advance()
            return String(token.value)

        if token.type == 'KEYWORD':
            if token.value == 'true':
                self.advance()
                return Boolean(True)
            if token.value == 'false':
                self.advance()
                return Boolean(False)
            if token.value == 'nil':
                self.advance()
                return Nil()

        if token.type == 'IDENTIFIER':
            self.advance()
            return Identifier(token.value)

        if token.value == '(':
            self.advance()
            expr = self.parse_expression()
            self.expect('PUNCTUATION', ')')
            return expr

        if token.value == '[':
            self.advance()
            elements = []
            while self.peek().value != ']':
                elements.append(self.parse_expression())
                if self.peek().value == ',':
                    self.advance()
            self.expect('PUNCTUATION', ']')
            return ListLiteral(elements)

        raise SyntaxError(f"Unexpected token: {token.type} '{token.value}' at line {token.line}")
