# DevOps #1：CI/CD 流水线与自动化

> 2026-05-17
> 前置：Git 基础

## 1. CI/CD 的本质

CI/CD = 从代码到部署的自动化管道。

```
Dev ──→ 提交 ──→ CI（构建+测试）──→ CD（部署）
         Git        自动化                   自动化

核心收益：
  1. 消灭"在我机器上是好的"——统一构建环境
  2. 快速反馈——提交 5 分钟内知道是否有问题
  3. 可重复部署——每个版本都是可追溯的制品
```

### 1.1 三个核心阶段

- **Continuous Integration**：每次合并代码→自动构建+测试
- **Continuous Delivery**：通过 CI 的代码→自动部署到预发布/生产
- **Continuous Deployment**：通过 CI 的代码→直接部署到生产（无人工审批）

### 1.2 量化系统中的 Pipeline

```
量化策略开发 → 代码提交(PR) → 回测验证 → 参数优化 → 部署到实盘

CI 部分：
  ┌─ lint / type check（Pylint / mypy）
  ├─ 单元测试（pytest）
  ├─ 稳定性测试（给定数据输出是否稳定）
  └─ 回测验证（10 年数据是否通过）

CD 部分：
  ┌─ 策略参数更新
  ├─ 实盘监控重启
  └─ 回测结果发布
```

## 2. GitHub Actions（SaaS CI/CD）

### 2.1 基础 Pipeline

```yaml
# .github/workflows/quant-tests.yml
name: Quant Strategy Tests

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Lint with Ruff
        run: ruff check .
      
      - name: Type check with mypy
        run: mypy src/
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src --cov-report=xml
      
      - name: Run backtest smoke test
        run: |
          python scripts/backtest_smoke.py
```

### 2.2 优化：缓存依赖

```yaml
- name: Cache pip
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### 2.3 量化回测 Pipeline

```yaml
name: Quant Backtest CI

on:
  push:
    paths:
      - 'strategies/**'  # 只有策略文件变更才触发
      - 'tests/**'

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - name: Backtest - all strategies on last 500 days
        run: |
          python -m src.backtest --days 500 --output /tmp/smoke
      
      - name: Compare with baseline
        run: |
          python scripts/compare_baseline.py --new /tmp/smoke --baseline data/baseline.json
      
      - name: Alert on regression
        if: failure()
        run: |
          python scripts/notify_dev.py "回测回归！夏普比率下降超过 10%"
```

用路径过滤来节省 CI 资源。只改策略文件才跑完整回测，改文档不触发。

## 3. 自托管 Runner（Windows）

量化的 Python 回测需要 Windows？可以自建 Runner。

```bash
# 在 Windows 5070Ti 机上注册 Runner
# 下载 GitHub Actions Runner
./config.cmd --url https://github.com/your-org/quant-system
             --token YOUR_TOKEN
             --labels windows,nvidia

# 安装为服务自动启动
.\svc.cmd install
```

优势：可以直接访问本地 GPU（训练 RL Agent）和行情数据源。

## 4. 本地 CI（Linux/macOS）

### 4.1 pre-commit hooks

在提交前自动检查（本地 CI 第一道防线）：

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-json
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

```bash
pip install pre-commit
pre-commit install  # 安装到 .git/hooks
# 每次 git commit 自动触发检查
```

### 4.2 回测基线比对

CI 关键流程：新代码不能比旧代码差。

```python
# scripts/compare_baseline.py
import json

def compare(new_results: dict, baseline: dict):
    for strategy, metrics in new_results.items():
        old_sharpe = baseline[strategy]["sharpe_ratio"]
        new_sharpe = metrics["sharpe_ratio"]
        
        if new_sharpe < old_sharpe * 0.95:  # 下降超过 5%
            raise ValueError(
                f"{strategy} 夏普从 {old_sharpe:.2f} 降为 {new_sharpe:.2f}"
            )
        print(f"✅ {strategy}: {new_sharpe:.2f} (baseline: {old_sharpe:.2f})")
```

## 5. 量化系统的 CI 策略

### 5.1 分层测试

```
Layer 0（秒级）：
  ruff lint + mypy + pytest 单元测试
  每次 push 触发

Layer 1（分钟级）：
  500 天快速回测
  每次 PR 合并前触发

Layer 2（小时级）：
  完整参数搜索 + 10 年回测
  每日凌晨定时触发

Layer 3（非自动化）：
  人工审查策略逻辑
  kill switch 机制
```

### 5.2 制品管理

```
构建产物（可回溯的二进制包）：

1. 每次 CI 通过的代码 → 打包为 wheel
2. 标记版本号：git tag v2026-05-17-01
3. 发布到内部 PyPI 或 GitLab Packages

部署时：
  回滚 = 换一个 wheel 的版本号

不用 Git 做部署（Git 可以回滚代码，不代表可以回滚生产环境状态）。
```

### 5.3 版本号规范

```
语义化版本 + 天级标签：
  MAJOR.MINOR.PATCH-DATE

示例：
  v1.2.3-20260517
  v2.0.0-20260517

主要用于日志中追踪哪个版本产生了结果。
```

## 总结

```
CI/CD = 从提交到部署的自动化高速公路

量化系统 CI 分层：
  L0: lint + 单元测试（每次 push）
  L1: 快速回测（PR 前）
  L2: 全量回测（每日定时）
  L3: 人工审核

工具：
  GitHub Actions（SaaS）
  自托管 Runner（Windows/GPU）
  pre-commit hooks（本地）
  基线比对（防止/度退回）

最终目标：
  改动一个参数 → 自动测试 → 自动回测 → 通过后直接上线
  （人工只在三层自动化都通过后看一眼）
```
