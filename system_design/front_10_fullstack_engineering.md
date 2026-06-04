# 🚀 前端/全栈 #10：全栈工程化与容器部署

> 本文档面向已有 HTML/CSS/JS/TS/React/Next.js 基础的全栈开发者，系统梳理从架构设计到生产部署的全链路工程化实践。

---

## 引言

从单页应用（SPA）到全栈应用，工程复杂度呈指数级增长。你需要同时管理：前端路由与状态、后端 API 与数据库、构建工具链、测试套件、Docker 容器、CI/CD 流水线，以及生产环境的监控与安全。第 10 课的目标是把这些碎片拼成一张完整的工程地图——**不只是能用，而是能交付**。

---

## 1. 全栈架构设计

### 1.1 前后端分离 vs BFF vs 微前端

**前后端分离（SPA + REST API）**

经典模式：前端 React/Next.js 独立部署，后端提供 REST/GraphQL API。适合大多数中型项目。

```
[Browser] ──HTTP──> [Frontend SPA] ──API──> [Backend API] ──DB──> [Database]
```

优势：清晰的责任边界，前后端可独立迭代。劣势：前端需要处理 loading/error/empty 三态，首屏性能受 API 延迟影响。

**BFF（Backend For Frontend）**

每个前端（Web/iOS/Android）有一个专属的后端网关，聚合底层微服务数据，输出"刚好够用"的响应。

```
[Web Browser] ──> [BFF for Web] ──> [Service A]
                                 ──> [Service B]
                                 ──> [Service C]
```

适合场景：多客户端需求差异大、后端采用微服务架构。Next.js API Routes 天然适合做 BFF。

**微前端**

将一个大型前端应用拆分为多个独立子应用，每个子应用可独立开发、部署、运行时组装。

```
[Shell App (Layout + Router)]
  ├── [Team A: 商品微应用]
  ├── [Team B: 订单微应用]
  └── [Team C: 用户微应用]
```

常见方案：Module Federation（Webpack 5）、qiankun（基于 single-spa）、Micro-app（京东）。适合大型团队协作场景，小团队不建议引入，代价大于收益。

### 1.2 API 设计：RESTful + GraphQL 混合

**RESTful 规范要点：**

```typescript
// ✅ 好设计：资源导向
GET    /api/users          // 列表
POST   /api/users          // 创建
GET    /api/users/:id      // 单条
PATCH  /api/users/:id      // 部分更新
DELETE /api/users/:id      // 删除

// 分页规范
GET /api/users?page=1&pageSize=20
// 响应
{
  "data": [...],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

**GraphQL 与 REST 混合策略：**

```typescript
// 简单查询/变更 → REST（直接、缓存友好）
// 复杂数据聚合 → GraphQL（避免 over-fetching / under-fetching）
// 项目不强制二选一，可以在 BFF 层做 GraphQL，对客户端暴露 REST

// Next.js API Route 示例：BFF 聚合
export async function GET(req: Request) {
  const [user, orders, preferences] = await Promise.all([
    fetchUser(req),
    fetchOrders(req),
    fetchPreferences(req),
  ]);
  return Response.json({ user, orders, preferences });
}
```

### 1.3 状态管理三层模型

```
┌─────────────────────────┐
│    URL 状态（SSR 友好）   │  ← 路由参数、search params
├─────────────────────────┤
│  服务端状态（Server State）│  ← React Query / SWR / tRPC
├─────────────────────────┤
│  客户端状态（Client State）│  ← Zustand / Jotai / Context
└─────────────────────────┘
```

**最佳实践：**

| 状态类型 | 存储位置 | 工具 | 持久化方式 |
|---------|---------|------|-----------|
| URL 参数 | `useSearchParams()` / `next/navigation` | 原生 | URL |
| 服务端数据 | 缓存层 | TanStack Query / SWR | 内存 + 持久化缓存 |
| UI 状态 | Zustand store | Zustand | localStorage（按需） |
| 表单状态 | React Hook Form | RHF | 本地 state |

```typescript
// URL 状态（Next.js App Router）
const searchParams = useSearchParams();
const tab = searchParams.get('tab') ?? 'overview';

