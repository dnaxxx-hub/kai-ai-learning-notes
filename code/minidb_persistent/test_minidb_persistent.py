"""MiniDB Persistent — Comprehensive test suite.

Run with: python -m pytest projects/minidb_persistent/ -v
"""

import os
import sys
import shutil
import pytest

# Ensure project is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from btree import BPlusTree, BPlusTreeNode, PAGE_SIZE
from wal import WAL, WALRecord, RECORD_HEADER_SIZE
from sql_parser import Lexer, Parser, parse_sql, parse_sql_multi
from storage import (
    StorageEngine, Column, TableSchema, Table,
    DATA_DIR, TYPE_MAP, coerce_value,
)
from engine import MiniDBEngine

# ── Fixtures ──────────────────────────────────────

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


@pytest.fixture(autouse=True)
def cleanup_data():
    """Clean up test data before and after each test."""
    # Clean before
    _clean_data_dir()
    yield
    # Clean after
    _clean_data_dir()


def _clean_data_dir():
    if os.path.exists(TEST_DATA_DIR):
        for f in os.listdir(TEST_DATA_DIR):
            fpath = os.path.join(TEST_DATA_DIR, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except PermissionError:
                pass


# ══════════════════════════════════════════════════
# 1. B+Tree Core Tests
# ══════════════════════════════════════════════════

class TestBPlusTreeNode:
    def test_node_creation(self):
        node = BPlusTreeNode(is_leaf=True)
        assert node.is_leaf
        assert node.keys == []
        assert node.children == []
        assert node.next is None
        assert node.parent is None

    def test_internal_node_creation(self):
        node = BPlusTreeNode(is_leaf=False)
        assert not node.is_leaf


class TestBPlusTreeInsertAndSearch:
    @pytest.fixture
    def tree(self):
        return BPlusTree(order=4)

    def test_insert_and_search(self, tree):
        tree.insert(10, 'ten')
        tree.insert(20, 'twenty')
        tree.insert(5, 'five')
        assert tree.search(10) == 'ten'
        assert tree.search(20) == 'twenty'
        assert tree.search(5) == 'five'
        assert tree.search(99) is None

    def test_insert_and_search_many(self, tree):
        for i in range(100):
            tree.insert(i, f'val-{i}')
        for i in range(100):
            assert tree.search(i) == f'val-{i}'
        assert tree.search(200) is None


class TestBPlusTreeUpdate:
    @pytest.fixture
    def tree(self):
        return BPlusTree(order=4)

    def test_update_value(self, tree):
        tree.insert(10, 'ten')
        assert tree.search(10) == 'ten'
        tree.insert(10, 'TEN')
        assert tree.search(10) == 'TEN'

    def test_multiple_updates(self, tree):
        tree.insert(1, 'a')
        tree.insert(1, 'b')
        tree.insert(1, 'c')
        assert tree.search(1) == 'c'


class TestBPlusTreeDelete:
    @pytest.fixture
    def tree(self):
        return BPlusTree(order=4)

    def test_delete_simple(self, tree):
        tree.insert(10, 'ten')
        assert tree.search(10) == 'ten'
        result = tree.delete(10)
        assert result
        assert tree.search(10) is None

    def test_delete_nonexistent(self, tree):
        result = tree.delete(99)
        assert not result

    def test_delete_from_many(self, tree):
        for i in range(20):
            tree.insert(i, f'val-{i}')
        for i in range(10):
            tree.delete(i)
        for i in range(10):
            assert tree.search(i) is None
        for i in range(10, 20):
            assert tree.search(i) == f'val-{i}'

    def test_delete_all(self, tree):
        for i in range(10):
            tree.insert(i, f'val-{i}')
        for i in range(10):
            tree.delete(i)
        assert tree.search(0) is None
        assert tree.search(9) is None
        assert tree.root.is_leaf


class TestRangeQuery:
    @pytest.fixture
    def tree(self):
        return BPlusTree(order=4)

    def test_range_query(self, tree):
        for i in range(0, 100, 10):
            tree.insert(i, f'val-{i}')
        results = tree.range_query(20, 60)
        assert len(results) == 4
        assert results == [(20, 'val-20'), (30, 'val-30'), (40, 'val-40'), (50, 'val-50')]

    def test_range_query_all(self, tree):
        for i in range(10):
            tree.insert(i, f'val-{i}')
        results = tree.range_query(0)
        assert len(results) == 10

    def test_range_query_empty(self, tree):
        results = tree.range_query(0, 100)
        assert results == []


class TestBalance:
    def check_invariant(self, tree, node=None):
        if node is None:
            node = tree.root
        if node is not tree.root:
            assert len(node.keys) >= tree.min_keys, \
                "Non-root node %s keys %d < min %d" % (node, len(node.keys), tree.min_keys)
        assert len(node.keys) <= tree.max_keys, \
            "Node %s keys %d > max %d" % (node, len(node.keys), tree.max_keys)
        if not node.is_leaf:
            assert len(node.children) == len(node.keys) + 1
            for child in node.children:
                self.check_invariant(tree, child)

    def test_balance_after_inserts(self):
        tree = BPlusTree(order=4)
        for i in range(100):
            tree.insert(i, f'val-{i}')
        self.check_invariant(tree)

    def test_balance_after_delete(self):
        tree = BPlusTree(order=4)
        for i in range(20):
            tree.insert(i, f'val-{i}')
        for i in range(5, 15):
            tree.delete(i)
        self.check_invariant(tree)


class TestBTreeSerialization:
    def test_to_from_dict(self):
        tree = BPlusTree(order=4)
        for i in range(50):
            tree.insert(i, f'val-{i}')

        d = tree.to_dict()
        tree2 = BPlusTree.from_dict(d)
        for i in range(50):
            assert tree2.search(i) == f'val-{i}', "Mismatch at key %d" % i
        assert tree2.search(100) is None

    def test_serialization_after_delete(self):
        tree = BPlusTree(order=4)
        for i in range(20):
            tree.insert(i, f'val-{i}')
        tree.delete(5)
        tree.delete(10)
        tree.delete(15)

        d = tree.to_dict()
        tree2 = BPlusTree.from_dict(d)
        for i in range(20):
            if i in (5, 10, 15):
                assert tree2.search(i) is None
            else:
                assert tree2.search(i) == f'val-{i}'

    def test_binary_serialization(self):
        tree = BPlusTree(order=4)
        for i in range(50):
            tree.insert(i, f'val-{i}')

        pages = tree.serialize_to_pages()
        pages_dict = {pid: data for pid, data in pages}

        tree2 = BPlusTree.deserialize_from_pages(pages_dict)
        for i in range(50):
            assert tree2.search(i) == f'val-{i}'
        assert tree2.search(100) is None


# ══════════════════════════════════════════════════
# 2. WAL Tests
# ══════════════════════════════════════════════════

class TestWAL:
    @pytest.fixture
    def wal_path(self):
        return os.path.join(TEST_DATA_DIR, 'test.wal')

    @pytest.fixture
    def wal(self, wal_path):
        w = WAL(wal_path)
        yield w
        w.close()
        if os.path.exists(wal_path):
            os.remove(wal_path)

    def test_begin_commit(self, wal):
        wal.begin(1)
        wal.commit(1)
        committed, uncommitted, schemas, actions = wal.replay()
        assert len(committed) == 1
        assert committed[0][0] == 1

    def test_begin_rollback(self, wal):
        wal.begin(1)
        wal.log_insert(1, 'USERS', 42, {'name': 'Alice', 'age': 30})
        wal.rollback(1)
        committed, uncommitted, schemas, actions = wal.replay()
        # Rolled back transactions should not appear in committed
        assert len(committed) == 0

    def test_insert_replay(self, wal):
        wal.begin(1)
        wal.log_insert(1, 'USERS', 42, {'name': 'Alice'})
        wal.commit(1)
        committed, uncommitted, schemas, actions = wal.replay()
        assert len(actions) == 1
        assert actions[0] == ('insert', 'USERS', 42, {'name': 'Alice'})

    def test_delete_replay(self, wal):
        wal.begin(1)
        wal.log_delete(1, 'USERS', 42)
        wal.commit(1)
        committed, uncommitted, schemas, actions = wal.replay()
        assert len(actions) == 1
        assert actions[0] == ('delete', 'USERS', 42)

    def test_update_replay(self, wal):
        wal.begin(1)
        wal.log_update(1, 'USERS', 42, {'name': 'Bob'})
        wal.commit(1)
        committed, uncommitted, schemas, actions = wal.replay()
        assert len(actions) == 1
        assert actions[0] == ('update', 'USERS', 42, {'name': 'Bob'})

    def test_table_schema_replay(self, wal):
        wal.begin(1)
        wal.log_table_schema(1, 'USERS', [{'name': 'id', 'type': 'INT'}])
        wal.commit(1)
        committed, uncommitted, schemas, actions = wal.replay()
        assert 'USERS' in schemas
        assert schemas['USERS'][0]['name'] == 'id'

    def test_checkpoint_truncation(self, wal):
        wal.begin(1)
        wal.log_insert(1, 'T', 1, {'v': 'a'})
        wal.commit(1)
        wal.log_checkpoint()
        wal.truncate()

        # After truncation, WAL should be empty
        committed, uncommitted, schemas, actions = wal.replay()
        assert len(actions) == 0

    def test_mixed_transactions(self, wal):
        # Txn 1: inserts key 1
        wal.begin(1)
        wal.log_insert(1, 'T', 1, {'v': 'a'})
        wal.commit(1)
        # Txn 2: rolled back
        wal.begin(2)
        wal.log_insert(2, 'T', 2, {'v': 'b'})
        wal.rollback(2)
        # Txn 3: commits key 3
        wal.begin(3)
        wal.log_insert(3, 'T', 3, {'v': 'c'})
        wal.commit(3)

        committed, uncommitted, schemas, actions = wal.replay()
        # Only txn 1 and 3 should be committed
        txn_ids = [t[0] for t in committed]
        assert 1 in txn_ids
        assert 2 not in txn_ids
        assert 3 in txn_ids


class TestWALRecordEncoding:
    def test_roundtrip(self):
        rec = WALRecord(1, 0x10, b'hello')
        raw = rec.encode()
        decoded, consumed = WALRecord.decode(raw)
        assert decoded is not None
        assert decoded.txn_id == 1
        assert decoded.type == 0x10
        assert decoded.data == b'hello'
        assert consumed == len(raw)

    def test_corrupted_magic(self):
        rec = WALRecord(1, 0x10, b'test')
        raw = bytearray(rec.encode())
        raw[0] = 0xFF  # Corrupt magic
        decoded, consumed = WALRecord.decode(bytes(raw))
        assert decoded is None


# ══════════════════════════════════════════════════
# 3. SQL Parser Tests
# ══════════════════════════════════════════════════

class TestLexer:
    def test_simple_select(self):
        lex = Lexer("SELECT * FROM users")
        tokens = lex.tokens
        assert tokens[0].value == 'SELECT'
        assert tokens[1].value == '*'
        assert tokens[2].value == 'FROM'
        assert tokens[3].value == 'users'
        assert tokens[-1].type.name == 'EOF'

    def test_number_and_string(self):
        lex = Lexer("INSERT INTO t VALUES (42, 'hello')")
        tokens = lex.tokens
        vals = [t.value for t in tokens if t.type.name != 'EOF']
        assert 42 in vals
        assert 'hello' in vals

    def test_create_table(self):
        lex = Lexer("CREATE TABLE users (id INT, name VARCHAR(100))")
        tokens = lex.tokens
        keywords = [t.value for t in tokens if t.type.name == 'KEYWORD']
        assert 'CREATE' in keywords
        assert 'TABLE' in keywords
        assert 'INT' in keywords
        assert 'VARCHAR' in keywords


class TestParser:
    def test_parse_create(self):
        ast = parse_sql("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR, age INT)")
        from sql_parser import CreateTable
        assert isinstance(ast, CreateTable)
        assert ast.name == 'USERS'
        assert len(ast.columns) == 3

    def test_parse_insert(self):
        ast = parse_sql("INSERT INTO users VALUES (1, 'Alice', 30)")
        from sql_parser import Insert
        assert isinstance(ast, Insert)
        assert ast.name == 'USERS'
        assert ast.values == [1, 'Alice', 30]

    def test_parse_select_simple(self):
        ast = parse_sql("SELECT * FROM users")
        from sql_parser import Select
        assert isinstance(ast, Select)
        assert ast.columns == ['*']
        assert ast.from_table == 'USERS'

    def test_parse_select_where(self):
        ast = parse_sql("SELECT name, age FROM users WHERE age > 28")
        from sql_parser import Select, Condition
        assert isinstance(ast, Select)
        assert ast.columns == ['name', 'age']
        assert ast.where is not None
        assert ast.where.op == '>'
        assert ast.where.left == 'age'
        assert ast.where.right == 28

    def test_parse_select_order_by(self):
        ast = parse_sql("SELECT * FROM users ORDER BY age DESC")
        assert ast.order_by is not None
        assert ast.order_by[0] == ('age', 'DESC')

    def test_parse_select_limit(self):
        ast = parse_sql("SELECT * FROM users LIMIT 10")
        assert ast.limit == 10

    def test_parse_select_distinct(self):
        ast = parse_sql("SELECT DISTINCT city FROM users")
        assert ast.distinct

    def test_parse_update(self):
        ast = parse_sql("UPDATE users SET age = 31 WHERE name = 'Alice'")
        from sql_parser import Update
        assert isinstance(ast, Update)
        assert ast.name == 'USERS'
        assert ast.set_clause == {'age': 31}

    def test_parse_delete(self):
        ast = parse_sql("DELETE FROM users WHERE id = 1")
        from sql_parser import Delete
        assert isinstance(ast, Delete)
        assert ast.name == 'USERS'

    def test_parse_drop(self):
        ast = parse_sql("DROP TABLE users")
        from sql_parser import DropTable
        assert isinstance(ast, DropTable)
        assert ast.name == 'USERS'

    def test_parse_show_tables(self):
        ast = parse_sql("SHOW TABLES")
        from sql_parser import ShowTables
        assert isinstance(ast, ShowTables)

    def test_parse_begin_commit(self):
        ast = parse_sql("BEGIN")
        from sql_parser import Transaction
        assert isinstance(ast, Transaction)
        assert ast.action == 'BEGIN'

        ast = parse_sql("COMMIT")
        assert isinstance(ast, Transaction)
        assert ast.action == 'COMMIT'

        ast = parse_sql("ROLLBACK")
        assert isinstance(ast, Transaction)
        assert ast.action == 'ROLLBACK'

    def test_parse_and_condition(self):
        ast = parse_sql("SELECT * FROM t WHERE age > 25 AND city = 'NYC'")
        assert ast.where is not None
        assert ast.where.op == 'AND'

    def test_parse_or_condition(self):
        ast = parse_sql("SELECT * FROM t WHERE age < 20 OR age > 60")
        assert ast.where.op == 'OR'

    def test_multi_statement(self):
        sql = "INSERT INTO t VALUES (1); INSERT INTO t VALUES (2);"
        stmts = parse_sql_multi(sql)
        assert len(stmts) == 2
        from sql_parser import Insert
        assert isinstance(stmts[0], Insert)
        assert isinstance(stmts[1], Insert)


# ══════════════════════════════════════════════════
# 4. Storage Engine Tests
# ══════════════════════════════════════════════════

class TestStorageEngine:
    def test_create_table(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR'),
                Column('age', 'INT')]
        engine.create_table('USERS', cols)
        assert 'USERS' in engine.list_tables()

    def test_insert_and_get(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]
        engine.create_table('USERS', cols)
        engine.insert('USERS', {'id': 1, 'name': 'Alice'})
        row = engine.get('USERS', 1)
        assert row is not None
        assert row['name'] == 'Alice'

    def test_insert_update_get(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]
        engine.create_table('USERS', cols)
        engine.insert('USERS', {'id': 1, 'name': 'Alice'})
        engine.update('USERS', 1, {'name': 'Bob'})
        row = engine.get('USERS', 1)
        assert row['name'] == 'Bob'

    def test_insert_delete(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]
        engine.create_table('USERS', cols)
        engine.insert('USERS', {'id': 1, 'name': 'Alice'})
        assert engine.get('USERS', 1) is not None
        engine.delete('USERS', 1)
        assert engine.get('USERS', 1) is None

    def test_drop_table(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True)]
        engine.create_table('T', cols)
        assert 'T' in engine.list_tables()
        engine.drop_table('T')
        assert 'T' not in engine.list_tables()

    def test_all_rows(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('val', 'VARCHAR')]
        engine.create_table('T', cols)
        for i in range(10):
            engine.insert('T', {'id': i, 'val': 'val-%d' % i})
        rows = engine.all_rows('T')
        assert len(rows) == 10
        assert rows[0][0] == 0
        assert rows[-1][0] == 9

    def test_persistence(self):
        """Close and reopen engine — data should persist."""
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]

        # First session
        engine1 = StorageEngine(TEST_DATA_DIR)
        engine1.create_table('USERS', cols)
        engine1.insert('USERS', {'id': 1, 'name': 'Alice'})
        engine1.insert('USERS', {'id': 2, 'name': 'Bob'})
        engine1.save_all()
        engine1.close()

        # Second session
        engine2 = StorageEngine(TEST_DATA_DIR)
        assert 'USERS' in engine2.list_tables()
        assert engine2.get('USERS', 1)['name'] == 'Alice'
        assert engine2.get('USERS', 2)['name'] == 'Bob'
        engine2.close()


