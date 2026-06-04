# 逆向工程 — 第十四课：内存扫描器

## 核心原理

### VirtualQueryEx 枚举
```python
while addr < max_addr:
    mbi = MEMORY_BASIC_INFORMATION()
    VirtualQueryEx(hProcess, addr, &mbi, sizeof(mbi))
    if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) != 0:
        # 可读内存 → 加入扫描列表
    addr = mbi.BaseAddress + mbi.RegionSize
```

### 扫描策略

| 方法 | 描述 | 用例 |
|------|------|------|
| **精确字节扫描** | 按字节匹配 | 找已知数据 (字符串/结构体) |
| **通配符模式 (masked)** | 0xCC ???? 0x90 (mask: 0xFF 0x00 0x00 0xFF) | 找跳转/调用 |
| **字符串扫描 (UTF-8/16)** | 编码转换后匹配 | 找文本/配置/密码 |
| **数值扫描** | 按 DWORD/QWORD 值 | 找血量/金钱/坐标 |

## 性能优化

```
237 个内存区域 × 4KB 分片读取 = 逐片扫
Python 瓶颈: ReadProcessMemory → ctypes 调用开销
加速方案: 一次读整个 64KB 再查 → 比逐 4KB 快 16x
```

## 验证结果

| 测试 | 结果 |
|------|------|
| 枚举内存区域 | 237 个，全部正确分类 (Private/Mapped/Image) |
| 精确模式扫描 (VirtualQueryEx 函数) | 12 处匹配 (多个模块中同一 JMP 表) |
| 通配符扫描 `CC ???? 90` | 36 处匹配 |
| 字符串提取 | 100,885 个，包含 Python DLL 导出表 |

## 实际应用

- **游戏修改**: 搜血量/弹药 → 精确数值 → 定位内存地址
- **恶意软件分析**: 搜可疑字符串/配置 → 定位加密/通信代码
- **函数定位**: 搜已知字节模式 → 跨版本定位 API
- **两次扫描**: 第一次建立快照 → 改变状态 → 第二次过滤 → 缩小范围