// 服务端状态（TanStack Query）
const { data: posts } = useQuery({
  queryKey: ['posts', tab],
  queryFn: () => fetch(`/api/posts?tab=${tab}`).then(r => r.json()),
});

// 客户端状态（Zustand）
const useStore = create<{ sidebarOpen: boolean; toggle: () => void }>((set) => ({
  sidebarOpen: false,
  toggle: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

### 1.4 数据流：Server Actions vs tRPC vs 传统 REST

| 方案 | 类型安全 | 传输方式 | 适用场景 |
|-----|---------|---------|---------|
| **Server Actions** | ✅ 内置（form action 签名） | HTTP POST + form data | Next.js 全栈，表单提交 |
| **tRPC** | ✅ 端到端类型安全 | HTTP JSON | 全栈 TypeScript 项目 |
| **传统 REST** | 需工具链（zod + openapi） | HTTP | 多客户端、公开 API |

**Server Actions（Next.js 推荐）：**

```typescript
// app/actions.ts
'use server';

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string;
  const content = formData.get('content') as string;

  // 服务端验证
  if (!title || title.length < 2) {
    return { error: '标题至少2个字符' };
  }

  // 数据库操作
  const post = await db.post.create({ data: { title, content } });

  // 重新验证缓存
  revalidatePath('/posts');
  return { success: true, post };
}

// app/posts/new/page.tsx
export default function NewPostPage() {
  return (
    <form action={createPost}>
      <input name="title" required />
      <textarea name="content" required />
      <button type="submit">发布</button>
    </form>
  );
}
```

**tRPC（极致类型安全）：**

```typescript
// server/trpc/router.ts
export const appRouter = t.router({
  userById: t.procedure
    .input(z.string())
    .query(async ({ input }) => {
      return db.user.findUnique({ where: { id: input } });
    }),
  createUser: t.procedure
    .input(z.object({ name: z.string(), email: z.string().email() }))
    .mutation(async ({ input }) => {
      return db.user.create({ data: input });
    }),
});

// 客户端自动推断类型（无需手动定义 API 类型）
const user = await trpc.userById.query('u_001'); // 自动推导返回值类型
```

### 1.5 Monorepo 管理：Turborepo vs Nx vs PNPM Workspace

| 工具 | 核心特点 | 学习曲线 | 适合场景 |
|-----|---------|---------|---------|
| **PNPM Workspaces** | 原生 npm 包管理，磁盘高效 | 低 | 简单多包项目 |
| **Turborepo** | 智能缓存 + 并行构建 + 远程缓存 | 中 | 前端为主的中大型 Monorepo |
| **Nx** | 完整工具链（构建/测试/生成器） | 高 | 大型企业级全栈项目 |

**Turborepo 结构示例：**

```
my-app/
├── apps/
│   ├── web/          # Next.js 前端
│   ├── admin/        # 管理后台
│   └── api/          # Express 后端
├── packages/
│   ├── shared/       # 共享类型 & 工具函数
│   ├── ui/           # 组件库
│   └── config/       # ESLint / TS / Prettier 配置
├── turbo.json
└── pnpm-workspace.yaml
```

```yaml
# pnpm-workspace.yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

```jsonc
// turbo.json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],      // 依赖先构建
      "outputs": [".next/**", "dist/**"],
      "cache": true
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": []
    },
    "lint": {
      "outputs": []
    },
    "dev": {
      "cache": false,
      "persistent": true
    }
  }
}
```

**选择建议：** 小团队（<5人）用 PNPM Workspace 就够了；中型项目用 Turborepo 获得最佳开发者体验；大型组织用 Nx 获取完整工具链支持。

---

## 2. 容器化与开发环境

### 2.1 Docker 多阶段构建

多阶段构建的关键思想：**开发阶段需要完整工具链，生产阶段只需要运行时**。

**Next.js 应用 Dockerfile：**

```dockerfile
# ===== Stage 1: 依赖安装 =====
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

