"""
MiniLang Bytecode Compiler
Compiles MiniLang AST into bytecode for the C VM.
"""

from enum import Enum

# === Opcodes (must match bytecode.h) ===
class Op(Enum):
    HALT = 0
    PUSH_CONST = 1
    LOAD_VAR = 2
    STORE_VAR = 3
    ADD = 4
    SUB = 5
    MUL = 6
    DIV = 7
    MOD = 8
    EQ = 9
    NE = 10
    LT = 11
    GT = 12
    LE = 13
    GE = 14
    JMP = 15
    JMP_IF_FALSE = 16
    CALL = 17
    RET = 18
    PRINT = 19
    NEG = 20


class Bytecode:
    """Flat instruction list. Each instruction is (op, arg)."""
    def __init__(self):
        self.instructions = []  # list of (opcode_int, arg_int)
        self.constants = []     # list of (type, value): type=0 int, type=1 string
        self.symbols = []       # list of variable/function names

    def emit(self, op, arg=0):
        self.instructions.append((op.value, arg))

    def add_const_int(self, value):
        for i, (t, v) in enumerate(self.constants):
            if t == 0 and v == value:
                return i
        idx = len(self.constants)
        self.constants.append((0, value))
        return idx

    def add_const_string(self, value):
        for i, (t, v) in enumerate(self.constants):
            if t == 1 and v == value:
                return i
        idx = len(self.constants)
        self.constants.append((1, value))
        return idx

    def add_symbol(self, name):
        if name in self.symbols:
            return self.symbols.index(name)
        idx = len(self.symbols)
        self.symbols.append(name)
        return idx

    def patch_jump(self, pos):
        op, _ = self.instructions[pos]
        self.instructions[pos] = (op, len(self.instructions))

    def patch_jump_to(self, pos, target):
        op, _ = self.instructions[pos]
        self.instructions[pos] = (op, target)

    def __len__(self):
        return len(self.instructions)


# === MiniLang Lexer ===
class TokenType(Enum):
    NUMBER = 1
    STRING = 2
    IDENTIFIER = 3
    KEYWORD = 4
    OPERATOR = 5
    LPAREN = 6
    RPAREN = 7
    LBRACE = 8
    RBRACE = 9
    SEMICOLON = 10
    COMMA = 11
    EOF = 12


KEYWORDS = {'if', 'else', 'while', 'def', 'return', 'print'}


class Token:
    def __init__(self, type, value, line, col):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


class Lexer:
    def __init__(self, source):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1

    def error(self, msg):
        raise SyntaxError(f"{msg} at line {self.line}, col {self.col}")

    def peek(self):
        return self.source[self.pos] if self.pos < len(self.source) else '\0'

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace(self):
        while self.pos < len(self.source) and self.peek() in ' \t\n\r':
            self.advance()

    def read_number(self):
        start = self.pos
        while self.pos < len(self.source) and self.peek().isdigit():
            self.advance()
        return int(self.source[start:self.pos])

    def read_identifier(self):
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        return self.source[start:self.pos]

    def read_string(self):
        self.advance()  # skip opening "
        start = self.pos
        while self.pos < len(self.source) and self.peek() != '"':
            if self.peek() == '\\':
                self.advance()
                if self.pos < len(self.source):
                    self.advance()
            else:
                self.advance()
        if self.pos >= len(self.source):
            self.error("Unterminated string literal")
        result = self.source[start:self.pos]
        self.advance()  # skip closing "
        return result

    def tokenize(self):
        tokens = []
        while self.pos < len(self.source):
            self.skip_whitespace()
            if self.pos >= len(self.source):
                break

            ch = self.peek()

            # Single-line comments
            if ch == '#':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
                continue

            if ch.isdigit():
                val = self.read_number()
                tokens.append(Token(TokenType.NUMBER, val, self.line, self.col))
                continue

            if ch.isalpha() or ch == '_':
                val = self.read_identifier()
                if val in KEYWORDS:
                    tokens.append(Token(TokenType.KEYWORD, val, self.line, self.col))
                else:
                    tokens.append(Token(TokenType.IDENTIFIER, val, self.line, self.col))
                continue

            if ch == '"':
                val = self.read_string()
                tokens.append(Token(TokenType.STRING, val, self.line, self.col))
                continue

            # Multi-char operators: ==, !=, <=, >=
            if ch in '!<>=' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '=':
                op = ch + '='
                self.advance()
                self.advance()
                tokens.append(Token(TokenType.OPERATOR, op, self.line, self.col))
                continue

            # Single-char operators and punctuation
            if ch == '(':
                tokens.append(Token(TokenType.LPAREN, '(', self.line, self.col))
                self.advance()
            elif ch == ')':
                tokens.append(Token(TokenType.RPAREN, ')', self.line, self.col))
                self.advance()
            elif ch == '{':
                tokens.append(Token(TokenType.LBRACE, '{', self.line, self.col))
                self.advance()
            elif ch == '}':
                tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                self.advance()
            elif ch == ';':
                tokens.append(Token(TokenType.SEMICOLON, ';', self.line, self.col))
                self.advance()
            elif ch == ',':
                tokens.append(Token(TokenType.COMMA, ',', self.line, self.col))
                self.advance()
            elif ch in '+-*/%=><':
                tokens.append(Token(TokenType.OPERATOR, ch, self.line, self.col))
                self.advance()
            else:
                self.error(f"Unexpected character {ch!r}")

        tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return tokens


