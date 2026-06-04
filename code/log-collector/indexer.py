import json
import re
import threading
from parser import LogParser, LogEntry


class LogIndexer:
    """日志索引器：倒排索引 + 时间线"""

    def __init__(self):
        self.parser = LogParser()
        self.entries = {}       # {log_id: LogEntry}
        self.inverted = {}      # {term: {log_id: count}}
        self.timeline = []      # [(timestamp, log_id)]
        self._counter = 0
        self._lock = threading.Lock()

    def index(self, log_line, fmt=None):
        """索引一条日志，返回 log_id"""
        data = self.parser.parse(log_line, fmt)

        with self._lock:
            self._counter += 1
            log_id = f"log_{self._counter}"
            entry = LogEntry(log_id, data)

            # 分词索引
            text = json.dumps(data)
            tokens = re.findall(r'\w+', text.lower())
            entry.tokens = list(set(tokens))

            for token in entry.tokens:
                if token not in self.inverted:
                    self.inverted[token] = {}
                self.inverted[token][log_id] = self.inverted[token].get(log_id, 0) + 1

            self.entries[log_id] = entry
            self.timeline.append((data.get('timestamp', ''), log_id))

            return log_id

    def search(self, query, start_time=None, end_time=None, field_filter=None, top_k=50):
        """搜索日志：关键词 + 时间范围 + 字段过滤"""
        query_tokens = re.findall(r'\w+', query.lower())
        if not query_tokens:
            return []

        # 倒排检索（AND 查询）
        result_ids = None
        for token in query_tokens:
            posting = self.inverted.get(token, {})
            term_ids = set(posting.keys())
            if result_ids is None:
                result_ids = term_ids
            else:
                result_ids &= term_ids

        if not result_ids:
            return []

        # 时间过滤
        if start_time or end_time:
            filtered = set()
            for log_id in result_ids:
                entry = self.entries.get(log_id)
                if entry:
                    ts = entry.timestamp
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
                    filtered.add(log_id)
            result_ids = filtered

        # 字段过滤
        if field_filter:
            filtered = set()
            for log_id in result_ids:
                entry = self.entries.get(log_id)
                if entry:
                    match = True
                    for key, val in field_filter.items():
                        if entry.data.get(key) != val:
                            match = False
                            break
                    if match:
                        filtered.add(log_id)
            result_ids = filtered

        # TF 排序
        scored = []
        for log_id in result_ids:
            score = sum(self.inverted.get(t, {}).get(log_id, 0) for t in query_tokens)
            scored.append((log_id, score))

        scored.sort(key=lambda x: (-x[1], x[0]))

        results = []
        for log_id, score in scored[:top_k]:
            entry = self.entries.get(log_id)
            if entry:
                results.append({
                    'log_id': log_id,
                    'score': score,
                    'data': entry.data,
                })

        return results

    def stats(self):
        """索引统计"""
        with self._lock:
            total = len(self.entries)
            avg = sum(len(e.tokens) for e in self.entries.values()) / max(total, 1)
            return {
                'total_entries': total,
                'unique_tokens': len(self.inverted),
                'avg_tokens_per_entry': avg,
            }
