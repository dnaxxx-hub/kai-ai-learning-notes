# 游戏性能优化

> 游戏开发第7课 — 渲染优化、CPU优化和包体瘦身

## 渲染优化核心

### Draw Call 合并

CPU → GPU 每次 Draw Call 的成本：
- CPU 端：提交缓冲区、状态切换、shader绑定
- GPU 端：管线切换、显存加载
- 移动端尤为昂贵

**目标**：尽量减少 Draw Call 数量。

```cpp
// 批次合并示例：静态批处理
struct StaticBatch {
    std::vector<Mesh> meshes;     // 同材质网格
    std::vector<Matrix4x4> transforms; // 世界矩阵
    bool isDirty;                 // 位置变更标记
};

void RenderBatched(const StaticBatch& batch) {
    // 1. 设置材质（只一次）
    SetMaterial(batch.meshes[0].material);
    
    // 2. 提交合并的几何数据
    BindVertexBuffer(batch.combinedVB);   // 合并顶点
    BindIndexBuffer(batch.combinedIB);    // 合并索引
    
    // 3. GPU Instancing
    DrawIndexedInstanced(
        batch.combinedIB.count,
        batch.transforms.size(),  // instance数
        batch.transforms.data()   // per-instance数据
    );
}
```

### 批处理类型对比
| 方式 | 条件 | 性能收益 | 内存成本 |
|------|------|---------|---------|
| 静态批处理 | 静态物体+同材质 | 极高 | 高（合并网格） |
| GPU Instancing | 同网格+同材质 | 高 | 低 |
| 动态批处理 | 小顶点+同材质 | 中 | 零 |
| SRP Batcher | URP/HDRP可用 | 高（现代） | 低 |

### LOD（Level of Detail）

```
距离较远 → 低面数模型（节省性能）
距离较近 → 高面数模型（保持画质）

LOD 0: 10000 面   [0~20米]
LOD 1: 5000 面    [20~50米]
LOD 2: 1000 面    [50~100米]
LOD 3: 公告板     [100米以上]
```

### LOD 选取算法

```python
def select_lod(camera_pos, object_pos, lod_distances, lod_sizes):
    """根据距离和屏幕大小选择LOD等级"""
    distance = |camera_pos - object_pos|
    
    # 屏幕大小估计（投影后占屏比例）
    screen_size = lod_sizes[0] / (distance + 1e-6)
    
    # 阈值判断
    if screen_size > 0.1:         # 占屏幕10%以上
        return 0                   # LOD0
    elif screen_size > 0.05:      # 5%-10%
        return 1                   # LOD1
    elif screen_size > 0.02:      # 2%-5%
        return 2                   # LOD2
    else:
        return 3                   # 公告板
```

## 纹理与内存优化

### 纹理压缩

| 格式 | 平台 | 压缩比 | 质量 |
|------|------|--------|------|
| ASTC | Android/iOS（主流） | 4:1~8:1 | 好 |
| ETC2 | Android（兼容） | 6:1 | 中 |
| PVRTC | 旧iOS设备 | 8:1 | 差 |
| BC1-7 | PC/Console | 4:1~8:1 | 好 |

### 纹理流送（Texture Streaming）
- 只加载当前可见的纹理缓存到显存
- 根据与相机的距离和纹理大小优先加载
- 大纹理（4K）只在近距离使用，远距离自动降级

## CPU 优化

### Profiling 优先
**不要在猜测中优化，永远先 Profile。**

```python
# 性能分析的黄金步骤
1. 设定性能目标（30/60/120fps）
2. 用Profiler找到热点（哪个系统占用最多CPU时间）
3. 分析热点根因（是Update太慢还是GC触发？）
4. 针对性优化
5. 重新Profile验证
```

### 常见CPU热点
| 问题 | 表现 | 解决 |
|------|------|------|
| 过多的Update | 大量MonoBehavior.Update | 使用事件驱动 |
| GC垃圾回收 | 帧率周期性骤降 | 对象池 + 避免GC.Alloc |
| 物理计算 | Physics.Simulate 耗时高 | 降低物理频率 |
| 动画系统 | Animator.Update 慢 | 简化动画层 |
| 寻路计算 | NavMesh更新 | 异步/分帧处理 |

### 对象池模式

```cpp
class ObjectPool<T> {
    std::vector<T> _pool;
    size_t _activeCount = 0;
    
    T Acquire() {
        if (_activeCount >= _pool.size()) {
            // 扩展池
            _pool.push_back(T::Create());
        }
        return _pool[_activeCount++];
    }
    
    void Release(T obj) {
        obj.Reset();
        std::swap(_pool[_activeCount - 1], _pool[_activeCount]);
        _activeCount--;
    }
};
```

## 资源包与包体优化

### 资源包策略

| 模式 | 适用 | 说明 |
|------|------|------|
| 内置资源 | 必须内容 | 安装包包含 |
| 按需下载 | 非核心资源 | 首次使用下载 |
| 分阶段下载 | 大型游戏 | 新手关卡先下载，后续后台 |

### 包体瘦身技巧
1. **纹理压缩**：ASTC 8×8 替代未压缩
2. **音频压缩**：Vorbis/Opus 替代 PCM/WAV
3. **网格压缩**：Mesh Compression
4. **剥离无用资源**：根据平台剥离Editor资源
5. **AssetBundle 分包**：按场景/功能分包

## Shader 优化

### 移动端 Shader 注意事项
- 避免 `discard` / `clip` — 打断Early-Z
- 减少纹理采样次数
- 用 `half` 替代 `float` 声明变量
- 不要用循环（GPU不支持复杂循环）

```hlsl
// 不推荐（移动端）
float4 frag_full(float2 uv) : SV_Target {
    float4 a = tex2D(_MainTex, uv);
    for(int i=0; i<_SampleCount; i++) {
        a += tex2D(_DetailTex, uv + _Offset[i]);
    }
    return a / _SampleCount;
}

// 优化后
half4 frag_fast(half2 uv) : SV_Target {
    half4 color = tex2D(_MainTex, uv);
    // 固定次数展开，避免循环
    color += tex2D(_DetailTex, uv + half2(0.01, 0.0));
    color += tex2D(_DetailTex, uv - half2(0.01, 0.0));
    color += tex2D(_DetailTex, uv + half2(0.0, 0.01));
    color += tex2D(_DetailTex, uv - half2(0.0, 0.01));
    return color * 0.2;
}
```

## GPU 优化重点

| 瓶颈 | 表现 | 诊断 | 解决 |
|------|------|------|------|
| Fill Rate | 高分辨率+复杂shader | GPU占用率100% | 降低分辨率/简化shader |
| 带宽 | 纹理过大/过多 | GPU Busy+内存高 | 纹理压缩/LOD |
| 顶点 | 高面数模型 | GPU Vertex花费高 | LOD/剔除 |
| VSync | 帧率天花板 | FrameTime = 16.6ms | VSync关闭 |

## 总结
- Draw Call 合并是最重要的渲染优化手段
- LOD+纹理压缩+纹理流送覆盖大部分游戏场景
- CPU优化需要先Profile再动手，对象池是万能药
- Shader优化特别注意移动端限制
- 包体瘦身从纹理和音频开始
