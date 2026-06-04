"""Storage Engine — B+Tree backed persistence layer with WAL integration.

Table data is stored in B+Trees (one per table), persisted to JSON files.
The WAL provides crash recovery.
"""

import os
import json
import sys
import shutil
# Ensure we can import sibling modules whether run as package or standalone
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from btree import BPlusTree
from wal import WAL, WALRecord

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
WAL_FILE = os.path.join(DATA_DIR, 'minidb.wal')

# ── Type system ────────────────────────────────────

TYPE_MAP = {
    'INT': int,
    'BIGINT': int,
    'INTEGER': int,
    'VARCHAR': str,
    'TEXT': str,
    'CHAR': str,
    'FLOAT': float,
    'DOUBLE': float,
    'BOOL': lambda v: v in (True, 1, 'true', 'TRUE', '1'),
}

ALLOWED_TYPES = set(TYPE_MAP.keys())


def coerce_value(val, type_name):
    """Coerce a value to the expected type."""
    if val is None:
        return None
    type_name = type_name.upper()
    if type_name in TYPE_MAP:
        try:
            return TYPE_MAP[type_name](val)
        except (ValueError, TypeError):
            return val
    return val


# ── Table schema ───────────────────────────────────

class Column:
    __slots__ = ('name', 'type_name', 'primary_key', 'not_null', 'default')

    def __init__(self, name, type_name, primary_key=False, not_null=False, default=None):
        self.name = name
        self.type_name = type_name.upper()
        self.primary_key = primary_key
        self.not_null = not_null
        self.default = default

    def __repr__(self):
        return "Column(%s %s%s)" % (
            self.name, self.type_name,
            ' PK' if self.primary_key else '')

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.type_name,
            'primary_key': self.primary_key,
            'not_null': self.not_null,
            'default': self.default,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d['name'], d['type'],
                   d.get('primary_key', False),
                   d.get('not_null', False),
                   d.get('default'))


class TableSchema:
    """Schema metadata for a table."""

    def __init__(self, name, columns, primary_key=None):
        self.name = name
        self.columns = columns
        self.pk = primary_key  # Column name used as B+Tree key
        if self.pk is None:
            for c in columns:
                if c.primary_key:
                    self.pk = c.name
        if self.pk is None and columns:
            self.pk = columns[0].name  # Default to first column

    def col_index(self, name):
        for i, c in enumerate(self.columns):
            if c.name.lower() == name.lower():
                return i
        return -1

    def col_by_name(self, name):
        idx = self.col_index(name)
        if idx >= 0:
            return self.columns[idx]
        return None

    def to_dict(self):
        return {
            'name': self.name,
            'pk': self.pk,
            'columns': [c.to_dict() for c in self.columns],
        }

    @classmethod
    def from_dict(cls, d):
        columns = [Column.from_dict(c) for c in d['columns']]
        return cls(d['name'], columns, d.get('pk'))

    def __repr__(self):
        return "Table(%s: %s)" % (self.name,
                                  ', '.join("%s %s" % (c.name, c.type_name) for c in self.columns))


# ── Table (B+Tree backed) ──────────────────────────

