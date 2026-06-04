#!/usr/bin/env python3
"""MiniDB Shell — interactive SQL database shell (like sqlite3).

Usage:
    python minidb_shell.py              # Interactive shell
    python minidb_shell.py <file>.sql   # Execute SQL file
    python minidb_shell.py --init sql   # Execute SQL, then shell
"""

import sys
import os
try:
    import readline  # For line editing in interactive mode
except ImportError:
    pass

# Ensure this module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import MiniDBEngine

VERSION = "MiniDB v1.0.0"


def format_result(result, pretty=True):
    """Format an execution result for terminal output."""
    if result is None:
        return ""

    t = result.get('type', '')

    if t == 'ok':
        msg = result.get('message', '')
        extra = ''
        if 'key' in result:
            extra += ' [key=%s]' % result['key']
        if 'count' in result:
            extra += ' [%d rows]' % result['count']
        if 'row' in result:
            extra += ' ' + str(result['row'])
        return 'OK: %s%s' % (msg, extra)

    elif t == 'error':
        return 'ERROR: %s' % result.get('message', 'Unknown error')

    elif t == 'select':
        cols = result.get('columns', [])
        rows = result.get('rows', [])
        count = result.get('count', 0)

        if not rows:
            return 'Empty set (%d rows)' % count

        if pretty:
            return _format_table(cols, rows, count)
        else:
            lines = ['| %s |' % ' | '.join(cols)]
            for r in rows:
                vals = [str(r.get(c, '')) for c in cols]
                lines.append('| %s |' % ' | '.join(vals))
            lines.append('(%d rows)' % count)
            return '\n'.join(lines)

    elif t == 'show_tables':
        tables = result.get('tables', [])
        if not tables:
            return 'No tables'
        return 'Tables:\n  ' + '\n  '.join(tables)

    return str(result)


def _format_table(cols, rows, count):
    """Format rows as an aligned table."""
    # Calculate column widths
    widths = [len(c) for c in cols]
    for r in rows:
        for i, c in enumerate(cols):
            val = str(r.get(c, ''))
            widths[i] = max(widths[i], len(val))

    # Build border
    border = '+' + '+'.join('-' * (w + 2) for w in widths) + '+'

    # Build header
    header = '|' + '|'.join(' %s ' % c.ljust(widths[i]) for i, c in enumerate(cols)) + '|'

    lines = [border, header, border]
    for r in rows:
        vals = [str(r.get(c, '')) for c in cols]
        line = '|' + '|'.join(' %s ' % vals[i].ljust(widths[i]) for i in range(len(cols))) + '|'
        lines.append(line)
    lines.append(border)
    lines.append('(%d rows)' % count)
    return '\n'.join(lines)


def print_help():
    print("""
MiniDB Shell — SQL commands:
  CREATE TABLE name (col TYPE, ...)
  INSERT INTO name VALUES (val, ...)
  SELECT * FROM name [WHERE cond] [ORDER BY col] [LIMIT n]
  UPDATE name SET col=val [WHERE cond]
  DELETE FROM name [WHERE cond]
  DROP TABLE name
  SHOW TABLES
  BEGIN [TRANSACTION]
  COMMIT [TRANSACTION]
  ROLLBACK [TRANSACTION]

Shell commands:
  .help     Show this help
  .tables   List tables
  .schema   Show table schema
  .exit     Exit shell
  .stats    Show table B+tree statistics
""")


def shell(db):
    """Interactive shell REPL."""
    print("%s interactive shell" % VERSION)
    print("Enter '.help' for help, '.exit' to quit.")

    buffer = ''

    while True:
        try:
            prompt = '  ' if buffer else 'minidb> '
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = line.strip()

        if not stripped:
            continue

        # Shell commands
        if stripped == '.exit' or stripped == '.quit':
            break
        elif stripped == '.help':
            print_help()
            continue
        elif stripped == '.tables':
            result = db.execute('SHOW TABLES')
            print(format_result(result))
            continue
        elif stripped == '.schema':
            result = db.execute('SHOW TABLES')
            tables = result.get('tables', [])
            for name in tables:
                print("Table: %s" % name)
                table = db.storage.get_table(name)
                if table:
                    for col in table.schema.columns:
                        flags = []
                        if col.primary_key:
                            flags.append('PK')
                        if col.not_null:
                            flags.append('NOT NULL')
                        flag_str = ' [%s]' % ','.join(flags) if flags else ''
                        print("  %s %s%s" % (col.name, col.type_name, flag_str))
            continue
        elif stripped == '.stats':
            result = db.execute('SHOW TABLES')
            tables = result.get('tables', [])
            for name in tables:
                stats = db.storage.table_stats(name)
                if stats:
                    print("Table: %s" % name)
                    for k, v in stats.items():
                        print("  %s: %s" % (k, v))
            continue

        # Handle multi-line SQL: accumulate until we see a semicolon
        if not line.rstrip().endswith(';'):
            buffer += ' ' + stripped
            continue
        else:
            full_sql = (buffer + ' ' + stripped).strip()
            buffer = ''

        # Remove trailing semicolons for single-statement execution
        sql_no_semi = full_sql.rstrip(';').strip()

        try:
            result = db.execute(sql_no_semi)
            formatted = format_result(result)
            if formatted:
                print(formatted)
        except Exception as e:
            print("Error: %s" % e)


def main():
    import shutil

    # Parse args
    init_sql = None
    sql_file = None
    interactive = True

    args = sys.argv[1:]

    # Check for --init flag or SQL file path
    while args:
        arg = args[0]
        if arg == '--init':
            # Remaining args are SQL to execute
            init_parts = []
            for a in args[1:]:
                if a.startswith('-'):
                    break
                init_parts.append(a)
            init_sql = ' '.join(init_parts)
            args = [a for a in args if a not in init_parts and a != '--init']
        elif arg.startswith('-'):
            args = args[1:]
        else:
            sql_file = arg
            args = args[1:]

    db = MiniDBEngine()

    try:
        if sql_file:
            # Execute SQL file
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            results = db.execute_multi(sql)
            for r in results:
                print(format_result(r))

        if init_sql:
            results = db.execute_multi(init_sql)
            for r in results:
                print(format_result(r))

        if interactive and not sql_file:
            shell(db)
        elif interactive and sql_file:
            shell(db)
    finally:
        db.close()


if __name__ == '__main__':
    main()
