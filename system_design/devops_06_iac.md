# DevOps #6：基础设施即代码（IaC）

> 2026-05-17
> 前置：日志聚合 #5

## 1. 什么是 IaC

### 1.1 手动部署的问题

```
传统方式：
  用 SSH 登录服务器
  手打命令安装软件
  手动修改配置文件
  记不清哪个配置改了没改

问题：
  环境漂移（"我记得改过这个……"）
  不可复现（"上次怎么配出来的？"）
  变更不可追溯（"谁动了什么？"）
  恢复时间长（从零重建要半天）

IaC 方案：
  配置写在代码里
  Git 管理变更历史
  一句命令重建环境
  环境一致性保障
```

### 1.2 IaC 工具定位

```
Terraform / OpenTofu：基础设施编排（创建云资源）
  → "给我建 3 台服务器 + 1 个数据库 + 网络"

Ansible / Puppet / Chef：配置管理
  → "在这台服务器上装 Python 3.11、配置环境变量、部署代码"

Docker Compose / K8s：应用部署
  → "启动量化引擎 + 行情接收 + 监控"

量化系统当前阶段：Docker Compose + 脚本化配置就够用
  未来需要多台机器 → Terraform + Ansible
```

## 2. 配置管理方案

### 2.1 环境变量管理

```bash
# .env 文件（不提交到 Git！在 .gitignore 中忽略）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
DB_PASSWORD=password123
STOCK_SYMBOLS=000009,002332

# 根据不同环境加载
ENVIRONMENT=production  # 或 development
```

### 2.2 YAML 配置文件

```yaml
# config/strategies.yaml
strategies:
  bollinger:
    enabled: true
    window: 14
    std_multiplier: 2.0
    stop_loss: 0.08
    
  rsi:
    enabled: true
    window: 14
    oversold: 30
    overbought: 70
    
  macd:
    enabled: false  # 暂时关闭
    fast: 12
    slow: 26
    signal: 9

# config/monitor.yaml
monitor:
  symbols:
    - code: "000009"
      name: "中国宝安"
      cost: 9.45
    - code: "002332"
      name: "仙琚制药"
      cost: 9.20
  
  check_interval: 30  # 分钟
  
  alerts:
    stop_loss: 0.08
    trailing_stop: 0.08
    limit_up: 0.095
```

配置在启动时加载：

```python
import yaml
from pathlib import Path

class Config:
    def __init__(self, env: str = "development"):
        self.env = env
        self.data = {}
        self.load_all()
        
    def load_all(self):
        config_dir = Path("config")
        for file in config_dir.glob("*.yaml"):
            with open(file) as f:
                name = file.stem
                self.data[name] = yaml.safe_load(f)
                
    def get(self, path: str):
        keys = path.split(".")
        value = self.data
        for key in keys:
            value = value[key]
        return value
```

### 2.3 配置验证

```python
# 启动时验证配置完整性
from pydantic import BaseModel, Field

class StrategyConfig(BaseModel):
    enabled: bool
    window: int = Field(gt=0, le=200)
    std_multiplier: float = Field(default=2.0, ge=0.5, le=5.0)
    stop_loss: float = Field(default=0.08, ge=0.0, le=0.5)

class MonitorConfig(BaseModel):
    symbols: list[str] = Field(min_length=1)
    check_interval: int = Field(default=30, ge=5)
    alerts: dict

# 验证
for name, cfg in config['strategies'].items():
    if cfg['enabled']:
        StrategyConfig(**cfg)
        print(f"✅ 策略 {name} 配置验证通过")
```

## 3. 脚本化部署

### 3.1 部署脚本

```bash
#!/bin/bash
# deploy.sh — 量化系统部署脚本

set -euo pipefail  # 任何错误即终止

ENV=${1:-development}
echo "🚀 部署环境: $ENV"

# 1. 从 Git 拉最新代码
echo "📦 拉取代码..."
git pull origin main

# 2. 安装依赖
echo "🐍 安装 Python 依赖..."
pip install -r requirements.txt --quiet

# 3. 配置验证
echo "✅ 验证配置..."
python scripts/validate_config.py

# 4. 运行测试
echo "🧪 运行测试..."
pytest tests/ -v --tb=short

# 5. 回测基线验证
echo "📊 回测验证..."
python scripts/backtest_smoke.py && echo "✅ 回测通过"

# 6. 重启服务
echo "🔄 重启监控服务..."
systemctl restart quant-monitor
```

