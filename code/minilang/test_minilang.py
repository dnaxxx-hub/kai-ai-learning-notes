import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from lexer import Lexer
from parser import Parser
from evaluator import Evaluator
from nodes import VarDecl, If, While, FunctionDef


def run(source):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    eval = Evaluator()
    return eval.evaluate(ast)


class TestLexer(unittest.TestCase):
    def test_numbers(self):
        tokens = Lexer("123 45.6").tokenize()
        self.assertEqual(tokens[0].type, 'NUMBER')
        self.assertEqual(tokens[0].value, 123)
        self.assertEqual(tokens[1].value, 45.6)

    def test_strings(self):
        tokens = Lexer('"hello"').tokenize()
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, 'hello')

    def test_identifiers(self):
        tokens = Lexer('x abc _test').tokenize()
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'x')

    def test_operators(self):
        tokens = Lexer('+ - * / == != <= >=').tokenize()
        types = ['OPERATOR'] * 8
        self.assertEqual([t.type for t in tokens if t.type != 'EOF'], types)

    def test_keywords(self):
        tokens = Lexer('let if else while fn return true false nil print').tokenize()
        for t in tokens:
            if t.type == 'EOF':
                break
            self.assertEqual(t.type, 'KEYWORD')


class TestParser(unittest.TestCase):
    def test_var_decl(self):
        tokens = Lexer("let x = 42;").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], VarDecl)

    def test_arithmetic(self):
        tokens = Lexer("let x = 1 + 2 * 3;").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], VarDecl)

    def test_comparison(self):
        tokens = Lexer("let x = 5 > 3;").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], VarDecl)

    def test_if(self):
        tokens = Lexer("if (true) { let x = 1; }").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], If)

    def test_while(self):
        tokens = Lexer("while (false) { let x = 1; }").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], While)

    def test_function(self):
        tokens = Lexer("fn add(a, b) { return a + b; }").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.assertTrue(len(ast.statements) > 0)
        self.assertIsInstance(ast.statements[0], FunctionDef)


class TestEvaluator(unittest.TestCase):
    def test_arithmetic(self):
        result = run("let x = 5 + 3; x;")
        self.assertEqual(result, 8)

    def test_var_decl_and_use(self):
        tokens = Lexer("let x = 10; x;").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        result = Evaluator().evaluate(ast)
        self.assertEqual(result, 10)

    def test_if_true(self):
        result = run("""
fn test() {
    if (true) {
        return 42;
    }
    return 0;
}
test();
""")
        self.assertEqual(result, 42)

    def test_function_call(self):
        result = run("""
fn add(a, b) {
    return a + b;
}
add(3, 4);
""")
        self.assertEqual(result, 7)

    def test_string_concat(self):
        result = run('"hello" + " " + "world";')
        self.assertEqual(result, "hello world")

    def test_list(self):
        result = run("[1, 2, 3];")
        self.assertEqual(result, [1, 2, 3])

    def test_while(self):
        result = run("""
let i = 0;
let sum = 0;
while (i < 10) {
    sum = sum + i;
    i = i + 1;
}
sum;
""")
        self.assertEqual(result, 45)  # 0+1+...+9 = 45

    def test_nested_function(self):
        result = run("""
fn outer(x) {
    fn inner(y) {
        return x + y;
    }
    return inner(x * 2);
}
outer(5);
""")
        self.assertEqual(result, 15)  # inner(10) = 5 + 10

    def test_recursion(self):
        result = run("""
fn factorial(n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
factorial(5);
""")
        self.assertEqual(result, 120)

    def test_fibonacci(self):
        result = run("""
fn fib(n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}
fib(10);
""")
        self.assertEqual(result, 55)

    def test_builtin_len(self):
        result = run('len([1, 2, 3, 4, 5]);')
        self.assertEqual(result, 5)

    def test_builtin_range(self):
        result = run('range(5);')
        self.assertEqual(result, [0, 1, 2, 3, 4])

    def test_nil(self):
        result = run('nil;')
        self.assertIsNone(result)


