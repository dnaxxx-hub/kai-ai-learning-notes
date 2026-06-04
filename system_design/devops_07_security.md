# DevOps #7：安全实践

> 2026-05-17
> 前置：IaC #6

## 1. 量化系统的攻击面

```
┌─────────────────────────────────────────┐
│  量化系统的安全维度                        │
├─────────────────────────────────────────┤
│  代码安全  │ 依赖漏洞、代码注入            │
│  数据安全  │ 行情数据、策略参数泄露        │
│  网络安全  │ API 密钥、WebSocket 劫持     │
│  运行安全  │ 容器逃逸、提权攻击            │
│  密钥安全  │ 硬编码密钥、日志泄露密钥      │
│  供应链安全│ pip 包被篡改、镜像后门        │
└─────────────────────────────────────────┘
```

## 2. 依赖安全

### 2.1 依赖检查

```bash
# pip-audit — 扫描已知漏洞
pip install pip-audit
pip-audit --requirement requirements.txt

# 输出示例：
# Found 2 known vulnerabilities:
# Package: numpy (1.24.0) --> fix: 1.25.0
# Package: requests (2.28.0) --> fix: 2.31.0

# Safety CLI — 持续监控
pip install safety
safety check -r requirements.txt
```

### 2.2 CI 中集成

```yaml
# GitHub Actions
- name: Security audit
  run: |
    pip install pip-audit
    pip-audit --requirement requirements.txt --format json | tee security-report.json
    
- name: Fail on critical
  run: |
    python -c "
    import json
    report = json.load(open('security-report.json'))
    critical = [v for v in report['vulnerabilities'] if v['severity'] == 'CRITICAL']
    if critical:
        for v in critical:
            print(f'❌ CRITICAL: {v[\"package\"]} {v[\"version\"]} - {v[\"advisory\"]}')
        exit(1)
    "
```

### 2.3 依赖锁定

```bash
# pip freeze 锁定精确版本
pip freeze > requirements-lock.txt

# requirements.txt（宽松，兼容）
# requirements-lock.txt（精确，生产用）

# CI 中使用锁文件构建（可复现构建）
pip install -r requirements-lock.txt --no-deps
```

## 3. 密钥管理最佳实践

### 3.1 不要做的事

```python
# ❌ 密钥硬编码
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# ❌ 密钥在 Git 历史中
# 即使后来删除 .env，Git history 里永远有

# ❌ 密钥在日志中
logger.info(f"Using webhook: {FEISHU_WEBHOOK}")  # 泄露！
```

### 3.2 正确做法

```python
# ✅ 环境变量
import os
feishu_webhook = os.environ.get("FEISHU_WEBHOOK")
if not feishu_webhook:
    raise RuntimeError("FEISHU_WEBHOOK 环境变量未设置")

# ✅ 密钥过滤器（防止不小心打印）
import re

class SecretFilter(logging.Filter):
    def __init__(self):
        self.secrets = [
            os.environ.get("FEISHU_WEBHOOK", ""),
            os.environ.get("DB_PASSWORD", ""),
        ]
    
    def filter(self, record):
        for secret in self.secrets:
            if secret and secret in record.getMessage():
                record.msg = record.msg.replace(secret, "***REDACTED***")
        return True

logging.getLogger().addFilter(SecretFilter())
```

## 4. 网络安全

### 4.1 API 限流

```python
# 防止 API 请求频率过高被限或被 Ban
import time
from functools import wraps

def rate_limit(max_per_second: int):
    min_interval = 1.0 / max_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 使用
class StockAPI:
    @rate_limit(max_per_second=5)  # 每秒最多 5 次请求
    def get_quote(self, symbol: str):
        # 对 qt.gtimg.cn 的请求...
```

### 4.2 请求验证

```python
# 对 API 响应的基本验证

def validate_quote_response(data: dict) -> bool:
    """验证行情响应是否合法"""
    required_fields = ['code', 'name', 'price']
    for field in required_fields:
        if field not in data:
            logger.warning(f"行情响应缺少字段: {field}")
            return False
    
    price = data.get('price', 0)
    if not isinstance(price, (int, float)) or price <= 0:
        logger.warning(f"行情价格异常: {price}")
        return False
    
    return True
```

