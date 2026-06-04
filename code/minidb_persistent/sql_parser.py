"""SQL Parser — Lexer + recursive-descent Parser for a subset of SQL.

Supported:
  CREATE TABLE name (col TYPE, ...)
  INSERT INTO name [(cols)] VALUES (vals)
  SELECT [DISTINCT] cols FROM name [WHERE cond] [ORDER BY col [ASC|DESC]] [LIMIT n]
  UPDATE name SET col=val [, ...] [WHERE cond]
  DELETE FROM name [WHERE cond]
  BEGIN / COMMIT / ROLLBACK
  DROP TABLE name
  SHOW TABLES
"""

import re
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    OPERATOR = auto()
    PUNCTUATION = auto()
    EOF = auto()


KEYWORDS = {
    'CREATE', 'TABLE', 'INSERT', 'INTO', 'VALUES', 'SELECT', 'FROM',
    'WHERE', 'UPDATE', 'SET', 'DELETE', 'DROP', 'SHOW', 'TABLES',
    'ORDER', 'BY', 'ASC', 'DESC', 'LIMIT', 'DISTINCT', 'AND', 'OR',
    'NOT', 'IN', 'IS', 'NULL', 'LIKE', 'BETWEEN', 'EXISTS',
    'BEGIN', 'COMMIT', 'ROLLBACK', 'TRANSACTION',
    'INT', 'INTEGER', 'BIGINT', 'VARCHAR', 'TEXT', 'CHAR', 'FLOAT',
    'DOUBLE', 'BOOL', 'PRIMARY', 'KEY', 'NOT', 'NULL', 'DEFAULT',
    'TRUE', 'FALSE',
}

TOKEN_RE = re.compile(r"""
    (\d+\.\d+|\d+)       |  # number (float or int)
    ('(?:[^'\\]|\\.)*')  |  # string literal
    ("(?:[^"\\]|\\.)*")  |  # double-quoted identifier
    (==|!=|<=|>=|<>|[-+*/=<>!(){},;.])  |  # operators / punctuation
    (\w+)                |  # word (keyword or identifier)
    (\s+)                |  # whitespace (skip)
    (.)                     # any other char (skip)
""", re.VERBOSE | re.IGNORECASE)


class Token:
    __slots__ = ('type', 'value', 'line', 'col')

    def __init__(self, typ, value, line=0, col=0):
        self.type = typ
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return "Token(%s, %r)" % (self.type.name, self.value)


class Lexer:
    """SQL Lexer — tokenizes SQL text."""

    def __init__(self, text):
        self.text = text
        self.tokens = []
        self.pos = 0
        self._tokenize()

    def _tokenize(self):
        line = 1
        col = 1
        for match in TOKEN_RE.finditer(self.text):
            num, sstr, dstr, op, word, ws, other = match.groups()
            if num:
                val = int(num) if '.' not in num else float(num)
                self.tokens.append(Token(TokenType.NUMBER, val, line, col))
            elif sstr or dstr:
                raw = sstr or dstr
                val = raw[1:-1]  # strip quotes
                self.tokens.append(Token(TokenType.STRING, val, line, col))
            elif op:
                self.tokens.append(Token(TokenType.OPERATOR, op, line, col))
            elif word:
                up = word.upper()
                if up in KEYWORDS:
                    self.tokens.append(Token(TokenType.KEYWORD, up, line, col))
                else:
                    self.tokens.append(Token(TokenType.IDENTIFIER, word, line, col))
            elif ws:
                pass  # skip whitespace
            elif other:
                pass  # skip unknown

            # Update line/col roughly
            consumed = match.end() - match.start()
            text_slice = self.text[match.start():match.end()]
            newlines = text_slice.count('\n')
            if newlines:
                line += newlines
                col = len(text_slice) - text_slice.rfind('\n')
            else:
                col += consumed

        self.tokens.append(Token(TokenType.EOF, None, line, col))

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return Token(TokenType.EOF, None)

    def advance(self):
        tok = self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TokenType.EOF, None)
        self.pos += 1
        return tok

    def expect(self, *expected):
        tok = self.peek()
        for exp in expected:
            if isinstance(exp, TokenType):
                if tok.type == exp:
                    return self.advance()
            elif isinstance(exp, str):
                if tok.type == TokenType.KEYWORD and tok.value == exp.upper():
                    return self.advance()
                if tok.type == TokenType.OPERATOR and tok.value == exp:
                    return self.advance()
                if tok.type == TokenType.PUNCTUATION and tok.value == exp:
                    return self.advance()
        raise SyntaxError("Expected %s, got %s" % (expected, tok))

    def skip_semicolon(self):
        """Skip optional semicolon."""
        if self.peek().type == TokenType.OPERATOR and self.peek().value == ';':
            self.advance()