class TestTransaction:
    def test_begin_commit(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]
        engine.create_table('USERS', cols)
        engine.begin_txn()
        engine.insert('USERS', {'id': 1, 'name': 'Alice'})
        engine.commit_txn()
        assert engine.get('USERS', 1)['name'] == 'Alice'

    def test_begin_rollback(self):
        engine = StorageEngine(TEST_DATA_DIR)
        cols = [Column('id', 'INT', primary_key=True),
                Column('name', 'VARCHAR')]
        engine.create_table('USERS', cols)
        engine.begin_txn()
        engine.insert('USERS', {'id': 1, 'name': 'Alice'})
        engine.rollback_txn()
        # After rollback and reload from disk, should not have the inserted row
        row = engine.get('USERS', 1)
        assert row is None


class TestColumnCoerce:
    def test_int_coerce(self):
        assert coerce_value('42', 'INT') == 42
        assert coerce_value(42, 'INT') == 42

    def test_str_coerce(self):
        assert coerce_value(42, 'VARCHAR') == '42'

    def test_none_coerce(self):
        assert coerce_value(None, 'INT') is None


# ══════════════════════════════════════════════════
# 5. Integration Tests (Engine + SQL)
# ══════════════════════════════════════════════════

class TestSQLEngine:
    def test_create_and_insert(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        r = db.execute("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR, age INT)")
        assert r['type'] == 'ok'

        r = db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        assert r['type'] == 'ok'
        assert r['key'] == 1
        db.close()

    def test_select_all(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")
        db.execute("INSERT INTO t VALUES (1, 'Alice')")
        db.execute("INSERT INTO t VALUES (2, 'Bob')")

        r = db.execute("SELECT * FROM t")
        assert r['type'] == 'select'
        assert r['count'] == 2
        assert len(r['rows']) == 2

        # Check data
        rows_by_id = {row.get('id'): row for row in r['rows']}
        assert rows_by_id[1]['name'] == 'Alice'
        assert rows_by_id[2]['name'] == 'Bob'
        db.close()

    def test_select_with_where(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR, age INT)")
        db.execute("INSERT INTO t VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO t VALUES (2, 'Bob', 25)")
        db.execute("INSERT INTO t VALUES (3, 'Charlie', 35)")

        r = db.execute("SELECT * FROM t WHERE age > 28")
        assert r['count'] == 2  # Alice 30, Charlie 35
        db.close()

    def test_select_with_order_by(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")
        db.execute("INSERT INTO t VALUES (2, 'Bob')")
        db.execute("INSERT INTO t VALUES (1, 'Alice')")
        db.execute("INSERT INTO t VALUES (3, 'Charlie')")

        r = db.execute("SELECT * FROM t ORDER BY id ASC")
        assert r['rows'][0]['id'] == 1
        assert r['rows'][1]['id'] == 2
        assert r['rows'][2]['id'] == 3
        db.close()

    def test_select_with_limit(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT)")
        for i in range(100):
            db.execute("INSERT INTO t VALUES (%d)" % i)

        r = db.execute("SELECT * FROM t LIMIT 5")
        assert r['count'] == 5
        db.close()

    def test_update(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")
        db.execute("INSERT INTO t VALUES (1, 'Alice')")

        r = db.execute("UPDATE t SET name = 'Bob' WHERE id = 1")
        assert r['type'] == 'ok'
        assert r['count'] == 1

        r = db.execute("SELECT * FROM t WHERE id = 1")
        assert r['rows'][0]['name'] == 'Bob'
        db.close()

    def test_delete(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")
        db.execute("INSERT INTO t VALUES (1, 'Alice')")
        db.execute("INSERT INTO t VALUES (2, 'Bob')")

        r = db.execute("DELETE FROM t WHERE id = 1")
        assert r['count'] == 1

        r = db.execute("SELECT * FROM t")
        assert r['count'] == 1
        assert r['rows'][0]['name'] == 'Bob'
        db.close()

    def test_show_tables(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        r = db.execute("SHOW TABLES")
        assert r['type'] == 'show_tables'
        assert 'tables' in r
        db.close()

    def test_drop_table(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT)")
        r = db.execute("SHOW TABLES")
        assert 'T' in r['tables']

        db.execute("DROP TABLE t")
        r = db.execute("SHOW TABLES")
        assert 'T' not in r['tables']
        db.close()

    def test_begin_commit_rollback(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")

        # Insert outside transaction
        db.execute("INSERT INTO t VALUES (1, 'persistent')")

        # Insert inside transaction, then rollback
        db.execute("BEGIN")
        db.execute("INSERT INTO t VALUES (2, 'rolled-back')")
        db.execute("ROLLBACK")

        # Only key 1 should exist
        r = db.execute("SELECT * FROM t")
        ids = [row['id'] for row in r['rows']]
        assert 1 in ids
        assert 2 not in ids

        # Insert inside transaction, then commit
        db.execute("BEGIN")
        db.execute("INSERT INTO t VALUES (3, 'committed')")
        db.execute("COMMIT")

        r = db.execute("SELECT * FROM t")
        ids = [row['id'] for row in r['rows']]
        assert 1 in ids
        assert 3 in ids
        db.close()

    def test_persistence_across_sessions(self):
        """Complete persistence test — full SQL across engine restarts."""
        # Session 1
        db1 = MiniDBEngine(TEST_DATA_DIR)
        db1.execute("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR, age INT)")
        db1.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db1.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        db1.execute("INSERT INTO users VALUES (3, 'Charlie', 35)")
        db1.close()

        # Session 2
        db2 = MiniDBEngine(TEST_DATA_DIR)

        r = db2.execute("SELECT * FROM users WHERE age > 28")
        assert r['count'] == 2  # Alice & Charlie

        r = db2.execute("SELECT name FROM users ORDER BY age DESC LIMIT 1")
        assert r['rows'][0]['name'] == 'Charlie'

        r = db2.execute("SELECT * FROM users")
        assert r['count'] == 3

        r = db2.execute("DELETE FROM users WHERE name = 'Bob'")
        assert r['count'] == 1
        db2.close()

        # Session 3 — verify delete persisted
        db3 = MiniDBEngine(TEST_DATA_DIR)
        r = db3.execute("SELECT * FROM users")
        assert r['count'] == 2
        names = [row['name'] for row in r['rows']]
        assert 'Alice' in names
        assert 'Charlie' in names
        assert 'Bob' not in names
        db3.close()


class TestEdgeCases:
    def test_empty_table(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT, name VARCHAR)")
        r = db.execute("SELECT * FROM t")
        assert r['count'] == 0

    def test_select_nonexistent_table(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        r = db.execute("SELECT * FROM nonexistent")
        assert r['type'] == 'error'

    def test_insert_nonexistent_table(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        r = db.execute("INSERT INTO nonexistent VALUES (1)")
        assert r['type'] == 'error'

    def test_duplicate_table(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE t (id INT)")
        with pytest.raises(ValueError):
            db.execute("CREATE TABLE t (id INT)")

    def test_large_dataset(self):
        db = MiniDBEngine(TEST_DATA_DIR)
        db.execute("CREATE TABLE large (id INT, val VARCHAR)")

        # Insert 500 records
        for i in range(500):
            db.execute("INSERT INTO large VALUES (%d, 'val-%d')" % (i, i))

        r = db.execute("SELECT * FROM large")
        assert r['count'] == 500

        # Range query
        r = db.execute("SELECT * FROM large WHERE id >= 100 AND id < 200")
        assert r['count'] == 100

        db.close()


if __name__ == '__main__':
    pytest.main(['-v', __file__])
