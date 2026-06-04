"""
CUDA vs CPU 性能对比基准
需要 numba 和 CUDA 环境
"""
import numpy as np
import time

def run_cpu_benchmark(n=10_000_000):
    """CPU 基准"""
    a = np.random.randn(n).astype(np.float32)
    b = np.random.randn(n).astype(np.float32)
    
    # 预热
    _ = a + b
    
    t0 = time.perf_counter()
    for _ in range(10):
        c = a + b
    t1 = time.perf_counter()
    return (t1 - t0) / 10

def run_numpy_benchmark(n=10_000_000):
    """NumPy SIMD 基准"""
    a = np.random.randn(n).astype(np.float32)
    b = np.random.randn(n).astype(np.float32)
    
    _ = np.add(a, b)
    
    t0 = time.perf_counter()
    for _ in range(100):
        c = np.add(a, b)
    t1 = time.perf_counter()
    return (t1 - t0) / 100

def run_gpu_benchmark(n=10_000_000):
    """GPU CUDA 基准"""
    from numba import cuda
    import math
    
    @cuda.jit
    def vector_add(a, b, c):
        idx = cuda.grid(1)
        if idx < a.size:
            c[idx] = a[idx] + b[idx]
    
    a = np.random.randn(n).astype(np.float32)
    b = np.random.randn(n).astype(np.float32)
    c = np.zeros_like(a)
    
    d_a = cuda.to_device(a)
    d_b = cuda.to_device(b)
    d_c = cuda.device_array_like(c)
    
    threads = 256
    blocks = (n + threads - 1) // threads
    
    # 预热
    vector_add[blocks, threads](d_a, d_b, d_c)
    cuda.synchronize()
    
    t0 = time.perf_counter()
    for _ in range(100):
        vector_add[blocks, threads](d_a, d_b, d_c)
    cuda.synchronize()
    t1 = time.perf_counter()
    return (t1 - t0) / 100

def run_reduction_benchmark(n=10_000_000):
    """GPU Reduction 基准"""
    from numba import cuda
    
    @cuda.jit
    def reduce_sum(arr, out):
        sdata = cuda.shared.array(256, dtype=np.float32)
        tid = cuda.threadIdx.x
        idx = cuda.blockIdx.x * cuda.blockDim.x + tid
        
        sdata[tid] = arr[idx] if idx < arr.size else 0.0
        cuda.syncthreads()
        
        s = cuda.blockDim.x // 2
        while s > 0:
            if tid < s:
                sdata[tid] += sdata[tid + s]
            cuda.syncthreads()
            s //= 2
        
        if tid == 0:
            out[cuda.blockIdx.x] = sdata[0]
    
    a = np.random.randn(n).astype(np.float32)
    threads = 256
    blocks = (n + threads - 1) // threads
    partial = np.zeros(blocks, dtype=np.float32)
    
    d_a = cuda.to_device(a)
    d_partial = cuda.to_device(partial)
    
    reduce_sum[blocks, threads](d_a, d_partial)
    cuda.synchronize()
    
    t0 = time.perf_counter()
    for _ in range(100):
        reduce_sum[blocks, threads](d_a, d_partial)
    cuda.synchronize()
    t1 = time.perf_counter()
    return (t1 - t0) / 100

if __name__ == "__main__":
    print("=" * 50)
    print("CUDA 性能基准测试")
    print("=" * 50)
    
    n = 10_000_000
    
    print(f"\n数据量: {n:,} 个 float32 ({n*4/1024/1024:.1f} MB)")
    print("-" * 40)
    
    cpu_t = run_cpu_benchmark(n)
    numpy_t = run_numpy_benchmark(n)
    print(f"CPU Python Loop: {cpu_t*1000:.3f} ms")
    print(f"CPU NumPy SIMD:  {numpy_t*1000:.3f} ms")
    
    try:
        gpu_t = run_gpu_benchmark(n)
        print(f"GPU CUDA:        {gpu_t*1000:.3f} ms")
        print(f"CPU/GPU 加速比:  {cpu_t/gpu_t:.1f}x")
        print(f"NumPy/GPU 加速比: {numpy_t/gpu_t:.1f}x")
        
        reduc_t = run_reduction_benchmark(n)
        print(f"\nGPU Reduction:   {reduc_t*1000:.3f} ms")
    except Exception as e:
        print(f"\nGPU 测试失败: {e}")
        print("请确保 CUDA 环境已配置")
