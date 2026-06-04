import json, re, datetime


class LogParser:
    """日志解析器：支持 JSON / Apache common / Apache combined / syslog / nginx / raw"""

    def __init__(self):
        self.parsers = {
            'json': self._parse_json,
            'apache_common': self._parse_apache_common,
            'apache_combined': self._parse_apache_combined,
            'syslog': self._parse_syslog,
            'nginx': self._parse_nginx,
        }

    def detect_format(self, line):
        """自动检测日志格式"""
        if line.startswith('{') and line.endswith('}'):
            return 'json'
        if re.match(r'\S+ \S+ \S+ \[', line):
            if '" "' in line:
                return 'apache_combined'
            return 'apache_common'
        if re.match(r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', line):
            return 'syslog'
        return 'raw'

    def parse(self, line, fmt=None):
        """解析单行日志，返回结构化字典"""
        if not fmt:
            fmt = self.detect_format(line)

        parser = self.parsers.get(fmt, self._parse_raw)
        try:
            return parser(line)
        except Exception:
            return self._parse_raw(line)

    def _parse_json(self, line):
        return json.loads(line)

    def _parse_apache_common(self, line):
        """127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326"""
        m = re.match(
            r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\S+)',
            line,
        )
        if m:
            return {
                'ip': m.group(1),
                'timestamp': m.group(2),
                'method': m.group(3),
                'path': m.group(4),
                'protocol': m.group(5),
                'status': int(m.group(6)),
                'size': int(m.group(7)) if m.group(7) != '-' else 0,
                '_raw': line,
            }
        return self._parse_raw(line)

    def _parse_apache_combined(self, line):
        """Apache combined: ... "http://referer" "user-agent" """
        m = re.match(
            r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\S+) "([^"]*)" "([^"]*)"',
            line,
        )
        if m:
            return {
                'ip': m.group(1),
                'timestamp': m.group(2),
                'method': m.group(3),
                'path': m.group(4),
                'protocol': m.group(5),
                'status': int(m.group(6)),
                'size': int(m.group(7)) if m.group(7) != '-' else 0,
                'referer': m.group(8),
                'user_agent': m.group(9),
                '_raw': line,
            }
        return self._parse_raw(line)

    def _parse_syslog(self, line):
        """Oct 10 13:55:36 hostname sshd[1234]: Accepted public key for user"""
        m = re.match(
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s+(.*)',
            line,
        )
        if m:
            return {
                'timestamp': m.group(1),
                'hostname': m.group(2),
                'process': m.group(3),
                'pid': m.group(4),
                'message': m.group(5),
                '_raw': line,
            }
        return self._parse_raw(line)

    def _parse_nginx(self, line):
        """类似 combined 但可能有差异"""
        return self._parse_apache_combined(line)

    def _parse_raw(self, line):
        return {'message': line, '_raw': line}


class LogEntry:
    """日志条目"""

    def __init__(self, log_id, data):
        self.log_id = log_id
        self.data = data
        self.timestamp = data.get('timestamp', datetime.datetime.now().isoformat())
        self.tokens = None  # 由 indexer 填充