## 5. 容器安全

### 5.1 最小权限

```dockerfile
# ❌ root 运行
FROM python:3.11-slim
COPY . /app
RUN pip install -r requirements.txt
CMD ["python", "monitor.py"]

# ✅ 非 root 用户
FROM python:3.11-slim

RUN groupadd -r quant && useradd -r -g quant quant

WORKDIR /app
COPY . /app
RUN pip install --user -r requirements.txt && \
    chown -R quant:quant /app

USER quant
CMD ["python", "monitor.py"]
```

### 5.2 只读文件系统

```dockerfile
# 容器只读（仅挂载可写卷）
docker run \
  --read-only \
  --tmpfs /app/data:rw,noexec,nosuid,size=100m \
  --tmpfs /app/tmp:rw,noexec,nosuid,size=50m \
  quant-engine:latest
```

### 5.3 镜像签名

```bash
# Docker Content Trust
export DOCKER_CONTENT_TRUST=1
docker build -t quant-engine:latest .
docker push quant-engine:latest  # 推送时会签名

# 验证
docker trust inspect quant-engine:latest --pretty
```

## 6. 审计与追溯

### 6.1 操作审计日志

```python
# 所有关键操作都记录
class AuditLog:
    def __init__(self):
        self.logger = logging.getLogger('audit')
        
    def strategy_change(self, user: str, strategy: str, changes: dict):
        self.logger.info("STRATEGY_CHANGE", extra={
            "action": "strategy_update",
            "user": user,
            "strategy": strategy,
            "changes": changes,
            "timestamp": datetime.now().isoformat()
        })
        
    def trade_override(self, user: str, order_id: str, action: str):
        self.logger.info("TRADE_OVERRIDE", extra={
            "action": "manual_intervention",
            "user": user,
            "order_id": order_id,
            "override": action,
            "timestamp": datetime.now().isoformat()
        })
```

### 6.2 Git 提交规范

```bash
# scoped commits - 更容易追溯问题

# ✅ 好
feat(strategy): add trailing stop to bollinger
fix(monitor): handle None price in quote parser
chore(deps): bump numpy to 1.26.1

# ❌ 不好
update stuff
fix bug
WIP
```

## 7. 恢复与备份

### 7.1 备份策略

```python
# 配置文件的定期备份
import shutil
from pathlib import Path

def backup_config():
    """每日备份配置文件"""
    today = datetime.now().strftime("%Y%m%d")
    src = Path("config")
    dst = Path(f"backups/config_{today}")
    
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.yaml"):
        shutil.copy2(f, dst / f.name)
    
    # 清理 30 天前的备份
    for old in Path("backups").glob("config_*"):
        if (datetime.now() - datetime.fromtimestamp(old.stat().st_mtime)).days > 30:
            shutil.rmtree(old)
```

### 7.2 恢复演练

```bash
# 从零恢复到正常运行

恢复步骤：
  1. 重建环境：git clone + pip install（确认 requirements-lock.txt 可用）
  2. 恢复配置：从备份复制 config/
  3. 恢复数据：从备份复制行情数据（或重新下载）
  4. 设置密钥：填入 .env
  5. 验证：回测昨天的数据——结果应与之前一致
```

## 总结

```
安全不是功能——是设计原则

量化系统的安全优先级：
  P0：密钥不泄露（环境变量、日志过滤、Git 无历史）
  P0：代码安全（依赖扫描、容器非 root）
  P1：数据安全（备份、恢复演练）
  P1：网络安全（API 限流、请求验证）
  P2：审计日志（关键操作可追溯）
  P2：备份策略（每日 + 30 天保留）

检视点：如果你突然失去这台电脑，多久能恢复？
答案应该是 < 2 小时，有 git + 环境变量 + 备份配置。
```