# ── AST Nodes ──────────────────────────────────────

class ASTNode:
    """Base class for AST nodes."""
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.__dict__)


class CreateTable(ASTNode):
    def __init__(self, name, columns):
        self.name = name
        self.columns = columns  # list of ColumnDef


class ColumnDef(ASTNode):
    def __init__(self, name, type_name, primary_key=False, not_null=False, default=None):
        self.name = name
        self.type_name = type_name
        self.primary_key = primary_key
        self.not_null = not_null
        self.default = default


class Insert(ASTNode):
    def __init__(self, name, columns, values):
        self.name = name
        self.columns = columns  # None or list of col names
        self.values = values  # list of values


class Select(ASTNode):
    def __init__(self, distinct=False, columns=None, from_table=None,
                 where=None, order_by=None, limit=None):
        self.distinct = distinct
        self.columns = columns  # ['*'] or list of names
        self.from_table = from_table
        self.where = where  # Condition or None
        self.order_by = order_by  # [(col, 'ASC'|'DESC'), ...] or None
        self.limit = limit  # int or None


class Update(ASTNode):
    def __init__(self, name, set_clause, where=None):
        self.name = name
        self.set_clause = set_clause  # {col: value, ...}
        self.where = where


class Delete(ASTNode):
    def __init__(self, name, where=None):
        self.name = name
        self.where = where


class DropTable(ASTNode):
    def __init__(self, name):
        self.name = name


class ShowTables(ASTNode):
    pass


class Transaction(ASTNode):
    def __init__(self, action):
        self.action = action  # 'BEGIN', 'COMMIT', 'ROLLBACK'


class Condition(ASTNode):
    def __init__(self, op, left, right=None):
        self.op = op  # 'AND', 'OR', '=', '<', '>', etc.
        self.left = left
        self.right = right

    def __repr__(self):
        return "Condition(%s %s %s)" % (self.left, self.op, self.right)


# ── Parser ─────────────────────────────────────────

