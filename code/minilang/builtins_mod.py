def builtin_print(*args):
    print(' '.join(str(a) for a in args))


def builtin_len(obj):
    return len(obj)


def builtin_type(obj):
    return type(obj).__name__


def builtin_range(n):
    return list(range(n))


def builtin_str(obj):
    return str(obj)


def builtin_int(obj):
    return int(obj)


def get_builtins():
    return {
        'print': builtin_print,
        'len': builtin_len,
        'type': builtin_type,
        'range': builtin_range,
        'str': builtin_str,
        'int': builtin_int,
        # 数据库函数
        'db_open': _builtin_db_open,
        'db_exec': _builtin_db_exec,
        'db_query': _builtin_db_query,
        'db_close': _builtin_db_close,
    }


import sqlite3
import os

# 数据库连接池
_db_connections = {}
_db_next_id = 1


def _builtin_db_open(filename: str) -> int:
    """打开 SQLite 数据库，返回连接 ID"""
    global _db_next_id
    try:
        conn = sqlite3.connect(filename)
        conn.row_factory = sqlite3.Row
        conn_id = _db_next_id
        _db_next_id += 1
        _db_connections[conn_id] = conn
        return conn_id
    except Exception as e:
        raise RuntimeError(f"DB open error: {e}")


def _builtin_db_exec(conn_id: int, sql: str) -> int:
    """执行 SQL，返回影响行数"""
    try:
        conn = _db_connections.get(conn_id)
        if not conn:
            raise RuntimeError(f"Invalid connection: {conn_id}")
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        raise RuntimeError(f"DB exec error: {e}")


def _builtin_db_query(conn_id: int, sql: str) -> list:
    """执行查询，返回结果列表"""
    try:
        conn = _db_connections.get(conn_id)
        if not conn:
            raise RuntimeError(f"Invalid connection: {conn_id}")
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [list(row) for row in rows]
    except Exception as e:
        raise RuntimeError(f"DB query error: {e}")


def _builtin_db_close(conn_id: int):
    """关闭数据库连接"""
    try:
        conn = _db_connections.pop(conn_id, None)
        if conn:
            conn.close()
    except Exception as e:
        raise RuntimeError(f"DB close error: {e}")