class Table:
    """A single table backed by a persistent B+Tree."""

    def __init__(self, schema, data_dir=DATA_DIR):
        self.schema = schema
        self.data_dir = data_dir
        self.tree = BPlusTree(order=8)
        self._dirty = False
        self._load()

    def _table_path(self):
        return os.path.join(self.data_dir, '%s.json' % self.schema.name)

    def _save(self):
        path = self._table_path()
        d = self.tree.to_dict()
        data = {
            'schema': self.schema.to_dict(),
            'tree': d,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(path + '.tmp', path)
        self._dirty = False

    def _load(self):
        path = self._table_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.schema = TableSchema.from_dict(data['schema'])
            self.tree = BPlusTree.from_dict(data['tree'])
            self._dirty = False
        except Exception as e:
            raise IOError("Failed to load table '%s': %s" % (self.schema.name, e))

    def get_row_key(self, row):
        """Extract the primary key value from a row dict."""
        if not self.schema.pk:
            return row.get(list(row.keys())[0]) if row else None
        return row.get(self.schema.pk)

    def insert(self, row):
        key = self.get_row_key(row)
        if key is None:
            raise ValueError("Row has no value for primary key '%s'" % self.schema.pk)
        self.tree.insert(int(key), dict(row))
        self._dirty = True

    def get(self, key):
        val = self.tree.search(int(key))
        if val is not None and isinstance(val, dict):
            return val
        return None

    def update(self, key, new_values):
        key = int(key)
        existing = self.tree.search(key)
        if existing is None:
            return False
        if isinstance(existing, dict):
            existing.update(new_values)
            self.tree.insert(key, existing)
        else:
            self.tree.insert(key, new_values)
        self._dirty = True
        return True

    def delete(self, key):
        result = self.tree.delete(int(key))
        if result:
            self._dirty = True
        return result

    def scan(self, start=None, end=None):
        if start is not None:
            start = int(start)
        if end is not None:
            end = int(end)
        return self.tree.range_query(start, end)

    def all_rows(self):
        """Return all rows as (key, dict) pairs."""
        leaf = self._first_leaf()
        results = []
        while leaf:
            for i, k in enumerate(leaf.keys):
                v = leaf.children[i]
                if isinstance(v, dict):
                    results.append((k, v))
                else:
                    results.append((k, v))
            leaf = leaf.next
        return results

    def _first_leaf(self):
        n = self.tree.root
        while not n.is_leaf and n.children:
            n = n.children[0]
        return n

    def save(self):
        if self._dirty:
            self._save()

    def count(self):
        leaf = self._first_leaf()
        total = 0
        while leaf:
            total += len(leaf.keys)
            leaf = leaf.next
        return total

    def stats(self):
        return self.tree.stats()


# ── Storage Engine ─────────────────────────────────

class StorageEngine:
    """Top-level storage engine managing multiple tables + WAL."""

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.tables = {}  # name -> Table
        self.wal = None
        self._txn_counter = 0
        self._active_txn = None  # Current transaction ID if in transaction
        os.makedirs(data_dir, exist_ok=True)
        self._init_wal()
        self._recover()

    def _init_wal(self):
        if self.wal is not None:
            self.wal.close()
        self.wal = WAL(WAL_FILE)

    def _recover(self):
        """On startup, replay WAL for crash recovery. Also load existing tables from disk."""
        # First, load all existing table files from disk
        self._load_existing_tables()

        committed, uncommitted, schemas, actions = self.wal.replay()

        # Rebuild tables from WAL schemas (for any new tables not recovered from disk)
        for name, cols in schemas.items():
            if name not in self.tables:
                col_objs = []
                for c in cols:
                    if isinstance(c, dict):
                        col_objs.append(Column.from_dict(c))
                    else:
                        col_objs.append(Column(c, 'INT'))
                schema = TableSchema(name, col_objs)
                self.tables[name] = Table(schema, self.data_dir)

        # Apply committed actions
        for action in actions:
            if action[0] == 'table_schema':
                pass  # Already handled
            elif action[0] == 'insert':
                _, name, key, val = action
                if name in self.tables:
                    self.tables[name].tree.insert(int(key), val)
                    self.tables[name]._dirty = True
            elif action[0] == 'delete':
                _, name, key = action
                if name in self.tables:
                    self.tables[name].tree.delete(int(key))
                    self.tables[name]._dirty = True
            elif action[0] == 'update':
                _, name, key, val = action
                if name in self.tables:
                    self.tables[name].tree.insert(int(key), val)
                    self.tables[name]._dirty = True

        # Save recovered state
        for t in self.tables.values():
            t.save()

        # Write checkpoint + truncate WAL after recovery
        if actions:
            self.wal.log_checkpoint()
            self.wal.truncate()
            self._init_wal()

    def _load_existing_tables(self):
        """Load table files that exist on disk into memory."""
        if not os.path.isdir(self.data_dir):
            return
        for fname in os.listdir(self.data_dir):
            if fname.endswith('.json'):
                name = fname[:-5].upper()  # Remove .json, UPPERCASE
                try:
                    # Try loading the schema first
                    path = os.path.join(self.data_dir, fname)
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    schema = TableSchema.from_dict(data['schema'])
                    table = Table(schema, self.data_dir)
                    # Force reload from file
                    table._load()
                    self.tables[name] = table
                except Exception as e:
                    pass  # Skip corrupted tables

    # ── DDL ──────────────────────────────────────────

    def create_table(self, name, columns):
        """CREATE TABLE. columns: list of Column objects."""
        name = name.upper()
        if name in self.tables:
            raise ValueError("Table '%s' already exists" % name)
        schema = TableSchema(name, columns)
        table = Table(schema, self.data_dir)
        self.tables[name] = table

        # Log schema creation
        if self._is_in_txn():
            self.wal.log_table_schema(self._active_txn, name,
                                      [c.to_dict() for c in columns])

        table.save()
        return table

    def drop_table(self, name):
        """DROP TABLE."""
        name = name.upper()
        if name in self.tables:
            path = os.path.join(self.data_dir, '%s.json' % name)
            if os.path.exists(path):
                os.remove(path)
            del self.tables[name]

    def get_table(self, name):
        name = name.upper()
        return self.tables.get(name)

    def list_tables(self):
        return list(self.tables.keys())

    # ── DML ──────────────────────────────────────────

    def insert(self, table_name, row):
        """Insert a row dict into a table."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            raise ValueError("Table '%s' not found" % name)

        # Coerce types
        coerced = {}
        for col in table.schema.columns:
            if col.name in row:
                coerced[col.name] = coerce_value(row[col.name], col.type_name)
            elif col.default is not None:
                coerced[col.name] = col.default
            elif col.not_null:
                raise ValueError("NOT NULL column '%s' has no value" % col.name)
            else:
                coerced[col.name] = None

        key = table.get_row_key(coerced)
        # WAL log
        if self._is_in_txn():
            self.wal.log_insert(self._active_txn, name, key, coerced)

        table.insert(coerced)
        return key

    def get(self, table_name, key):
        """Get a single row by primary key."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return None
        return table.get(int(key))

    def update(self, table_name, key, new_values):
        """Update a row. Returns True if the row existed."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return False
        key = int(key)
        existing = table.get(key)
        if existing is None:
            return False
        existing.update(new_values)
        table.insert(existing)
        if self._is_in_txn():
            self.wal.log_update(self._active_txn, name, key, existing)
        return True

    def delete(self, table_name, key):
        """Delete a row by primary key."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return False
        result = table.delete(int(key))
        if result and self._is_in_txn():
            self.wal.log_delete(self._active_txn, name, int(key))
        return result

    def scan(self, table_name, start=None, end=None):
        """Range scan by primary key."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return []
        return table.scan(start, end)

    def all_rows(self, table_name):
        """Return all rows."""
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return []
        return table.all_rows()

    def table_stats(self, table_name):
        name = table_name.upper()
        table = self.tables.get(name)
        if table is None:
            return None
        return table.stats()

    # ── Transaction support ──────────────────────────

    def _is_in_txn(self):
        return self._active_txn is not None

    def begin_txn(self):
        # Save all dirty tables before starting transaction (so rollback can recover)
        for t in self.tables.values():
            t.save()
        self._txn_counter += 1
        self._active_txn = self._txn_counter
        self.wal.begin(self._active_txn)
        return self._active_txn

    def commit_txn(self):
        if self._active_txn is None:
            return
        txn_id = self._active_txn
        # Save all dirty tables
        for t in self.tables.values():
            t.save()
        self.wal.commit(txn_id)
        self.wal.log_checkpoint()
        self._active_txn = None

    def rollback_txn(self):
        if self._active_txn is None:
            return
        txn_id = self._active_txn
        self.wal.rollback(txn_id)
        self._active_txn = None
        # Reload tables from disk (discard uncommitted changes)
        self._reload_all()

    def _reload_all(self):
        # Re-initialize from disk
        self.tables.clear()
        self._load_existing_tables()

    # ── Save/Load ────────────────────────────────────

    def save_all(self):
        for t in self.tables.values():
            t.save()

    def close(self):
        if self._active_txn is not None:
            self.rollback_txn()
        self.save_all()
        if self.wal:
            self.wal.log_checkpoint()
            self.wal.truncate()
            self.wal.close()
