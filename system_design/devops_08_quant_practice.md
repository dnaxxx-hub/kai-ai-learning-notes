# DevOps 量化实践：Docker + GitHub Actions CI

> 学习日期：2026-05-18 | 行数：第8课（量化落地）

## Docker 容器化

### 量化引擎 Dockerfile 架构
```
FROM python:3.11-slim        # 最小镜像
├── tzdata / Asia/Shanghai    # 时区设置
├── WORKDIR /app              # 工作目录
├── requirements.txt → pip    # 依赖层（缓存优化）
├── COPY . .                  # 源码复制
└── CMD ["python", "mini_realtime.py"]
```

### 最佳实践
- **分层缓存**：先复制 requirements.txt 安装pip依赖，再复制代码（docker build缓存层）
- **最小镜像**：python:3.11-slim 只有100MB+，比full小5倍
- **环境变量**：`PYTHONUNBUFFERED=1`（日志实时输出）、`PYTHONDONTWRITEBYTECODE=1`（不留.pyc）

## GitHub Actions CI

### Backtest 工作流结构
```yaml
name: Quant Backtest CI
on: [push, pull_request] → main

jobs:
  backtest:
    steps:
    1. actions/checkout@v4
    2. actions/setup-python@v5 with cache
    3. pip install (pandas/numpy/httpx/pytest)
    4. Run backtest (python -c 内联脚本)
    5. Generate report summary ($GITHUB_STEP_SUMMARY)
    6. Optional pytest
```

### CI 特点
- **容错设计**：`continue-on-error: true`，CI环境缺少数据源时不会阻塞
- **内联验证**：直接用`python -c`导入模块 + 快速回测，不依赖外部脚本
- **报告输出**：`$GITHUB_STEP_SUMMARY`生成Markdown摘要表格
- **缓存**：`cache: pip` + `cache-dependency-path`加速pip安装

### 关键经验
- Docker Desktop not available on Windows 11? → 基于WSL2运行或直接用裸机
- GitHub Actions只在云端push时触发，本地验证靠`npx hardhat test`或`python backtest_v3.py`
- `continue-on-error: true`需要配合`if: always()`确保后续步骤执行