# === Parser ===
class ASTNode:
    pass


class Program(ASTNode):
    def __init__(self, statements):
        self.statements = statements


class ExprStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr


class NumberLiteral(ASTNode):
    def __init__(self, value):
        self.value = value


class StringLiteral(ASTNode):
    def __init__(self, value):
        self.value = value


class Identifier(ASTNode):
    def __init__(self, name):
        self.name = name


class BinaryOp(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right


class UnaryOp(ASTNode):
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr


class Assign(ASTNode):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class PrintStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr


class IfStmt(ASTNode):
    def __init__(self, condition, then_branch, else_branch=None):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class WhileStmt(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class Block(ASTNode):
    def __init__(self, statements):
        self.statements = statements


class FunctionDef(ASTNode):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class ReturnStmt(ASTNode):
    def __init__(self, expr):
        self.expr = expr


class CallExpr(ASTNode):
    def __init__(self, name, args):
        self.name = name
        self.args = args


PRECEDENCE = {
    '==': 2, '!=': 2,
    '<': 3, '>': 3, '<=': 3, '>=': 3,
    '+': 4, '-': 4,
    '*': 5, '/': 5, '%': 5,
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, expected_type, expected_value=None):
        tok = self.peek()
        if tok.type != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {tok.type} ({tok.value}) at line {tok.line}")
        if expected_value is not None and tok.value != expected_value:
            raise SyntaxError(f"Expected '{expected_value}', got '{tok.value}' at line {tok.line}")
        return self.advance()

    def parse(self):
        statements = []
        while self.peek().type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return Program(statements)

    def parse_statement(self):
        tok = self.peek()

        if tok.type == TokenType.KEYWORD:
            if tok.value == 'print':
                return self.parse_print()
            elif tok.value == 'if':
                return self.parse_if()
            elif tok.value == 'while':
                return self.parse_while()
            elif tok.value == 'def':
                return self.parse_function_def()
            elif tok.value == 'return':
                return self.parse_return()
            elif tok.value == 'else':
                raise SyntaxError("Unexpected 'else' without 'if'")

        if tok.type == TokenType.LBRACE:
            return self.parse_block()

        # Expression statement (assignment or expression)
        expr = self.parse_expression(0)
        if isinstance(expr, Identifier) and self.peek().type == TokenType.OPERATOR and self.peek().value == '=':
            self.advance()  # consume '='
            rhs = self.parse_expression(0)
            if self.peek().type == TokenType.SEMICOLON:
                self.advance()
            return Assign(expr.name, rhs)
        else:
            if self.peek().type == TokenType.SEMICOLON:
                self.advance()
            return ExprStmt(expr)

    def parse_print(self):
        self.advance()  # consume 'print'
        self.expect(TokenType.LPAREN)
        expr = self.parse_expression(0)
        self.expect(TokenType.RPAREN)
        if self.peek().type == TokenType.SEMICOLON:
            self.advance()
        return PrintStmt(expr)

    def parse_if(self):
        self.advance()  # consume 'if'
        self.expect(TokenType.LPAREN)
        condition = self.parse_expression(0)
        self.expect(TokenType.RPAREN)
        then_branch = self.parse_statement()
        else_branch = None
        if self.peek().type == TokenType.KEYWORD and self.peek().value == 'else':
            self.advance()  # consume 'else'
            else_branch = self.parse_statement()
        return IfStmt(condition, then_branch, else_branch)

    def parse_while(self):
        self.advance()  # consume 'while'
        self.expect(TokenType.LPAREN)
        condition = self.parse_expression(0)
        self.expect(TokenType.RPAREN)
        body = self.parse_statement()
        return WhileStmt(condition, body)

    def parse_block(self):
        self.advance()  # consume '{'
        statements = []
        while self.peek().type != TokenType.RBRACE and self.peek().type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        self.expect(TokenType.RBRACE)
        return Block(statements)

    def parse_function_def(self):
        self.advance()  # consume 'def'
        name_tok = self.expect(TokenType.IDENTIFIER)
        self.expect(TokenType.LPAREN)
        params = []
        if self.peek().type == TokenType.IDENTIFIER:
            params.append(self.advance().value)
            while self.peek().type == TokenType.COMMA:
                self.advance()  # consume ','
                params.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.RPAREN)
        body = self.parse_statement()
        return FunctionDef(name_tok.value, params, body)

    def parse_return(self):
        self.advance()  # consume 'return'
        expr = self.parse_expression(0)
        if self.peek().type == TokenType.SEMICOLON:
            self.advance()
        return ReturnStmt(expr)

    def parse_expression(self, min_prec):
        left = self.parse_atom()
        while True:
            tok = self.peek()
            if tok.type == TokenType.OPERATOR and tok.value in PRECEDENCE:
                prec = PRECEDENCE[tok.value]
                if prec < min_prec:
                    break
                self.advance()
                right = self.parse_expression(prec + 1)
                left = BinaryOp(left, tok.value, right)
            else:
                break
        return left

    def parse_atom(self):
        tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return NumberLiteral(tok.value)

        if tok.type == TokenType.STRING:
            self.advance()
            return StringLiteral(tok.value)

        if tok.type == TokenType.IDENTIFIER:
            self.advance()
            if self.peek().type == TokenType.LPAREN:
                self.advance()
                args = []
                if self.peek().type != TokenType.RPAREN:
                    args.append(self.parse_expression(0))
                    while self.peek().type == TokenType.COMMA:
                        self.advance()
                        args.append(self.parse_expression(0))
                self.expect(TokenType.RPAREN)
                return CallExpr(tok.value, args)
            return Identifier(tok.value)

        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression(0)
            self.expect(TokenType.RPAREN)
            return expr

        if tok.type == TokenType.OPERATOR and tok.value == '-':
            self.advance()
            expr = self.parse_atom()
            return UnaryOp('-', expr)

        raise SyntaxError(f"Unexpected token {tok.type}({tok.value}) at line {tok.line}")


# === Bytecode Compiler ===
class Compiler:
    def __init__(self, source):
        self.source = source
        self.bc = Bytecode()
        self.scopes = []
        self.functions = {}
        self.main_scope = {}

    def resolve_var(self, name):
        if self.scopes:
            scope = self.scopes[-1]
        else:
            scope = self.main_scope
        if name not in scope:
            scope[name] = len(scope)
        return scope[name]

    def compile(self):
        tokens = Lexer(self.source).tokenize()
        ast = Parser(tokens).parse()

        # First pass: register function defs
        for stmt in ast.statements:
            if isinstance(stmt, FunctionDef):
                self.functions[stmt.name] = (len(stmt.params), None)

        # Separate function defs from other statements
        func_defs = []
        other_stmts = []
        for stmt in ast.statements:
            if isinstance(stmt, FunctionDef):
                func_defs.append(stmt)
            else:
                other_stmts.append(stmt)

        # Track CALL instructions that need function addresses patched
        call_patches = []  # list of (instr_index, func_name)

        # Compile main body first (so it comes before function bodies in bytecode)
        main_start = len(self.bc)
        for stmt in other_stmts:
            self._compile_with_patches(stmt, call_patches)
        self.bc.emit(Op.HALT)

        # Compile functions after main body (CALL jumps to these addresses)
        # Strategy: compile each function and immediately patch its CALL addresses
        for func in func_defs:
            addr = len(self.bc)
            self.functions[func.name] = (len(func.params), addr)
            # Patch this function's CALL instructions
            for instr_idx, func_name in call_patches:
                if func_name == func.name:
                    packed = (len(func.params) << 20) | addr
                    self.bc.instructions[instr_idx] = (self.bc.instructions[instr_idx][0], packed)
            # Compile function body
            self.scopes.append({})
            scope = self.scopes[-1]
            for i, p in enumerate(func.params):
                scope[p] = i
            self.compile_statement(func.body)
            # Implicit return 0 if no explicit return
            if not self.bc.instructions or self.bc.instructions[-1][0] != Op.RET.value:
                self.bc.emit(Op.PUSH_CONST, self.bc.add_const_int(0))
                self.bc.emit(Op.RET)
            self.scopes.pop()

        return self.bc

    def _compile_with_patches(self, stmt, call_patches):
        """Like compile_statement but tracks CALL instructions needing address patching."""
        if isinstance(stmt, PrintStmt):
            self._compile_expr_with_patches(stmt.expr, call_patches)
            self.bc.emit(Op.PRINT)
        elif isinstance(stmt, Assign):
            var_idx = self.resolve_var(stmt.name)
            self._compile_expr_with_patches(stmt.expr, call_patches)
            self.bc.emit(Op.STORE_VAR, var_idx)
        elif isinstance(stmt, IfStmt):
            self._compile_if_with_patches(stmt, call_patches)
        elif isinstance(stmt, WhileStmt):
            self._compile_while_with_patches(stmt, call_patches)
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                self._compile_with_patches(s, call_patches)
        elif isinstance(stmt, FunctionDef):
            pass  # already handled
        elif isinstance(stmt, ReturnStmt):
            self._compile_expr_with_patches(stmt.expr, call_patches)
            self.bc.emit(Op.RET)
        elif isinstance(stmt, ExprStmt):
            self._compile_expr_with_patches(stmt.expr, call_patches)

    def _compile_if_with_patches(self, stmt, call_patches):
        self._compile_expr_with_patches(stmt.condition, call_patches)
        jmp_false_pos = len(self.bc)
        self.bc.emit(Op.JMP_IF_FALSE, 0)
        self._compile_with_patches(stmt.then_branch, call_patches)
        if stmt.else_branch:
            jmp_end_pos = len(self.bc)
            self.bc.emit(Op.JMP, 0)
            self.bc.patch_jump(jmp_false_pos)
            self._compile_with_patches(stmt.else_branch, call_patches)
            self.bc.patch_jump(jmp_end_pos)
        else:
            self.bc.patch_jump(jmp_false_pos)

    def _compile_while_with_patches(self, stmt, call_patches):
        loop_start = len(self.bc)
        self._compile_expr_with_patches(stmt.condition, call_patches)
        jmp_false_pos = len(self.bc)
        self.bc.emit(Op.JMP_IF_FALSE, 0)
        self._compile_with_patches(stmt.body, call_patches)
        self.bc.emit(Op.JMP, loop_start)
        self.bc.patch_jump(jmp_false_pos)

    def _compile_expr_with_patches(self, expr, call_patches):
        """Like compile_expression but records CALL patch info."""
        if isinstance(expr, NumberLiteral):
            idx = self.bc.add_const_int(expr.value)
            self.bc.emit(Op.PUSH_CONST, idx)
        elif isinstance(expr, StringLiteral):
            idx = self.bc.add_const_string(expr.value)
            self.bc.emit(Op.PUSH_CONST, idx)
        elif isinstance(expr, Identifier):
            var_idx = self.resolve_var(expr.name)
            self.bc.emit(Op.LOAD_VAR, var_idx)
        elif isinstance(expr, BinaryOp):
            op_map = {
                '+': Op.ADD, '-': Op.SUB, '*': Op.MUL,
                '/': Op.DIV, '%': Op.MOD,
                '==': Op.EQ, '!=': Op.NE,
                '<': Op.LT, '>': Op.GT,
                '<=': Op.LE, '>=': Op.GE,
            }
            self._compile_expr_with_patches(expr.left, call_patches)
            self._compile_expr_with_patches(expr.right, call_patches)
            self.bc.emit(op_map[expr.op])
        elif isinstance(expr, UnaryOp):
            self._compile_expr_with_patches(expr.expr, call_patches)
            if expr.op == '-':
                self.bc.emit(Op.NEG)
        elif isinstance(expr, CallExpr):
            for arg in expr.args:
                self._compile_expr_with_patches(arg, call_patches)
            name = expr.name
            nargs = None
            for fn in self.functions:
                if fn == name:
                    nargs, _ = self.functions[fn]
                    break
            if nargs is None:
                raise NameError(f"Undefined function: {name}")
            # Emit CALL with placeholder address (0), record for patching
            instr_idx = len(self.bc)
            self.bc.emit(Op.CALL, 0)
            call_patches.append((instr_idx, name))
        else:
            raise NotImplementedError(f"Unknown expression: {type(expr)}")

    def compile_statement(self, stmt):
        if isinstance(stmt, PrintStmt):
            self.compile_expression(stmt.expr)
            self.bc.emit(Op.PRINT)
        elif isinstance(stmt, Assign):
            var_idx = self.resolve_var(stmt.name)
            self.compile_expression(stmt.expr)
            self.bc.emit(Op.STORE_VAR, var_idx)
        elif isinstance(stmt, IfStmt):
            self.compile_if(stmt)
        elif isinstance(stmt, WhileStmt):
            self.compile_while(stmt)
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                self.compile_statement(s)
        elif isinstance(stmt, FunctionDef):
            pass  # already handled
        elif isinstance(stmt, ReturnStmt):
            self.compile_expression(stmt.expr)
            self.bc.emit(Op.RET)
        elif isinstance(stmt, ExprStmt):
            self.compile_expression(stmt.expr)
        else:
            raise NotImplementedError(f"Unknown statement: {type(stmt)}")

    def compile_if(self, stmt):
        self.compile_expression(stmt.condition)
        jmp_false_pos = len(self.bc)
        self.bc.emit(Op.JMP_IF_FALSE, 0)
        self.compile_statement(stmt.then_branch)
        if stmt.else_branch:
            jmp_end_pos = len(self.bc)
            self.bc.emit(Op.JMP, 0)
            self.bc.patch_jump(jmp_false_pos)
            self.compile_statement(stmt.else_branch)
            self.bc.patch_jump(jmp_end_pos)
        else:
            self.bc.patch_jump(jmp_false_pos)

    def compile_while(self, stmt):
        loop_start = len(self.bc)
        self.compile_expression(stmt.condition)
        jmp_false_pos = len(self.bc)
        self.bc.emit(Op.JMP_IF_FALSE, 0)
        self.compile_statement(stmt.body)
        self.bc.emit(Op.JMP, loop_start)
        self.bc.patch_jump(jmp_false_pos)

    def compile_expression(self, expr):
        if isinstance(expr, NumberLiteral):
            idx = self.bc.add_const_int(expr.value)
            self.bc.emit(Op.PUSH_CONST, idx)
        elif isinstance(expr, StringLiteral):
            idx = self.bc.add_const_string(expr.value)
            self.bc.emit(Op.PUSH_CONST, idx)
        elif isinstance(expr, Identifier):
            var_idx = self.resolve_var(expr.name)
            self.bc.emit(Op.LOAD_VAR, var_idx)
        elif isinstance(expr, BinaryOp):
            op_map = {
                '+': Op.ADD, '-': Op.SUB, '*': Op.MUL,
                '/': Op.DIV, '%': Op.MOD,
                '==': Op.EQ, '!=': Op.NE,
                '<': Op.LT, '>': Op.GT,
                '<=': Op.LE, '>=': Op.GE,
            }
            self.compile_expression(expr.left)
            self.compile_expression(expr.right)
            self.bc.emit(op_map[expr.op])
        elif isinstance(expr, UnaryOp):
            self.compile_expression(expr.expr)
            if expr.op == '-':
                self.bc.emit(Op.NEG)
        elif isinstance(expr, CallExpr):
            for arg in expr.args:
                self.compile_expression(arg)
            name = expr.name
            if name not in self.functions:
                raise NameError(f"Undefined function: {name}")
            nargs, addr = self.functions[name]
            if len(expr.args) != nargs:
                raise TypeError(f"Function {name} expects {nargs} args, got {len(expr.args)}")
            packed = (nargs << 20) | addr
            self.bc.emit(Op.CALL, packed)
        else:
            raise NotImplementedError(f"Unknown expression: {type(expr)}")


def compile_source(source):
    compiler = Compiler(source)
    bc = compiler.compile()
    return bc.instructions, bc.constants, bc.symbols
