# DevOps #2：Docker 容器化

> 2026-05-17
> 前置：CI/CD #1

## 1. 为什么需要容器

```
传统部署：
  "代码在我机器上跑得好好的" → 环境差异
  每台服务器装 Python 3.10 + pip install + 配置

容器部署：
  Docker Image = 代码 + 依赖 + 系统库 + 配置
  一次构建，到处运行
  开发/测试/生产完全一致的环境
```

### 1.1 虚拟机 vs 容器

```
              ┌──────────────────┐
              │    容器           │
              │  App A  App B     │
              │  ├─────┼─────┤    │
              │  │libs │libs │    │
              │  └─────┴─────┘    │
              │  共享 OS 内核      │
              └──────────────────┘
                     ↓
               ┌───────────┐
               │ Host OS   │
               └───────────┘

              ┌──────────────────┐
              │  虚拟机           │
              │  VM1    VM2      │
              │  App    App      │
              │  OS     OS       │
              │  └─────┴─────┘   │
              │  Hypervisor      │
              └──────────────────┘

容器优势：
  启动：毫秒级（vs 虚拟机分钟级）
  密度：一台机器跑几十个容器
  大小：MB 级镜像

虚拟机优势：
  隔离性更强（独立内核）
  可以跑不同 OS
```

## 2. 量化系统的 Dockerfile

### 2.1 基础镜像

```dockerfile
# 多阶段构建：减小最终镜像体积

# === Stage 1: Build ===
FROM python:3.11-slim AS builder

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装量化特定依赖
RUN pip install --no-cache-dir \
    numpy==1.26.0 \
    pandas==2.1.0 \
    numba==0.59.0 \
    joblib==1.3.0 \
    scikit-learn==1.3.0

# === Stage 2: Runtime ===
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY scripts/ ./scripts/
COPY config/ ./config/

# 非 root 用户运行
RUN useradd -m -u 1000 quant && chown -R quant:quant /app
USER quant

ENTRYPOINT ["python", "src/monitor.py"]
```

### 2.2 轻量级方案（Alpine）

```dockerfile
FROM python:3.11-alpine

# Alpine 的 musl libc 可能和 numpy 兼容性问题
# 实测 numpy/numba 在 Alpine 上偶尔有莫名的 SIGSEGV
# 建议稳定环境用 slim 而不是 alpine

RUN apk add --no-cache gfortran openblas-dev
```

### 2.3 构建和运行

```bash
# 构建
docker build -t quant-engine:latest .

# 运行（交互模式，调试用）
docker run -it --rm \
  -v /host/data:/app/data \
  quant-engine:latest

# 后台运行（生产）
docker run -d --name quant-monitor \
  -v /host/logs:/app/logs \
  -v /host/config:/app/config \
  --restart unless-stopped \
  quant-engine:latest

# 查看日志
docker logs -f quant-monitor
```

## 3. Docker Compose（多服务编排）

### 3.1 量化系统 Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # 行情接收
  market-data:
    build: ./market
    volumes:
      - market_data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "from monitor import status; status()"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 策略引擎
  strategy-engine:
    build: ./strategies
    volumes:
      - market_data:/app/data:ro
      - ./config:/app/config:ro
    depends_on:
      - market-data
    restart: unless-stopped

  # 监控面板（如果有）
  # grafana:
  #   image: grafana/grafana:latest
  #   ports:
  #     - "3000:3000"

  # 通知服务
  notifier:
    build: ./notifier
    depends_on:
      - strategy-engine
    environment:
      FEISHU_WEBHOOK: "${FEISHU_WEBHOOK}"
    restart: unless-stopped

volumes:
  market_data:
```

## 4. Docker 网络

```
容器默认隔离的网络环境：

量化系统的服务间网络：
  market-data → 内部端口 8000
  strategy-engine → 连接到 market-data 的 8000
  notifier → 连接到 strategy-engine（咨询交易信号）

外部访问：
  只有需要暴露端口时才映射（-p 8080:8080）
```

```yaml
# 自定义网络
networks:
  quant-net:
    driver: bridge

services:
  market-data:
    networks:
      - quant-net
    ports:
      - "8080:8080"  # 对外暴露 HTTP 接口

  strategy-engine:
    networks:
      - quant-net
    # 不暴露端口，仅内部可访问
```

## 5. Docker 最佳实践

### 5.1 镜像瘦身

```dockerfile
# ❌ 大镜像（每层都增加体积）
FROM python:3.11
RUN pip install numpy pandas
RUN pip install scikit-learn
RUN pip install numba
# 镜像 ~1.5GB

# ✅ 小镜像
FROM python:3.11-slim
RUN pip install --no-cache-dir \
    numpy pandas scikit-learn numba \
    && rm -rf ~/.cache/pip
# 镜像 ~500MB

# 进一步优化：
#   多阶段构建
#   只复制需要的东西（不要 COPY .）
#   合并 RUN 指令
```

### 5.2 持久化数据

```bash
# 容器是无状态的——数据必须挂载到宿主机或 volume
docker volume create quant-data

# 三种挂载方式：
# 1. 绑定挂载（开发用）
docker run -v /host/path:/container/path

# 2. Volumes（生产用，docker 管理）
docker run -v quant-data:/app/data

# 3. tmpfs（临时，内存中）
docker run --tmpfs /app/tmp:noexec
```

### 5.3 资源限制

```bash
# 限制量化容器的资源使用
docker run -d \
  --memory="4g" \           # 最大 4GB 内存
  --memory-reservation="2g" # 预留 2GB
  --cpus="2.5" \             # 最多 2.5 核
  --pids-limit=100 \         # 最多 100 个进程
  quant-engine:latest
```

## 6. Windows 上的 Docker

### 6.1 WSL 2 后端

```
Windows 上运行 Docker 推荐用 WSL 2 后端：
  Docker Desktop → Settings → Use WSL 2 based engine

优势：
  性能接近原生 Linux
  可以直接访问 Windows 文件系统（/mnt/c）
  支持 Linux 容器

注意点：
  默认挂载 /mnt/c 跨文件系统性能差
  量化数据放到 WSL 内部文件系统 ~/data 而非 C 盘
```

### 6.2 Windows 容器

```powershell
# Windows 原生容器（非 WSL）
docker run -it mcr.microsoft.com/windows/servercore:ltsc2022

# 适用于：需要 Windows 的 .NET/Excel COM 操作
# 不适用于量化引擎（Linux 容器性能更好，社区更强）
```

## 总结

```
容器 = 环境一致性 + 可重复构建

量化 Dockerfile：
  多阶段构建 → 减小体积
  slim 基础镜像（非 alpine，兼容 numpy）
  挂载数据卷（容器不存持久数据）
  资源限制（内存/CPU/PID）

Compose 编排：
  market-data + strategy-engine + notifier
  内部网络隔离，仅暴露必要端口

最佳实践：
  瘦镜像（--no-cache-dir、多阶段、只复制需要的）
  非 root 运行
  健康检查
  restart unless-stopped
```
