#!/usr/bin/env python3
"""
日志收集系统 — 单元测试
至少 20 个测试用例
"""

import sys
import os
import json
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import LogParser, LogEntry
from agent import LogAgent
from indexer import LogIndexer
from aggregator import LogAggregator
from server import LogServer


def _start_server():
    """启动一个测试用服务器"""
    srv = LogServer(host='127.0.0.1', port=18999)
    srv.start()
    time.sleep(0.1)
    return srv


class TestParser(unittest.TestCase):
    """Parser 测试"""

    def setUp(self):
        self.parser = LogParser()

    # 1. Parser: JSON 日志
    def test_parse_json(self):
        line = '{"level": "error", "message": "DB timeout", "service": "api"}'
        result = self.parser.parse(line, 'json')
        self.assertEqual(result['level'], 'error')
        self.assertEqual(result['message'], 'DB timeout')
        self.assertEqual(result['service'], 'api')

    # 2. Parser: Apache common
    def test_parse_apache_common(self):
        line = '192.168.1.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326'
        result = self.parser.parse(line, 'apache_common')
        self.assertEqual(result['ip'], '192.168.1.1')
        self.assertEqual(result['method'], 'GET')
        self.assertEqual(result['path'], '/apache_pb.gif')
        self.assertEqual(result['status'], 200)
        self.assertEqual(result['size'], 2326)

    # 3. Parser: Apache combined
    def test_parse_apache_combined(self):
        line = '10.0.0.1 - - [21/May/2026:10:04:00 +0800] "GET /api/users HTTP/1.1" 200 89 "http://example.com" "Mozilla/5.0"'
        result = self.parser.parse(line, 'apache_combined')
        self.assertEqual(result['ip'], '10.0.0.1')
        self.assertEqual(result['referer'], 'http://example.com')
        self.assertEqual(result['user_agent'], 'Mozilla/5.0')

    # 4. Parser: syslog
    def test_parse_syslog(self):
        line = 'May 21 10:00:00 myhost sshd[1234]: Failed password for root from 192.168.1.100 port 22 ssh2'
        result = self.parser.parse(line, 'syslog')
        self.assertEqual(result['hostname'], 'myhost')
        self.assertEqual(result['process'], 'sshd')
        self.assertEqual(result['pid'], '1234')
        self.assertIn('Failed password', result['message'])

    # 5. Parser: raw 兜底
    def test_parse_raw_fallback(self):
        line = 'this is just some random text that does not match any format'
        result = self.parser.parse(line)
        self.assertEqual(result['message'], line)
        self.assertEqual(result['_raw'], line)

    # 6. Parser: 格式自动检测 (unspecified format)
    def test_detect_format(self):
        # JSON
        self.assertEqual(self.parser.detect_format('{"a":1}'), 'json')
        # Apache common
        self.assertEqual(self.parser.detect_format('1.2.3.4 - - [01/Jan/2021:00:00:00 +0000] "GET / HTTP/1.0" 200 100'), 'apache_common')
        # Apache combined (has quotes ' "" "" ' → two empty strings after status = '" "' in line)
        combined = '1.2.3.4 - - [01/Jan/2021:00:00:00 +0000] "GET / HTTP/1.0" 200 100 "-" "Mozilla"'
        self.assertEqual(self.parser.detect_format(combined), 'apache_combined')
        # syslog
        self.assertEqual(self.parser.detect_format('Jan 01 12:00:00 host proc: msg'), 'syslog')
        # raw
        self.assertEqual(self.parser.detect_format('hello world'), 'raw')

    # Bonus: nginx 解析 (同 combined)
    def test_parse_nginx(self):
        line = '10.0.0.1 - - [21/May/2026:10:04:00 +0800] "GET /api/users HTTP/1.1" 200 89 "http://example.com" "nginx-test-agent"'
        result = self.parser.parse(line, 'nginx')
        self.assertEqual(result['user_agent'], 'nginx-test-agent')
        self.assertEqual(result['status'], 200)

    # Bonus: JSON 自动检测
    def test_parse_json_auto_detect(self):
        line = '{"level": "info", "event": "login", "user": "admin"}'
        result = self.parser.parse(line)
        self.assertEqual(result['level'], 'info')
        self.assertEqual(result['user'], 'admin')

    # Bonus: Apache 自动检测 (combined 匹配)
    def test_parse_apache_auto_detect(self):
        line = '1.1.1.1 - - [01/Jan/2025:00:00:00 +0000] "POST /api HTTP/1.1" 404 0 "-" "curl/7.0"'
        result = self.parser.parse(line)
        self.assertEqual(result['status'], 404)
        self.assertEqual(result['method'], 'POST')

    # Bonus: LogEntry 创建
    def test_log_entry(self):
        data = {'message': 'test', 'timestamp': '2026-05-21T10:00:00'}
        entry = LogEntry('log_1', data)
        self.assertEqual(entry.log_id, 'log_1')
        self.assertEqual(entry.timestamp, '2026-05-21T10:00:00')
        self.assertIsNone(entry.tokens)


