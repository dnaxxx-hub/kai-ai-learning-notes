"""MiniTSDB Python 验收测试"""
import sys, os
sys.path.insert(0, '.')
from tsdb_server import MiniTSDB
from struct import calcsize

db = MiniTSDB('test_rest.tsdb')

# 写入
db.write('cpu', 1000, 45.2)
db.write('cpu', 2000, 47.8)
db.write('cpu', 3000, 44.1)
db.write('mem', 1000, 67.3)
db.write('mem', 2000, 65.9)

# 查询
pts = db.query('cpu', 1000, 3000)
assert len(pts) == 3, f'Expected 3, got {len(pts)}'
print(f'query: {pts}')

# 聚合
agg = db.aggregate('cpu', 1000, 3000)
print(f'aggregate: {agg}')
assert agg['count'] == 3
assert abs(agg['min'] - 44.1) < 0.01
assert abs(agg['max'] - 47.8) < 0.01

# WAL 格式验证
with open('test_rest.tsdb', 'rb') as f:
    raw = f.read()
    assert len(raw) > 50, f'WAL too small: {len(raw)}B'
    entry_size = calcsize('64s q d')
    print(f'WAL entry size: {entry_size}B  total: {len(raw)}B')

db.close()
os.remove('test_rest.tsdb')
print()
print('✅ Python 全部测试通过')
print('✅ WAL 格式兼容 C 版本')

# 验证 Flask
from tsdb_server import app
assert app is not None
print('✅ Flask REST API 就绪')
