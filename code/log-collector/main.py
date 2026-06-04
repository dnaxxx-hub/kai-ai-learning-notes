#!/usr/bin/env python3
"""
日志收集系统 — 命令行入口

用法:
  python main.py search "keyword"
  python main.py search "keyword" --field status 404
  python main.py stats
  python main.py top status
  python main.py top ip
  python main.py top path
  python main.py top user_agent
  python main.py error-rate
  python main.py time-series [interval=60]
  python main.py ingest <filepath>
"""

import argparse
import sys
import time
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import LogServer
from agent import LogAgent


def main():
    parser = argparse.ArgumentParser(description='日志收集系统 CLI')
    subparsers = parser.add_subparsers(dest='command')

    # search
    search_parser = subparsers.add_parser('search', help='搜索日志')
    search_parser.add_argument('query', help='搜索关键词')
    search_parser.add_argument('--field', nargs=2, metavar=('KEY', 'VALUE'), help='字段过滤')
    search_parser.add_argument('--start', help='起始时间')
    search_parser.add_argument('--end', help='结束时间')
    search_parser.add_argument('--top', type=int, default=10, help='返回条数')

    # stats
    subparsers.add_parser('stats', help='索引统计')

    # top
    top_parser = subparsers.add_parser('top', help='Top N 统计')
    top_parser.add_argument('field', help='统计字段')
    top_parser.add_argument('--top', type=int, default=10, help='返回条数')

    # error-rate
    subparsers.add_parser('error-rate', help='错误率')

    # time-series
    ts_parser = subparsers.add_parser('time-series', help='时间序列')
    ts_parser.add_argument('interval', nargs='?', type=int, default=60, help='时间间隔（秒）')

    # ingest
    ingest_parser = subparsers.add_parser('ingest', help='从文件导入日志')
    ingest_parser.add_argument('filepath', help='日志文件路径')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 启动服务器
    server = LogServer()
    server.start()
    time.sleep(0.1)  # 等待服务器就绪

    # 注入一些示例数据（如果是 search/stats/top 等查询命令）
    _inject_sample_data(server)

    if args.command == 'search':
        field_filter = None
        if args.field:
            field_filter = {args.field[0]: int(args.field[1]) if args.field[1].isdigit() else args.field[1]}

        results = server.search(
            args.query,
            start_time=args.start,
            end_time=args.end,
            field_filter=field_filter,
            top_k=args.top,
        )

        print(f"🔍 搜索 \"{args.query}\": 找到 {len(results)} 条结果")
        print("-" * 60)
        for r in results:
            data = r['data']
            msg = data.get('message') or data.get('_raw', '')
            timestamp = data.get('timestamp', '')
            status = data.get('status', '')
            path = data.get('path', '')
            ip = data.get('ip', '')
            parts = []
            if timestamp:
                parts.append(f"[{timestamp}]")
            if ip:
                parts.append(ip)
            if status:
                parts.append(str(status))
            if path:
                parts.append(path)
            print(f"  {r['log_id']} (score={r['score']}): {' '.join(parts)}")
            if msg:
                print(f"    {msg[:120]}")

    elif args.command == 'stats':
        s = server.stats()
        print("📊 索引统计")
        print(f"  总日志条数: {s['total_entries']}")
        print(f"  唯一词条数: {s['unique_tokens']}")
        print(f"  平均词条/条: {s['avg_tokens_per_entry']:.2f}")

    elif args.command == 'top':
        results = server.aggregator.count_by_field(args.field, args.top)
        print(f"📈 Top {args.top} {args.field}")
        print("-" * 40)
        for val, count in results:
            print(f"  {val!r}: {count}")

    elif args.command == 'error-rate':
        rate = server.aggregator.error_rate()
        print(f"📉 错误率: {rate}%")

    elif args.command == 'time-series':
        ts = server.aggregator.time_series(int(args.interval))
        print(f"📈 时间序列（间隔 {args.interval}s）")
        print("-" * 40)
        import datetime
        for bucket, count in ts[:20]:
            dt = datetime.datetime.fromtimestamp(bucket)
            print(f"  {dt.isoformat()}: {count}")
        if len(ts) > 20:
            print(f"  ... 共 {len(ts)} 个时间段")

    elif args.command == 'ingest':
        filepath = args.filepath
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            return

        server.stop()
        # 直接读取文件并索引
        print(f"📥 正在导入: {filepath}")
        count = 0
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    server.indexer.index(line)
                    count += 1
        print(f"✅ 已导入 {count} 条日志")

        # 重新展示统计
        s = server.stats()
        print(f"📊 总计 {s['total_entries']} 条, {s['unique_tokens']} 个唯一词条")

    server.stop()


def _inject_sample_data(server):
    """注入示例数据用于演示"""
    sample_logs = [
        '{"level": "error", "message": "Connection timeout", "service": "api", "timestamp": "2026-05-21T10:00:00"}',
        '{"level": "info", "message": "Request completed", "service": "api", "timestamp": "2026-05-21T10:01:00"}',
        '{"level": "error", "message": "Database connection failed", "service": "db", "timestamp": "2026-05-21T10:02:00"}',
        '192.168.1.1 - - [21/May/2026:10:00:00 +0800] "GET /index.html HTTP/1.1" 200 1234',
        '192.168.1.2 - - [21/May/2026:10:01:00 +0800] "POST /api/login HTTP/1.1" 401 56',
        '192.168.1.1 - - [21/May/2026:10:02:00 +0800] "GET /images/logo.png HTTP/1.1" 404 234',
        '192.168.1.3 - - [21/May/2026:10:03:00 +0800] "GET /index.html HTTP/1.1" 200 5678',
        '10.0.0.1 - - [21/May/2026:10:04:00 +0800] "GET /api/users HTTP/1.1" 200 89 "http://example.com" "Mozilla/5.0"',
        'May 21 10:00:00 myhost sshd[1234]: Failed password for root from 192.168.1.100 port 22 ssh2',
        'May 21 10:01:00 myhost sshd[1234]: Accepted public key for admin from 192.168.1.5 port 22 ssh2',
        'May 21 10:02:00 myhost kernel: [12345.678] CPU temperature high',
        '{"level": "warn", "message": "High memory usage", "service": "monitor", "timestamp": "2026-05-21T10:05:00"}',
        '192.168.1.1 - - [21/May/2026:10:05:00 +0800] "GET /api/data HTTP/1.1" 500 120',
        '192.168.1.4 - - [21/May/2026:10:06:00 +0800] "GET /favicon.ico HTTP/1.1" 404 12',
        '127.0.0.1 - admin [21/May/2026:10:07:00 +0800] "DELETE /api/cache HTTP/1.1" 204 0',
    ]

    # 只注入没有索引过的（防止重复）
    for log in sample_logs:
        server.indexer.index(log)


if __name__ == '__main__':
    main()
