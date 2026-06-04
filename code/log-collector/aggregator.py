from collections import Counter, defaultdict
from datetime import datetime


class LogAggregator:
    """聚合分析：计数 / 分组 / 趋势"""

    def __init__(self, indexer):
        self.indexer = indexer

    def count_by_field(self, field, top_k=10):
        """按字段值统计"""
        counter = Counter()
        for entry in self.indexer.entries.values():
            val = entry.data.get(field, 'unknown')
            counter[val] += 1
        return counter.most_common(top_k)

    def count_by_status(self):
        """HTTP 状态码分布"""
        return self.count_by_field('status')

    def count_by_ip(self, top_k=10):
        """IP 访问排名"""
        return self.count_by_field('ip', top_k)

    def time_series(self, interval=60):
        """时间序列（按 interval 秒分组）"""
        buckets = defaultdict(int)

        for entry in self.indexer.entries.values():
            ts = entry.timestamp
            try:
                if 'T' in ts:
                    dt = datetime.strptime(ts[:19], '%Y-%m-%dT%H:%M:%S')
                else:
                    dt = datetime.strptime(ts[:19], '%d/%b/%Y:%H:%M:%S')
                bucket = (dt.timestamp() // interval) * interval
                buckets[bucket] += 1
            except (ValueError, IndexError):
                pass

        return sorted(buckets.items())

    def error_rate(self):
        """错误率（HTTP 4xx/5xx）"""
        total = len(self.indexer.entries)
        if total == 0:
            return 0.0
        errors = sum(
            1 for e in self.indexer.entries.values()
            if e.data.get('status', 200) >= 400
        )
        return round(errors / total * 100, 2)

    def top_paths(self, top_k=10):
        """最常访问的路径"""
        return self.count_by_field('path', top_k)

    def top_user_agents(self, top_k=5):
        """User-Agent 分布"""
        return self.count_by_field('user_agent', top_k)
