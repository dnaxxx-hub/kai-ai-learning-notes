"""MiniDB Engine — top-level database engine combining all components.

Wires together: StorageEngine → SQL Parser → Executor
Provides a clean API for CLI and tests.
"""

import os
import sys
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from sql_parser import parse_sql, parse_sql_multi
from storage import StorageEngine, DATA_DIR
from executor import Executor


class MiniDBEngine:
    """Complete database engine with persistence, SQL, and transactions."""

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.storage = StorageEngine(data_dir)
        self.executor = Executor(self.storage)

    def execute(self, sql):
        """Execute a single SQL statement and return result dict."""
        ast = parse_sql(sql)
        if ast is None:
            return None
        return self.executor.execute(ast)

    def execute_multi(self, sql):
        """Execute multiple SQL statements (separated by ;)."""
        results = []
        for ast in parse_sql_multi(sql):
            result = self.executor.execute(ast)
            results.append(result)
        return results

    def close(self):
        self.storage.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
