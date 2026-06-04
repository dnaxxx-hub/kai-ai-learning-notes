"""
MiniTSDB - 纯 Python 实现
WAL 文件格式与 C 版本兼容（二进制：metric[64] + timestamp[int64] + value[double]）
"""
import struct
import os
import json
from flask import Flask, request, jsonify

# 常量
WAL_ENTRY_FORMAT = "64s q d"  # metric(64 bytes) + timestamp(int64) + value(double)
WAL_ENTRY_SIZE = struct.calcsize(WAL_ENTRY_FORMAT)

class MiniTSDB:
    """纯 Python 实现的迷你时序数据库"""

    def __init__(self, wal_path, memtable_max_size=10000):
        self.wal_path = wal_path
        self.memtable_max_size = memtable_max_size
        self.memtable = {}       # metric -> [(timestamp, value), ...]
        self.memtable_count = 0
        self.series = {}         # metric -> [(timestamp, value), ...] (持久区)
        self.wal_entry_count = 0

        # 加载已有 WAL
        self._load_wal()

    def _load_wal(self):
        """从 WAL 文件加载数据到 MemTable"""
        if not os.path.exists(self.wal_path):
            return

        with open(self.wal_path, "rb") as f:
            while True:
                data = f.read(WAL_ENTRY_SIZE)
                if len(data) < WAL_ENTRY_SIZE:
                    break
                metric_bytes, timestamp, value = struct.unpack(
                    WAL_ENTRY_FORMAT, data)
                metric = metric_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
                self._memtable_insert(metric, timestamp, value)

    def _memtable_insert(self, metric, timestamp, value):
        """插入到 MemTable"""
        if metric not in self.memtable:
            self.memtable[metric] = []
        self.memtable[metric].append((timestamp, value))
        self.memtable_count += 1

    def _wal_append(self, metric, timestamp, value):
        """追加到 WAL 文件"""
        metric_bytes = metric.encode('utf-8')
        if len(metric_bytes) > 63:
            metric_bytes = metric_bytes[:63]
        metric_bytes = metric_bytes.ljust(64, b'\x00')

        data = struct.pack(WAL_ENTRY_FORMAT, metric_bytes, timestamp, value)
        with open(self.wal_path, "ab") as f:
            f.write(data)
            f.flush()
        self.wal_entry_count += 1

    def write(self, metric, timestamp, value):
        """写入一个数据点"""
        # WAL 记录
        self._wal_append(metric, timestamp, value)

        # MemTable 插入
        self._memtable_insert(metric, timestamp, value)

        # MemTable 满了自动 flush
        if self.memtable_count >= self.memtable_max_size:
            self.flush()

    def query(self, metric, start_ts, end_ts):
        """查询某个 metric 在时间范围内的数据"""
        result = []

        # 从持久区查询
        if metric in self.series:
            for ts, val in self.series[metric]:
                if start_ts <= ts <= end_ts:
                    result.append({"timestamp": ts, "value": val})

        # 从 MemTable 查询
        if metric in self.memtable:
            for ts, val in self.memtable[metric]:
                if start_ts <= ts <= end_ts:
                    result.append({"timestamp": ts, "value": val})

        # 按时间戳排序
        result.sort(key=lambda x: x["timestamp"])
        return result

    def aggregate(self, metric, start_ts, end_ts):
        """聚合查询"""
        points = self.query(metric, start_ts, end_ts)

        if not points:
            return {"min": 0, "max": 0, "avg": 0, "count": 0}

        values = [p["value"] for p in points]
        count = len(values)
        min_val = min(values)
        max_val = max(values)
        avg_val = sum(values) / count

        return {
            "min": min_val,
            "max": max_val,
            "avg": avg_val,
            "count": count
        }

    def flush(self):
        """合并 MemTable 到持久区"""
        if self.memtable_count == 0:
            return

        for metric, points in self.memtable.items():
            if metric not in self.series:
                self.series[metric] = []
            self.series[metric].extend(points)
            # 排序
            self.series[metric].sort(key=lambda x: x[0])

        # 清空 MemTable
        self.memtable = {}
        self.memtable_count = 0
        self.wal_entry_count = 0

    def close(self):
        """关闭数据库"""
        self.flush()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ========== Flask REST API ==========

app = Flask(__name__)

# 全局 DB 实例
db = MiniTSDB('data_py.tsdb')


@app.route('/write', methods=['POST'])
def write_endpoint():
    data = request.json
    if not data:
        return jsonify({'error': 'missing body'}), 400

    metric = data.get('metric')
    timestamp = data.get('timestamp')
    value = data.get('value')

    if not metric or timestamp is None or value is None:
        return jsonify({'error': 'missing metric/timestamp/value'}), 400

    db.write(metric, int(timestamp), float(value))
    return jsonify({'status': 'ok'})


@app.route('/query')
def query_endpoint():
    metric = request.args.get('metric')
    start = int(request.args.get('start', 0))
    end = int(request.args.get('end', 9999999999999))

    if not metric:
        return jsonify({'error': 'missing metric'}), 400

    points = db.query(metric, start, end)
    return jsonify({'metric': metric, 'points': points})


@app.route('/aggregate')
def aggregate_endpoint():
    metric = request.args.get('metric')
    start = int(request.args.get('start', 0))
    end = int(request.args.get('end', 9999999999999))

    if not metric:
        return jsonify({'error': 'missing metric'}), 400

    result = db.aggregate(metric, start, end)
    result['metric'] = metric
    return jsonify(result)


@app.route('/flush', methods=['POST'])
def flush_endpoint():
    db.flush()
    return jsonify({'status': 'ok'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
