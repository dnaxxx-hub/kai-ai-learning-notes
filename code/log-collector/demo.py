#!/usr/bin/env python3
"""
日志收集系统 — 演示脚本

运行: python demo.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import LogServer
from agent import LogAgent


def main():
    print("=" * 60)
    print("📋 日志收集系统 — 演示")
    print("=" * 60)

    # 创建服务器
    server = LogServer()
    server.start()
    print("\n✅ 服务器已启动 (127.0.0.1:8800)")

    # 准备日志样本
    sample_logs = [
        # JSON
        '{"level": "error", "message": "Connection timeout", "service": "api", "timestamp": "2026-05-21T10:00:00"}',
        '{"level": "info", "message": "Request completed", "service": "api", "timestamp": "2026-05-21T10:01:00"}',
        '{"level": "error", "message": "Database connection failed", "service": "db", "timestamp": "2026-05-21T10:02:00"}',
        # Apache common
        '192.168.1.1 - - [21/May/2026:10:00:00 +0800] "GET /index.html HTTP/1.1" 200 1234',
        '192.168.1.2 - - [21/May/2026:10:01:00 +0800] "POST /api/login HTTP/1.1" 401 56',
        '192.168.1.1 - - [21/May/2026:10:02:00 +0800] "GET /images/logo.png HTTP/1.1" 404 234',
        '192.168.1.3 - - [21/May/2026:10:03:00 +0800] "GET /index.html HTTP/1.1" 200 5678',
        # Apache combined
        '10.0.0.1 - - [21/May/2026:10:04:00 +0800] "GET /api/users HTTP/1.1" 200 89 "http://example.com" "Mozilla/5.0"',
        # syslog
        'May 21 10:00:00 myhost sshd[1234]: Failed password for root from 192.168.1.100 port 22 ssh2',
        'May 21 10:01:00 myhost sshd[1234]: Accepted public key for admin from 192.168.1.5 port 22 ssh2',
        'May 21 10:02:00 myhost kernel: [12345.678] CPU temperature high',
        # more
        '{"level": "warn", "message": "High memory usage", "service": "monitor", "timestamp": "2026-05-21T10:05:00"}',
        '192.168.1.1 - - [21/May/2026:10:05:00 +0800] "GET /api/data HTTP/1.1" 500 120',
        '192.168.1.4 - - [21/May/2026:10:06:00 +0800] "GET /favicon.ico HTTP/1.1" 404 12',
    ]

    # 使用 Agent 发送日志
    agent = LogAgent()

    print("\n📤 正在注入日志样本...")
    for log in sample_logs:
        agent.send_line(log)
        print(f"  → {log[:60]}...")

    print("\n⏳ 等待服务器处理...")
    import time
    time.sleep(0.5)

    # ====== 查询演示 ======
    print("\n" + "=" * 60)
    print("🔍 搜索演示")
    print("=" * 60)

    # 1. 搜索 "error"
    print("\n▶ 搜索: error")
    results = server.search("error")
    for r in results:
        print(f"  [{r['log_id']}] score={r['score']} → {r['data'].get('message', r['data'].get('_raw', ''))[:80]}")

    # 2. 搜索 HTTP 相关
    print("\n▶ 搜索: GET (所有 GET 请求)")
    results = server.search("GET")
    for r in results[:5]:
        print(f"  [{r['log_id']}] score={r['score']} → {r['data'].get('_raw', '')[:80]}")

    # 3. 字段过滤：status=404
    print("\n▶ 搜索: GET 且 status=404")
    results = server.search("GET", field_filter={'status': 404})
    for r in results:
        print(f"  [{r['log_id']}] score={r['score']} → {r['data'].get('_raw', '')[:80]}")

    # ====== 聚合演示 ======
    print("\n" + "=" * 60)
    print("📊 聚合分析")
    print("=" * 60)

    print("\n▶ HTTP 状态码分布:")
    for status, count in server.aggregator.count_by_status():
        s_val = int(status) if isinstance(status, str) and status.isdigit() else status
        status_icon = '✅' if (isinstance(s_val, int) and s_val < 400) else '❌'
        print(f"  {status_icon} {status}: {count}")

    print(f"\n▶ 错误率: {server.aggregator.error_rate()}%")

    print("\n▶ 访问 IP Top:")
    for ip, count in server.aggregator.count_by_ip(5):
        print(f"  {ip}: {count}")

    print("\n▶ 访问路径 Top:")
    for path, count in server.aggregator.top_paths():
        print(f"  {path}: {count}")

    # ====== 统计 ======
    print("\n" + "=" * 60)
    print("📈 索引统计")
    print("=" * 60)
    s = server.stats()
    print(f"  总日志条数: {s['total_entries']}")
    print(f"  唯一词条数: {s['unique_tokens']}")
    print(f"  平均词条/条: {s['avg_tokens_per_entry']:.2f}")

    # 清理
    server.stop()
    print("\n✅ 演示完成")


if __name__ == '__main__':
    main()