class TestAgent(unittest.TestCase):
    """Agent 测试"""

    # 7. Agent: 单行发送
    def test_send_line(self):
        srv = _start_server()
        agent = LogAgent(server_host='127.0.0.1', server_port=18999)
        agent.send_line('test log line')
        time.sleep(0.2)
        self.assertGreater(srv.indexer._counter, 0)
        srv.stop()

    # 8. Agent: 批量发送
    def test_batch_send(self):
        srv = _start_server()
        agent = LogAgent(server_host='127.0.0.1', server_port=18999, batch_size=3)
        for i in range(10):
            agent.send_line(f'batch log message {i}')
        time.sleep(0.3)
        self.assertEqual(srv.indexer._counter, 10)
        srv.stop()

    # Bonus: Agent start/stop
    def test_agent_start_stop(self):
        agent = LogAgent()
        self.assertFalse(agent._running)
        agent.start()
        self.assertTrue(agent._running)
        agent.stop()
        self.assertFalse(agent._running)


class TestIndexer(unittest.TestCase):
    """Indexer 测试"""

    def setUp(self):
        self.indexer = LogIndexer()

    # 9. Indexer: 索引单条日志
    def test_index_single(self):
        log_id = self.indexer.index('test message')
        self.assertIsNotNone(log_id)
        self.assertIn(log_id, self.indexer.entries)
        self.assertEqual(len(self.indexer.entries), 1)

    # 10. Indexer: 倒排索引结构
    def test_inverted_index(self):
        self.indexer.index('hello world')
        self.indexer.index('hello python')
        self.assertIn('hello', self.indexer.inverted)
        self.assertIn('world', self.indexer.inverted)
        self.assertIn('python', self.indexer.inverted)
        self.assertEqual(len(self.indexer.inverted['hello']), 2)

    # 11. Indexer: 关键词搜索
    def test_keyword_search(self):
        self.indexer.index('hello world')
        self.indexer.index('foo bar')
        results = self.indexer.search('hello')
        self.assertEqual(len(results), 1)
        self.assertIn('world', str(results[0]['data']))

    # 12. Indexer: 多词搜索 (AND)
    def test_multi_word_search(self):
        self.indexer.index('hello world python')
        self.indexer.index('hello foo')
        self.indexer.index('world python')
        results = self.indexer.search('hello python')
        self.assertEqual(len(results), 1)  # only first has both

    # 13. Indexer: 无匹配搜索
    def test_no_match_search(self):
        self.indexer.index('hello world')
        results = self.indexer.search('nonexistent')
        self.assertEqual(len(results), 0)

    # 14. Indexer: 字段过滤
    def test_field_filter(self):
        self.indexer.index('192.168.1.1 - - [21/May/2026:10:00:00 +0800] "GET / HTTP/1.1" 200 100')
        self.indexer.index('192.168.1.2 - - [21/May/2026:10:01:00 +0800] "POST /api HTTP/1.1" 404 50')
        results = self.indexer.search('GET', field_filter={'status': 200})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['data']['status'], 200)

    # Bonus: 时间范围过滤
    def test_time_range_filter(self):
        self.indexer.index('{"timestamp": "2026-01-01T10:00:00", "msg": "early"}')
        self.indexer.index('{"timestamp": "2026-06-15T10:00:00", "msg": "middle"}')
        self.indexer.index('{"timestamp": "2026-12-31T10:00:00", "msg": "late"}')
        results = self.indexer.search('2026', start_time='2026-06-01T00:00:00', end_time='2026-12-31T23:59:59')
        self.assertEqual(len(results), 2)

    # Bonus: stats
    def test_stats(self):
        self.indexer.index('hello world')
        self.indexer.index('hello python foo bar')
        s = self.indexer.stats()
        self.assertEqual(s['total_entries'], 2)
        self.assertGreater(s['unique_tokens'], 0)

    # Bonus: 大小写不敏感
    def test_case_insensitive(self):
        self.indexer.index('Hello World')
        results = self.indexer.search('hello')
        self.assertEqual(len(results), 1)

    # Bonus: 空查询
    def test_empty_query(self):
        self.indexer.index('hello')
        results = self.indexer.search('')
        self.assertEqual(len(results), 0)

    # Bonus: 查询空索引
    def test_search_empty_index(self):
        results = self.indexer.search('anything')
        self.assertEqual(len(results), 0)


