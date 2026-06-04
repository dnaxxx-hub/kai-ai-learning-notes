"""Query Executor — translates AST nodes into storage engine operations.

Converts parsed SQL AST into calls against the StorageEngine.
Handles WHERE clause evaluation, ORDER BY, LIMIT, DISTINCT, and aggregation.
"""

import re
import os
import sys
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from sql_parser import (
    CreateTable, ColumnDef, Insert, Select, Update, Delete,
    DropTable, ShowTables, Transaction, Condition,
)
from storage import StorageEngine, Column, TYPE_MAP, ALLOWED_TYPES, coerce_value


class Executor:
    """SQL query executor."""

    def __init__(self, storage):
        self.storage = storage  # StorageEngine instance

    def execute(self, ast):
        """Execute an AST node and return a result dict."""
        if isinstance(ast, CreateTable):
            return self._exec_create(ast)
        elif isinstance(ast, Insert):
            return self._exec_insert(ast)
        elif isinstance(ast, Select):
            return self._exec_select(ast)
        elif isinstance(ast, Update):
            return self._exec_update(ast)
        elif isinstance(ast, Delete):
            return self._exec_delete(ast)
        elif isinstance(ast, DropTable):
            return self._exec_drop(ast)
        elif isinstance(ast, ShowTables):
            return self._exec_show_tables()
        elif isinstance(ast, Transaction):
            return self._exec_transaction(ast)
        else:
            raise ValueError("Unknown AST node: %s" % type(ast).__name__)

    # ── CREATE TABLE ──────────────────────────────────

    def _exec_create(self, ast):
        columns = []
        for c in ast.columns:
            type_name = c.type_name.upper()
            if type_name not in ALLOWED_TYPES:
                # Map common variants
                if type_name in ('STRING',):
                    type_name = 'VARCHAR'
                elif type_name in ('INT', 'INTEGER'):
                    type_name = 'INT'
                elif type_name in ('REAL',):
                    type_name = 'FLOAT'
                else:
                    raise ValueError("Unsupported type: %s" % c.type_name)
            columns.append(Column(c.name, type_name, c.primary_key, c.not_null, c.default))

        self.storage.create_table(ast.name, columns)
        return {'type': 'ok', 'message': 'Table created'}

    # ── INSERT ────────────────────────────────────────

    def _exec_insert(self, ast):
        table = self.storage.get_table(ast.name)
        if table is None:
            return {'type': 'error', 'message': "Table '%s' not found" % ast.name}

        # Build row dict
        if ast.columns:
            # Column-specified INSERT
            row = {}
            for col_name, val in zip(ast.columns, ast.values):
                row[col_name] = val
        else:
            # Positional INSERT - map to columns in schema order
            row = {}
            for i, col in enumerate(table.schema.columns):
                if i < len(ast.values):
                    row[col.name] = ast.values[i]
                elif col.default is not None:
                    row[col.name] = col.default
                elif col.not_null:
                    return {'type': 'error',
                            'message': "NOT NULL column '%s' has no value" % col.name}

        # Coerce types
        for col in table.schema.columns:
            if col.name in row:
                row[col.name] = coerce_value(row[col.name], col.type_name)

        key = self.storage.insert(ast.name, row)
        return {'type': 'ok', 'message': 'Inserted', 'key': key, 'row': row}

    # ── SELECT ────────────────────────────────────────

    def _exec_select(self, ast):
        table = self.storage.get_table(ast.from_table)
        if table is None:
            return {'type': 'error', 'message': "Table '%s' not found" % ast.from_table}

        rows = self.storage.all_rows(ast.from_table)
        schema = table.schema

        # Apply WHERE filter
        if ast.where:
            rows = [r for r in rows if self._eval_condition(r[1], ast.where)]

        # Apply ORDER BY
        if ast.order_by:
            def sort_key(item):
                keys = []
                for col, direction in ast.order_by:
                    val = item[1].get(col, 0)
                    if isinstance(val, str):
                        keys.append(val)
                    else:
                        keys.append(val or 0)
                return tuple(keys)

            reverse = any(d == 'DESC' for _, d in ast.order_by)
            rows.sort(key=sort_key, reverse=reverse)

        # Apply LIMIT
        if ast.limit:
            rows = rows[:ast.limit]

        # Apply DISTINCT
        if ast.distinct:
            seen = set()
            unique = []
            for k, r in rows:
                key = tuple(sorted(r.items()))
                if key not in seen:
                    seen.add(key)
                    unique.append((k, r))
            rows = unique

        # Determine output columns
        if ast.columns == ['*']:
            output_cols = [c.name for c in schema.columns]
        else:
            output_cols = ast.columns

        # Build result rows
        result_rows = []
        for key, row in rows:
            out_row = {}
            for col_name in output_cols:
                out_row[col_name] = row.get(col_name)
            result_rows.append(out_row)

        return {
            'type': 'select',
            'columns': output_cols,
            'rows': result_rows,
            'count': len(result_rows),
        }

    # ── UPDATE ────────────────────────────────────────

    def _exec_update(self, ast):
        table = self.storage.get_table(ast.name)
        if table is None:
            return {'type': 'error', 'message': "Table '%s' not found" % ast.name}

        rows = self.storage.all_rows(ast.name)
        updated = 0

        # Get primary key column
        pk = table.schema.pk

        for key, row in rows:
            row_with_key = dict(row)
            if ast.where and not self._eval_condition(row_with_key, ast.where):
                continue

            # Apply SET
            for col, val in ast.set_clause.items():
                row_with_key[col] = val

            # Coerce types
            for col in table.schema.columns:
                if col.name in row_with_key:
                    row_with_key[col.name] = coerce_value(
                        row_with_key[col.name], col.type_name)

            # Update in storage
            self.storage.insert(ast.name, row_with_key)
            updated += 1

        return {'type': 'ok', 'message': 'Updated %d rows' % updated, 'count': updated}

    # ── DELETE ────────────────────────────────────────

    def _exec_delete(self, ast):
        table = self.storage.get_table(ast.name)
        if table is None:
            return {'type': 'error', 'message': "Table '%s' not found" % ast.name}

        rows = self.storage.all_rows(ast.name)
        deleted = 0

        for key, row in rows:
            row_with_key = dict(row)
            if ast.where and not self._eval_condition(row_with_key, ast.where):
                continue
            self.storage.delete(ast.name, key)
            deleted += 1

        return {'type': 'ok', 'message': 'Deleted %d rows' % deleted, 'count': deleted}

    # ── DROP TABLE ────────────────────────────────────

    def _exec_drop(self, ast):
        self.storage.drop_table(ast.name)
        return {'type': 'ok', 'message': 'Table dropped'}

    # ── SHOW TABLES ───────────────────────────────────

    def _exec_show_tables(self):
        tables = self.storage.list_tables()
        return {'type': 'show_tables', 'tables': tables}

    # ── TRANSACTION ──────────────────────────────────

    def _exec_transaction(self, ast):
        if ast.action == 'BEGIN':
            txn_id = self.storage.begin_txn()
            return {'type': 'ok', 'message': 'Transaction started', 'txn_id': txn_id}
        elif ast.action == 'COMMIT':
            self.storage.commit_txn()
            return {'type': 'ok', 'message': 'Transaction committed'}
        elif ast.action == 'ROLLBACK':
            self.storage.rollback_txn()
            return {'type': 'ok', 'message': 'Transaction rolled back'}
        return {'type': 'error', 'message': 'Unknown transaction action: %s' % ast.action}

    # ── Condition evaluation ─────────────────────────

    def _eval_condition(self, row, cond):
        """Evaluate a condition tree against a row dict."""
        if cond is None:
            return True

        if isinstance(cond, Condition):
            op = cond.op

            if op == 'AND':
                return self._eval_condition(row, cond.left) and \
                       self._eval_condition(row, cond.right)
            elif op == 'OR':
                return self._eval_condition(row, cond.left) or \
                       self._eval_condition(row, cond.right)
            elif op == 'NOT':
                return not self._eval_condition(row, cond.left)

            # Simple binary op
            left_val = self._resolve_value(row, cond.left)
            right_val = cond.right

            # Resolve right side if it's a column reference
            if isinstance(right_val, str) and not isinstance(right_val, (int, float)):
                if right_val.upper() in ('NULL',):
                    right_val = None
                elif right_val.upper() in ('TRUE',):
                    right_val = True
                elif right_val.upper() in ('FALSE',):
                    right_val = False
                else:
                    # Check if it's a column reference
                    row_val = row.get(right_val)
                    if row_val is not None or right_val in row:
                        right_val = row_val

            if op == '=':
                return left_val == right_val
            elif op in ('!=', '<>'):
                return left_val != right_val
            elif op == '<':
                return left_val is not None and right_val is not None and left_val < right_val
            elif op == '>':
                return left_val is not None and right_val is not None and left_val > right_val
            elif op == '<=':
                return left_val is not None and right_val is not None and left_val <= right_val
            elif op == '>=':
                return left_val is not None and right_val is not None and left_val >= right_val
            elif op == 'IS':
                return left_val is None
            elif op == 'IS NOT':
                return left_val is not None
            elif op == 'IN':
                return left_val in right_val if isinstance(right_val, (list, tuple)) else False
            elif op == 'NOT IN':
                return left_val not in right_val if isinstance(right_val, (list, tuple)) else False
            elif op == 'LIKE':
                if not isinstance(left_val, str) or not isinstance(right_val, str):
                    return False
                pattern = right_val.replace('%', '.*').replace('_', '.')
                return bool(re.search('^' + pattern + '$', left_val, re.IGNORECASE))
            elif op == 'BETWEEN':
                if not isinstance(right_val, (list, tuple)) or len(right_val) != 2:
                    return False
                return left_val is not None and \
                       right_val[0] is not None and right_val[1] is not None and \
                       right_val[0] <= left_val <= right_val[1]

        # No condition matched — truthy value
        return bool(cond) if not isinstance(cond, bool) else cond

    def _resolve_value(self, row, val):
        """Resolve a value: if it's a string and exists in row, return row value."""
        if val is None:
            return None
        if isinstance(val, str) and val in row:
            return row[val]
        if isinstance(val, str) and val.upper() == 'NULL':
            return None
        if isinstance(val, str) and val.upper() == 'TRUE':
            return True
        if isinstance(val, str) and val.upper() == 'FALSE':
            return False
        return val