class TestDatabase(unittest.TestCase):
    def test_db_create_and_insert(self):
        """创建表并插入"""
        result = run("""
let conn = db_open(":memory:");
db_exec(conn, "CREATE TABLE users (id INT, name TEXT, age INT)");
db_exec(conn, "INSERT INTO users VALUES (1, 'Alice', 30)");
db_exec(conn, "INSERT INTO users VALUES (2, 'Bob', 25)");
db_exec(conn, "INSERT INTO users VALUES (3, 'Charlie', 35)");
let rows = db_query(conn, "SELECT count(*) FROM users");
db_close(conn);
rows[0][0];
""")
        self.assertEqual(result, 3)

    def test_db_query(self):
        """查询并读取结果"""
        result = run("""
let conn = db_open(":memory:");
db_exec(conn, "CREATE TABLE items (id INT, name TEXT, price REAL)");
db_exec(conn, "INSERT INTO items VALUES (1, 'apple', 1.5)");
db_exec(conn, "INSERT INTO items VALUES (2, 'banana', 2.0)");
db_exec(conn, "INSERT INTO items VALUES (3, 'cherry', 3.0)");
let rows = db_query(conn, "SELECT name, price FROM items WHERE price > 1.5");
db_close(conn);
rows;
""")
        # 应该有 2 行: banana (2.0), cherry (3.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], 'banana')

    def test_db_update(self):
        """更新并验证"""
        result = run("""
let conn = db_open(":memory:");
db_exec(conn, "CREATE TABLE scores (id INT, score INT)");
db_exec(conn, "INSERT INTO scores VALUES (1, 80)");
db_exec(conn, "INSERT INTO scores VALUES (2, 90)");
let affected = db_exec(conn, "UPDATE scores SET score = 100 WHERE id = 1");
let rows = db_query(conn, "SELECT score FROM scores WHERE id = 1");
db_close(conn);
rows[0][0];
""")
        self.assertEqual(result, 100)

    def test_db_delete(self):
        """删除并验证"""
        result = run("""
let conn = db_open(":memory:");
db_exec(conn, "CREATE TABLE test (id INT)");
db_exec(conn, "INSERT INTO test VALUES (1)");
db_exec(conn, "INSERT INTO test VALUES (2)");
db_exec(conn, "DELETE FROM test WHERE id = 2");
let rows = db_query(conn, "SELECT count(*) FROM test");
db_close(conn);
rows[0][0];
""")
        self.assertEqual(result, 1)

    def test_db_multiple_connections(self):
        """多个连接"""
        result = run("""
let c1 = db_open(":memory:");
let c2 = db_open(":memory:");
db_exec(c1, "CREATE TABLE t1 (v INT)");
db_exec(c2, "CREATE TABLE t2 (v INT)");
db_exec(c1, "INSERT INTO t1 VALUES (10)");
db_exec(c2, "INSERT INTO t2 VALUES (20)");
let r1 = db_query(c1, "SELECT v FROM t1");
let r2 = db_query(c2, "SELECT v FROM t2");
db_close(c1);
db_close(c2);
r1[0][0] + r2[0][0];
""")
        self.assertEqual(result, 30)

    def test_db_file_persistence(self):
        """文件数据库持久化"""
        import tempfile
        db_path = os.path.join(tempfile.gettempdir(), "_minilang_test.db")

        # 先删除旧文件
        try:
            os.remove(db_path)
        except:
            pass

        source1 = f'let conn = db_open("{db_path}"); db_exec(conn, "CREATE TABLE t (x INT)"); db_exec(conn, "INSERT INTO t VALUES (42)"); db_close(conn);'
        run(source1)

        source2 = f'let conn = db_open("{db_path}"); let r = db_query(conn, "SELECT x FROM t"); db_close(conn); r[0][0];'
        result = run(source2)

        try:
            os.remove(db_path)
        except:
            pass

        self.assertEqual(result, 42)

    def test_db_error_handling(self):
        """错误处理"""
        with self.assertRaises(Exception):
            run("db_query(-1, 'SELECT 1');")

    def test_db_invalid_sql(self):
        """非法 SQL"""
        with self.assertRaises(Exception):
            run("""
let conn = db_open(":memory:");
db_exec(conn, "INVALID SQL");
db_close(conn);
""")


if __name__ == '__main__':
    unittest.main()
