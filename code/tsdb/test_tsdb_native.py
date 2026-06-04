"""测试 pybind11 包装的 tsdb_native 模块"""
import sys, os
sys.path.insert(0, '.')

try:
    import tsdb_native
    NATIVE_OK = True
except ImportError as e:
    print(f"⚠️ 未加载本地模块，将用纯Python版本: {e}")
    NATIVE_OK = False

# 测试 WAL 兼容性
def test_native():
    db = tsdb_native.MiniTSDB('test_native.tsdb')

    # 写入
    db.write('cpu', 1000, 45.2)
    db.write('cpu', 2000, 47.8)
    db.write('cpu', 3000, 44.1)
    db.write('mem', 1000, 67.3)
    db.write('mem', 2000, 65.9)

    # 查询
    pts = db.query('cpu', 1000, 3000)
    assert len(pts) == 3, f"Expected 3, got {len(pts)}"
    print(f"query: {pts}")

    # 聚合
    agg = db.aggregate('cpu', 1000, 3000)
    print(f"aggregate: {agg}")
    assert agg['count'] == 3
    assert abs(agg['min'] - 44.1) < 0.01

    # Flush
    db.flush()
    print("flush: OK")

    db.close()
    os.remove('test_native.tsdb')
    print("✅ tsdb_native 全部测试通过")

if __name__ == '__main__':
    if NATIVE_OK:
        test_native()
    else:
        print("⚠️ 跳过 C 原生模块测试")
        print("   可尝试: pip install pybind11")
        print("   然后手动编译 tsdb_bridge.cpp + tsdb.c")