# ===== Stage 2: 构建 =====
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && pnpm build

# ===== Stage 3: 生产运行 =====
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# 只复制生产需要的产物
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

注意：`output: 'standalone'` 需在 `next.config.ts` 中开启：

```typescript
// next.config.ts
const nextConfig = {
  output: 'standalone', // 自动最小化生产镜像
};
export default nextConfig;
```

**静态前端（Nginx）Dockerfile：**

```dockerfile
# ===== Stage 1: 构建 =====
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# ===== Stage 2: Nginx 静态服务 =====
FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# nginx.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location /assets {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
}
```

### 2.2 Docker Compose：三件套（前端 + 后端 + 数据库）

```yaml
# docker-compose.yml
version: '3.8'

services:
  # 前端
  frontend:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
      target: runner
    ports:
      - '3000:3000'
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:4000
    depends_on:
      - backend
    restart: unless-stopped

  # 后端 API
  backend:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    ports:
      - '4000:4000'
    environment:
      - DATABASE_URL=postgres://user:pass@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  # 数据库
  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=myapp
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U user -d myapp']
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - '5432:5432'

  # 缓存
  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

启动命令：

```bash
# 构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f

# 停止并清理
docker compose down -v

# 只在特定服务上运行命令
docker compose exec backend npx prisma migrate dev
```

### 2.3 开发环境一致性：DevContainer

DevContainer 让整个团队使用相同的开发环境（Node 版本、系统工具、VS Code 插件），彻底解决"在我电脑上能跑"的问题。

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "My Fullstack App",
  "image": "mcr.microsoft.com/devcontainers/typescript-node:20",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/git:1": {}
  },
  "forwardPorts": [3000, 4000, 5432],
  "postCreateCommand": "corepack enable && pnpm install",
  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "bradlc.vscode-tailwindcss",
        "Prisma.prisma",
        "ms-azuretools.vscode-docker"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode"
      }
    }
  }
}
```

### 2.4 环境变量管理

```bash
# .env.local（本地开发，不提交到 git）
DATABASE_URL=postgres://user:pass@localhost:5432/myapp
REDIS_URL=redis://localhost:6379
NEXT_PUBLIC_API_URL=http://localhost:3000/api

# .env.production（生产环境，CI 中注入）
DATABASE_URL=postgres://user:pass@prod-db:5432/myapp
REDIS_URL=redis://prod-redis:6379
NEXT_PUBLIC_API_URL=https://api.example.com

# .env.example（模板，提交到 git）
DATABASE_URL=postgres://user:pass@localhost:5432/myapp
REDIS_URL=redis://localhost:6379
NEXT_PUBLIC_API_URL=http://localhost:3000/api
```

**密钥注入策略（按安全等级排序）：**

| 方法 | 安全等级 | 适用场景 |
|-----|---------|---------|
| `.env.local` 文件 | ⭐⭐ | 本地开发 |
| CI/CD Secrets（GitHub Actions Secrets） | ⭐⭐⭐⭐ | CI 流水线 |
| Docker Secrets（Swarm） | ⭐⭐⭐⭐⭐ | 容器编排 |
| Vault / AWS Secrets Manager | ⭐⭐⭐⭐⭐ | 企业级生产环境 |
| 运行时环境变量注入 | ⭐⭐⭐ | K8s/PaaS 部署 |

**重要规则：** `NEXT_PUBLIC_*` 前缀的变量会在构建时内联到 JS bundle 中，因此**永远不要**在 `NEXT_PUBLIC_` 前缀中存放密钥。真正的密钥只在服务器端运行时可用。