class Parser:
    """Recursive-descent SQL parser."""

    def __init__(self, lexer):
        self.lexer = lexer

    def parse(self):
        stmt = self._parse_statement()
        self.lexer.skip_semicolon()
        return stmt

    def _parse_statement(self):
        tok = self.lexer.peek()
        if tok.type == TokenType.EOF:
            return None

        if tok.type == TokenType.KEYWORD:
            kw = tok.value
            if kw == 'CREATE':
                return self._parse_create()
            elif kw == 'INSERT':
                return self._parse_insert()
            elif kw == 'SELECT':
                return self._parse_select()
            elif kw == 'UPDATE':
                return self._parse_update()
            elif kw == 'DELETE':
                return self._parse_delete()
            elif kw == 'DROP':
                return self._parse_drop()
            elif kw == 'SHOW':
                return self._parse_show()
            elif kw == 'BEGIN':
                self.lexer.advance()
                # Skip optional TRANSACTION / WORK
                if self.lexer.peek().type == TokenType.KEYWORD and \
                   self.lexer.peek().value in ('TRANSACTION', 'WORK'):
                    self.lexer.advance()
                return Transaction('BEGIN')
            elif kw == 'COMMIT':
                self.lexer.advance()
                if self.lexer.peek().type == TokenType.KEYWORD and \
                   self.lexer.peek().value in ('TRANSACTION', 'WORK'):
                    self.lexer.advance()
                return Transaction('COMMIT')
            elif kw == 'ROLLBACK':
                self.lexer.advance()
                if self.lexer.peek().type == TokenType.KEYWORD and \
                   self.lexer.peek().value in ('TRANSACTION', 'WORK'):
                    self.lexer.advance()
                return Transaction('ROLLBACK')

        raise SyntaxError("Unexpected token: %s" % tok)

    # ── CREATE TABLE ────────────────────────────────

    def _parse_create(self):
        self.lexer.expect('CREATE')
        self.lexer.expect('TABLE')
        name = self.lexer.expect(TokenType.IDENTIFIER).value
        self.lexer.expect('(')
        columns = []
        while True:
            col = self._parse_column_def()
            columns.append(col)
            tok = self.lexer.peek()
            if tok.type == TokenType.OPERATOR and tok.value == ',':
                self.lexer.advance()
                continue
            break
        self.lexer.expect(')')
        return CreateTable(name.upper(), columns)

    def _parse_column_def(self):
        name = self.lexer.expect(TokenType.IDENTIFIER).value
        type_tok = self.lexer.expect(TokenType.KEYWORD)
        type_name = type_tok.value.upper()

        primary_key = False
        not_null = False
        default = None

        # Extended type: e.g., VARCHAR(255) — just consume the (255)
        if self.lexer.peek().type == TokenType.OPERATOR and self.lexer.peek().value == '(':
            self.lexer.advance()
            self.lexer.expect(TokenType.NUMBER)
            self.lexer.expect(')')

        while True:
            tok = self.lexer.peek()
            if tok.type == TokenType.KEYWORD:
                if tok.value == 'PRIMARY':
                    self.lexer.advance()
                    self.lexer.expect('KEY')
                    primary_key = True
                elif tok.value == 'NOT':
                    self.lexer.advance()
                    self.lexer.expect('NULL')
                    not_null = True
                elif tok.value == 'DEFAULT':
                    self.lexer.advance()
                    if self.lexer.peek().type == TokenType.STRING:
                        default = self.lexer.advance().value
                    elif self.lexer.peek().type == TokenType.NUMBER:
                        default = self.lexer.advance().value
                    elif self.lexer.peek().type == TokenType.KEYWORD and \
                         self.lexer.peek().value == 'NULL':
                        self.lexer.advance()
                        default = None
                    else:
                        raise SyntaxError("Expected value after DEFAULT")
                else:
                    break
            else:
                break

        return ColumnDef(name, type_name, primary_key, not_null, default)

    # ── INSERT ──────────────────────────────────────

    def _parse_insert(self):
        self.lexer.expect('INSERT')
        self.lexer.expect('INTO')
        name = self.lexer.expect(TokenType.IDENTIFIER).value

        columns = None
        if self.lexer.peek().type == TokenType.OPERATOR and self.lexer.peek().value == '(':
            self.lexer.advance()
            columns = [self.lexer.expect(TokenType.IDENTIFIER).value]
            while self.lexer.peek().type == TokenType.OPERATOR and \
                  self.lexer.peek().value == ',':
                self.lexer.advance()
                columns.append(self.lexer.expect(TokenType.IDENTIFIER).value)
            self.lexer.expect(')')

        self.lexer.expect('VALUES')
        self.lexer.expect('(')
        values = []
        values.append(self._parse_value())
        while self.lexer.peek().type == TokenType.OPERATOR and \
              self.lexer.peek().value == ',':
            self.lexer.advance()
            values.append(self._parse_value())
        self.lexer.expect(')')

        return Insert(name.upper(), columns, values)

    def _parse_value(self):
        tok = self.lexer.peek()
        if tok.type == TokenType.NUMBER:
            return self.lexer.advance().value
        elif tok.type == TokenType.STRING:
            return self.lexer.advance().value
        elif tok.type == TokenType.KEYWORD and tok.value == 'NULL':
            self.lexer.advance()
            return None
        elif tok.type == TokenType.KEYWORD and tok.value in ('TRUE', 'FALSE'):
            v = self.lexer.advance().value
            return True if v == 'TRUE' else False
        else:
            # Identifier (column ref)
            return self.lexer.expect(TokenType.IDENTIFIER).value

    # ── SELECT ──────────────────────────────────────

    def _parse_select(self):
        self.lexer.expect('SELECT')
        distinct = False
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'DISTINCT':
            self.lexer.advance()
            distinct = True

        columns = self._parse_column_list()
        self.lexer.expect('FROM')
        from_table = self.lexer.expect(TokenType.IDENTIFIER).value

        where = None
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'WHERE':
            self.lexer.advance()
            where = self._parse_condition()

        order_by = None
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'ORDER':
            self.lexer.advance()
            self.lexer.expect('BY')
            order_by = []
            while True:
                col = self.lexer.expect(TokenType.IDENTIFIER).value
                direction = 'ASC'
                if self.lexer.peek().type == TokenType.KEYWORD:
                    if self.lexer.peek().value == 'ASC':
                        self.lexer.advance()
                    elif self.lexer.peek().value == 'DESC':
                        self.lexer.advance()
                        direction = 'DESC'
                order_by.append((col, direction))
                if self.lexer.peek().type == TokenType.OPERATOR and \
                   self.lexer.peek().value == ',':
                    self.lexer.advance()
                else:
                    break

        limit = None
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'LIMIT':
            self.lexer.advance()
            limit = self.lexer.expect(TokenType.NUMBER).value

        return Select(distinct, columns, from_table.upper(), where, order_by, limit)

    def _parse_column_list(self):
        tok = self.lexer.peek()
        if tok.type == TokenType.OPERATOR and tok.value == '*':
            self.lexer.advance()
            return ['*']
        cols = [self.lexer.expect(TokenType.IDENTIFIER).value]
        while self.lexer.peek().type == TokenType.OPERATOR and \
              self.lexer.peek().value == ',':
            self.lexer.advance()
            cols.append(self.lexer.expect(TokenType.IDENTIFIER).value)
        return cols

    # ── Condition parser ───────────────────────────

    def _parse_condition(self):
        """Parse a condition expression (AND/OR supported)."""
        left = self._parse_simple_condition()
        tok = self.lexer.peek()
        while tok.type == TokenType.KEYWORD and tok.value in ('AND', 'OR'):
            self.lexer.advance()
            op = tok.value
            right = self._parse_simple_condition()
            left = Condition(op, left, right)
            tok = self.lexer.peek()
        return left

    def _parse_simple_condition(self):
        """Parse a simple condition: expr OP expr or expr IS [NOT] NULL."""
        tok = self.lexer.peek()

        # NOT <condition>
        if tok.type == TokenType.KEYWORD and tok.value == 'NOT':
            self.lexer.advance()
            inner = self._parse_simple_condition()
            return Condition('NOT', inner)

        # expr OP expr
        left = self._parse_expr()

        tok = self.lexer.peek()
        if tok.type == TokenType.KEYWORD:
            if tok.value == 'IS':
                self.lexer.advance()
                negate = False
                if self.lexer.peek().type == TokenType.KEYWORD and \
                   self.lexer.peek().value == 'NOT':
                    self.lexer.advance()
                    negate = True
                self.lexer.expect('NULL')
                op = 'IS NOT' if negate else 'IS'
                return Condition(op, left)
            elif tok.value == 'IN':
                self.lexer.advance()
                self.lexer.expect('(')
                values = []
                values.append(self._parse_value())
                while self.lexer.peek().type == TokenType.OPERATOR and \
                      self.lexer.peek().value == ',':
                    self.lexer.advance()
                    values.append(self._parse_value())
                self.lexer.expect(')')
                return Condition('IN', left, values)
            elif tok.value == 'LIKE':
                self.lexer.advance()
                right = self._parse_value()
                return Condition('LIKE', left, right)
            elif tok.value == 'BETWEEN':
                self.lexer.advance()
                low = self._parse_value()
                self.lexer.expect('AND')
                high = self._parse_value()
                return Condition('BETWEEN', left, (low, high))
            else:
                return left

        elif tok.type == TokenType.OPERATOR:
            op = tok.value
            if op in ('=', '!=', '<>', '<', '>', '<=', '>='):
                self.lexer.advance()
                right = self._parse_expr()
                op_sql = '=' if op == '=' else op
                return Condition(op_sql, left, right)

        # Single expression
        return left

    def _parse_expr(self):
        """Parse an expression: column name, literal, or number."""
        tok = self.lexer.peek()
        if tok.type == TokenType.NUMBER:
            return self.lexer.advance().value
        elif tok.type == TokenType.STRING:
            return self.lexer.advance().value
        elif tok.type == TokenType.IDENTIFIER:
            return self.lexer.advance().value
        elif tok.type == TokenType.KEYWORD and tok.value == 'NULL':
            self.lexer.advance()
            return None
        elif tok.type == TokenType.KEYWORD and tok.value in ('TRUE', 'FALSE'):
            v = self.lexer.advance().value
            return True if v == 'TRUE' else False
        elif tok.type == TokenType.OPERATOR and tok.value == '(':
            self.lexer.advance()
            cond = self._parse_condition()
            self.lexer.expect(')')
            return cond
        raise SyntaxError("Expected expression, got %s" % tok)

    # ── UPDATE ──────────────────────────────────────

    def _parse_update(self):
        self.lexer.expect('UPDATE')
        name = self.lexer.expect(TokenType.IDENTIFIER).value
        self.lexer.expect('SET')
        set_clause = {}
        while True:
            col = self.lexer.expect(TokenType.IDENTIFIER).value
            self.lexer.expect('=')
            val = self._parse_value()
            set_clause[col] = val
            if self.lexer.peek().type == TokenType.OPERATOR and \
               self.lexer.peek().value == ',':
                self.lexer.advance()
            else:
                break

        where = None
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'WHERE':
            self.lexer.advance()
            where = self._parse_condition()

        return Update(name.upper(), set_clause, where)

    # ── DELETE ──────────────────────────────────────

    def _parse_delete(self):
        self.lexer.expect('DELETE')
        self.lexer.expect('FROM')
        name = self.lexer.expect(TokenType.IDENTIFIER).value

        where = None
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'WHERE':
            self.lexer.advance()
            where = self._parse_condition()

        return Delete(name.upper(), where)

    # ── DROP TABLE ──────────────────────────────────

    def _parse_drop(self):
        self.lexer.expect('DROP')
        self.lexer.expect('TABLE')
        name = self.lexer.expect(TokenType.IDENTIFIER).value
        return DropTable(name.upper())

    # ── SHOW TABLES ─────────────────────────────────

    def _parse_show(self):
        self.lexer.expect('SHOW')
        if self.lexer.peek().type == TokenType.KEYWORD and \
           self.lexer.peek().value == 'TABLES':
            self.lexer.advance()
            return ShowTables()
        raise SyntaxError("Expected TABLES after SHOW")


# ── Convenience ────────────────────────────────────

def parse_sql(sql):
    """Parse a single SQL statement and return an AST node."""
    lexer = Lexer(sql)
    parser = Parser(lexer)
    return parser.parse()


def parse_sql_multi(sql):
    """Parse multiple SQL statements (separated by semicolons)."""
    statements = []
    for stmt_text in sql.split(';'):
        stmt_text = stmt_text.strip()
        if not stmt_text:
            continue
        lexer = Lexer(stmt_text)
        parser = Parser(lexer)
        ast = parser.parse()
        if ast is not None:
            statements.append(ast)
    return statements