### 3.2 回滚脚本

```bash
#!/bin/bash
# rollback.sh — 回滚到指定版本

VERSION=${1:-"HEAD~1"}
echo "⏪ 回滚到: $VERSION"

git revert --no-commit $VERSION
git commit -m "rollback: $VERSION"
git push origin main

# 自动使用旧版本重新部署
./deploy.sh production
```

### 3.3 Windows 部署脚本

```powershell
# deploy.ps1 — Windows 部署脚本
param(
    [string]$Env = "development"
)

Write-Host "🚀 部署环境: $Env" -ForegroundColor Cyan

# 1. 更新代码
git pull origin main

# 2. 安装/更新依赖
pip install -r requirements.txt --quiet

# 3. 验证
python scripts/validate_config.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 配置验证失败" -ForegroundColor Red
    exit 1
}

# 4. 回测
python scripts/backtest_smoke.py

# 5. 重启
# （Windows 上重启服务/进程的方式）
Get-Process "python" -ErrorAction SilentlyContinue | Stop-Process
Start-Process python -ArgumentList "src/monitor.py"
Write-Host "✅ 部署完成" -ForegroundColor Green
```

## 4. 配置变更管理

### 4.1 配置版本化

```
配置文件也应该版本管理（不含密钥）：

config/
├── development/
│   ├── strategies.yaml
│   ├── monitor.yaml
│   └── logging.yaml
├── production/
│   ├── strategies.yaml
│   ├── monitor.yaml
│   └── logging.yaml

.env（不提交）
.env.example（示例，提交）
```

### 4.2 配置迁移

配置结构变更时需要迁移方案：

```python
# config_migrations.py
MIGRATIONS = [
    {
        "version": "1.0",
        "description": "Initial configuration",
        "upgrade": lambda cfg: cfg
    },
    {
        "version": "2.0",
        "description": "Add trailing_stop to bollinger",
        "upgrade": lambda cfg: {
            **cfg,
            "strategies": {
                **cfg["strategies"],
                "bollinger": {
                    **cfg["strategies"]["bollinger"],
                    "trailing_stop": 0.08
                }
            }
        }
    },
]

def upgrade_config(cfg: dict, from_version: str, to_version: str):
    """逐版本升级配置（不跳版本）"""
    versions = [m for m in MIGRATIONS 
                if from_version < m["version"] <= to_version]
    for migration in sorted(versions, key=lambda x: x["version"]):
        cfg = migration["upgrade"](cfg)
        print(f"  ✅ 配置升级到 {migration['version']}: {migration['description']}")
    return cfg
```

## 5. 密钥管理

### 5.1 基本原则

```
永远不要把密钥提交到 Git
.env 在 .gitignore 中
使用环境变量或专门的密钥管理服务

密钥类别：
  1. 环境变量（当前合适）
  2. .env 文件（被 gitignore）
  3. Windows Credential Manager（当前 Windows 平台）
  4. HashiCorp Vault（团队级）
```

### 5.2 Windows 凭据管理器

```powershell
# Windows 环境用凭据管理器存储敏感信息

# 写入
cmdkey /add:quantFeishuWebhook /user:quant /pass:"https://open.feishu.cn/..."

# 读取（Python 代码中）
import subprocess
import re

def get_secret(name: str) -> str:
    """从 Windows Credential Manager 读取凭据"""
    result = subprocess.run(
        ['cmdkey', '/list', name],
        capture_output=True, text=True
    )
    # 解析输出中的密码字段
    match = re.search(r'目标: .+?\n  类型: 通用凭据\n  用户: quant\n  密码: (.+)', 
                      result.stdout, re.MULTILINE)
    return match.group(1) if match else ""
```

## 总结

```
IaC = Infrastructure as Code

核心原则：
  对环境的所有操作记录在代码中
  Git 管理所有变更
  配置验证在部署前进行
  密钥绝不提交

当前阶段（单机）：
  Docker Compose + .env + 脚本部署
  YAML 配置（版本管理）+ Pydantic 验证

未来阶段（多机）：
  Terraform（云资源）
  Ansible（配置管理）
  HashiCorp Vault（密钥管理）
```