class TestAggregator(unittest.TestCase):
    """Aggregator 测试"""

    def setUp(self):
        self.indexer = LogIndexer()
        self.aggregator = LogAggregator(self.indexer)
        # 注入测试数据
        logs = [
            '192.168.1.1 - - [21/May/2026:10:00:00 +0800] "GET /index.html HTTP/1.1" 200 100',
            '192.168.1.2 - - [21/May/2026:10:01:00 +0800] "GET /index.html HTTP/1.1" 200 200',
            '192.168.1.1 - - [21/May/2026:10:02:00 +0800] "POST /api/login HTTP/1.1" 401 50',
            '192.168.1.3 - - [21/May/2026:10:03:00 +0800] "GET /about.html HTTP/1.1" 404 30',
            '192.168.1.1 - - [21/May/2026:10:04:00 +0800] "GET /index.html HTTP/1.1" 500 0',
        ]
        for log in logs:
            self.indexer.index(log)

    # 15. Aggregator: count_by_field
    def test_count_by_field(self):
        result = self.aggregator.count_by_field('path')
        paths = dict(result)
        self.assertEqual(paths.get('/index.html'), 3)

    # 16. Aggregator: count_by_status
    def test_count_by_status(self):
        result = self.aggregator.count_by_status()
        statuses = dict(result)
        self.assertEqual(statuses.get(200), 2)
        self.assertEqual(statuses.get(401), 1)

    # 17. Aggregator: count_by_ip
    def test_count_by_ip(self):
        result = self.aggregator.count_by_ip(3)
        ips = dict(result)
        self.assertEqual(ips.get('192.168.1.1'), 3)

    # 18. Aggregator: error_rate
    def test_error_rate(self):
        rate = self.aggregator.error_rate()
        self.assertEqual(rate, 60.0)  # 3 errors (401, 404, 500) out of 5

    # 19. Aggregator: time_series
    def test_time_series(self):
        ts = self.aggregator.time_series(interval=60)
        self.assertGreater(len(ts), 0)

    # 20. Aggregator: top_paths
    def test_top_paths(self):
        result = self.aggregator.top_paths(5)
        paths = dict(result)
        self.assertIn('/index.html', paths)
        self.assertEqual(paths['/index.html'], 3)


class TestServer(unittest.TestCase):
    """Server 集成测试"""

    # Bonus: Server search API
    def test_server_search(self):
        srv = _start_server()
        srv.indexer.index('hello world test')
        srv.indexer.index('python testing')
        results = srv.search('hello')
        self.assertEqual(len(results), 1)
        srv.stop()

    # Bonus: Server 接收 TCP 日志
    def test_server_tcp_receive(self):
        srv = _start_server()
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(('127.0.0.1', 18999))
        msg = json.dumps({'logs': ['tcp test line 1', 'tcp test line 2']}) + '\n'
        sock.sendall(msg.encode())
        sock.close()
        time.sleep(0.2)
        self.assertEqual(srv.indexer._counter, 2)
        srv.stop()

    # Bonus: Server 多次接收
    def test_server_multiple_batches(self):
        srv = _start_server()
        agent = LogAgent(server_host='127.0.0.1', server_port=18999)
        agent.send_line('multi 1')
        agent.send_line('multi 2')
        agent.send_line('multi 3')
        time.sleep(0.3)
        self.assertEqual(srv.indexer._counter, 3)
        srv.stop()


if __name__ == '__main__':
    unittest.main()
